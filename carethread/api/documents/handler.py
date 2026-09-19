"""AWS Lambda request handler for CareThread document management endpoints.

Endpoints handled:
- POST /documents        (Initiate upload and receive presigned S3 PUT URL)
- GET /documents/{id}    (Query document ingestion status)

SECURITY INVARIANT:
All requests are authenticated. patient_id is derived strictly from JWT sub claims.
Client request bodies can never specify or override patient_id.
"""

import json
from typing import Any, Dict, Optional
from pydantic import ValidationError

from carethread.shared.schemas.api import DocumentCreateRequest
from carethread.shared.auth import extract_patient_id, UnauthorizedError
from carethread.shared.repository import get_repository, DocumentNotFoundError
from carethread.shared.storage import get_storage_service
from .service import DocumentsService

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Patient-Id",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def _response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def handle_post_documents(
    event: Dict[str, Any],
    service: DocumentsService
) -> Dict[str, Any]:
    """Handler for POST /documents."""
    # 1. Authenticate user from JWT claims
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return _response(401, {"error": str(e)})

    # 2. Parse request body
    body_raw = event.get("body")
    if not body_raw:
        return _response(400, {"error": "Missing request body"})

    if isinstance(body_raw, str):
        try:
            body_dict = json.loads(body_raw)
        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid JSON body"})
    elif isinstance(body_raw, dict):
        body_dict = body_raw
    else:
        return _response(400, {"error": "Invalid body format"})

    # 3. Validate metadata using shared schema
    # Crucial security rule: Client-supplied patient_id is ignored
    try:
        req = DocumentCreateRequest(
            filename=body_dict.get("filename", ""),
            content_type=body_dict.get("content_type", "")
        )
    except ValidationError as e:
        return _response(400, {"error": "Invalid document metadata", "details": e.errors()})

    # 4. Invoke domain service
    try:
        res = service.create_document(patient_id=patient_id, request=req)
        return _response(201, res.model_dump())
    except Exception as e:
        return _response(500, {"error": f"Failed to register document: {str(e)}"})


def handle_get_document(
    event: Dict[str, Any],
    service: DocumentsService
) -> Dict[str, Any]:
    """Handler for GET /documents/{id}."""
    # 1. Authenticate user
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return _response(401, {"error": str(e)})

    # 2. Extract doc_id from path parameters
    path_params = event.get("pathParameters") or {}
    doc_id = path_params.get("id") or path_params.get("doc_id")
    if not doc_id:
        return _response(400, {"error": "Missing document ID in path parameters"})

    # 3. Query status
    try:
        res = service.get_document_status(patient_id=patient_id, doc_id=doc_id)
        return _response(200, res.model_dump())
    except DocumentNotFoundError:
        return _response(404, {"error": f"Document {doc_id} not found"})
    except Exception as e:
        return _response(500, {"error": f"Failed to retrieve document status: {str(e)}"})


def handler(
    event: Dict[str, Any],
    context: Any = None,
    service: Optional[DocumentsService] = None
) -> Dict[str, Any]:
    """Main AWS Lambda entrypoint for documents API."""
    if service is None:
        repo = get_repository()
        storage = get_storage_service()
        service = DocumentsService(repository=repo, storage=storage)

    http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "POST")
    http_method = http_method.upper()

    if http_method == "OPTIONS":
        return _response(200, {"status": "ok"})

    if http_method == "POST":
        return handle_post_documents(event, service)
    elif http_method == "GET":
        return handle_get_document(event, service)

    return _response(405, {"error": f"Method {http_method} not allowed"})
