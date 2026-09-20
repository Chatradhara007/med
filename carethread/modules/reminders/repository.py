"""Persistence adapter for tracking scheduled reminders and enforcing idempotency.

Stores records under single-table key pattern:
PK = PATIENT#<patient_id>
SK = REMINDER#<reminder_id>
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.modules.reminders.schemas import ReminderRecord, ReminderStatus


class ReminderRepository:
    """Repository helper for managing ReminderRecord entities in the single table."""

    def __init__(self, repository: Optional[PatientRepositoryInterface] = None) -> None:
        self.repository = repository
        self._local_storage: Dict[str, Dict[str, Any]] = {}

    def save_reminder(self, record: ReminderRecord) -> ReminderRecord:
        """Persist a scheduled or updated reminder record."""
        pk = record.pk
        sk = record.sk
        data = record.model_dump()
        # Convert enum to value string for DynamoDB compatibility
        data["status"] = record.status.value

        if self.repository is not None:
            # Check if InMemory repo with internal table dict
            if hasattr(self.repository, "_table") and isinstance(self.repository._table, dict):
                self.repository._table[(pk, sk)] = data
            elif hasattr(self.repository, "_table") and hasattr(self.repository._table, "put_item"):
                # Real DynamoDB table resource
                data["PK"] = pk
                data["SK"] = sk
                self.repository._table.put_item(Item=data)
        else:
            self._local_storage[f"{pk}#{sk}"] = data

        return record

    def get_reminder(self, patient_id: str, reminder_id: str) -> Optional[ReminderRecord]:
        """Retrieve a reminder record by patient ID and reminder ID."""
        pk = f"PATIENT#{patient_id}"
        sk = f"REMINDER#{reminder_id}"

        if self.repository is not None:
            if hasattr(self.repository, "_table") and isinstance(self.repository._table, dict):
                raw = self.repository._table.get((pk, sk))
                if raw:
                    return ReminderRecord.model_validate(raw)
            elif hasattr(self.repository, "_table") and hasattr(self.repository._table, "get_item"):
                res = self.repository._table.get_item(Key={"PK": pk, "SK": sk})
                item = res.get("Item")
                if item:
                    return ReminderRecord.model_validate(item)
        else:
            raw = self._local_storage.get(f"{pk}#{sk}")
            if raw:
                return ReminderRecord.model_validate(raw)

        return None

    def mark_reminder_sent(
        self,
        patient_id: str,
        reminder_id: str,
        sent_at: Optional[str] = None,
        event: Optional[Any] = None,
    ) -> ReminderRecord:
        """Mark reminder as successfully sent, creating record if not previously persisted."""
        now_iso = sent_at or datetime.now(timezone.utc).isoformat()
        record = self.get_reminder(patient_id, reminder_id)
        if record:
            updated = record.model_copy(update={
                "status": ReminderStatus.SENT,
                "sent_at": now_iso,
            })
            return self.save_reminder(updated)

        # Create record on the fly if not pre-saved
        day_index = getattr(event, "day_index", 0) if event else 0
        slot = getattr(event, "slot", "morning") if event else "morning"
        scheduled_time = getattr(event, "scheduled_time", now_iso) if event else now_iso
        idem_key = getattr(event, "idempotency_key", f"idem-{reminder_id}") if event else f"idem-{reminder_id}"

        new_record = ReminderRecord(
            reminder_id=reminder_id,
            patient_id=patient_id,
            day_index=day_index,
            slot=slot,
            scheduled_time=scheduled_time,
            status=ReminderStatus.SENT,
            sent_at=now_iso,
            created_at=now_iso,
            idempotency_key=idem_key,
        )
        return self.save_reminder(new_record)

    def mark_reminder_suppressed(
        self,
        patient_id: str,
        reminder_id: str,
        event: Optional[Any] = None,
    ) -> ReminderRecord:
        """Mark reminder as suppressed due to prior dose completion."""
        now_iso = datetime.now(timezone.utc).isoformat()
        record = self.get_reminder(patient_id, reminder_id)
        if record:
            updated = record.model_copy(update={"status": ReminderStatus.SUPPRESSED_COMPLETED})
            return self.save_reminder(updated)

        day_index = getattr(event, "day_index", 0) if event else 0
        slot = getattr(event, "slot", "morning") if event else "morning"
        scheduled_time = getattr(event, "scheduled_time", now_iso) if event else now_iso
        idem_key = getattr(event, "idempotency_key", f"idem-{reminder_id}") if event else f"idem-{reminder_id}"

        new_record = ReminderRecord(
            reminder_id=reminder_id,
            patient_id=patient_id,
            day_index=day_index,
            slot=slot,
            scheduled_time=scheduled_time,
            status=ReminderStatus.SUPPRESSED_COMPLETED,
            created_at=now_iso,
            idempotency_key=idem_key,
        )
        return self.save_reminder(new_record)

    def is_already_processed(self, patient_id: str, reminder_id: str) -> bool:
        """Check if reminder was already sent, suppressed, or skipped."""
        record = self.get_reminder(patient_id, reminder_id)
        if not record:
            return False
        return record.status in (
            ReminderStatus.SENT,
            ReminderStatus.SUPPRESSED_COMPLETED,
            ReminderStatus.DUPLICATE_SKIPPED,
        )
