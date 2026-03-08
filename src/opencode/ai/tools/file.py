"""File operation tools — read, write, search."""

from __future__ import annotations

import glob as _glob
from pathlib import Path

from . import Tool


def _validate_path(path: str, working_dir: Path | None) -> Path | None:
    """Resolve *path* and ensure it lives under *working_dir*.

    Returns the resolved ``Path`` on success, or ``None`` if the path
    escapes the sandbox.
    """
    resolved = Path(path).resolve()
    if working_dir is not None and not resolved.is_relative_to(working_dir.resolve()):
        return None
    return resolved


def read_file_tool(working_dir: Path | None = None) -> Tool:
    """Create a read_file tool."""

    async def execute(*, path: str, **_: object) -> str:
        resolved = _validate_path(path, working_dir)
        if resolved is None:
            return f"Error: path {path} is outside the allowed working directory"
        try:
            return resolved.read_text(encoding="utf-8")
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except UnicodeDecodeError:
            return f"Error: {path} is a binary file"
        except OSError as e:
            return f"Error: {e}"

    return Tool(
        name="read_file",
        description="Read the contents of a file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file."},
            },
            "required": ["path"],
        },
        execute=execute,
    )


def write_file_tool(working_dir: Path | None = None) -> Tool:
    """Create a write_file tool."""

    async def execute(*, path: str, content: str, **_: object) -> str:
        resolved = _validate_path(path, working_dir)
        if resolved is None:
            return f"Error: path {path} is outside the allowed working directory"
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} chars to {path}"
        except OSError as e:
            return f"Error: {e}"

    return Tool(
        name="write_file",
        description="Write content to a file, creating parent directories if needed.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        },
        execute=execute,
    )


def search_files_tool() -> Tool:
    """Create a search_files tool."""

    _MAX_RESULTS = 10_000

    async def execute(*, pattern: str, directory: str = ".", **_: object) -> str:
        matches = sorted(_glob.glob(pattern, root_dir=directory, recursive=True))
        if not matches:
            return "No matches found."
        truncated = matches[:_MAX_RESULTS]
        result = "\n".join(truncated)
        if len(matches) > _MAX_RESULTS:
            result += f"\n... ({len(matches) - _MAX_RESULTS} more matches truncated)"
        return result

    return Tool(
        name="search_files",
        description="Search for files matching a glob pattern.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py')."},
                "directory": {"type": "string", "description": "Directory to search in.", "default": "."},
            },
            "required": ["pattern"],
        },
        execute=execute,
    )
