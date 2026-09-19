"""Diagnosis schema with mandatory provenance.

Maps to DynamoDB:
PK = PATIENT#<id>
SK = DIAG#<code_or_slug>
"""

from typing import Any, Optional
from pydantic import BaseModel, Field
from .provenance import ProvenanceEnvelope


class Diagnosis(BaseModel):
    """Canonical diagnosis entity with mandatory provenance tracking."""
    label: str = Field(..., min_length=1, description="Clinical diagnosis label (e.g. Type 2 Diabetes, Hypertension)")
    code_or_slug: Optional[str] = Field(default=None, description="Normalized slug or diagnostic code")
    icd_hint: Optional[str] = Field(default=None, description="Extracted or referenced ICD code hint if present")
    status: str = Field(default="active", description="Condition status: active or resolved")
    provenance: ProvenanceEnvelope[Any] = Field(
        ...,
        description="Mandatory provenance citation proving this diagnosis was extracted from a verified document"
    )

    @property
    def slug(self) -> str:
        base = self.code_or_slug or self.label
        return base.strip().lower().replace(" ", "_").replace("-", "_")

    def pk(self, patient_id: str) -> str:
        return f"PATIENT#{patient_id}"

    @property
    def sk(self) -> str:
        return f"DIAG#{self.slug}"
