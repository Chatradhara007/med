"""Deterministic deviation analysis and reproducible finding ranking.

MATHEMATICAL SPECIFICATION:
1. Normalised Interval Span: span = ref_high - ref_low
2. Above Range:
   If value > ref_high:
     status = ABOVE
     deviation_score = round((value - ref_high) / span, 2)
3. Below Range:
   If value < ref_low:
     status = BELOW
     deviation_score = round((ref_low - value) / span, 2)
4. Within Range (including boundary equality value == ref_low or value == ref_high):
   status = WITHIN
   deviation_score = 0.0
5. Missing Reference Bounds:
   status = UNKNOWN
   deviation_score = None

RANKING ORDER:
- Abnormal findings (ABOVE or BELOW) sorted descending by deviation_score.
- Tie-breaker: analyte name alphabetically (guarantees 100% reproducible ordering).
- Within-range findings follow abnormal findings, sorted alphabetically.
- Unranked/unknown findings follow at the end.
- Sequential 1-based ranks (1, 2, 3...) assigned.
"""

from typing import List, Optional, Tuple, Union

from carethread.modules.lab_interpreter.schemas import FindingStatus, InterpretedLabFinding


def calculate_deviation(
    value: Union[float, str],
    ref_low: Optional[float],
    ref_high: Optional[float],
) -> Tuple[FindingStatus, Optional[float]]:
    """Deterministically determine abnormality and normalized deviation magnitude.

    Boundary handling:
    - value == ref_low -> WITHIN, deviation_score = 0.0
    - value == ref_high -> WITHIN, deviation_score = 0.0
    - value < ref_low -> BELOW, deviation_score > 0.0
    - value > ref_high -> ABOVE, deviation_score > 0.0
    """
    # Attempt numeric parse
    try:
        numeric_val = float(value)
    except (ValueError, TypeError):
        # Qualitative or non-numeric result
        return (FindingStatus.UNKNOWN, None)

    # Missing both bounds
    if ref_low is None and ref_high is None:
        return (FindingStatus.UNKNOWN, None)

    # Standard two-sided interval
    if ref_low is not None and ref_high is not None:
        span = ref_high - ref_low
        if span <= 0:
            span = max(abs(ref_high), 1.0)

        if numeric_val < ref_low:
            score = round((ref_low - numeric_val) / span, 2)
            return (FindingStatus.BELOW, score)
        elif numeric_val > ref_high:
            score = round((numeric_val - ref_high) / span, 2)
            return (FindingStatus.ABOVE, score)
        else:
            return (FindingStatus.WITHIN, 0.0)

    # One-sided upper bound only (e.g. Troponin < 0.04)
    if ref_high is not None and ref_low is None:
        divisor = ref_high if ref_high > 0 else 1.0
        if numeric_val > ref_high:
            score = round((numeric_val - ref_high) / divisor, 2)
            return (FindingStatus.ABOVE, score)
        else:
            return (FindingStatus.WITHIN, 0.0)

    # One-sided lower bound only
    if ref_low is not None and ref_high is None:
        divisor = ref_low if ref_low > 0 else 1.0
        if numeric_val < ref_low:
            score = round((ref_low - numeric_val) / divisor, 2)
            return (FindingStatus.BELOW, score)
        else:
            return (FindingStatus.WITHIN, 0.0)

    return (FindingStatus.UNKNOWN, None)


def rank_findings(findings: List[InterpretedLabFinding]) -> List[InterpretedLabFinding]:
    """Sort and rank findings deterministically.

    Order:
    1. Abnormal findings (ABOVE or BELOW) sorted descending by deviation_score,
       with alphabetical analyte tie-breaking.
    2. Within-range findings sorted alphabetically by analyte.
    3. Unknown/missing findings sorted alphabetically by analyte.

    Assigns sequential 1-based ranks.
    """
    abnormal: List[InterpretedLabFinding] = []
    within: List[InterpretedLabFinding] = []
    unknown: List[InterpretedLabFinding] = []

    for f in findings:
        if f.status in (FindingStatus.ABOVE, FindingStatus.BELOW):
            abnormal.append(f)
        elif f.status == FindingStatus.WITHIN:
            within.append(f)
        else:
            unknown.append(f)

    # Sort abnormal by descending deviation_score, tie-break by analyte
    abnormal.sort(
        key=lambda x: (-(x.deviation_score if x.deviation_score is not None else -1.0), x.analyte.lower())
    )

    # Sort within and unknown alphabetically
    within.sort(key=lambda x: x.analyte.lower())
    unknown.sort(key=lambda x: x.analyte.lower())

    ordered = abnormal + within + unknown

    # Assign ranks
    ranked_results: List[InterpretedLabFinding] = []
    for idx, item in enumerate(ordered, start=1):
        # Create a new copy or update rank
        updated = item.model_copy(update={"rank": idx})
        ranked_results.append(updated)

    return ranked_results
