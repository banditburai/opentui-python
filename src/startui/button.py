"""Button component — TUI equivalent of starui Button."""

from __future__ import annotations

from typing import Any, Literal

from opentui.components import Box, Text

from .dispatch import dispatch_action
from .props import split_props
from .theme import resolve_props

ButtonVariant = Literal["default", "destructive", "outline", "secondary", "ghost", "link"]
ButtonSize = Literal["default", "sm", "lg", "icon"]


def Button(
    *children: Any,
    variant: ButtonVariant = "default",
    size: ButtonSize = "default",
    disabled: bool = False,
    on_click: Any = None,
    cls: str = "",  # Accepted but ignored in TUI mode
    **kwargs: Any,
) -> Box:
    """Create a Button component.

    Same function signature as starui.Button but returns OpenTUI Renderables.
    """
    props = {**resolve_props("button", variant=variant, size=size), **kwargs}
    text_props, box_props = split_props(props)

    if disabled:
        text_props["fg"] = "#666666"

    inner_children = []
    for c in children:
        if isinstance(c, str):
            inner_children.append(Text(c, **text_props))
        else:
            inner_children.append(c)
    if not inner_children:
        inner_children.append(Text("", **text_props))
    box = Box(*inner_children, **box_props)

    if on_click is not None and not disabled:
        box.on_mouse_down = lambda _evt: dispatch_action(on_click)

    return box
