"""Amazon Bedrock model access layer for CareThread.

All model calls in CareThread go through this package so that the safety
boundary (Section 11 of the build documentation) is enforced in exactly one
place: the model may only read documents and return structured JSON. It never
decides escalation thresholds, never alters doses, and never invents values.
"""

from .client import (
    BedrockClient,
    BedrockClientInterface,
    BedrockInvocationError,
    MockBedrockClient,
    extract_json_object,
    get_bedrock_client,
)

__all__ = [
    "BedrockClient",
    "BedrockClientInterface",
    "BedrockInvocationError",
    "MockBedrockClient",
    "extract_json_object",
    "get_bedrock_client",
]
