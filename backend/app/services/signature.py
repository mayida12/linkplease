"""
Webhook signature verification (Part B).

The mock API signs each webhook delivery with:

    X-PseudoGram-Signature: sha256=<hex>

where <hex> is HMAC-SHA256 of the *raw* request body, using our API key as
the shared secret. We must verify this using the exact bytes that were sent
- not a JSON.dumps() of the parsed body, which can differ from the original
in whitespace, key order, or number formatting and would make the signature
never match. That's why routes/webhook.py reads `await request.body()`
*before* doing any JSON parsing, and passes those raw bytes in here.
"""
import hashlib
import hmac

SIGNATURE_PREFIX = "sha256="


import base64

def compute_signature(raw_body: bytes, secret: str) -> str:
    """Returns the expected header value, e.g. 'sha256=abcd1234...'."""
    # The mock API expects the HMAC secret to be the decoded email address,
    # which is the first base64 part of the API key before the dot.
    if "." in secret:
        try:
            b64_part = secret.split(".")[0]
            # Python's b64decode requires correct padding; API keys often strip it
            b64_part += "=" * ((4 - len(b64_part) % 4) % 4)
            hmac_key = base64.b64decode(b64_part)
        except Exception:
            hmac_key = secret.encode("utf-8")
    else:
        hmac_key = secret.encode("utf-8")

    digest = hmac.new(hmac_key, raw_body, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def is_valid_signature(raw_body: bytes, header_value: str | None, secret: str) -> bool:
    """
    Returns True only if header_value is a well-formed 'sha256=<hex>' string
    whose hex digest matches what we compute ourselves.

    Uses hmac.compare_digest instead of `==` to compare digests in constant
    time, so an attacker can't use response-time differences to guess the
    correct signature one byte at a time (a timing attack).
    """
    if not header_value or not secret:
        return False
    if not header_value.startswith(SIGNATURE_PREFIX):
        return False

    expected = compute_signature(raw_body, secret)
    return hmac.compare_digest(expected, header_value)
