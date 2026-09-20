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


DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"

#: Model ids that mean "nothing usable is configured". The empty string is the
#: unset case; the other two are a placeholder that was once deployed verbatim
#: and the template default, which is only a valid id if the account happens to
#: be entitled to it. A key never belongs in this file, so there is no default
#: Groq credential -- `GROQ_API_KEY` is read from the environment or the
#: fallback simply does not engage.
PLACEHOLDER_MODEL_IDS = frozenset(
    {
        "",
        "THE_ID_THAT_WORKED",
        # The template default. Leaving it untouched means no model was chosen
        # for this account, and an account without entitlement to it fails the
        # call outright -- which is exactly when the Groq fallback should take
        # over. Set BedrockModelId explicitly to force Bedrock.
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
    }
)


class GroqClient(BedrockClientInterface):
    """Multimodal vision client backed by Groq API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model or os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)

    def _call(
        self,
        messages: List[Dict[str, Any]],
        json_mode: bool = True,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        import urllib.error
        import urllib.request

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CareThread/1.0",
            },
            data=json.dumps(payload).encode("utf-8"),
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices") or []
                if not choices:
                    raise BedrockInvocationError("Groq response contained no choices")
                content = choices[0].get("message", {}).get("content", "")
                if not content.strip():
                    raise BedrockInvocationError("Groq response contained empty content")
                return content
        except Exception as exc:
            raise BedrockInvocationError(f"Groq API call failed: {exc}") from exc

    def invoke_json(
        self,
        prompt: str,
        images: Optional[Sequence[bytes]] = None,
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        image_media_type: str = "image/png",
    ) -> Dict[str, Any]:
        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})

        content_parts: List[Dict[str, Any]] = []
        for image_bytes in images or []:
            b64_str = base64.b64encode(image_bytes).decode("ascii")
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_media_type};base64,{b64_str}"},
                }
            )
        content_parts.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": content_parts})

        raw = self._call(messages, json_mode=True, max_tokens=max_tokens)
        return extract_json_object(raw)

    def invoke_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._call(messages, json_mode=False, max_tokens=max_tokens)


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

    # Groq is the fallback for an account without Bedrock model entitlement.
    # It is used only when a key is actually configured and no usable Bedrock
    # model is: falling back silently while Bedrock is available would route
    # clinical extraction to a different vendor than the operator chose.
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    bedrock_model = (model_id or os.environ.get("BEDROCK_MODEL_ID", "")).strip()
    if groq_key and bedrock_model in PLACEHOLDER_MODEL_IDS:
        logger.info("No usable Bedrock model configured; using Groq for vision/extraction")
        return GroqClient(api_key=groq_key)

    return BedrockClient(model_id=model_id, region_name=region_name)

