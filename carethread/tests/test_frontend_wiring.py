"""Tests for the four frontend wiring gaps.

Each of these was a path the web app would have hit on day one: no profile to
render, no way to display a scan, reminders that were never scheduled, and no
sign-in page.
"""

import json

import pytest

from carethread.api.documents.service import DocumentsService
from carethread.api.record.handler import handle_get_record
from carethread.api.record.service import (
    UNSET_AGE,
    UNSET_PHONE,
    UNSET_SEX,
    RecordService,
    is_profile_complete,
)
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.schemas.api import DocumentCreateRequest
from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType
from carethread.shared.schemas.patient import Patient
from carethread.shared.storage.in_memory import InMemoryStorageService

PATIENT = "pt_wire_001"
DOC = "d_wire01"


def jwt_event(sub=PATIENT, **claims):
    """An API Gateway event carrying authorizer-verified JWT claims."""
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": sub, **claims}}}},
        "httpMethod": "GET",
        "rawPath": "/record",
    }


@pytest.fixture
def repo():
    return InMemoryPatientRepository()


@pytest.fixture
def service(repo):
    return RecordService(repository=repo)


# ==================================================
# 1. Patient profile bootstrap
# ==================================================

def test_new_patient_gets_a_profile_instead_of_null(service, repo):
    """A freshly signed-up patient previously got patient: null."""
    record = service.get_patient_record(
        PATIENT, claims={"sub": PATIENT, "email": "anil.verma@example.com"}
    )

    assert record.patient is not None
    assert record.patient.patient_id == PATIENT
    # The profile is persisted, not just returned.
    assert repo.get_patient(PATIENT) is not None


def test_bootstrap_prefers_the_name_claim(service):
    record = service.get_patient_record(
        PATIENT, claims={"name": "Anil Verma", "email": "av@example.com"}
    )
    assert record.patient.name == "Anil Verma"


def test_bootstrap_falls_back_through_given_family_then_email(repo):
    given = RecordService(repository=InMemoryPatientRepository()).get_patient_record(
        "pt_a", claims={"given_name": "Anil", "family_name": "Verma"}
    )
    assert given.patient.name == "Anil Verma"

    email_only = RecordService(repository=InMemoryPatientRepository()).get_patient_record(
        "pt_b", claims={"email": "ramesh.kumar@example.com"}
    )
    assert email_only.patient.name == "ramesh.kumar"


def test_bootstrap_never_invents_age_sex_or_phone(service):
    """A Cognito token carries none of these; they must not be guessed."""
    record = service.get_patient_record(PATIENT, claims={"name": "Anil Verma"})

    assert record.patient.age == UNSET_AGE
    assert record.patient.sex == UNSET_SEX
    assert record.patient.phone == UNSET_PHONE
    assert record.profile_complete is False


def test_bootstrap_uses_the_phone_claim_when_present(service):
    record = service.get_patient_record(
        PATIENT, claims={"name": "Anil", "phone_number": "+919876543210"}
    )
    assert record.patient.phone == "+919876543210"


def test_existing_profile_is_never_overwritten(service, repo):
    repo.create_patient(
        Patient(patient_id=PATIENT, name="Real Name", age=64, sex="M", phone="+919876543210")
    )
    record = service.get_patient_record(PATIENT, claims={"name": "Claim Name"})

    assert record.patient.name == "Real Name"
    assert record.patient.age == 64
    assert record.profile_complete is True


def test_profile_becomes_complete_once_the_patient_fills_it_in(service, repo):
    service.get_patient_record(PATIENT, claims={"name": "Anil"})
    assert service.get_patient_record(PATIENT).profile_complete is False

    for field, value in (("age", 64), ("sex", "M"), ("phone", "+919876543210")):
        repo.update_entity_field(PATIENT, "PROFILE", field, value, confirm_provenance=False)

    assert service.get_patient_record(PATIENT).profile_complete is True


def test_get_record_handler_passes_verified_claims_only(service):
    """A spoofed header must not seed the profile."""
    event = jwt_event(sub=PATIENT, email="real@example.com")
    event["headers"] = {"x-patient-id": "attacker", "x-name": "Attacker"}

    response = handle_get_record(event, service)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["patient"]["patient_id"] == PATIENT
    assert body["patient"]["name"] == "real"


def test_is_profile_complete_handles_a_missing_patient():
    assert is_profile_complete(None) is False


# ==================================================
# 2. Presigned page image URLs
# ==================================================

@pytest.fixture
def docs(repo):
    return DocumentsService(repository=repo, storage=InMemoryStorageService())


def _ready_document(repo, pages):
    repo.create_document(
        Document(
            patient_id=PATIENT,
            doc_id=DOC,
            type=DocumentType.DISCHARGE_SUMMARY,
            s3_key=f"raw/{PATIENT}/{DOC}.pdf",
            status=DocumentStatus.READY,
            pages=pages,
            created_at="2026-09-19T10:00:00+00:00",
            updated_at="2026-09-19T10:05:00+00:00",
        )
    )


