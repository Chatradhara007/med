"""Regression tests for the correctness and safety fixes.

Each test here pins a defect that was live in the codebase: a mock selected in
a deployed function, a fabricated ARN, a safety rail enforced only in the test
double, a truncated DynamoDB read, or a wrong HTTP status.
"""

import json

import pytest

from carethread.api.common.response import cors_headers
from carethread.api.router import ApiRouter
from carethread.modules.reminders.publisher import (
    PrivacyViolationError,
    SNSNotificationPublisher,
    assert_no_phi,
)
from carethread.modules.reminders.scheduler import (
    EventBridgeReminderScheduler,
    compute_scheduled_time,
)
from carethread.shared.auth import extract_patient_id
from carethread.shared.bedrock.client import use_mock_bedrock
from carethread.shared.repository.dynamodb import DynamoDBPatientRepository
from carethread.shared.schemas.plan_entry import SlotName


# ==================================================
# 1. Mocks must never be selected inside a Lambda
# ==================================================

def test_mock_bedrock_is_refused_inside_a_deployed_lambda(monkeypatch):
    monkeypatch.setenv("USE_MOCK_BEDROCK", "true")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "CareThreadExtractFn")
    assert use_mock_bedrock() is False


def test_mock_bedrock_is_available_locally(monkeypatch):
    monkeypatch.setenv("USE_MOCK_BEDROCK", "true")
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert use_mock_bedrock() is True


def test_mock_auth_header_is_ignored_inside_a_deployed_lambda(monkeypatch):
    """A header-supplied identity is an authentication bypass in production."""
    monkeypatch.setenv("ALLOW_MOCK_AUTH", "true")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "CareThreadRecordFn")

    from carethread.shared.auth.interfaces import UnauthorizedError

    with pytest.raises(UnauthorizedError):
        extract_patient_id({"headers": {"x-patient-id": "attacker"}})


def test_mock_auth_header_works_locally(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_AUTH", "true")
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    assert extract_patient_id({"headers": {"x-patient-id": "pt_local"}}) == "pt_local"


def test_jwt_sub_always_wins_over_a_spoofed_header(monkeypatch):
    monkeypatch.setenv("ALLOW_MOCK_AUTH", "true")
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    event = {
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "pt_real"}}}},
        "headers": {"x-patient-id": "pt_spoofed"},
    }
    assert extract_patient_id(event) == "pt_real"


def test_nested_authorizer_map_is_not_treated_as_an_identity():
    from carethread.shared.auth.interfaces import UnauthorizedError

    with pytest.raises(UnauthorizedError):
        extract_patient_id({"requestContext": {"authorizer": {"sub": {"nested": "map"}}}})


# ==================================================
# 2. No fabricated AWS identifiers
# ==================================================

def test_scheduler_refuses_to_construct_without_real_arns(monkeypatch):
    monkeypatch.delenv("REMINDER_LAMBDA_ARN", raising=False)
    monkeypatch.delenv("EVENTBRIDGE_SCHEDULER_ROLE_ARN", raising=False)
    with pytest.raises(ValueError) as excinfo:
        EventBridgeReminderScheduler()
    assert "REMINDER_LAMBDA_ARN" in str(excinfo.value)


def test_scheduler_constructs_when_configured(monkeypatch):
    monkeypatch.setenv("REMINDER_LAMBDA_ARN", "arn:aws:lambda:eu-west-1:111122223333:function:Rem")
    monkeypatch.setenv("EVENTBRIDGE_SCHEDULER_ROLE_ARN", "arn:aws:iam::111122223333:role/Sched")
    scheduler = EventBridgeReminderScheduler()
    assert "111122223333" in scheduler.target_arn


def test_sns_publisher_has_no_placeholder_topic(monkeypatch):
    monkeypatch.delenv("SNS_TOPIC_ARN", raising=False)
    monkeypatch.delenv("REMINDER_SNS_TOPIC_ARN", raising=False)
    assert SNSNotificationPublisher(boto_client=object()).default_topic_arn is None


def test_sns_publish_without_a_destination_is_refused(monkeypatch):
    monkeypatch.delenv("SNS_TOPIC_ARN", raising=False)
    monkeypatch.delenv("REMINDER_SNS_TOPIC_ARN", raising=False)
    publisher = SNSNotificationPublisher(boto_client=object())
    with pytest.raises(ValueError):
        publisher.publish(destination="", message="CareThread reminder: check your app.")


