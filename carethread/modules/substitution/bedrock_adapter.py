"""Real medicine-strip extraction backed by Bedrock and the canonical record.

Replaces the fixture adapter in every deployed path. The strip photo has
already been rasterised by M1 into ``pages/<patient_id>/<doc_id>/p1.png``, so
this adapter re-reads that page rather than re-uploading anything.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from carethread.pipeline.bbox import FULL_PAGE_BBOX
from carethread.shared.bedrock import BedrockClientInterface, get_bedrock_client
from carethread.shared.prompts import EXTRACTION_SYSTEM, MEDICINE_STRIP_PROMPT
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.schemas.extraction import MedicineStripExtraction
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    evaluate_confidence,
)
from carethread.modules.substitution.extraction_adapter import (
    MedicineExtractionAdapterInterface,
    MockMedicineExtractionAdapter,
)

logger = logging.getLogger(__name__)


class MedicineExtractionError(RuntimeError):
    """Raised when a strip photo cannot be read into a usable extraction."""


class BedrockMedicineExtractionAdapter(MedicineExtractionAdapterInterface):
    """Reads brand/salt/strength/form off a blister pack photo."""

    def __init__(
        self,
        patient_id: str,
        repository: PatientRepositoryInterface,
        bedrock: Optional[BedrockClientInterface] = None,
        bucket_name: Optional[str] = None,
        s3_client: Optional[Any] = None,
    ) -> None:
        # The adapter is per-request and carries the authenticated patient
        # scope, so a doc_id can never resolve outside its own partition.
        self.patient_id = patient_id
        self.repository = repository
        self._bedrock = bedrock
        self.bucket_name = bucket_name or os.environ.get("DOC_BUCKET")
        self._s3_client = s3_client

    @property
    def bedrock(self) -> BedrockClientInterface:
        if self._bedrock is None:
            self._bedrock = get_bedrock_client()
        return self._bedrock

    def extract_from_document(self, doc_id: str) -> MedicineStripExtraction:
        """Extract the medicine on a strip photo belonging to this patient."""
        from carethread.pipeline.common import load_page_images, page_key

        patient_id = self.patient_id
        if not self.bucket_name:
            raise MedicineExtractionError("DOC_BUCKET is not configured")

        document = self.repository.get_document(patient_id, doc_id)
        if document is None:
            raise MedicineExtractionError(
                f"Document {doc_id} not found for patient {patient_id}"
            )

        pages = document.pages if isinstance(document.pages, list) else []
        if not pages:
            pages = [page_key(patient_id, doc_id, 1)]

        images = load_page_images(
            self.bucket_name, pages, limit=1, s3_client=self._s3_client
        )
        payload = self.bedrock.invoke_json(
            prompt=MEDICINE_STRIP_PROMPT,
            images=images,
            system=EXTRACTION_SYSTEM,
            max_tokens=1024,
        )

        def _text(key: str) -> Optional[str]:
            raw = payload.get(key)
            if raw is None:
                return None
            value = str(raw).strip()
            return value or None

        brand = _text("brand")
        salt = _text("salt")
        strength = _text("strength")
        if not salt:
            # Substitution is salt-equivalence; without a salt there is nothing
            # safe to match on and the scan must go back to the patient.
            raise MedicineExtractionError(
                "Could not read the active ingredient from this pack photo"
            )

        source_raw = payload.get("source") or {}
        verbatim = str(source_raw.get("verbatim") or "").strip()
        if not verbatim:
            raise MedicineExtractionError(
                "Extraction returned no verbatim citation; refusing to persist an unsourced value"
            )

        try:
            confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0

        envelope = ProvenanceEnvelope(
            field="medicine_strip",
            value={"brand": brand, "salt": salt},
            source=ProvenanceSource(
                doc_id=doc_id,
                page=1,
                bbox=list(FULL_PAGE_BBOX),
                verbatim=verbatim,
            ),
            confidence=confidence,
            # A pack photo has no text layer to match against, so the gate is
            # the model's own legibility score.
            status=evaluate_confidence(confidence),
        )

        return MedicineStripExtraction(
            brand=brand or salt,
            salt=salt,
            strength=strength or "not stated",
            form=_text("form") or "tablet",
            manufacturer=_text("manufacturer"),
            provenance=envelope,
        )


def use_mock_extraction() -> bool:
    """Fixtures are opt-in for local runs, never inside a deployed function."""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return False
    return os.environ.get("USE_MOCK_EXTRACTION", "false").lower() in ("true", "1", "yes")


def get_medicine_extraction_adapter(
    patient_id: str,
    repository: PatientRepositoryInterface,
    bedrock: Optional[BedrockClientInterface] = None,
) -> MedicineExtractionAdapterInterface:
    """Return the extraction adapter for the current environment."""
    if use_mock_extraction():
        logger.warning("USE_MOCK_EXTRACTION is set; using fixture strip extractions")
        return MockMedicineExtractionAdapter()
    return BedrockMedicineExtractionAdapter(
        patient_id=patient_id, repository=repository, bedrock=bedrock
    )
