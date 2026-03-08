"""Tool result renderers — per-tool rendering for bash, read, write, edit, glob, grep."""

from __future__ import annotations

import json
from typing import Any

from opentui.components import Box, Text

from ..themes import get_theme


def _parse_metadata(metadata: str | None) -> dict[str, Any]:
    """Safely parse metadata JSON string."""
    if not metadata:
        return {}
    try:
        return json.loads(metadata)
    except (json.JSONDecodeError, TypeError):
        return {}


def _truncate_lines(text: str, max_lines: int = 10) -> tuple[str, int]:
    """Truncate text to max_lines, return (truncated, total_lines)."""
    lines = text.split("\n")
    total = len(lines)
    if total <= max_lines:
        return text, total
    return "\n".join(lines[:max_lines]), total


def tool_icon(icon: str, color: str) -> Text:
    """Render a tool icon character."""
    return Text(f" {icon} ", fg=color, bold=True)


def inline_tool(
    *,
    icon: str,
    label: str,
    detail: str = "",
    status: str = "completed",
    **kwargs: Any,
) -> Box:
    """Render a single-line tool display."""
    t = get_theme()
    icon_color = t.accent if status == "completed" else t.warning
    if status == "error":
        icon_color = t.error

    children: list[Text] = [
        tool_icon(icon, icon_color),
        Text(label, fg=t.text),
    ]
    if detail:
        children.append(Text(f" {detail}", fg=t.text_muted))

    return Box(
        *children,
        flex_direction="row",
        padding_left=1,
        **kwargs,
    )


def block_tool(
    *,
    title: str,
    children: list[Box | Text],
    status: str = "completed",
    **kwargs: Any,
) -> Box:
    """Render a multi-line tool display with left border."""
    t = get_theme()
    border_color = t.accent if status == "completed" else t.warning
    if status == "error":
        border_color = t.error

    header = Text(f" {title}", fg=t.text_muted, bold=True)
    return Box(
        header,
        *children,
        flex_direction="column",
        border=True,
        border_style="round",
        border_color=border_color,
        padding_left=1,
        padding_right=1,
        margin_left=2,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Per-tool renderers
# ---------------------------------------------------------------------------


def render_bash_result(content: str, metadata: str | None = None, *, status: str = "completed") -> Box:
    """Render shell command result with $ prefix and output."""
    t = get_theme()
    meta = _parse_metadata(metadata)
    command = meta.get("command", "")
    exit_code = meta.get("exit_code")

    children: list[Box | Text] = []
    if command:
        cmd_text = f"$ {command}"
        children.append(Text(cmd_text, fg=t.accent, bold=True))

    if content:
        truncated, total = _truncate_lines(content)
        children.append(Text(truncated, fg=t.text))
        if total > 10:
            children.append(Text(f"  ... ({total} lines total)", fg=t.text_muted))

    if exit_code is not None and exit_code != 0:
        children.append(Text(f"  exit code: {exit_code}", fg=t.error))

    if not children:
        return inline_tool(icon="$", label="bash", detail="(no output)", status=status)

    return block_tool(title="bash", children=children, status=status)


def render_read_result(content: str, metadata: str | None = None, *, status: str = "completed") -> Box:
    """Render file read result with path and line numbers."""
    t = get_theme()
    meta = _parse_metadata(metadata)
    path = meta.get("path", "file")

    label = f"{path}"
    if not content:
        return inline_tool(icon="\u2192", label=label, detail="(empty)", status=status)

    truncated, total = _truncate_lines(content, max_lines=15)
    lines = truncated.split("\n")
    numbered = []
    for i, line in enumerate(lines, 1):
        numbered.append(Text(f" {i:>4} \u2502 {line}", fg=t.text))

    children: list[Box | Text] = list(numbered)
    if total > 15:
        children.append(Text(f"  ... ({total} lines total)", fg=t.text_muted))

    return block_tool(title=f"\u2192 {label}", children=children, status=status)


def render_write_result(content: str, metadata: str | None = None, *, status: str = "completed") -> Box:
    """Render file write confirmation."""
    meta = _parse_metadata(metadata)
    path = meta.get("path", "file")
    return inline_tool(icon="\u2190", label=path, detail=content or "written", status=status)


def render_edit_result(content: str, metadata: str | None = None, *, status: str = "completed") -> Box:
    """Render edit result as a diff."""
    t = get_theme()
    meta = _parse_metadata(metadata)
    path = meta.get("path", "file")

    if not content:
        return inline_tool(icon="\u2190", label=path, detail="edited", status=status)

    # Render diff lines with colors
    children: list[Box | Text] = []
    for line in content.split("\n")[:20]:
        if line.startswith("+"):
            children.append(Text(line, fg=t.diff_added))
        elif line.startswith("-"):
            children.append(Text(line, fg=t.diff_removed))
        elif line.startswith("@@"):
            children.append(Text(line, fg=t.diff_hunk_header))
        else:
            children.append(Text(line, fg=t.text_muted))

    return block_tool(title=f"\u2190 {path}", children=children, status=status)


def render_glob_result(content: str, metadata: str | None = None, *, status: str = "completed") -> Box:
    """Render glob/file search results."""
    meta = _parse_metadata(metadata)
    pattern = meta.get("pattern", "*")
    path = meta.get("path", ".")

    matches = content.strip().split("\n") if content.strip() else []
    count = len(matches)
    return inline_tool(
        icon="\u2731",
        label=f'Glob "{pattern}"',
        detail=f"in {path} ({count} matches)",
        status=status,
    )


def render_grep_result(content: str, metadata: str | None = None, *, status: str = "completed") -> Box:
    """Render grep/search results."""
    meta = _parse_metadata(metadata)
    pattern = meta.get("pattern", "")
    path = meta.get("path", ".")

    matches = content.strip().split("\n") if content.strip() else []
    count = len(matches)
    return inline_tool(
        icon="\u2731",
        label=f'Grep "{pattern}"',
        detail=f"in {path} ({count} matches)",
        status=status,
    )


def render_generic_result(
    tool_name: str,
    content: str,
    status: str = "completed",
) -> Box:
    """Fallback renderer for unknown tools."""
    t = get_theme()
    if not content:
        return inline_tool(icon="\u2699", label=tool_name, status=status)

    truncated, total = _truncate_lines(content, max_lines=3)
    children: list[Box | Text] = [Text(truncated, fg=t.text)]
    if total > 3:
        children.append(Text(f"  ... ({total} lines)", fg=t.text_muted))

    return block_tool(title=tool_name, children=children, status=status)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_RENDERERS = {
    "bash": render_bash_result,
    "shell": render_bash_result,
    "read": render_read_result,
    "read_file": render_read_result,
    "write": render_write_result,
    "write_file": render_write_result,
    "edit": render_edit_result,
    "glob": render_glob_result,
    "search_files": render_glob_result,
    "grep": render_grep_result,
}


def render_tool_result(
    tool_name: str,
    content: str,
    metadata: str | None = None,
    status: str = "completed",
) -> Box:
    """Dispatch to the appropriate tool renderer."""
    renderer = _TOOL_RENDERERS.get(tool_name)
    if renderer:
        return renderer(content, metadata, status=status)
    return render_generic_result(tool_name, content, status=status)
