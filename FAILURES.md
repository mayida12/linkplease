# FAILURES.md

This is an honest list of known ways the system can still lose a DM, send a duplicate, or report an inaccurate number. These are deliberate tradeoffs for the scope of this assignment.

## 1. Crash after the mock API accepts a DM but before the database commit

The worker sends the DM to the mock API and then persists the returned `dm_id` and job status in Postgres. If the worker crashes after the API accepts the request but before our database transaction commits, the database may still show the job as `pending`.

After restart, the worker can retry the job. Because the original API call may already have succeeded, this creates a narrow possibility of sending the same logical DM twice.

A true solution would require stronger coordination between the database and external API, or a durable "send in progress / outcome unknown" state followed by reconciliation.

## 2. The send operation has an unavoidable external-API race window

The database transaction cannot atomically include the external HTTP request. If the process dies while the HTTP request is in flight, we cannot know from our database alone whether the mock API received the request.

We deliberately prefer retrying an uncertain job over silently losing a DM, but this means an extremely narrow duplicate-send window remains.

## 3. The rate limiter is safe for the documented single-worker deployment, but not fully atomic across multiple workers

The rate limiter counts recent send attempts in Postgres before allowing another send.

With one worker process, sends happen sequentially and the 10-requests-per-60-seconds limit is respected.

If multiple worker processes were allowed to send concurrently, two workers could theoretically check the limit at the same time and both observe an available slot. A production multi-worker implementation would use a database lock or another atomic rate-limiting mechanism around the check-and-record operation.

## 4. Reconciliation can leave a DM queued if status checks remain unavailable

After a successful send response, the job enters `sent_pending_confirmation` and the worker checks the mock API for the final delivery status.

If the mock API's status endpoint remains unavailable for an extended period, the job can remain unconfirmed indefinitely. We intentionally do not resend merely because a status check failed, because doing so could create a duplicate DM.

A production system would add monitoring and a separate policy for jobs that remain unconfirmed for too long.

## 5. Comment deletion only cancels jobs that are still pending

If a `comment.deleted` event arrives while its DM job is still pending, the job is cancelled.

If the DM has already been sent or is being reconciled, we leave it alone. Once an external DM has been sent, attempting to undo it is not possible through the provided mock API.

## 6. `/stats` is a live database snapshot

`/stats` is calculated from the current database state. During a high-volume load test, the numbers can change between requests while workers are processing events, sending DMs, retrying failures, and reconciling delivery statuses.

Therefore, intermediate `/stats` responses during an active load test should not be treated as the final result. The stable numbers after the queue has drained are the meaningful comparison point.

## 7. The implementation is intentionally optimized for the assignment's single-worker deployment

The worker uses Postgres as the durable source of truth for webhook events, deduplication, jobs, retries, and delivery attempts. Restarting the worker does not lose pending database-backed work.

For a production system at much larger scale, I would separate webhook ingestion, job processing, rate limiting, and reconciliation into independently scalable components and add stronger observability, alerting, and distributed coordination.