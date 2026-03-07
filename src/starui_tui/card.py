"""Card component — TUI equivalent of starui Card."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from .props import split_props
from .theme import resolve_props


def Card(*children: Any, variant: str = "default", **kwargs: Any) -> Box:
    """Card container with themed border and background."""
    props = {**resolve_props("card", variant=variant), **kwargs}
    _, box_props = split_props(props)
    return Box(*children, **box_props)


def CardHeader(*children: Any, **kwargs: Any) -> Box:
    """Card header section."""
    return Box(*children, flex_direction="column", **kwargs)


def CardTitle(content: str = "", **kwargs: Any) -> Text:
    """Card title text (bold)."""
    return Text(content, bold=True, **kwargs)


def CardDescription(content: str = "", **kwargs: Any) -> Text:
    """Card description text (muted)."""
    return Text(content, fg="#888888", **kwargs)


def CardContent(*children: Any, **kwargs: Any) -> Box:
    """Card content section."""
    return Box(*children, **kwargs)


def CardFooter(*children: Any, **kwargs: Any) -> Box:
    """Card footer section."""
    return Box(*children, flex_direction="row", justify_content="flex-end", **kwargs)
