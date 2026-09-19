"""Bedrock runtime client wrapper returning strict JSON payloads.

The pipeline is only ever allowed to consume *structured* model output. This
module is therefore responsible for three things:

1. Invoking a multimodal Claude model on Bedrock with page images attached.
2. Recovering the JSON object from the response, rejecting prose.
3. Surfacing a typed error so the Step Functions retry policy can act on it.
"""

from abc import ABC, abstractmethod
import base64
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_ANTHROPIC_VERSION = "bedrock-2023-05-31"

# Model output must be a JSON object. Prose responses are a contract violation.
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class BedrockInvocationError(RuntimeError):
    """Raised when a model call fails or returns unusable output."""


class BedrockClientInterface(ABC):
    """Abstract model access contract used by every CareThread extractor."""

    @abstractmethod
    def invoke_json(
        self,
        prompt: str,
        images: Optional[Sequence[bytes]] = None,
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        image_media_type: str = "image/png",
    ) -> Dict[str, Any]:
        """Invoke the model and return the parsed JSON object it produced."""

    @abstractmethod
    def invoke_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        """Invoke the model for a plain-language string (formatting only)."""


def extract_json_object(raw_text: str) -> Dict[str, Any]:
    """Recover a JSON object from a model response.

    Tolerates markdown fences because models occasionally add them, but refuses
    anything that is not ultimately a JSON object: silently accepting prose is
    how unsourced values reach the record.
    """
    if not raw_text or not raw_text.strip():
        raise BedrockInvocationError("Model returned an empty response")

    candidate = _FENCE.sub("", raw_text.strip())
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(candidate)
        if not match:
            raise BedrockInvocationError(
                f"Model response contained no JSON object: {raw_text[:200]!r}"
            )
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise BedrockInvocationError(
                f"Model response was not valid JSON: {exc}"
            ) from exc

    if not isinstance(parsed, dict):
        raise BedrockInvocationError(
            f"Model response must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


class BedrockClient(BedrockClientInterface):
    """Production Amazon Bedrock runtime adapter."""

    def __init__(
        self,
        model_id: Optional[str] = None,
        region_name: Optional[str] = None,
        runtime_client: Optional[Any] = None,
    ) -> None:
        self.model_id = model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self._client = runtime_client

    @property
    def client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("bedrock-runtime", region_name=self.region_name)
        return self._client

    def _invoke(
        self,
        prompt: str,
        images: Optional[Sequence[bytes]],
        system: Optional[str],
        max_tokens: int,
        image_media_type: str,
    ) -> str:
        content: List[Dict[str, Any]] = []
        for image_bytes in images or []:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    },
                }
            )
        content.append({"type": "text", "text": prompt})

        body: Dict[str, Any] = {
            "anthropic_version": DEFAULT_ANTHROPIC_VERSION,
            "max_tokens": max_tokens,
            # Deterministic reads: extraction is transcription, not creativity.
            "temperature": 0.0,
            "messages": [{"role": "user", "content": content}],
        }
        if system:
            body["system"] = system

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
        except Exception as exc:  # boto3 raises many client-specific errors
            raise BedrockInvocationError(
                f"Bedrock invoke_model failed for model {self.model_id}: {exc}"
            ) from exc

        raw_body = response.get("body")
        payload_text = raw_body.read() if hasattr(raw_body, "read") else raw_body
        if isinstance(payload_text, (bytes, bytearray)):
            payload_text = payload_text.decode("utf-8")

        try:
            payload = json.loads(payload_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise BedrockInvocationError(
                f"Bedrock returned a non-JSON envelope: {exc}"
            ) from exc

        blocks = payload.get("content") or []
        text = "".join(
            block.get("text", "") for block in blocks if block.get("type") == "text"
        )
        if not text.strip():
            raise BedrockInvocationError("Bedrock response contained no text content")
        return text

    def invoke_json(
        self,
        prompt: str,
        images: Optional[Sequence[bytes]] = None,
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        image_media_type: str = "image/png",
    ) -> Dict[str, Any]:
        text = self._invoke(prompt, images, system, max_tokens, image_media_type)
        return extract_json_object(text)

    def invoke_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        return self._invoke(prompt, None, system, max_tokens, "image/png").strip()


class MockBedrockClient(BedrockClientInterface):
    """Scripted client for offline tests.

    Only ever selected explicitly (tests, or ``USE_MOCK_BEDROCK=true``); it is
    never the default in a deployed function.
    """

    def __init__(
        self,
        json_responses: Optional[List[Dict[str, Any]]] = None,
        text_responses: Optional[List[str]] = None,
    ) -> None:
        self.json_responses: List[Dict[str, Any]] = list(json_responses or [])
        self.text_responses: List[str] = list(text_responses or [])
        self.calls: List[Dict[str, Any]] = []

    def queue_json(self, payload: Dict[str, Any]) -> None:
        self.json_responses.append(payload)

    def queue_text(self, text: str) -> None:
        self.text_responses.append(text)

    def invoke_json(
        self,
        prompt: str,
        images: Optional[Sequence[bytes]] = None,
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        image_media_type: str = "image/png",
    ) -> Dict[str, Any]:
        self.calls.append(
            {"prompt": prompt, "images": len(images or []), "system": system}
        )
        if not self.json_responses:
            raise BedrockInvocationError("MockBedrockClient has no queued JSON response")
        return self.json_responses.pop(0)

    def invoke_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        self.calls.append({"prompt": prompt, "images": 0, "system": system})
        if not self.text_responses:
            raise BedrockInvocationError("MockBedrockClient has no queued text response")
        return self.text_responses.pop(0)


def use_mock_bedrock() -> bool:
    """Mocks are opt-in only, and never inside a deployed Lambda."""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return False
    return os.environ.get("USE_MOCK_BEDROCK", "false").lower() in ("true", "1", "yes")


def get_bedrock_client(
    model_id: Optional[str] = None,
    region_name: Optional[str] = None,
) -> BedrockClientInterface:
    """Return the model client for the current environment."""
    if use_mock_bedrock():
        logger.warning("USE_MOCK_BEDROCK is set; returning scripted Bedrock client")
        return MockBedrockClient()
    return BedrockClient(model_id=model_id, region_name=region_name)
