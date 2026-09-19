"""Unit and integration tests for M3 — Lab Interpreter module.

Verifies:
1. Printed reference range precedence (Report range takes absolute priority over fallback)
2. Fallback reference range resolution when report range is missing
3. Controlled handling when no range exists (zero range invention)
4. Below-range deterministic deviation calculation
5. Within-range deterministic deviation calculation
6. Above-range deterministic deviation calculation
7. Boundary values behavior (value == ref_low and value == ref_high are within range)
8. Multiple lab findings processing
9. Deterministic and reproducible abnormal-first ranking
10. Diagnosis context cross-reading (no new diagnosis created)
11. Medication context cross-reading (medication entity unchanged)
12. Unbroken provenance preservation and missing provenance rejection
13. Low-confidence uncertainty preservation (needs_review not promoted to confirmed)
14. Patient-readable plain-language explanation formatting
15. Critical LLM safety: LLM formatter cannot modify structured values or alter finding direction
16. End-to-end local integration test (canonical single-table patient context -> LabInterpretationReport)
"""

import pytest

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.repository.exceptions import MissingProvenanceError
from carethread.modules.lab_interpreter import (
    ClinicalSafetyViolation,
    FindingStatus,
    InterpretedLabFinding,
    LabInterpretationReport,
    LabInterpreterService,
    MockLabExplanationFormatter,
    ReferenceRangeRepository,
    ReferenceRangeSource,
    calculate_deviation,
    rank_findings,
    resolve_reference_range,
    verify_lab_explanation_safety,
)


@pytest.fixture
def repo():
    return InMemoryPatientRepository()


@pytest.fixture
def sample_source():
    return ProvenanceSource(
        doc_id="d_lab_001",
        page=1,
        bbox=[280.0, 110.0, 310.0, 890.0],
        verbatim="Serum Creatinine (Enzymatic) 2.40 mg/dL [0.70 - 1.30] HIGH *"
    )


@pytest.fixture
def sample_envelope(sample_source):
    return ProvenanceEnvelope(
        field="lab_result",
        value={"analyte": "Serum Creatinine", "value": 2.4},
        source=sample_source,
        confidence=0.96
    )


@pytest.fixture
def fallback_repo():
    return ReferenceRangeRepository()


# ==================================================
# 1. PRINTED REFERENCE RANGE PRECEDENCE
# ==================================================

def test_printed_reference_range_takes_precedence(fallback_repo, sample_envelope):
    """Printed report range (10-20) MUST take precedence over fallback database range.

    Scenario:
    Lab report: value = 8, ref_low = 10, ref_high = 20
    Fallback DB (e.g. for Serum Creatinine) might be 0.7 - 1.3.
    Expected:
    ref_source = REPORT
    status = below
    """
    ref_low, ref_high, source = resolve_reference_range(
        analyte="Serum Creatinine",
        report_low=10.0,
        report_high=20.0,
        fallback_repo=fallback_repo,
    )
    assert source == ReferenceRangeSource.REPORT
    assert ref_low == 10.0
    assert ref_high == 20.0

    status, dev = calculate_deviation(value=8.0, ref_low=ref_low, ref_high=ref_high)
    assert status == FindingStatus.BELOW
    assert dev == pytest.approx(0.20)  # (10 - 8) / (20 - 10) = 0.2


# ==================================================
# 2. FALLBACK REFERENCE RANGE RESOLUTION
# ==================================================

def test_fallback_reference_range_when_report_range_missing(fallback_repo):
    """When the report contains no usable range, fallback database is queried.

    Scenario:
    Lab report: ref_low = None, ref_high = None
    Analyte: 'Serum Creatinine' (in fallback CSV: 0.7 - 1.3 mg/dL)
    Expected:
    ref_source = FALLBACK
    ref_low = 0.7
    ref_high = 1.3
    """
    ref_low, ref_high, source = resolve_reference_range(
        analyte="Serum Creatinine",
        report_low=None,
        report_high=None,
        fallback_repo=fallback_repo,
    )
    assert source == ReferenceRangeSource.FALLBACK
    assert ref_low == 0.7
    assert ref_high == 1.3


# ==================================================
# 3. MISSING REFERENCE RANGE (ZERO INVENTED RANGE)
# ==================================================

