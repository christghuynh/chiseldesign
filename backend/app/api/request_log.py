"""INF-8: one log line per request — method, path, status, latency. Never bodies or keys.

Registered in app.main via `add_request_logging(app)`. Kept tiny and body-agnostic so it can
never leak an uploaded image, a measurement blob or an API key.
"""

from __future__ import annotations

import logging
import time

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

log = logging.getLogger("app.request")


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        start = time.perf_counter()
        status_code = 500

        async def _send(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            ms = (time.perf_counter() - start) * 1000
            log.info(
                "%s %s status=%d latency_ms=%.0f",
                request.method,
                request.url.path,
                status_code,
                ms,
            )


def _ensure_app_logging() -> None:
    """Make INFO lines from `app.*` loggers (this one, `app.ai` latency) visible under uvicorn.

    uvicorn only configures its own loggers; without this, Python's default WARNING level would
    silently drop them. Records still propagate to the root logger (pytest's caplog relies on it).
    """
    app_log = logging.getLogger("app")
    if not app_log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        app_log.addHandler(handler)
    if app_log.level == logging.NOTSET:
        app_log.setLevel(logging.INFO)


def add_request_logging(app) -> None:
    _ensure_app_logging()
    app.add_middleware(RequestLogMiddleware)
