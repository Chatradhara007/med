"""High-level service orchestrator for M5 Reminders module.

Coordinates scheduling plan reminders from canonical PlanEntry objects,
dispatching evaluations, and querying reminder execution state.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from carethread.shared.schemas.plan_entry import PlanEntry, SlotName
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.modules.reminders.schemas import (
    ReminderEvent,
    ReminderExecutionResult,
    ReminderRecord,
    ReminderStatus,
)
from carethread.modules.reminders.repository import ReminderRepository
from carethread.modules.reminders.scheduler import (
    ReminderSchedulerInterface,
    MockReminderScheduler,
    compute_scheduled_time,
)
from carethread.modules.reminders.publisher import (
    NotificationPublisherInterface,
    MockNotificationPublisher,
)
from carethread.modules.reminders.handler import ReminderHandler

logger = logging.getLogger(__name__)


class ReminderService:
    """Service facade coordinating reminder scheduling, event processing, and persistence."""

    def __init__(
        self,
        patient_repo: PatientRepositoryInterface,
        scheduler: Optional[ReminderSchedulerInterface] = None,
        publisher: Optional[NotificationPublisherInterface] = None,
        reminder_repo: Optional[ReminderRepository] = None,
    ) -> None:
        self.patient_repo = patient_repo
        self.reminder_repo = reminder_repo or ReminderRepository(repository=patient_repo)
        self.scheduler = scheduler or MockReminderScheduler()
        self.publisher = publisher or MockNotificationPublisher()
        self.handler = ReminderHandler(
            patient_repo=self.patient_repo,
            reminder_repo=self.reminder_repo,
            publisher=self.publisher,
        )

    def schedule_plan_reminders(
        self,
        patient_id: str,
        plan_entries: List[PlanEntry],
        demo_mode: bool = False,
        demo_delay_seconds: int = 30,
        base_time: Optional[datetime] = None,
    ) -> List[ReminderRecord]:
        """Convert a list of PlanEntry items into scheduled reminders.

        Deduplicates by (day_index, slot) so that multiple medications scheduled for the
        same slot produce a single consolidated reminder trigger.
        """
        created_records: List[ReminderRecord] = []
        seen_slots: Set[Tuple[int, SlotName]] = set()

        for entry in plan_entries:
            key = (entry.day_index, entry.slot)
            if key in seen_slots:
                continue
            seen_slots.add(key)

            day_idx, slot = key
            scheduled_dt = compute_scheduled_time(
                day_index=day_idx,
                slot=slot,
                demo_mode=demo_mode,
                demo_delay_seconds=demo_delay_seconds,
                base_time=base_time,
            )
            scheduled_time_iso = scheduled_dt.isoformat()
            reminder_id = f"{patient_id}-d{day_idx}-{slot.value}"
            idem_key = f"idem-{reminder_id}"
            now_iso = datetime.now(timezone.utc).isoformat()

            event = ReminderEvent(
                reminder_id=reminder_id,
                patient_id=patient_id,
                day_index=day_idx,
                slot=slot,
                scheduled_time=scheduled_time_iso,
                demo_mode=demo_mode,
                idempotency_key=idem_key,
            )

            record = ReminderRecord(
                reminder_id=reminder_id,
                patient_id=patient_id,
                day_index=day_idx,
                slot=slot,
                scheduled_time=scheduled_time_iso,
                status=ReminderStatus.SCHEDULED,
                created_at=now_iso,
                idempotency_key=idem_key,
            )

            # Persist record in canonical single table
            self.reminder_repo.save_reminder(record)

            # Register with EventBridge scheduler
            self.scheduler.schedule_reminder(event)
            created_records.append(record)

            logger.info(
                "Scheduled reminder %s for patient %s (day %s slot %s at %s)",
                reminder_id, patient_id, day_idx, slot.value, scheduled_time_iso
            )

        return created_records

    def process_reminder_event(
        self,
        event: Union[ReminderEvent, Dict[str, Any]],
    ) -> ReminderExecutionResult:
        """Process a triggered reminder event through the evaluation and dispatch pipeline."""
        return self.handler.evaluate_and_dispatch(event)

    def get_reminder_status(
        self,
        patient_id: str,
        reminder_id: str,
    ) -> Optional[ReminderRecord]:
        """Retrieve execution state of a specific reminder from single-table persistence."""
        return self.reminder_repo.get_reminder(patient_id, reminder_id)
