"""Unit and integration tests for M5 — Reminders module.

Verifies:
1. Schedule creation from canonical PlanEntry objects
2. Deduplication across same (day_index, slot)
3. Production schedule time calculation
4. Demo mode schedule time calculation (DEMO_MODE=True, 30-second delay)
5. ReminderEvent schema parsing and validation success
6. ReminderEvent validation failure returns 400
7. Patient not found in canonical record returns 404
8. PlanEntry not found in patient context returns 404
9. Completed dose adherence suppression (done=True -> SUPPRESSED_COMPLETED, zero SNS messages)
10. Uncompleted dose dispatch (done=False -> SENT, 1 SNS message)
11. Strict idempotency: duplicate EventBridge trigger returns DUPLICATE_SKIPPED
12. Suppressed dose idempotency
13. Mock notification publisher records destinations and attributes
14. Mock scheduler management (scheduling, filtering, cancellation)
15. Privacy leak detection: clinical terms strictly blocked
16. Safe notification message formatting (no PHI exposure)
17. Publisher failure handling returns 500
18. AWS Lambda handler EventBridge unwrapping
19. End-to-end local integration test (schedule -> dispatch -> adherence done -> suppress)
"""

from datetime import datetime, timezone, timedelta
import json
import pytest

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.plan_entry import PlanEntry, SlotName
from carethread.shared.schemas.provenance import (
    ProvenanceEnvelope,
    ProvenanceSource,
    ProvenanceStatus,
)
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.modules.reminders import (
    ReminderEvent,
    ReminderRecord,
    ReminderStatus,
    ReminderExecutionResult,
    ReminderRepository,
    ReminderSchedulerInterface,
    MockReminderScheduler,
    compute_scheduled_time,
    NotificationPublisherInterface,
    MockNotificationPublisher,
    ReminderHandler,
    lambda_handler,
    ReminderService,
)
from carethread.modules.reminders.handler import build_safe_notification_message


@pytest.fixture
def repo():
    return InMemoryPatientRepository()


@pytest.fixture
def sample_source():
    return ProvenanceSource(
        doc_id="d_test_001",
        page=1,
        bbox=[100.0, 150.0, 400.0, 180.0],
        verbatim="Take Tab Metformin 500mg Morning"
    )


@pytest.fixture
def sample_envelope(sample_source):
    return ProvenanceEnvelope(
        field="medication",
        value={"name": "Metformin", "dose": "500mg"},
        source=sample_source,
        confidence=0.98,
        status=ProvenanceStatus.CONFIRMED,
    )


@pytest.fixture
def test_patient(repo):
    patient = Patient(
        patient_id="pt_rem_001",
        name="Ramesh Kumar",
        age=58,
        sex="M",
        phone="+919876543210",
    )
    return repo.create_patient(patient)


@pytest.fixture
def mock_scheduler():
    return MockReminderScheduler()


@pytest.fixture
def mock_publisher():
    return MockNotificationPublisher()


@pytest.fixture
def reminder_service(repo, mock_scheduler, mock_publisher):
    return ReminderService(
        patient_repo=repo,
        scheduler=mock_scheduler,
        publisher=mock_publisher,
    )


# ==================================================
# 1. SCHEDULE CREATION & DEDUPLICATION
# ==================================================

