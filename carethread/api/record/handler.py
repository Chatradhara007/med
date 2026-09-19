"""Lambda handler for CareThread canonical record, field patch, and plan adherence endpoints.

Endpoints handled:
- GET   /record
- PATCH /record/{field}
- PATCH /record/field
- POST  /plan/{day}/{slot}/done
"""

import json
import logging
from typing import Any, Dict, Optional
from pydantic import ValidationError

from carethread.shared.auth import extract_claims, extract_patient_id, UnauthorizedError
from carethread.shared.repository import get_repository
from carethread.shared.repository.exceptions import EntityNotFoundError, DatabaseError
from carethread.shared.schemas.api import RecordFieldPatchRequest
from carethread.api.common.response import make_response, error_response
from .service import RecordService

logger = logging.getLogger(__name__)


def handle_get_record(
    event: Dict[str, Any],
    service: RecordService,
) -> Dict[str, Any]:
    """Handle GET /record."""
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return error_response(401, "UNAUTHORIZED", str(e))

    try:
        record = service.get_patient_record(patient_id, claims=extract_claims(event))
        return make_response(200, record.model_dump())
    except Exception as e:
        logger.error("Failed to retrieve record for patient %s: %s", patient_id, e)
        return error_response(500, "DATABASE_ERROR", f"Failed to retrieve patient record: {str(e)}")


def handle_patch_field(
    event: Dict[str, Any],
    service: RecordService,
) -> Dict[str, Any]:
    """Handle PATCH /record/field and PATCH /record/{field}."""
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return error_response(401, "UNAUTHORIZED", str(e))

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

    # Path parameter support for /record/{field}
    path_params = event.get("pathParameters") or {}
    path_field = path_params.get("field")
    if path_field and path_field.lower() != "field" and "field" not in body_dict:
        body_dict["field"] = path_field

    try:
        req = RecordFieldPatchRequest.model_validate(body_dict)
    except ValidationError as e:
        return error_response(400, "VALIDATION_ERROR", "Invalid field patch request", details=e.errors())

    try:
        res = service.patch_record_field(patient_id=patient_id, request=req)
        return make_response(200, res.model_dump())
    except EntityNotFoundError as e:
        return error_response(404, "NOT_FOUND", str(e))
    except ValueError as e:
        return error_response(400, "INVALID_MUTATION", str(e))
    except Exception as e:
        logger.error("Error patching field for patient %s: %s", patient_id, e)
        return error_response(500, "DATABASE_ERROR", f"Failed to patch record field: {str(e)}")


def handle_plan_done(
    event: Dict[str, Any],
    service: RecordService,
) -> Dict[str, Any]:
    """Handle POST /plan/{day}/{slot}/done."""
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return error_response(401, "UNAUTHORIZED", str(e))

    path_params = event.get("pathParameters") or {}
    day_raw = path_params.get("day")
    slot_raw = path_params.get("slot")

    if day_raw is None or slot_raw is None:
        return error_response(400, "MISSING_PARAMS", "day and slot path parameters are required")

    try:
        day = int(day_raw)
    except ValueError:
        return error_response(400, "INVALID_DAY", f"day must be an integer (0-6), got '{day_raw}'")

    try:
        res = service.mark_plan_done(patient_id=patient_id, day=day, slot_raw=slot_raw)
        return make_response(200, res.model_dump())
    except EntityNotFoundError as e:
        return error_response(404, "PLAN_ENTRY_NOT_FOUND", str(e))
    except ValueError as e:
        return error_response(400, "INVALID_REQUEST", str(e))
    except Exception as e:
        logger.error("Failed to mark plan done for patient %s: %s", patient_id, e)
        return error_response(500, "DATABASE_ERROR", f"Failed to mark plan done: {str(e)}")


def handler(
    event: Dict[str, Any],
    context: Any = None,
    service: Optional[RecordService] = None,
) -> Dict[str, Any]:
    """Main AWS Lambda entrypoint for Record API Function."""
    if service is None:
        repo = get_repository()
        service = RecordService(repository=repo)

    http_method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    )
    http_method = http_method.upper()

    if http_method == "OPTIONS":
        return make_response(200, {"status": "ok"})

    raw_path = (
        event.get("rawPath")
        or event.get("path")
        or event.get("requestContext", {}).get("http", {}).get("path", "")
    )

    if "/plan/" in raw_path and raw_path.endswith("/done") and http_method == "POST":
        return handle_plan_done(event, service)

    if http_method == "GET" and ("/record" in raw_path or not raw_path):
        return handle_get_record(event, service)

    if http_method == "PATCH":
        return handle_patch_field(event, service)

    return error_response(405, "METHOD_NOT_ALLOWED", f"Method {http_method} not allowed on {raw_path}")
