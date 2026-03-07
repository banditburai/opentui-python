"""Table + subcomponents — TUI equivalent of starui Table."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text


def Table(*children: Any, **kwargs: Any) -> Box:
    """Table container with border."""
    return Box(*children, flex_direction="column", border=True, border_style="single", **kwargs)


def TableHeader(*children: Any, **kwargs: Any) -> Box:
    """Table header row container."""
    return Box(*children, flex_direction="row", **kwargs)


def TableBody(*children: Any, **kwargs: Any) -> Box:
    """Table body container."""
    return Box(*children, flex_direction="column", **kwargs)


def TableRow(*children: Any, **kwargs: Any) -> Box:
    """Table row."""
    return Box(*children, flex_direction="row", **kwargs)


def TableHead(content: str = "", **kwargs: Any) -> Text:
    """Table header cell (bold)."""
    return Text(content, bold=True, **kwargs)


def TableCell(content: str = "", **kwargs: Any) -> Text:
    """Table data cell."""
    return Text(content, **kwargs)


def TableCaption(content: str = "", **kwargs: Any) -> Text:
    """Table caption."""
    return Text(content, fg="#888888", **kwargs)
