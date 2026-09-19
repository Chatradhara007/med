"""Structured document extraction schemas.

Represents output from M1 (Ingest Pipeline) before persistence to DynamoDB single table.
Enforces the one invariant: every clinical item must carry verified provenance.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .document import DocumentStatus, DocumentType
from .medication import Medication
from .lab_result import LabResult
from .diagnosis import Diagnosis
from .provenance import ProvenanceEnvelope, ProvenanceStatus


class DischargeFollowup(BaseModel):
    """Extracted follow-up appointment instructions."""
    what: str = Field(..., min_length=1, description="Followup action or clinic name")
    when: str = Field(..., min_length=1, description="Timing or target date")
    provenance: ProvenanceEnvelope[Any] = Field(..., description="Source citation")


class DischargeRestriction(BaseModel):
    """Extracted dietary, physical, or lifestyle restrictions."""
    text: str = Field(..., min_length=1, description="Restriction description (e.g. low sodium diet)")
    provenance: ProvenanceEnvelope[Any] = Field(..., description="Source citation")


class DischargeSummaryExtraction(BaseModel):
    """Typed payload extracted from a hospital discharge summary per Section 10.1."""
    discharge_date: str = Field(..., min_length=1, description="Hospital discharge date string")
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    medications: List[Medication] = Field(default_factory=list)
    followups: List[DischargeFollowup] = Field(default_factory=list)
    restrictions: List[DischargeRestriction] = Field(default_factory=list)


class MedicineStripExtraction(BaseModel):
    """Typed payload extracted from a blister pack scan per Section 7 (M4)."""
    brand: str = Field(..., min_length=1, description="Commercial packaging brand name")
    salt: str = Field(..., min_length=1, description="Active chemical ingredient")
    strength: str = Field(..., min_length=1, description="Dose per unit (e.g., 500mg)")
    form: str = Field(default="tablet", description="Dosage formulation (tablet, capsule)")
    manufacturer: Optional[str] = Field(default=None, description="Pharmaceutical manufacturer")
    provenance: ProvenanceEnvelope[Any] = Field(..., description="Source citation")


class LabReportExtraction(BaseModel):
    """Typed payload extracted from an outpatient laboratory report per Section 7 (M3)."""
    report_date: Optional[str] = Field(default=None, description="Lab report issuance date")
    lab_results: List[LabResult] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Unified container for document extraction output across the pipeline."""
    doc_id: str = Field(..., min_length=1, description="Processed document ID")
    document_type: DocumentType = Field(..., description="Classified document type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall document extraction confidence")
    status: DocumentStatus = Field(default=DocumentStatus.EXTRACTING, description="Current lifecycle state")
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    medications: List[Medication] = Field(default_factory=list)
    lab_results: List[LabResult] = Field(default_factory=list)
    followups: List[DischargeFollowup] = Field(default_factory=list)
    restrictions: List[DischargeRestriction] = Field(default_factory=list)
    medicine_strip: Optional[MedicineStripExtraction] = Field(default=None)
    validation_status: str = Field(default="valid", description="'valid', 'invalid', or 'repaired'")
    validation_errors: List[str] = Field(default_factory=list)
    raw_json: Optional[Dict[str, Any]] = Field(default=None, description="Raw model response before parsing")

    def has_unreviewed_entities(self) -> bool:
        """Check if any extracted entity requires patient review (confidence < 0.85)."""
        all_envelopes: List[ProvenanceEnvelope[Any]] = [
            d.provenance for d in self.diagnoses
        ] + [
            m.provenance for m in self.medications
        ] + [
            l.provenance for l in self.lab_results
        ] + [
            f.provenance for f in self.followups
        ] + [
            r.provenance for r in self.restrictions
        ]
        if self.medicine_strip:
            all_envelopes.append(self.medicine_strip.provenance)
        return any(env.status == ProvenanceStatus.NEEDS_REVIEW for env in all_envelopes)
