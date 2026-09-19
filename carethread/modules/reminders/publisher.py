"""Notification delivery adapters and implementations for M5 Reminders.

Provides Amazon SNS integration and an in-memory mock with privacy leak
detection to enforce HIPAA-compliant non-sensitive messaging.
"""

from abc import ABC, abstractmethod
import logging
import os
import re
from typing import Any, Dict, List, Optional

from carethread.modules.reminders.schemas import PublishResult

logger = logging.getLogger(__name__)

# List of sensitive clinical terms strictly forbidden in external push/SMS notifications
DISALLOWED_SENSITIVE_KEYWORDS = [
    "diagnosis",
    "cad",
    "coronary",
    "diabetes",
    "hypertension",
    "creatinine",
    "hemoglobin",
    "troponin",
    "potassium",
    "glucose",
    "cancer",
    "hiv",
    "carcinoma",
    "infarction",
    "mg/dl",
    "mmol/l",
]


class NotificationPublisherInterface(ABC):
    """Abstract interface for publishing reminder notifications to end-users."""

    @abstractmethod
    def publish(
        self,
        destination: str,
        message: str,
        subject: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> PublishResult:
        """Deliver notification to the target destination (SNS topic or endpoint)."""
        pass


class MockNotificationPublisher(NotificationPublisherInterface):
    """Deterministic in-memory publisher for testing and local verification."""

    def __init__(self) -> None:
        self.published_messages: List[Dict[str, Any]] = []
        self.fail_all: bool = False
        self.fail_destinations: set = set()

    def publish(
        self,
        destination: str,
        message: str,
        subject: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> PublishResult:
        # Check for privacy violations
        self.validate_privacy(message)

        if self.fail_all or destination in self.fail_destinations:
            err_msg = f"Simulated delivery failure to {destination}"
            logger.warning("Mock publisher failed delivery: %s", err_msg)
            return PublishResult(
                success=False,
                destination=destination,
                error=err_msg,
            )

        msg_id = f"mock-msg-{len(self.published_messages) + 1}"
        record = {
            "message_id": msg_id,
            "destination": destination,
            "message": message,
            "subject": subject,
            "attributes": attributes or {},
        }
        self.published_messages.append(record)
        logger.info("Mock publisher delivered reminder %s to %s", msg_id, destination)

        return PublishResult(
            success=True,
            message_id=msg_id,
            destination=destination,
        )

    def validate_privacy(self, message: str) -> None:
        """Validate that message does not contain sensitive health details."""
        lower_msg = message.lower()
        for kw in DISALLOWED_SENSITIVE_KEYWORDS:
            # Word boundary search to avoid accidental substring matches
            if re.search(r"\b" + re.escape(kw) + r"\b", lower_msg):
                raise ValueError(
                    f"Privacy violation: Outgoing notification contains sensitive clinical term '{kw}'"
                )

    def clear(self) -> None:
        self.published_messages.clear()
        self.fail_all = False
        self.fail_destinations.clear()


class SNSNotificationPublisher(NotificationPublisherInterface):
    """Real Amazon SNS publisher adapter."""

    def __init__(
        self,
        boto_client: Optional[Any] = None,
        default_topic_arn: Optional[str] = None,
    ) -> None:
        self._client = boto_client
        self.default_topic_arn = default_topic_arn or os.getenv(
            "REMINDER_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:CareThreadReminderTopic"
        )

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3
            self._client = boto3.client("sns")
        return self._client

    def publish(
        self,
        destination: str,
        message: str,
        subject: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> PublishResult:
        target = destination or self.default_topic_arn
        params: Dict[str, Any] = {
            "Message": message,
        }
        if target.startswith("arn:aws:sns:"):
            params["TopicArn"] = target
        elif target.startswith("+"):
            params["PhoneNumber"] = target
        else:
            params["TargetArn"] = target

        if subject:
            params["Subject"] = subject[:100]  # SNS subject max length is 100

        if attributes:
            sns_attrs = {}
            for k, v in attributes.items():
                sns_attrs[k] = {
                    "DataType": "String",
                    "StringValue": str(v),
                }
            params["MessageAttributes"] = sns_attrs

        try:
            response = self.client.publish(**params)
            msg_id = response.get("MessageId", "sns-unknown-id")
            logger.info("Published SNS notification %s to %s", msg_id, target)
            return PublishResult(
                success=True,
                message_id=msg_id,
                destination=target,
            )
        except Exception as e:
            logger.error("Failed to publish SNS message to %s: %s", target, e)
            return PublishResult(
                success=False,
                destination=target,
                error=str(e),
            )
