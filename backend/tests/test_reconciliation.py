from datetime import datetime, timezone

from app.models.dm_job import DmJob, SENT_PENDING_CONFIRMATION, DELIVERED, PENDING, FAILED
from app.models.delivery_attempt import DeliveryAttempt
from app.services.mock_api_client import ApiResponse
from app.workers import reconciler


def make_sent_job(db, **overrides) -> DmJob:
    defaults = dict(
        rule_id="rule_1",
        webhook_event_id="evt_1",
        comment_id="cmt_1",
        recipient_user_id="usr_1",
        message="hello",
        status=SENT_PENDING_CONFIRMATION,
        dm_id="dm_abc",
        attempt_count=1,
        next_attempt_at=datetime.now(timezone.utc),
        idempotency_key="idem-1",
    )
    defaults.update(overrides)
    job = DmJob(**defaults)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_reconciliation_marks_delivered_dm_as_sent(db, monkeypatch):
    job = make_sent_job(db)

    monkeypatch.setattr(
        reconciler.mock_api_client,
        "get_dm_status",
        lambda dm_id, **kw: ApiResponse(
            status_code=200,
            body={"dm_id": dm_id, "status": "delivered", "recipient_user_id": "usr_1"},
        ),
    )

    reconciler.reconcile_one_job(db, job)
    db.commit()

    assert job.status == DELIVERED


def test_reconciliation_retries_a_dm_that_later_failed(db, monkeypatch):
    job = make_sent_job(db, attempt_count=1)

    monkeypatch.setattr(
        reconciler.mock_api_client,
        "get_dm_status",
        lambda dm_id, **kw: ApiResponse(
            status_code=200, body={"dm_id": dm_id, "status": "failed", "recipient_user_id": "usr_1"}
        ),
    )

    reconciler.reconcile_one_job(db, job)
    db.commit()

    assert job.status == PENDING  # attempts remain, so it goes back into the send queue
    assert job.next_attempt_at > datetime.now(timezone.utc)


def test_reconciliation_gives_up_after_max_attempts(db, monkeypatch):
    job = make_sent_job(db, attempt_count=6)  # already at the default max

    monkeypatch.setattr(
        reconciler.mock_api_client,
        "get_dm_status",
        lambda dm_id, **kw: ApiResponse(
            status_code=200, body={"dm_id": dm_id, "status": "failed", "recipient_user_id": "usr_1"}
        ),
    )

    reconciler.reconcile_one_job(db, job)
    db.commit()

    assert job.status == FAILED


def test_reconciliation_leaves_still_queued_dms_alone(db, monkeypatch):
    job = make_sent_job(db)

    monkeypatch.setattr(
        reconciler.mock_api_client,
        "get_dm_status",
        lambda dm_id, **kw: ApiResponse(
            status_code=200, body={"dm_id": dm_id, "status": "queued", "recipient_user_id": "usr_1"}
        ),
    )

    reconciler.reconcile_one_job(db, job)
    db.commit()

    assert job.status == SENT_PENDING_CONFIRMATION  # unchanged - still waiting


def test_reconciliation_does_not_resend_on_a_failed_status_check(db, monkeypatch):
    """
    If the mock API itself errors out when we ask about a dm_id, we must
    NOT interpret that as "the DM failed" and trigger a resend - the DM may
    already be safely delivered. We just leave the job as-is and try the
    status check again later.
    """
    job = make_sent_job(db)

    monkeypatch.setattr(
        reconciler.mock_api_client,
        "get_dm_status",
        lambda dm_id, **kw: ApiResponse(status_code=500, body={"error": "internal_error"}),
    )

    reconciler.reconcile_one_job(db, job)
    db.commit()

    assert job.status == SENT_PENDING_CONFIRMATION
    attempt = (
        db.query(DeliveryAttempt)
        .filter(DeliveryAttempt.dm_job_id == job.id, DeliveryAttempt.action == "reconcile")
        .one()
    )
    assert attempt.outcome == "check_failed"
