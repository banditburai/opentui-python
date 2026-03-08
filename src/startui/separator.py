"""Separator component — TUI equivalent of starui Separator."""

from __future__ import annotations

from typing import Any, Literal

from opentui.components import Text

from .theme import resolve_props


def Separator(
    *,
    orientation: Literal["horizontal", "vertical"] = "horizontal",
    width: int | None = None,
    **kwargs: Any,
) -> Text:
    """Horizontal or vertical line separator."""
    theme = resolve_props("separator", variant="default")
    char = theme.get("border_char", "\u2500")

    if orientation == "vertical":
        content = "\u2502"  # │
    else:
        repeat = width if width is not None else 1
        content = char * repeat

    return Text(content, **kwargs)
