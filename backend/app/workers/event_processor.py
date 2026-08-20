"""
Takes rows from `webhook_events` that haven't been processed yet and turns
each one into either:
  - nothing (event_type we don't act on, or no rule matched), or
  - a cancelled-in-advance job (comment.deleted for a comment we hadn't sent for), or
  - a new DmJob (comment.created matched a rule and this user hasn't been sent before), or
  - a DuplicateBlock row (comment.created matched a rule, but this user was
    already sent for that rule).

This is where the actual duplicate-prevention decision happens, and it
happens inside one DB transaction per event so the decision is atomic:
either we both record "this user is claimed" AND create the job, or
neither happens.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dm_dedup import DmDedup
from app.models.dm_job import DmJob
from app.models.duplicate_block import DuplicateBlock
from app.models.rule import Rule
from app.models.webhook_event import WebhookEvent
from app.services.matching import find_matching_rule

BATCH_SIZE = 25


def claim_unprocessed_events(db: Session) -> list[WebhookEvent]:
    """
    Locks a small batch of unprocessed events for this worker only.
    SKIP LOCKED means: if another worker process already has some of these
    rows locked, just skip them and grab different ones, instead of
    blocking and waiting. That's what lets you safely run more than one
    worker process without them fighting over the same rows.
    """
    stmt = (
        select(WebhookEvent)
        .where(WebhookEvent.processed.is_(False))
        .order_by(WebhookEvent.received_at.asc())
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    return list(db.execute(stmt).scalars().all())


def _handle_comment_created(db: Session, event: WebhookEvent) -> str:
    if not event.from_user_id or not event.comment_text:
        return "missing user_id or comment text"

    rules = db.query(Rule).all()
    matched_rule = find_matching_rule(event.comment_text, rules)
    if matched_rule is None:
        return "no matching rule"

    # Try to atomically claim (rule, user). This is the single source of
    # truth for "has this user already been sent this rule's DM" - not an
    # in-memory set, not a pre-check-then-insert (which would have a race
    # window between the check and the insert).
    #
    # We do this inside a SAVEPOINT (db.begin_nested), not the outer
    # transaction directly: run_once() processes a whole batch of events
    # and only commits once at the end, so if we let the IntegrityError
    # roll back the *outer* transaction, we'd also wipe out every other
    # event's work done earlier in the same batch. A savepoint lets us
    # undo just this one failed insert and keep going.
    try:
        with db.begin_nested():
            db.add(DmDedup(rule_id=matched_rule.id, recipient_user_id=event.from_user_id))
    except IntegrityError:
        db.add(
            DuplicateBlock(
                rule_id=matched_rule.id,
                recipient_user_id=event.from_user_id,
                webhook_event_id=event.id,
            )
        )
        return f"duplicate blocked for rule {matched_rule.id}"

    job = DmJob(
        rule_id=matched_rule.id,
        webhook_event_id=event.id,
        comment_id=event.comment_id,
        recipient_user_id=event.from_user_id,
        message=matched_rule.dm_message,
        idempotency_key=str(uuid.uuid4()),
    )
    db.add(job)
    return f"queued dm job for rule {matched_rule.id}"


def _handle_comment_deleted(db: Session, event: WebhookEvent) -> str:
    """
    If a comment gets deleted before we've sent its DM, cancel the pending
    job rather than sending a DM that's now irrelevant. If a DM already
    went out (or is already in flight past "pending"), we leave it alone -
    it's simpler and safer to let an already-in-progress send finish than
    to try to interrupt it.
    """
    if not event.comment_id:
        return "no comment_id on delete event"

    pending_job = (
        db.query(DmJob)
        .filter(DmJob.comment_id == event.comment_id, DmJob.status == "pending")
        .with_for_update()
        .first()
    )
    if pending_job is None:
        return "no pending job for this comment"

    pending_job.status = "cancelled"
    return f"cancelled job {pending_job.id}"


def process_one_event(db: Session, event: WebhookEvent) -> None:
    if event.event_type == "comment.created":
        note = _handle_comment_created(db, event)
    elif event.event_type == "comment.deleted":
        note = _handle_comment_deleted(db, event)
    else:
        note = f"unhandled event_type: {event.event_type}"

    event.processed = True
    event.process_note = note


def run_once(db: Session) -> int:
    """Processes one batch of unprocessed events. Returns how many it handled."""
    events = claim_unprocessed_events(db)
    for event in events:
        process_one_event(db, event)
    db.commit()
    return len(events)
