"""AI-10: a simple per-client-IP rate limiter, as a reusable FastAPI dependency.

Fixed-window counter: at most `RATE_LIMIT_PER_MIN` (default 20) requests per client IP per
60-second window. Over the limit -> ApiError 429 {code: RATE_LIMITED}. In-memory only (single
process); good enough for the demo. Read the limit from the env at call time so tests and .env
changes take effect without a restart.

Applied to /parse in this lane. Lane B wires it onto /edit, /instructions and /voice/* after the
merge (their routes don't exist here yet).
"""

from __future__ import annotations

import os
import threading
import time

from fastapi import Request

WINDOW_S = 60.0
DEFAULT_LIMIT = 20

_lock = threading.Lock()
# client key -> (window_start_epoch, count)
_hits: dict[str, tuple[float, int]] = {}


def limit_per_min() -> int:
    raw = os.environ.get("RATE_LIMIT_PER_MIN", "").strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_LIMIT
    return value if value > 0 else DEFAULT_LIMIT


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client and client.host else "unknown"


def reset() -> None:
    """Clear all counters (tests call this between cases)."""
    with _lock:
        _hits.clear()


def _check(key: str, limit: int, now: float) -> bool:
    """Return True if allowed. Fixed 60 s window per key."""
    with _lock:
        start, count = _hits.get(key, (now, 0))
        if now - start >= WINDOW_S:
            start, count = now, 0
        count += 1
        _hits[key] = (start, count)
        return count <= limit


class RateLimiter:
    """Dependency instance. `RateLimiter()` reads the env limit per request."""

    def __call__(self, request: Request) -> None:
        from app.api.errors import ApiError

        limit = limit_per_min()
        if not _check(_client_key(request), limit, time.monotonic()):
            raise ApiError(429, "RATE_LIMITED", f"Too many requests; the limit is {limit} per minute. Try again shortly.")


rate_limit = RateLimiter()
