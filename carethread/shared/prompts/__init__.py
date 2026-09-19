"""Extraction prompts, reused verbatim across every extractor.

Section 10.2 of the build documentation fixes these rules. The third rule --
never infer a value that is not on the page -- is the one that keeps the
product safe, so it is stated first in the system prompt and repeated in the
per-type instructions.
"""

from .extraction import (
    CLASSIFY_PROMPT,
    CLASSIFY_SYSTEM,
    DISCHARGE_SUMMARY_PROMPT,
    DISCHARGE_SUMMARY_SCHEMA,
    EXTRACTION_RULES,
    EXTRACTION_SYSTEM,
    LAB_REPORT_PROMPT,
    LAB_REPORT_SCHEMA,
    MEDICINE_STRIP_PROMPT,
    MEDICINE_STRIP_SCHEMA,
    PRESCRIPTION_PROMPT,
    build_repair_prompt,
    prompt_for_type,
    schema_for_type,
)

__all__ = [
    "CLASSIFY_PROMPT",
    "CLASSIFY_SYSTEM",
    "DISCHARGE_SUMMARY_PROMPT",
    "DISCHARGE_SUMMARY_SCHEMA",
    "EXTRACTION_RULES",
    "EXTRACTION_SYSTEM",
    "LAB_REPORT_PROMPT",
    "LAB_REPORT_SCHEMA",
    "MEDICINE_STRIP_PROMPT",
    "MEDICINE_STRIP_SCHEMA",
    "PRESCRIPTION_PROMPT",
    "build_repair_prompt",
    "prompt_for_type",
    "schema_for_type",
]
