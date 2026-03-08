"""Alert component — TUI equivalent of starui Alert."""

from __future__ import annotations

from typing import Any, Literal

from opentui.components import Box, Text

from .props import split_props
from .theme import resolve_props

AlertVariant = Literal["default", "destructive"]


def Alert(*children: Any, variant: AlertVariant = "default", **kwargs: Any) -> Box:
    """Alert container with themed border and color."""
    props = {**resolve_props("alert", variant=variant), **kwargs}
    text_props, box_props = split_props(props)
    # Apply fg to all text children
    processed = []
    for child in children:
        if isinstance(child, str):
            processed.append(Text(child, **text_props))
        else:
            processed.append(child)
    return Box(*processed, flex_direction="column", **box_props)


def AlertTitle(content: str = "", **kwargs: Any) -> Text:
    """Alert title (bold)."""
    return Text(content, bold=True, **kwargs)


def AlertDescription(content: str = "", **kwargs: Any) -> Text:
    """Alert description text."""
    return Text(content, **kwargs)
