"""Patient demographic profile schema.

Maps to DynamoDB:
PK = PATIENT#<id>
SK = PROFILE
"""

from typing import Optional
from pydantic import BaseModel, Field


class Patient(BaseModel):
    """Canonical patient profile."""
    patient_id: str = Field(..., min_length=1, description="Unique patient identifier")
    name: str = Field(..., min_length=1, description="Full name of the patient")
    age: int = Field(..., ge=0, le=150, description="Patient age in years")
    sex: str = Field(..., min_length=1, description="Patient sex (e.g., M, F, Other)")
    language: str = Field(default="en", description="Primary preferred language")
    phone: str = Field(..., min_length=1, description="Patient contact telephone/SMS number")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of patient registration")

    @property
    def pk(self) -> str:
        return f"PATIENT#{self.patient_id}"

    @property
    def sk(self) -> str:
        return "PROFILE"
