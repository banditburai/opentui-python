"""Starlette application factory for the OpenCode web API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opencode.bus import EventBus
    from opencode.tui.state import AppState


def create_app(bus: EventBus, state: AppState) -> object:
    """Create and return a Starlette ASGI app.

    Requires ``starlette`` and ``sse-starlette`` to be installed.
    """
    try:
        from starlette.applications import Starlette
    except ImportError as e:
        raise ImportError(
            "starlette is required for the web server: pip install starlette sse-starlette uvicorn"
        ) from e

    from .routes import collect_routes

    routes = collect_routes(bus, state)
    app = Starlette(routes=routes)

    # Apply middleware
    from .middleware import cors_middleware, logging_middleware

    cors_middleware(app)
    logging_middleware(app)

    return app
