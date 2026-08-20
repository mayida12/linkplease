import json
from app.services.signature import compute_signature, is_valid_signature
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Request, HTTPException
# pyrefly: ignore [missing-import]
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.config import settings
from app.database.session import get_db
from app.models.webhook_event import WebhookEvent
from app.schemas.webhook import WebhookEventIn


router = APIRouter()

SIGNATURE_HEADER = "X-PseudoGram-Signature"


@router.post("/webhook", status_code=200)
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """
    This route must do as little work as possible and return fast (the
    spec requires < 5s, but really it should be milliseconds): verify the
    signature, persist one row, done. No rule matching, no calls to the
    mock API happen here - that's all done later by the background worker
    polling `webhook_events` for unprocessed rows (see workers/event_processor.py).
    """
    # IMPORTANT: read the raw bytes BEFORE any JSON parsing. The signature
    # is computed over the exact bytes the mock API sent - re-serializing
    # parsed JSON could produce different bytes (key order, spacing, number
    # formatting) and would make a legitimate signature look invalid.
    raw_body = await request.body()


    signature_header = request.headers.get(SIGNATURE_HEADER)

    if not is_valid_signature(raw_body, signature_header, settings.mock_api_key):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = WebhookEventIn.model_validate_json(raw_body)
    except (ValidationError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="malformed event payload")

    comment = payload.data
    event = WebhookEvent(
        event_id=payload.event_id,
        event_type=payload.event_type,
        post_id=comment.post_id,
        comment_id=comment.comment_id,
        comment_text=comment.text,
        from_user_id=comment.from_.user_id if comment.from_ else None,
        from_username=comment.from_.username if comment.from_ else None,
        event_sent_at=payload.sent_at,
    )

    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # event_id already exists (webhook_events.event_id is UNIQUE).
        # This is the mock API re-delivering an event we've already
        # accepted. We still return 200 - the sender shouldn't retry
        # something we've already got - we just don't insert it again,
        # which means the worker will never see it as "new" and won't
        # reprocess it.
        db.rollback()

    return {"status": "accepted"}
