"""Handlers for triggering domain workflows (Care Plan generation, Lab report interpretation)."""

import logging
from typing import Any, Dict, Optional

from carethread.shared.auth import extract_patient_id, UnauthorizedError
from carethread.shared.repository import get_repository
from carethread.shared.repository.exceptions import PatientNotFoundError
from carethread.modules.care_plan.service import CarePlanService
from carethread.modules.lab_interpreter.service import LabInterpreterService
from carethread.api.common.response import make_response, error_response

logger = logging.getLogger(__name__)


def handle_generate_plan(
    event: Dict[str, Any],
    service: Optional[CarePlanService] = None,
) -> Dict[str, Any]:
    """Handle POST /plan/generate."""
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return error_response(401, "UNAUTHORIZED", str(e))

    if service is None:
        repo = get_repository()
        service = CarePlanService(repository=repo)

    try:
        result = service.generate_care_plan(patient_id=patient_id)
        return make_response(200, result.model_dump())
    except PatientNotFoundError as e:
        return error_response(404, "PATIENT_NOT_FOUND", str(e))
    except Exception as e:
        logger.exception("Failed to generate care plan for patient %s", patient_id)
        return error_response(
            500, "PLAN_GENERATION_FAILED", "Failed to generate care plan"
        )


def handle_interpret_labs(
    event: Dict[str, Any],
    service: Optional[LabInterpreterService] = None,
) -> Dict[str, Any]:
    """Handle POST /labs/interpret."""
    try:
        patient_id = extract_patient_id(event)
    except UnauthorizedError as e:
        return error_response(401, "UNAUTHORIZED", str(e))

    if service is None:
        repo = get_repository()
        service = LabInterpreterService(repository=repo)
    else:
        repo = service.repository or get_repository()

    try:
        context = repo.get_patient_context(patient_id)
        report = service.interpret_labs(
            patient_id=patient_id,
            lab_results=context.lab_results,
            diagnoses=context.diagnoses,
            medications=context.medications,
        )
        return make_response(200, report.model_dump())
    except Exception as e:
        logger.exception("Failed to interpret labs for patient %s", patient_id)
        return error_response(
            500, "LAB_INTERPRETATION_FAILED", "Failed to interpret labs"
        )


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda entrypoint for the workflow endpoints."""
    path = (
        event.get("rawPath")
        or event.get("path")
        or event.get("requestContext", {}).get("http", {}).get("path", "")
    )
    method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "POST")
    ).upper()

    if method == "OPTIONS":
        return make_response(200, {"status": "ok"})
    if path.endswith("/plan/generate") and method == "POST":
        return handle_generate_plan(event)
    if path.endswith("/labs/interpret") and method == "POST":
        return handle_interpret_labs(event)
    return error_response(404, "NOT_FOUND", f"Cannot {method} {path}")