def test_missing_reference_range_not_invented(fallback_repo):
    """When neither report nor fallback database contains a range, DO NOT INVENT ONE.

    Scenario:
    Unusual biomarker: 'Novel Gene X Expression Index'
    Expected:
    ref_source = NONE
    ref_low = None, ref_high = None
    status = UNKNOWN
    deviation_score = None
    """
    ref_low, ref_high, source = resolve_reference_range(
        analyte="Novel Gene X Expression Index",
        report_low=None,
        report_high=None,
        fallback_repo=fallback_repo,
    )
    assert source == ReferenceRangeSource.NONE
    assert ref_low is None
    assert ref_high is None

    status, dev = calculate_deviation(value=42.5, ref_low=ref_low, ref_high=ref_high)
    assert status == FindingStatus.UNKNOWN
    assert dev is None


# ==================================================
# 4. DEVIATION & BOUNDARY BEHAVIOR
# ==================================================

@pytest.mark.parametrize(
    "val, expected_status, expected_dev",
    [
        (5.0, FindingStatus.BELOW, 0.50),   # value < ref_low: (10 - 5) / 10 = 0.50
        (10.0, FindingStatus.WITHIN, 0.0),  # value == ref_low: exactly at boundary
        (15.0, FindingStatus.WITHIN, 0.0),  # ref_low < value < ref_high: inside range
        (20.0, FindingStatus.WITHIN, 0.0),  # value == ref_high: exactly at boundary
        (25.0, FindingStatus.ABOVE, 0.50),  # value > ref_high: (25 - 20) / 10 = 0.50
    ]
)
def test_deviation_boundaries_deterministic(val, expected_status, expected_dev):
    """Deterministic behavior across boundaries: < low, == low, inside, == high, > high."""
    status, score = calculate_deviation(value=val, ref_low=10.0, ref_high=20.0)
    assert status == expected_status
    assert score == pytest.approx(expected_dev)


# ==================================================
# 5. MULTIPLE FINDINGS & DETERMINISTIC RANKING
# ==================================================

def test_deterministic_ranking_abnormal_first(sample_envelope):
    """Abnormal findings must rank strictly above normal findings, ordered by descending deviation.

    Scenario:
    - Serum Creatinine: value 2.4, range 0.7 - 1.3 -> High, deviation = (2.4 - 1.3) / 0.6 = 1.83
    - Serum Potassium: value 5.8, range 3.5 - 5.1 -> High, deviation = (5.8 - 5.1) / 1.6 = 0.44
    - Fasting Blood Sugar: value 150.0, range 70 - 100 -> High, deviation = (150 - 100) / 30 = 1.67
    - Serum Sodium: value 138.0, range 135 - 145 -> Within normal limits, deviation = 0.0
    - Total Bilirubin: value 0.8, range 0.2 - 1.2 -> Within normal limits, deviation = 0.0

    Expected Ranking:
    Rank 1: Serum Creatinine (dev 1.83)
    Rank 2: Fasting Blood Sugar (dev 1.67)
    Rank 3: Serum Potassium (dev 0.44)
    Rank 4: Serum Sodium (alphabetical within normal)
    Rank 5: Total Bilirubin (alphabetical within normal)
    """
    findings = [
        InterpretedLabFinding(
            analyte="Serum Creatinine", value=2.4, unit="mg/dL",
            ref_low=0.7, ref_high=1.3, ref_source=ReferenceRangeSource.REPORT,
            status=FindingStatus.ABOVE, deviation_score=1.83, provenance=sample_envelope
        ),
        InterpretedLabFinding(
            analyte="Serum Potassium", value=5.8, unit="mEq/L",
            ref_low=3.5, ref_high=5.1, ref_source=ReferenceRangeSource.REPORT,
            status=FindingStatus.ABOVE, deviation_score=0.44, provenance=sample_envelope
        ),
        InterpretedLabFinding(
            analyte="Fasting Blood Sugar", value=150.0, unit="mg/dL",
            ref_low=70.0, ref_high=100.0, ref_source=ReferenceRangeSource.REPORT,
            status=FindingStatus.ABOVE, deviation_score=1.67, provenance=sample_envelope
        ),
        InterpretedLabFinding(
            analyte="Serum Sodium", value=138.0, unit="mEq/L",
            ref_low=135.0, ref_high=145.0, ref_source=ReferenceRangeSource.REPORT,
            status=FindingStatus.WITHIN, deviation_score=0.0, provenance=sample_envelope
        ),
        InterpretedLabFinding(
            analyte="Total Bilirubin", value=0.8, unit="mg/dL",
            ref_low=0.2, ref_high=1.2, ref_source=ReferenceRangeSource.REPORT,
            status=FindingStatus.WITHIN, deviation_score=0.0, provenance=sample_envelope
        ),
    ]

    ranked = rank_findings(findings)

    assert [r.analyte for r in ranked] == [
        "Serum Creatinine",
        "Fasting Blood Sugar",
        "Serum Potassium",
        "Serum Sodium",
        "Total Bilirubin",
    ]
    assert [r.rank for r in ranked] == [1, 2, 3, 4, 5]


