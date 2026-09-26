"""AI-10: a simple per-client-IP rate limiter, as a reusable FastAPI dependency.

Fixed-window counter per (scope, client IP): each route group gets its own budget, so a burst on
one (Build mode prefetches TTS for every step at once) can't lock a user out of the others.

- `/parse`, `/edit`, `/instructions`, `/voice/stt`: `RATE_LIMIT_PER_MIN` (default 20) each.
- `/voice/tts`: `RATE_LIMIT_TTS_PER_MIN` (default 120); one build prefetches ~a dozen clips and
  replays are cache hits, so the general limit would be too tight.

Over the limit -> ApiError 429 {code: RATE_LIMITED}. In-memory only (single process); good enough
for the demo VM. Limits are read from the env at call time so tests and .env changes take effect
without a restart. Behind Caddy the client IP comes from X-Forwarded-For (uvicorn --proxy-headers).
"""

from __future__ import annotations

import os
import threading
import time

from fastapi import Request

WINDOW_S = 60.0
DEFAULT_LIMIT = 20

_lock = threading.Lock()
# "scope:client" -> (window_start_epoch, count)
_hits: dict[str, tuple[float, int]] = {}


def limit_per_min(env_var: str = "RATE_LIMIT_PER_MIN", default: int = DEFAULT_LIMIT) -> int:
    raw = os.environ.get(env_var, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


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
    """Dependency instance: one budget per (scope, client IP), limit read from `env_var` per request."""

    def __init__(self, scope: str, env_var: str = "RATE_LIMIT_PER_MIN", default: int = DEFAULT_LIMIT):
        self.scope, self.env_var, self.default = scope, env_var, default

    def __call__(self, request: Request) -> None:
        from app.api.errors import ApiError

        limit = limit_per_min(self.env_var, self.default)
        if not _check(f"{self.scope}:{_client_key(request)}", limit, time.monotonic()):
            raise ApiError(429, "RATE_LIMITED", f"Too many requests; the limit is {limit} per minute. Try again shortly.")


rate_limit = RateLimiter("parse")
edit_rate_limit = RateLimiter("edit")
instructions_rate_limit = RateLimiter("instructions")
stt_rate_limit = RateLimiter("voice_stt")
tts_rate_limit = RateLimiter("voice_tts", env_var="RATE_LIMIT_TTS_PER_MIN", default=120)
