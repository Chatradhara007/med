"""Deterministic alert rule and escalation schema.

Maps to DynamoDB:
PK = PATIENT#<id>
SK = ALERT#<iso_ts>

SAFETY CONSTRAINT:
The rules decide. LLMs format and translate.
Escalation advice is strictly deterministic and never LLM-generated.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    """Clinical severity levels for escalation rules."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertRule(BaseModel):
    """Static clinical escalation rule definition (from rules.yaml)."""
    id: str = Field(..., min_length=1, description="Unique static rule identifier (e.g., fever_persistent)")
    when: Optional[str] = Field(default=None, description="Deterministic conditional expression")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    message: str = Field(..., min_length=1, description="Standard patient escalation instructions")
    applies_if_diagnosis: Optional[List[str]] = Field(
        default=None,
        description="List of diagnosis slugs/labels required for this rule to activate"
    )


class FiredAlert(BaseModel):
    """Active escalation alert record fired by deterministic evaluation."""
    alert_id: str = Field(..., min_length=1, description="Unique event alert ID")
    rule_id: str = Field(..., min_length=1, description="ID of static rule that triggered this alert")
    severity: AlertSeverity = Field(..., description="Severity level")
    message: str = Field(..., min_length=1, description="Escalation message displayed to patient")
    fired_at: str = Field(..., min_length=1, description="ISO timestamp when rule fired")
    acknowledged: bool = Field(default=False, description="Whether patient acknowledged this alert")
    cross_module_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Evidence context connecting diagnoses, medications, or lab deviations"
    )

    def pk(self, patient_id: str) -> str:
        return f"PATIENT#{patient_id}"

    @property
    def sk(self) -> str:
        return f"ALERT#{self.fired_at}"