# ==================================================
# 6. DIAGNOSIS CONTEXT (NO NEW DIAGNOSES CREATED)
# ==================================================

def test_diagnosis_context_used_without_creating_new_diagnosis(repo, sample_envelope, sample_source):
    """M3 must consume active diagnoses for context without creating or mutating diagnoses."""
    pid = "pat_m3_diag"
    repo.create_patient(Patient(patient_id=pid, name="Arun Verma", age=58, sex="M", phone="1234567890"))

    # Patient has documented Type 2 Diabetes
    d_env = ProvenanceEnvelope(field="diag", value="T2DM", source=sample_source, confidence=0.95)
    repo.create_diagnosis(pid, Diagnosis(label="Type 2 Diabetes", code_or_slug="t2dm", provenance=d_env))

    # Ingest elevated fasting blood sugar
    lab = LabResult(
        analyte="Fasting Blood Sugar", value=165.0, unit="mg/dL",
        ref_low=70.0, ref_high=100.0, provenance=sample_envelope
    )
    repo.create_lab_result(pid, lab)

    service = LabInterpreterService(repository=repo)
    report = service.interpret_patient_labs(pid)

    assert report.total_findings == 1
    finding = report.all_findings[0]
    assert finding.analyte == "Fasting Blood Sugar"
    assert "Type 2 Diabetes" in finding.context_diagnoses

    # STRICT INVARIANT: M3 must NOT create new diagnoses in repository
    diagnoses_in_repo = repo.get_diagnoses(pid)
    assert len(diagnoses_in_repo) == 1
    assert diagnoses_in_repo[0].label == "Type 2 Diabetes"


# ==================================================
# 7. MEDICATION CONTEXT (MEDICATION UNCHANGED)
# ==================================================

def test_medication_context_cross_read_without_modifying_prescription(repo, sample_envelope, sample_source):
    """Elevated creatinine cross-read with active Metformin produces alert; prescription is unmodified."""
    pid = "pat_m3_med"
    repo.create_patient(Patient(patient_id=pid, name="Sunita Roy", age=63, sex="F", phone="9876543210"))

    # Active Metformin
    m_env = ProvenanceEnvelope(field="med", value={"name": "Metformin"}, source=sample_source, confidence=0.92)
    original_med = Medication(
        name="Metformin", salt="metformin hydrochloride", strength="500mg",
        freq="BD", duration_days=30, instructions="Take with meal", provenance=m_env
    )
    repo.create_medication(pid, original_med)

    # Elevated Creatinine (2.4 mg/dL)
    lab = LabResult(
        analyte="Serum Creatinine", value=2.4, unit="mg/dL",
        ref_low=0.7, ref_high=1.3, provenance=sample_envelope
    )
    repo.create_lab_result(pid, lab)

    service = LabInterpreterService(repository=repo)
    report = service.interpret_patient_labs(pid)

    finding = report.all_findings[0]
    assert "Metformin" in finding.context_medications
    assert any("lactic acidosis" in note.lower() for note in finding.context_notes)
    assert len(report.cross_module_alerts) > 0
    assert "lactic acidosis" in report.cross_module_alerts[0].lower()

    # STRICT INVARIANT: M3 must NOT modify the medication record in repo
    meds_in_repo = repo.get_medications(pid)
    assert len(meds_in_repo) == 1
    assert meds_in_repo[0].strength == "500mg"
    assert meds_in_repo[0].freq == "BD"
    assert meds_in_repo[0].duration_days == 30