def test_schedule_creation_from_plan_entries(reminder_service, test_patient, sample_envelope, mock_scheduler):
    """Scheduling converts PlanEntry list into ReminderRecord entries and registers with scheduler."""
    entries = [
        PlanEntry(
            day_index=0,
            slot=SlotName.MORNING,
            action="Take Tab Metformin 500mg",
            med_ref="MED#metformin",
            done=False,
            provenance=sample_envelope,
        ),
        PlanEntry(
            day_index=0,
            slot=SlotName.NIGHT,
            action="Take Tab Atorvastatin 20mg",
            med_ref="MED#atorvastatin",
            done=False,
            provenance=sample_envelope,
        ),
        PlanEntry(
            day_index=1,
            slot=SlotName.MORNING,
            action="Take Tab Metformin 500mg",
            med_ref="MED#metformin",
            done=False,
            provenance=sample_envelope,
        ),
    ]

    records = reminder_service.schedule_plan_reminders(test_patient.patient_id, entries)

    assert len(records) == 3
    assert all(r.status == ReminderStatus.SCHEDULED for r in records)
    assert len(mock_scheduler.scheduled) == 3

    # Check persistence in single-table repository
    stored_0_morning = reminder_service.get_reminder_status(test_patient.patient_id, f"{test_patient.patient_id}-d0-morning")
    assert stored_0_morning is not None
    assert stored_0_morning.day_index == 0
    assert stored_0_morning.slot == SlotName.MORNING


def test_slot_deduplication_in_scheduling(reminder_service, test_patient, sample_envelope, mock_scheduler):
    """Multiple prescriptions in the same (day_index, slot) produce a single consolidated reminder trigger."""
    entries = [
        PlanEntry(
            day_index=0,
            slot=SlotName.MORNING,
            action="Take Tab Metformin 500mg",
            med_ref="MED#metformin",
            done=False,
            provenance=sample_envelope,
        ),
        PlanEntry(
            day_index=0,
            slot=SlotName.MORNING,
            action="Take Tab Aspirin 75mg",
            med_ref="MED#aspirin",
            done=False,
            provenance=sample_envelope,
        ),
    ]

    records = reminder_service.schedule_plan_reminders(test_patient.patient_id, entries)
    assert len(records) == 1
    assert records[0].slot == SlotName.MORNING
    assert len(mock_scheduler.scheduled) == 1


# ==================================================
# 2. TIME CALCULATION: PRODUCTION VS DEMO MODE
# ==================================================

def test_prod_schedule_time_calculation():
    """Production mode calculates future target timestamps matching slot hours."""
    base = datetime(2026, 9, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_morn = compute_scheduled_time(day_index=1, slot=SlotName.MORNING, demo_mode=False, base_time=base)
    t_aft = compute_scheduled_time(day_index=1, slot=SlotName.AFTERNOON, demo_mode=False, base_time=base)
    t_eve = compute_scheduled_time(day_index=1, slot=SlotName.EVENING, demo_mode=False, base_time=base)
    t_night = compute_scheduled_time(day_index=1, slot=SlotName.NIGHT, demo_mode=False, base_time=base)

    assert t_morn == datetime(2026, 9, 21, 8, 0, 0, tzinfo=timezone.utc)
    assert t_aft == datetime(2026, 9, 21, 13, 0, 0, tzinfo=timezone.utc)
    assert t_eve == datetime(2026, 9, 21, 18, 0, 0, tzinfo=timezone.utc)
    assert t_night == datetime(2026, 9, 21, 21, 0, 0, tzinfo=timezone.utc)


def test_demo_mode_schedule_time():
    """Demo mode calculates a fast compressed delay (default 30 seconds)."""
    base = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)
    t_demo = compute_scheduled_time(
        day_index=2,
        slot=SlotName.MORNING,
        demo_mode=True,
        demo_delay_seconds=30,
        base_time=base,
    )
    assert t_demo == base + timedelta(seconds=30)


# ==================================================
# 3. SCHEMA VALIDATION & ERROR HANDLING
# ==================================================

def test_reminder_event_validation_success():
    """Valid dictionary successfully parses into ReminderEvent."""
    event_data = {
        "reminder_id": "rem-101",
        "patient_id": "pt_001",
        "day_index": 0,
        "slot": "morning",
        "scheduled_time": "2026-09-20T08:00:00Z",
        "demo_mode": False,
        "idempotency_key": "idem-rem-101",
    }
    event = ReminderEvent.model_validate(event_data)
    assert event.reminder_id == "rem-101"
    assert event.slot == SlotName.MORNING


