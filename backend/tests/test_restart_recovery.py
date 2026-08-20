"""
There is no in-memory state in this system that matters for correctness -
every queue, every retry timer, every dedup claim lives in Postgres. So
"restarting the app" is modeled here simply as: throw away any Python
objects/sessions we were using, open a brand new DB session (as a freshly
started worker process would), and confirm the exact same unprocessed
event and pending job are still there and get handled correctly.
"""
from datetime import datetime, timezone

from app.database.session import SessionLocal
from app.models.dm_job import DmJob, PENDING, SENT_PENDING_CONFIRMATION
from app.models.webhook_event import WebhookEvent
from app.workers import event_processor, dm_sender
from tests.helpers import make_comment_event, post_event


def test_unprocessed_webhook_event_survives_a_simulated_restart(client, db):
    db.add_all([])  # no-op, just to use the fixture explicitly
    client.post("/rules", json={"keyword": "PRICE", "dm_message": "price info"})
    post_event(client, make_comment_event("evt_restart_1", "PRICE please", user_id="usr_restart"))

    # Confirm it's sitting there unprocessed, exactly like it would be if
    # the worker process had never started yet or had just crashed.
    stored = db.query(WebhookEvent).filter(WebhookEvent.event_id == "evt_restart_1").one()
    assert stored.processed is False

    # "Restart": open a brand new session, as a freshly-launched worker process would.
    with SessionLocal() as fresh_session:
        handled = event_processor.run_once(fresh_session)
        assert handled == 1

    db.expire_all()
    stored = db.query(WebhookEvent).filter(WebhookEvent.event_id == "evt_restart_1").one()
    assert stored.processed is True

    job = db.query(DmJob).filter(DmJob.recipient_user_id == "usr_restart").one()
    assert job.status == PENDING


def test_pending_dm_job_survives_a_simulated_restart_and_still_sends(db, monkeypatch):
    from app.services.mock_api_client import ApiResponse

    job = DmJob(
        rule_id="rule_1",
        webhook_event_id="evt_1",
        comment_id="cmt_1",
        recipient_user_id="usr_1",
        message="hello",
        status=PENDING,
        next_attempt_at=datetime.now(timezone.utc),
        idempotency_key="idem-restart-1",
    )
    db.add(job)
    db.commit()

    monkeypatch.setattr(
        dm_sender.mock_api_client,
        "send_dm",
        lambda **kwargs: ApiResponse(status_code=202, body={"dm_id": "dm_restart", "status": "queued"}),
    )

    # "Restart": fresh session, fresh call into the worker logic, no memory
    # of anything carried over from before.
    with SessionLocal() as fresh_session:
        sent = dm_sender.run_once(fresh_session)
        assert sent == 1

    db.expire_all()
    reloaded = db.get(DmJob, job.id)
    assert reloaded.status == SENT_PENDING_CONFIRMATION
    assert reloaded.dm_id == "dm_restart"
