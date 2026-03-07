"""Card component — TUI equivalent of starui Card."""

from __future__ import annotations

from typing import Any, Literal

from opentui.components import Box, Text

from .props import split_props
from .theme import resolve_props

CardVariant = Literal["default"]


def Card(*children: Any, variant: CardVariant = "default", **kwargs: Any) -> Box:
    """Card container with themed border and background."""
    props = {**resolve_props("card", variant=variant), **kwargs}
    _, box_props = split_props(props)
    return Box(*children, **box_props)


def CardHeader(*children: Any, **kwargs: Any) -> Box:
    """Card header section."""
    props = {**resolve_props("card_header", variant="default"), **kwargs}
    return Box(*children, **props)


def CardTitle(content: str = "", **kwargs: Any) -> Text:
    """Card title text (bold)."""
    props = {**resolve_props("card_title", variant="default"), **kwargs}
    return Text(content, **props)


def CardDescription(content: str = "", **kwargs: Any) -> Text:
    """Card description text (muted)."""
    props = {**resolve_props("card_description", variant="default"), **kwargs}
    return Text(content, **props)


def CardContent(*children: Any, **kwargs: Any) -> Box:
    """Card content section."""
    return Box(*children, **kwargs)


def CardFooter(*children: Any, **kwargs: Any) -> Box:
    """Card footer section."""
    props = {**resolve_props("card_footer", variant="default"), **kwargs}
    return Box(*children, **props)
