"""Service layer for canonical patient record retrieval, controlled patching, and plan adherence."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Set
from pydantic import ValidationError

from carethread.shared.schemas.api import (
    PatientRecordResponse,
    RecordFieldPatchRequest,
    RecordFieldPatchResponse,
    PlanDoneResponse,
)
from carethread.shared.schemas.plan_entry import SlotName, PlanEntry
from carethread.shared.schemas.provenance import ProvenanceStatus
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.repository.exceptions import (
    EntityNotFoundError,
    PatientNotFoundError,
    DatabaseError,
)

logger = logging.getLogger(__name__)

# Controlled mutation allowlists per DynamoDB entity type
ENTITY_ALLOWLIST: Dict[str, Dict[str, Set[str]]] = {
    "PROFILE": {
        "editable": {"name", "age", "phone", "language", "sex"},
        "forbidden": {"patient_id", "pk", "sk", "created_at"},
    },
    "MED": {
        "editable": {"strength", "freq", "instructions", "duration_days", "status"},
        "forbidden": {"pk", "sk", "name", "created_at", "source", "doc_id", "bbox", "verbatim", "provenance.source"},
    },
    "DIAG": {
        "editable": {"code", "status", "notes", "display_name"},
        "forbidden": {"pk", "sk", "provenance.source", "source", "doc_id", "bbox", "verbatim"},
    },
    "PLAN": {
        "editable": {"action", "time_target", "done"},
        "forbidden": {"pk", "sk", "day_index", "slot", "med_ref", "source", "doc_id", "bbox", "verbatim"},
    },
}


def _resolve_entity_type(sk: str) -> str:
    """Classify sort key to determine validation and allowlist rules."""
    if sk == "PROFILE":
        return "PROFILE"
    if sk.startswith("MED#"):
        return "MED"
    if sk.startswith("DIAG#"):
        return "DIAG"
    if sk.startswith("PLAN#"):
        return "PLAN"
    raise ValueError(f"Entity with sort key '{sk}' is not supported for field editing")


class RecordService:
    """Domain operations for canonical patient record and care-plan adherence."""

    def __init__(self, repository: PatientRepositoryInterface) -> None:
        self.repo = repository

    def get_patient_record(self, patient_id: str) -> PatientRecordResponse:
        """Fetch the full canonical patient record from the single partition."""
        if not patient_id or not str(patient_id).strip():
            raise ValueError("patient_id must be a non-empty string")

        return self.repo.get_patient_context(patient_id)

    def patch_record_field(
        self,
        patient_id: str,
        request: RecordFieldPatchRequest,
    ) -> RecordFieldPatchResponse:
        """Apply controlled schema-validated field update while preserving provenance."""
        if not patient_id or not str(patient_id).strip():
            raise ValueError("patient_id must be a non-empty string")

        sk = request.sk.strip()
        field = request.field.strip()
        value = request.value

        # 1. Resolve entity type and check allowlists
        entity_type = _resolve_entity_type(sk)
        rules = ENTITY_ALLOWLIST[entity_type]

        if field in rules["forbidden"]:
            raise ValueError(f"Field '{field}' is immutable and cannot be modified")
        if field not in rules["editable"]:
            raise ValueError(f"Field '{field}' is not editable on entity '{entity_type}'")

        # 2. Field-specific data validation
        if field == "age":
            if not isinstance(value, int) or value < 0 or value > 150:
                raise ValueError("age must be an integer between 0 and 150")
        elif field in ("name", "phone", "strength", "freq"):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")

        # 3. Retrieve raw item from repository
        pk = f"PATIENT#{patient_id}"
        item: Optional[Dict[str, Any]] = None

        if hasattr(self.repo, "_table") and isinstance(self.repo._table, dict):
            # InMemory repo
            raw = self.repo._table.get((pk, sk))
            if raw:
                item = dict(raw)
        elif hasattr(self.repo, "_table") and hasattr(self.repo._table, "get_item"):
            # DynamoDB Table resource
            res = self.repo._table.get_item(Key={"PK": pk, "SK": sk})
            item = res.get("Item")

        if item is None:
            raise EntityNotFoundError(f"Record entity with SK '{sk}' not found for patient '{patient_id}'")

        # 4. Safe non-destructive update
        item[field] = value
        item["updated_at"] = datetime.now(timezone.utc).isoformat()

        # If item has provenance, transition status from needs_review to confirmed
        status = ProvenanceStatus.CONFIRMED
        if "provenance" in item and isinstance(item["provenance"], dict):
            item["provenance"]["status"] = ProvenanceStatus.CONFIRMED.value

        # 5. Persist updated item back
        if hasattr(self.repo, "_table") and isinstance(self.repo._table, dict):
            self.repo._table[(pk, sk)] = item
        elif hasattr(self.repo, "_table") and hasattr(self.repo._table, "put_item"):
            item["PK"] = pk
            item["SK"] = sk
            self.repo._table.put_item(Item=item)

        logger.info("Successfully updated %s.%s for patient %s", sk, field, patient_id)
        return RecordFieldPatchResponse(
            status=status,
            updated_item=item,
        )

    def mark_plan_done(
        self,
        patient_id: str,
        day: int,
        slot_raw: str,
    ) -> PlanDoneResponse:
        """Mark care-plan task as completed (adherence tracking)."""
        if not patient_id or not str(patient_id).strip():
            raise ValueError("patient_id must be a non-empty string")

        if not isinstance(day, int) or day < 0 or day > 6:
            raise ValueError(f"day must be an integer between 0 and 6, got {day}")

        try:
            slot = SlotName(slot_raw.lower().strip())
        except ValueError:
            valid_slots = [s.value for s in SlotName]
            raise ValueError(f"Invalid schedule slot '{slot_raw}'. Allowed: {valid_slots}")

        now_iso = datetime.now(timezone.utc).isoformat()
        updated_entry = self.repo.update_plan_entry_done(
            patient_id=patient_id,
            day_index=day,
            slot=slot.value,
            done=True,
            completed_at=now_iso,
        )

        completed_at = updated_entry.completed_at or now_iso
        logger.info("Marked plan day %s slot %s done for patient %s", day, slot.value, patient_id)

        return PlanDoneResponse(
            day=day,
            slot=slot,
            done=True,
            completed_at=completed_at,
        )
