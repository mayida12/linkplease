from app.models.webhook_event import WebhookEvent
from tests.helpers import make_comment_event, post_event


# --- Test 13: valid signature is accepted -----------------------------------

def test_valid_signature_is_accepted(client, db):
    event = make_comment_event("evt_sig_ok", "hello world")
    response = post_event(client, event, valid_signature=True)

    assert response.status_code == 200
    stored = db.query(WebhookEvent).filter(WebhookEvent.event_id == "evt_sig_ok").first()
    assert stored is not None


# --- Test 12: invalid signature is rejected ---------------------------------

def test_invalid_signature_is_rejected(client, db):
    event = make_comment_event("evt_sig_bad", "hello world")
    response = post_event(client, event, valid_signature=False)

    assert response.status_code == 401
    stored = db.query(WebhookEvent).filter(WebhookEvent.event_id == "evt_sig_bad").first()
    assert stored is None  # rejected before it was ever persisted


def test_missing_signature_header_is_rejected(client, db):
    import json

    raw = json.dumps(make_comment_event("evt_sig_missing", "hello world")).encode("utf-8")
    response = client.post("/webhook", content=raw, headers={"Content-Type": "application/json"})

    assert response.status_code == 401


def test_signature_computed_over_reparsed_json_would_still_be_wrong(client, db):
    """
    Guards against a subtle bug: if the code ever "helpfully" parsed the
    body to JSON and re-serialized it before checking the signature, a
    real signature (computed over the ORIGINAL bytes) would stop matching
    the moment key order or spacing changed. We post body bytes with
    non-canonical spacing to make sure verification is happening against
    the exact raw bytes, not a round-tripped version of them.
    """
    import json
    from app.config import settings
    from app.services.signature import compute_signature

    payload = make_comment_event("evt_sig_spacing", "hello world")
    # Deliberately unusual formatting (extra spaces) that json.dumps()
    # would not reproduce if the body were parsed and re-serialized.
    raw = json.dumps(payload, indent=4).encode("utf-8")
    signature = compute_signature(raw, settings.mock_api_key)

    response = client.post(
        "/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "X-PseudoGram-Signature": signature},
    )

    assert response.status_code == 200
