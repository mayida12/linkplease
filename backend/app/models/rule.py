import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime
from app.database.session import Base


def new_id() -> str:
    return str(uuid.uuid4())


class Rule(Base):
    """A creator's automation rule: 'if a comment contains <keyword>, send <dm_message>'."""

    __tablename__ = "rules"

    id = Column(String, primary_key=True, default=new_id)
    keyword = Column(String, nullable=False)
    dm_message = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
