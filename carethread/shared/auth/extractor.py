"""Cognito JWT and testing authentication claim extractor.

SECURITY INVARIANT:
The authenticated user's patient identity comes strictly from the JWT sub claim.
Request body patient_id is NEVER trusted or used to override authenticated context.
"""

import logging
import os
from typing import Any, Dict, Optional
from .interfaces import UnauthorizedError

logger = logging.getLogger(__name__)


def extract_patient_id(
    event: Dict[str, Any],
    allow_mock: Optional[bool] = None
) -> str:
    """Extract authenticated patient_id from API Gateway event context.

    Sources checked in order:
    1. HTTP API JWT Authorizer: event.requestContext.authorizer.jwt.claims.sub
    2. REST API Cognito Authorizer: event.requestContext.authorizer.claims.sub
    3. If allow_mock=True or ALLOW_MOCK_AUTH=true: headers['x-patient-id']
    """
    if allow_mock is None:
        allow_mock = os.environ.get("ALLOW_MOCK_AUTH", "false").lower() in ("true", "1", "yes")
        # A header-supplied identity is an authentication bypass. It is only
        # ever acceptable outside AWS; inside a deployed function the JWT
        # authorizer is the single source of identity, whatever the env says.
        if allow_mock and os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            logger.error(
                "ALLOW_MOCK_AUTH is set inside a deployed Lambda and is being ignored"
            )
            allow_mock = False

    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})

    # 1. HTTP API JWT Authorizer (default for SAM template HTTP API)
    jwt_claims = authorizer.get("jwt", {}).get("claims", {})
    patient_id = jwt_claims.get("sub")
    if patient_id and str(patient_id).strip():
        return str(patient_id).strip()

    # 2. REST API / Lambda Authorizer claims
    direct_claims = authorizer.get("claims", {})
    patient_id = direct_claims.get("sub")
    if patient_id and str(patient_id).strip():
        return str(patient_id).strip()

    # Direct sub on authorizer (scalar only; a nested map is not an identity)
    direct_sub = authorizer.get("sub")
    if isinstance(direct_sub, (str, int)) and str(direct_sub).strip():
        return str(direct_sub).strip()

    # 3. Local/testing mock adapter
    if allow_mock:
        headers = event.get("headers", {}) or {}
        # Case-insensitive header lookup
        for k, v in headers.items():
            if k.lower() == "x-patient-id" and v and str(v).strip():
                return str(v).strip()

    raise UnauthorizedError("Unauthorized: Missing or invalid authenticated patient identity in JWT claims")
