"""Global routes — health, config, dispose."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.bus import EventBus
    from opencode.tui.state import AppState


def global_routes(bus: EventBus, state: AppState) -> list[Any]:
    """Global management routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def health(request: Request) -> JSONResponse:
        """Health check endpoint."""
        try:
            from importlib.metadata import version
            ver = version("opencode")
        except Exception:
            ver = "0.0.0-dev"
        return JSONResponse({
            "status": "ok",
            "version": ver,
        })

    async def get_global_config(request: Request) -> JSONResponse:
        """Get global configuration."""
        from opencode.config import load_config

        cfg = load_config()
        return JSONResponse({
            "model": cfg.model,
            "provider": cfg.provider,
            "theme": cfg.theme,
            "theme_mode": cfg.theme_mode,
        })

    async def patch_global_config(request: Request) -> JSONResponse:
        """Update global configuration."""
        body = await request.json()
        if "theme" in body:
            from opencode.tui.themes import set_theme

            set_theme(body["theme"])
        if "theme_mode" in body:
            from opencode.tui.themes import set_mode

            set_mode(body["theme_mode"])
        return JSONResponse({"status": "updated"})

    async def dispose(request: Request) -> JSONResponse:
        """Dispose all resources."""
        from opencode.bus import Event

        bus.publish(Event("global.disposed", ""))
        return JSONResponse({"status": "disposed"})

    return [
        Route("/global/health", health, methods=["GET"]),
        Route("/global/config", get_global_config, methods=["GET"]),
        Route("/global/config", patch_global_config, methods=["PATCH"]),
        Route("/global/dispose", dispose, methods=["POST"]),
    ]