def test_reminder_event_validation_failure(reminder_service):
    """Malformed event triggers 400 Bad Request."""
    invalid_data = {
        "reminder_id": "",  # Min length violation
        "day_index": 10,    # Max 6 violation
    }
    result = reminder_service.process_reminder_event(invalid_data)
    assert result.status_code == 400
    assert result.status == ReminderStatus.FAILED
    assert result.published is False


def test_patient_not_found_handling(reminder_service):
    """Unknown patient returns 404 Not Found."""
    event = ReminderEvent(
        reminder_id="rem-unknown",
        patient_id="pt_non_existent",
        day_index=0,
        slot=SlotName.MORNING,
        scheduled_time=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem-rem-unknown",
    )
    result = reminder_service.process_reminder_event(event)
    assert result.status_code == 404
    assert result.status == ReminderStatus.FAILED
    assert "not found" in result.message.lower()


def test_plan_entry_not_found_handling(reminder_service, test_patient):
    """Valid patient with no plan entry for target slot returns 404."""
    event = ReminderEvent(
        reminder_id="rem-no-plan",
        patient_id=test_patient.patient_id,
        day_index=5,
        slot=SlotName.EVENING,
        scheduled_time=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem-rem-no-plan",
    )
    result = reminder_service.process_reminder_event(event)
    assert result.status_code == 404
    assert result.status == ReminderStatus.FAILED
    assert "no plan entry found" in result.message.lower()


# ==================================================
# 4. ADHERENCE SUPPRESSION & DISPATCH WORKFLOW
# ==================================================

def test_completed_dose_suppression(repo, reminder_service, test_patient, sample_envelope, mock_publisher):
    """When plan_entry.done is True, reminder is suppressed with zero SNS calls."""
    # Persist completed plan entry
    entry = PlanEntry(
        day_index=0,
        slot=SlotName.MORNING,
        action="Take Tab Metformin 500mg",
        med_ref="MED#metformin",
        done=True,
        completed_at="2026-09-20T07:45:00Z",
        provenance=sample_envelope,
    )
    repo.create_plan_entry(test_patient.patient_id, entry)

    event = ReminderEvent(
        reminder_id=f"{test_patient.patient_id}-d0-morning",
        patient_id=test_patient.patient_id,
        day_index=0,
        slot=SlotName.MORNING,
        scheduled_time=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem-suppress-test",
    )

    result = reminder_service.process_reminder_event(event)

    assert result.status_code == 200
    assert result.status == ReminderStatus.SUPPRESSED_COMPLETED
    assert result.published is False
    assert len(mock_publisher.published_messages) == 0

    # Verify single-table status update
    record = reminder_service.get_reminder_status(test_patient.patient_id, event.reminder_id)
    assert record is not None
    assert record.status == ReminderStatus.SUPPRESSED_COMPLETED


def test_uncompleted_dose_dispatches_notification(repo, reminder_service, test_patient, sample_envelope, mock_publisher):
    """When plan_entry.done is False, notification is published to SNS and status marked SENT."""
    entry = PlanEntry(
        day_index=0,
        slot=SlotName.MORNING,
        action="Take Tab Metformin 500mg",
        med_ref="MED#metformin",
        done=False,
        provenance=sample_envelope,
    )
    repo.create_plan_entry(test_patient.patient_id, entry)

    event = ReminderEvent(
        reminder_id=f"{test_patient.patient_id}-d0-morning",
        patient_id=test_patient.patient_id,
        day_index=0,
        slot=SlotName.MORNING,
        scheduled_time=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem-send-test",
    )

    result = reminder_service.process_reminder_event(event)

    assert result.status_code == 200
    assert result.status == ReminderStatus.SENT
    assert result.published is True
    assert len(mock_publisher.published_messages) == 1

    msg = mock_publisher.published_messages[0]
    # With no SNS_TOPIC_ARN configured the reminder falls back to the patient's
    # own phone number for direct SMS; it is never a fabricated per-patient ARN.
    assert msg["destination"] == test_patient.phone
    assert msg["attributes"]["patient_id"] == test_patient.patient_id
    assert "Morning" in msg["message"]

    # Verify status updated to SENT in repository
    record = reminder_service.get_reminder_status(test_patient.patient_id, event.reminder_id)
    assert record is not None
    assert record.status == ReminderStatus.SENT
    assert record.sent_at is not None


