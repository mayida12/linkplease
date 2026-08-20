"""
Part C: delivery reconciliation.

A 202 from POST /v1/dm/send only means "accepted", not "delivered" - about
15% of accepted DMs later fail, per the mock API's documented behavior. This
worker periodically checks GET /v1/dm/{dm_id} for every job sitting in
SENT_PENDING_CONFIRMATION and moves it to its real final state.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_attempt import DeliveryAttempt
from app.models.dm_job import DmJob, SENT_PENDING_CONFIRMATION, DELIVERED, PENDING, FAILED
from app.services import mock_api_client
from app.services.retry_policy import next_attempt_at, has_attempts_remaining

BATCH_SIZE = 25


def claim_one_job_to_reconcile(db: Session) -> DmJob | None:
    """Locks a single job at a time - see the comment on dm_sender.claim_one_due_job
    for why we don't lock a whole batch up front."""
    stmt = (
        select(DmJob)
        .where(DmJob.status == SENT_PENDING_CONFIRMATION, DmJob.dm_id.is_not(None))
        .order_by(DmJob.updated_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return db.execute(stmt).scalars().first()


def reconcile_one_job(db: Session, job: DmJob) -> None:
    response = mock_api_client.get_dm_status(job.dm_id)

    if response.status_code != 200:
        # Couldn't check right now (mock API hiccup) - leave it as-is and
        # try again on the next reconciliation pass. We do NOT resend here;
        # the DM may well already be on its way.
        db.add(
            DeliveryAttempt(
                dm_job_id=job.id,
                attempt_number=job.attempt_count,
                action="reconcile",
                http_status=response.status_code,
                outcome="check_failed",
                detail=str(response.body),
            )
        )
        return

    status = response.body.get("status")
    db.add(
        DeliveryAttempt(
            dm_job_id=job.id,
            attempt_number=job.attempt_count,
            action="reconcile",
            http_status=200,
            outcome=status or "unknown",
            detail=None,
        )
    )

    if status == "delivered":
        job.status = DELIVERED
        job.last_error = None
    elif status == "failed":
        # The mock API accepted the send but the DM itself failed to
        # deliver. This counts as a fresh reason to retry (if we have
        # attempts left) using the same retry/backoff policy as an HTTP
        # failure - we just don't have an HTTP status code to key off, so
        # we treat it like a transient failure.
        job.last_error = "delivery_failed"
        if has_attempts_remaining(job.attempt_count):
            job.status = PENDING
            job.next_attempt_at = next_attempt_at(job.attempt_count)
            # A fresh idempotency key suffix (next attempt_count) is applied
            # automatically by dm_sender.send_one_job on the next attempt,
            # since it appends attempt_count itself.
        else:
            job.status = FAILED
    # status == "queued" -> still waiting, nothing to change; we'll check again.


def run_once(db: Session) -> int:
    checked = 0
    for _ in range(BATCH_SIZE):
        job = claim_one_job_to_reconcile(db)
        if job is None:
            break
        reconcile_one_job(db, job)
        db.commit()
        checked += 1
    return checked
