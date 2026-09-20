"""Lab result schema with mandatory provenance and reference range handling.

Maps to DynamoDB:
PK = PATIENT#<id>
SK = LAB#<iso_ts>#<analyte>
"""

from typing import Any, Optional, Union
from pydantic import BaseModel, Field, computed_field
from .provenance import ProvenanceEnvelope


class LabResultValue(BaseModel):
    """Structured attributes of a laboratory measurement."""
    analyte: str = Field(..., min_length=1, description="Analyte name (e.g. Serum Creatinine, Fasting Blood Sugar)")
    value: Union[float, str] = Field(..., description="Reported numeric or qualitative lab value")
    unit: str = Field(..., min_length=1, description="Standard or reported measurement unit (e.g., mg/dL, mmol/L)")
    ref_low: Optional[float] = Field(default=None, description="Lower reference interval bound")
    ref_high: Optional[float] = Field(default=None, description="Upper reference interval bound")
    ref_source: str = Field(default="printed", description="'printed' if from document, 'fallback_ref_ranges' if imputed")


class LabResult(BaseModel):
    """Canonical lab result entity with mandatory provenance and deviation scoring."""
    analyte: str = Field(..., min_length=1, description="Analyte identifier/name")
    value: Union[float, str] = Field(..., description="Measured analyte value")
    unit: str = Field(..., min_length=1, description="Unit of measurement")
    ref_low: Optional[float] = Field(default=None, description="Reported lower reference range limit")
    ref_high: Optional[float] = Field(default=None, description="Reported upper reference range limit")
    ref_source: str = Field(default="printed", description="'printed' or 'fallback_ref_ranges'")
    deviation_score: Optional[float] = Field(
        default=None,
        description="Normalised deviation from range: (value - ref_high) / (ref_high - ref_low) if high"
    )
    flag: Optional[str] = Field(default=None, description="Clinical alert flag: normal, high, low, critical")
    reported_at: Optional[str] = Field(
        default=None,
        description=(
            "ISO timestamp this result was recorded under. Forms part of the sort "
            "key, so it is set by the repository on write and must not be edited."
        ),
    )
    provenance: ProvenanceEnvelope[Any] = Field(
        ...,
        description="Mandatory provenance citation proving this result was extracted from a verified lab report"
    )

    @classmethod
    def normalise_analyte(cls, analyte: str) -> str:
        return analyte.strip().lower().replace(" ", "_").replace("-", "_")

    def pk(self, patient_id: str) -> str:
        return f"PATIENT#{patient_id}"

    def sk_for(self, timestamp: str) -> str:
        """Build the sort key for a given recording timestamp."""
        return f"LAB#{timestamp}#{self.normalise_analyte(self.analyte)}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sk(self) -> str:
        """Sort key, serialised so the UI can address this row.

        Unlike the other entities the lab key embeds the recording timestamp,
        which only exists once the row has been written. Before then this is a
        provisional, analyte-scoped key: stable enough to use as a list key,
        but not resolvable in storage.
        """
        if not self.reported_at:
            return f"LAB#{self.normalise_analyte(self.analyte)}"
        return self.sk_for(self.reported_at)
