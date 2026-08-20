from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer
from app.database.session import Base
from app.models.rule import new_id


class DeliveryAttempt(Base):
    """
    An audit trail row for every individual call we make to the mock API
    about a given DmJob (both the initial send and each reconciliation
    check). DmJob.status tells you "where things stand right now"; this
    table tells you "what actually happened, in order" - useful for
    debugging retries and for explaining exactly why a DM is stuck.
    """

    __tablename__ = "delivery_attempts"

    id = Column(String, primary_key=True, default=new_id)
    dm_job_id = Column(String, nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)

    action = Column(String, nullable=False)  # "send" | "reconcile"
    http_status = Column(Integer, nullable=True)
    outcome = Column(String, nullable=False)  # e.g. "queued", "rate_limited", "server_error", "invalid", "delivered", "failed"
    detail = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
