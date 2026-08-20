"""
Picks up DmJobs that are due to be sent (status=pending, next_attempt_at in
the past) and actually calls the mock API's POST /v1/dm/send.

Crucially: a 202 response is NOT treated as "delivered". It just means the
mock API accepted the request into its own queue. We store the returned
dm_id and move the job to SENT_PENDING_CONFIRMATION; workers/reconciler.py
is what later confirms whether it was really delivered or failed.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_attempt import DeliveryAttempt
from app.models.dm_job import DmJob, PENDING, SENT_PENDING_CONFIRMATION, FAILED
from app.services import mock_api_client
from app.services.rate_limiter import can_send_now
from app.services.retry_policy import next_attempt_at, has_attempts_remaining, should_retry

BATCH_SIZE = 10  # matches the rate limit ceiling - never worth claiming more per pass


def claim_one_due_job(db: Session) -> DmJob | None:
    """
    Locks (at most) a single due job, skipping any row another worker
    process already has locked.

    We deliberately claim and commit ONE job at a time here rather than
    locking a whole batch up front: SQLAlchemy releases row locks when the
    transaction commits, so if we locked 10 rows and then took a while
    sending job #1, jobs #2-10 would still be sitting there locked (and
    therefore invisible to any other worker) even though nothing is
    actively working on them yet. Claiming one at a time keeps each lock
    held for the shortest possible time.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(DmJob)
        .where(DmJob.status == PENDING, DmJob.next_attempt_at <= now)
        .order_by(DmJob.next_attempt_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return db.execute(stmt).scalars().first()


def _record_attempt(db: Session, job: DmJob, http_status: int | None, outcome: str, detail: str | None):
    db.add(
        DeliveryAttempt(
            dm_job_id=job.id,
            attempt_number=job.attempt_count,
            action="send",
            http_status=http_status,
            outcome=outcome,
            detail=detail,
        )
    )


def send_one_job(db: Session, job: DmJob) -> None:
    job.attempt_count += 1

    response = mock_api_client.send_dm(
        recipient_user_id=job.recipient_user_id,
        message=job.message,
        comment_id=job.comment_id,
        idempotency_key=f"{job.idempotency_key}:{job.attempt_count}",
    )

    if response.status_code in (200, 202):
        job.dm_id = response.body.get("dm_id")
        job.status = SENT_PENDING_CONFIRMATION
        job.last_error = None
        _record_attempt(db, job, response.status_code, "queued", None)
        return

    if response.status_code == 400:
        # Never retry malformed requests - they'll never succeed.
        job.status = FAILED
        job.last_error = response.body.get("detail", "invalid_request")
        _record_attempt(db, job, 400, "invalid", job.last_error)
        return

    if should_retry(response.status_code):
        detail = response.body.get("error", f"http_{response.status_code}")
        job.last_error = detail
        outcome = "rate_limited" if response.status_code == 429 else "server_error"
        _record_attempt(db, job, response.status_code, outcome, detail)

        if has_attempts_remaining(job.attempt_count):
            job.status = PENDING
            job.next_attempt_at = next_attempt_at(job.attempt_count, response.retry_after_seconds)
        else:
            job.status = FAILED
        return

    # Any other unexpected status: treat conservatively as a permanent failure
    # rather than retrying forever against something we don't understand.
    job.status = FAILED
    job.last_error = f"unexpected_status_{response.status_code}"
    _record_attempt(db, job, response.status_code, "unexpected", job.last_error)


def run_once(db: Session) -> int:
    """
    Sends as many due jobs as the rate limit allows right now, one at a
    time, up to BATCH_SIZE per pass. Returns how many it actually sent
    (which may be fewer than were due, if the rate limit window is
    currently full - anything left over stays `pending` and gets picked up
    on a later pass, since job state lives in the database, not memory).
    """
    sent_count = 0
    for _ in range(BATCH_SIZE):
        if not can_send_now(db):
            break
        job = claim_one_due_job(db)
        if job is None:
            break
        send_one_job(db, job)
        db.commit()
        sent_count += 1
    return sent_count
