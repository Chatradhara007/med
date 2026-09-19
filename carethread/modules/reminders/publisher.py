"""Notification delivery adapters and implementations for M5 Reminders.

Provides Amazon SNS integration and an in-memory mock with privacy leak
detection to enforce HIPAA-compliant non-sensitive messaging.
"""

from abc import ABC, abstractmethod
import csv
from functools import lru_cache
import logging
import os
from pathlib import Path
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


class PrivacyViolationError(ValueError):
    """Raised when an outgoing notification would disclose clinical detail."""


@lru_cache(maxsize=1)
def _drug_name_tokens() -> frozenset:
    """Drug names and salts drawn from the curated index and the NTI list.

    Section 8.5 forbids drug names in outgoing notifications, and a hand-written
    keyword list cannot cover them. The project already ships a vetted index, so
    the same data backs the privacy rail.
    """
    tokens: set = set()

    def _add(text: str) -> None:
        for part in re.split(r"[\s,;/()]+", (text or "").lower()):
            cleaned = part.strip().strip(".")
            # Short fragments ("5", "mg", "sr") would cause false positives.
            if len(cleaned) >= 5 and cleaned.isalpha():
                tokens.add(cleaned)

    data_dir = Path(__file__).resolve().parents[2] / "data"
    for filename, columns in (
        ("drugs.csv", ("brand", "salt")),
        ("nti.csv", ("salt", "brand_examples")),
    ):
        path = data_dir / filename
        if not path.exists():
            logger.warning("Privacy rail could not load %s", path)
            continue
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    for column in columns:
                        _add(row.get(column, ""))
        except OSError as exc:
            logger.warning("Privacy rail could not read %s: %s", path, exc)

    return frozenset(tokens)


def assert_no_phi(message: str) -> None:
    """Reject any outgoing notification containing protected health information.

    Section 8.5 is non-negotiable and applies to every delivery channel, not
    just the test double: push and SMS payloads leave the authenticated app and
    are visible on a lock screen.
    """
    lower_msg = (message or "").lower()
    for kw in DISALLOWED_SENSITIVE_KEYWORDS:
        # Word boundary search to avoid accidental substring matches
        if re.search(r"\b" + re.escape(kw) + r"\b", lower_msg):
            raise PrivacyViolationError(
                f"Privacy violation: Outgoing notification contains sensitive clinical term '{kw}'"
            )

    drug_tokens = _drug_name_tokens()
    for word in re.findall(r"[a-z]+", lower_msg):
        if word in drug_tokens:
            raise PrivacyViolationError(
                f"Privacy violation: Outgoing notification names a medicine ('{word}')"
            )


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
        assert_no_phi(message)

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
        self.default_topic_arn = (
            default_topic_arn
            or os.getenv("SNS_TOPIC_ARN")
            or os.getenv("REMINDER_SNS_TOPIC_ARN")
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
        # The same rail the mock enforces, applied before anything leaves AWS.
        assert_no_phi(message)
        if subject:
            assert_no_phi(subject)

        target = destination or self.default_topic_arn
        if not target:
            raise ValueError(
                "SNS publish requires a destination: set SNS_TOPIC_ARN or pass a target"
            )

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


def use_mock_delivery() -> bool:
    """Mock delivery is opt-in locally and impossible inside a Lambda."""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return False
    return os.environ.get("USE_MOCK_AWS", "false").lower() in ("true", "1", "yes")


def get_notification_publisher(
    topic_arn: Optional[str] = None,
) -> NotificationPublisherInterface:
    """Return the publisher for the current environment. Real SNS by default."""
    if use_mock_delivery():
        logger.warning("USE_MOCK_AWS is set; reminder delivery is mocked")
        return MockNotificationPublisher()
    return SNSNotificationPublisher(default_topic_arn=topic_arn)
