"""Extract state: type-specific structured extraction with real provenance.

The model transcribes; it never infers. Each returned object carries a
``source.verbatim`` substring, which this state resolves into a page and a
bounding box (Section 10.3) so that every value shown to the patient is
traceable to a region of a document they uploaded.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from carethread.pipeline.bbox import (
    TextLayer,
    derive_source_location,
    extract_pdf_text_layer,
)
from carethread.pipeline.common import (
    PipelineError,
    envelope_from_event,
    fetch_object,
    get_pipeline_repository,
    load_page_images,
    update_document_status,
)
from carethread.shared.bedrock import BedrockClientInterface, get_bedrock_client
from carethread.shared.prompts import EXTRACTION_SYSTEM, prompt_for_type
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.schemas.document import DocumentStatus, DocumentType

logger = logging.getLogger(__name__)

EXTRACT_PAGE_LIMIT = 10

# Collections whose items each carry their own source citation.
ENTITY_COLLECTIONS = ("diagnoses", "medications", "lab_results", "followups", "restrictions")


def _resolve_text_layer(
    bucket: str, key: Optional[str], extension: Optional[str], s3_client: Optional[Any]
) -> Optional[TextLayer]:
    """Load a text layer for bbox matching when the upload is a digital PDF."""
    if not key or (extension or "").lower() != "pdf":
        return None
    try:
        raw = fetch_object(bucket, key, s3_client=s3_client)
    except PipelineError as exc:
        logger.warning("Could not re-read raw object for text layer: %s", exc)
        return None
    return extract_pdf_text_layer(raw)


def _attach_location(
    obj: Dict[str, Any], doc_id: str, text_layer: Optional[TextLayer]
) -> Dict[str, Any]:
    """Resolve one object's verbatim citation into a full provenance source."""
    source = obj.get("source")
    if not isinstance(source, dict):
        source = {}
    verbatim = source.get("verbatim")

    if not verbatim or not str(verbatim).strip():
        # No verbatim means no source. The object is kept but flagged so the
        # confidence state can route it to review instead of the record.
        obj["source"] = {
            "doc_id": doc_id,
            "page": 1,
            "bbox": [0.0, 0.0, 1000.0, 1000.0],
            "verbatim": "",
        }
        obj["_provenance_missing"] = True
        return obj

    page, bbox, located = derive_source_location(str(verbatim), text_layer)
    obj["source"] = {
        "doc_id": doc_id,
        "page": page,
        "bbox": bbox,
        "verbatim": str(verbatim).strip(),
    }
    obj["_bbox_exact"] = located
    return obj


def _walk_and_attach(
    payload: Dict[str, Any], doc_id: str, text_layer: Optional[TextLayer]
) -> Dict[str, Any]:
    """Attach resolved source citations to every entity in the payload."""
    for collection in ENTITY_COLLECTIONS:
        items = payload.get(collection)
        if isinstance(items, list):
            payload[collection] = [
                _attach_location(item, doc_id, text_layer)
                for item in items
                if isinstance(item, dict)
            ]

    # A medicine strip is a single object rather than a collection.
    if "source" in payload and isinstance(payload.get("source"), dict):
        _attach_location(payload, doc_id, text_layer)
    return payload


def extract_document(
    event: Dict[str, Any],
    repository: Optional[PatientRepositoryInterface] = None,
    bedrock: Optional[BedrockClientInterface] = None,
    s3_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run type-specific structured extraction over the rasterised pages."""
    envelope = envelope_from_event(event)
    patient_id = envelope["patient_id"]
    doc_id = envelope["doc_id"]
    bucket = envelope["bucket"]
    pages: List[str] = envelope.get("pages") or []
    repo = get_pipeline_repository(repository)

    try:
        document_type = DocumentType(envelope.get("document_type", DocumentType.UNKNOWN.value))
    except ValueError:
        document_type = DocumentType.UNKNOWN

    if document_type == DocumentType.UNKNOWN:
        raise PipelineError(
            f"Extract state reached with an unclassified document ({doc_id})"
        )
    if not pages:
        raise PipelineError(f"Extract state reached with no rasterised pages for {doc_id}")

    update_document_status(repo, patient_id, doc_id, DocumentStatus.EXTRACTING)

    client = bedrock or get_bedrock_client()
    prompt = prompt_for_type(document_type)
    images = load_page_images(bucket, pages, limit=EXTRACT_PAGE_LIMIT, s3_client=s3_client)

    payload = client.invoke_json(prompt=prompt, images=images, system=EXTRACTION_SYSTEM)

    text_layer = _resolve_text_layer(
        bucket, envelope.get("key"), envelope.get("extension"), s3_client
    )
    payload = _walk_and_attach(payload, doc_id, text_layer)

    envelope["extraction"] = payload
    envelope["extraction_prompt"] = prompt
    envelope["text_layer_available"] = text_layer is not None
    logger.info("Extracted %s document %s", document_type.value, doc_id)
    return envelope


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda entrypoint for the Extract state."""
    return extract_document(event)
