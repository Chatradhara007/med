"""Medicine blister pack extraction adapter interface and mock implementation.

Preserves mandatory provenance citation (doc_id, page, bbox, verbatim, confidence)
and enforces confidence gating (>= 0.85 -> confirmed, < 0.85 -> needs_review).
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from carethread.shared.schemas.extraction import MedicineStripExtraction
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)


class MedicineExtractionAdapterInterface(ABC):
    """Abstract interface for extracting pharmaceutical details from medicine images."""

    @abstractmethod
    def extract_from_document(self, doc_id: str) -> MedicineStripExtraction:
        """Extract brand, salt, strength, and form with verified provenance."""
        pass


class MockMedicineExtractionAdapter(MedicineExtractionAdapterInterface):
    """Deterministic extraction adapter for offline development and testing."""

    def __init__(self) -> None:
        self._fixtures: Dict[str, MedicineStripExtraction] = {}
        self._seed_default_fixtures()

    def _seed_default_fixtures(self) -> None:
        # Fixture 1: Glycomet 500 (Metformin stockout scenario)
        src_glyco = ProvenanceSource(
            doc_id="doc_strip_glycomet_003",
            page=1,
            bbox=[340.0, 210.0, 620.0, 810.0],
            verbatim="Glycomet 500 / Metformin Hydrochloride Tablets I.P. 500 mg / USV Pvt Ltd",
        )
        env_glyco = ProvenanceEnvelope(
            field="medicine_strip",
            value={"brand": "Glycomet 500", "salt": "metformin hydrochloride"},
            source=src_glyco,
            confidence=0.94,
            status=ProvenanceStatus.CONFIRMED,
        )
        self._fixtures["doc_strip_glycomet_003"] = MedicineStripExtraction(
            brand="Glycomet 500",
            salt="metformin hydrochloride",
            strength="500mg",
            form="tablet",
            manufacturer="USV Private Limited",
            provenance=env_glyco,
        )

        # Fixture 2: Warf 5 (Warfarin NTI refusal scenario)
        src_warf = ProvenanceSource(
            doc_id="doc_strip_warfarin_004",
            page=1,
            bbox=[290.0, 180.0, 580.0, 830.0],
            verbatim="Warf-5 / Warfarin Sodium Tablets I.P. 5mg / Cipla",
        )
        env_warf = ProvenanceEnvelope(
            field="medicine_strip",
            value={"brand": "Warf 5", "salt": "warfarin"},
            source=src_warf,
            confidence=0.96,
            status=ProvenanceStatus.CONFIRMED,
        )
        self._fixtures["doc_strip_warfarin_004"] = MedicineStripExtraction(
            brand="Warf 5",
            salt="warfarin",
            strength="5mg",
            form="tablet",
            manufacturer="Cipla Ltd",
            provenance=env_warf,
        )

    def register_fixture(self, doc_id: str, extraction: MedicineStripExtraction) -> None:
        """Register a dynamic test fixture."""
        self._fixtures[doc_id] = extraction

    def extract_from_document(self, doc_id: str) -> MedicineStripExtraction:
        """Retrieve extraction fixture by doc_id."""
        if doc_id in self._fixtures:
            return self._fixtures[doc_id]

        raise KeyError(f"No extraction fixture found for doc_id: '{doc_id}'")
