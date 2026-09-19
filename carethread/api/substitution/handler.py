"""Lambda handler for POST /substitution endpoint."""

import json
import logging
from typing import Any, Dict, Optional
from pydantic import ValidationError

from carethread.shared.auth import extract_patient_id, UnauthorizedError
from carethread.shared.repository import get_repository
from carethread.shared.schemas.api import SubstitutionRequest
from carethread.api.common.response import make_response, error_response
from .service import SubstitutionApiService

logger = logging.getLogger(__name__)


def handle_post_substitution(
    event: Dict[str, Any],
    service: SubstitutionApiService,
) -> Dict[str, Any]:
    """Handle POST /substitution."""
    # 1. Resolve patient identity if available (for active medication cross-check)
    patient_id: Optional[str] = None
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError:
        # Substitution check can also evaluate formulary without active prescriptions if unauthenticated
        patient_id = None

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

    # 3. Validate request schema
    try:
        req = SubstitutionRequest.model_validate(body_dict)
    except ValidationError as e:
        return error_response(400, "VALIDATION_ERROR", "Invalid substitution request payload", details=e.errors())

    # 4. Invoke service
    try:
        res = service.evaluate_substitution(patient_id=patient_id, request=req)
        return make_response(200, res.model_dump())
    except Exception as e:
        logger.error("Failed to process substitution request: %s", e)
        return error_response(500, "INTERNAL_ERROR", f"Failed to process substitution: {str(e)}")


def handler(
    event: Dict[str, Any],
    context: Any = None,
    service: Optional[SubstitutionApiService] = None,
) -> Dict[str, Any]:
    """Main AWS Lambda entrypoint for Substitution API Function."""
    if service is None:
        repo = get_repository()
        service = SubstitutionApiService(repository=repo)

    http_method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "POST")
    )
    http_method = http_method.upper()

    if http_method == "OPTIONS":
        return make_response(200, {"status": "ok"})

    if http_method == "POST":
        return handle_post_substitution(event, service)

    return error_response(405, "METHOD_NOT_ALLOWED", f"Method {http_method} not allowed")
