"""
Load test driver for the mock API's built-in simulator.

I could NOT run this myself - it requires outbound internet access to
https://pseudogram-api.onrender.com and a publicly reachable deployment of
this app for the mock API to send webhooks to, neither of which is
available in the sandbox this project was built in. You need to run this
yourself after deploying. See the README "Load test" section for exactly
what to check.

Usage:
    python scripts/load_test.py \\
        --webhook-url https://your-deployed-app.example.com/webhook \\
        --api-key <your MOCK_API_KEY> \\
        --stats-url https://your-deployed-app.example.com/stats \\
        --count 500 --duration 10
"""
import argparse
import time

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock-api-base-url", default="https://pseudogram-api.onrender.com")
    parser.add_argument("--webhook-url", required=True, help="your deployed app's /webhook URL")
    parser.add_argument("--stats-url", required=True, help="your deployed app's /stats URL")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--wait-after", type=int, default=120,
                         help="seconds to keep polling /stats after the simulation window ends, "
                              "to let retries/rate-limited sends and reconciliation catch up")
    args = parser.parse_args()

    headers = {"X-API-Key": args.api_key}
    client = httpx.Client(timeout=30.0)

    before_stats = client.get(args.stats_url).json()
    print(f"stats before: {before_stats}")

    print(f"Starting simulation: {args.count} events over {args.duration}s -> {args.webhook_url}")
    start_resp = client.post(
        f"{args.mock_api_base_url}/v1/simulate/start",
        json={"webhook_url": args.webhook_url, "count": args.count, "duration_seconds": args.duration},
        headers=headers,
    )
    start_resp.raise_for_status()
    run_id = start_resp.json()["run_id"]
    print(f"run_id = {run_id}")

    # Let the simulation finish, then give the app time to work through its
    # queue (rate limiting means 500 DMs at 10/60s takes roughly 50 minutes
    # in the worst case if every comment matches a rule for a distinct
    # user - adjust --wait-after accordingly for a real run).
    time.sleep(args.duration)

    deadline = time.time() + args.wait_after
    while time.time() < deadline:
        stats = client.get(args.stats_url).json()
        print(f"  current stats: {stats}")
        time.sleep(5)

    truth_resp = client.get(f"{args.mock_api_base_url}/v1/simulate/{run_id}/truth", headers=headers)
    truth_resp.raise_for_status()
    truth = truth_resp.json()

    final_stats = client.get(args.stats_url).json()

    print("\n--- RESULTS ---")
    print(f"mock API's truth: {truth}")
    print(f"our final stats:  {final_stats}")
    print(
        "\nCompare these by hand: every event the mock API's truth says should have produced a DM "
        "should be reflected in our 'sent' (or still 'queued' if rate-limiting/retries haven't "
        "finished, or 'failed' if attempts were exhausted). See README for how to interpret gaps."
    )


if __name__ == "__main__":
    main()
