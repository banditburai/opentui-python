"""MCP routes — server status, connect, disconnect."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.tui.state import AppState


def mcp_routes(state: AppState) -> list[Any]:
    """MCP server management routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def get_mcp_status(request: Request) -> JSONResponse:
        """Get MCP server connection status."""
        from opencode.config import load_config

        cfg = load_config()
        servers = []
        mcp_data = cfg.mcp or {}
        for name, server_cfg in mcp_data.items():
            if isinstance(server_cfg, dict):
                servers.append({
                    "name": name,
                    "command": server_cfg.get("command", ""),
                    "status": "configured",
                })
        return JSONResponse(servers)

    async def connect_mcp(request: Request) -> JSONResponse:
        """Connect to an MCP server."""
        return JSONResponse(
            {"error": "MCP connect is not yet implemented"},
            status_code=501,
        )

    async def disconnect_mcp(request: Request) -> JSONResponse:
        """Disconnect from an MCP server."""
        return JSONResponse(
            {"error": "MCP disconnect is not yet implemented"},
            status_code=501,
        )

    return [
        Route("/mcp", get_mcp_status, methods=["GET"]),
        Route("/mcp/connect", connect_mcp, methods=["POST"]),
        Route("/mcp/disconnect", disconnect_mcp, methods=["POST"]),
    ]
