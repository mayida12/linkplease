from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommentFrom(BaseModel):
    user_id: str
    username: Optional[str] = None


class CommentData(BaseModel):
    # "from" is a reserved word in Python, so the JSON field "from" is
    # aliased to the Python attribute "from_".
    model_config = {"populate_by_name": True}

    comment_id: Optional[str] = None
    post_id: Optional[str] = None
    text: Optional[str] = None
    created_at: Optional[datetime] = None
    from_: Optional[CommentFrom] = Field(default=None, alias="from")


class WebhookEventIn(BaseModel):
    event_id: str
    event_type: str
    sent_at: Optional[datetime] = None
    data: CommentData
