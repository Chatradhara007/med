"""CareThread canonical shared data contracts and provenance layer."""

from .provenance import (
    CONFIDENCE_THRESHOLD,
    ProvenanceStatus,
    ProvenanceSource,
    ProvenanceEnvelope,
    ProvenancedEntity,
    evaluate_confidence,
)
from .patient import Patient
from .document import Document, DocumentStatus, DocumentType
from .medication import Medication, MedicationValue
from .lab_result import LabResult, LabResultValue
from .diagnosis import Diagnosis
from .plan_entry import PlanEntry, SlotName
from .alert_rule import AlertRule, AlertSeverity, FiredAlert
from .extraction import (
    DischargeFollowup,
    DischargeRestriction,
    DischargeSummaryExtraction,
    MedicineStripExtraction,
    LabReportExtraction,
    ExtractionResult,
)
from .api import (
    DocumentCreateRequest,
    DocumentCreateResponse,
    DocumentStatusResponse,
    PatientRecordResponse,
    RecordFieldPatchRequest,
    RecordFieldPatchResponse,
    DrugAlternative,
    SubstitutionRequest,
    SubstitutionResponse,
    PlanDoneResponse,
)

__all__ = [
    # Provenance
    "CONFIDENCE_THRESHOLD",
    "ProvenanceStatus",
    "ProvenanceSource",
    "ProvenanceEnvelope",
    "ProvenancedEntity",
    "evaluate_confidence",
    # Core Entities
    "Patient",
    "Document",
    "DocumentStatus",
    "DocumentType",
    "Medication",
    "MedicationValue",
    "LabResult",
    "LabResultValue",
    "Diagnosis",
    "PlanEntry",
    "SlotName",
    "AlertRule",
    "AlertSeverity",
    "FiredAlert",
    # Extraction
    "DischargeFollowup",
    "DischargeRestriction",
    "DischargeSummaryExtraction",
    "MedicineStripExtraction",
    "LabReportExtraction",
    "ExtractionResult",
    # API Contracts
    "DocumentCreateRequest",
    "DocumentCreateResponse",
    "DocumentStatusResponse",
    "PatientRecordResponse",
    "RecordFieldPatchRequest",
    "RecordFieldPatchResponse",
    "DrugAlternative",
    "SubstitutionRequest",
    "SubstitutionResponse",
    "PlanDoneResponse",
]
