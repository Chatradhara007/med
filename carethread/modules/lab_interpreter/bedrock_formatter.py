"""Bedrock-backed patient-readable lab explanations.

The deviation, the status direction and the reference range are all computed
deterministically before this module runs. The model only turns the finding
into a readable sentence, and every sentence is checked by
``verify_lab_explanation_safety`` -- which rejects a dropped analyte name, an
altered value, an inverted direction, or any diagnostic or prescriptive claim.
A rejected sentence falls back to the deterministic wording.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from carethread.shared.bedrock import BedrockClientInterface, get_bedrock_client
from carethread.modules.lab_interpreter.llm_adapter import (
    ClinicalSafetyViolation,
    LabExplanationFormatterInterface,
    MockLabExplanationFormatter,
    verify_lab_explanation_safety,
)
from carethread.modules.lab_interpreter.schemas import InterpretedLabFinding

logger = logging.getLogger(__name__)

LAB_SYSTEM = """\
You explain one laboratory result to a patient in two short sentences of plain
language, at a sixth-grade reading level.

Hard limits:
- Repeat the analyte name and the measured value exactly as given. Never round,
  rescale or restate a number, a unit or a reference bound.
- Never change the direction of the finding. If it is above range, say above.
- Never diagnose, never name a disease as the cause, never suggest or change a
  treatment or a dose, and never tell the patient what to do next beyond
  speaking to their doctor.
- Do not reassure and do not alarm. Describe only what the number is.
- Return plain text only. No JSON, no markdown, no preamble.
"""


class BedrockLabExplanationFormatter(LabExplanationFormatterInterface):
    """Patient-readable lab wording with a verified deterministic fallback."""

    def __init__(
        self,
        bedrock: Optional[BedrockClientInterface] = None,
        fallback: Optional[LabExplanationFormatterInterface] = None,
    ) -> None:
        self._bedrock = bedrock
        self.fallback = fallback or MockLabExplanationFormatter()

    @property
    def bedrock(self) -> BedrockClientInterface:
        if self._bedrock is None:
            self._bedrock = get_bedrock_client()
        return self._bedrock

    def format_explanation(self, finding: InterpretedLabFinding) -> str:
        deterministic = self.fallback.format_explanation(finding)

        prompt = (
            "Explain this laboratory finding to the patient.\n\n"
            f"Analyte: {finding.analyte}\n"
            f"Value: {finding.value} {finding.unit}\n"
            f"Reference range: {finding.ref_low} to {finding.ref_high} "
            f"(source: {finding.ref_source.value if hasattr(finding.ref_source, 'value') else finding.ref_source})\n"
            f"Status: {finding.status.value if hasattr(finding.status, 'value') else finding.status}\n"
            f"Context notes (repeat only if relevant, do not expand): "
            f"{'; '.join(finding.context_notes) if finding.context_notes else 'none'}\n\n"
            f"Baseline wording to improve: {deterministic}"
        )

        try:
            candidate = self.bedrock.invoke_text(
                prompt=prompt, system=LAB_SYSTEM, max_tokens=300
            )
            verify_lab_explanation_safety(finding, candidate)
            return candidate
        except ClinicalSafetyViolation as exc:
            logger.warning(
                "Model explanation for %s failed the safety check (%s); using deterministic wording",
                finding.analyte,
                exc,
            )
        except Exception as exc:
            logger.warning(
                "Model formatting unavailable for %s (%s); using deterministic wording",
                finding.analyte,
                exc,
            )
        return deterministic


def use_deterministic_formatter() -> bool:
    """Deterministic-only wording is opt-in; deployed functions use the model."""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return os.environ.get("USE_DETERMINISTIC_FORMATTER", "false").lower() in (
            "true",
            "1",
            "yes",
        )
    return os.environ.get("USE_DETERMINISTIC_FORMATTER", "true").lower() in (
        "true",
        "1",
        "yes",
    )


def get_lab_explanation_formatter(
    bedrock: Optional[BedrockClientInterface] = None,
) -> LabExplanationFormatterInterface:
    """Return the lab explanation formatter for the current environment."""
    if use_deterministic_formatter():
        return MockLabExplanationFormatter()
    return BedrockLabExplanationFormatter(bedrock=bedrock)
