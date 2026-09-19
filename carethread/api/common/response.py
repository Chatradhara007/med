"""HTTP response and error serialization helpers for CareThread REST APIs.

Guarantees consistent status codes, CORS headers, and structured error payloads.
"""

import json
from typing import Any, Dict, List, Optional, Union

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Patient-Id,x-patient-id",
    "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
}


def make_response(
    status_code: int,
    body: Any,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Format standard API Gateway HTTP response with CORS headers."""
    merged_headers = dict(CORS_HEADERS)
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
