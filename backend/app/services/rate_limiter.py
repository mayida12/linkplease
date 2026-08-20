"""
Enforces "no more than N send requests per rolling window" against the mock
API's limit of 10 requests / 60 seconds.

Instead of an in-memory counter (which would reset on restart and be wrong
the moment you run more than one worker process), we count actual rows in
`delivery_attempts` where action='send' and created_at falls inside the
current rolling window. That table is written every time we genuinely call
POST /v1/dm/send - successful or not, because every one of those calls
counts against the mock API's limit, not just the ones that succeed.

This makes the limiter durable (a restart doesn't forget recent sends) and
correct by construction rather than by careful bookkeeping.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.config import settings
from app.models.delivery_attempt import DeliveryAttempt


def sends_in_current_window(db: Session) -> int:
    window_start = datetime.now(timezone.utc) - timedelta(
        seconds=settings.dm_rate_limit_window_seconds
    )
    stmt = select(func.count(DeliveryAttempt.id)).where(
        DeliveryAttempt.action == "send",
        DeliveryAttempt.created_at >= window_start,
    )
    return db.execute(stmt).scalar_one()


def can_send_now(db: Session) -> bool:
    return sends_in_current_window(db) < settings.dm_rate_limit_max
