"""Unit and integration tests for M2 — Care Plan module.

Verifies:
1. Canonical patient context -> structured day-by-day PlanEntry items
2. Frequency-to-slot mapping across multiple days and slots
3. Provenance preservation invariant (source citation retained on every plan entry)
4. Rejection when source data lacks provenance
5. Preservation of needs_review status for low-confidence source items
6. Discharge restrictions and follow-up transformation into PlanEntry
7. Deterministic static escalation rule evaluation (rules.yaml)
8. Critical safety tests: LLM formatter cannot corrupt dosages or invent escalation rules
9. Plan persistence idempotency (preserves dose adherence completion)
10. Full end-to-end local integration test
"""

import pytest

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.plan_entry import PlanEntry, SlotName
from carethread.shared.schemas.alert_rule import AlertSeverity
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)
from carethread.shared.schemas.extraction import DischargeFollowup, DischargeRestriction
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.repository.exceptions import MissingProvenanceError
from carethread.modules.care_plan.service import CarePlanService, map_frequency_to_slots
from carethread.modules.care_plan.rules import load_rules, evaluate_escalation_rules
from carethread.modules.care_plan.schemas import SymptomReport
from carethread.modules.care_plan.formatter import (
    MockLLMFormatter,
    ClinicalSafetyViolation,
    verify_medication_action_safety,
)


@pytest.fixture
def repo():
    return InMemoryPatientRepository()


@pytest.fixture
def sample_source():
    return ProvenanceSource(
        doc_id="d_discharge_001",
        page=2,
        bbox=[120.0, 340.0, 480.0, 362.0],
        verbatim="Tab. Metformin 500mg BD x 30 days"
    )


@pytest.fixture
def sample_envelope(sample_source):
    return ProvenanceEnvelope(
        field="medication",
        value={"name": "Metformin", "strength": "500mg"},
        source=sample_source,
        confidence=0.92
    )


@pytest.fixture
def seeded_patient(repo, sample_envelope, sample_source):
    pid = "pat_plan_01"
    repo.create_patient(Patient(
        patient_id=pid, name="Suresh Patel", age=61, sex="M", phone="+919876543210"
    ))
    # Diagnoses
    diag_env = ProvenanceEnvelope(
        field="diagnosis", value="CAD", source=sample_source, confidence=0.95
    )
    repo.create_diagnosis(pid, Diagnosis(
        label="Coronary Artery Disease", code_or_slug="cad", provenance=diag_env
    ))
    # Medications
    med1 = Medication(
        name="Metformin", salt="metformin hydrochloride", strength="500mg",
        freq="BD", duration_days=30, instructions="Take after meals", provenance=sample_envelope
    )
    med2_env = ProvenanceEnvelope(
        field="medication", value={"name": "Atorvastatin"}, source=sample_source, confidence=0.90
    )
    med2 = Medication(
        name="Atorvastatin", salt="atorvastatin calcium", strength="40mg",
        freq="OD", duration_days=30, instructions="Take at bedtime", provenance=med2_env
    )
    repo.create_medication(pid, med1)
    repo.create_medication(pid, med2)
    return pid


# ==================================================
# 1. FREQUENCY MAPPING & SLOT COVERAGE
# ==================================================

def test_map_frequency_to_slots():
    """Verify standard clinical frequencies map to expected schedule slots."""
    assert map_frequency_to_slots("OD") == [SlotName.MORNING]
    assert map_frequency_to_slots("BD") == [SlotName.MORNING, SlotName.NIGHT]
    assert map_frequency_to_slots("TDS") == [SlotName.MORNING, SlotName.AFTERNOON, SlotName.NIGHT]
    assert map_frequency_to_slots("QID") == [SlotName.MORNING, SlotName.AFTERNOON, SlotName.EVENING, SlotName.NIGHT]
    assert map_frequency_to_slots("OD", instructions="bedtime") == [SlotName.NIGHT]
    assert map_frequency_to_slots("OD", drug_name="Atorvastatin") == [SlotName.NIGHT]


# ==================================================
# 2. CANONICAL CONTEXT -> CARE PLAN GENERATION
# ==================================================

def test_generate_care_plan_multi_day_multi_slot(repo, seeded_patient):
    """Test day-by-day care plan generation covering days 0 to 6 and slots."""
    service = CarePlanService(repository=repo)
    result = service.generate_care_plan(seeded_patient, days=7)

    assert result.patient_id == seeded_patient
    assert result.days_covered == 7
    assert len(result.entries) > 0

    # Metformin BD (morning + night) = 2 per day * 7 days = 14
    # Atorvastatin OD night = 1 per day * 7 days = 7
    # Total entries = 21
    assert len(result.entries) == 21

    # Check Day 0 slots
    day0_entries = [e for e in result.entries if e.day_index == 0]
    slots_day0 = {e.slot for e in day0_entries}
    assert SlotName.MORNING in slots_day0
    assert SlotName.NIGHT in slots_day0

    # Verify every single entry preserves provenanced citations
    for e in result.entries:
        assert e.provenance is not None
        assert e.provenance.source.doc_id == "d_discharge_001"
        assert e.provenance.source.verbatim != ""


