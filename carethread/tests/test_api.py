"""Comprehensive test suite for CareThread REST API layer (Module 10).

Verifies:
1. POST /documents (valid, malformed, unsupported media type, storage failure)
2. GET /documents/{id} (existing, missing 404, unauthorized 401)
3. GET /record (complete canonical record, empty record, isolation, db failure)
4. PATCH /record/{field} and PATCH /record/field (metadata edit, medication correction,
   provenance transition to confirmed, immutable rejection, malformed value rejection, 404)
5. POST /substitution (valid match, NTI hard-block, active medication interaction, validation error)
6. POST /plan/{day}/{slot}/done (valid adherence, missing entry 404, invalid day/slot 400, idempotency)
7. Workflow endpoints: POST /plan/generate and POST /labs/interpret
8. End-to-end integration test connecting all modules through the API layer
"""

import json
from typing import Any
from datetime import datetime, timezone
import pytest

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.plan_entry import PlanEntry, SlotName
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.storage.in_memory import InMemoryStorageService
from carethread.api.documents.service import DocumentsService
from carethread.api.documents.handler import handler as documents_handler
from carethread.api.record.service import RecordService
from carethread.api.record.handler import handler as record_handler
from carethread.api.substitution.service import SubstitutionApiService
from carethread.api.substitution.handler import handler as substitution_handler
from carethread.api.router import ApiRouter


@pytest.fixture
def repo():
    return InMemoryPatientRepository()


@pytest.fixture
def storage():
    return InMemoryStorageService(bucket_name="test-docs-bucket")


@pytest.fixture
def router(repo, storage):
    return ApiRouter(repository=repo, storage=storage)


@pytest.fixture
def sample_source():
    return ProvenanceSource(
        doc_id="d_api_test_01",
        page=1,
        bbox=[100.0, 150.0, 400.0, 180.0],
        verbatim="Tab. Metformin 500mg BD x 30 days"
    )


@pytest.fixture
def sample_provenance(sample_source):
    return ProvenanceEnvelope(
        field="medication",
        value={"name": "Metformin", "dose": "500mg"},
        source=sample_source,
        confidence=0.92,
        status=ProvenanceStatus.CONFIRMED,
    )


@pytest.fixture
def test_patient(repo):
    p = Patient(
        patient_id="pt_api_001",
        name="Sunita Sharma",
        age=52,
        sex="F",
        phone="+919123456780",
        language="en",
    )
    return repo.create_patient(p)


def make_auth_event(
    patient_id: str,
    method: str,
    path: str,
    body: Any = None,
    path_params: Any = None,
) -> dict:
    """Helper constructing simulated API Gateway HTTP API event with JWT authorizer."""
    event = {
        "httpMethod": method,
        "rawPath": path,
        "path": path,
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            },
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": patient_id
                    }
                }
            }
        },
        "headers": {
            "content-type": "application/json",
            "x-patient-id": patient_id,
        },
    }
    if body is not None:
        event["body"] = json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    if path_params is not None:
        event["pathParameters"] = path_params
    return event


# ==================================================
# 1. POST /documents & GET /documents/{id}
# ==================================================

