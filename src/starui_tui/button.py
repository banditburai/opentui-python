"""Button component — TUI equivalent of starui Button."""

from __future__ import annotations

from typing import Any, Literal

from opentui.components import Box, Text

from .dispatch import dispatch_action
from .theme import resolve_props

ButtonVariant = Literal["default", "destructive", "outline", "secondary", "ghost", "link"]
ButtonSize = Literal["default", "sm", "lg", "icon"]

# Theme keys that map to Text props (not Box props)
_TEXT_KEYS = {"underline", "bold", "italic", "strikethrough"}
# Theme key translation: theme name -> OpenTUI Box kwarg name
_BOX_KEY_MAP = {"bg": "background_color"}
# Shorthand keys that Box doesn't accept directly
_SHORTHAND_EXPAND = {
    "padding_x": ("padding_left", "padding_right"),
    "padding_y": ("padding_top", "padding_bottom"),
    "margin_x": ("margin_left", "margin_right"),
    "margin_y": ("margin_top", "margin_bottom"),
}


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

    # Separate text props from box props, expanding shorthands
    text_props: dict[str, Any] = {}
    box_props: dict[str, Any] = {}
    for key, value in props.items():
        if key == "fg":
            text_props["fg"] = value
        elif key in _TEXT_KEYS:
            text_props[key] = value
        elif key in _BOX_KEY_MAP:
            box_props[_BOX_KEY_MAP[key]] = value
        elif key in _SHORTHAND_EXPAND:
            for expanded_key in _SHORTHAND_EXPAND[key]:
                box_props[expanded_key] = value
        else:
            box_props[key] = value

    if disabled:
        text_props["fg"] = "#666666"

    # Build text content from children
    text_content = " ".join(str(c) for c in children if isinstance(c, str))
    text_node = Text(text_content, **text_props)

    box = Box(text_node, **box_props)

    # Set event handler as property (not constructor kwarg)
    if on_click is not None and not disabled:
        box.on_mouse_down = lambda _evt: dispatch_action(on_click)

    return box
