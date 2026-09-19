"""Core service orchestrating medicine substitution evaluation.

SAFETY INVARIANTS:
1. Strict NTI Hard-Block: Zero alternatives returned for NTI drugs; hard refusal rationale enforced.
2. Active Prescriptions from Canonical Record: Loaded exclusively via get_patient_context(patient_id).
3. Zero Autonomous Prescription: Only surfaces vetted options; never modifies patient records.
4. Divergence Transparency: Differences in formulation strength and dosage form are explicitly flagged.
5. Provenance & Uncertainty: Enforces source citations; low-confidence extractions retain needs_review state.
"""

from typing import List, Optional, Union

from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.repository.exceptions import MissingProvenanceError
from carethread.shared.schemas.api import DrugAlternative, SubstitutionResponse
from carethread.shared.schemas.provenance import ProvenanceEnvelope, ProvenanceStatus
from carethread.modules.substitution.schemas import (
    CandidateAlternative,
    DetectedMedicine,
    InteractionAdvisory,
    SubstitutionAnalysisResult,
    SubstitutionResultState,
)
from carethread.modules.substitution.drug_index import (
    DrugIndexRepository,
    get_default_drug_index,
    parse_numeric_strength,
)
from carethread.modules.substitution.nti import (
    NTIRepository,
    get_default_nti_repo,
)
from carethread.modules.substitution.interactions import (
    InteractionChecker,
)
from carethread.modules.substitution.extraction_adapter import (
    MedicineExtractionAdapterInterface,
    MockMedicineExtractionAdapter,
)


