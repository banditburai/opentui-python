"""Progress component — TUI equivalent of starui Progress."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from .theme import resolve_props


def Progress(
    *,
    value: int | float = 0,
    max: int | float = 100,
    width: int = 20,
    **kwargs: Any,
) -> Box:
    """Progress bar with [████░░░░░░] visual."""
    theme = resolve_props("progress", variant="default")
    fill_char = theme.get("fill_char", "\u2588")
    empty_char = theme.get("empty_char", "\u2591")
    fg = theme.get("fg", "#3498db")

    ratio = min(value / max, 1.0) if max > 0 else 0.0
    filled = int(ratio * width)
    empty = width - filled

    bar_text = fill_char * filled + empty_char * empty
    return Box(Text(bar_text, fg=fg), width=width, **kwargs)