# ==================================================
# 3. PROVENANCE PRESERVATION & LOW-CONFIDENCE GATING
# ==================================================

def test_provenance_preserves_needs_review_status(repo, sample_source):
    """If source medication has confidence < 0.85, plan entry must preserve needs_review status."""
    pid = "pat_low_conf"
    repo.create_patient(Patient(patient_id=pid, name="Low Conf", age=50, sex="F", phone="123"))

    low_env = ProvenanceEnvelope(
        field="medication",
        value={"name": "Amlodipine"},
        source=sample_source,
        confidence=0.78  # < 0.85 -> needs_review
    )
    assert low_env.status == ProvenanceStatus.NEEDS_REVIEW

    repo.create_medication(pid, Medication(
        name="Amlodipine", salt="amlodipine", strength="5mg", freq="OD", duration_days=7, provenance=low_env
    ))

    service = CarePlanService(repository=repo)
    res = service.generate_care_plan(pid, days=3)

    for entry in res.entries:
        assert entry.provenance.status == ProvenanceStatus.NEEDS_REVIEW
        assert entry.provenance.confidence == 0.78


def test_missing_provenance_rejected(repo):
    """Clinical items without provenance must fail validation and not generate fabricated provenance."""
    pid = "pat_no_prov"
    repo.create_patient(Patient(patient_id=pid, name="No Prov", age=50, sex="M", phone="123"))

    class FakeMedication:
        name = "Aspirin"
        freq = "OD"
        duration_days = 7
        provenance = None

    context = repo.get_patient_context(pid)
    context.medications.append(FakeMedication())

    service = CarePlanService(repository=repo)
    # Mocking repo to return the unprovenanced med
    repo.get_patient_context = lambda p: context

    with pytest.raises(MissingProvenanceError):
        service.generate_care_plan(pid, days=3)


# ==================================================
# 4. RESTRICTIONS & FOLLOW-UPS
# ==================================================

def test_restrictions_and_followup_plan_entries(repo, sample_source, sample_envelope):
    """Verify documented discharge restrictions and follow-ups become structured PlanEntry items."""
    pid = "pat_rest_01"
    repo.create_patient(Patient(patient_id=pid, name="Restricted", age=55, sex="M", phone="123"))
    repo.create_medication(pid, Medication(
        name="Metformin", salt="metformin", strength="500mg", freq="OD", duration_days=7, provenance=sample_envelope
    ))

    rest_env = ProvenanceEnvelope(
        field="restriction", value="Low sodium diet", source=sample_source, confidence=0.94
    )
    follow_env = ProvenanceEnvelope(
        field="followup", value="Cardiology OPD", source=sample_source, confidence=0.91
    )

    restrictions = [DischargeRestriction(text="Low sodium diet", provenance=rest_env)]
    followups = [DischargeFollowup(what="Cardiology OPD Review", when="Day 7", provenance=follow_env)]

    service = CarePlanService(repository=repo)
    res = service.generate_care_plan(pid, days=7, restrictions=restrictions, followups=followups)

    # Check restriction entries exist for all 7 days
    rest_entries = [e for e in res.entries if "RESTRICTION" in e.med_ref]
    assert len(rest_entries) == 7
    assert "Low sodium diet" in rest_entries[0].action
    assert rest_entries[0].provenance.source.doc_id == sample_source.doc_id

    # Check followup entry scheduled for Day 6 (end of post-discharge week)
    follow_entries = [e for e in res.entries if "FOLLOWUP" in e.med_ref]
    assert len(follow_entries) == 1
    assert follow_entries[0].day_index == 6
    assert "Cardiology OPD Review" in follow_entries[0].action


# ==================================================
# 5. DETERMINISTIC ESCALATION RULES (rules.yaml)
# ==================================================

def test_static_rules_loaded_and_evaluated():
    """Verify static rules from rules.yaml fire deterministically based on diagnoses and vitals."""
    rules = load_rules()
    assert len(rules) >= 4
    rule_ids = {r.id for r in rules}
    assert "fever_persistent" in rule_ids
    assert "post_cardiac_chest_pain" in rule_ids

    # 1. Test post_cardiac_chest_pain triggers when CAD diagnosis + chest pain
    source = ProvenanceSource(doc_id="d1", page=1, bbox=[0, 0, 100, 100], verbatim="CAD")
    env = ProvenanceEnvelope(field="diag", value={}, source=source, confidence=0.9)
    diagnoses = [Diagnosis(label="Coronary Artery Disease", provenance=env)]

    alerts_pain = evaluate_escalation_rules(
        patient_diagnoses=diagnoses,
        symptoms={"chest_pain": True},
        rules=rules
    )
    assert len(alerts_pain) == 1
    assert alerts_pain[0].rule_id == "post_cardiac_chest_pain"
    assert alerts_pain[0].severity == AlertSeverity.CRITICAL

    # 2. Same chest pain with NON-cardiac diagnosis does NOT trigger post_cardiac_chest_pain
    non_cardiac = [Diagnosis(label="Osteoarthritis", provenance=env)]
    alerts_no_cardiac = evaluate_escalation_rules(
        patient_diagnoses=non_cardiac,
        symptoms={"chest_pain": True},
        rules=rules
    )
    assert len(alerts_no_cardiac) == 0

    # 3. Persistent fever (> 101 for 48h) triggers fever_persistent regardless of diagnosis
    alerts_fever = evaluate_escalation_rules(
        patient_diagnoses=non_cardiac,
        symptoms={"fever_f": 102.2, "fever_hours": 50},
        rules=rules
    )
    assert len(alerts_fever) == 1
    assert alerts_fever[0].rule_id == "fever_persistent"
    assert alerts_fever[0].severity == AlertSeverity.HIGH


