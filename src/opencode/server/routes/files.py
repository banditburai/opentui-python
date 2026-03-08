"""File routes — search, read, status."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.tui.state import AppState


def _validate_path(path: str | Path, base_dir: Path) -> Path | None:
    """Resolve *path* and return it only if it's inside *base_dir*.

    Returns ``None`` (and the caller should return 403) when the resolved
    path escapes the sandbox.
    """
    try:
        resolved = Path(path).resolve()
        base_resolved = base_dir.resolve()
        # Ensure the resolved path is within the base directory
        resolved.relative_to(base_resolved)
        return resolved
    except (ValueError, OSError):
        return None


def file_routes(state: AppState) -> list[Any]:
    """File operation routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    base_dir = Path(os.getcwd())

    async def find_files(request: Request) -> JSONResponse:
        """Search for files by glob pattern."""
        import glob as glob_mod

        pattern = request.query_params.get("pattern", "*")
        directory = request.query_params.get("directory", ".")
        max_results = int(request.query_params.get("limit", "100"))

        resolved_dir = _validate_path(directory, base_dir)
        if resolved_dir is None:
            return JSONResponse({"error": "path outside project directory"}, status_code=403)

        try:
            matches = await asyncio.to_thread(
                glob_mod.glob, pattern, root_dir=str(resolved_dir), recursive=True,
            )
            return JSONResponse({
                "pattern": pattern,
                "directory": directory,
                "matches": matches[:max_results],
                "total": len(matches),
            })
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    async def find_text(request: Request) -> JSONResponse:
        """Search file contents for a pattern (simple grep)."""
        pattern = request.query_params.get("pattern", "")
        directory = request.query_params.get("directory", ".")
        max_results = int(request.query_params.get("limit", "50"))

        if not pattern:
            return JSONResponse({"error": "pattern is required"}, status_code=400)

        resolved_dir = _validate_path(directory, base_dir)
        if resolved_dir is None:
            return JSONResponse({"error": "path outside project directory"}, status_code=403)

        def _search() -> list[dict[str, Any]]:
            matches: list[dict[str, Any]] = []
            base = resolved_dir
            for root, _, files in os.walk(base):
                for fname in files:
                    if len(matches) >= max_results:
                        break
                    fpath = Path(root) / fname
                    try:
                        text = fpath.read_text(errors="ignore")
                        for i, line in enumerate(text.splitlines(), 1):
                            if pattern in line:
                                matches.append({
                                    "file": str(fpath.relative_to(base)),
                                    "line": i,
                                    "content": line.strip()[:200],
                                })
                                if len(matches) >= max_results:
                                    break
                    except (OSError, UnicodeDecodeError):
                        continue
            return matches

        try:
            matches = await asyncio.to_thread(_search)
        except OSError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        return JSONResponse({
            "pattern": pattern,
            "directory": directory,
            "matches": matches,
            "total": len(matches),
        })

    async def read_file(request: Request) -> JSONResponse:
        """Read file content."""
        path = request.query_params.get("path", "")
        if not path:
            return JSONResponse({"error": "path is required"}, status_code=400)

        resolved = _validate_path(path, base_dir)
        if resolved is None:
            return JSONResponse({"error": "path outside project directory"}, status_code=403)

        try:
            content = await asyncio.to_thread(resolved.read_text)
            return JSONResponse({
                "path": path,
                "content": content,
                "lines": content.count("\n") + 1,
            })
        except FileNotFoundError:
            return JSONResponse({"error": "file not found"}, status_code=404)
        except OSError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    async def list_dir(request: Request) -> JSONResponse:
        """List directory contents."""
        path = request.query_params.get("path", ".")

        resolved = _validate_path(path, base_dir)
        if resolved is None:
            return JSONResponse({"error": "path outside project directory"}, status_code=403)

        def _list() -> list[dict[str, Any]]:
            entries = []
            for entry in sorted(resolved.iterdir()):
                entries.append({
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else 0,
                })
            return entries

        try:
            entries = await asyncio.to_thread(_list)
            return JSONResponse({"path": path, "entries": entries})
        except OSError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    return [
        Route("/find", find_text, methods=["GET"]),
        Route("/find/file", find_files, methods=["GET"]),
        Route("/file", list_dir, methods=["GET"]),
        Route("/file/content", read_file, methods=["GET"]),
    ]