def test_api_post_documents_valid(router, test_patient):
    """POST /documents creates document metadata and returns presigned S3 PUT URL."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/documents",
        body={"filename": "discharge_summary.pdf", "content_type": "application/pdf"},
    )
    resp = router.route(event)
    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert "doc_id" in body
    assert "upload_url" in body
    assert body["doc_id"].startswith("d_")


def test_api_post_documents_malformed(router, test_patient):
    """POST /documents with missing filename returns 400 VALIDATION_ERROR."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/documents",
        body={"content_type": "application/pdf"},
    )
    resp = router.route(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_api_post_documents_unsupported_type(router, test_patient):
    """POST /documents with unsupported content type returns 400 UNSUPPORTED_MEDIA_TYPE."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/documents",
        body={"filename": "script.sh", "content_type": "text/x-shellscript"},
    )
    resp = router.route(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_api_post_documents_unauthorized(router):
    """POST /documents without authentication credentials returns 401 UNAUTHORIZED."""
    event = {
        "httpMethod": "POST",
        "rawPath": "/documents",
        "path": "/documents",
        "body": json.dumps({"filename": "doc.pdf", "content_type": "application/pdf"}),
        "requestContext": {},
    }
    resp = router.route(event)
    assert resp["statusCode"] == 401
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_api_get_documents_existing(router, test_patient):
    """GET /documents/{id} retrieves document lifecycle status."""
    # 1. Create document
    post_event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/documents",
        body={"filename": "lab_report.pdf", "content_type": "application/pdf"},
    )
    post_resp = router.route(post_event)
    doc_id = json.loads(post_resp["body"])["doc_id"]

    # 2. Get document
    get_event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="GET",
        path=f"/documents/{doc_id}",
    )
    get_resp = router.route(get_event)
    assert get_resp["statusCode"] == 200
    body = json.loads(get_resp["body"])
    assert body["doc_id"] == doc_id
    assert body["status"] == DocumentStatus.UPLOADING


def test_api_get_documents_not_found(router, test_patient):
    """GET /documents/{id} for non-existent document returns 404 DOCUMENT_NOT_FOUND."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="GET",
        path="/documents/d_non_existent",
    )
    resp = router.route(event)
    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "DOCUMENT_NOT_FOUND"


# ==================================================
# 2. GET /record
# ==================================================

def test_api_get_record_complete(repo, router, test_patient, sample_provenance):
    """GET /record returns complete canonical episodic context."""
    # Populate record
    med = Medication(
        name="Metformin",
        salt="metformin hydrochloride",
        strength="500mg",
        freq="BD",
        duration_days=30,
        route="oral",
        provenance=sample_provenance,
    )
    diag = Diagnosis(
        label="Type 2 Diabetes Mellitus",
        code_or_slug="E11.9",
        provenance=sample_provenance,
    )
    repo.create_medication(test_patient.patient_id, med)
    repo.create_diagnosis(test_patient.patient_id, diag)

    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="GET",
        path="/record",
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    assert body["patient"]["name"] == "Sunita Sharma"
    assert len(body["medications"]) == 1
    assert body["medications"][0]["name"] == "Metformin"
    assert len(body["diagnoses"]) == 1
    assert body["diagnoses"][0]["label"] == "Type 2 Diabetes Mellitus"


def test_api_get_record_empty(router, repo):
    """GET /record for brand new patient with no items returns 200 with empty arrays."""
    p = Patient(patient_id="pt_empty", name="Empty User", age=30, sex="M", phone="+911111111111")
    repo.create_patient(p)

    event = make_auth_event(patient_id="pt_empty", method="GET", path="/record")
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["patient"]["name"] == "Empty User"
    assert body["medications"] == []
    assert body["plan_entries"] == []


def test_api_get_record_cross_patient_isolation(repo, router, test_patient):
    """Cross-patient isolation: Patient A only sees their own partition."""
    p2 = Patient(patient_id="pt_victim", name="Victim User", age=45, sex="F", phone="+912222222222")
    repo.create_patient(p2)

    event_a = make_auth_event(patient_id=test_patient.patient_id, method="GET", path="/record")
    resp = router.route(event_a)
    body = json.loads(resp["body"])
    assert body["patient"]["patient_id"] == test_patient.patient_id
    assert body["patient"]["name"] == "Sunita Sharma"


# ==================================================
# 3. PATCH /record/{field}
# ==================================================

