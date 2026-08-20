from datetime import datetime, timezone

from app.models.dm_job import DmJob, DELIVERED, FAILED, PENDING, SENT_PENDING_CONFIRMATION
from app.models.duplicate_block import DuplicateBlock


def test_stats_reflects_live_job_counts(client, db):
    jobs = [
        DmJob(rule_id="r", webhook_event_id="e1", recipient_user_id="u1", message="m",
              status=DELIVERED, idempotency_key="k1"),
        DmJob(rule_id="r", webhook_event_id="e2", recipient_user_id="u2", message="m",
              status=DELIVERED, idempotency_key="k2"),
        DmJob(rule_id="r", webhook_event_id="e3", recipient_user_id="u3", message="m",
              status=FAILED, idempotency_key="k3"),
        DmJob(rule_id="r", webhook_event_id="e4", recipient_user_id="u4", message="m",
              status=PENDING, idempotency_key="k4",
              next_attempt_at=datetime.now(timezone.utc)),
        DmJob(rule_id="r", webhook_event_id="e5", recipient_user_id="u5", message="m",
              status=SENT_PENDING_CONFIRMATION, idempotency_key="k5"),
    ]
    db.add_all(jobs)
    db.add(DuplicateBlock(rule_id="r", recipient_user_id="u6", webhook_event_id="e6"))
    db.add(DuplicateBlock(rule_id="r", recipient_user_id="u7", webhook_event_id="e7"))
    db.commit()

    response = client.get("/stats")
    assert response.status_code == 200
    body = response.json()

    assert body["sent"] == 2
    assert body["failed"] == 1
    assert body["queued"] == 2  # PENDING + SENT_PENDING_CONFIRMATION
    assert body["duplicates_blocked"] == 2


def test_stats_on_empty_database_is_all_zeros(client):
    response = client.get("/stats")
    assert response.json() == {"sent": 0, "failed": 0, "queued": 0, "duplicates_blocked": 0}
