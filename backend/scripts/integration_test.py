"""
Integration test script (not pytest) - exercises a REAL running instance of
this app (API server + worker both need to be running) over HTTP, the same
way the actual mock Instagram API would.

This is different from the pytest suite: the pytest suite calls Python
functions directly against a test database. This script only talks to
whatever BASE_URL you point it at, so you can run it against your local
dev server or against your deployed URL.

Usage:
    python scripts/integration_test.py --base-url http://localhost:8000 --api-key <your MOCK_API_KEY>

What it does:
    1. Creates a rule for keyword PRICE.
    2. Sends 5 webhook events, correctly signed:
       - 3 comments from the same user matching PRICE (should → 1 DM, 2 blocked duplicates)
       - 1 duplicate delivery of the same event_id (should not double-count)
       - 1 comment from a different user matching PRICE (should → 1 more DM)
    3. Polls GET /stats until the worker has caught up (or times out).
    4. Asserts the numbers match what should have happened.

NOTE: this only checks that jobs reach "queued" (accepted by the app) -
whether they actually reach "sent" depends on the mock API being reachable,
since that's a real HTTP dependency. See the README for exactly what to
verify manually after deploying.
"""
import argparse
import hashlib
import hmac
import json
import sys
import time

import httpx


def sign(body: bytes, secret: str) -> str:
    import base64

    b64_part = secret.split(".")[0]
    b64_part += "=" * ((4 - len(b64_part) % 4) % 4)
    hmac_key = base64.b64decode(b64_part)

    digest = hmac.new(hmac_key, body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def make_event(event_id, text, user_id, comment_id, event_type="comment.created"):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "sent_at": "2026-08-10T09:14:22.481Z",
        "data": {
            "comment_id": comment_id,
            "post_id": "post_test",
            "text": text,
            "created_at": "2026-08-10T09:14:21.900Z",
            "from": {"user_id": user_id, "username": f"{user_id}_name"},
        },
    }


def post_webhook(client: httpx.Client, base_url: str, secret: str, event: dict) -> httpx.Response:
    raw = json.dumps(event).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-PseudoGram-Signature": sign(raw, secret)}
    return client.post(f"{base_url}/webhook", content=raw, headers=headers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", required=True, help="must match the server's MOCK_API_KEY")
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for the worker")
    args = parser.parse_args()

    client = httpx.Client()
    base_url = args.base_url.rstrip("/")

    print(f"Creating rule against {base_url} ...")
    rule_resp = client.post(
        f"{base_url}/rules", json={"keyword": "PRICE", "dm_message": "Here's the price list"}
    )
    assert rule_resp.status_code == 201, f"expected 201, got {rule_resp.status_code}: {rule_resp.text}"
    print(f"  created rule {rule_resp.json()['rule_id']}")

    before = client.get(f"{base_url}/stats").json()
    print(f"stats before: {before}")

    events = [
        make_event("itest_evt_1", "PRICE please", "itest_user_a", "cmt_1"),
        make_event("itest_evt_2", "what's the PRICE?", "itest_user_a", "cmt_2"),
        make_event("itest_evt_3", "PRICE", "itest_user_a", "cmt_3"),
        make_event("itest_evt_1", "PRICE please", "itest_user_a", "cmt_1"),  # duplicate event_id
        make_event("itest_evt_4", "PRICE", "itest_user_b", "cmt_4"),
    ]

    for event in events:
        response = post_webhook(client, base_url, args.api_key, event)
        assert response.status_code == 200, f"webhook rejected: {response.status_code} {response.text}"
    print(f"posted {len(events)} webhook deliveries (including one duplicate event_id)")

    # Give the background worker a moment to process the events. We only
    # expect "queued" to have moved - whether jobs then reach "sent"
    # depends on the mock API being reachable from wherever the app runs.
    expected_new_queued_or_sent = 2  # user_a should get exactly 1 DM job, user_b exactly 1
    deadline = time.time() + args.timeout
    after = before
    while time.time() < deadline:
        after = client.get(f"{base_url}/stats").json()
        in_flight_or_done = (
            (after["sent"] - before["sent"])
            + (after["failed"] - before["failed"])
            + (after["queued"] - before["queued"])
        )
        if in_flight_or_done >= expected_new_queued_or_sent:
            break
        time.sleep(1)

    print(f"stats after:  {after}")

    new_duplicates = after["duplicates_blocked"] - before["duplicates_blocked"]
    assert new_duplicates == 2, (
        f"expected 2 new duplicates_blocked (the 2 extra PRICE comments from itest_user_a), "
        f"got {new_duplicates}"
    )
    print("PASS: duplicates_blocked increased by exactly 2")

    new_jobs = in_flight_or_done
    assert new_jobs == expected_new_queued_or_sent, (
        f"expected exactly {expected_new_queued_or_sent} new dm jobs total "
        f"(sent+failed+queued combined), got {new_jobs}"
    )
    print(f"PASS: exactly {expected_new_queued_or_sent} new dm job(s) created "
          f"(one for itest_user_a, one for itest_user_b)")

    print("\nIntegration test PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\nIntegration test FAILED: {e}")
        sys.exit(1)