def test_document_status_returns_viewable_page_urls(repo, docs):
    """Raw S3 keys are unusable: the bucket blocks all public access."""
    pages = [f"pages/{PATIENT}/{DOC}/p1.png", f"pages/{PATIENT}/{DOC}/p2.png"]
    _ready_document(repo, pages)

    status = docs.get_document_status(PATIENT, DOC)

    assert status.pages == pages
    assert len(status.page_urls) == len(pages)
    # Index-aligned, so the UI can pair page N with its overlay.
    for key, url in zip(pages, status.page_urls):
        assert key in url
        assert url.startswith("https://")


def test_page_urls_are_empty_when_there_are_no_pages(repo, docs):
    _ready_document(repo, [])
    assert docs.get_document_status(PATIENT, DOC).page_urls == []


def test_page_urls_only_cover_this_patients_own_prefix(repo, docs):
    """The document is fetched patient-scoped, so keys cannot cross partitions."""
    _ready_document(repo, [f"pages/{PATIENT}/{DOC}/p1.png"])
    status = docs.get_document_status(PATIENT, DOC)
    assert f"pages/{PATIENT}/" in status.page_urls[0]


def test_upload_url_is_still_a_put_and_separate_from_download(docs):
    response = docs.create_document(
        PATIENT, DocumentCreateRequest(filename="summary.pdf", content_type="application/pdf")
    )
    assert response.upload_url
    assert "op=get" not in response.upload_url


def test_download_url_rejects_an_empty_key():
    with pytest.raises(ValueError):
        InMemoryStorageService().generate_download_url("")


# ==================================================
# 3. Reminder scheduling is actually triggered
# ==================================================

def test_plan_generation_schedules_reminders(monkeypatch):
    """Nothing used to call ReminderService, so no reminder ever fired."""
    from carethread.api.workflows import handler as workflows

    captured = {}

    class RecordingReminderService:
        def __init__(self, patient_repo):
            captured["repo"] = patient_repo

        def schedule_plan_reminders(self, patient_id, plan_entries, **kwargs):
            captured["patient_id"] = patient_id
            captured["entries"] = plan_entries
            captured["demo_mode"] = kwargs.get("demo_mode")
            return ["r1", "r2"]

    import carethread.modules.reminders.service as reminders
    monkeypatch.setattr(reminders, "ReminderService", RecordingReminderService)
    monkeypatch.setenv("DEMO_MODE", "true")

    count = workflows._schedule_reminders(PATIENT, ["entry"], repository="repo-sentinel")

    assert count == 2
    assert captured["patient_id"] == PATIENT
    assert captured["repo"] == "repo-sentinel"
    assert captured["demo_mode"] is True


def test_plan_generation_survives_unconfigured_reminders(monkeypatch):
    """An unconfigured reminder channel must not lose the generated plan."""
    from carethread.api.workflows import handler as workflows

    class ExplodingReminderService:
        def __init__(self, patient_repo):
            raise ValueError("EventBridgeReminderScheduler is not configured")

    import carethread.modules.reminders.service as reminders
    monkeypatch.setattr(reminders, "ReminderService", ExplodingReminderService)

    assert workflows._schedule_reminders(PATIENT, ["entry"], repository=None) == 0


def test_no_plan_entries_schedules_nothing():
    from carethread.api.workflows import handler as workflows

    assert workflows._schedule_reminders(PATIENT, [], repository=None) == 0


# ==================================================
# 4. Cognito hosted UI is present in the template
# ==================================================

def _template():
    import pathlib
    import re

    import yaml

    src = pathlib.Path(__file__).resolve().parents[1] / "infra" / "template.yaml"
    return yaml.safe_load(re.sub(r"!\w+\s", "", src.read_text()))


def test_template_defines_a_hosted_ui_domain():
    assert "UserPoolDomain" in _template()["Resources"]


def test_client_allows_the_authorization_code_flow_without_a_secret():
    client = _template()["Resources"]["UserPoolClient"]["Properties"]

    assert client["GenerateSecret"] is False
    assert client["AllowedOAuthFlowsUserPoolClient"] is True
    # Implicit flow would put tokens in the URL fragment.
    assert client["AllowedOAuthFlows"] == ["code"]
    assert "openid" in client["AllowedOAuthScopes"]


def test_client_has_callback_and_logout_urls():
    client = _template()["Resources"]["UserPoolClient"]["Properties"]
    assert client["CallbackURLs"]
    assert client["LogoutURLs"]


def test_user_pool_exposes_the_claims_the_bootstrap_reads():
    schema = _template()["Resources"]["UserPool"]["Properties"]["Schema"]
    names = {attribute["Name"] for attribute in schema}
    assert {"name", "phone_number"} <= names


def test_template_outputs_everything_the_frontend_needs():
    outputs = set(_template()["Outputs"])
    assert {"ApiUrl", "UserPoolId", "ClientId", "HostedUiUrl"} <= outputs
