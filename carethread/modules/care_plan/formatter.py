"""LLM adapter interface and deterministic formatter for patient-readable care plan wording.

SAFETY INVARIANTS:
1. LLMs may only format, normalize, and translate documented clinical text into plain language.
2. LLMs must NEVER alter drug names, strengths, frequencies, or duration.
3. LLMs must NEVER invent clinical advice or escalation thresholds.
"""

from abc import ABC, abstractmethod
import re
from typing import Optional

from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.plan_entry import SlotName


class ClinicalSafetyViolation(ValueError):
    """Raised when an LLM formatting attempt contradicts or corrupts canonical clinical data."""
    pass


def verify_medication_action_safety(medication: Medication, formatted_action: str) -> None:
    """Verify that formatted patient wording strictly preserves clinical truth."""
    action_lower = formatted_action.lower()

    # 1. Drug name or salt must be present
    name_clean = medication.name.lower().split()[0]
    salt_clean = medication.salt.lower().split()[0] if medication.salt else ""
    if name_clean not in action_lower and not (salt_clean and salt_clean in action_lower):
        raise ClinicalSafetyViolation(
            f"Safety Violation: Formatted action '{formatted_action}' dropped canonical drug name '{medication.name}'"
        )

    # 2. Strength numeric value must be present
    strength_nums = re.findall(r"\d+", medication.strength)
    for num in strength_nums:
        if num not in action_lower:
            raise ClinicalSafetyViolation(
                f"Safety Violation: Formatted action '{formatted_action}' altered canonical strength '{medication.strength}'"
            )


class LLMFormatterInterface(ABC):
    """Abstract interface for patient-friendly phrasing."""

    @abstractmethod
    def format_medication_action(self, medication: Medication, slot: SlotName) -> str:
        """Translate a prescription entry into patient-readable dosing instructions."""
        pass

    @abstractmethod
    def format_instruction(self, text: str) -> str:
        """Normalize clinical abbreviations into clear instructions."""
        pass


class MockLLMFormatter(LLMFormatterInterface):
    """Deterministic, rule-based formatter for local development and offline test suites."""

    def format_medication_action(self, medication: Medication, slot: SlotName) -> str:
        form = medication.form or "dose"
        timing = "with meal" if slot in (SlotName.MORNING, SlotName.AFTERNOON, SlotName.EVENING) else "at bedtime"
        instructions = f" ({medication.instructions})" if medication.instructions else ""
        
        formatted = f"Take {medication.name} {medication.strength} {form} {timing}{instructions}"
        
        # Verify safety immediately
        verify_medication_action_safety(medication, formatted)
        return formatted

    def format_instruction(self, text: str) -> str:
        # Standard clinical abbreviation expansions without adding advice
        expanded = text.replace("TDS", "three times daily").replace("BD", "twice daily").replace("OD", "once daily")
        return expanded.strip()
