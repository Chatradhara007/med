"""Unit tests for CareThread single-table repository layer.

Verifies:
1. All 16 CRUD operations on Patient, Document, Medication, LabResult, Diagnosis, PlanEntry, Alert
2. The canonical single-partition query get_patient_context()
3. Provenance validation invariant (rejection of unprovenanced clinical entities)
4. Cross-patient data isolation (PATIENT#A vs PATIENT#B)
5. Exact DynamoDB PK/SK key pattern generation
6. Targeted plan completion update
7. Both InMemoryPatientRepository and DynamoDBPatientRepository (via mock Table resource)
"""

from datetime import datetime, timezone
import pytest
from botocore.exceptions import ClientError

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.plan_entry import PlanEntry, SlotName
from carethread.shared.schemas.alert_rule import AlertSeverity, FiredAlert
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.repository.dynamodb import DynamoDBPatientRepository
from carethread.shared.repository.exceptions import (
    MissingProvenanceError,
    PatientNotFoundError,
    EntityNotFoundError,
    InvalidPatientIdError,
)


# --- Mock DynamoDB Table for testing DynamoDBPatientRepository without AWS ---
class MockDynamoDBTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        pk = Item["PK"]
        sk = Item["SK"]
        self.items[(pk, sk)] = dict(Item)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_item(self, Key):
        pk = Key["PK"]
        sk = Key["SK"]
        item = self.items.get((pk, sk))
        if item:
            return {"Item": dict(item)}
        return {}

    def _matches_condition(self, item, cond):
        if hasattr(cond, "get_expression"):
            expr = cond.get_expression()
            op = expr.get("operator")
            vals = expr.get("values", ())
            if op == "=":
                return item.get(vals[0].name) == vals[1]
            elif op == "begins_with":
                val = item.get(vals[0].name, "")
                return isinstance(val, str) and val.startswith(vals[1])
            elif op == "AND":
                return self._matches_condition(item, vals[0]) and self._matches_condition(item, vals[1])
        return True

    def query(self, KeyConditionExpression):
        results = []
        for item in self.items.values():
            if self._matches_condition(item, KeyConditionExpression):
                results.append(dict(item))
        return {"Items": results}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues, ConditionExpression=None, ReturnValues="NONE"):
        pk = Key["PK"]
        sk = Key["SK"]
        if (pk, sk) not in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "The conditional request failed"}},
                "UpdateItem"
            )
        item = self.items[(pk, sk)]
        if ":done" in ExpressionAttributeValues:
            item["done"] = ExpressionAttributeValues[":done"]
        if ":completed_at" in ExpressionAttributeValues:
            item["completed_at"] = ExpressionAttributeValues[":completed_at"]
        return {"Attributes": dict(item)}


@pytest.fixture(params=["in_memory", "dynamodb_mock"])
def repo(request):
    """Parametrized fixture providing both InMemoryPatientRepository and DynamoDBPatientRepository."""
    if request.param == "in_memory":
        return InMemoryPatientRepository()
    else:
        mock_table = MockDynamoDBTable()
        return DynamoDBPatientRepository(table_resource=mock_table)