# ==================================================
# 5. STRICT IDEMPOTENCY
# ==================================================

def test_strict_idempotency_duplicate_suppression(repo, reminder_service, test_patient, sample_envelope, mock_publisher):
    """Duplicate EventBridge invocations do not send duplicate SNS alerts."""
    entry = PlanEntry(
        day_index=0,
        slot=SlotName.EVENING,
        action="Take Tab Atorvastatin 20mg",
        med_ref="MED#atorvastatin",
        done=False,
        provenance=sample_envelope,
    )
    repo.create_plan_entry(test_patient.patient_id, entry)

    event = ReminderEvent(
        reminder_id=f"{test_patient.patient_id}-d0-evening",
        patient_id=test_patient.patient_id,
        day_index=0,
        slot=SlotName.EVENING,
        scheduled_time=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem-duplicate-test",
    )

    # First invocation -> SENT
    res1 = reminder_service.process_reminder_event(event)
    assert res1.status == ReminderStatus.SENT
    assert res1.published is True
    assert len(mock_publisher.published_messages) == 1

    # Second duplicate invocation -> DUPLICATE_SKIPPED
    res2 = reminder_service.process_reminder_event(event)
    assert res2.status == ReminderStatus.DUPLICATE_SKIPPED
    assert res2.published is False
    assert len(mock_publisher.published_messages) == 1  # No new message sent!


def test_suppressed_dose_idempotency(repo, reminder_service, test_patient, sample_envelope, mock_publisher):
    """Already-suppressed dose skips subsequent invocations without dispatch."""
    entry = PlanEntry(
        day_index=1,
        slot=SlotName.NIGHT,
        action="Take Tab Amlodipine 5mg",
        med_ref="MED#amlodipine",
        done=True,
        provenance=sample_envelope,
    )
    repo.create_plan_entry(test_patient.patient_id, entry)

    event = ReminderEvent(
        reminder_id=f"{test_patient.patient_id}-d1-night",
        patient_id=test_patient.patient_id,
        day_index=1,
        slot=SlotName.NIGHT,
        scheduled_time=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem-suppress-idem",
    )

    res1 = reminder_service.process_reminder_event(event)
    assert res1.status == ReminderStatus.SUPPRESSED_COMPLETED

    res2 = reminder_service.process_reminder_event(event)
    assert res2.status == ReminderStatus.DUPLICATE_SKIPPED
    assert len(mock_publisher.published_messages) == 0


# ==================================================
# 6. PRIVACY & SAFETY CHECKS
# ==================================================

def test_mock_publisher_records_details(mock_publisher):
    """Publisher records target, attributes, and supports clear."""
    res = mock_publisher.publish(
        destination="arn:aws:sns:mock:topic",
        message="CareThread reminder: It is time for your Morning care plan.",
        subject="Care Plan Reminder",
        attributes={"slot": "morning"},
    )
    assert res.success is True
    assert len(mock_publisher.published_messages) == 1
    mock_publisher.clear()
    assert len(mock_publisher.published_messages) == 0


def test_mock_scheduler_management(mock_scheduler):
    """Mock scheduler supports scheduling, querying by patient, and cancellation."""
    e1 = ReminderEvent(
        reminder_id="r1",
        patient_id="p1",
        day_index=0,
        slot=SlotName.MORNING,
        scheduled_time="2026-09-20T08:00:00Z",
        idempotency_key="i1",
    )
    e2 = ReminderEvent(
        reminder_id="r2",
        patient_id="p2",
        day_index=0,
        slot=SlotName.EVENING,
        scheduled_time="2026-09-20T18:00:00Z",
        idempotency_key="i2",
    )
    mock_scheduler.schedule_reminder(e1)
    mock_scheduler.schedule_reminder(e2)

    assert len(mock_scheduler.list_scheduled()) == 2
    assert len(mock_scheduler.list_scheduled("p1")) == 1

    cancelled = mock_scheduler.cancel_reminder("r1")
    assert cancelled is True
    assert len(mock_scheduler.list_scheduled("p1")) == 0
    assert "r1" in mock_scheduler.cancelled


