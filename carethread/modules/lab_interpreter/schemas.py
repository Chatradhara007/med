"""Domain schemas for M3 Lab Interpreter module.

Prefers and re-exports shared canonical schemas to prevent drift.
Defines machine-readable contracts for interpreted lab findings and summary reports.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

# Re-export canonical schemas from shared layer
from carethread.shared.schemas.lab_result import LabResult, LabResultValue
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)


class ReferenceRangeSource(str, Enum):
    """Source of the reference range used for interpretation."""
    REPORT = "REPORT"
    FALLBACK = "FALLBACK"
    NONE = "NONE"


class FindingStatus(str, Enum):
    """Deterministic clinical classification of analyte value against reference interval."""
    BELOW = "below"
    WITHIN = "within"
    ABOVE = "above"
    UNKNOWN = "unknown"


class InterpretedLabFinding(BaseModel):
    """Structured, provenance-grounded interpretation of a single analyte measurement."""
    analyte: str = Field(..., min_length=1, description="Analyte name (e.g. Serum Creatinine)")
    value: Union[float, str] = Field(..., description="Reported numeric or qualitative lab value")
    unit: str = Field(..., description="Measurement unit (e.g. mg/dL, mEq/L)")
    ref_low: Optional[float] = Field(default=None, description="Lower reference interval bound")
    ref_high: Optional[float] = Field(default=None, description="Upper reference interval bound")
    ref_source: ReferenceRangeSource = Field(
        default=ReferenceRangeSource.REPORT,
        description="Explicit source of reference interval: REPORT, FALLBACK, or NONE"
    )
    status: FindingStatus = Field(
        default=FindingStatus.WITHIN,
        description="Deterministic position relative to reference range: below, within, above, unknown"
    )
    deviation_score: Optional[float] = Field(
        default=None,
        description="Deterministic normalized deviation magnitude from reference bounds"
    )
    rank: int = Field(
        default=1,
        ge=1,
        description="Deterministic ranking position (abnormal findings first by deviation)"
    )
    context_diagnoses: List[str] = Field(
        default_factory=list,
        description="Relevant active diagnoses from canonical patient record"
    )
    context_medications: List[str] = Field(
        default_factory=list,
        description="Relevant active prescribed medications from canonical patient record"
    )
    context_notes: List[str] = Field(
        default_factory=list,
        description="Deterministic clinical advisory notes (e.g. Metformin + elevated Creatinine)"
    )
    explanation: str = Field(
        default="",
        description="Patient-readable plain language explanation grounded in structured facts"
    )
    provenance: ProvenanceEnvelope[Any] = Field(
        ...,
        description="Mandatory provenance citation inherited unbroken from the source LabResult"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Extraction confidence score from OCR/M1 pipeline"
    )
    review_status: str = Field(
        default="confirmed",
        description="Review gate status: confirmed or needs_review (strictly preserved from source)"
    )


class LabInterpretationReport(BaseModel):
    """Comprehensive machine-readable lab interpretation report for a patient episode."""
    patient_id: str = Field(..., min_length=1, description="Canonical patient identifier")
    total_findings: int = Field(default=0, ge=0, description="Total count of analyzed lab findings")
    abnormal_count: int = Field(default=0, ge=0, description="Count of findings outside reference bounds")
    top_findings: List[InterpretedLabFinding] = Field(
        default_factory=list,
        description="Top 3 abnormal findings ranked by normalized deviation"
    )
    all_findings: List[InterpretedLabFinding] = Field(
        default_factory=list,
        description="All analyzed lab findings ranked deterministically"
    )
    cross_module_alerts: List[str] = Field(
        default_factory=list,
        description="Critical cross-module clinical alerts (e.g. Metformin + acute renal elevation)"
    )
    generated_at: str = Field(..., description="ISO 8601 UTC timestamp of report generation")
