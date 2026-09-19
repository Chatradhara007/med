"""Document metadata and lifecycle status schema.

Maps to DynamoDB:
PK = PATIENT#<id>
SK = DOC#<iso_ts>#<doc_id>
"""

from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document classifications per Section 6."""
    DISCHARGE_SUMMARY = "discharge_summary"
    LAB_REPORT = "lab_report"
    MEDICINE_STRIP = "medicine_strip"
    PRESCRIPTION = "prescription"
    UNKNOWN = "unknown"


class DocumentStatus(str, Enum):
    """The 10 document lifecycle statuses."""
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    RASTERISING = "rasterising"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    REVIEW_REQUIRED = "review_required"
    READY = "ready"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class Document(BaseModel):
    """Canonical document metadata."""
    patient_id: str = Field(..., min_length=1, description="Patient ID who owns this document")
    doc_id: str = Field(..., min_length=1, description="Unique document ID (e.g., d_014)")
    type: DocumentType = Field(default=DocumentType.UNKNOWN, description="Classified document type")
    s3_key: str = Field(..., min_length=1, description="S3 location raw/<patient_id>/<doc_id>.<ext>")
    status: DocumentStatus = Field(default=DocumentStatus.UPLOADING, description="Current ingestion status")
    pages: Union[List[str], int] = Field(
        default_factory=list,
        description="Number of pages or list of rasterised S3 page keys"
    )
    created_at: str = Field(..., min_length=1, description="ISO timestamp of document registration")
    updated_at: str = Field(..., min_length=1, description="ISO timestamp of last status transition")
    error_reason: Optional[str] = Field(default=None, description="Failure diagnostic message if status=failed")

    @property
    def pk(self) -> str:
        return f"PATIENT#{self.patient_id}"

    @property
    def sk(self) -> str:
        return f"DOC#{self.created_at}#{self.doc_id}"
