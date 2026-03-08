"""Todo item component — status indicator with colored text."""

from __future__ import annotations

from opentui.components import Box, Text

from ..themes import get_theme

_STATUS_CHARS = {
    "completed": "\u2713",
    "in_progress": "\u2022",
    "pending": " ",
}


def todo_item(*, status: str, content: str) -> Box:
    """Render a todo item with status indicator.

    Status indicators:
    - completed: [✓] green/muted
    - in_progress: [•] warning color
    - pending: [ ] muted
    """
    t = get_theme()
    char = _STATUS_CHARS.get(status, " ")
    color = t.warning if status == "in_progress" else t.text_muted
    if status == "completed":
        color = t.success

    return Box(
        Text(f"[{char}] ", fg=color),
        Text(content, fg=color),
        flex_direction="row",
    )
