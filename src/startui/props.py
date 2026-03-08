"""Shared prop translation utilities for startui components."""

from __future__ import annotations

from typing import Any

__all__ = ["TEXT_KEYS", "BOX_KEY_MAP", "SHORTHAND_EXPAND", "split_props", "resolve_value"]

# Theme keys that map to Text props (not Box props)
TEXT_KEYS = frozenset({"underline", "bold", "italic", "strikethrough"})

# Theme key translation: theme name -> OpenTUI Box kwarg name
BOX_KEY_MAP = {"bg": "background_color"}

# Shorthand keys that Box doesn't accept directly
SHORTHAND_EXPAND = {
    "padding_x": ("padding_left", "padding_right"),
    "padding_y": ("padding_top", "padding_bottom"),
    "margin_x": ("margin_left", "margin_right"),
    "margin_y": ("margin_top", "margin_bottom"),
}


def split_props(props: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split theme props into (text_props, box_props).

    Handles:
    - fg goes to text_props
    - underline/bold/italic/strikethrough go to text_props
    - bg -> background_color in box_props
    - padding_x/y -> expanded to individual sides in box_props
    - Everything else goes to box_props
    """
    text_props: dict[str, Any] = {}
    box_props: dict[str, Any] = {}
    for key, value in props.items():
        if key == "fg":
            text_props["fg"] = value
        elif key in TEXT_KEYS:
            text_props[key] = value
        elif key in BOX_KEY_MAP:
            box_props[BOX_KEY_MAP[key]] = value
        elif key in SHORTHAND_EXPAND:
            for expanded_key in SHORTHAND_EXPAND[key]:
                box_props[expanded_key] = value
        else:
            box_props[key] = value
    return text_props, box_props


def resolve_value(val):
    """Resolve a Signal or plain value to its current value."""
    if callable(val) and hasattr(val, 'get'):
        return val.get()
    if callable(val) and hasattr(val, '_value'):
        return val._value
    return val
