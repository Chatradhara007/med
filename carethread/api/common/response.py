"""HTTP response and error serialization helpers for CareThread REST APIs.

Guarantees consistent status codes, CORS headers, and structured error payloads.
"""

import json
import os
from typing import Any, Dict, List, Optional, Union


def allowed_origin() -> str:
    """The browser origin permitted to call this API.

    Defaults to the deployed web origin via ``CORS_ALLOW_ORIGIN``. A wildcard
    is only returned when nothing is configured, which is a local-development
    convenience and should be set before the API is exposed.
    """
    return os.environ.get("CORS_ALLOW_ORIGIN", "*")


def cors_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": allowed_origin(),
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Patient-Id,x-patient-id",
        "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
        "Vary": "Origin",
    }


# Retained for callers that import the constant; prefer cors_headers().
CORS_HEADERS = cors_headers()


def make_response(
    status_code: int,
    body: Any,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Format standard API Gateway HTTP response with CORS headers."""
    merged_headers = cors_headers()
    if headers:
        merged_headers.update(headers)

    if isinstance(body, str):
        payload = body
    else:
        payload = json.dumps(body, default=str)

    return {
        "statusCode": status_code,
        "headers": merged_headers,
        "body": payload,
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Union[List[Any], Dict[str, Any]]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Format standard structured JSON error response.

    Error shape:
    {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "...",
            "details": [...]
        }
    }
    """
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else [],
        }
    }
    return make_response(status_code=status_code, body=body, headers=headers)
