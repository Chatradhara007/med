"""Reminder evaluation handler and AWS Lambda entry point.

Workflow:
EventBridge trigger -> Schema Validation -> Canonical Patient Context ->
Adherence Check (Suppression) -> Idempotency Check -> Safe SNS Publish -> Single Table Update.
"""

from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, Optional, Union
from pydantic import ValidationError

from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.modules.reminders.schemas import (
    ReminderEvent,
    ReminderExecutionResult,
    ReminderStatus,
)
from carethread.modules.reminders.repository import ReminderRepository
from carethread.modules.reminders.publisher import (
    NotificationPublisherInterface,
    MockNotificationPublisher,
    SNSNotificationPublisher,
)

logger = logging.getLogger(__name__)


def build_safe_notification_message(slot_name: str) -> str:
    """Build privacy-preserving notification text strictly free of PHI/clinical details."""
    slot_display = slot_name.capitalize()
    return (
        f"CareThread reminder: It is time for your {slot_display} care-plan activities. "
        "Please check your schedule in the CareThread app."
    )


class ReminderHandler:
    """Evaluates scheduled reminder events and dispatches notifications if required."""

    def __init__(
        self,
        patient_repo: PatientRepositoryInterface,
        reminder_repo: Optional[ReminderRepository] = None,
        publisher: Optional[NotificationPublisherInterface] = None,
    ) -> None:
        self.patient_repo = patient_repo
        self.reminder_repo = reminder_repo or ReminderRepository(repository=patient_repo)
        self.publisher = publisher or MockNotificationPublisher()

    def evaluate_and_dispatch(
        self,
        raw_event: Union[ReminderEvent, Dict[str, Any]],
    ) -> ReminderExecutionResult:
        """Evaluate a scheduled reminder event and dispatch notification with strict idempotency."""
        # 1. Parse and validate event payload
        if isinstance(raw_event, ReminderEvent):
            event = raw_event
        else:
            try:
                event = ReminderEvent.model_validate(raw_event)
            except ValidationError as e:
                logger.error("Invalid reminder event payload: %s", e)
                return ReminderExecutionResult(
                    status_code=400,
                    status=ReminderStatus.FAILED,
                    reminder_id="unknown",
                    message=f"Invalid reminder event payload: {str(e)}",
                    published=False,
                    error=str(e),
                )

        reminder_id = event.reminder_id
        patient_id = event.patient_id

        # 2. Check patient existence in canonical patient record
        context = self.patient_repo.get_patient_context(patient_id)
        if context is None or context.patient is None:
            logger.warning("Patient %s not found in canonical record", patient_id)
            return ReminderExecutionResult(
                status_code=404,
                status=ReminderStatus.FAILED,
                reminder_id=reminder_id,
                message=f"Patient {patient_id} not found",
                published=False,
                error="PatientNotFound",
            )

        # 3. Check for matching plan entries in canonical context
        matching_entries = [
            pe for pe in context.plan_entries
            if pe.day_index == event.day_index and pe.slot == event.slot
        ]

        if not matching_entries:
            logger.warning(
                "No care-plan entry found for patient %s at day %s slot %s",
                patient_id, event.day_index, event.slot.value
            )
            return ReminderExecutionResult(
                status_code=404,
                status=ReminderStatus.FAILED,
                reminder_id=reminder_id,
                message=f"No plan entry found for patient {patient_id} at day {event.day_index} slot {event.slot.value}",
                published=False,
                error="PlanEntryNotFound",
            )

        # 4. Idempotency Check: Don't deliver duplicate notifications for the same trigger
        if self.reminder_repo.is_already_processed(patient_id, reminder_id):
            logger.info(
                "Reminder %s for patient %s already processed; skipping duplicate dispatch.",
                reminder_id, patient_id
            )
            return ReminderExecutionResult(
                status_code=200,
                status=ReminderStatus.DUPLICATE_SKIPPED,
                reminder_id=reminder_id,
                message="Reminder already processed; skipped to prevent duplicate notification",
                published=False,
            )

        # 5. Adherence Check: If dose was already confirmed taken, suppress reminder
        all_completed = all(pe.done for pe in matching_entries)
        if all_completed:
            logger.info(
                "Adherence verified: all plan entries for patient %s day %s slot %s already completed. Suppressing reminder.",
                patient_id, event.day_index, event.slot.value
            )
            self.reminder_repo.mark_reminder_suppressed(patient_id, reminder_id, event=event)
            return ReminderExecutionResult(
                status_code=200,
                status=ReminderStatus.SUPPRESSED_COMPLETED,
                reminder_id=reminder_id,
                message="Reminder suppressed: task already completed",
                published=False,
            )

        # 6. Compose safe privacy-preserving notification message
        message_body = build_safe_notification_message(event.slot.value)
        subject = f"CareThread: {event.slot.value.capitalize()} Care Plan Reminder"
        destination = f"arn:aws:sns:us-east-1:123456789012:patient-{patient_id}"

        # 7. Deliver notification via configured publisher
        publish_result = self.publisher.publish(
            destination=destination,
            message=message_body,
            subject=subject,
            attributes={
                "reminder_id": reminder_id,
                "patient_id": patient_id,
                "slot": event.slot.value,
            },
        )

        if not publish_result.success:
            logger.error("Failed to publish reminder %s: %s", reminder_id, publish_result.error)
            return ReminderExecutionResult(
                status_code=500,
                status=ReminderStatus.FAILED,
                reminder_id=reminder_id,
                message=f"Notification delivery failed: {publish_result.error}",
                published=False,
                error=publish_result.error,
            )

        # 8. Mark reminder as SENT in single table to preserve idempotency
        self.reminder_repo.mark_reminder_sent(patient_id, reminder_id, event=event)
        logger.info("Successfully delivered and recorded reminder %s for patient %s", reminder_id, patient_id)

        return ReminderExecutionResult(
            status_code=200,
            status=ReminderStatus.SENT,
            reminder_id=reminder_id,
            message="Reminder sent successfully",
            published=True,
        )


def lambda_handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Standard AWS Lambda entrypoint invoked by EventBridge Scheduler."""
    # Unpack EventBridge rule wrapping if present
    payload = event.get("detail", event) if isinstance(event, dict) else event
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            pass

    # In production AWS Lambda, construct repository using DynamoDB table
    table_name = os.getenv("TABLE_NAME", "carethread-records")
    use_real_aws = os.getenv("USE_REAL_AWS", "false").lower() == "true"

    if use_real_aws:
        from carethread.shared.repository.dynamodb import DynamoDBPatientRepository
        repo = DynamoDBPatientRepository(table_name=table_name)
        publisher = SNSNotificationPublisher()
    else:
        from carethread.shared.repository.in_memory import InMemoryPatientRepository
        repo = InMemoryPatientRepository()
        publisher = MockNotificationPublisher()

    handler = ReminderHandler(patient_repo=repo, publisher=publisher)
    result = handler.evaluate_and_dispatch(payload)

    return {
        "statusCode": result.status_code,
        "body": json.dumps(result.model_dump()),
    }
