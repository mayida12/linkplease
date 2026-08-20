from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, UniqueConstraint
from app.database.session import Base
from app.models.rule import new_id


class DmDedup(Base):
    """
    The actual duplicate-prevention mechanism.

    One row means "this user has already been claimed for a DM from this
    rule". Before creating a DmJob, the worker tries to INSERT a row here
    inside a transaction. Because of the UniqueConstraint below, a second
    attempt to insert the same (rule_id, recipient_user_id) pair fails at
    the database level - this works correctly even if two worker processes
    (or two webhook deliveries processed concurrently) try it at the exact
    same time, which a plain "check a Python set, then decide" approach
    would not guarantee.
    """

    __tablename__ = "dm_dedup"
    __table_args__ = (
        UniqueConstraint("rule_id", "recipient_user_id", name="uq_dm_dedup_rule_user"),
    )

    id = Column(String, primary_key=True, default=new_id)
    rule_id = Column(String, nullable=False)
    recipient_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
