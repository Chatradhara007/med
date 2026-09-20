"""M3 — Lab Interpreter Module.

Processes canonical outpatient laboratory results with strict reference-range precedence,
deterministic deviation scoring, reproducible abnormal-first ranking, clinical context
cross-reading against active diagnoses and medications, and unbroken provenance tracking.
"""

from .schemas import (
    FindingStatus,
    InterpretedLabFinding,
    LabInterpretationReport,
    ReferenceRangeSource,
)
from .reference_ranges import (
    ReferenceRangeEntry,
    ReferenceRangeRepository,
    get_default_fallback_repo,
    resolve_reference_range,
)
from .ranking import (
    calculate_deviation,
    rank_findings,
)
from .context import (
    ClinicalContextResult,
    evaluate_lab_context,
)
from .llm_adapter import (
    ClinicalSafetyViolation,
    LabExplanationFormatterInterface,
    MockLabExplanationFormatter,
    verify_lab_explanation_safety,
)
from .service import LabInterpreterService

__all__ = [
    "ClinicalContextResult",
    "ClinicalSafetyViolation",
    "FindingStatus",
    "InterpretedLabFinding",
    "LabExplanationFormatterInterface",
    "LabInterpretationReport",
    "LabInterpreterService",
    "MockLabExplanationFormatter",
    "ReferenceRangeEntry",
    "ReferenceRangeRepository",
    "ReferenceRangeSource",
    "calculate_deviation",
    "evaluate_lab_context",
    "get_default_fallback_repo",
    "rank_findings",
    "resolve_reference_range",
    "verify_lab_explanation_safety",
]