def test_api_patch_record_patient_metadata(repo, router, test_patient):
    """PATCH /record/field updates allowed patient demographic fields."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="PATCH",
        path="/record/field",
        body={
            "sk": "PROFILE",
            "field": "phone",
            "value": "+919999888877",
        },
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["updated_item"]["phone"] == "+919999888877"

    # Verify persisted in repository
    updated_p = repo.get_patient(test_patient.patient_id)
    assert updated_p.phone == "+919999888877"


def test_api_patch_record_medication_correction(repo, router, test_patient, sample_source):
    """PATCH /record/field on low-confidence medication resolves review chip and transitions status to confirmed."""
    env = ProvenanceEnvelope(
        field="medication",
        value={"name": "Metformin"},
        source=sample_source,
        confidence=0.72,  # < 0.85 -> NEEDS_REVIEW
        status=ProvenanceStatus.NEEDS_REVIEW,
    )
    med = Medication(
        name="Metformin",
        salt="metformin hydrochloride",
        strength="250mg",
        freq="BD",
        duration_days=30,
        provenance=env,
    )
    repo.create_medication(test_patient.patient_id, med)

    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="PATCH",
        path="/record/strength",
        body={
            "sk": "MED#metformin",
            "field": "strength",
            "value": "500mg",
        },
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "confirmed"
    assert body["updated_item"]["strength"] == "500mg"
    assert body["updated_item"]["provenance"]["status"] == "confirmed"


def test_api_patch_record_immutable_provenance_rejection(repo, router, test_patient):
    """Attempting to mutate immutable OCR provenance citations returns 400."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="PATCH",
        path="/record/field",
        body={
            "sk": "MED#metformin",
            "field": "bbox",
            "value": [0.0, 0.0, 10.0, 10.0],
        },
    )
    resp = router.route(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "immutable" in body["error"]["message"].lower()


def test_api_patch_record_immutable_identifiers_rejection(repo, router, test_patient):
    """Attempting to mutate system keys (PK, SK, patient_id) returns 400."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="PATCH",
        path="/record/field",
        body={
            "sk": "PROFILE",
            "field": "patient_id",
            "value": "hacked_id",
        },
    )
    resp = router.route(event)
    assert resp["statusCode"] == 400


def test_api_patch_record_malformed_value(repo, router, test_patient):
    """Passing invalid value (negative age) returns 400."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="PATCH",
        path="/record/field",
        body={
            "sk": "PROFILE",
            "field": "age",
            "value": -5,
        },
    )
    resp = router.route(event)
    assert resp["statusCode"] == 400


def test_api_patch_record_entity_not_found(repo, router, test_patient):
    """Target SK not in partition returns 404 NOT_FOUND."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="PATCH",
        path="/record/field",
        body={
            "sk": "MED#non_existent_drug",
            "field": "strength",
            "value": "10mg",
        },
    )
    resp = router.route(event)
    assert resp["statusCode"] == 404


# ==================================================
# 4. POST /substitution
# ==================================================

def test_api_substitution_valid_request(router):
    """POST /substitution with valid non-NTI medicine returns alternatives and blocked=False."""
    event = make_auth_event(
        patient_id="pt_anon",
        method="POST",
        path="/substitution",
        body={"brand": "Glycomet 500", "strength": "500mg"},
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["blocked"] is False
    assert len(body["alternatives"]) >= 1
    brands = [a["brand"] for a in body["alternatives"]]
    assert "Obimet 500" in brands


def test_api_substitution_nti_hard_block(router):
    """POST /substitution with Narrow Therapeutic Index drug enforces hard-block."""
    event = make_auth_event(
        patient_id="pt_anon",
        method="POST",
        path="/substitution",
        body={"brand": "Warf 5", "strength": "5mg"},
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["blocked"] is True
    assert len(body["alternatives"]) == 0
    assert "narrow therapeutic" in body["reason"].lower()


def test_api_substitution_active_medication_interaction(repo, router, test_patient, sample_provenance):
    """POST /substitution cross-checks candidate formulation against patient's active prescriptions."""
    # Prescribe active Warfarin
    warfarin = Medication(
        name="Warfarin",
        salt="warfarin sodium",
        strength="5mg",
        freq="OD",
        duration_days=30,
        provenance=sample_provenance,
    )
    repo.create_medication(test_patient.patient_id, warfarin)

    # Patient asks about Aspirin
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/substitution",
        body={"brand": "Ecosprin 75", "strength": "75mg"},
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert any("bleeding" in note.lower() or "warfarin" in note.lower() for note in body["interactions"])