# ==================================================
# 3. The PHI rail applies to real delivery, not just the mock
# ==================================================

@pytest.mark.parametrize(
    "message",
    [
        "Time for your metformin",
        "Your creatinine result is ready",
        "Reminder about your diabetes care",
        "Take 5.9 mmol/L potassium reading to your doctor",
    ],
)
def test_phi_is_blocked_on_the_real_sns_publisher(message):
    publisher = SNSNotificationPublisher(
        boto_client=object(), default_topic_arn="arn:aws:sns:us-east-1:111122223333:t"
    )
    with pytest.raises(PrivacyViolationError):
        publisher.publish(destination="arn:aws:sns:us-east-1:111122223333:t", message=message)


def test_phi_is_blocked_in_the_subject_line():
    publisher = SNSNotificationPublisher(
        boto_client=object(), default_topic_arn="arn:aws:sns:us-east-1:111122223333:t"
    )
    with pytest.raises(PrivacyViolationError):
        publisher.publish(
            destination="arn:aws:sns:us-east-1:111122223333:t",
            message="CareThread reminder: please open the app.",
            subject="Your hypertension schedule",
        )


def test_generic_reminder_text_passes_the_rail():
    assert_no_phi(
        "CareThread reminder: It is time for your Morning care-plan activities. "
        "Please check your schedule in the CareThread app."
    )


# ==================================================
# 4. DynamoDB reads must not truncate at the 1 MB page boundary
# ==================================================

class PagingTable:
    """Table double that always returns results across two pages."""

    def __init__(self):
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if "ExclusiveStartKey" not in kwargs:
            return {
                "Items": [{"PK": "PATIENT#p", "SK": "MED#a"}],
                "LastEvaluatedKey": {"PK": "PATIENT#p", "SK": "MED#a"},
            }
        return {"Items": [{"PK": "PATIENT#p", "SK": "MED#b"}]}


def test_query_follows_last_evaluated_key_to_completion():
    table = PagingTable()
    repo = DynamoDBPatientRepository(table_name="t", table_resource=table)
    items = repo._query_all(KeyConditionExpression="anything")

    assert len(items) == 2, "a truncated read silently returns a partial record"
    assert len(table.calls) == 2
    assert table.calls[1]["ExclusiveStartKey"] == {"PK": "PATIENT#p", "SK": "MED#a"}


# ==================================================
# 5. HTTP semantics
# ==================================================

@pytest.mark.parametrize(
    "method,path,expected_allow",
    [
        ("PUT", "/documents", "OPTIONS,POST"),
        ("DELETE", "/record", "GET,OPTIONS,PATCH"),
        ("GET", "/substitution", "OPTIONS,POST"),
        ("GET", "/plan/generate", "OPTIONS,POST"),
    ],
)
def test_known_path_wrong_verb_is_405_not_404(method, path, expected_allow):
    response = ApiRouter().route({"httpMethod": method, "rawPath": path})
    assert response["statusCode"] == 405
    assert response["headers"]["Allow"] == expected_allow
    assert json.loads(response["body"])["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_genuinely_unknown_path_is_still_404():
    response = ApiRouter().route({"httpMethod": "GET", "rawPath": "/does-not-exist"})
    assert response["statusCode"] == 404


def test_cors_origin_is_configurable(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGIN", "https://carethread.example.com")
    headers = cors_headers()
    assert headers["Access-Control-Allow-Origin"] == "https://carethread.example.com"
    assert headers["Vary"] == "Origin"


# ==================================================
# 6. Reminder scheduling never lands in the past
# ==================================================

def test_past_slot_on_a_later_day_is_not_scheduled_backwards():
    from datetime import datetime, timezone

    # 23:00 UTC on day 0: every standard slot hour has already passed.
    base = datetime(2026, 9, 19, 23, 0, tzinfo=timezone.utc)
    for day in range(0, 3):
        scheduled = compute_scheduled_time(
            day_index=day, slot=SlotName.MORNING, base_time=base
        )
        assert scheduled > base, f"day {day} reminder was scheduled into the past"


def test_demo_mode_compresses_to_the_configured_delay():
    from datetime import datetime, timezone

    base = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    scheduled = compute_scheduled_time(
        day_index=3, slot=SlotName.NIGHT, demo_mode=True, demo_delay_seconds=30, base_time=base
    )
    assert (scheduled - base).total_seconds() == 30
