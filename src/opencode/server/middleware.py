"""Server middleware — CORS, logging, timing."""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)


def cors_middleware(app: Any, *, allow_origins: list[str] | None = None) -> Any:
    """Wrap a Starlette app with CORS headers.

    Defaults to localhost-only origins for security.
    """
    from starlette.middleware.cors import CORSMiddleware

    if allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Restrict to localhost by default
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
            allow_methods=["*"],
            allow_headers=["*"],
        )
    return app


def logging_middleware(app: Any) -> Any:
    """Add request logging middleware."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class LogMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Any) -> Response:
            start = time.monotonic()
            response = await call_next(request)
            elapsed = (time.monotonic() - start) * 1000
            log.debug(
                "%s %s %d %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                elapsed,
            )
            return response

    app.add_middleware(LogMiddleware)
    return app
