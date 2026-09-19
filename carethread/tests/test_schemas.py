"""Unit tests for CareThread shared data contracts and provenance layer.

Verifies:
1. Valid entity instantiation (Patient, Document, Medication, LabResult, Diagnosis, PlanEntry, AlertRule, Provenance, ExtractionResult)
2. Provenance invariant enforcement (rejection of missing or malformed provenance)
3. Confidence threshold semantics (>= 0.85 -> confirmed, < 0.85 -> needs_review)
4. Failure modes (invalid bbox, invalid confidence bounds, missing required fields, unsupported document types)
5. API contract schemas
6. JSON Schema validation
"""

import json
import os
import pytest
from pydantic import ValidationError
import jsonschema

from carethread.shared.schemas.provenance import (
    CONFIDENCE_THRESHOLD,
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
    evaluate_confidence,
)
from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType
from carethread.shared.schemas.medication import Medication, MedicationValue
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.plan_entry import PlanEntry, SlotName
from carethread.shared.schemas.alert_rule import AlertRule, AlertSeverity, FiredAlert
from carethread.shared.schemas.extraction import (
    DischargeFollowup,
    DischargeRestriction,
    DischargeSummaryExtraction,
    ExtractionResult,
    MedicineStripExtraction,
)
from carethread.shared.schemas.api import (
    DocumentCreateRequest,
    DocumentCreateResponse,
    DocumentStatusResponse,
    PatientRecordResponse,
    RecordFieldPatchRequest,
    RecordFieldPatchResponse,
    DrugAlternative,
    SubstitutionRequest,
    SubstitutionResponse,
    PlanDoneResponse,
)


# --- Helper Fixtures ---
@pytest.fixture
def valid_source():
    return ProvenanceSource(
        doc_id="doc_test_001",
        page=1,
        bbox=[120.0, 340.0, 480.0, 362.0],
        verbatim="Tab. Metformin 500mg BD x 30 days"
    )


@pytest.fixture
def valid_envelope(valid_source):
    return ProvenanceEnvelope(
        field="medication",
        value={"name": "Metformin", "strength": "500mg"},
        source=valid_source,
        confidence=0.92
    )


# ==================================================
# 1. PROVENANCE & CONFIDENCE TESTS
# ==================================================

def test_valid_provenance(valid_source):
    """Test valid provenance source and envelope."""
    envelope = ProvenanceEnvelope(
        field="medication",
        value={"name": "Metformin"},
        source=valid_source,
        confidence=0.91
    )
    assert envelope.field == "medication"
    assert envelope.source.doc_id == "doc_test_001"
    assert envelope.source.page == 1
    assert envelope.source.bbox == [120.0, 340.0, 480.0, 362.0]
    assert envelope.confidence == 0.91
    # Auto-gated to confirmed because 0.91 >= 0.85
    assert envelope.status == ProvenanceStatus.CONFIRMED


def test_confidence_threshold_semantics():
    """Verify the non-negotiable 0.85 confidence gate."""
    # Boundary: exactly 0.85 -> confirmed
    assert evaluate_confidence(0.85) == ProvenanceStatus.CONFIRMED
    assert evaluate_confidence(0.99) == ProvenanceStatus.CONFIRMED
    assert evaluate_confidence(1.0) == ProvenanceStatus.CONFIRMED

    # Boundary: just below 0.85 -> needs_review
    assert evaluate_confidence(0.8499) == ProvenanceStatus.NEEDS_REVIEW
    assert evaluate_confidence(0.70) == ProvenanceStatus.NEEDS_REVIEW
    assert evaluate_confidence(0.0) == ProvenanceStatus.NEEDS_REVIEW


def test_envelope_confidence_auto_gating(valid_source):
    """Verify ProvenanceEnvelope automatically sets status based on confidence."""
    # High confidence -> confirmed
    high_conf = ProvenanceEnvelope(
        field="diagnosis",
        value="Hypertension",
        source=valid_source,
        confidence=0.88
    )
    assert high_conf.status == ProvenanceStatus.CONFIRMED

    # Low confidence -> needs_review
    low_conf = ProvenanceEnvelope(
        field="diagnosis",
        value="Hypertension",
        source=valid_source,
        confidence=0.82
    )
    assert low_conf.status == ProvenanceStatus.NEEDS_REVIEW


