"""Bedrock-backed care plan wording.

The model translates and clarifies. It does not decide anything: the dose, the
frequency and every escalation threshold come from the canonical record and
``rules.yaml`` before this module is reached. Every generated string is run
through ``verify_medication_action_safety`` and any violation falls back to the
deterministic phrasing, so a model that drifts can never reach the patient.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from carethread.shared.bedrock import BedrockClientInterface, get_bedrock_client
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.plan_entry import SlotName
from carethread.modules.care_plan.formatter import (
    ClinicalSafetyViolation,
    LLMFormatterInterface,
    MockLLMFormatter,
    verify_medication_action_safety,
)

logger = logging.getLogger(__name__)

CARE_PLAN_SYSTEM = """\
You rewrite a single prescribed dose into one plain sentence a patient can act
on, in simple language at a sixth-grade reading level.

Hard limits:
- Copy the drug name and the strength exactly as given. Never change a number.
- Never add, remove or reinterpret a dose, a frequency or a duration.
- Never add clinical advice, warnings, reassurance or any statement about what
  the medicine treats.
- Return one sentence of plain text. No JSON, no markdown, no preamble.
"""

INSTRUCTION_SYSTEM = """\
You expand clinical abbreviations in a prescription instruction into plain
language. Change nothing else: no added advice, no reordering of meaning, no
new information. Return the rewritten instruction as plain text only.
"""


class BedrockLLMFormatter(LLMFormatterInterface):
    """Patient-readable dosing wording with a deterministic fallback."""

    def __init__(
        self,
        bedrock: Optional[BedrockClientInterface] = None,
        fallback: Optional[LLMFormatterInterface] = None,
    ) -> None:
        self._bedrock = bedrock
        self.fallback = fallback or MockLLMFormatter()

    @property
    def bedrock(self) -> BedrockClientInterface:
        if self._bedrock is None:
            self._bedrock = get_bedrock_client()
        return self._bedrock

    def format_medication_action(self, medication: Medication, slot: SlotName) -> str:
        deterministic = self.fallback.format_medication_action(medication, slot)
        prompt = (
            "Rewrite this dose instruction as one plain sentence for the "
            f"{slot.value} slot.\n\n"
            f"Drug name: {medication.name}\n"
            f"Strength: {medication.strength}\n"
            f"Form: {medication.form}\n"
            f"Frequency: {medication.freq}\n"
            f"Instructions: {medication.instructions or 'none given'}\n\n"
            f"Baseline wording to improve: {deterministic}"
        )

        try:
            candidate = self.bedrock.invoke_text(
                prompt=prompt, system=CARE_PLAN_SYSTEM, max_tokens=256
            )
            verify_medication_action_safety(medication, candidate)
            return candidate
        except ClinicalSafetyViolation as exc:
            logger.warning(
                "Model wording for %s failed the safety check (%s); using deterministic phrasing",
                medication.name,
                exc,
            )
        except Exception as exc:
            logger.warning(
                "Model formatting unavailable for %s (%s); using deterministic phrasing",
                medication.name,
                exc,
            )
        return deterministic

    def format_instruction(self, text: str) -> str:
        deterministic = self.fallback.format_instruction(text)
        if not text or not text.strip():
            return deterministic
        try:
            return self.bedrock.invoke_text(
                prompt=f"Rewrite this instruction in plain language: {text}",
                system=INSTRUCTION_SYSTEM,
                max_tokens=256,
            )
        except Exception as exc:
            logger.warning("Model instruction rewrite unavailable (%s)", exc)
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


def get_care_plan_formatter(
    bedrock: Optional[BedrockClientInterface] = None,
) -> LLMFormatterInterface:
    """Return the care plan formatter for the current environment."""
    if use_deterministic_formatter():
        return MockLLMFormatter()
    return BedrockLLMFormatter(bedrock=bedrock)
