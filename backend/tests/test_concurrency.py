import threading

from app.database.session import SessionLocal
from app.models.dm_dedup import DmDedup
from app.models.dm_job import DmJob
from app.models.duplicate_block import DuplicateBlock
from app.models.rule import Rule
from app.models.webhook_event import WebhookEvent
from app.workers.event_processor import process_one_event


def _make_event(db, event_id: str, rule_id: str, user_id: str) -> WebhookEvent:
    event = WebhookEvent(
        event_id=event_id,
        event_type="comment.created",
        comment_id=f"cmt_{event_id}",
        comment_text="PRICE please",
        from_user_id=user_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_concurrent_processing_of_same_user_only_creates_one_dm_job(db):
    """
    Simulates two worker threads independently processing two different
    comment events from the SAME user against the SAME rule, at (as close
    to) the same time as Python threads allow. Each thread uses its own DB
    session/connection, exactly like two separate worker processes would.

    This is what actually exercises the UniqueConstraint on DmDedup - a
    naive "check a Python set, then insert" approach could let both threads
    past the check before either one commits. Because our code relies on
    the database's own uniqueness guarantee (see event_processor._handle_comment_created),
    at most one of the two concurrent attempts can win.
    """
    rule = Rule(id="rule_concurrent", keyword="PRICE", dm_message="price info")
    db.add(rule)
    db.commit()

    event_a = _make_event(db, "evt_concurrent_a", rule.id, "usr_race")
    event_b = _make_event(db, "evt_concurrent_b", rule.id, "usr_race")

    results = {}
    start_barrier = threading.Barrier(2)

    def worker(event_id: str, key: str):
        with SessionLocal() as thread_db:
            local_event = thread_db.get(WebhookEvent, event_id)
            start_barrier.wait()  # line both threads up to maximize the chance of a real race
            process_one_event(thread_db, local_event)
            try:
                thread_db.commit()
                results[key] = "committed"
            except Exception as exc:
                thread_db.rollback()
                results[key] = f"error: {exc}"

    t1 = threading.Thread(target=worker, args=(event_a.id, "a"))
    t2 = threading.Thread(target=worker, args=(event_b.id, "b"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both threads should finish cleanly (our code catches the IntegrityError
    # itself via the SAVEPOINT, it doesn't let it blow up the whole commit).
    assert results == {"a": "committed", "b": "committed"}

    jobs = db.query(DmJob).filter(DmJob.recipient_user_id == "usr_race").all()
    dedup_rows = db.query(DmDedup).filter(
        DmDedup.rule_id == rule.id, DmDedup.recipient_user_id == "usr_race"
    ).all()
    blocks = db.query(DuplicateBlock).filter(DuplicateBlock.recipient_user_id == "usr_race").all()

    assert len(jobs) == 1, "exactly one of the two concurrent comments should win the DM"
    assert len(dedup_rows) == 1, "the unique constraint should leave exactly one dedup claim row"
    assert len(blocks) == 1, "the other concurrent attempt should be recorded as a blocked duplicate"
