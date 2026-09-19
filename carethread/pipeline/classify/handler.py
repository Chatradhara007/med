"""Classify state: vision model -> one of the five document types.

Section 6: ``unknown`` is a first-class outcome. When classification is not
confident the document is marked ``unsupported`` and the patient is shown a
clear message. A system that admits what it cannot read is more trustworthy
than one that guesses, and guessing routes the wrong extractor at a record.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from carethread.pipeline.common import (
    envelope_from_event,
    get_pipeline_repository,
    load_page_images,
    update_document_status,
)
from carethread.shared.bedrock import BedrockClientInterface, get_bedrock_client
from carethread.shared.prompts import CLASSIFY_PROMPT, CLASSIFY_SYSTEM
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.schemas.document import DocumentStatus, DocumentType

logger = logging.getLogger(__name__)

# Below this the classification is not trusted and the document is rejected
# rather than routed to an extractor.
CLASSIFICATION_THRESHOLD = float(os.environ.get("CLASSIFICATION_THRESHOLD", "0.6"))

# The model only ever sees the first pages; a discharge summary is identifiable
# from its first page and this keeps the call inside the Lambda timeout.
CLASSIFY_PAGE_LIMIT = int(os.environ.get("CLASSIFY_PAGE_LIMIT", "2"))

UNSUPPORTED_MESSAGE = (
    "We could not recognise this document. CareThread reads discharge "
    "summaries, lab reports, prescriptions and medicine strip photos. "
    "Please check the file and try uploading it again."
)


def _coerce_document_type(raw_value: Any) -> DocumentType:
    try:
        return DocumentType(str(raw_value).strip().lower())
    except ValueError:
        logger.warning("Model returned unrecognised document type %r", raw_value)
        return DocumentType.UNKNOWN


def classify_document(
    event: Dict[str, Any],
    repository: Optional[PatientRepositoryInterface] = None,
    bedrock: Optional[BedrockClientInterface] = None,
    s3_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Classify a rasterised document into one of the supported types."""
    envelope = envelope_from_event(event)
    patient_id = envelope["patient_id"]
    doc_id = envelope["doc_id"]
    bucket = envelope["bucket"]
    pages = envelope.get("pages") or []
    repo = get_pipeline_repository(repository)

    update_document_status(repo, patient_id, doc_id, DocumentStatus.CLASSIFYING)

    if not pages:
        envelope["document_type"] = DocumentType.UNKNOWN.value
        envelope["classification_confidence"] = 0.0
        envelope["unsupported_reason"] = UNSUPPORTED_MESSAGE
        update_document_status(
            repo,
            patient_id,
            doc_id,
            DocumentStatus.UNSUPPORTED,
            document_type=DocumentType.UNKNOWN,
            error_reason=UNSUPPORTED_MESSAGE,
        )
        return envelope

    client = bedrock or get_bedrock_client()
    images = load_page_images(bucket, pages, limit=CLASSIFY_PAGE_LIMIT, s3_client=s3_client)

    result = client.invoke_json(
        prompt=CLASSIFY_PROMPT,
        images=images,
        system=CLASSIFY_SYSTEM,
        max_tokens=512,
    )

    document_type = _coerce_document_type(result.get("document_type"))
    try:
        confidence = float(result.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    reason = str(result.get("reason", "")).strip()

    envelope["document_type"] = document_type.value
    envelope["classification_confidence"] = confidence
    envelope["classification_reason"] = reason

    if document_type == DocumentType.UNKNOWN or confidence < CLASSIFICATION_THRESHOLD:
        logger.info(
            "Document %s not confidently classified (type=%s confidence=%.2f)",
            doc_id,
            document_type.value,
            confidence,
        )
        envelope["document_type"] = DocumentType.UNKNOWN.value
        envelope["unsupported_reason"] = UNSUPPORTED_MESSAGE
        update_document_status(
            repo,
            patient_id,
            doc_id,
            DocumentStatus.UNSUPPORTED,
            document_type=DocumentType.UNKNOWN,
            error_reason=UNSUPPORTED_MESSAGE,
        )
        return envelope

    update_document_status(
        repo,
        patient_id,
        doc_id,
        DocumentStatus.EXTRACTING,
        document_type=document_type,
    )
    logger.info(
        "Classified document %s as %s (confidence=%.2f)", doc_id, document_type.value, confidence
    )
    return envelope


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda entrypoint for the Classify state."""
    return classify_document(event)
