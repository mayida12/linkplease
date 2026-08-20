"""
Thin wrapper around the mock Instagram API's DM endpoints.

Deliberately "thin": it does one HTTP call and hands back the raw pieces
(status code, parsed body, Retry-After header) rather than deciding what
to do about them. Deciding what a 429 vs a 500 vs a 202 *means* for a job
is the worker's job (see workers/dm_sender.py) - keeping that decision out
of this file makes both halves easier to test and read independently.
"""
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import settings


@dataclass
class ApiResponse:
    status_code: int
    body: dict[str, Any]
    retry_after_seconds: Optional[int] = None


def _headers(idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "X-API-Key": settings.mock_api_key,
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def send_dm(
    recipient_user_id: str,
    message: str,
    comment_id: str | None,
    idempotency_key: str,
    timeout_seconds: float = 10.0,
) -> ApiResponse:
    url = f"{settings.mock_api_base_url}/v1/dm/send"
    payload = {
        "recipient_user_id": recipient_user_id,
        "message": message,
        "comment_id": comment_id,
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=payload, headers=_headers(idempotency_key))

    retry_after = None
    if response.status_code == 429:
        header_val = response.headers.get("Retry-After")
        if header_val is not None:
            try:
                retry_after = int(header_val)
            except ValueError:
                retry_after = None

    try:
        body = response.json()
    except ValueError:
        body = {}

    return ApiResponse(status_code=response.status_code, body=body, retry_after_seconds=retry_after)


def get_dm_status(dm_id: str, timeout_seconds: float = 10.0) -> ApiResponse:
    url = f"{settings.mock_api_base_url}/v1/dm/{dm_id}"
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(url, headers=_headers())

    try:
        body = response.json()
    except ValueError:
        body = {}

    return ApiResponse(status_code=response.status_code, body=body)