@pytest.fixture
def sample_source():
    return ProvenanceSource(
        doc_id="d_014",
        page=1,
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


# ==================================================
# 1. INDIVIDUAL CRUD TESTS
# ==================================================

def test_create_and_get_patient(repo):
    patient = Patient(
        patient_id="pat_001",
        name="Sunita Sharma",
        age=58,
        sex="F",
        language="hi",
        phone="+919876543210"
    )
    repo.create_patient(patient)
    fetched = repo.get_patient("pat_001")
    assert fetched is not None
    assert fetched.name == "Sunita Sharma"
    assert fetched.age == 58


def test_update_patient(repo):
    patient = Patient(
        patient_id="pat_001",
        name="Sunita Sharma",
        age=58,
        sex="F",
        phone="+919876543210"
    )
    repo.create_patient(patient)
    patient.age = 59
    repo.update_patient(patient)
    updated = repo.get_patient("pat_001")
    assert updated.age == 59


def test_update_nonexistent_patient_raises(repo):
    patient = Patient(
        patient_id="pat_ghost",
        name="Ghost",
        age=40,
        sex="M",
        phone="+910000000000"
    )
    with pytest.raises(PatientNotFoundError):
        repo.update_patient(patient)


def test_create_and_get_document(repo):
    doc = Document(
        patient_id="pat_001",
        doc_id="d_001",
        type=DocumentType.DISCHARGE_SUMMARY,
        s3_key="raw/pat_001/d_001.pdf",
        status=DocumentStatus.READY,
        pages=2,
        created_at="2026-09-19T10:00:00Z",
        updated_at="2026-09-19T10:02:00Z"
    )
    repo.create_document(doc)
    fetched = repo.get_document("pat_001", "d_001")
    assert fetched is not None
    assert fetched.doc_id == "d_001"
    assert fetched.type == DocumentType.DISCHARGE_SUMMARY
    assert fetched.status == DocumentStatus.READY


def test_create_and_get_medication(repo, sample_envelope):
    med = Medication(
        name="Metformin",
        salt="metformin hydrochloride",
        strength="500mg",
        freq="BD",
        duration_days=30,
        instructions="Take after food",
        provenance=sample_envelope
    )
    repo.create_medication("pat_001", med)
    meds = repo.get_medications("pat_001")
    assert len(meds) == 1
    assert meds[0].name == "Metformin"
    assert meds[0].provenance.source.doc_id == "d_014"


def test_create_and_get_lab_result(repo, sample_source):
    env = ProvenanceEnvelope(
        field="lab_result",
        value={"analyte": "Serum Creatinine", "value": 1.83},
        source=sample_source,
        confidence=0.95
    )
    lab = LabResult(
        analyte="Serum Creatinine",
        value=1.83,
        unit="mg/dL",
        ref_low=0.7,
        ref_high=1.3,
        ref_source="printed",
        deviation_score=1.83,
        flag="high",
        provenance=env
    )
    repo.create_lab_result("pat_001", lab, timestamp="2026-09-19T11:00:00Z")
    labs = repo.get_lab_results("pat_001")
    assert len(labs) == 1
    assert labs[0].analyte == "Serum Creatinine"
    assert labs[0].value == 1.83


def test_create_and_get_diagnosis(repo, sample_source):
    env = ProvenanceEnvelope(
        field="diagnosis",
        value="Hypertension",
        source=sample_source,
        confidence=0.88
    )
    diag = Diagnosis(
        label="Essential Hypertension",
        code_or_slug="hypertension",
        icd_hint="I10",
        provenance=env
    )
    repo.create_diagnosis("pat_001", diag)
    diags = repo.get_diagnoses("pat_001")
    assert len(diags) == 1
    assert diags[0].label == "Essential Hypertension"


def test_create_and_get_plan_entry(repo, sample_envelope):
    entry = PlanEntry(
        day_index=0,
        slot=SlotName.MORNING,
        action="Take Tab Metformin 500mg",
        med_ref="MED#metformin",
        time_target="08:00",
        done=False,
        provenance=sample_envelope
    )
    repo.create_plan_entry("pat_001", entry)
    entries = repo.get_plan_entries("pat_001")
    assert len(entries) == 1
    assert entries[0].day_index == 0
    assert entries[0].slot == SlotName.MORNING
    assert entries[0].done is False


def test_update_plan_entry_done(repo, sample_envelope):
    entry = PlanEntry(
        day_index=0,
        slot=SlotName.MORNING,
        action="Take Tab Metformin 500mg",
        med_ref="MED#metformin",
        done=False,
        provenance=sample_envelope
    )
    repo.create_plan_entry("pat_001", entry)
    
    updated = repo.update_plan_entry_done(
        patient_id="pat_001",
        day_index=0,
        slot="morning",
        done=True,
        completed_at="2026-09-19T08:15:00Z"
    )
    assert updated.done is True
    assert updated.completed_at == "2026-09-19T08:15:00Z"


def test_update_nonexistent_plan_entry_raises(repo):
    with pytest.raises(EntityNotFoundError):
        repo.update_plan_entry_done(
            patient_id="pat_001",
            day_index=0,
            slot="night",
            done=True
        )


def test_create_and_get_alert(repo):
    alert = FiredAlert(
        alert_id="alt_001",
        rule_id="fever_persistent",
        severity=AlertSeverity.HIGH,
        message="Return to hospital or call doctor.",
        fired_at="2026-09-19T12:00:00Z"
    )
    repo.create_alert("pat_001", alert)
    alerts = repo.get_alerts("pat_001")
    assert len(alerts) == 1
    assert alerts[0].rule_id == "fever_persistent"


# ==================================================
# 2. CANONICAL PATIENT CONTEXT QUERY TEST
# ==================================================

def test_get_patient_context(repo, sample_source, sample_envelope):
    """Test the single-partition query returning the full episodic record."""
    pid = "pat_full_001"

    # Profile
    repo.create_patient(Patient(
        patient_id=pid, name="Anil Verma", age=64, sex="M", phone="+919876543210"
    ))

    # Documents
    repo.create_document(Document(
        patient_id=pid, doc_id="d_01", type=DocumentType.DISCHARGE_SUMMARY,
        s3_key="raw/pat/d_01.pdf", status=DocumentStatus.READY, pages=3,
        created_at="2026-09-19T10:00:00Z", updated_at="2026-09-19T10:02:00Z"
    ))
    repo.create_document(Document(
        patient_id=pid, doc_id="d_02", type=DocumentType.LAB_REPORT,
        s3_key="raw/pat/d_02.pdf", status=DocumentStatus.READY, pages=1,
        created_at="2026-09-19T11:00:00Z", updated_at="2026-09-19T11:01:00Z"
    ))

    # Medication
    repo.create_medication(pid, Medication(
        name="Metformin", salt="metformin hydrochloride", strength="500mg",
        freq="BD", duration_days=30, provenance=sample_envelope
    ))

    # Diagnosis
    diag_env = ProvenanceEnvelope(
        field="diagnosis", value="Type 2 Diabetes", source=sample_source, confidence=0.91
    )
    repo.create_diagnosis(pid, Diagnosis(
        label="Type 2 Diabetes Mellitus", code_or_slug="t2dm", provenance=diag_env
    ))

    # Lab
    lab_env = ProvenanceEnvelope(
        field="lab_result", value={"analyte": "FBS", "value": 142}, source=sample_source, confidence=0.93
    )
    repo.create_lab_result(pid, LabResult(
        analyte="Fasting Blood Sugar", value=142, unit="mg/dL",
        ref_low=70, ref_high=100, provenance=lab_env
    ), timestamp="2026-09-19T11:00:00Z")

    # Plan
    repo.create_plan_entry(pid, PlanEntry(
        day_index=0, slot=SlotName.MORNING, action="Take Metformin",
        med_ref="MED#metformin", done=False, provenance=sample_envelope
    ))

    # Alert
    repo.create_alert(pid, FiredAlert(
        alert_id="alt_01", rule_id="post_cardiac_chest_pain",
        severity=AlertSeverity.CRITICAL, message="Call emergency services now.",
        fired_at="2026-09-19T12:00:00Z"
    ))

    # Execute single partition query
    ctx = repo.get_patient_context(pid)

    assert ctx.patient is not None
    assert ctx.patient.name == "Anil Verma"
    assert len(ctx.documents) == 2
    assert len(ctx.medications) == 1
    assert len(ctx.diagnoses) == 1
    assert len(ctx.lab_results) == 1
    assert len(ctx.plan_entries) == 1
    assert len(ctx.alerts) == 1

    # Verify provenance preserved on returned context
    assert ctx.medications[0].provenance.source.doc_id == "d_014"
    assert ctx.diagnoses[0].provenance.source.verbatim == sample_source.verbatim


# ==================================================
# 3. PROVENANCE INTEGRITY & REJECTION TESTS
# ==================================================

def test_missing_provenance_rejected(repo):
    """Clinical entity missing provenance must fail validation and be rejected."""
    class FakeUnprovenancedMedication:
        name = "Aspirin"
        provenance = None

    with pytest.raises(MissingProvenanceError):
        repo.create_medication("pat_001", FakeUnprovenancedMedication())


# ==================================================
# 4. CROSS-PATIENT DATA ISOLATION TEST
# ==================================================

def test_cross_patient_isolation(repo, sample_envelope):
    """Ensure PATIENT#A context never leaks into PATIENT#B."""
    p_a = "pat_A"
    p_b = "pat_B"

    repo.create_patient(Patient(patient_id=p_a, name="Patient A", age=30, sex="F", phone="111"))
    repo.create_patient(Patient(patient_id=p_b, name="Patient B", age=40, sex="M", phone="222"))

    repo.create_medication(p_a, Medication(
        name="DrugA", salt="SaltA", strength="10mg", freq="OD", duration_days=5, provenance=sample_envelope
    ))
    repo.create_medication(p_b, Medication(
        name="DrugB", salt="SaltB", strength="20mg", freq="BD", duration_days=10, provenance=sample_envelope
    ))

    ctx_a = repo.get_patient_context(p_a)
    ctx_b = repo.get_patient_context(p_b)

    assert ctx_a.patient.name == "Patient A"
    assert len(ctx_a.medications) == 1
    assert ctx_a.medications[0].name == "DrugA"

    assert ctx_b.patient.name == "Patient B"
    assert len(ctx_b.medications) == 1
    assert ctx_b.medications[0].name == "DrugB"


# ==================================================
# 5. DYNAMODB KEY STRUCTURE TESTS
# ==================================================

def test_documented_key_patterns():
    """Verify exact sort key patterns specified in Section 4.1."""
    # PROFILE
    patient = Patient(patient_id="123", name="Test", age=50, sex="M", phone="123")
    assert patient.pk == "PATIENT#123"
    assert patient.sk == "PROFILE"

    # DOC#<iso_ts>#<doc_id>
    doc = Document(
        patient_id="123", doc_id="d_014", type=DocumentType.DISCHARGE_SUMMARY,
        s3_key="raw/123/d_014.pdf", status=DocumentStatus.READY,
        created_at="2026-09-19T10:00:00Z", updated_at="2026-09-19T10:00:00Z"
    )
    assert doc.pk == "PATIENT#123"
    assert doc.sk == "DOC#2026-09-19T10:00:00Z#d_014"

    # MED#<normalised_name>
    source = ProvenanceSource(doc_id="d_014", page=1, bbox=[0, 0, 100, 100], verbatim="text")
    env = ProvenanceEnvelope(field="med", value={}, source=source, confidence=0.9)
    med = Medication(name="Metformin HCl", salt="salt", strength="500mg", freq="BD", duration_days=30, provenance=env)
    assert med.pk("123") == "PATIENT#123"
    assert med.sk == "MED#metformin_hcl"

    # LAB#<iso_ts>#<analyte>
    lab = LabResult(analyte="Serum Creatinine", value=1.2, unit="mg/dL", provenance=env)
    assert lab.pk("123") == "PATIENT#123"
    assert lab.sk_for("2026-09-19T10:00:00Z") == "LAB#2026-09-19T10:00:00Z#serum_creatinine"

    # DIAG#<code_or_slug>
    diag = Diagnosis(label="Myocardial Infarction", code_or_slug="mi", provenance=env)
    assert diag.pk("123") == "PATIENT#123"
    assert diag.sk == "DIAG#mi"

    # PLAN#<day_index>#<slot>
    plan = PlanEntry(day_index=2, slot=SlotName.EVENING, action="Take Tab", med_ref="MED#metformin", provenance=env)
    assert plan.pk("123") == "PATIENT#123"
    assert plan.sk == "PLAN#2#evening"

    # ALERT#<iso_ts>
    alert = FiredAlert(alert_id="a1", rule_id="r1", severity=AlertSeverity.HIGH, message="msg", fired_at="2026-09-19T12:00:00Z")
    assert alert.pk("123") == "PATIENT#123"
    assert alert.sk == "ALERT#2026-09-19T12:00:00Z"
