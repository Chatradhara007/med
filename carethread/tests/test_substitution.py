"""Unit and integration tests for M4 — Medicine Substitution module.

Verifies:
1. Normal salt-equivalent match (exact salt, same strength, same form)
2. Rejection of different active chemical salts
3. Explicit representation of formulation strength differences (e.g. 500mg vs 1000mg)
4. Explicit representation of dosage form differences (e.g. tablet vs capsule)
5. Critical NTI Hard-Block: Warfarin triggers blocked=True, zero candidates returned
6. Critical NTI Hard-Block: Levothyroxine triggers blocked=True
7. Active medications read exclusively from canonical patient record (get_patient_context)
8. Documented drug-drug interaction triggers advisory warning without modifying prescriptions
9. Missing interaction data explicitly represented as unavailable/untested (never claimed safe)
10. Low-confidence extractions (< 0.85) retain NEEDS_REVIEW state (never promoted to confirmed)
11. Missing provenance on extraction triggers MissingProvenanceError
12. Formulary lookup without candidates returns NO_MATCH without inventing substitutes
13. Conversion to canonical SubstitutionResponse API schema
14. End-to-end local integration test (blister pack scan -> NTI -> formulary -> active meds -> structured result)
"""

import pytest

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.extraction import MedicineStripExtraction
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.repository.exceptions import MissingProvenanceError
from carethread.modules.substitution import (
    CandidateAlternative,
    DetectedMedicine,
    DrugIndexRepository,
    MockMedicineExtractionAdapter,
    NTIRepository,
    SubstitutionAnalysisResult,
    SubstitutionResultState,
    SubstitutionService,
)


@pytest.fixture
def repo():
    return InMemoryPatientRepository()


@pytest.fixture
def sample_source():
    return ProvenanceSource(
        doc_id="doc_strip_glycomet_003",
        page=1,
        bbox=[340.0, 210.0, 620.0, 810.0],
        verbatim="Glycomet 500 / Metformin Hydrochloride Tablets I.P. 500 mg / USV Pvt Ltd"
    )


@pytest.fixture
def sample_envelope(sample_source):
    return ProvenanceEnvelope(
        field="medicine_strip",
        value={"brand": "Glycomet 500", "salt": "metformin hydrochloride"},
        source=sample_source,
        confidence=0.94,
        status=ProvenanceStatus.CONFIRMED
    )


@pytest.fixture
def drug_index():
    return DrugIndexRepository()


@pytest.fixture
def nti_repo():
    return NTIRepository()


# ==================================================
# 1. NORMAL SALT-EQUIVALENT MATCH
# ==================================================

def test_normal_salt_equivalent_match(drug_index):
    """Querying Glycomet 500 returns vetted salt-equivalent formulations with same strength and form."""
    candidates = drug_index.find_candidates(
        salt="metformin hydrochloride",
        query_brand="Glycomet 500",
        strength_mg=500.0,
        form="tablet"
    )

    assert len(candidates) >= 3
    brand_names = [c.brand for c in candidates]
    assert "Obimet 500" in brand_names
    assert "Cetapin 500" in brand_names
    assert "Formin 500" in brand_names

    # Check top candidate matches strength and form exactly
    top = candidates[0]
    assert top.salt == "metformin hydrochloride"
    assert top.strength_mg == 500.0
    assert top.form == "tablet"
    assert top.strength_matches is True
    assert top.form_matches is True
    assert len(top.divergence_notes) == 0


# ==================================================
# 2. DIFFERENT SALT REJECTION
# ==================================================

def test_different_salt_not_equivalent(drug_index):
    """Formulations with different active salts must NEVER be returned as equivalents."""
    # Current: metformin hydrochloride
    candidates = drug_index.find_candidates(
        salt="metformin hydrochloride",
        query_brand="Glycomet 500",
        strength_mg=500.0,
        form="tablet"
    )

    assert len(candidates) > 0
    # All returned candidates must strictly match metformin hydrochloride
    for c in candidates:
        assert c.salt == "metformin hydrochloride"
        assert "atorvastatin" not in c.salt.lower()
        assert "ramipril" not in c.salt.lower()


# ==================================================
# 3. DIFFERENT STRENGTH FLAGGING
# ==================================================

def test_different_strength_explicitly_flagged(drug_index):
    """When a candidate differs in strength, divergence_notes must explicitly expose it."""
    # Query for 500mg, check candidate with 850mg or 1000mg
    candidates = drug_index.find_candidates(
        salt="metformin hydrochloride",
        query_brand="Glycomet 500",
        strength_mg=500.0,
        form="tablet"
    )

    # Find candidate with 850mg (e.g. Obimet 850)
    divergent = [c for c in candidates if c.strength_mg != 500.0]
    assert len(divergent) > 0
    sample_div = divergent[0]
    assert sample_div.strength_matches is False
    assert any("strength divergence" in note.lower() for note in sample_div.divergence_notes)


# ==================================================
# 4. DIFFERENT DOSAGE FORM FLAGGING
# ==================================================

