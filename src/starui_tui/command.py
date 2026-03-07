"""Command palette component — TUI equivalent of starui Command."""

from __future__ import annotations

from typing import Any, Callable

from opentui.components import Box, Text

from .props import split_props
from .theme import resolve_props


def Command(
    *children: Any,
    **kwargs: Any,
) -> Box:
    """Command palette container."""
    props = {**resolve_props("command", variant="default"), **kwargs}
    _, box_props = split_props(props)
    return Box(*children, flex_direction="column", **box_props)


def CommandInput(
    *,
    placeholder: str = "",
    **kwargs: Any,
) -> Box:
    """Command palette search input."""
    return Box(
        Text(placeholder, fg="#888888"),
        border=True,
        border_style="single",
        **kwargs,
    )


def CommandList(
    *children: Any,
    **kwargs: Any,
) -> Box:
    """Command palette results list."""
    return Box(*children, flex_direction="column", **kwargs)


def CommandItem(
    label: str,
    *,
    value: str = "",
    shortcut: str | None = None,
    on_select: Callable[[str], None] | None = None,
    **kwargs: Any,
) -> Box:
    """Command palette item with optional shortcut and callback."""
    children: list[Any] = [Text(label)]
    if shortcut is not None:
        children.append(Text(shortcut, fg="#666666"))

    box = Box(
        *children,
        flex_direction="row",
        justify_content="space-between",
        **kwargs,
    )

    if on_select is not None:
        def _handle(_evt: Any) -> None:
            on_select(value)
        box.on_mouse_down = _handle

    return box


def CommandGroup(
    heading: str,
    *children: Any,
    **kwargs: Any,
) -> Box:
    """Command palette group with heading."""
    header = Text(heading, fg="#888888", bold=True)
    return Box(header, *children, flex_direction="column", **kwargs)
