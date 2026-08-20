from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Boolean
from app.database.session import Base
from app.models.rule import new_id


class WebhookEvent(Base):
    """
    Every comment event we receive from the mock Instagram API, exactly as
    persisted the moment /webhook accepts it - before any processing.

    `event_id` has a UNIQUE constraint. That's what makes duplicate webhook
    deliveries safe: if the same event_id arrives twice, the second INSERT
    is rejected at the database level (we catch that and just return 200
    without reprocessing), rather than trusting an in-memory "have I seen
    this before?" set that would be wiped out on restart or wouldn't be
    shared across multiple API server processes.
    """

    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=new_id)
    event_id = Column(String, unique=True, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # "comment.created" | "comment.deleted"

    post_id = Column(String, nullable=True)
    comment_id = Column(String, nullable=True)
    comment_text = Column(String, nullable=True)

    # The commenter's identity. We store user_id (stable) and username
    # (for display only) separately - user_id is what we key dedup on,
    # per the assignment rules, because usernames can change.
    from_user_id = Column(String, nullable=True)
    from_username = Column(String, nullable=True)

    event_sent_at = Column(DateTime(timezone=True), nullable=True)  # sent_at from the payload
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Has the background worker finished acting on this event yet?
    processed = Column(Boolean, default=False, nullable=False)
    process_note = Column(String, nullable=True)  # e.g. "no matching rule", "duplicate blocked"
