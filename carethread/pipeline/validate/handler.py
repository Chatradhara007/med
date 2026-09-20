"""ValidateSchema state: JSON-schema validation with one self-correcting retry.

Section 6: on schema failure, re-prompt once with the validation error text
appended to the prompt. This roughly halves extraction failures and is the
cheapest reliability win in the pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from carethread.pipeline.bbox import TextLayer, extract_pdf_text_layer
from carethread.pipeline.common import (
    PipelineError,
    envelope_from_event,
    fetch_object,
    get_pipeline_repository,
    load_page_images,
    update_document_status,
)
from carethread.pipeline.extract.handler import EXTRACT_PAGE_LIMIT, _walk_and_attach
from carethread.shared.bedrock import BedrockClientInterface, get_bedrock_client
from carethread.shared.prompts import (
    EXTRACTION_SYSTEM,
    build_repair_prompt,
    prompt_for_type,
    schema_for_type,
)
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.schemas.document import DocumentStatus, DocumentType

logger = logging.getLogger(__name__)

MAX_REPORTED_ERRORS = 10


def validate_payload(payload: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate an extraction payload, returning human-readable error strings."""
    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema unavailable; skipping structural validation")
        return []

    validator = jsonschema.Draft7Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        location = ".".join(str(p) for p in error.path) or "<root>"
        errors.append(f"{location}: {error.message}")
        if len(errors) >= MAX_REPORTED_ERRORS:
            break
    return errors


def _text_layer(
    bucket: str, key: Optional[str], extension: Optional[str], s3_client: Optional[Any]
) -> Optional[TextLayer]:
    if not key or (extension or "").lower() != "pdf":
        return None
    try:
        return extract_pdf_text_layer(fetch_object(bucket, key, s3_client=s3_client))
    except PipelineError:
        return None


def validate_extraction(
    event: Dict[str, Any],
    repository: Optional[PatientRepositoryInterface] = None,
    bedrock: Optional[BedrockClientInterface] = None,
    s3_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Validate the extraction, re-prompting once with the errors on failure."""
    envelope = envelope_from_event(event)
    patient_id = envelope["patient_id"]
    doc_id = envelope["doc_id"]
    bucket = envelope["bucket"]
    repo = get_pipeline_repository(repository)

    payload = envelope.get("extraction")
    if not isinstance(payload, dict):
        raise PipelineError(f"Validate state reached with no extraction payload for {doc_id}")

    try:
        document_type = DocumentType(envelope.get("document_type", DocumentType.UNKNOWN.value))
    except ValueError:
        document_type = DocumentType.UNKNOWN
    if document_type == DocumentType.UNKNOWN:
        raise PipelineError(f"Validate state reached with an unclassified document ({doc_id})")

    update_document_status(repo, patient_id, doc_id, DocumentStatus.VALIDATING)

    schema = schema_for_type(document_type)
    errors = validate_payload(payload, schema)

    if not errors:
        envelope["validation_status"] = "valid"
        envelope["validation_errors"] = []
        return envelope

    logger.info("Extraction for %s failed validation: %s", doc_id, errors)

    # ---- the self-correcting loop: exactly one repair attempt -------------
    client = bedrock or get_bedrock_client()
    pages = envelope.get("pages") or []
    images = load_page_images(bucket, pages, limit=EXTRACT_PAGE_LIMIT, s3_client=s3_client)
    base_prompt = envelope.get("extraction_prompt") or prompt_for_type(document_type)
    repair_prompt = build_repair_prompt(base_prompt, errors)

    try:
        repaired = client.invoke_json(
            prompt=repair_prompt, images=images, system=EXTRACTION_SYSTEM
        )
    except Exception as exc:
        logger.warning("Repair attempt for %s failed: %s", doc_id, exc)
        envelope["validation_status"] = "invalid"
        envelope["validation_errors"] = errors
        return envelope

    text_layer = _text_layer(bucket, envelope.get("key"), envelope.get("extension"), s3_client)
    repaired = _walk_and_attach(repaired, doc_id, text_layer)
    repair_errors = validate_payload(repaired, schema)

    if repair_errors:
        # Keep the repaired payload only if it is strictly better; otherwise
        # the original stands and the document goes to review.
        logger.info("Repair for %s still invalid: %s", doc_id, repair_errors)
        envelope["validation_status"] = "invalid"
        envelope["validation_errors"] = repair_errors
        if len(repair_errors) < len(errors):
            envelope["extraction"] = repaired
        return envelope

    envelope["extraction"] = repaired
    envelope["validation_status"] = "repaired"
    envelope["validation_errors"] = []
    logger.info("Repaired extraction for %s on the second attempt", doc_id)
    return envelope


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda entrypoint for the ValidateSchema state."""
    return validate_extraction(event)