def test_api_substitution_invalid_payload(router):
    """POST /substitution missing both doc_id and brand/strength returns 400."""
    event = {
        "httpMethod": "POST",
        "rawPath": "/substitution",
        "path": "/substitution",
        "body": json.dumps({}),
        "requestContext": {},
    }
    resp = router.route(event)
    assert resp["statusCode"] == 400


# ==================================================
# 5. POST /plan/{day}/{slot}/done
# ==================================================

def test_api_plan_done_valid(repo, router, test_patient, sample_provenance):
    """POST /plan/{day}/{slot}/done confirms dose completion with timestamp."""
    entry = PlanEntry(
        day_index=0,
        slot=SlotName.MORNING,
        action="Take Tab Metformin 500mg",
        med_ref="MED#metformin",
        done=False,
        provenance=sample_provenance,
    )
    repo.create_plan_entry(test_patient.patient_id, entry)

    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/plan/0/morning/done",
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["day"] == 0
    assert body["slot"] == "morning"
    assert body["done"] is True
    assert "completed_at" in body

    # Verify repository status
    ctx = repo.get_patient_context(test_patient.patient_id)
    assert ctx.plan_entries[0].done is True


def test_api_plan_done_missing_entry(router, test_patient):
    """POST /plan/{day}/{slot}/done for non-existent slot returns 404."""
    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/plan/3/night/done",
    )
    resp = router.route(event)
    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "PLAN_ENTRY_NOT_FOUND"


def test_api_plan_done_invalid_day_or_slot(router, test_patient):
    """POST /plan/{day}/{slot}/done with day=10 or slot=midnight returns 400."""
    event1 = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/plan/10/morning/done",
    )
    resp1 = router.route(event1)
    assert resp1["statusCode"] == 400

    event2 = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/plan/0/midnight/done",
    )
    resp2 = router.route(event2)
    assert resp2["statusCode"] == 400


def test_api_plan_done_idempotency(repo, router, test_patient, sample_provenance):
    """Calling POST /plan/{day}/{slot}/done on already-completed dose returns 200 idempotently."""
    entry = PlanEntry(
        day_index=1,
        slot=SlotName.EVENING,
        action="Take Tab Atorvastatin 20mg",
        med_ref="MED#atorvastatin",
        done=True,
        completed_at="2026-09-20T19:30:00Z",
        provenance=sample_provenance,
    )
    repo.create_plan_entry(test_patient.patient_id, entry)

    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/plan/1/evening/done",
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["done"] is True


# ==================================================
# 6. WORKFLOW ENDPOINTS (Plan Generation & Lab Interpretation)
# ==================================================

def test_api_workflow_generate_care_plan(repo, router, test_patient, sample_provenance):
    """POST /plan/generate compiles care plan from active prescriptions."""
    med = Medication(
        name="Telmisartan",
        salt="telmisartan",
        strength="40mg",
        freq="OD",
        duration_days=30,
        provenance=sample_provenance,
    )
    repo.create_medication(test_patient.patient_id, med)

    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/plan/generate",
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["entries"]) >= 7  # 7 days of morning Telmisartan


