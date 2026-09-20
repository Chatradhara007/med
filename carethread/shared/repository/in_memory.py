"""In-memory implementation of the PatientRepositoryInterface.

Provides high-fidelity, credential-free persistence for local testing
and development while enforcing identical single-table key patterns and
provenance validation invariants.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.document import Document
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.plan_entry import PlanEntry
from carethread.shared.schemas.alert_rule import FiredAlert
from carethread.shared.schemas.api import PatientRecordResponse
from carethread.shared.schemas.provenance import ProvenanceStatus

from .interfaces import PatientRepositoryInterface
from .exceptions import (
    PatientNotFoundError,
    DocumentNotFoundError,
    EntityNotFoundError,
    MissingProvenanceError,
    InvalidPatientIdError,
)


class InMemoryPatientRepository(PatientRepositoryInterface):
    """In-memory single-table simulation keyed by (PK, SK)."""

    def __init__(self):
        # Store items indexed by (PK, SK)
        self._table: Dict[Tuple[str, str], dict] = {}

    def _validate_patient_id(self, patient_id: str) -> str:
        if not patient_id or not isinstance(patient_id, str) or not patient_id.strip():
            raise InvalidPatientIdError("patient_id must be a non-empty string")
        return patient_id.strip()

    def _validate_provenance(self, entity_name: str, entity: object) -> None:
        """Enforce the one invariant: extracted clinical entities must possess valid provenance."""
        provenance = getattr(entity, "provenance", None)
        if provenance is None:
            raise MissingProvenanceError(f"Cannot persist {entity_name} without valid provenance")
        source = getattr(provenance, "source", None)
        if source is None:
            raise MissingProvenanceError(f"Cannot persist {entity_name}: provenance.source is missing")

    def create_patient(self, patient: Patient) -> Patient:
        self._validate_patient_id(patient.patient_id)
        pk = patient.pk
        sk = patient.sk
        self._table[(pk, sk)] = patient.model_dump()
        return patient

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        sk = "PROFILE"
        data = self._table.get((pk, sk))
        if data:
            return Patient.model_validate(data)
        return None

    def update_patient(self, patient: Patient) -> Patient:
        self._validate_patient_id(patient.patient_id)
        pk = patient.pk
        sk = patient.sk
        if (pk, sk) not in self._table:
            raise PatientNotFoundError(f"Patient {patient.patient_id} not found")
        self._table[(pk, sk)] = patient.model_dump()
        return patient

    def create_document(self, document: Document) -> Document:
        self._validate_patient_id(document.patient_id)
        pk = document.pk
        sk = document.sk
        self._table[(pk, sk)] = document.model_dump()
        return document

    def get_document(self, patient_id: str, doc_id: str) -> Optional[Document]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk and item_sk.startswith("DOC#"):
                if data.get("doc_id") == doc_id:
                    return Document.model_validate(data)
        return None

    def list_documents(self, patient_id: str) -> List[Document]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        docs = []
        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk and item_sk.startswith("DOC#"):
                docs.append(Document.model_validate(data))
        return sorted(docs, key=lambda d: d.created_at)

    def update_document(self, document: Document) -> Document:
        self._validate_patient_id(document.patient_id)
        pk = document.pk
        existing_sk = None
        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk and item_sk.startswith("DOC#") and data.get("doc_id") == document.doc_id:
                existing_sk = item_sk
                break
        if existing_sk is None:
            raise DocumentNotFoundError(
                f"Document {document.doc_id} not found for patient {document.patient_id}"
            )
        # The sort key embeds created_at, so it must not move on a status change.
        self._table[(pk, existing_sk)] = document.model_dump()
        return document

    def update_entity_field(
        self,
        patient_id: str,
        sk: str,
        field: str,
        value: Any,
        confirm_provenance: bool = True,
    ) -> Dict[str, Any]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        item = self._table.get((pk, sk))
        if item is None:
            raise EntityNotFoundError(
                f"Record entity with SK '{sk}' not found for patient '{patient_id}'"
            )
        updated = dict(item)
        updated[field] = value
        updated["updated_at"] = datetime.now(timezone.utc).isoformat()
        if confirm_provenance and isinstance(updated.get("provenance"), dict):
            provenance = dict(updated["provenance"])
            provenance["status"] = ProvenanceStatus.CONFIRMED.value
            updated["provenance"] = provenance
        self._table[(pk, sk)] = updated
        return updated

    def create_medication(self, patient_id: str, medication: Medication) -> Medication:
        self._validate_patient_id(patient_id)
        self._validate_provenance("Medication", medication)
        pk = medication.pk(patient_id)
        sk = medication.sk
        self._table[(pk, sk)] = medication.model_dump()
        return medication

    def get_medications(self, patient_id: str) -> List[Medication]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        meds = []
        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk and item_sk.startswith("MED#"):
                meds.append(Medication.model_validate(data))
        return meds

    def create_lab_result(self, patient_id: str, lab_result: LabResult, timestamp: Optional[str] = None) -> LabResult:
        self._validate_patient_id(patient_id)
        self._validate_provenance("LabResult", lab_result)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        # Stamping the timestamp makes the serialised `sk` the real storage key.
        lab_result = lab_result.model_copy(update={"reported_at": ts})
        pk = lab_result.pk(patient_id)
        sk = lab_result.sk_for(ts)
        self._table[(pk, sk)] = lab_result.model_dump()
        return lab_result

    def get_lab_results(self, patient_id: str) -> List[LabResult]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        labs = []
        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk and item_sk.startswith("LAB#"):
                labs.append(LabResult.model_validate(data))
        return labs

    def create_diagnosis(self, patient_id: str, diagnosis: Diagnosis) -> Diagnosis:
        self._validate_patient_id(patient_id)
        self._validate_provenance("Diagnosis", diagnosis)
        pk = diagnosis.pk(patient_id)
        sk = diagnosis.sk
        self._table[(pk, sk)] = diagnosis.model_dump()
        return diagnosis

    def get_diagnoses(self, patient_id: str) -> List[Diagnosis]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        diags = []
        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk and item_sk.startswith("DIAG#"):
                diags.append(Diagnosis.model_validate(data))
        return diags

    def create_plan_entry(self, patient_id: str, plan_entry: PlanEntry) -> PlanEntry:
        self._validate_patient_id(patient_id)
        self._validate_provenance("PlanEntry", plan_entry)
        pk = plan_entry.pk(patient_id)
        sk = plan_entry.sk
        self._table[(pk, sk)] = plan_entry.model_dump()
        return plan_entry

    def get_plan_entries(self, patient_id: str) -> List[PlanEntry]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        entries = []
        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk and item_sk.startswith("PLAN#"):
                entries.append(PlanEntry.model_validate(data))
        return sorted(entries, key=lambda e: (e.day_index, e.slot.value))

    def update_plan_entry_done(
        self,
        patient_id: str,
        day_index: int,
        slot: str,
        done: bool = True,
        completed_at: Optional[str] = None
    ) -> PlanEntry:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        slot_str = slot.value if hasattr(slot, "value") else str(slot)
        sk = f"PLAN#{day_index}#{slot_str}"
        if (pk, sk) not in self._table:
            raise EntityNotFoundError(f"PlanEntry for day {day_index} slot {slot_str} not found")
        
        # Targeted field update (safe, non-destructive to rest of item or partition)
        item = self._table[(pk, sk)]
        item["done"] = done
        item["completed_at"] = completed_at or datetime.now(timezone.utc).isoformat()
        return PlanEntry.model_validate(item)

    def create_alert(self, patient_id: str, alert: FiredAlert) -> FiredAlert:
        self._validate_patient_id(patient_id)
        pk = alert.pk(patient_id)
        sk = alert.sk
        self._table[(pk, sk)] = alert.model_dump()
        return alert

    def get_alerts(self, patient_id: str) -> List[FiredAlert]:
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"
        alerts = []
        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk and item_sk.startswith("ALERT#"):
                alerts.append(FiredAlert.model_validate(data))
        return alerts

    def get_patient_context(self, patient_id: str) -> PatientRecordResponse:
        """Single partition query (PK = PATIENT#<id>) returning complete canonical context."""
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"

        patient: Optional[Patient] = None
        docs: List[Document] = []
        meds: List[Medication] = []
        labs: List[LabResult] = []
        diags: List[Diagnosis] = []
        plan: List[PlanEntry] = []
        alerts: List[FiredAlert] = []

        for (item_pk, item_sk), data in self._table.items():
            if item_pk == pk:
                if item_sk == "PROFILE":
                    patient = Patient.model_validate(data)
                elif item_sk.startswith("DOC#"):
                    docs.append(Document.model_validate(data))
                elif item_sk.startswith("MED#"):
                    meds.append(Medication.model_validate(data))
                elif item_sk.startswith("LAB#"):
                    labs.append(LabResult.model_validate(data))
                elif item_sk.startswith("DIAG#"):
                    diags.append(Diagnosis.model_validate(data))
                elif item_sk.startswith("PLAN#"):
                    plan.append(PlanEntry.model_validate(data))
                elif item_sk.startswith("ALERT#"):
                    alerts.append(FiredAlert.model_validate(data))

        return PatientRecordResponse(
            patient=patient,
            documents=sorted(docs, key=lambda d: d.created_at),
            diagnoses=diags,
            medications=meds,
            lab_results=labs,
            plan_entries=sorted(plan, key=lambda e: (e.day_index, e.slot.value)),
            alerts=sorted(alerts, key=lambda a: a.fired_at, reverse=True)
        )
