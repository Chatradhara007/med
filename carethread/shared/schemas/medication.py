"""Medication prescription schema with mandatory provenance.

Maps to DynamoDB:
PK = PATIENT#<id>
SK = MED#<normalised_name>
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from .provenance import ProvenanceEnvelope


class MedicationValue(BaseModel):
    """The structured attributes of a prescribed medication."""
    name: str = Field(..., min_length=1, description="Brand or common medication name")
    salt: str = Field(..., min_length=1, description="Active chemical salt/generic name")
    strength: str = Field(..., min_length=1, description="Formulation strength (e.g., 500mg, 10mg)")
    form: str = Field(default="tablet", description="Dosage form (e.g., tablet, capsule, syrup, injection)")
    freq: str = Field(..., min_length=1, description="Dosing frequency (e.g., OD, BD, TDS, QID, PRN)")
    duration_days: int = Field(..., ge=0, description="Prescribed duration in days")
    start_date: Optional[str] = Field(default=None, description="Prescription initiation date")
    instructions: Optional[str] = Field(default=None, description="Special administration instructions")


class Medication(BaseModel):
    """Canonical medication entity with mandatory provenance tracking."""
    name: str = Field(..., min_length=1, description="Brand or prescribed name")
    salt: str = Field(..., min_length=1, description="Active pharmaceutical ingredient / salt")
    strength: str = Field(..., min_length=1, description="Strength (e.g., 500mg)")
    form: str = Field(default="tablet", description="Form (tablet, capsule, etc.)")
    freq: str = Field(..., min_length=1, description="Frequency (e.g., BD, OD)")
    duration_days: int = Field(..., ge=0, description="Duration in days")
    start_date: Optional[str] = Field(default=None, description="Start date ISO string")
    instructions: Optional[str] = Field(default=None, description="Specific instructions (e.g. after food)")
    provenance: ProvenanceEnvelope[Any] = Field(
        ...,
        description="Mandatory provenance citation proving this prescription was extracted from a document"
    )

    @classmethod
    def normalise_name(cls, name: str) -> str:
        """Normalise medication name for sort key generation."""
        return name.strip().lower().replace(" ", "_").replace("-", "_")

    def pk(self, patient_id: str) -> str:
        return f"PATIENT#{patient_id}"

    @property
    def sk(self) -> str:
        return f"MED#{self.normalise_name(self.name)}"