class SubstitutionService:
    """Core domain service for evaluating pharmacy drug substitutions."""

    def __init__(
        self,
        repository: Optional[PatientRepositoryInterface] = None,
        drug_index: Optional[DrugIndexRepository] = None,
        nti_repo: Optional[NTIRepository] = None,
        interaction_checker: Optional[InteractionChecker] = None,
        extraction_adapter: Optional[MedicineExtractionAdapterInterface] = None,
    ) -> None:
        self.repository = repository
        self.drug_index = drug_index or get_default_drug_index()
        self.nti_repo = nti_repo or get_default_nti_repo()
        self.interaction_checker = interaction_checker or InteractionChecker()
        self.extraction_adapter = extraction_adapter or MockMedicineExtractionAdapter()

    def check_substitution(
        self,
        patient_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        brand: Optional[str] = None,
        salt: Optional[str] = None,
        strength: Optional[str] = None,
        form: Optional[str] = None,
    ) -> SubstitutionAnalysisResult:
        """Evaluate substitution feasibility, NTI restrictions, and interaction risks."""
        detected: Optional[DetectedMedicine] = None
        review_status = "confirmed"
        provenance_env: Optional[ProvenanceEnvelope] = None

        # 1. Resolve medicine details (via blister pack OCR doc_id or direct input)
        if doc_id:
            extraction = self.extraction_adapter.extract_from_document(doc_id)
            if extraction.provenance is None or extraction.provenance.source is None:
                raise MissingProvenanceError(
                    f"Provenance Invariant Violation: Extraction for doc_id '{doc_id}' lacks source citation."
                )

            provenance_env = extraction.provenance
            conf = extraction.provenance.confidence
            if extraction.provenance.status == ProvenanceStatus.NEEDS_REVIEW or (conf is not None and conf < 0.85):
                review_status = "needs_review"

            detected_brand = extraction.brand
            detected_salt = extraction.salt
            detected_strength = extraction.strength
            detected_form = extraction.form
            detected_mfg = extraction.manufacturer
            num_strength = parse_numeric_strength(detected_strength)

            detected = DetectedMedicine(
                brand=detected_brand,
                salt=detected_salt,
                strength=detected_strength,
                strength_mg=num_strength,
                form=detected_form,
                manufacturer=detected_mfg,
                provenance=provenance_env,
                confidence=conf,
            )
        elif brand or salt:
            detected_brand = brand or ""
            detected_salt = salt or ""
            detected_strength = strength or ""
            detected_form = form or "tablet"
            detected_mfg = None

            # If salt not provided, attempt catalog resolution
            if not detected_salt and detected_brand:
                catalog_entry = self.drug_index.find_by_brand(detected_brand)
                if catalog_entry:
                    detected_salt = catalog_entry.salt
                    if not detected_strength:
                        detected_strength = f"{catalog_entry.strength_mg:g}mg"
                    if not form:
                        detected_form = catalog_entry.form
                    detected_mfg = catalog_entry.manufacturer

            num_strength = parse_numeric_strength(detected_strength)

            detected = DetectedMedicine(
                brand=detected_brand,
                salt=detected_salt,
                strength=detected_strength,
                strength_mg=num_strength,
                form=detected_form,
                manufacturer=detected_mfg,
            )
        else:
            raise ValueError("Substitution check requires either 'doc_id' or 'brand'/'salt'")

        # 2. CRITICAL SAFETY CHECK: Narrow Therapeutic Index (NTI) Hard-Block
        nti_match = self.nti_repo.check_nti(salt=detected_salt, brand=detected_brand)
        if nti_match:
            return SubstitutionAnalysisResult(
                state=SubstitutionResultState.SUBSTITUTION_BLOCKED_NTI,
                blocked=True,
                title="Substitution Prohibited",
                message=(
                    f"{detected_brand or detected_salt} is classified under the Narrow Therapeutic Index (NTI). "
                    "Brand or formulation substitution is strictly prohibited without treating physician oversight."
                ),
                clinical_rationale=nti_match.clinical_rationale,
                detected_medicine=detected,
                alternatives=[],
                interactions=[],
                interaction_check_status="available",
                review_status=review_status,
                provenance=provenance_env,
            )

        # 3. Retrieve salt-equivalent candidates from curated index
        candidates: List[CandidateAlternative] = []
        if detected_salt:
            candidates = self.drug_index.find_candidates(
                salt=detected_salt,
                query_brand=detected_brand,
                strength_mg=num_strength,
                form=detected_form,
            )

        # 4. Cross-check active prescriptions from canonical patient record
        active_medications = []
        if patient_id and self.repository:
            patient_context = self.repository.get_patient_context(patient_id)
            active_medications = patient_context.medications

        all_interactions: List[InteractionAdvisory] = []
        interaction_status = "available"

        eval_items: List[CandidateAlternative] = []
        if detected and detected.salt:
            eval_items.append(
                CandidateAlternative(
                    brand=detected.brand or detected.salt,
                    salt=detected.salt,
                    strength=detected.strength or "unknown",
                    strength_mg=detected.strength_mg or 0.0,
                    form=detected.form or "tablet",
                    common_interactions=[],
                )
            )
        eval_items.extend(candidates)

        for cand in eval_items:
            cand_advisories, cand_status = self.interaction_checker.check_interactions(
                candidate=cand,
                active_medications=active_medications,
            )
            all_interactions.extend(cand_advisories)
            if cand_status == "unavailable":
                interaction_status = "unavailable"

        # Deduplicate interactions
        seen_interactions = set()
        deduped_interactions = []
        for item in all_interactions:
            key = (item.active_medication, item.candidate_drug, item.risk_description)
            if key not in seen_interactions:
                seen_interactions.add(key)
                deduped_interactions.append(item)

        # 5. Determine outcome state
        if review_status == "needs_review":
            state = SubstitutionResultState.NEEDS_REVIEW
            title = "Medicine Extraction Requires Review"
            message = "Blister pack scan confidence is below confirmation threshold. Verify medicine identity before substituting."
        elif not candidates:
            state = SubstitutionResultState.NO_MATCH
            title = "No Vetted Substitutes Found"
            message = f"No bioequivalent salt-matched alternatives found in formulary for {detected_brand or detected_salt}."
        else:
            state = SubstitutionResultState.SUBSTITUTION_AVAILABLE
            title = "Salt-Equivalent Alternatives Available"
            message = f"Found {len(candidates)} bioequivalent salt-matched alternative(s)."

        return SubstitutionAnalysisResult(
            state=state,
            blocked=False,
            title=title,
            message=message,
            clinical_rationale=None,
            detected_medicine=detected,
            alternatives=candidates,
            interactions=deduped_interactions,
            interaction_check_status=interaction_status,
            review_status=review_status,
            provenance=provenance_env,
        )

    def to_api_response(self, analysis: SubstitutionAnalysisResult) -> SubstitutionResponse:
        """Convert domain analysis result to canonical SubstitutionResponse API schema."""
        api_alts: List[DrugAlternative] = [
            DrugAlternative(
                brand=c.brand,
                salt=c.salt,
                strength_mg=c.strength_mg,
                form=c.form,
                manufacturer=c.manufacturer,
                price_inr=c.price_inr,
                nti=c.nti,
                common_interactions=c.common_interactions,
            )
            for c in analysis.alternatives
        ]

        interaction_msgs = [adv.risk_description for adv in analysis.interactions]
        reason = analysis.clinical_rationale or analysis.message if analysis.blocked else None

        return SubstitutionResponse(
            blocked=analysis.blocked,
            reason=reason,
            alternatives=api_alts,
            interactions=interaction_msgs,
        )
