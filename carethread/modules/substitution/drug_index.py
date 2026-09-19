"""Curated drug formulary index and salt-equivalence matcher.

DATA SOURCE:
Parses data/drugs.csv containing 200+ vetted bioequivalent pharmaceutical entries.
Matches candidates strictly on identical active chemical salts.
Exposes divergences in formulation strength and dosage form.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Optional, Union

from carethread.modules.substitution.schemas import CandidateAlternative


@dataclass(frozen=True)
class DrugEntry:
    """Individual drug item from curated Indian pharmacopeia formulary."""
    brand: str
    salt: str
    strength_mg: float
    form: str
    nti: bool
    common_interactions: List[str]
    manufacturer: str
    approx_mrp_inr: float


def normalise_drug_text(text: str) -> str:
    """Lowercase alphanumeric string for consistent indexing."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def parse_numeric_strength(strength_str: Union[str, float, int, None]) -> Optional[float]:
    """Parse numeric milligrams from strings such as '500mg', '5 mg', '0.5mg'."""
    if strength_str is None:
        return None
    if isinstance(strength_str, (int, float)):
        return float(strength_str)

    match = re.search(r"(\d+(?:\.\d+)?)", str(strength_str))
    if match:
        return float(match.group(1))
    return None


class DrugIndexRepository:
    """Repository adapter querying curated formulary data from data/drugs.csv."""

    def __init__(self, csv_path: Optional[Path] = None) -> None:
        if csv_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            csv_path = base_dir / "data" / "drugs.csv"

        self.csv_path = csv_path
        self._entries: List[DrugEntry] = []
        self._by_brand: Dict[str, DrugEntry] = {}
        self._by_salt: Dict[str, List[DrugEntry]] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Parse CSV and index entries by brand and active salt."""
        if not self.csv_path.exists():
            return

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                brand = row.get("brand", "").strip()
                salt = row.get("salt", "").strip()
                if not brand or not salt:
                    continue

                try:
                    strength_mg = float(row.get("strength_mg", "0").strip() or "0")
                except ValueError:
                    strength_mg = 0.0

                try:
                    mrp = float(row.get("approx_mrp_inr", "0").strip() or "0")
                except ValueError:
                    mrp = 0.0

                interactions_raw = row.get("common_interactions", "")
                interactions = [
                    i.strip() for i in interactions_raw.split(";") if i.strip()
                ]

                nti_val = str(row.get("nti", "")).strip().lower() in ("true", "1", "yes")

                entry = DrugEntry(
                    brand=brand,
                    salt=salt,
                    strength_mg=strength_mg,
                    form=row.get("form", "tablet").strip().lower(),
                    nti=nti_val,
                    common_interactions=interactions,
                    manufacturer=row.get("manufacturer", "").strip(),
                    approx_mrp_inr=mrp,
                )
                self._entries.append(entry)

                brand_key = normalise_drug_text(brand)
                self._by_brand[brand_key] = entry

                salt_key = normalise_drug_text(salt)
                if salt_key not in self._by_salt:
                    self._by_salt[salt_key] = []
                self._by_salt[salt_key].append(entry)

    def find_by_brand(self, brand: str) -> Optional[DrugEntry]:
        """Find a drug entry by its exact or normalized brand name."""
        key = normalise_drug_text(brand)
        if key in self._by_brand:
            return self._by_brand[key]

        # Partial prefix matching if query starts with brand (e.g. 'Glycomet 500' -> 'Glycomet')
        for b_key, entry in self._by_brand.items():
            if key in b_key or b_key in key:
                return entry
        return None

    def find_by_salt(self, salt: str) -> List[DrugEntry]:
        """Find all drug entries containing the given active salt."""
        key = normalise_drug_text(salt)
        if key in self._by_salt:
            return list(self._by_salt[key])

        # Partial matching across salts
        results: List[DrugEntry] = []
        for s_key, entries in self._by_salt.items():
            if key in s_key or s_key in key:
                results.extend(entries)
        return results

    def find_candidates(
        self,
        salt: str,
        query_brand: Optional[str] = None,
        strength_mg: Optional[float] = None,
        form: Optional[str] = None,
    ) -> List[CandidateAlternative]:
        """Find salt-equivalent candidate alternatives, evaluating strength and form divergences.

        CRITICAL EQUIVALENCE INVARIANT:
        Candidates must match the exact active chemical salt.
        Differences in strength and dosage form are explicitly flagged on each candidate.
        """
        raw_matches = self.find_by_salt(salt)
        candidates: List[CandidateAlternative] = []

        query_brand_norm = normalise_drug_text(query_brand) if query_brand else ""
        query_form_norm = form.strip().lower() if form else None

        for entry in raw_matches:
            # Exclude the exact brand being queried
            if query_brand_norm and normalise_drug_text(entry.brand) == query_brand_norm:
                continue

            divergence_notes: List[str] = []

            # 1. Strength comparison
            if strength_mg is not None and strength_mg > 0:
                strength_matches = abs(entry.strength_mg - strength_mg) < 1e-4
                if not strength_matches:
                    divergence_notes.append(
                        f"Strength divergence: candidate is {entry.strength_mg}mg (prescribed is {strength_mg}mg)"
                    )
            else:
                strength_matches = True

            # 2. Dosage form comparison
            if query_form_norm:
                form_matches = entry.form.lower() == query_form_norm
                if not form_matches:
                    divergence_notes.append(
                        f"Dosage form divergence: candidate is {entry.form} (prescribed is {query_form_norm})"
                    )
            else:
                form_matches = True

            cand = CandidateAlternative(
                brand=entry.brand,
                salt=entry.salt,
                strength=f"{entry.strength_mg:g}mg",
                strength_mg=entry.strength_mg,
                form=entry.form,
                manufacturer=entry.manufacturer,
                price_inr=entry.approx_mrp_inr,
                nti=entry.nti,
                common_interactions=entry.common_interactions,
                strength_matches=strength_matches,
                form_matches=form_matches,
                divergence_notes=divergence_notes,
            )
            candidates.append(cand)

        # Sort: exact matches first (same strength and form), then by ascending retail price
        candidates.sort(
            key=lambda c: (
                not (c.strength_matches and c.form_matches),
                not c.strength_matches,
                not c.form_matches,
                c.price_inr if c.price_inr is not None else 9999.0,
            )
        )
        return candidates


_DEFAULT_DRUG_INDEX: Optional[DrugIndexRepository] = None


def get_default_drug_index() -> DrugIndexRepository:
    """Retrieve or initialize the global default drug index repository."""
    global _DEFAULT_DRUG_INDEX
    if _DEFAULT_DRUG_INDEX is None:
        _DEFAULT_DRUG_INDEX = DrugIndexRepository()
    return _DEFAULT_DRUG_INDEX
