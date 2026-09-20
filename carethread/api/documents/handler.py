"""AWS Lambda request handler for CareThread document management endpoints.

Endpoints handled:
- POST /documents        (Initiate upload and receive presigned S3 PUT URL)
- GET /documents/{id}    (Query document ingestion status)

SECURITY INVARIANT:
All requests are authenticated. patient_id is derived strictly from JWT sub claims.
Client request bodies can never specify or override patient_id.
"""

import json
import logging
import re
from typing import Any, Dict, Optional
from pydantic import ValidationError

from carethread.shared.schemas.api import DocumentCreateRequest
from carethread.shared.auth import extract_patient_id, UnauthorizedError
from carethread.shared.repository import get_repository, DocumentNotFoundError
from carethread.shared.storage import get_storage_service
from carethread.api.common.response import make_response, error_response
from .service import DocumentsService

logger = logging.getLogger(__name__)

SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}


def handle_post_documents(
    event: Dict[str, Any],
    service: DocumentsService,
) -> Dict[str, Any]:
    """Handler for POST /documents."""
    # 1. Authenticate user from JWT claims
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return error_response(401, "UNAUTHORIZED", str(e))

    # 2. Parse request body
    body_raw = event.get("body")
    if not body_raw:
        return error_response(400, "MISSING_BODY", "Missing request body")

    if isinstance(body_raw, str):
        try:
            body_dict = json.loads(body_raw)
        except json.JSONDecodeError:
            return error_response(400, "INVALID_JSON", "Invalid JSON body")
    elif isinstance(body_raw, dict):
        body_dict = body_raw
    else:
        return error_response(400, "INVALID_BODY", "Invalid body format")

    # 3. Validate metadata using shared schema
    try:
        req = DocumentCreateRequest(
            filename=body_dict.get("filename", ""),
            content_type=body_dict.get("content_type", ""),
        )
    except ValidationError as e:
        return error_response(
            400,
            "VALIDATION_ERROR",
            "Invalid document metadata",
            details=e.errors(),
        )

    # 4. Check supported content types
    if req.content_type.lower() not in SUPPORTED_CONTENT_TYPES:
        return error_response(
            400,
            "UNSUPPORTED_MEDIA_TYPE",
            f"Content-Type '{req.content_type}' is not supported. Allowed: {sorted(SUPPORTED_CONTENT_TYPES)}",
        )

    # 5. Invoke domain service
    try:
        res = service.create_document(patient_id=patient_id, request=req)
        return make_response(201, res.model_dump())
    except Exception as e:
        logger.error("Failed to register document: %s", e)
        return error_response(500, "STORAGE_FAILURE", f"Failed to register document: {str(e)}")


def handle_get_document(
    event: Dict[str, Any],
    service: DocumentsService,
) -> Dict[str, Any]:
    """Handler for GET /documents/{id}."""
    # 1. Authenticate user
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return error_response(401, "UNAUTHORIZED", str(e))

    # 2. Extract doc_id from path parameters
    path_params = event.get("pathParameters") or {}
    doc_id = path_params.get("id") or path_params.get("doc_id")
    if not doc_id:
        return error_response(400, "MISSING_PARAM", "Missing document ID in path parameters")

    # 3. Query status
    try:
        res = service.get_document_status(patient_id=patient_id, doc_id=doc_id)
        return make_response(200, res.model_dump())
    except DocumentNotFoundError:
        return error_response(404, "DOCUMENT_NOT_FOUND", f"Document {doc_id} not found")
    except Exception as e:
        logger.error("Failed to retrieve document status: %s", e)
        return error_response(500, "INTERNAL_ERROR", f"Failed to retrieve document status: {str(e)}")


def handle_delete_document(
    event: Dict[str, Any],
    service: DocumentsService,
) -> Dict[str, Any]:
    """Handler for DELETE /documents/{id}."""
    # 1. Authenticate user
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return error_response(401, "UNAUTHORIZED", str(e))

    # 2. Extract doc_id from path parameters
    path_params = event.get("pathParameters") or {}
    doc_id = path_params.get("id") or path_params.get("doc_id")
    if not doc_id:
        return error_response(400, "MISSING_PARAM", "Missing document ID in path parameters")

    # 3. Delete document
    try:
        service.delete_document(patient_id=patient_id, doc_id=doc_id)
        return make_response(200, {"status": "deleted", "doc_id": doc_id})
    except DocumentNotFoundError:
        return error_response(404, "DOCUMENT_NOT_FOUND", f"Document {doc_id} not found")
    except Exception as e:
        logger.error("Failed to delete document %s: %s", doc_id, e)
        return error_response(500, "INTERNAL_ERROR", f"Failed to delete document: {str(e)}")


def handler(
    event: Dict[str, Any],
    context: Any = None,
    service: Optional[DocumentsService] = None,
) -> Dict[str, Any]:
    """Main AWS Lambda entrypoint for documents API."""
    if service is None:
        repo = get_repository()
        storage = get_storage_service()
        service = DocumentsService(repository=repo, storage=storage)

    http_method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "POST")
    )
    http_method = http_method.upper()

    path = (
        event.get("rawPath")
        or event.get("path")
        or event.get("requestContext", {}).get("http", {}).get("path", "")
    )

    if http_method == "OPTIONS":
        return make_response(200, {"status": "ok"})

    if http_method == "POST":
        # Match the delete *segment*, not the substring: `"delete" in path`
        # also fired for any doc_id that happened to contain the word.
        if re.match(r"^/documents/[^/]+/delete$", path):
            return handle_delete_document(event, service)
        return handle_post_documents(event, service)
    elif http_method == "GET":
        return handle_get_document(event, service)
    elif http_method == "DELETE":
        return handle_delete_document(event, service)

    return error_response(405, "METHOD_NOT_ALLOWED", f"Method {http_method} not allowed")
