from datetime import datetime, timezone

from app.models.delivery_attempt import DeliveryAttempt
from app.models.dm_job import DmJob, PENDING, FAILED, SENT_PENDING_CONFIRMATION
from app.services.mock_api_client import ApiResponse
from app.workers import dm_sender


def make_job(db, **overrides) -> DmJob:
    defaults = dict(
        rule_id="rule_1",
        webhook_event_id="evt_1",
        comment_id="cmt_1",
        recipient_user_id="usr_1",
        message="hello",
        status=PENDING,
        next_attempt_at=datetime.now(timezone.utc),
        idempotency_key="idem-key-1",
    )
    defaults.update(overrides)
    job = DmJob(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# --- Test 8: HTTP 500 is retried ---------------------------------------------

def test_500_response_schedules_a_retry(db, monkeypatch):
    job = make_job(db)

    monkeypatch.setattr(
        dm_sender.mock_api_client,
        "send_dm",
        lambda **kwargs: ApiResponse(status_code=500, body={"error": "internal_error"}),
    )

    dm_sender.send_one_job(db, job)
    db.commit()

    assert job.status == PENDING  # stays pending -> will be retried
    assert job.attempt_count == 1
    assert job.next_attempt_at > datetime.now(timezone.utc)  # scheduled in the future
    assert job.last_error == "internal_error"

    attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.dm_job_id == job.id).one()
    assert attempt.http_status == 500
    assert attempt.outcome == "server_error"


def test_500_exhausting_all_attempts_ends_in_failed(db, monkeypatch):
    job = make_job(db, attempt_count=5)  # one attempt away from the default max of 6

    monkeypatch.setattr(
        dm_sender.mock_api_client,
        "send_dm",
        lambda **kwargs: ApiResponse(status_code=500, body={"error": "internal_error"}),
    )

    dm_sender.send_one_job(db, job)
    db.commit()

    assert job.status == FAILED
    assert job.attempt_count == 6


# --- Test 9: HTTP 429 is retried and Retry-After is respected ---------------

def test_429_response_respects_retry_after_header(db, monkeypatch):
    job = make_job(db)

    monkeypatch.setattr(
        dm_sender.mock_api_client,
        "send_dm",
        lambda **kwargs: ApiResponse(
            status_code=429, body={"error": "rate_limited"}, retry_after_seconds=17
        ),
    )

    before = datetime.now(timezone.utc)
    dm_sender.send_one_job(db, job)
    db.commit()

    assert job.status == PENDING
    seconds_until_retry = (job.next_attempt_at - before).total_seconds()
    assert 16 <= seconds_until_retry <= 18  # ~17s, allowing a little test-runtime slack

    attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.dm_job_id == job.id).one()
    assert attempt.outcome == "rate_limited"


# --- Test 10: HTTP 400 is NOT retried ----------------------------------------

def test_400_response_fails_immediately_without_retry(db, monkeypatch):
    job = make_job(db)

    monkeypatch.setattr(
        dm_sender.mock_api_client,
        "send_dm",
        lambda **kwargs: ApiResponse(
            status_code=400, body={"error": "invalid_request", "detail": "bad recipient"}
        ),
    )

    dm_sender.send_one_job(db, job)
    db.commit()

    assert job.status == FAILED
    assert job.attempt_count == 1  # only tried once - 400s never get a second chance
    assert job.last_error == "bad recipient"

    attempt = db.query(DeliveryAttempt).filter(DeliveryAttempt.dm_job_id == job.id).one()
    assert attempt.outcome == "invalid"
    assert attempt.http_status == 400


# --- 202 (sanity check - not one of the numbered tests, but the base case) --

def test_202_response_moves_job_to_pending_confirmation_not_delivered(db, monkeypatch):
    """
    A 202 must NOT be treated as delivered - it only means "accepted".
    Confirmation only happens later, via reconciliation (Part C).
    """
    job = make_job(db)

    monkeypatch.setattr(
        dm_sender.mock_api_client,
        "send_dm",
        lambda **kwargs: ApiResponse(status_code=202, body={"dm_id": "dm_abc123", "status": "queued"}),
    )

    dm_sender.send_one_job(db, job)
    db.commit()

    assert job.status == SENT_PENDING_CONFIRMATION
    assert job.dm_id == "dm_abc123"
