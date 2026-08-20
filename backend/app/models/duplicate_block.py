from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime
from app.database.session import Base
from app.models.rule import new_id


class DuplicateBlock(Base):
    """
    One row per time we correctly decided NOT to send a DM because that
    user had already been sent (or already claimed) a DM for that rule.
    COUNT(*) on this table is exactly the `duplicates_blocked` stat -
    there's no separate counter to keep in sync and risk drifting.
    """

    __tablename__ = "duplicate_blocks"

    id = Column(String, primary_key=True, default=new_id)
    rule_id = Column(String, nullable=False)
    recipient_user_id = Column(String, nullable=False)
    webhook_event_id = Column(String, nullable=False)
    blocked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
