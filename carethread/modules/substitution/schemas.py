"""Domain contracts and schemas for M4 Medicine Substitution module.

Prefers and re-exports shared canonical schemas to prevent drift.
Defines machine-readable contracts for substitution evaluation, candidate matching,
NTI hard-blocks, and interaction advisories.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

# Re-export canonical schemas from shared layer
from carethread.shared.schemas.extraction import MedicineStripExtraction
from carethread.shared.schemas.api import (
    DrugAlternative,
    SubstitutionRequest,
    SubstitutionResponse,
)
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)


class SubstitutionResultState(str, Enum):
    """Deterministic result state of medication substitution evaluation."""
    SUBSTITUTION_AVAILABLE = "SUBSTITUTION_AVAILABLE"
    SUBSTITUTION_BLOCKED_NTI = "SUBSTITUTION_BLOCKED_NTI"
    NO_MATCH = "NO_MATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DetectedMedicine(BaseModel):
    """Pharmaceutical details extracted from blister pack scan or manual input."""
    brand: Optional[str] = Field(default=None, description="Packaging trade or brand name")
    salt: Optional[str] = Field(default=None, description="Active chemical salt")
    strength: Optional[str] = Field(default=None, description="Dosage strength string (e.g. 500mg)")
    strength_mg: Optional[float] = Field(default=None, description="Numeric strength in milligrams if parsed")
    form: str = Field(default="tablet", description="Dosage formulation (tablet, capsule, etc.)")
    manufacturer: Optional[str] = Field(default=None, description="Packaging manufacturer")
    provenance: Optional[ProvenanceEnvelope[Any]] = Field(
        default=None,
        description="Source document citation proving origin of medicine identification"
    )
    confidence: Optional[float] = Field(default=None, description="OCR extraction confidence score")


class CandidateAlternative(BaseModel):
    """Bioequivalent pharmaceutical alternative from curated formulary."""
    brand: str = Field(..., min_length=1, description="Alternative brand name")
    salt: str = Field(..., min_length=1, description="Active chemical ingredient")
    strength: str = Field(..., min_length=1, description="Strength string")
    strength_mg: float = Field(..., description="Numeric strength in mg")
    form: str = Field(default="tablet", description="Dosage form (tablet, capsule)")
    manufacturer: Optional[str] = Field(default=None, description="Pharmaceutical company")
    price_inr: Optional[float] = Field(default=None, description="Approximate retail price in INR per strip")
    nti: bool = Field(default=False, description="Narrow therapeutic index flag")
    common_interactions: List[str] = Field(default_factory=list, description="Documented common interactions")
    strength_matches: bool = Field(default=True, description="True if numeric strength matches query drug")
    form_matches: bool = Field(default=True, description="True if dosage form matches query drug")
    divergence_notes: List[str] = Field(default_factory=list, description="Exposed differences in strength or form")


class InteractionAdvisory(BaseModel):
    """Advisory warning for drug interactions detected against canonical patient prescriptions."""
    active_medication: str = Field(..., description="Prescribed medication from patient context")
    candidate_drug: str = Field(..., description="Candidate substitute formulation")
    risk_description: str = Field(..., description="Documented clinical interaction advisory")
    severity: str = Field(default="advisory", description="Severity label (advisory, warning, critical)")


class SubstitutionAnalysisResult(BaseModel):
    """Comprehensive structured outcome of substitution evaluation."""
    state: SubstitutionResultState = Field(..., description="Primary classification state")
    blocked: bool = Field(default=False, description="True if substitution is prohibited (e.g. NTI hard-block)")
    title: Optional[str] = Field(default=None, description="Headline summary (e.g. Substitution Prohibited)")
    message: Optional[str] = Field(default=None, description="Plain language explanation for patient and pharmacist")
    clinical_rationale: Optional[str] = Field(default=None, description="Clinical pharmacology rationale")
    detected_medicine: Optional[DetectedMedicine] = Field(default=None, description="Extracted source medicine")
    alternatives: List[CandidateAlternative] = Field(
        default_factory=list,
        description="Salt-equivalent candidate formulations with price and divergence metadata"
    )
    interactions: List[InteractionAdvisory] = Field(
        default_factory=list,
        description="Advisory warnings cross-checked against canonical active medications"
    )
    interaction_check_status: str = Field(
        default="available",
        description="'available' if checked, or 'unavailable' if interaction data missing"
    )
    review_status: str = Field(
        default="confirmed",
        description="'confirmed' or 'needs_review' preserving low-confidence extraction uncertainty"
    )
    provenance: Optional[ProvenanceEnvelope[Any]] = Field(
        default=None,
        description="Inherited provenance from source medicine extraction"
    )
