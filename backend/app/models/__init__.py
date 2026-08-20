"""
Importing every model here means one `import app.models` (which
`Base.metadata.create_all` and Alembic both rely on) is enough to register
every table with SQLAlchemy's metadata.
"""
from app.models.rule import Rule
from app.models.webhook_event import WebhookEvent
from app.models.dm_dedup import DmDedup
from app.models.dm_job import DmJob
from app.models.delivery_attempt import DeliveryAttempt
from app.models.duplicate_block import DuplicateBlock

__all__ = [
    "Rule",
    "WebhookEvent",
    "DmDedup",
    "DmJob",
    "DeliveryAttempt",
    "DuplicateBlock",
]
