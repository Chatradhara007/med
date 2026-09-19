"""Tests for the M1 ingest pipeline.

Covers the four failure paths the audit flagged as unwired, plus the two
invariants the pipeline is responsible for: confidence gating and never
inferring a value that is not on the page.
"""

import json

import pytest

from carethread.pipeline.bbox import TextLayer, derive_source_location, normalise
from carethread.pipeline.classify.handler import (
    CLASSIFICATION_THRESHOLD,
    classify_document,
)
from carethread.pipeline.common import (
    UnsupportedDocumentError,
    envelope_from_event,
    page_key,
    parse_raw_key,
)
from carethread.pipeline.confidence.handler import (
    build_diagnoses,
    build_lab_results,
    build_medications,
    gate_confidence,
    handle_failure,
    mark_ready,
    persist_entities,
)
from carethread.pipeline.extract.handler import extract_document
from carethread.pipeline.validate.handler import validate_extraction, validate_payload
from carethread.shared.bedrock import MockBedrockClient, extract_json_object
from carethread.shared.bedrock.client import BedrockInvocationError
from carethread.shared.prompts import schema_for_type
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType
from carethread.shared.schemas.provenance import ProvenanceStatus

PATIENT = "pt_pipeline_001"
DOC = "d_pipe01"
BUCKET = "carethread-docs-test"


class FakeS3:
    """Minimal in-memory S3 double."""

    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.puts = {}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(f"no such key {Key}")
        return {"Body": self.objects[Key]}

    def put_object(self, Bucket, Key, Body, ContentType=None, ServerSideEncryption=None):
        self.puts[Key] = Body
        return {}


@pytest.fixture
def repo():
    repository = InMemoryPatientRepository()
    repository.create_document(
        Document(
            patient_id=PATIENT,
            doc_id=DOC,
            type=DocumentType.UNKNOWN,
            s3_key=f"raw/{PATIENT}/{DOC}.pdf",
            status=DocumentStatus.UPLOADING,
            pages=[],
            created_at="2026-09-19T10:00:00+00:00",
            updated_at="2026-09-19T10:00:00+00:00",
        )
    )
    return repository


@pytest.fixture
def envelope():
    return {
        "patient_id": PATIENT,
        "doc_id": DOC,
        "bucket": BUCKET,
        "key": f"raw/{PATIENT}/{DOC}.pdf",
        "pages": [page_key(PATIENT, DOC, 1)],
    }


@pytest.fixture
def s3():
    return FakeS3({page_key(PATIENT, DOC, 1): b"\x89PNG-fake-page"})


# ==================================================
# 1. Envelope / key parsing
# ==================================================

def test_parse_raw_key_extracts_patient_and_doc():
    assert parse_raw_key("raw/pt_1/d_9.pdf") == ("pt_1", "d_9", "pdf")


def test_parse_raw_key_rejects_foreign_layout():
    with pytest.raises(UnsupportedDocumentError):
        parse_raw_key("uploads/whatever.pdf")


def test_envelope_unwraps_eventbridge_s3_event():
    env = envelope_from_event(
        {
            "detail": {
                "bucket": {"name": BUCKET},
                "object": {"key": f"raw/{PATIENT}/{DOC}.pdf"},
            }
        }
    )
    assert env["patient_id"] == PATIENT
    assert env["doc_id"] == DOC
    assert env["extension"] == "pdf"


# ==================================================
# 2. Classification -- unknown is a first-class outcome
# ==================================================

def test_low_confidence_classification_marks_document_unsupported(repo, envelope, s3):
    bedrock = MockBedrockClient(
        json_responses=[
            {
                "document_type": "discharge_summary",
                "confidence": CLASSIFICATION_THRESHOLD - 0.1,
                "reason": "blurred",
            }
        ]
    )
    result = classify_document(envelope, repository=repo, bedrock=bedrock, s3_client=s3)

    assert result["document_type"] == "unknown"
    document = repo.get_document(PATIENT, DOC)
    assert document.status == DocumentStatus.UNSUPPORTED
    # The patient gets a clear message, never a guess.
    assert "could not recognise" in document.error_reason.lower()


def test_unknown_classification_is_not_routed_to_an_extractor(repo, envelope, s3):
    bedrock = MockBedrockClient(
        json_responses=[{"document_type": "unknown", "confidence": 0.99, "reason": "a receipt"}]
    )
    result = classify_document(envelope, repository=repo, bedrock=bedrock, s3_client=s3)
    assert result["document_type"] == "unknown"
    assert repo.get_document(PATIENT, DOC).status == DocumentStatus.UNSUPPORTED