# ==================================================
# 8. PROVENANCE PRESERVATION & UNCERTAINTY HANDLING
# ==================================================

def test_provenance_preserved_intact(sample_source, sample_envelope):
    """Each interpreted finding must retain exact citation to underlying document row."""
    lab = LabResult(
        analyte="Serum Creatinine", value=2.4, unit="mg/dL",
        ref_low=0.7, ref_high=1.3, provenance=sample_envelope
    )

    service = LabInterpreterService()
    report = service.interpret_labs("pat_test", [lab])

    finding = report.all_findings[0]
    assert finding.provenance.source.doc_id == sample_source.doc_id
    assert finding.provenance.source.page == 1
    assert finding.provenance.source.bbox == [280.0, 110.0, 310.0, 890.0]
    assert finding.provenance.source.verbatim == sample_source.verbatim
    assert finding.confidence == 0.96


def test_missing_provenance_fails_validation():
    """Unprovenanced lab data must be rejected immediately."""
    class UnprovenancedLab:
        analyte = "Potassium"
        value = 4.2
        unit = "mEq/L"
        ref_low = 3.5
        ref_high = 5.1
        provenance = None

    service = LabInterpreterService()
    with pytest.raises(MissingProvenanceError):
        service.interpret_labs("pat_test", [UnprovenancedLab()])


def test_low_confidence_uncertainty_preserved(sample_source):
    """Low-confidence results (status=needs_review or conf < 0.85) must NOT be promoted to confirmed."""
    low_env = ProvenanceEnvelope(
        field="lab_result",
        value={"analyte": "Serum Potassium"},
        source=sample_source,
        confidence=0.60,
        status=ProvenanceStatus.NEEDS_REVIEW
    )
    lab = LabResult(
        analyte="Serum Potassium", value=5.8, unit="mEq/L",
        ref_low=3.5, ref_high=5.1, provenance=low_env
    )

    service = LabInterpreterService()
    report = service.interpret_labs("pat_low_conf", [lab])

    finding = report.all_findings[0]
    assert finding.review_status == "needs_review"
    assert finding.confidence == 0.60


# ==================================================
# 9. LLM FORMATTING & CLINICAL SAFETY GUARDRAILS
# ==================================================

def test_mock_llm_formatter_generates_plain_language(sample_envelope):
    """Formatter generates accessible wording while preserving all clinical numbers."""
    finding = InterpretedLabFinding(
        analyte="Serum Creatinine", value=2.4, unit="mg/dL",
        ref_low=0.7, ref_high=1.3, ref_source=ReferenceRangeSource.REPORT,
        status=FindingStatus.ABOVE, deviation_score=1.83, provenance=sample_envelope
    )

    formatter = MockLabExplanationFormatter()
    explanation = formatter.format_explanation(finding)

    assert "Serum Creatinine" in explanation
    assert "2.4" in explanation
    assert "0.7" in explanation
    assert "1.3" in explanation
    assert "above" in explanation


def test_llm_safety_violation_when_altering_clinical_facts(sample_envelope):
    """Clinical safety check must catch and reject any attempt to alter clinical values or status."""
    finding = InterpretedLabFinding(
        analyte="Serum Creatinine", value=2.4, unit="mg/dL",
        ref_low=0.7, ref_high=1.3, ref_source=ReferenceRangeSource.REPORT,
        status=FindingStatus.ABOVE, deviation_score=1.83, provenance=sample_envelope
    )

    # 1. Dropping analyte name
    with pytest.raises(ClinicalSafetyViolation):
        verify_lab_explanation_safety(finding, "Your kidney test is 2.4 mg/dL, above range 0.7 to 1.3.")

    # 2. Altering reported value from 2.4 to 1.4
    with pytest.raises(ClinicalSafetyViolation):
        verify_lab_explanation_safety(finding, "Your Serum Creatinine is 1.4 mg/dL, above range 0.7 to 1.3.")

    # 3. Inverting finding direction (calling an above-range value normal)
    with pytest.raises(ClinicalSafetyViolation):
        verify_lab_explanation_safety(finding, "Your Serum Creatinine is 2.4 mg/dL, within normal limits 0.7 to 1.3.")

    # 4. Unauthorized autonomous diagnostic claim
    with pytest.raises(ClinicalSafetyViolation):
        verify_lab_explanation_safety(
            finding,
            "Your Serum Creatinine is 2.4 mg/dL. This proves you have acute renal failure."
        )