def test_invalid_confidence_bounds(valid_source):
    """Confidence must be between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        ProvenanceEnvelope(
            field="medication",
            value={},
            source=valid_source,
            confidence=1.05
        )

    with pytest.raises(ValidationError):
        ProvenanceEnvelope(
            field="medication",
            value={},
            source=valid_source,
            confidence=-0.1
        )


def test_malformed_provenance_bbox():
    """Bbox must contain exactly 4 coordinates in range 0-1000 with ymin<=ymax, xmin<=xmax."""
    # Length != 4
    with pytest.raises(ValidationError):
        ProvenanceSource(doc_id="d1", page=1, bbox=[100.0, 200.0, 300.0], verbatim="text")

    # Coordinate > 1000
    with pytest.raises(ValidationError):
        ProvenanceSource(doc_id="d1", page=1, bbox=[0.0, 0.0, 1005.0, 500.0], verbatim="text")

    # ymin > ymax
    with pytest.raises(ValidationError):
        ProvenanceSource(doc_id="d1", page=1, bbox=[500.0, 100.0, 400.0, 200.0], verbatim="text")

    # xmin > xmax
    with pytest.raises(ValidationError):
        ProvenanceSource(doc_id="d1", page=1, bbox=[100.0, 600.0, 200.0, 500.0], verbatim="text")


def test_malformed_provenance_page():
    """Page number must be >= 1."""
    with pytest.raises(ValidationError):
        ProvenanceSource(doc_id="d1", page=0, bbox=[0.0, 0.0, 100.0, 100.0], verbatim="text")


def test_empty_verbatim_or_doc_id():
    """Verbatim text and doc_id cannot be empty."""
    with pytest.raises(ValidationError):
        ProvenanceSource(doc_id="", page=1, bbox=[0.0, 0.0, 100.0, 100.0], verbatim="text")

    with pytest.raises(ValidationError):
        ProvenanceSource(doc_id="d1", page=1, bbox=[0.0, 0.0, 100.0, 100.0], verbatim="")


# ==================================================
# 2. SHARED ENTITIES TESTS
# ==================================================

def test_valid_patient():
    """Test valid Patient entity."""
    patient = Patient(
        patient_id="pat_001",
        name="Sunita Sharma",
        age=58,
        sex="F",
        language="hi",
        phone="+919876543210",
        created_at="2026-09-19T10:00:00Z"
    )
    assert patient.pk == "PATIENT#pat_001"
    assert patient.sk == "PROFILE"
    assert patient.name == "Sunita Sharma"


def test_invalid_patient():
    """Patient must have valid required fields."""
    with pytest.raises(ValidationError):
        Patient(patient_id="", name="", age=-5, sex="F", phone="")


def test_valid_document():
    """Test valid Document entity."""
    doc = Document(
        patient_id="pat_001",
        doc_id="d_014",
        type=DocumentType.DISCHARGE_SUMMARY,
        s3_key="raw/pat_001/d_014.pdf",
        status=DocumentStatus.UPLOADING,
        pages=3,
        created_at="2026-09-19T10:00:00Z",
        updated_at="2026-09-19T10:00:00Z"
    )
    assert doc.pk == "PATIENT#pat_001"
    assert doc.sk == "DOC#2026-09-19T10:00:00Z#d_014"
    assert doc.type == DocumentType.DISCHARGE_SUMMARY


def test_invalid_document_type():
    """Document type must be one of the supported enum values."""
    with pytest.raises(ValidationError):
        Document(
            patient_id="pat_001",
            doc_id="d_014",
            type="invalid_doc_type",
            s3_key="raw/d_014.pdf",
            status=DocumentStatus.UPLOADING,
            created_at="2026-09-19T10:00:00Z",
            updated_at="2026-09-19T10:00:00Z"
        )


def test_valid_medication(valid_envelope):
    """Test valid Medication entity with mandatory provenance."""
    med = Medication(
        name="Metformin",
        salt="metformin hydrochloride",
        strength="500mg",
        form="tablet",
        freq="BD",
        duration_days=30,
        instructions="Take after food",
        provenance=valid_envelope
    )
    assert med.pk("pat_001") == "PATIENT#pat_001"
    assert med.sk == "MED#metformin"
    assert med.salt == "metformin hydrochloride"
    assert med.provenance.status == ProvenanceStatus.CONFIRMED


def test_medication_missing_provenance():
    """Medication without provenance must fail validation."""
    with pytest.raises(ValidationError):
        Medication(
            name="Metformin",
            salt="metformin hydrochloride",
            strength="500mg",
            freq="BD",
            duration_days=30
        )


def test_valid_lab_result(valid_source):
    """Test valid LabResult with mandatory provenance and deviation score."""
    envelope = ProvenanceEnvelope(
        field="lab_result",
        value={"analyte": "Serum Creatinine", "value": 1.9},
        source=valid_source,
        confidence=0.95
    )
    lab = LabResult(
        analyte="Serum Creatinine",
        value=1.9,
        unit="mg/dL",
        ref_low=0.7,
        ref_high=1.3,
        ref_source="printed",
        deviation_score=1.83,
        flag="high",
        provenance=envelope
    )
    assert lab.pk("pat_001") == "PATIENT#pat_001"
    assert lab.sk("2026-09-19T10:00:00Z") == "LAB#2026-09-19T10:00:00Z#serum_creatinine"
    assert lab.flag == "high"


def test_lab_result_missing_provenance():
    """LabResult without provenance must fail validation."""
    with pytest.raises(ValidationError):
        LabResult(
            analyte="Serum Creatinine",
            value=1.9,
            unit="mg/dL"
        )


def test_valid_diagnosis(valid_source):
    """Test valid Diagnosis with mandatory provenance."""
    envelope = ProvenanceEnvelope(
        field="diagnosis",
        value="Type 2 Diabetes",
        source=valid_source,
        confidence=0.89
    )
    diag = Diagnosis(
        label="Type 2 Diabetes Mellitus",
        code_or_slug="t2dm",
        icd_hint="E11",
        status="active",
        provenance=envelope
    )
    assert diag.pk("pat_001") == "PATIENT#pat_001"
    assert diag.sk == "DIAG#t2dm"


def test_diagnosis_missing_provenance():
    """Diagnosis without provenance must fail validation."""
    with pytest.raises(ValidationError):
        Diagnosis(label="Type 2 Diabetes Mellitus")


def test_valid_plan_entry(valid_source):
    """Test valid PlanEntry with mandatory provenance."""
    envelope = ProvenanceEnvelope(
        field="plan_entry",
        value="Take Metformin",
        source=valid_source,
        confidence=0.91
    )
    entry = PlanEntry(
        day_index=0,
        slot=SlotName.MORNING,
        action="Take Tab Metformin 500mg",
        med_ref="MED#metformin",
        time_target="08:00",
        done=False,
        provenance=envelope
    )
    assert entry.pk("pat_001") == "PATIENT#pat_001"
    assert entry.sk == "PLAN#0#morning"
    assert entry.slot == SlotName.MORNING


def test_plan_entry_invalid_day_index(valid_envelope):
    """Day index must be between 0 and 6."""
    with pytest.raises(ValidationError):
        PlanEntry(
            day_index=7,  # Invalid: > 6
            slot=SlotName.MORNING,
            action="Take Tab Metformin 500mg",
            med_ref="MED#metformin",
            provenance=valid_envelope
        )


def test_valid_alert_rule():
    """Test AlertRule and FiredAlert models."""
    rule = AlertRule(
        id="fever_persistent",
        when="symptom.fever_f > 101 for 48h",
        severity=AlertSeverity.HIGH,
        message="Return to the hospital or call your doctor."
    )
    assert rule.id == "fever_persistent"
    assert rule.severity == AlertSeverity.HIGH

    fired = FiredAlert(
        alert_id="alt_001",
        rule_id="fever_persistent",
        severity=AlertSeverity.HIGH,
        message="Return to the hospital or call your doctor.",
        fired_at="2026-09-19T10:30:00Z"
    )
    assert fired.pk("pat_001") == "PATIENT#pat_001"
    assert fired.sk == "ALERT#2026-09-19T10:30:00Z"


def test_valid_extraction_result(valid_source):
    """Test ExtractionResult container with confidence gating detection."""
    env_confirmed = ProvenanceEnvelope(
        field="medication",
        value={"name": "Amlodipine"},
        source=valid_source,
        confidence=0.90
    )
    med_confirmed = Medication(
        name="Amlodipine",
        salt="amlodipine besylate",
        strength="5mg",
        freq="OD",
        duration_days=30,
        provenance=env_confirmed
    )

    result_ready = ExtractionResult(
        doc_id="d_014",
        document_type=DocumentType.DISCHARGE_SUMMARY,
        confidence=0.92,
        status=DocumentStatus.READY,
        medications=[med_confirmed]
    )
    assert not result_ready.has_unreviewed_entities()

    # Now add an entity with confidence < 0.85
    env_review = ProvenanceEnvelope(
        field="medication",
        value={"name": "Atorvastatin"},
        source=valid_source,
        confidence=0.81
    )
    med_review = Medication(
        name="Atorvastatin",
        salt="atorvastatin calcium",
        strength="10mg",
        freq="HS",
        duration_days=30,
        provenance=env_review
    )
    result_needs_review = ExtractionResult(
        doc_id="d_014",
        document_type=DocumentType.DISCHARGE_SUMMARY,
        confidence=0.88,
        status=DocumentStatus.REVIEW_REQUIRED,
        medications=[med_confirmed, med_review]
    )
    assert result_needs_review.has_unreviewed_entities()


# ==================================================
# 3. API CONTRACT TESTS
# ==================================================

def test_document_api_contracts():
    """Verify document creation and status API contracts."""
    req = DocumentCreateRequest(filename="discharge.pdf", content_type="application/pdf")
    assert req.filename == "discharge.pdf"

    res = DocumentCreateResponse(doc_id="d_001", upload_url="https://s3.amazonaws.com/...")
    assert res.doc_id == "d_001"

    status_res = DocumentStatusResponse(
        doc_id="d_001",
        status=DocumentStatus.EXTRACTING,
        type=DocumentType.DISCHARGE_SUMMARY,
        pages=["pages/pat_001/d_001/p1.png"]
    )
    assert status_res.status == DocumentStatus.EXTRACTING


def test_substitution_request_validation():
    """Substitution check requires either doc_id or (brand and strength)."""
    # Valid with doc_id
    req1 = SubstitutionRequest(doc_id="strip_01")
    assert req1.doc_id == "strip_01"

    # Valid with brand + strength
    req2 = SubstitutionRequest(brand="Glycomet", strength="500mg")
    assert req2.brand == "Glycomet"

    # Invalid: neither provided
    with pytest.raises(ValidationError):
        SubstitutionRequest()

    # Invalid: brand only without strength
    with pytest.raises(ValidationError):
        SubstitutionRequest(brand="Glycomet")


def test_substitution_response_nti_block():
    """Verify substitution contract representing NTI hard block."""
    res = SubstitutionResponse(
        blocked=True,
        reason="Warfarin has a narrow therapeutic index. Do not substitute, contact the prescriber.",
        alternatives=[],
        interactions=[]
    )
    assert res.blocked is True
    assert "narrow therapeutic index" in res.reason


def test_plan_done_contract():
    """Verify plan dose adherence completion contract."""
    res = PlanDoneResponse(
        day=0,
        slot=SlotName.MORNING,
        done=True,
        completed_at="2026-09-19T08:15:00Z"
    )
    assert res.day == 0
    assert res.slot == SlotName.MORNING
    assert res.done is True


# ==================================================
# 4. JSON SCHEMA VALIDATION TESTS
# ==================================================

def test_json_schemas_against_draft07():
    """Verify draft-07 JSON schemas in shared/schemas/ parse and validate payloads."""
    schema_dir = os.path.join(os.path.dirname(__file__), "..", "shared", "schemas")
    
    # Test provenance.json
    prov_path = os.path.join(schema_dir, "provenance.json")
    with open(prov_path, "r", encoding="utf-8") as fp:
        prov_schema = json.load(fp)
    
    valid_prov_payload = {
        "field": "medication",
        "value": {"name": "Metformin"},
        "source": {
            "doc_id": "d_014",
            "page": 1,
            "bbox": [120, 340, 480, 362],
            "verbatim": "Tab. Metformin 500mg BD x 30 days"
        },
        "confidence": 0.91,
        "status": "confirmed"
    }
    jsonschema.validate(instance=valid_prov_payload, schema=prov_schema)

    # Test patient.json
    patient_path = os.path.join(schema_dir, "patient.json")
    with open(patient_path, "r", encoding="utf-8") as fp:
        patient_schema = json.load(fp)

    valid_patient_payload = {
        "patient_id": "pat_123",
        "name": "Ramesh Kumar",
        "age": 62,
        "sex": "M",
        "phone": "+919876543210"
    }
    jsonschema.validate(instance=valid_patient_payload, schema=patient_schema)