def test_confident_classification_advances_to_extracting(repo, envelope, s3):
    bedrock = MockBedrockClient(
        json_responses=[
            {"document_type": "lab_report", "confidence": 0.94, "reason": "analyte table"}
        ]
    )
    result = classify_document(envelope, repository=repo, bedrock=bedrock, s3_client=s3)

    assert result["document_type"] == "lab_report"
    document = repo.get_document(PATIENT, DOC)
    assert document.status == DocumentStatus.EXTRACTING
    assert document.type == DocumentType.LAB_REPORT


# ==================================================
# 3. Extraction -- every value carries a source
# ==================================================

def test_extraction_attaches_source_citation_to_every_entity(repo, envelope, s3):
    envelope["document_type"] = "discharge_summary"
    bedrock = MockBedrockClient(
        json_responses=[
            {
                "discharge_date": "2026-09-18",
                "diagnoses": [
                    {
                        "label": "Type 2 Diabetes Mellitus",
                        "icd_hint": "E11",
                        "source": {"verbatim": "T2DM on metformin"},
                        "confidence": 0.93,
                    }
                ],
                "medications": [
                    {
                        "name": "Metformin",
                        "salt": "metformin hydrochloride",
                        "strength": "500mg",
                        "freq": "BD",
                        "duration_days": 30,
                        "source": {"verbatim": "Tab. Metformin 500mg BD x 30 days"},
                        "confidence": 0.91,
                    }
                ],
            }
        ]
    )
    result = extract_document(envelope, repository=repo, bedrock=bedrock, s3_client=s3)

    med = result["extraction"]["medications"][0]
    assert med["source"]["doc_id"] == DOC
    assert med["source"]["verbatim"] == "Tab. Metformin 500mg BD x 30 days"
    assert len(med["source"]["bbox"]) == 4


def test_extraction_refuses_an_unclassified_document(repo, envelope, s3):
    envelope["document_type"] = "unknown"
    with pytest.raises(Exception):
        extract_document(envelope, repository=repo, bedrock=MockBedrockClient(), s3_client=s3)


# ==================================================
# 4. The self-correcting validate loop
# ==================================================

def test_invalid_extraction_is_repaired_on_the_second_attempt(repo, envelope, s3):
    envelope["document_type"] = "lab_report"
    # Missing the required lab_results key entirely.
    envelope["extraction"] = {"report_date": "2026-09-18"}

    repaired = {
        "report_date": "2026-09-18",
        "lab_results": [
            {
                "analyte": "Serum Creatinine",
                "value": 2.4,
                "unit": "mg/dL",
                "ref_low": 0.7,
                "ref_high": 1.3,
                "source": {"verbatim": "Creatinine 2.4 mg/dL"},
                "confidence": 0.95,
            }
        ],
    }
    bedrock = MockBedrockClient(json_responses=[repaired])

    result = validate_extraction(envelope, repository=repo, bedrock=bedrock, s3_client=s3)

    assert result["validation_status"] == "repaired"
    assert result["validation_errors"] == []
    assert result["extraction"]["lab_results"][0]["analyte"] == "Serum Creatinine"
    # The repair prompt must carry the original validation error text.
    assert "failed schema validation" in bedrock.calls[0]["prompt"]


def test_valid_extraction_skips_the_repair_call(repo, envelope, s3):
    envelope["document_type"] = "lab_report"
    envelope["extraction"] = {
        "lab_results": [
            {
                "analyte": "Potassium",
                "value": 5.9,
                "unit": "mmol/L",
                "ref_low": 3.5,
                "ref_high": 5.1,
                "source": {"verbatim": "K+ 5.9"},
                "confidence": 0.9,
            }
        ]
    }
    bedrock = MockBedrockClient()  # no queued response: a call would raise
    result = validate_extraction(envelope, repository=repo, bedrock=bedrock, s3_client=s3)
    assert result["validation_status"] == "valid"
    assert bedrock.calls == []


def test_validate_payload_reports_schema_errors():
    errors = validate_payload({"lab_results": "not a list"}, schema_for_type(DocumentType.LAB_REPORT))
    assert errors and "lab_results" in errors[0]


# ==================================================
# 5. Confidence gating -- the 0.85 threshold
# ==================================================

def _med(confidence, **overrides):
    payload = {
        "name": "Metformin",
        "salt": "metformin hydrochloride",
        "strength": "500mg",
        "freq": "BD",
        "duration_days": 30,
        "source": {"doc_id": DOC, "page": 1, "bbox": [10, 10, 20, 20], "verbatim": "Tab. Metformin 500mg BD"},
        "confidence": confidence,
        "_bbox_exact": True,
    }
    payload.update(overrides)
    return payload


