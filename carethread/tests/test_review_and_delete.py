"""Regression tests for the three bugs that made a reviewed record unusable.

Each of these was reachable from the documents screen and none of them was
covered before:

* every extracted entity came back ``needs_review`` however confident the
  extraction was, because no TextLayer ever carried word geometry so the bbox
  was always the whole page and the gate forced review on that;
* a patient who agreed with a correct extraction had no way to say so -- the
  only write path required changing a value;
* ``DELETE /documents/{id}`` reached no route, because the handler and router
  supported it but the template never declared it.
"""

from pathlib import Path

import pytest
import yaml

from carethread.api.record.service import RecordService
from carethread.api.router import ApiRouter
from carethread.pipeline.bbox import TextLayer, derive_source_location
from carethread.pipeline.confidence.handler import _build_envelope
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.schemas.api import RecordFieldPatchRequest
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)

PATIENT = "pt_review_001"
DOC = "d_review01"

TEMPLATE = Path(__file__).resolve().parents[1] / "infra" / "template.yaml"


# --------------------------------------------------------------------------
# bbox geometry
# --------------------------------------------------------------------------


def _layer_with_geometry() -> TextLayer:
    """A one-page layer whose two lines sit at different heights."""
    line_one = "1. Tab. Metformin 500mg BD x 30 days".split()
    line_two = "2. Tab. Amlodipine 5mg OD x 30 days".split()
    words = []
    for index, token in enumerate(line_one):
        words.append(
            {"text": token, "ymin": 100.0, "ymax": 120.0,
             "xmin": 50.0 + index * 40, "xmax": 85.0 + index * 40}
        )
    for index, token in enumerate(line_two):
        words.append(
            {"text": token, "ymin": 200.0, "ymax": 220.0,
             "xmin": 50.0 + index * 40, "xmax": 85.0 + index * 40}
        )
    return TextLayer(
        page_texts=[" ".join(line_one) + "\n" + " ".join(line_two)],
        word_boxes=[words],
    )


def test_word_geometry_yields_an_exact_box():
    page, bbox, located = derive_source_location(
        "1. Tab. Metformin 500mg BD x 30 days", _layer_with_geometry()
    )
    assert located is True
    assert page == 1
    assert bbox != [0.0, 0.0, 1000.0, 1000.0]
    assert bbox[0] == 100.0 and bbox[2] == 120.0


def test_box_covers_only_the_matching_line():
    """"x 30 days" appears on both lines; the box must not span them."""
    _, bbox, located = derive_source_location(
        "2. Tab. Amlodipine 5mg OD x 30 days", _layer_with_geometry()
    )
    assert located is True
    assert bbox[0] == 200.0, "box leaked into the line above"
    assert bbox[2] == 220.0


def test_without_geometry_the_citation_is_page_level():
    layer = TextLayer(page_texts=["1. Tab. Metformin 500mg BD x 30 days"])
    page, bbox, located = derive_source_location("Tab. Metformin 500mg", layer)
    assert (page, bbox, located) == (1, [0.0, 0.0, 1000.0, 1000.0], False)


# --------------------------------------------------------------------------
# the confidence gate
# --------------------------------------------------------------------------


def _extracted(confidence: float, bbox_exact: bool) -> dict:
    return {
        "confidence": confidence,
        "_bbox_exact": bbox_exact,
        "source": {"doc_id": DOC, "page": 1, "verbatim": "Tab. Metformin 500mg BD x 30 days"},
    }


VALUE = {"name": "Metformin", "salt": "Metformin", "strength": "500mg",
         "freq": "BD", "duration_days": 30}


def test_a_coarse_box_no_longer_forces_review():
    """This is the bug: confidence 1.0 still came back amber, every time."""
    envelope, needs_review = _build_envelope("medication", VALUE, _extracted(1.0, False), False)
    assert envelope.status is ProvenanceStatus.CONFIRMED
    assert needs_review is False


def test_a_coarse_box_is_recorded_on_the_source():
    envelope, _ = _build_envelope("medication", VALUE, _extracted(1.0, False), False)
    assert envelope.source.bbox_exact is False

    exact, _ = _build_envelope("medication", VALUE, _extracted(1.0, True), False)
    assert exact.source.bbox_exact is True


def test_low_confidence_still_needs_review():
    envelope, needs_review = _build_envelope("medication", VALUE, _extracted(0.4, True), False)
    assert envelope.status is ProvenanceStatus.NEEDS_REVIEW
    assert needs_review is True


def test_an_unstated_field_still_forces_review_whatever_the_confidence():
    """The "never infer a missing value" rail is untouched by the bbox change."""
    envelope, needs_review = _build_envelope("medication", VALUE, _extracted(1.0, True), True)
    assert envelope.status is ProvenanceStatus.NEEDS_REVIEW
    assert needs_review is True


# --------------------------------------------------------------------------
# confirming a correct extraction
# --------------------------------------------------------------------------


