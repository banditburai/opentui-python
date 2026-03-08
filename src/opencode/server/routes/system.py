"""System routes — path, vcs, commands, agents, skills."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.tui.state import AppState


def system_routes(state: AppState) -> list[Any]:
    """System information routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def get_paths(request: Request) -> JSONResponse:
        """Get relevant paths."""
        return JSONResponse({
            "cwd": os.getcwd(),
            "home": str(Path.home()),
            "data": str(Path.home() / ".local" / "share" / "opencode"),
            "config": str(Path.home() / ".config" / "opencode"),
        })

    async def get_vcs(request: Request) -> JSONResponse:
        """Get VCS (git) information."""
        def _git_info() -> dict[str, Any]:
            try:
                branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=5,
                ).strip()
                dirty = bool(subprocess.check_output(
                    ["git", "status", "--porcelain"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=5,
                ).strip())
                return {"type": "git", "branch": branch, "dirty": dirty}
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                return {"type": "none"}

        result = await asyncio.to_thread(_git_info)
        return JSONResponse(result)

    async def list_commands(request: Request) -> JSONResponse:
        """List available commands."""
        from opencode.tui.commands import default_commands

        reg = default_commands()
        return JSONResponse([
            {
                "id": cmd.id,
                "name": cmd.name,
                "description": cmd.description,
                "keybinding": cmd.keybinding,
                "category": cmd.category,
            }
            for cmd in reg.list()
        ])

    async def list_agents(request: Request) -> JSONResponse:
        """List available agents."""
        return JSONResponse([
            {"id": "coder", "name": "Coder", "description": "General coding assistant"},
            {"id": "planner", "name": "Planner", "description": "Task planning"},
            {"id": "researcher", "name": "Researcher", "description": "Code exploration"},
            {"id": "reviewer", "name": "Reviewer", "description": "Code review"},
        ])

    async def list_tools(request: Request) -> JSONResponse:
        """List available tools."""
        tools = state.tool_registry.list()
        return JSONResponse([
            {
                "name": t.name,
                "description": t.description,
            }
            for t in tools
        ])

    return [
        Route("/path", get_paths, methods=["GET"]),
        Route("/vcs", get_vcs, methods=["GET"]),
        Route("/command", list_commands, methods=["GET"]),
        Route("/agent", list_agents, methods=["GET"]),
        Route("/tool", list_tools, methods=["GET"]),
    ]