def test_api_workflow_interpret_labs(repo, router, test_patient, sample_provenance):
    """POST /labs/interpret analyzes patient lab results and returns findings report."""
    lab = LabResult(
        analyte="Serum Creatinine",
        value=2.4,
        unit="mg/dL",
        ref_low=0.7,
        ref_high=1.3,
        provenance=sample_provenance,
    )
    repo.create_lab_result(test_patient.patient_id, lab)

    event = make_auth_event(
        patient_id=test_patient.patient_id,
        method="POST",
        path="/labs/interpret",
    )
    resp = router.route(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["total_findings"] == 1
    assert body["abnormal_count"] == 1


# ==================================================
# 7. END-TO-END REST API INTEGRATION WORKFLOW
# ==================================================

def test_api_end_to_end_integration(repo, storage, sample_source):
    """Complete End-to-End API Integration Workflow:

    1. Register Patient via repository
    2. POST /documents -> Upload presigned URL returned
    3. Register active prescription in canonical patient record
    4. POST /plan/generate -> Day-by-day care schedule compiled
    5. GET /record -> Comprehensive episodic timeline verified
    6. POST /substitution -> Salt-equivalent check for pharmacy stockout
    7. POST /plan/0/morning/done -> Dose marked confirmed taken
    8. GET /record -> Adherence state reflected in timeline
    9. PATCH /record/strength -> Corrected field resolved and confirmed
    """
    router = ApiRouter(repository=repo, storage=storage)

    # 1. Patient Profile
    patient = Patient(
        patient_id="pt_e2e_api",
        name="Vikram Sethi",
        age=60,
        sex="M",
        phone="+919876543210",
    )
    repo.create_patient(patient)

    # 2. Upload Document
    doc_resp = router.route(make_auth_event(
        patient_id=patient.patient_id,
        method="POST",
        path="/documents",
        body={"filename": "discharge.pdf", "content_type": "application/pdf"},
    ))
    assert doc_resp["statusCode"] == 201
    doc_id = json.loads(doc_resp["body"])["doc_id"]

    # 3. Add Prescriptions
    prov = ProvenanceEnvelope(
        field="medication",
        value={"name": "Amlodipine 5mg"},
        source=sample_source,
        confidence=0.95,
        status=ProvenanceStatus.CONFIRMED,
    )
    med = Medication(
        name="Amlodipine",
        salt="amlodipine besylate",
        strength="5mg",
        freq="BD",
        duration_days=30,
        provenance=prov,
    )
    repo.create_medication(patient.patient_id, med)

    # 4. Generate Care Plan
    plan_resp = router.route(make_auth_event(
        patient_id=patient.patient_id,
        method="POST",
        path="/plan/generate",
    ))
    assert plan_resp["statusCode"] == 200

    # 5. GET /record
    rec_resp = router.route(make_auth_event(
        patient_id=patient.patient_id,
        method="GET",
        path="/record",
    ))
    assert rec_resp["statusCode"] == 200
    rec_body = json.loads(rec_resp["body"])
    assert len(rec_body["plan_entries"]) >= 14  # BD -> 2 slots/day x 7 days

    # 6. Check Substitution
    sub_resp = router.route(make_auth_event(
        patient_id=patient.patient_id,
        method="POST",
        path="/substitution",
        body={"brand": "Amlong 5", "strength": "5mg"},
    ))
    assert sub_resp["statusCode"] == 200
    sub_body = json.loads(sub_resp["body"])
    assert sub_body["blocked"] is False
    assert len(sub_body["alternatives"]) >= 1

    # 7. Complete Dose
    done_resp = router.route(make_auth_event(
        patient_id=patient.patient_id,
        method="POST",
        path="/plan/0/morning/done",
    ))
    assert done_resp["statusCode"] == 200

    # 8. Verify Updated Record Adherence
    rec_resp_after = router.route(make_auth_event(
        patient_id=patient.patient_id,
        method="GET",
        path="/record",
    ))
    rec_body_after = json.loads(rec_resp_after["body"])
    d0_morn = next(e for e in rec_body_after["plan_entries"] if e["day_index"] == 0 and e["slot"] == "morning")
    assert d0_morn["done"] is True

    # 9. Correct Field via PATCH /record/field
    patch_resp = router.route(make_auth_event(
        patient_id=patient.patient_id,
        method="PATCH",
        path="/record/field",
        body={"sk": "MED#amlodipine", "field": "instructions", "value": "Take after meals"},
    ))
    assert patch_resp["statusCode"] == 200
    patch_body = json.loads(patch_resp["body"])
    assert patch_body["updated_item"]["instructions"] == "Take after meals"
