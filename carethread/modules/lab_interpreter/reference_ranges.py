"""Fallback biological reference range adapter and precedence resolution engine.

PRECEDENCE HIERARCHY:
1. REPORT: Printed reference range on the uploaded laboratory report takes absolute precedence.
2. FALLBACK: Fallback reference range from data/ref_ranges.csv ONLY when the report contains no usable range.
3. NONE: If both report and fallback lack ranges, DO NOT INVENT ONE. Return controlled missing state.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Optional, Tuple

from carethread.modules.lab_interpreter.schemas import ReferenceRangeSource


@dataclass(frozen=True)
class ReferenceRangeEntry:
    """Biological reference range definition from the curated fallback dataset."""
    analyte: str
    unit: str
    ref_low: Optional[float]
    ref_high: Optional[float]
    sample_type: str
    category: str
    clinical_note: str


def normalise_lookup_key(text: str) -> str:
    """Normalize analyte name to alphanumeric lowercase for robust fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


# Common clinical aliases mapping variations to canonical fallback analytes
ANALYTE_ALIASES: Dict[str, str] = {
    "creatinine": "serumcreatinine",
    "s_creatinine": "serumcreatinine",
    "serum_creatinine": "serumcreatinine",
    "potassium": "serumpotassium",
    "k+": "serumpotassium",
    "serum_potassium": "serumpotassium",
    "sodium": "serumsodium",
    "na+": "serumsodium",
    "serum_sodium": "serumsodium",
    "chloride": "serumchloride",
    "serum_chloride": "serumchloride",
    "bun": "bloodureanitrogen",
    "urea": "bloodureanitrogen",
    "blood_urea": "bloodureanitrogen",
    "blood_urea_nitrogen": "bloodureanitrogen",
    "fbs": "fastingbloodsugar",
    "fasting_blood_sugar": "fastingbloodsugar",
    "fasting_glucose": "fastingbloodsugar",
    "fasting_blood_glucose": "fastingbloodsugar",
    "ppbs": "postprandialbloodsugar",
    "postprandial_blood_sugar": "postprandialbloodsugar",
    "postprandial_glucose": "postprandialbloodsugar",
    "hba1c": "hba1c",
    "glycated_hemoglobin": "hba1c",
    "alt": "sgptalt",
    "sgpt": "sgptalt",
    "ast": "sgotast",
    "sgot": "sgotast",
    "platelet": "plateletcount",
    "platelets": "plateletcount",
    "tlc": "totalleukocytecount",
    "wbc": "totalleukocytecount",
    "tsh": "thyroidstimulatinghormonetsh",
    "cholesterol": "totalcholesterol",
    "bilirubin": "totalbilirubin",
    "total_bilirubin": "totalbilirubin",
    "troponin": "troponini",
    "troponin_i": "troponini",
    "crp": "creactiveproteincrp",
    "pt": "prothrombintime",
}


class ReferenceRangeRepository:
    """Repository adapter for biological reference ranges loaded from curated CSV data."""

    def __init__(self, csv_path: Optional[Path] = None) -> None:
        if csv_path is None:
            # Default to carethread/data/ref_ranges.csv
            base_dir = Path(__file__).resolve().parent.parent.parent
            csv_path = base_dir / "data" / "ref_ranges.csv"

        self.csv_path = csv_path
        self._ranges_by_key: Dict[str, ReferenceRangeEntry] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Parse CSV and index entries by normalized keys."""
        if not self.csv_path.exists():
            return

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                analyte = row.get("analyte", "").strip()
                if not analyte:
                    continue

                def _parse_float(val: Optional[str]) -> Optional[float]:
                    if val is None or val.strip() == "":
                        return None
                    try:
                        return float(val.strip())
                    except ValueError:
                        return None

                entry = ReferenceRangeEntry(
                    analyte=analyte,
                    unit=row.get("unit", "").strip(),
                    ref_low=_parse_float(row.get("ref_low")),
                    ref_high=_parse_float(row.get("ref_high")),
                    sample_type=row.get("sample_type", "").strip(),
                    category=row.get("category", "").strip(),
                    clinical_note=row.get("clinical_note", "").strip(),
                )

                norm_key = normalise_lookup_key(analyte)
                self._ranges_by_key[norm_key] = entry

    def lookup(self, analyte: str) -> Optional[ReferenceRangeEntry]:
        """Look up reference range by analyte name or clinical alias."""
        key = normalise_lookup_key(analyte)
        if key in self._ranges_by_key:
            return self._ranges_by_key[key]

        # Try mapped alias
        alias_key = ANALYTE_ALIASES.get(key)
        if alias_key and alias_key in self._ranges_by_key:
            return self._ranges_by_key[alias_key]

        return None


# Global singleton instance for easy reuse
_DEFAULT_FALLBACK_REPO: Optional[ReferenceRangeRepository] = None


def get_default_fallback_repo() -> ReferenceRangeRepository:
    """Retrieve or initialize the global default fallback reference range repository."""
    global _DEFAULT_FALLBACK_REPO
    if _DEFAULT_FALLBACK_REPO is None:
        _DEFAULT_FALLBACK_REPO = ReferenceRangeRepository()
    return _DEFAULT_FALLBACK_REPO


def resolve_reference_range(
    analyte: str,
    report_low: Optional[float],
    report_high: Optional[float],
    fallback_repo: Optional[ReferenceRangeRepository] = None,
) -> Tuple[Optional[float], Optional[float], ReferenceRangeSource]:
    """Resolve reference range enforcing strict precedence.

    PRECEDENCE:
    1. If report contains a usable printed range (at least one bound present),
       REPORT range takes absolute precedence. Fallback is NOT queried or applied.
    2. If report has no usable range (both None), query fallback repository.
       If found, return FALLBACK range.
    3. If neither has a usable range, return (None, None, ReferenceRangeSource.NONE).
       DO NOT INVENT A RANGE.
    """
    # 1. Printed report range takes absolute precedence
    if report_low is not None or report_high is not None:
        return (report_low, report_high, ReferenceRangeSource.REPORT)

    # 2. Fallback reference range ONLY when report contains no usable range
    repo = fallback_repo or get_default_fallback_repo()
    fallback_entry = repo.lookup(analyte)
    if fallback_entry is not None and (fallback_entry.ref_low is not None or fallback_entry.ref_high is not None):
        return (fallback_entry.ref_low, fallback_entry.ref_high, ReferenceRangeSource.FALLBACK)

    # 3. Missing range - DO NOT INVENT ONE
    return (None, None, ReferenceRangeSource.NONE)