@pytest.fixture
def repo_with_medication():
    repo = InMemoryPatientRepository()
    repo.create_medication(
        PATIENT,
        Medication(
            name="Metformin", salt="Metformin", strength="500mg", form="tablet",
            freq="BD", duration_days=30,
            provenance=ProvenanceEnvelope(
                field="medication", value=VALUE,
                source=ProvenanceSource(
                    doc_id=DOC, page=1, bbox=[0.0, 0.0, 1000.0, 1000.0],
                    verbatim="Tab. Metformin 500mg BD x 30 days", bbox_exact=False,
                ),
                confidence=0.62, status=ProvenanceStatus.NEEDS_REVIEW,
            ),
        ),
    )
    return repo


def test_confirm_resolves_the_chip_without_changing_a_value(repo_with_medication):
    service = RecordService(repository=repo_with_medication)
    response = service.patch_record_field(
        patient_id=PATIENT,
        request=RecordFieldPatchRequest(sk="MED#metformin", confirm=True),
    )
    assert response.status is ProvenanceStatus.CONFIRMED
    assert response.updated_item["strength"] == "500mg", "confirming must not alter the value"


def test_confirm_needs_no_field_but_a_bare_patch_is_still_rejected():
    RecordFieldPatchRequest(sk="MED#metformin", confirm=True)
    with pytest.raises(ValueError):
        RecordFieldPatchRequest(sk="MED#metformin")


def test_confirming_an_unknown_entity_type_is_refused(repo_with_medication):
    service = RecordService(repository=repo_with_medication)
    with pytest.raises(ValueError):
        service.patch_record_field(
            patient_id=PATIENT,
            request=RecordFieldPatchRequest(sk="NOPE#whatever", confirm=True),
        )


# --------------------------------------------------------------------------
# document deletion
# --------------------------------------------------------------------------


def test_router_reports_delete_as_an_allowed_method():
    assert "DELETE" in ApiRouter._allowed_methods("/documents/d_abc")


def test_a_doc_id_containing_the_word_delete_is_not_a_delete():
    """`"delete" in path` used to be enough to route a POST to the deleter."""
    from carethread.api.documents.handler import handler

    event = {
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": PATIENT}}}},
        "httpMethod": "POST",
        "rawPath": "/documents/d_undeleted",
        "body": None,
    }
    # No body means the create path rejects it; the point is that it *reached*
    # the create path rather than being mistaken for a deletion.
    assert handler(event)["statusCode"] == 400


def _template() -> dict:
    text = TEMPLATE.read_text()
    # SAM's short-form intrinsics are not valid YAML tags; they are irrelevant
    # to the route shape, so resolve them to their argument.
    for tag in ("!Ref", "!GetAtt", "!Sub", "!Join", "!Select", "!Split", "!ImportValue"):
        text = text.replace(tag + " ", "")
    return yaml.safe_load(text)


def test_template_declares_the_delete_route():
    events = _template()["Resources"]["DocumentsApiFn"]["Properties"]["Events"]
    routes = {(e["Properties"]["Path"], e["Properties"]["Method"]) for e in events.values()}
    assert ("/documents/{id}", "DELETE") in routes, (
        "the handler supports DELETE but API Gateway has no route to reach it"
    )


def test_cors_allows_delete():
    """A preflight that omits DELETE blocks the request before it is sent."""
    cors = _template()["Resources"]["HttpApi"]["Properties"]["CorsConfiguration"]
    assert "DELETE" in cors["AllowMethods"]


# --------------------------------------------------------------------------
# model client selection
# --------------------------------------------------------------------------


def test_client_selection_does_not_raise_without_mocks(monkeypatch):
    """`get_bedrock_client` referenced an undefined DEFAULT_GROQ_API_KEY.

    Every test set USE_MOCK_BEDROCK, which returns before that line, so a
    NameError on the real path shipped green -- it would have taken down
    classify and extract on the first upload after deploy.
    """
    from carethread.shared.bedrock.client import BedrockClient, get_bedrock_client

    monkeypatch.delenv("USE_MOCK_BEDROCK", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")

    assert isinstance(get_bedrock_client(), BedrockClient)


def test_groq_is_used_only_when_configured_and_bedrock_is_not(monkeypatch):
    from carethread.shared.bedrock.client import BedrockClient, GroqClient, get_bedrock_client

    monkeypatch.delenv("USE_MOCK_BEDROCK", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    monkeypatch.setenv("BEDROCK_MODEL_ID", "")
    assert isinstance(get_bedrock_client(), GroqClient)

    # An explicitly chosen model means the operator picked Bedrock; clinical
    # extraction must not silently move to another vendor.
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
    assert isinstance(get_bedrock_client(), BedrockClient)


def test_no_api_key_is_committed_in_the_client():
    import pathlib
    import re

    source = (
        pathlib.Path(__file__).resolve().parents[1] / "shared" / "bedrock" / "client.py"
    ).read_text()
    assert not re.search(r"gsk_[A-Za-z0-9]{10,}", source), "a Groq API key is hardcoded"


def test_template_exposes_the_groq_fallback_as_a_parameter():
    """Otherwise the key can only be set by hand on each function."""
    params = _template()["Parameters"]
    assert params["GroqApiKey"]["NoEcho"] is True
    assert params["GroqApiKey"]["Default"] == ""

    extract_env = _template()["Resources"]["ExtractFn"]["Properties"]["Environment"]["Variables"]
    assert "GROQ_API_KEY" in extract_env
