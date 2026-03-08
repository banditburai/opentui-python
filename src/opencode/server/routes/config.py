"""Config routes — GET/PATCH configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.tui.state import AppState


def config_routes(state: AppState) -> list[Any]:
    """Configuration routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def get_config(request: Request) -> JSONResponse:
        """Return current configuration."""
        from opencode.config import load_config

        cfg = load_config()
        return JSONResponse({
            "model": cfg.model,
            "theme": cfg.theme,
            "theme_mode": cfg.theme_mode,
            "provider": cfg.provider,
        })

    async def patch_config(request: Request) -> JSONResponse:
        """Update configuration fields."""
        body = await request.json()
        # Config updates are applied in memory — not persisted to file
        if "theme" in body:
            from opencode.tui.themes import set_theme

            set_theme(body["theme"])
        if "theme_mode" in body:
            from opencode.tui.themes import set_mode

            set_mode(body["theme_mode"])
        return JSONResponse({"status": "updated"})

    async def get_providers_config(request: Request) -> JSONResponse:
        """Return configured providers."""
        from opencode.config import load_config

        cfg = load_config()
        return JSONResponse({
            "provider": cfg.provider,
            "model": cfg.model,
        })

    return [
        Route("/config", get_config, methods=["GET"]),
        Route("/config", patch_config, methods=["PATCH"]),
        Route("/config/providers", get_providers_config, methods=["GET"]),
    ]