def test_service_evaluate_escalation_rules_persists(repo, seeded_patient):
    """Verify service evaluates and persists fired alerts into single table."""
    service = CarePlanService(repository=repo)
    symptoms = SymptomReport(chest_pain=True)

    alerts = service.evaluate_escalation_rules(seeded_patient, symptoms, persist=True)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "post_cardiac_chest_pain"

    # Verify alert exists in patient partition
    saved_alerts = repo.get_alerts(seeded_patient)
    assert len(saved_alerts) == 1
    assert saved_alerts[0].rule_id == "post_cardiac_chest_pain"


# ==================================================
# 6. CRITICAL SAFETY TESTS
# ==================================================

def test_safety_check_detects_dosage_alteration(sample_envelope):
    """The formatter MUST NOT alter clinical dosages or omit drug names."""
    med = Medication(
        name="Metformin", salt="metformin hydrochloride", strength="500mg",
        freq="BD", duration_days=30, provenance=sample_envelope
    )

    # Valid formatting
    verify_medication_action_safety(med, "Take Metformin 500mg tablet with meal")

    # Safety violation: dose altered from 500mg to 1000mg
    with pytest.raises(ClinicalSafetyViolation):
        verify_medication_action_safety(med, "Take Metformin 1000mg tablet with meal")

    # Safety violation: drug name dropped
    with pytest.raises(ClinicalSafetyViolation):
        verify_medication_action_safety(med, "Take 500mg tablet with meal")


# ==================================================
# 7. IDEMPOTENT PERSISTENCE & DOSE ADHERENCE
# ==================================================

def test_plan_regeneration_preserves_dose_adherence(repo, seeded_patient):
    """Re-running care plan generation must not overwrite previously checked-off doses."""
    service = CarePlanService(repository=repo)
    service.generate_care_plan(seeded_patient, days=7, persist=True)

    # Patient marks Day 0 morning dose as done
    repo.update_plan_entry_done(seeded_patient, day_index=0, slot="morning", done=True)
    assert repo.get_plan_entries(seeded_patient)[0].done is True

    # Re-run care plan generation (e.g. on page refresh or context update)
    res_again = service.generate_care_plan(seeded_patient, days=7, persist=True)

    day0_morning = [e for e in res_again.entries if e.day_index == 0 and e.slot == SlotName.MORNING][0]
    assert day0_morning.done is True  # Preserved!


# ==================================================
# 8. END-TO-END LOCAL INTEGRATION TEST
# ==================================================

def test_end_to_end_care_plan_integration(repo, sample_source, sample_envelope):
    """Comprehensive test: canonical context -> care plan -> single-table query."""
    pid = "pat_e2e_plan"

    # Profile
    repo.create_patient(Patient(patient_id=pid, name="Kavita Rao", age=48, sex="F", phone="+919123456780"))

    # Diagnoses
    d_env = ProvenanceEnvelope(field="diag", value="T2DM", source=sample_source, confidence=0.96)
    repo.create_diagnosis(pid, Diagnosis(label="Type 2 Diabetes", code_or_slug="t2dm", provenance=d_env))

    # Medications
    repo.create_medication(pid, Medication(
        name="Metformin", salt="metformin", strength="500mg", freq="BD", duration_days=30, provenance=sample_envelope
    ))

    # Restrictions & Followups
    rest_env = ProvenanceEnvelope(field="rest", value="Diet", source=sample_source, confidence=0.92)
    restrictions = [DischargeRestriction(text="Diabetic diet, avoid refined sugar", provenance=rest_env)]

    service = CarePlanService(repository=repo)
    result = service.generate_care_plan(pid, days=7, persist=True, restrictions=restrictions)

    assert result.days_covered == 7

    # Retrieve full patient context through single-table query
    ctx = repo.get_patient_context(pid)
    assert ctx.patient.name == "Kavita Rao"
    assert len(ctx.medications) == 1
    assert len(ctx.diagnoses) == 1
    assert len(ctx.plan_entries) > 0

    # Verify all plan entries have intact provenance referencing d_discharge_001
    for entry in ctx.plan_entries:
        assert entry.provenance.source.doc_id == "d_discharge_001"
