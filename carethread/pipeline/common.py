"""Shared plumbing for the M1 ingest pipeline states.

Every state receives and returns the same envelope so the Step Functions
definition stays readable and each Lambda can be invoked standalone with
``sam local invoke``:

    {
      "patient_id": "...",
      "doc_id": "...",
      "bucket": "...",
      "key": "raw/<patient_id>/<doc_id>.pdf",
      "pages": ["pages/<patient_id>/<doc_id>/p1.png", ...],
      "document_type": "discharge_summary",
      "extraction": { ... }
    }
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from carethread.shared.repository import get_repository
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType

logger = logging.getLogger(__name__)

# raw/<patient_id>/<doc_id>.<ext>
RAW_KEY_RE = re.compile(r"^raw/(?P<patient_id>[^/]+)/(?P<doc_id>[^/.]+)\.(?P<ext>[^/.]+)$")

PAGE_PREFIX = "pages"


class PipelineError(RuntimeError):
    """Recoverable pipeline failure. Step Functions retries these."""


class UnsupportedDocumentError(PipelineError):
    """The document cannot be read. Never retried -- it routes to HandleFailure."""


def parse_raw_key(key: str) -> Tuple[str, str, str]:
    """Split an S3 raw object key into (patient_id, doc_id, extension)."""
    match = RAW_KEY_RE.match(key)
    if not match:
        raise UnsupportedDocumentError(
            f"S3 key '{key}' does not match the raw/<patient_id>/<doc_id>.<ext> layout"
        )
    return match.group("patient_id"), match.group("doc_id"), match.group("ext").lower()


def page_key(patient_id: str, doc_id: str, page_number: int) -> str:
    """S3 key for a rasterised page image (1-indexed, per Section 4.2)."""
    return f"{PAGE_PREFIX}/{patient_id}/{doc_id}/p{page_number}.png"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_s3_client(client: Optional[Any] = None) -> Any:
    if client is not None:
        return client
    import boto3

    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def get_pipeline_repository(
    repository: Optional[PatientRepositoryInterface] = None,
) -> PatientRepositoryInterface:
    return repository if repository is not None else get_repository()


def fetch_object(bucket: str, key: str, s3_client: Optional[Any] = None) -> bytes:
    """Read an object out of S3."""
    client = get_s3_client(s3_client)
    try:
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        return body.read() if hasattr(body, "read") else bytes(body)
    except Exception as exc:
        raise PipelineError(f"Failed to read s3://{bucket}/{key}: {exc}") from exc


def put_object(
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "image/png",
    s3_client: Optional[Any] = None,
) -> str:
    """Write an object to S3 with server-side encryption on."""
    client = get_s3_client(s3_client)
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
    except Exception as exc:
        raise PipelineError(f"Failed to write s3://{bucket}/{key}: {exc}") from exc
    return key


def load_page_images(
    bucket: str,
    page_keys: List[str],
    limit: Optional[int] = None,
    s3_client: Optional[Any] = None,
) -> List[bytes]:
    """Fetch rasterised page images for a multimodal model call."""
    selected = page_keys[:limit] if limit else page_keys
    return [fetch_object(bucket, key, s3_client=s3_client) for key in selected]


def update_document_status(
    repository: PatientRepositoryInterface,
    patient_id: str,
    doc_id: str,
    status: DocumentStatus,
    document_type: Optional[DocumentType] = None,
    pages: Optional[List[str]] = None,
    error_reason: Optional[str] = None,
) -> Optional[Document]:
    """Advance a document through its lifecycle, keying off the canonical record.

    Returns None when the document row is absent; callers decide whether that
    is fatal. Status updates must never mask the underlying pipeline error, so
    failures here are logged rather than raised.
    """
    try:
        document = repository.get_document(patient_id, doc_id)
    except Exception as exc:
        logger.error("Could not load document %s for status update: %s", doc_id, exc)
        return None

    if document is None:
        logger.warning("Document %s not found for patient %s", doc_id, patient_id)
        return None

    document.status = status
    document.updated_at = now_iso()
    if document_type is not None:
        document.type = document_type
    if pages is not None:
        document.pages = pages
    # error_reason is sticky only while the document is failed/unsupported
    if error_reason is not None:
        document.error_reason = error_reason
    elif status not in (DocumentStatus.FAILED, DocumentStatus.UNSUPPORTED):
        document.error_reason = None

    try:
        repository.update_document(document)
    except Exception as exc:
        logger.error("Failed to persist status %s for document %s: %s", status, doc_id, exc)
        return None
    return document


def envelope_from_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise the incoming event into the pipeline envelope.

    Accepts the EventBridge S3 shape used by the state machine's trigger as
    well as a plain envelope, so each state stays invocable on its own.
    """
    payload = dict(event or {})
    detail = payload.get("detail")
    if isinstance(detail, dict):
        bucket = (detail.get("bucket") or {}).get("name")
        key = (detail.get("object") or {}).get("key")
        if bucket and key:
            payload = {"bucket": bucket, "key": key}

    bucket = payload.get("bucket") or os.environ.get("DOC_BUCKET")
    key = payload.get("key")

    if key and not (payload.get("patient_id") and payload.get("doc_id")):
        patient_id, doc_id, ext = parse_raw_key(key)
        payload.setdefault("patient_id", patient_id)
        payload.setdefault("doc_id", doc_id)
        payload.setdefault("extension", ext)

    if not payload.get("patient_id") or not payload.get("doc_id"):
        raise UnsupportedDocumentError(
            "Pipeline event is missing patient_id/doc_id and carries no parseable raw key"
        )
    if not bucket:
        raise PipelineError("Pipeline event is missing the document bucket")

    payload["bucket"] = bucket
    return payload