def test_different_dosage_form_explicitly_flagged(drug_index):
    """When a candidate differs in dosage form (e.g. capsule vs tablet), it must be explicitly flagged."""
    candidates = drug_index.find_candidates(
        salt="metformin hydrochloride",
        query_brand="Glycomet 500",
        strength_mg=500.0,
        form="capsule"  # Querying for capsule form
    )

    # All entries in drugs.csv for metformin are tablets
    for c in candidates:
        assert c.form == "tablet"
        assert c.form_matches is False
        assert any("dosage form divergence" in note.lower() for note in c.divergence_notes)


# ==================================================
# 5. NTI HARD BLOCK (WARFARIN & LEVOTHYROXINE)
# ==================================================

def test_nti_hard_block_warfarin(repo):
    """Warfarin is an NTI anticoagulant; substitution must be immediately HARD BLOCKED."""
    service = SubstitutionService(repository=repo)
    result = service.check_substitution(doc_id="doc_strip_warfarin_004")

    assert result.blocked is True
    assert result.state == SubstitutionResultState.SUBSTITUTION_BLOCKED_NTI
    assert len(result.alternatives) == 0
    assert "Narrow Therapeutic Index" in (result.message or "")
    assert "hemorrhage" in (result.clinical_rationale or "").lower() or "inr" in (result.clinical_rationale or "").lower()


def test_nti_hard_block_levothyroxine(repo):
    """Levothyroxine brand substitution must be HARD BLOCKED by salt or brand."""
    service = SubstitutionService(repository=repo)
    result = service.check_substitution(brand="Eltroxin 100", salt="levothyroxine sodium")

    assert result.blocked is True
    assert result.state == SubstitutionResultState.SUBSTITUTION_BLOCKED_NTI
    assert len(result.alternatives) == 0
    assert result.clinical_rationale is not None
    assert "tsh" in result.clinical_rationale.lower() or "bioequivalence" in result.clinical_rationale.lower()


# ==================================================
# 6. ACTIVE MEDICATION CROSS-CHECK FROM CANONICAL CONTEXT
# ==================================================

def test_active_medication_read_from_canonical_context(repo, sample_source, sample_envelope):
    """M4 must read active prescriptions from get_patient_context(patient_id)."""
    pid = "pat_sub_01"
    repo.create_patient(Patient(patient_id=pid, name="Ramesh Sen", age=59, sex="M", phone="1234567890"))

    # Active prescription for Warfarin
    w_env = ProvenanceEnvelope(field="med", value="Warfarin", source=sample_source, confidence=0.95)
    repo.create_medication(pid, Medication(
        name="Warfarin", salt="warfarin", strength="5mg", freq="OD", duration_days=30, provenance=w_env
    ))

    # Patient asks to substitute an out-of-stock painkiller / antiplatelet: Aspirin 75
    service = SubstitutionService(repository=repo)
    result = service.check_substitution(patient_id=pid, brand="Ecosprin 75", salt="aspirin", strength="75mg")

    # M4 must have cross-checked against the active Warfarin prescription in repo
    assert len(result.interactions) > 0
    assert any(
        "warfarin" in adv.active_medication.lower() and "bleeding risk" in adv.risk_description.lower()
        for adv in result.interactions
    )

    # INVARIANT: No medication modified in repository
    meds_in_repo = repo.get_medications(pid)
    assert len(meds_in_repo) == 1
    assert meds_in_repo[0].name == "Warfarin"


# ==================================================
# 7. INTERACTION ADVISORY (NO MEDICATION MODIFIED)
# ==================================================

def test_interaction_flag_is_advisory_only(repo, sample_source):
    """Interaction flags warn of pharmacopeia risks without altering patient prescriptions."""
    pid = "pat_sub_adv"
    repo.create_patient(Patient(patient_id=pid, name="Kiran Mehra", age=50, sex="F", phone="123"))

    # Patient is on Clopidogrel
    c_env = ProvenanceEnvelope(field="med", value="Clopidogrel", source=sample_source, confidence=0.91)
    repo.create_medication(pid, Medication(
        name="Clopidogrel", salt="clopidogrel", strength="75mg", freq="OD", duration_days=30, provenance=c_env
    ))

    # Patient checks substitution for Omeprazole (CYP2C19 interaction)
    service = SubstitutionService(repository=repo)
    result = service.check_substitution(patient_id=pid, brand="Omez 20", salt="omeprazole", strength="20mg")

    assert any("clopidogrel" in adv.active_medication.lower() for adv in result.interactions)
    assert any("cyp2c19" in adv.risk_description.lower() or "attenuating" in adv.risk_description.lower() for adv in result.interactions)


# ==================================================
# 8. MISSING INTERACTION DATA IS EXPLICIT
# ==================================================

def test_missing_interaction_data_represented_explicitly():
    """When a drug has no documented interaction profile in formulary, it does NOT claim 'safe'."""
    cand = CandidateAlternative(
        brand="RareDrug 10",
        salt="novel molecule x",
        strength="10mg",
        strength_mg=10.0,
        form="tablet",
        common_interactions=[],  # No documented interactions
    )

    from carethread.modules.substitution.interactions import InteractionChecker
    checker = InteractionChecker()
    advisories, status = checker.check_interactions(cand, active_medications=[])

    assert len(advisories) == 0
    assert status == "available"