def test_high_confidence_medication_is_confirmed():
    meds, problems = build_medications([_med(0.91)])
    assert problems == []
    assert meds[0].provenance.status == ProvenanceStatus.CONFIRMED


def test_low_confidence_medication_needs_review():
    meds, _ = build_medications([_med(0.62)])
    assert meds[0].provenance.status == ProvenanceStatus.NEEDS_REVIEW


def test_confidence_exactly_at_threshold_is_confirmed():
    meds, _ = build_medications([_med(0.85)])
    assert meds[0].provenance.status == ProvenanceStatus.CONFIRMED


def test_missing_dose_is_never_inferred():
    """A strength absent from the document must not be completed from knowledge."""
    meds, _ = build_medications([_med(0.98, strength=None)])
    med = meds[0]
    assert med.strength == "not stated"
    # High model confidence must not confirm a field the document never carried.
    assert med.provenance.status == ProvenanceStatus.NEEDS_REVIEW


def test_medication_without_a_source_is_rejected():
    bad = _med(0.95)
    bad["source"] = {"doc_id": DOC, "page": 1, "bbox": [0, 0, 1, 1], "verbatim": ""}
    meds, problems = build_medications([bad])
    assert meds == []
    assert problems and "rejected" in problems[0]


def test_lab_row_keeps_the_printed_range_and_never_invents_one():
    printed, _ = build_lab_results(
        [
            {
                "analyte": "Creatinine",
                "value": 2.4,
                "unit": "mg/dL",
                "ref_low": 0.7,
                "ref_high": 1.3,
                "source": {"doc_id": DOC, "page": 1, "bbox": [1, 1, 2, 2], "verbatim": "Creatinine 2.4"},
                "confidence": 0.95,
                "_bbox_exact": True,
            }
        ]
    )
    assert printed[0].ref_source == "printed"
    assert (printed[0].ref_low, printed[0].ref_high) == (0.7, 1.3)

    unprinted, _ = build_lab_results(
        [
            {
                "analyte": "Creatinine",
                "value": 2.4,
                "unit": "mg/dL",
                "ref_low": None,
                "ref_high": None,
                "source": {"doc_id": DOC, "page": 1, "bbox": [1, 1, 2, 2], "verbatim": "Creatinine 2.4"},
                "confidence": 0.95,
                "_bbox_exact": True,
            }
        ]
    )
    assert unprinted[0].ref_source == "none"
    assert unprinted[0].ref_low is None and unprinted[0].ref_high is None


def test_diagnosis_without_a_label_is_discarded():
    diags, problems = build_diagnoses(
        [{"label": "", "source": {"verbatim": "x"}, "confidence": 0.9}]
    )
    assert diags == [] and problems


# ==================================================
# 6. Gate -> persist -> mark ready
# ==================================================

def test_gated_entities_are_persisted_and_document_marked_ready(repo, envelope):
    envelope["document_type"] = "discharge_summary"
    envelope["extraction"] = {"medications": [_med(0.93)], "diagnoses": [], "lab_results": []}

    gated = gate_confidence(envelope)
    assert gated["needs_review_count"] == 0

    persisted = persist_entities(gated, repository=repo)
    assert persisted["persisted_count"] == 1
    assert len(repo.get_medications(PATIENT)) == 1

    final = mark_ready(persisted, repository=repo)
    assert final["final_status"] == DocumentStatus.READY.value
    assert repo.get_document(PATIENT, DOC).status == DocumentStatus.READY


def test_needs_review_entity_marks_document_review_required(repo, envelope):
    envelope["document_type"] = "discharge_summary"
    envelope["extraction"] = {"medications": [_med(0.55)], "diagnoses": [], "lab_results": []}

    final = mark_ready(persist_entities(gate_confidence(envelope), repository=repo), repository=repo)
    assert final["final_status"] == DocumentStatus.REVIEW_REQUIRED.value


# ==================================================
# 7. Failure path -- status failed with a usable reason
# ==================================================

def test_handle_failure_marks_document_failed_with_a_reason(repo, envelope):
    envelope["error"] = {"Error": "UnsupportedDocumentError", "Cause": "Uploaded file is not a readable image"}
    result = handle_failure(envelope, repository=repo)

    assert result["final_status"] == DocumentStatus.FAILED.value
    document = repo.get_document(PATIENT, DOC)
    assert document.status == DocumentStatus.FAILED
    assert document.error_reason == "Uploaded file is not a readable image"


