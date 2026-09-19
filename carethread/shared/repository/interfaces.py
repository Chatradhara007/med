"""Repository interface defining the data-access contract for CareThread.

Guarantees single-table canonical episodic access pattern:
ONE PATIENT -> ONE PARTITION KEY -> ALL RELATED CONTEXT.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.document import Document
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.plan_entry import PlanEntry
from carethread.shared.schemas.alert_rule import FiredAlert
from carethread.shared.schemas.api import PatientRecordResponse


class PatientRepositoryInterface(ABC):
    """Abstract data-access layer for CareThread's canonical patient record."""

    @abstractmethod
    def create_patient(self, patient: Patient) -> Patient:
        """Persist a new patient profile under PK = PATIENT#<id>, SK = PROFILE."""
        pass

    @abstractmethod
    def get_patient(self, patient_id: str) -> Optional[Patient]:
        """Retrieve patient profile by patient ID."""
        pass

    @abstractmethod
    def update_patient(self, patient: Patient) -> Patient:
        """Update an existing patient profile."""
        pass

    @abstractmethod
    def create_document(self, document: Document) -> Document:
        """Persist document metadata under PK = PATIENT#<id>, SK = DOC#<iso_ts>#<doc_id>."""
        pass

    @abstractmethod
    def get_document(self, patient_id: str, doc_id: str) -> Optional[Document]:
        """Retrieve a specific document by patient ID and doc_id."""
        pass

    @abstractmethod
    def list_documents(self, patient_id: str) -> List[Document]:
        """Retrieve all documents belonging to a patient."""
        pass

    @abstractmethod
    def create_medication(self, patient_id: str, medication: Medication) -> Medication:
        """Persist a medication prescription with verified provenance under PK = PATIENT#<id>, SK = MED#<normalised_name>."""
        pass

    @abstractmethod
    def get_medications(self, patient_id: str) -> List[Medication]:
        """Retrieve all medications prescribed for a patient."""
        pass

    @abstractmethod
    def create_lab_result(self, patient_id: str, lab_result: LabResult, timestamp: Optional[str] = None) -> LabResult:
        """Persist an outpatient lab result with verified provenance under PK = PATIENT#<id>, SK = LAB#<iso_ts>#<analyte>."""
        pass

    @abstractmethod
    def get_lab_results(self, patient_id: str) -> List[LabResult]:
        """Retrieve all lab results for a patient."""
        pass

    @abstractmethod
    def create_diagnosis(self, patient_id: str, diagnosis: Diagnosis) -> Diagnosis:
        """Persist a diagnosis with verified provenance under PK = PATIENT#<id>, SK = DIAG#<code_or_slug>."""
        pass

    @abstractmethod
    def get_diagnoses(self, patient_id: str) -> List[Diagnosis]:
        """Retrieve all diagnoses for a patient."""
        pass

    @abstractmethod
    def create_plan_entry(self, patient_id: str, plan_entry: PlanEntry) -> PlanEntry:
        """Persist a daily care plan schedule slot under PK = PATIENT#<id>, SK = PLAN#<day_index>#<slot>."""
        pass

    @abstractmethod
    def get_plan_entries(self, patient_id: str) -> List[PlanEntry]:
        """Retrieve all care plan schedule slots for a patient."""
        pass

    @abstractmethod
    def update_plan_entry_done(
        self,
        patient_id: str,
        day_index: int,
        slot: str,
        done: bool = True,
        completed_at: Optional[str] = None
    ) -> PlanEntry:
        """Targeted update for plan entry adherence status without overwriting unrelated data."""
        pass

    @abstractmethod
    def create_alert(self, patient_id: str, alert: FiredAlert) -> FiredAlert:
        """Persist a fired deterministic escalation alert under PK = PATIENT#<id>, SK = ALERT#<iso_ts>."""
        pass

    @abstractmethod
    def get_alerts(self, patient_id: str) -> List[FiredAlert]:
        """Retrieve all fired escalation alerts for a patient."""
        pass

    @abstractmethod
    def get_patient_context(self, patient_id: str) -> PatientRecordResponse:
        """Single partition query (PK = PATIENT#<id>) returning complete canonical context."""
        pass