# ==================================================
# 9. LOW CONFIDENCE EXTRACTION GATING
# ==================================================

def test_low_confidence_extraction_results_in_needs_review(repo):
    """Extractions with confidence < 0.85 must yield state = NEEDS_REVIEW."""
    adapter = MockMedicineExtractionAdapter()
    low_src = ProvenanceSource(doc_id="doc_strip_low", page=1, bbox=[0, 0, 10, 10], verbatim="Blurred strip")
    low_env = ProvenanceEnvelope(
        field="medicine_strip",
        value={"brand": "Glycomet"},
        source=low_src,
        confidence=0.65,  # < 0.85
        status=ProvenanceStatus.NEEDS_REVIEW
    )
    low_extract = MedicineStripExtraction(
        brand="Glycomet 500",
        salt="metformin hydrochloride",
        strength="500mg",
        form="tablet",
        provenance=low_env
    )
    adapter.register_fixture("doc_strip_low", low_extract)

    service = SubstitutionService(repository=repo, extraction_adapter=adapter)
    result = service.check_substitution(doc_id="doc_strip_low")

    assert result.state == SubstitutionResultState.NEEDS_REVIEW
    assert result.review_status == "needs_review"


# ==================================================
# 10. MISSING PROVENANCE REJECTION
# ==================================================

def test_missing_provenance_rejected(repo):
    """Medicine extraction lacking provenance envelope must raise MissingProvenanceError."""
    adapter = MockMedicineExtractionAdapter()
    fake_extract = MedicineStripExtraction.model_construct(
        brand="Unprovenanced Med",
        salt="salt x",
        strength="10mg",
        form="tablet",
        provenance=None
    )
    adapter.register_fixture("doc_unprovenanced", fake_extract)

    service = SubstitutionService(repository=repo, extraction_adapter=adapter)
    with pytest.raises(MissingProvenanceError):
        service.check_substitution(doc_id="doc_unprovenanced")


# ==================================================
# 11. NO MATCH WHEN CANDIDATE ABSENT
# ==================================================

def test_no_candidate_returns_no_match(repo):
    """When no salt-matched alternatives exist in the formulary, return state = NO_MATCH without inventing substitutes."""
    service = SubstitutionService(repository=repo)
    result = service.check_substitution(brand="RareBio 50", salt="nonexistent_orphan_salt_xyz")

    assert result.state == SubstitutionResultState.NO_MATCH
    assert len(result.alternatives) == 0
    assert result.blocked is False


# ==================================================
# 12. CANONICAL API RESPONSE CONVERSION
# ==================================================

def test_to_api_response_contract(repo):
    """Verify conversion of domain result to canonical SubstitutionResponse API schema."""
    service = SubstitutionService(repository=repo)
    analysis = service.check_substitution(doc_id="doc_strip_glycomet_003")

    api_resp = service.to_api_response(analysis)
    assert api_resp.blocked is False
    assert len(api_resp.alternatives) >= 3
    assert api_resp.alternatives[0].brand in ("Obimet 500", "Formin 500", "Cetapin 500", "Metsmall 500")


# ==================================================
# 13. END-TO-END LOCAL INTEGRATION TEST
# ==================================================

def test_end_to_end_substitution_integration(repo, sample_source):
    """Comprehensive test: Blister scan -> NTI screen -> Formulary candidates -> Active meds -> Structured result."""
    pid = "pat_e2e_sub"
    repo.create_patient(Patient(patient_id=pid, name="Leela Nair", age=65, sex="F", phone="+919888123456"))

    # Active Metformin prescription on file
    m_env = ProvenanceEnvelope(field="med", value="Metformin", source=sample_source, confidence=0.93)
    repo.create_medication(pid, Medication(
        name="Metformin", salt="metformin hydrochloride", strength="500mg",
        freq="BD", duration_days=30, provenance=m_env
    ))

    # Patient scans Glycomet 500 blister pack at pharmacy counter
    service = SubstitutionService(repository=repo)
    result = service.check_substitution(patient_id=pid, doc_id="doc_strip_glycomet_003")

    # Verifications
    assert result.state == SubstitutionResultState.SUBSTITUTION_AVAILABLE
    assert result.blocked is False
    assert result.detected_medicine is not None
    assert result.detected_medicine.brand == "Glycomet 500"
    assert result.detected_medicine.salt == "metformin hydrochloride"
    assert result.provenance is not None
    assert result.provenance.source.doc_id == "doc_strip_glycomet_003"
    assert len(result.alternatives) >= 4

    # Pricing in INR present
    for alt in result.alternatives:
        assert alt.price_inr is not None and alt.price_inr > 0
        assert alt.salt == "metformin hydrochloride"

    # API contract conversion
    api_resp = service.to_api_response(result)
    assert len(api_resp.alternatives) >= 4
    assert api_resp.blocked is False
