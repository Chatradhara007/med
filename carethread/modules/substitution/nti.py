"""Narrow Therapeutic Index (NTI) repository and hard-block safety guardrail.

CRITICAL SAFETY INVARIANT:
Drugs classified under NTI (e.g. Warfarin, Levothyroxine, Digoxin, Phenytoin, Lithium)
carry severe life-threatening bioequivalence variance risks.
Substitution is immediately HARD BLOCKED (blocked = True).
Zero candidates are returned.
Clinical safety rationale is enforced.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Optional


@dataclass(frozen=True)
class NTIEntry:
    """Narrow Therapeutic Index classification definition from data/nti.csv."""
    salt: str
    brand_examples: List[str]
    clinical_rationale: str
    substitution_policy: str


def normalise_nti_key(text: str) -> str:
    """Normalize text for consistent NTI matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


class NTIRepository:
    """Repository adapter querying NTI safety classifications from data/nti.csv."""

    def __init__(self, csv_path: Optional[Path] = None) -> None:
        if csv_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            csv_path = base_dir / "data" / "nti.csv"

        self.csv_path = csv_path
        self._entries: List[NTIEntry] = []
        self._by_salt: Dict[str, NTIEntry] = {}
        self._brand_to_entry: Dict[str, NTIEntry] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Parse NTI CSV and index by salt and brand examples."""
        if not self.csv_path.exists():
            return

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                salt = row.get("salt", "").strip()
                if not salt:
                    continue

                brands_raw = row.get("brand_examples", "")
                brands = [b.strip() for b in brands_raw.split(",") if b.strip()]

                entry = NTIEntry(
                    salt=salt,
                    brand_examples=brands,
                    clinical_rationale=row.get("clinical_rationale", "").strip(),
                    substitution_policy=row.get("substitution_policy", "HARD_BLOCK_DO_NOT_SUBSTITUTE").strip(),
                )
                self._entries.append(entry)

                salt_key = normalise_nti_key(salt)
                self._by_salt[salt_key] = entry

                for b in brands:
                    b_key = normalise_nti_key(b)
                    self._brand_to_entry[b_key] = entry

    def check_nti(self, salt: Optional[str], brand: Optional[str] = None) -> Optional[NTIEntry]:
        """Check whether a drug salt or brand name triggers the NTI Hard-Block."""
        # 1. Check salt
        if salt:
            salt_clean = salt.strip().lower()
            salt_norm = normalise_nti_key(salt)
            if salt_norm in self._by_salt:
                return self._by_salt[salt_norm]

            for s_key, entry in self._by_salt.items():
                if s_key in salt_norm or entry.salt.lower() in salt_clean:
                    return entry

        # 2. Check brand
        if brand:
            brand_norm = normalise_nti_key(brand)
            if brand_norm in self._brand_to_entry:
                return self._brand_to_entry[brand_norm]

            for b_key, entry in self._brand_to_entry.items():
                if b_key in brand_norm:
                    return entry

        return None


_DEFAULT_NTI_REPO: Optional[NTIRepository] = None


def get_default_nti_repo() -> NTIRepository:
    """Retrieve or initialize the global default NTI repository."""
    global _DEFAULT_NTI_REPO
    if _DEFAULT_NTI_REPO is None:
        _DEFAULT_NTI_REPO = NTIRepository()
    return _DEFAULT_NTI_REPO
