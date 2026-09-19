"""Service layer adapter connecting POST /substitution endpoint to M4 substitution domain logic."""

import logging
from typing import Optional

from carethread.shared.schemas.api import SubstitutionRequest, SubstitutionResponse
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.modules.substitution.service import SubstitutionService
from carethread.modules.substitution.bedrock_adapter import (
    get_medicine_extraction_adapter,
)

logger = logging.getLogger(__name__)


class SubstitutionApiService:
    """Coordinates substitution requests with domain substitution engine."""

    def __init__(
        self,
        repository: Optional[PatientRepositoryInterface] = None,
        substitution_service: Optional[SubstitutionService] = None,
    ) -> None:
        self.repo = repository
        self.service = substitution_service or SubstitutionService(repository=repository)

    def evaluate_substitution(
        self,
        patient_id: Optional[str],
        request: SubstitutionRequest,
    ) -> SubstitutionResponse:
        """Run substitution screening and format canonical API response.

        Never alters, cancels, or prescribes medications autonomously.
        """
        logger.info(
            "Evaluating substitution for patient=%s doc_id=%s brand=%s strength=%s",
            patient_id, request.doc_id, request.brand, request.strength
        )

        # A strip scan is read by the real extractor, scoped to the
        # authenticated patient so a doc_id cannot reach another partition.
        if request.doc_id and patient_id and self.repo is not None:
            self.service.extraction_adapter = get_medicine_extraction_adapter(
                patient_id=patient_id, repository=self.repo
            )

        analysis = self.service.check_substitution(
            patient_id=patient_id,
            doc_id=request.doc_id,
            brand=request.brand,
            strength=request.strength,
        )
        return self.service.to_api_response(analysis)
