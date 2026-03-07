"""File operation tools — read, write, search."""

from __future__ import annotations

import glob as _glob
from pathlib import Path

from . import Tool


def read_file_tool() -> Tool:
    """Create a read_file tool."""

    async def execute(*, path: str, **_: object) -> str:
        try:
            return Path(path).read_text()
        except FileNotFoundError:
            return f"Error: file not found: {path}"
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


def write_file_tool() -> Tool:
    """Create a write_file tool."""

    async def execute(*, path: str, content: str, **_: object) -> str:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Wrote {len(content)} bytes to {path}"
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

    async def execute(*, pattern: str, directory: str = ".", **_: object) -> str:
        matches = sorted(_glob.glob(pattern, root_dir=directory))
        if not matches:
            return "No matches found."
        return "\n".join(matches)

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