def test_handle_failure_never_leaks_a_stack_trace(repo, envelope):
    envelope["error"] = {
        "Cause": 'Traceback (most recent call last):\n  File "/var/task/x.py", line 1\nValueError: boom'
    }
    handle_failure(envelope, repository=repo)
    reason = repo.get_document(PATIENT, DOC).error_reason
    assert "\n" not in reason
    assert "/var/task" not in reason


# ==================================================
# 8. Model output handling
# ==================================================

def test_json_is_recovered_from_a_fenced_response():
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_prose_response_is_rejected():
    with pytest.raises(BedrockInvocationError):
        extract_json_object("I think the patient has diabetes.")


def test_non_object_json_is_rejected():
    with pytest.raises(BedrockInvocationError):
        extract_json_object("[1, 2, 3]")


# ==================================================
# 9. Bounding boxes by verbatim matching
# ==================================================

def test_verbatim_match_resolves_the_correct_page():
    layer = TextLayer(page_texts=["cover page", "Tab. Metformin 500mg BD x 30 days"])
    page, bbox, located = derive_source_location("Tab. Metformin 500mg BD x 30 days", layer)
    assert page == 2
    # No word geometry supplied, so the citation is a page-level highlight.
    assert located is False
    assert bbox == [0.0, 0.0, 1000.0, 1000.0]


def test_word_geometry_upgrades_to_a_region_box():
    layer = TextLayer(
        page_texts=["Metformin 500mg"],
        word_boxes=[
            [
                {"text": "Metformin", "ymin": 100, "xmin": 50, "ymax": 120, "xmax": 200},
                {"text": "500mg", "ymin": 100, "xmin": 210, "ymax": 120, "xmax": 280},
            ]
        ],
    )
    page, bbox, located = derive_source_location("Metformin 500mg", layer)
    assert (page, located) == (1, True)
    assert bbox == [100.0, 50.0, 120.0, 280.0]


def test_unlocatable_verbatim_falls_back_to_page_highlight():
    layer = TextLayer(page_texts=["something else entirely"])
    page, bbox, located = derive_source_location("Tab. Metformin", layer)
    assert located is False
    assert bbox == [0.0, 0.0, 1000.0, 1000.0]


def test_normalise_collapses_ocr_whitespace():
    assert normalise("  Tab.   Metformin\n500mg ") == "tab. metformin 500mg"


# ==================================================
# 10. HandleFailure must survive a Rasterise failure
# ==================================================

def test_rasterise_failure_still_marks_the_document_failed(repo):
    """Rasterise fails before patient_id/doc_id exist on the state.

    The state machine sends the whole failed state under "input" for exactly
    this reason. Resolving $.patient_id there would fail HandleFailure itself
    and leave the document stuck at "rasterising" forever, spinning in the UI.
    """
    # Precisely what Step Functions delivers after Rasterise fails: the
    # EventBridge input ({bucket, key}) plus the caught error, and nothing else.
    event = {
        "input": {
            "bucket": BUCKET,
            "key": f"raw/{PATIENT}/{DOC}.pdf",
            "error": {
                "Error": "UnsupportedDocumentError",
                "Cause": "No PDF rasteriser available in this runtime",
            },
        }
    }
    result = handle_failure(event, repository=repo)

    assert result["final_status"] == DocumentStatus.FAILED.value
    document = repo.get_document(PATIENT, DOC)
    assert document.status == DocumentStatus.FAILED
    assert document.error_reason == "No PDF rasteriser available in this runtime"


def test_handle_failure_still_accepts_a_flat_late_stage_state(repo):
    """A failure after Rasterise carries patient_id/doc_id directly."""
    event = {
        "patient_id": PATIENT,
        "doc_id": DOC,
        "bucket": BUCKET,
        "error": {"Cause": "Bedrock throttled"},
    }
    assert handle_failure(event, repository=repo)["final_status"] == DocumentStatus.FAILED.value
    assert repo.get_document(PATIENT, DOC).error_reason == "Bedrock throttled"


def test_state_machine_failure_path_resolves_against_the_eventbridge_input():
    """Guard the JSONPath contract itself, not just the Lambda."""
    import json as _json
    import pathlib as _pathlib

    asl = _json.loads(
        (_pathlib.Path(__file__).resolve().parents[1]
         / "pipeline" / "statemachine" / "ingest_pipeline.asl.json").read_text()
    )
    payload = asl["States"]["HandleFailure"]["Parameters"]["Payload"]

    # The EventBridge rule supplies only these two fields.
    available = {"bucket", "key", "error"}
    for key, value in payload.items():
        if key.endswith(".$") and value != "$":
            field = value.split(".", 1)[1] if "." in value else value
            assert field in available, (
                f"HandleFailure resolves {value}, absent when Rasterise fails"
            )
