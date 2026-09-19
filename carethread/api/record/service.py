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

        # 3. Targeted, non-destructive write through the repository contract.
        #    Resolving a needs_review chip transitions provenance to confirmed
        #    (Section 9.2); the source citation itself is never touched.
        item = self.repo.update_entity_field(
            patient_id=patient_id,
            sk=sk,
            field=field,
            value=value,
            confirm_provenance=True,
        )

        logger.info("Successfully updated %s.%s for patient %s", sk, field, patient_id)

        provenance = item.get("provenance")
        status = (
            ProvenanceStatus(provenance["status"])
            if isinstance(provenance, dict) and provenance.get("status")
            else ProvenanceStatus.CONFIRMED
        )
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
