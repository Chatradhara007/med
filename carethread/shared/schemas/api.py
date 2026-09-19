"""Request and response contract schemas for CareThread REST APIs.

Section 9 API Contract:
All endpoints authenticated via Cognito JWT authorizer.
patient_id is derived exclusively from the JWT sub claim and is never accepted from request body.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, model_validator
from .document import Document, DocumentStatus, DocumentType
from .patient import Patient
from .medication import Medication
from .lab_result import LabResult
from .diagnosis import Diagnosis
from .plan_entry import PlanEntry, SlotName
from .alert_rule import FiredAlert
from .provenance import ProvenanceStatus


# --- POST /documents ---
class DocumentCreateRequest(BaseModel):
    """Payload to initiate direct-to-S3 document upload."""
    filename: str = Field(..., min_length=1, description="Original filename uploaded by patient")
    content_type: str = Field(..., min_length=1, description="MIME type (e.g. application/pdf, image/png)")


class DocumentCreateResponse(BaseModel):
    """Response returning the unique document ID and presigned S3 PUT URL."""
    doc_id: str = Field(..., min_length=1, description="Generated document identifier (e.g., d_014)")
    upload_url: str = Field(..., min_length=1, description="Presigned S3 PUT URL valid for 300 seconds")


# --- GET /documents/{id} ---
class DocumentStatusResponse(BaseModel):
    """Processing and readiness status for an uploaded document."""
    doc_id: str = Field(..., min_length=1)
    status: DocumentStatus = Field(..., description="Current document status")
    type: Optional[DocumentType] = Field(default=None, description="Classified document type")
    pages: List[str] = Field(default_factory=list, description="List of rasterised page S3 keys")
    error: Optional[str] = Field(default=None, description="Failure diagnostic message if status=failed")


# --- GET /record ---
class PatientRecordResponse(BaseModel):
    """Full canonical episodic patient record returned by single query Query(PK = PATIENT#<id>)."""
    patient: Optional[Patient] = Field(default=None, description="Patient profile demographics")
    documents: List[Document] = Field(default_factory=list, description="All patient documents")
    diagnoses: List[Diagnosis] = Field(default_factory=list, description="Active and historical diagnoses")
    medications: List[Medication] = Field(default_factory=list, description="Prescribed medications")
    lab_results: List[LabResult] = Field(default_factory=list, description="Reported laboratory results")
    plan_entries: List[PlanEntry] = Field(default_factory=list, description="Day-by-day care schedule slots")
    alerts: List[FiredAlert] = Field(default_factory=list, description="Active escalation warnings")


# --- PATCH /record/field ---
class RecordFieldPatchRequest(BaseModel):
    """Payload to confirm or correct a field flagged as needs_review."""
    sk: str = Field(..., min_length=1, description="Target DynamoDB Sort Key (e.g. MED#metformin)")
    field: str = Field(..., min_length=1, description="Attribute name to update (e.g., strength)")
    value: Any = Field(..., description="New corrected value")


class RecordFieldPatchResponse(BaseModel):
    """Response confirming field update."""
    status: ProvenanceStatus = Field(
        default=ProvenanceStatus.CONFIRMED,
        description="Updated field status, transitions to confirmed"
    )
    updated_item: Dict[str, Any] = Field(..., description="Updated DynamoDB item representation")


# --- POST /substitution ---
class DrugAlternative(BaseModel):
    """Bioequivalent drug alternative from curated formulary."""
    brand: str = Field(..., min_length=1, description="Alternative brand name")
    salt: str = Field(..., min_length=1, description="Active salt formulation")
    strength_mg: Union[float, int] = Field(..., description="Formulation strength in mg")
    form: str = Field(default="tablet", description="Dosage form (tablet, capsule)")
    manufacturer: Optional[str] = Field(default=None, description="Pharmaceutical manufacturer")
    price_inr: Optional[float] = Field(default=None, description="Approximate price in INR")
    nti: bool = Field(default=False, description="Narrow Therapeutic Index flag")
    common_interactions: List[str] = Field(default_factory=list, description="Known interaction risks")


class SubstitutionRequest(BaseModel):
    """Request payload to check pharmacy substitution.

    Can be initiated either from an uploaded medicine strip (doc_id)
    or by explicit brand and strength query.
    """
    doc_id: Optional[str] = Field(default=None, description="Document ID of scanned medicine strip")
    brand: Optional[str] = Field(default=None, description="Brand name of prescribed drug")
    strength: Optional[str] = Field(default=None, description="Strength of prescribed drug")

    @model_validator(mode="after")
    def validate_input_presence(self) -> "SubstitutionRequest":
        if not self.doc_id and not (self.brand and self.strength):
            raise ValueError("Substitution check requires either 'doc_id' or both 'brand' and 'strength'")
        return self


class SubstitutionResponse(BaseModel):
    """Result of substitution evaluation."""
    blocked: bool = Field(..., description="True if drug is on NTI list (HARD BLOCK)")
    reason: Optional[str] = Field(default=None, description="Refusal rationale if blocked")
    alternatives: List[DrugAlternative] = Field(
        default_factory=list,
        description="Bioequivalent formulations with same salt, strength, and form"
    )
    interactions: List[str] = Field(
        default_factory=list,
        description="Advisory warnings cross-checked against active MED# prescriptions"
    )


# --- POST /plan/{day}/{slot}/done ---
class PlanDoneResponse(BaseModel):
    """Response confirming dose adherence recording."""
    day: int = Field(..., ge=0, le=6, description="Day index of care plan")
    slot: SlotName = Field(..., description="Schedule slot (morning, afternoon, evening, night)")
    done: bool = Field(default=True, description="Adherence confirmation flag")
    completed_at: str = Field(..., min_length=1, description="ISO timestamp of dose confirmation")
