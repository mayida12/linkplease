import json

from app.config import settings
from app.services.signature import compute_signature


def make_comment_event(
    event_id: str,
    text: str,
    user_id: str = "usr_default",
    username: str = "some_user",
    comment_id: str | None = None,
    event_type: str = "comment.created",
) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "sent_at": "2026-08-10T09:14:22.481Z",
        "data": {
            "comment_id": comment_id or f"cmt_{event_id}",
            "post_id": "post_44de1b",
            "text": text,
            "created_at": "2026-08-10T09:14:21.900Z",
            "from": {"user_id": user_id, "username": username},
        },
    }


def signed_body(payload: dict) -> tuple[bytes, str]:
    """Returns (raw_body_bytes, signature_header_value) for posting to /webhook."""
    raw = json.dumps(payload).encode("utf-8")
    signature = compute_signature(raw, settings.mock_api_key)
    return raw, signature


def post_event(client, payload: dict, valid_signature: bool = True):
    raw, signature = signed_body(payload)
    if not valid_signature:
        signature = "sha256=" + "0" * 64
    return client.post(
        "/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "X-PseudoGram-Signature": signature},
    )
