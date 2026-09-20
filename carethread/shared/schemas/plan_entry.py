"""Care plan entry schema with mandatory provenance.

Maps to DynamoDB:
PK = PATIENT#<id>
SK = PLAN#<day_index>#<slot>
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, computed_field
from .provenance import ProvenanceEnvelope


class SlotName(str, Enum):
    """The 4 daily medication schedule slots."""
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


class PlanEntry(BaseModel):
    """Canonical day-by-day care plan entry with mandatory provenance."""
    day_index: int = Field(..., ge=0, le=6, description="Day index in post-discharge plan (Day 0 to Day 6)")
    slot: SlotName = Field(..., description="Target time slot: morning, afternoon, evening, night")
    action: str = Field(..., min_length=1, description="Specific clinical administration action (e.g. Take Tab Metformin 500mg)")
    med_ref: str = Field(..., min_length=1, description="Reference key to active medication (e.g. MED#metformin)")
    time_target: Optional[str] = Field(default=None, description="Recommended time of day (e.g., 08:00, 13:00)")
    done: bool = Field(default=False, description="Adherence completion status")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when dose was confirmed taken")
    provenance: ProvenanceEnvelope[Any] = Field(
        ...,
        description="Mandatory provenance citation linking this dose to a verified prescription line"
    )

    def pk(self, patient_id: str) -> str:
        return f"PATIENT#{patient_id}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sk(self) -> str:
        """Sort key, serialised so the UI can address this row for PATCH."""
        slot_str = self.slot.value if isinstance(self.slot, SlotName) else str(self.slot)
        return f"PLAN#{self.day_index}#{slot_str}"
