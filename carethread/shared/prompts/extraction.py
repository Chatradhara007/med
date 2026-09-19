"""Prompt text and JSON schemas for document classification and extraction."""

from typing import Any, Dict, List

from carethread.shared.schemas.document import DocumentType

# ---------------------------------------------------------------------------
# Section 10.2 -- extraction prompt rules, reused verbatim by every extractor
# ---------------------------------------------------------------------------

EXTRACTION_RULES = """\
Rules you must follow exactly:
1. Return only JSON matching the supplied schema. No prose, no markdown fences.
2. Every object carries "source": {"verbatim": "..."} -- the exact substring
   from the document that the value came from, copied character for character.
3. If a field is not present in the document, return null. Never infer, never
   complete from medical knowledge. A missing dose is missing.
4. Return "confidence" per object, 0-1, reflecting the legibility of the source
   region. Use a low value when the text is blurred, cropped or handwritten.
5. Preserve the document's own units and reference ranges exactly as printed.
"""

EXTRACTION_SYSTEM = f"""\
You transcribe clinical documents into structured JSON for a patient-facing
record. You are a transcriber, not a clinician.

You must never infer, complete, normalise or correct a value using medical
knowledge. If the page does not show it, the value is null. Inventing a dose
is the single worst failure this system can produce.

You must never diagnose, never prescribe, never suggest treatment, and never
state whether a value is good or bad.

{EXTRACTION_RULES}"""

CLASSIFY_SYSTEM = """\
You classify scanned medical documents by type. You return only JSON.

"unknown" is a first-class, correct answer. If the pages are illegible,
blank, or are not one of the listed types, return "unknown" with a low
confidence. Guessing a type you are not confident about causes the wrong
extractor to run and corrupts a patient's record.
"""

CLASSIFY_PROMPT = """\
Classify this document. Return only this JSON object:

{
  "document_type": "discharge_summary" | "lab_report" | "medicine_strip" | "prescription" | "unknown",
  "confidence": 0.0-1.0,
  "reason": "one short sentence describing what you saw"
}
"""

# ---------------------------------------------------------------------------
# Per-type extraction schemas (Draft-07 subset, used by the validate state)
# ---------------------------------------------------------------------------

_SOURCE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {"verbatim": {"type": ["string", "null"]}},
    "required": ["verbatim"],
}


def _entity(properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    props = dict(properties)
    props["source"] = _SOURCE_SCHEMA
    props["confidence"] = {"type": "number", "minimum": 0.0, "maximum": 1.0}
    return {
        "type": "object",
        "properties": props,
        "required": required + ["source", "confidence"],
    }


DISCHARGE_SUMMARY_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "discharge_date": {"type": ["string", "null"]},
        "diagnoses": {
            "type": "array",
            "items": _entity(
                {
                    "label": {"type": "string"},
                    "icd_hint": {"type": ["string", "null"]},
                },
                ["label"],
            ),
        },
        "medications": {
            "type": "array",
            "items": _entity(
                {
                    "name": {"type": "string"},
                    "salt": {"type": ["string", "null"]},
                    "strength": {"type": ["string", "null"]},
                    "form": {"type": ["string", "null"]},
                    "freq": {"type": ["string", "null"]},
                    "duration_days": {"type": ["integer", "null"]},
                    "instructions": {"type": ["string", "null"]},
                },
                ["name"],
            ),
        },
        "followups": {
            "type": "array",
            "items": _entity(
                {
                    "what": {"type": "string"},
                    "when": {"type": ["string", "null"]},
                },
                ["what"],
            ),
        },
        "restrictions": {
            "type": "array",
            "items": _entity({"text": {"type": "string"}}, ["text"]),
        },
    },
    "required": ["diagnoses", "medications"],
}

LAB_REPORT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "report_date": {"type": ["string", "null"]},
        "lab_results": {
            "type": "array",
            "items": _entity(
                {
                    "analyte": {"type": "string"},
                    "value": {"type": ["number", "string"]},
                    "unit": {"type": ["string", "null"]},
                    "ref_low": {"type": ["number", "null"]},
                    "ref_high": {"type": ["number", "null"]},
                },
                ["analyte", "value"],
            ),
        },
    },
    "required": ["lab_results"],
}

MEDICINE_STRIP_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "brand": {"type": ["string", "null"]},
        "salt": {"type": ["string", "null"]},
        "strength": {"type": ["string", "null"]},
        "form": {"type": ["string", "null"]},
        "manufacturer": {"type": ["string", "null"]},
        "source": _SOURCE_SCHEMA,
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["source", "confidence"],
}

