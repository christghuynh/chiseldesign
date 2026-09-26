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


def add_request_logging(app) -> None:
    app.add_middleware(RequestLogMiddleware)
