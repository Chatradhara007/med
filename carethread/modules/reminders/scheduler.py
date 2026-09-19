"""EventBridge scheduling abstractions and implementations for M5 Reminders.

Provides both real EventBridge Scheduler integration and an in-memory mock for
deterministic local execution and testing.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional

from carethread.shared.schemas.plan_entry import SlotName
from carethread.modules.reminders.schemas import ReminderEvent

logger = logging.getLogger(__name__)

# Standard daily slot hour offsets (UTC or local target representation)
SLOT_HOUR_MAP: Dict[SlotName, int] = {
    SlotName.MORNING: 8,
    SlotName.AFTERNOON: 13,
    SlotName.EVENING: 18,
    SlotName.NIGHT: 21,
}


def compute_scheduled_time(
    day_index: int,
    slot: SlotName,
    demo_mode: bool = False,
    demo_delay_seconds: int = 30,
    base_time: Optional[datetime] = None,
) -> datetime:
    """Compute target trigger timestamp for a reminder.

    In Demo Mode (demo_mode=True), schedules execution demo_delay_seconds into the future.
    In Production Mode, schedules based on day_index offset and standardized slot hours.
    """
    now = base_time or datetime.now(timezone.utc)
    if demo_mode:
        return now + timedelta(seconds=demo_delay_seconds)

    # Production mode: calculate future target time
    target_date = (now + timedelta(days=day_index)).date()
    target_hour = SLOT_HOUR_MAP.get(slot, 9)
    target_dt = datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=target_hour,
        minute=0,
        second=0,
        tzinfo=timezone.utc,
    )
    # If the computed time is in the past for day 0, schedule at next available slot or immediate
    if target_dt <= now and day_index == 0:
        return now + timedelta(minutes=15)
    return target_dt


class ReminderSchedulerInterface(ABC):
    """Abstract interface for scheduling reminder triggers."""

    @abstractmethod
    def schedule_reminder(self, event: ReminderEvent) -> str:
        """Schedule a reminder event. Returns unique schedule ARN or identifier."""
        pass

    @abstractmethod
    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a previously scheduled reminder trigger."""
        pass

    @abstractmethod
    def list_scheduled(self, patient_id: Optional[str] = None) -> List[ReminderEvent]:
        """List currently active scheduled reminders, optionally filtered by patient."""
        pass


class MockReminderScheduler(ReminderSchedulerInterface):
    """Deterministic in-memory scheduler for testing and local development."""

    def __init__(self) -> None:
        self.scheduled: Dict[str, ReminderEvent] = {}
        self.cancelled: List[str] = []

    def schedule_reminder(self, event: ReminderEvent) -> str:
        self.scheduled[event.reminder_id] = event
        return f"arn:aws:scheduler:local:mock:schedule/{event.reminder_id}"

    def cancel_reminder(self, reminder_id: str) -> bool:
        if reminder_id in self.scheduled:
            del self.scheduled[reminder_id]
            self.cancelled.append(reminder_id)
            return True
        return False

    def list_scheduled(self, patient_id: Optional[str] = None) -> List[ReminderEvent]:
        if patient_id is None:
            return list(self.scheduled.values())
        return [e for e in self.scheduled.values() if e.patient_id == patient_id]


class EventBridgeReminderScheduler(ReminderSchedulerInterface):
    """Real AWS EventBridge Scheduler client adapter.

    Uses EventBridge Scheduler API (create_schedule, delete_schedule) with one-time schedules.
    """

    def __init__(
        self,
        boto_client: Optional[Any] = None,
        target_arn: Optional[str] = None,
        role_arn: Optional[str] = None,
        schedule_group: str = "carethread-reminders",
    ) -> None:
        self._client = boto_client
        self.target_arn = target_arn or os.getenv("REMINDER_LAMBDA_ARN", "arn:aws:lambda:us-east-1:123456789012:function:CareThreadReminderFn")
        self.role_arn = role_arn or os.getenv("EVENTBRIDGE_SCHEDULER_ROLE_ARN", "arn:aws:iam::123456789012:role/EventBridgeSchedulerRole")
        self.schedule_group = schedule_group

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3
            self._client = boto3.client("scheduler")
        return self._client

    def schedule_reminder(self, event: ReminderEvent) -> str:
        name = f"ct-rem-{event.reminder_id}"
        # EventBridge Scheduler expects format: at(yyyy-mm-ddThh:mm:ss)
        try:
            dt = datetime.fromisoformat(event.scheduled_time.replace("Z", "+00:00"))
            schedule_expr = f"at({dt.strftime('%Y-%m-%dT%H:%M:%S')})"
        except Exception:
            schedule_expr = f"at({event.scheduled_time})"

        payload = json.dumps(event.model_dump())

        params = {
            "Name": name,
            "GroupName": self.schedule_group,
            "ScheduleExpression": schedule_expr,
            "FlexibleTimeWindow": {"Mode": "OFF"},
            "Target": {
                "Arn": self.target_arn,
                "RoleArn": self.role_arn,
                "Input": payload,
            },
            "ActionAfterCompletion": "DELETE",
        }

        try:
            response = self.client.create_schedule(**params)
            arn = response.get("ScheduleArn", f"arn:aws:scheduler:::schedule/{self.schedule_group}/{name}")
            logger.info("Successfully scheduled EventBridge reminder: %s (arn: %s)", name, arn)
            return arn
        except Exception as e:
            logger.error("Failed to create EventBridge schedule %s: %s", name, e)
            raise

    def cancel_reminder(self, reminder_id: str) -> bool:
        name = f"ct-rem-{reminder_id}"
        try:
            self.client.delete_schedule(Name=name, GroupName=self.schedule_group)
            logger.info("Deleted EventBridge schedule: %s", name)
            return True
        except Exception as e:
            logger.warning("Could not delete EventBridge schedule %s: %s", name, e)
            return False

    def list_scheduled(self, patient_id: Optional[str] = None) -> List[ReminderEvent]:
        # EventBridge Scheduler list_schedules returns metadata; payload needs fetching
        # For listing in production, queries are usually tracked via DynamoDB single table
        return []
