# FAILURES.md

This is an honest list of known limitations and failure scenarios in the current implementation.

## 1. Crash after the DM is accepted but before the database is updated

If the worker crashes after the mock API accepts a DM but before the returned `dm_id` and status are committed to PostgreSQL, the job may still appear as `pending`.

After restart, the worker can retry it, which creates a small possibility of sending the same DM twice.

A production solution would require stronger idempotency support from the external API or a durable reconciliation mechanism for uncertain requests.

## 2. External API request can fail in an unknown state

The database transaction and external HTTP request cannot be atomic.

If the process crashes while a request is in flight, the system cannot know whether the mock API received it. Retrying protects against losing the DM but leaves a narrow duplicate-send possibility.

## 3. Rate limiting assumes a single worker

The rate limiter stores send attempts in PostgreSQL and correctly enforces the 10 requests / 60 seconds limit with the intended single-worker deployment.

If multiple workers send concurrently, two workers could check the limit at the same time and both see an available slot.

A production implementation would use an atomic database lock or distributed rate limiter.

## 4. Delivery confirmation can remain pending

A `202` response means the mock API accepted the DM but does not guarantee delivery.

The job therefore enters `sent_pending_confirmation` and is reconciled through the mock API. If the status endpoint remains unavailable, the job can remain unconfirmed.

The system intentionally does not resend in this situation because doing so could create a duplicate DM.

## 5. Deleted comments cannot cancel an already-sent DM

A `comment.deleted` event cancels the DM only while the job is still `pending`.

Once the DM has been sent or is being reconciled, it is left unchanged because the provided API does not support safely undoing an already-sent DM.

## 6. `/stats` is a live database snapshot

`/stats` reflects the current database state.

During active processing, values can temporarily change as jobs move between `pending`, `sent_pending_confirmation`, `delivered`, and `failed`.

The final numbers should therefore be compared after the queue has finished processing.

## 7. Single-worker architecture

The current implementation intentionally uses one worker process with PostgreSQL as the durable source of truth.

For production-scale traffic, I would separate ingestion, job processing, rate limiting, and reconciliation into independently scalable workers and add distributed coordination, monitoring, and alerting.
