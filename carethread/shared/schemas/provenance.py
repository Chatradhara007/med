"""Provenance contract and confidence gating semantics for CareThread.

THE ONE INVARIANT: No value reaches the UI without a source.
Every extracted field must be traceable back to its source document region.
"""

from enum import Enum
from typing import Any, Generic, List, TypeVar
from pydantic import BaseModel, Field, field_validator, model_validator

CONFIDENCE_THRESHOLD = 0.85


class ProvenanceStatus(str, Enum):
    """Extraction lifecycle status."""
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"


def evaluate_confidence(confidence: float) -> ProvenanceStatus:
    """Evaluate confidence against the non-negotiable 0.85 threshold.

    confidence >= 0.85 -> confirmed
    confidence < 0.85  -> needs_review
    """
    if confidence >= CONFIDENCE_THRESHOLD:
        return ProvenanceStatus.CONFIRMED
    return ProvenanceStatus.NEEDS_REVIEW


class ProvenanceSource(BaseModel):
    """Exact citation details pinning an extracted datum to physical scan coordinates."""
    doc_id: str = Field(..., min_length=1, description="Identifier of the source document")
    page: int = Field(..., ge=1, description="1-indexed page number in the document")
    bbox: List[float] = Field(
        ...,
        description="[ymin, xmin, ymax, xmax] coordinates normalized to a 0-1000 integer/float grid"
    )
    verbatim: str = Field(..., min_length=1, description="Exact verbatim substring extracted from scan")
    bbox_exact: bool = Field(
        default=True,
        description=(
            "False when the verbatim string could not be located in the document's "
            "text layer and bbox is the whole page. The citation is still real -- "
            "the quote and the page are known -- but the overlay cannot be tight, "
            "so the UI should show a page-level citation rather than a box."
        ),
    )

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        if len(v) != 4:
            raise ValueError(f"Bounding box must contain exactly 4 coordinates [ymin, xmin, ymax, xmax], got {len(v)}")
        ymin, xmin, ymax, xmax = v
        for coord in (ymin, xmin, ymax, xmax):
            if coord < 0.0 or coord > 1000.0:
                raise ValueError(f"Coordinate {coord} out of normalized range [0, 1000]")
        if ymin > ymax:
            raise ValueError(f"Invalid bbox: ymin ({ymin}) cannot exceed ymax ({ymax})")
        if xmin > xmax:
            raise ValueError(f"Invalid bbox: xmin ({xmin}) cannot exceed xmax ({xmax})")
        return v


T = TypeVar("T")


class ProvenanceEnvelope(BaseModel, Generic[T]):
    """The canonical provenance envelope mandated by Section 5 of the build spec.

    Wraps any extracted field with its source citation, confidence score, and status.
    """
    field: str = Field(..., min_length=1, description="Field name or entity type identifier")
    value: T = Field(..., description="The typed value or dictionary of the extracted entity")
    source: ProvenanceSource = Field(..., description="Source citation with page and coordinates")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    status: ProvenanceStatus = Field(
        default=ProvenanceStatus.EXTRACTED,
        description="Lifecycle status: extracted -> confirmed (>=0.85) or needs_review (<0.85)"
    )

    @model_validator(mode="after")
    def apply_confidence_gating(self) -> "ProvenanceEnvelope[T]":
        """Enforce documented confidence gate when status is initial EXTRACTED."""
        if self.status == ProvenanceStatus.EXTRACTED:
            self.status = evaluate_confidence(self.confidence)
        return self


class ProvenancedEntity(BaseModel):
    """Base class for clinical entities requiring mandatory provenance."""
    provenance: ProvenanceEnvelope[Any] = Field(
        ...,
        description="Mandatory provenance citation proving this entity originates from a verified document"
    )
