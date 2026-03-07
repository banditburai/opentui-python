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
    props = {**resolve_props("command_input", variant="default"), **kwargs}
    text_props, box_props = split_props(props)
    return Box(Text(placeholder, **text_props), **box_props)


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
    props = {**resolve_props("command_item", variant="default"), **kwargs}
    _, box_props = split_props(props)

    children: list[Any] = [Text(label)]
    if shortcut is not None:
        sc_props = resolve_props("command_shortcut", variant="default")
        sc_text, _ = split_props(sc_props)
        children.append(Text(shortcut, **sc_text))

    box = Box(*children, **box_props)

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
    h_props = resolve_props("command_group_heading", variant="default")
    h_text, _ = split_props(h_props)
    header = Text(heading, **h_text)
    return Box(header, *children, flex_direction="column", **kwargs)