def test_privacy_leak_detection_blocks_phi(mock_publisher):
    """Mock publisher actively validates and raises error if PHI or clinical terms are present."""
    with pytest.raises(ValueError, match="Privacy violation"):
        mock_publisher.publish(
            destination="topic",
            message="Your diagnosis CAD requires taking medication now.",
        )

    with pytest.raises(ValueError, match="Privacy violation"):
        mock_publisher.publish(
            destination="topic",
            message="Reminder: Your serum creatinine was elevated at 2.4 mg/dl.",
        )


def test_safe_notification_text_format():
    """Generated notification text is strictly generic and contains no medical diagnosis or drug names."""
    msg = build_safe_notification_message("morning")
    assert "Morning" in msg
    assert "CareThread" in msg
    assert "schedule" in msg
    # Assert zero clinical keywords leaked
    for bad_word in ["cad", "diabetes", "hypertension", "creatinine", "troponin", "metformin"]:
        assert bad_word not in msg.lower()


# ==================================================
# 7. INFRASTRUCTURE & FAILURE RESILIENCE
# ==================================================

def test_dynamodb_record_persistence(repo, test_patient):
    """ReminderRecord correctly maps to single table PK and SK patterns."""
    rem_repo = ReminderRepository(repository=repo)
    rec = ReminderRecord(
        reminder_id="rem-persist-1",
        patient_id=test_patient.patient_id,
        day_index=2,
        slot=SlotName.AFTERNOON,
        scheduled_time="2026-09-22T13:00:00Z",
        status=ReminderStatus.SCHEDULED,
        created_at=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem-persist-1",
    )

    rem_repo.save_reminder(rec)
    fetched = rem_repo.get_reminder(test_patient.patient_id, "rem-persist-1")

    assert fetched is not None
    assert fetched.pk == f"PATIENT#{test_patient.patient_id}"
    assert fetched.sk == "REMINDER#rem-persist-1"
    assert fetched.status == ReminderStatus.SCHEDULED


def test_publisher_failure_handling(repo, test_patient, sample_envelope, mock_publisher):
    """When publisher returns an error, handler returns 500 FAILED."""
    entry = PlanEntry(
        day_index=0,
        slot=SlotName.AFTERNOON,
        action="Take Tab Pantoprazole 40mg",
        med_ref="MED#pantoprazole",
        done=False,
        provenance=sample_envelope,
    )
    repo.create_plan_entry(test_patient.patient_id, entry)

    mock_publisher.fail_all = True
    handler = ReminderHandler(patient_repo=repo, publisher=mock_publisher)

    event = ReminderEvent(
        reminder_id="rem-fail-pub",
        patient_id=test_patient.patient_id,
        day_index=0,
        slot=SlotName.AFTERNOON,
        scheduled_time=datetime.now(timezone.utc).isoformat(),
        idempotency_key="idem-fail-pub",
    )

    result = handler.evaluate_and_dispatch(event)
    assert result.status_code == 500
    assert result.status == ReminderStatus.FAILED
    assert result.published is False
    assert result.error is not None


