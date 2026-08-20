"""
Pure calculation of "how long until the next retry", kept separate from
any HTTP or DB code so it's trivial to unit test and reason about.
"""
from datetime import datetime, timedelta, timezone

from app.config import settings


def should_retry(http_status: int) -> bool:
    """
    500 and 429 are transient - retry them.
    400 is a client error (malformed request) - never retry it, per the
    assignment's explicit rule.
    """
    return http_status == 500 or http_status == 429


def next_attempt_delay_seconds(attempt_count: int, retry_after_header: int | None = None) -> int:
    """
    attempt_count is the number of attempts made SO FAR (including the one
    that just failed). Returns how many seconds to wait before the next try.

    - If the mock API gave us a Retry-After value (only sent on 429), we
      respect it exactly, since that's the server telling us precisely when
      it'll accept requests again.
    - Otherwise we use exponential backoff: base * 2^(attempt_count - 1),
      capped at a maximum so a job doesn't end up waiting an absurd amount
      of time.
    """
    if retry_after_header is not None:
        return max(retry_after_header, 0)

    delay = settings.dm_retry_base_seconds * (2 ** max(attempt_count - 1, 0))
    return min(delay, settings.dm_retry_max_seconds)


def next_attempt_at(attempt_count: int, retry_after_header: int | None = None) -> datetime:
    delay = next_attempt_delay_seconds(attempt_count, retry_after_header)
    return datetime.now(timezone.utc) + timedelta(seconds=delay)


def has_attempts_remaining(attempt_count: int) -> bool:
    return attempt_count < settings.dm_max_attempts
