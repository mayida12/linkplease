from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer
from app.database.session import Base
from app.models.rule import new_id

# Valid values for DmJob.status. Kept as plain strings (not a DB enum type)
# so adding a new status later doesn't require a migration to alter a
# Postgres enum type - simpler for a small project like this.
PENDING = "pending"                                # waiting to be sent, or waiting to be retried
SENT_PENDING_CONFIRMATION = "sent_pending_confirmation"  # mock API returned 202, we're waiting on reconciliation
DELIVERED = "delivered"                             # reconciliation confirmed delivery -> counts as "sent"
FAILED = "failed"                                   # gave up (400, or retries exhausted)
CANCELLED = "cancelled"                              # comment was deleted before we sent the DM


class DmJob(Base):
    """One DM we intend to send (or have sent) because a rule matched a comment."""

    __tablename__ = "dm_jobs"

    id = Column(String, primary_key=True, default=new_id)

    rule_id = Column(String, nullable=False)
    webhook_event_id = Column(String, nullable=False)
    comment_id = Column(String, nullable=True)
    recipient_user_id = Column(String, nullable=False)
    message = Column(String, nullable=False)

    status = Column(String, nullable=False, default=PENDING)

    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_error = Column(String, nullable=True)

    # Set once the mock API accepts the send (202) and gives us a dm_id.
    dm_id = Column(String, nullable=True, index=True)

    # Sent as the Idempotency-Key header on every send attempt for this job,
    # so if our HTTP call to the mock API is retried at the network layer
    # (e.g. we sent the request but the response was lost), the mock API
    # won't create a second DM for the same attempt.
    idempotency_key = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