# ---------------------------------------------------------------------------
# Per-type extraction prompts
# ---------------------------------------------------------------------------

DISCHARGE_SUMMARY_PROMPT = """\
Extract this hospital discharge summary. Return only JSON in this shape:

{
  "discharge_date": "" | null,
  "diagnoses":    [{ "label": "", "icd_hint": "" | null, "source": {"verbatim": ""}, "confidence": 0.0 }],
  "medications":  [{ "name": "", "salt": "" | null, "strength": "" | null, "form": "" | null,
                     "freq": "" | null, "duration_days": 0 | null, "instructions": "" | null,
                     "source": {"verbatim": ""}, "confidence": 0.0 }],
  "followups":    [{ "what": "", "when": "" | null, "source": {"verbatim": ""}, "confidence": 0.0 }],
  "restrictions": [{ "text": "", "source": {"verbatim": ""}, "confidence": 0.0 }]
}

Keep dose abbreviations (BD, TDS, OD, HS, SOS) exactly as written. Do not
expand them and do not convert them into a schedule.
"""

LAB_REPORT_PROMPT = """\
Extract this laboratory report. Return only JSON in this shape:

{
  "report_date": "" | null,
  "lab_results": [{ "analyte": "", "value": 0, "unit": "" | null,
                    "ref_low": 0 | null, "ref_high": 0 | null,
                    "source": {"verbatim": ""}, "confidence": 0.0 }]
}

Copy the reference range printed on this report into ref_low and ref_high.
If this report prints no range for an analyte, return null for both. Never
substitute a range you know from elsewhere -- ranges vary by laboratory, age
and sex, and a borrowed range makes the result wrong.
"""

MEDICINE_STRIP_PROMPT = """\
Extract the medicine packaging in this photo. Return only JSON in this shape:

{
  "brand": "" | null,
  "salt": "" | null,
  "strength": "" | null,
  "form": "" | null,
  "manufacturer": "" | null,
  "source": {"verbatim": ""},
  "confidence": 0.0
}

"salt" is the active chemical ingredient printed on the pack (for example
"metformin hydrochloride"), not the brand. If the pack is blurred or partly
obscured, return a low confidence rather than a guess.
"""

PRESCRIPTION_PROMPT = DISCHARGE_SUMMARY_PROMPT

_PROMPTS: Dict[DocumentType, str] = {
    DocumentType.DISCHARGE_SUMMARY: DISCHARGE_SUMMARY_PROMPT,
    DocumentType.PRESCRIPTION: PRESCRIPTION_PROMPT,
    DocumentType.LAB_REPORT: LAB_REPORT_PROMPT,
    DocumentType.MEDICINE_STRIP: MEDICINE_STRIP_PROMPT,
}

_SCHEMAS: Dict[DocumentType, Dict[str, Any]] = {
    DocumentType.DISCHARGE_SUMMARY: DISCHARGE_SUMMARY_SCHEMA,
    DocumentType.PRESCRIPTION: DISCHARGE_SUMMARY_SCHEMA,
    DocumentType.LAB_REPORT: LAB_REPORT_SCHEMA,
    DocumentType.MEDICINE_STRIP: MEDICINE_STRIP_SCHEMA,
}


def prompt_for_type(document_type: DocumentType) -> str:
    """Return the extraction prompt for a classified document type."""
    try:
        return _PROMPTS[document_type]
    except KeyError:
        raise ValueError(
            f"No extraction prompt defined for document type '{document_type}'"
        ) from None


def schema_for_type(document_type: DocumentType) -> Dict[str, Any]:
    """Return the JSON schema the extraction output must validate against."""
    try:
        return _SCHEMAS[document_type]
    except KeyError:
        raise ValueError(
            f"No extraction schema defined for document type '{document_type}'"
        ) from None


def build_repair_prompt(original_prompt: str, errors: List[str]) -> str:
    """Build the second-attempt prompt for the self-correcting validate loop.

    Section 6: on schema failure, re-prompt with the validation error text
    included. This roughly halves extraction failures.
    """
    joined = "\n".join(f"- {err}" for err in errors)
    return (
        f"{original_prompt}\n\n"
        "Your previous response failed schema validation with these errors:\n"
        f"{joined}\n\n"
        "Return corrected JSON that fixes every error above. Do not invent "
        "values to satisfy the schema -- if a field is genuinely absent from "
        "the document, return null for it."
    )
