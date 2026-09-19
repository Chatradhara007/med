"""LLM adapter interface and deterministic formatter for patient-readable lab explanations.

SAFETY INVARIANTS:
1. LLMs may only format, translate, and explain validated findings in plain language.
2. LLMs must NEVER alter reported values, measurement units, or reference intervals.
3. LLMs must NEVER determine abnormality or invert finding direction (e.g. calling high "normal").
4. LLMs must NEVER diagnose disease or prescribe/alter medications.
5. All generated explanations must pass strict clinical safety verification.
"""

from abc import ABC, abstractmethod
import re
from typing import Optional

from carethread.modules.lab_interpreter.schemas import (
    FindingStatus,
    InterpretedLabFinding,
    ReferenceRangeSource,
)


class ClinicalSafetyViolation(ValueError):
    """Raised when an LLM formatting attempt contradicts or corrupts structured clinical findings."""
    pass


def verify_lab_explanation_safety(finding: InterpretedLabFinding, explanation: str) -> None:
    """Verify that formatted patient wording strictly preserves structured clinical truth."""
    exp_lower = explanation.lower()

    # 1. Analyte name must be present
    analyte_clean = finding.analyte.lower().split()[0]
    if analyte_clean not in exp_lower:
        raise ClinicalSafetyViolation(
            f"Safety Violation: Formatted explanation dropped canonical analyte name '{finding.analyte}'"
        )

    # 2. Value must be accurately represented
    # Support numeric or string representation
    if isinstance(finding.value, (int, float)):
        # Check integer or float format (e.g. 2.4, 2.40, 8, 8.0)
        str_val = str(finding.value)
        val_clean = str_val.rstrip('0').rstrip('.') if '.' in str_val else str_val
        if val_clean not in exp_lower and str(finding.value) not in exp_lower:
            raise ClinicalSafetyViolation(
                f"Safety Violation: Formatted explanation altered reported value '{finding.value}'"
            )
    elif str(finding.value).lower() not in exp_lower:
        raise ClinicalSafetyViolation(
            f"Safety Violation: Formatted explanation dropped qualitative value '{finding.value}'"
        )

    # 3. Status direction must match
    if finding.status == FindingStatus.ABOVE:
        if "below range" in exp_lower or "within normal" in exp_lower or "within the normal" in exp_lower:
            raise ClinicalSafetyViolation(
                "Safety Violation: Inverted finding direction; above-range analyte described as below or within range"
            )
    elif finding.status == FindingStatus.BELOW:
        if "above range" in exp_lower or "within normal" in exp_lower or "within the normal" in exp_lower:
            raise ClinicalSafetyViolation(
                "Safety Violation: Inverted finding direction; below-range analyte described as above or within range"
            )
    elif finding.status == FindingStatus.WITHIN:
        if "above range" in exp_lower or "below range" in exp_lower:
            raise ClinicalSafetyViolation(
                "Safety Violation: Inverted finding direction; normal analyte described as above or below range"
            )

    # 4. Strictly forbid autonomous diagnostic or prescriptive claims
    forbidden_diagnostic_phrases = [
        "this proves you have",
        "confirms diagnosis of",
        "you are diagnosed with",
        "i prescribe",
        "we prescribe",
        "prescribe new",
        "should prescribe",
        "discontinue your",
        "stop taking your",
        "increase your dose",
        "decrease your dose",
        "change your dose",
    ]
    for phrase in forbidden_diagnostic_phrases:
        if phrase in exp_lower:
            raise ClinicalSafetyViolation(
                f"Safety Violation: Formatted text contains unauthorized diagnostic/prescriptive claim: '{phrase}'"
            )


class LabExplanationFormatterInterface(ABC):
    """Abstract interface for formatting patient-friendly lab explanations."""

    @abstractmethod
    def format_explanation(self, finding: InterpretedLabFinding) -> str:
        """Translate a structured lab finding into an accessible, safety-verified patient explanation."""
        pass


class MockLabExplanationFormatter(LabExplanationFormatterInterface):
    """Deterministic, rule-based formatter for local test suites and development."""

    def format_explanation(self, finding: InterpretedLabFinding) -> str:
        analyte = finding.analyte
        val = finding.value
        unit = finding.unit

        # Range source label
        if finding.ref_source == ReferenceRangeSource.REPORT:
            src_lbl = "laboratory's printed report range"
        elif finding.ref_source == ReferenceRangeSource.FALLBACK:
            src_lbl = "standard biological fallback range"
        else:
            src_lbl = "reference range"

        # Construct explanation based on status
        if finding.status == FindingStatus.ABOVE:
            if finding.ref_low is not None and finding.ref_high is not None:
                core = (
                    f"Your {analyte} level is {val} {unit}, which is above the {src_lbl} "
                    f"of {finding.ref_low} to {finding.ref_high} {unit}."
                )
            else:
                core = f"Your {analyte} level is {val} {unit}, which is above the {src_lbl} limit of {finding.ref_high} {unit}."
        elif finding.status == FindingStatus.BELOW:
            if finding.ref_low is not None and finding.ref_high is not None:
                core = (
                    f"Your {analyte} level is {val} {unit}, which is below the {src_lbl} "
                    f"of {finding.ref_low} to {finding.ref_high} {unit}."
                )
            else:
                core = f"Your {analyte} level is {val} {unit}, which is below the {src_lbl} limit of {finding.ref_low} {unit}."
        elif finding.status == FindingStatus.WITHIN:
            core = (
                f"Your {analyte} level is {val} {unit}, which is within the {src_lbl} "
                f"of {finding.ref_low} to {finding.ref_high} {unit}."
            )
        else:
            core = (
                f"Your {analyte} level is {val} {unit}. The laboratory report did not specify "
                "a reference range, and no standard fallback range was available for this test."
            )

        # Append contextual notes if present
        if finding.context_notes:
            notes_str = " " + " ".join(finding.context_notes)
            full_explanation = core + notes_str
        else:
            full_explanation = core

        # Verify safety immediately
        verify_lab_explanation_safety(finding, full_explanation)
        return full_explanation
