"""Domain schemas and contracts for M5 Reminders module.

Defines schemas for scheduled reminder events, single-table persistence records,
SNS publish results, and execution outcomes.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from carethread.shared.schemas.plan_entry import PlanEntry, SlotName


class ReminderStatus(str, Enum):
    """Lifecycle states of a post-discharge care plan reminder."""
    SCHEDULED = "scheduled"
    SENT = "sent"
    SUPPRESSED_COMPLETED = "suppressed_completed"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderEvent(BaseModel):
    """EventBridge event payload triggering reminder evaluation."""
    reminder_id: str = Field(..., min_length=1, description="Unique identifier for reminder trigger")
    patient_id: str = Field(..., min_length=1, description="Target patient identifier")
    day_index: int = Field(..., ge=0, le=6, description="Day index in care plan (0 to 6)")
    slot: SlotName = Field(..., description="Daily schedule slot")
    scheduled_time: str = Field(..., description="ISO 8601 target trigger timestamp")
    demo_mode: bool = Field(default=False, description="Flag indicating 30-second demo compression")
    idempotency_key: str = Field(..., min_length=1, description="Unique key guaranteeing single delivery")


class ReminderRecord(BaseModel):
    """Single-table DynamoDB record tracking reminder execution and idempotency.

    Maps to DynamoDB:
    PK = PATIENT#<patient_id>
    SK = REMINDER#<reminder_id>
    """
    reminder_id: str = Field(..., min_length=1)
    patient_id: str = Field(..., min_length=1)
    day_index: int = Field(..., ge=0, le=6)
    slot: SlotName = Field(...)
    scheduled_time: str = Field(...)
    status: ReminderStatus = Field(default=ReminderStatus.SCHEDULED)
    sent_at: Optional[str] = Field(default=None)
    created_at: str = Field(...)
    idempotency_key: str = Field(...)

    @property
    def pk(self) -> str:
        return f"PATIENT#{self.patient_id}"

    @property
    def sk(self) -> str:
        return f"REMINDER#{self.reminder_id}"


class PublishResult(BaseModel):
    """Result of notification delivery to destination topic/endpoint."""
    success: bool = Field(...)
    message_id: Optional[str] = Field(default=None)
    destination: str = Field(...)
    error: Optional[str] = Field(default=None)


class ReminderExecutionResult(BaseModel):
    """Structured outcome returned by the reminder evaluation handler."""
    status_code: int = Field(...)
    status: ReminderStatus = Field(...)
    reminder_id: str = Field(...)
    message: str = Field(...)
    published: bool = Field(default=False)
    error: Optional[str] = Field(default=None)