def test_lambda_handler_eventbridge_format(monkeypatch):
    """Lambda entrypoint unwraps EventBridge rule event payload properly."""
    eb_event = {
        "detail-type": "CareThread Reminder Trigger",
        "source": "aws.events",
        "detail": {
            "reminder_id": "rem-lambda-1",
            "patient_id": "pt_non_existent",
            "day_index": 0,
            "slot": "morning",
            "scheduled_time": "2026-09-20T08:00:00Z",
            "idempotency_key": "idem-lambda-1",
        }
    }

    # The Lambda entrypoint talks to real DynamoDB/SNS by default; opt into
    # the local mocks explicitly for this unit test.
    monkeypatch.setenv("USE_MOCK_AWS", "true")
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)

    res = lambda_handler(eb_event, None)
    assert "statusCode" in res
    assert "body" in res
    body = json.loads(res["body"])
    # Non-existent patient will return 404 from the handler logic
    assert res["statusCode"] == 404
    assert body["status"] == "failed"


# ==================================================
# 8. END-TO-END LOCAL INTEGRATION TEST
# ==================================================

def test_end_to_end_local_workflow(repo, sample_envelope):
    """Complete end-to-end integration:

    1. Patient registered with care plan
    2. Reminders scheduled in demo mode (30s delay)
    3. Slot 1 (Morning) evaluated before adherence confirmation -> notification dispatched
    4. Adherence confirmed for Slot 2 (Night) -> update_plan_entry_done
    5. Slot 2 evaluated -> suppressed
    6. Slot 1 re-evaluated -> duplicate skipped
    """
    scheduler = MockReminderScheduler()
    publisher = MockNotificationPublisher()
    service = ReminderService(patient_repo=repo, scheduler=scheduler, publisher=publisher)

    # 1. Setup Patient
    patient = Patient(
        patient_id="pt_e2e_rem",
        name="Anita Desai",
        age=62,
        sex="F",
        phone="+919988776655",
    )
    repo.create_patient(patient)

    # 2. Add Care Plan Entries
    morn_entry = PlanEntry(
        day_index=0,
        slot=SlotName.MORNING,
        action="Take Tab Telmisartan 40mg",
        med_ref="MED#telmisartan",
        done=False,
        provenance=sample_envelope,
    )
    night_entry = PlanEntry(
        day_index=0,
        slot=SlotName.NIGHT,
        action="Take Tab Rosuvastatin 10mg",
        med_ref="MED#rosuvastatin",
        done=False,
        provenance=sample_envelope,
    )
    repo.create_plan_entry(patient.patient_id, morn_entry)
    repo.create_plan_entry(patient.patient_id, night_entry)

    # 3. Schedule Reminders in Demo Mode
    records = service.schedule_plan_reminders(
        patient_id=patient.patient_id,
        plan_entries=[morn_entry, night_entry],
        demo_mode=True,
        demo_delay_seconds=30,
    )
    assert len(records) == 2
    assert len(scheduler.scheduled) == 2

    # 4. Trigger Morning Reminder (uncompleted) -> Dispatched
    morn_event = scheduler.scheduled[f"{patient.patient_id}-d0-morning"]
    res_morn = service.process_reminder_event(morn_event)

    assert res_morn.status_code == 200
    assert res_morn.status == ReminderStatus.SENT
    assert res_morn.published is True
    assert len(publisher.published_messages) == 1

    # 5. Confirm Night dose adherence in canonical record
    repo.update_plan_entry_done(
        patient_id=patient.patient_id,
        day_index=0,
        slot="night",
        done=True,
        completed_at="2026-09-20T20:45:00Z"
    )

    # 6. Trigger Night Reminder -> Suppressed due to confirmed adherence
    night_event = scheduler.scheduled[f"{patient.patient_id}-d0-night"]
    res_night = service.process_reminder_event(night_event)

    assert res_night.status_code == 200
    assert res_night.status == ReminderStatus.SUPPRESSED_COMPLETED
    assert res_night.published is False
    # Publisher message count must still be 1!
    assert len(publisher.published_messages) == 1

    # 7. Re-trigger Morning Reminder -> Duplicate Skipped (Idempotent)
    res_morn_dup = service.process_reminder_event(morn_event)
    assert res_morn_dup.status_code == 200
    assert res_morn_dup.status == ReminderStatus.DUPLICATE_SKIPPED
    assert res_morn_dup.published is False
    assert len(publisher.published_messages) == 1
