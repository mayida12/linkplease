from datetime import datetime, timezone

from app.config import settings
from app.models.delivery_attempt import DeliveryAttempt
from app.models.dm_job import DmJob, PENDING
from app.services.mock_api_client import ApiResponse
from app.workers import dm_sender


def make_pending_job(db, i: int) -> DmJob:
    job = DmJob(
        rule_id="rule_1",
        webhook_event_id=f"evt_{i}",
        comment_id=f"cmt_{i}",
        recipient_user_id=f"usr_{i}",
        message="hello",
        status=PENDING,
        next_attempt_at=datetime.now(timezone.utc),
        idempotency_key=f"idem-{i}",
    )
    db.add(job)
    return job


def test_run_once_never_sends_more_than_the_configured_limit(db, monkeypatch):
    # Use a small limit so the test doesn't need to create hundreds of jobs
    # to prove the point - the logic is the same at any limit.
    monkeypatch.setattr(settings, "dm_rate_limit_max", 3)
    monkeypatch.setattr(settings, "dm_rate_limit_window_seconds", 60)

    for i in range(7):
        make_pending_job(db, i)
    db.commit()

    monkeypatch.setattr(
        dm_sender.mock_api_client,
        "send_dm",
        lambda **kwargs: ApiResponse(status_code=202, body={"dm_id": "dm_x", "status": "queued"}),
    )

    sent_this_pass = dm_sender.run_once(db)

    assert sent_this_pass == 3  # exactly the rate limit, even though 7 jobs were due

    send_attempts = db.query(DeliveryAttempt).filter(DeliveryAttempt.action == "send").count()
    assert send_attempts == 3

    still_pending = db.query(DmJob).filter(DmJob.status == PENDING).count()
    assert still_pending == 4  # the rest are left for the next pass, not lost


def test_rate_limit_window_frees_up_over_time(db, monkeypatch):
    """
    Sanity check on the rolling-window math itself: an old send attempt
    that's already outside the window shouldn't count against the current
    limit.
    """
    from app.services.rate_limiter import can_send_now
    from datetime import timedelta

    monkeypatch.setattr(settings, "dm_rate_limit_max", 1)
    monkeypatch.setattr(settings, "dm_rate_limit_window_seconds", 60)

    old_attempt = DeliveryAttempt(
        dm_job_id="job_x",
        attempt_number=1,
        action="send",
        http_status=202,
        outcome="queued",
        created_at=datetime.now(timezone.utc) - timedelta(seconds=120),  # outside the 60s window
    )
    db.add(old_attempt)
    db.commit()

    assert can_send_now(db) is True  # the old attempt is outside the window, so we're clear to send
