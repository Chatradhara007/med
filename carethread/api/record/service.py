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
from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.plan_entry import SlotName, PlanEntry
from carethread.shared.schemas.provenance import ProvenanceStatus
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.repository.exceptions import (
    EntityNotFoundError,
    PatientNotFoundError,
    DatabaseError,
)

logger = logging.getLogger(__name__)

# A Cognito token carries no age, sex or phone. These placeholders mark the
# fields as "not yet supplied by the patient" rather than inventing values.
UNSET_AGE = 0
UNSET_SEX = "Unknown"
UNSET_PHONE = "not provided"


def _display_name(claims: Dict[str, Any], patient_id: str) -> str:
    """Best available name from the token, without inventing one."""
    name = str(claims.get("name") or "").strip()
    if name:
        return name

    parts = [
        str(claims.get("given_name") or "").strip(),
        str(claims.get("family_name") or "").strip(),
    ]
    joined = " ".join(p for p in parts if p)
    if joined:
        return joined

    email = str(claims.get("email") or "").strip()
    if email and "@" in email:
        return email.split("@", 1)[0]
    return email or f"Patient {patient_id[:8]}"


def is_profile_complete(patient: Optional[Patient]) -> bool:
    """True once the patient has supplied what the token could not."""
    if patient is None:
        return False
    return (
        patient.age != UNSET_AGE
        and patient.sex != UNSET_SEX
        and patient.phone != UNSET_PHONE
    )

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
        # `icd_hint` is the editable code. `code_or_slug` derives the sort key,
        # so editing it would write to the old row and orphan it.
        "editable": {"icd_hint", "status", "notes", "display_name"},
        "forbidden": {
            "pk", "sk", "label", "code_or_slug", "provenance.source",
            "source", "doc_id", "bbox", "verbatim",
        },
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

    def get_patient_record(
        self,
        patient_id: str,
        claims: Optional[Dict[str, Any]] = None,
    ) -> PatientRecordResponse:
        """Fetch the full canonical patient record from the single partition.

        A patient who has just signed up through Cognito has no PROFILE row
        yet, which would leave the whole UI without a name to render. On the
        first read we seed one from the verified JWT claims and mark it
        incomplete, rather than returning a null patient.
        """
        if not patient_id or not str(patient_id).strip():
            raise ValueError("patient_id must be a non-empty string")

        record = self.repo.get_patient_context(patient_id)

        if record.patient is None:
            record.patient = self._bootstrap_profile(patient_id, claims or {})

        record.profile_complete = is_profile_complete(record.patient)
        return record

    def _bootstrap_profile(self, patient_id: str, claims: Dict[str, Any]) -> Optional[Patient]:
        """Seed a PROFILE row from verified JWT claims.

        Only values the token actually carries are used. Age and sex are not in
        a Cognito token, so they are recorded as unset placeholders for the
        patient to complete -- never guessed.
        """
        patient = Patient(
            patient_id=patient_id,
            name=_display_name(claims, patient_id),
            age=UNSET_AGE,
            sex=UNSET_SEX,
            language=str(claims.get("locale") or "en").strip() or "en",
            phone=str(claims.get("phone_number") or "").strip() or UNSET_PHONE,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        try:
            self.repo.create_patient(patient)
            logger.info("Seeded profile for new patient %s from JWT claims", patient_id)
        except Exception:
            # A missing profile must not break the whole record read; the UI
            # can still prompt, and the next call retries the write.
            logger.exception("Could not persist bootstrapped profile for %s", patient_id)
        return patient

    def patch_record_field(
        self,
        patient_id: str,
        request: RecordFieldPatchRequest,
    ) -> RecordFieldPatchResponse:
        """Apply controlled schema-validated field update while preserving provenance."""
        if not patient_id or not str(patient_id).strip():
            raise ValueError("patient_id must be a non-empty string")

        sk = request.sk.strip()
        field = request.field.strip() if request.field else None
        value = request.value

        # 1. Resolve entity type and check allowlists. A confirm-only request
        #    changes no value, so there is no field to screen -- but the sk is
        #    still resolved so an unknown entity type is rejected the same way.
        entity_type = _resolve_entity_type(sk)
        rules = ENTITY_ALLOWLIST[entity_type]

        if field is not None:
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

        if field is None:
            logger.info("Confirmed %s for patient %s", sk, patient_id)
        else:
            logger.info("Successfully updated %s.%s for patient %s", sk, field, patient_id)

        # PK/SK are internal storage keys; the caller already supplied the sk
        # and has no use for the partition key.
        item = {k: v for k, v in item.items() if k not in ("PK", "SK")}

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
