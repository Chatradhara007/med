"""Domain schemas for M2 Care Plan module.

Prefers and re-exports shared canonical schemas to prevent drift.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Re-export canonical schemas from shared layer
from carethread.shared.schemas.plan_entry import PlanEntry, SlotName
from carethread.shared.schemas.alert_rule import AlertRule, AlertSeverity, FiredAlert
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)
from carethread.shared.schemas.extraction import DischargeFollowup, DischargeRestriction


class SymptomReport(BaseModel):
    """Patient symptom and vitals observation container for deterministic escalation evaluation."""
    fever_f: Optional[float] = Field(default=None, description="Body temperature in Fahrenheit")
    fever_hours: Optional[float] = Field(default=None, description="Duration of elevated fever in hours")
    chest_pain: Optional[bool] = Field(default=None, description="Presence of acute chest pain or pressure")
    blood_glucose: Optional[float] = Field(default=None, description="Blood glucose reading in mg/dL")
    shortness_of_breath: Optional[bool] = Field(default=None, description="Acute dyspnea or respiratory distress")
    systolic_bp: Optional[float] = Field(default=None, description="Systolic blood pressure in mmHg")


class CarePlanResult(BaseModel):
    """Summary container of a generated 7-day care plan."""
    patient_id: str
    days_covered: int
    entries: List[PlanEntry] = Field(default_factory=list)
    alerts: List[FiredAlert] = Field(default_factory=list)