# ==================================================
# 10. END-TO-END LOCAL INTEGRATION TEST
# ==================================================

def test_end_to_end_lab_interpreter_integration(repo, sample_source, sample_envelope):
    """Comprehensive test: Canonical patient record -> LabInterpreterService -> LabInterpretationReport."""
    pid = "pat_e2e_labs"

    # Profile
    repo.create_patient(Patient(patient_id=pid, name="K. V. Ramanathan", age=62, sex="M", phone="+919444123456"))

    # Active Diagnosis
    d_env = ProvenanceEnvelope(field="diag", value="CAD", source=sample_source, confidence=0.97)
    repo.create_diagnosis(pid, Diagnosis(label="Coronary Artery Disease", code_or_slug="cad", provenance=d_env))

    # Active Medication
    m_env = ProvenanceEnvelope(field="med", value="Metformin", source=sample_source, confidence=0.94)
    repo.create_medication(pid, Medication(
        name="Metformin", salt="metformin hydrochloride", strength="500mg",
        freq="BD", duration_days=30, instructions="Take with meal", provenance=m_env
    ))

    # Add 4 lab results:
    # 1. Creatinine: elevated
    repo.create_lab_result(pid, LabResult(
        analyte="Serum Creatinine", value=2.4, unit="mg/dL",
        ref_low=0.7, ref_high=1.3, provenance=sample_envelope
    ))
    # 2. Potassium: elevated
    repo.create_lab_result(pid, LabResult(
        analyte="Serum Potassium", value=5.8, unit="mEq/L",
        ref_low=3.5, ref_high=5.1, provenance=sample_envelope
    ))
    # 3. Sodium: normal
    repo.create_lab_result(pid, LabResult(
        analyte="Serum Sodium", value=138.0, unit="mEq/L",
        ref_low=135.0, ref_high=145.0, provenance=sample_envelope
    ))
    # 4. Total Cholesterol: report range missing -> uses fallback (125 - 200 mg/dL)
    repo.create_lab_result(pid, LabResult(
        analyte="Total Cholesterol", value=240.0, unit="mg/dL",
        ref_low=None, ref_high=None, provenance=sample_envelope
    ))

    service = LabInterpreterService(repository=repo)
    report = service.interpret_patient_labs(pid)

    # Verifications
    assert report.patient_id == pid
    assert report.total_findings == 4
    assert report.abnormal_count == 3  # Creatinine, Potassium, Cholesterol are abnormal
    assert len(report.top_findings) == 3

    # Ranking check:
    # Creatinine: (2.4 - 1.3) / 0.6 = 1.83
    # Potassium: (5.8 - 5.1) / 1.6 = 0.44
    # Total Cholesterol: (240 - 200) / 75 = 0.53
    # Expected ranking: Creatinine (1.83) -> Cholesterol (0.53) -> Potassium (0.44) -> Sodium (within)
    assert report.all_findings[0].analyte == "Serum Creatinine"
    assert report.all_findings[0].rank == 1
    assert report.all_findings[1].analyte == "Total Cholesterol"
    assert report.all_findings[1].ref_source == ReferenceRangeSource.FALLBACK  # Fallback resolved!
    assert report.all_findings[2].analyte == "Serum Potassium"
    assert report.all_findings[3].analyte == "Serum Sodium"
    assert report.all_findings[3].status == FindingStatus.WITHIN

    # Cross-module alert check
    assert len(report.cross_module_alerts) > 0
    assert any("metformin" in a.lower() and "lactic acidosis" in a.lower() for a in report.cross_module_alerts)

    # Plain language explanation check
    for f in report.all_findings:
        assert len(f.explanation) > 0
        assert f.analyte in f.explanation
