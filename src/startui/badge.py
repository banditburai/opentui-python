"""Badge component — TUI equivalent of starui Badge."""

from __future__ import annotations

from typing import Any, Literal

from opentui.components import Box, Text

from .props import TEXT_KEYS, split_props
from .theme import resolve_props

BadgeVariant = Literal["default", "secondary", "destructive", "outline"]

# Props that Text accepts directly
_TEXT_PROPS = TEXT_KEYS | {"fg", "bg"}


def Badge(
    *children: Any,
    variant: BadgeVariant = "default",
    **kwargs: Any,
) -> Text | Box:
    """Inline styled badge. Returns a Text node with themed colors."""
    props = {**resolve_props("badge", variant=variant), **kwargs}

    # Extract only Text-compatible props, ignore Box-only props (border, padding, etc.)
    text_kwargs = {k: v for k, v in props.items() if k in _TEXT_PROPS}

    # Separate string and non-string children
    strings = [str(c) for c in children if isinstance(c, str)]
    non_strings = [c for c in children if not isinstance(c, str)]

    if non_strings:
        # If there are non-string children, wrap everything in a Box
        text_props, box_props = split_props(props)
        inner = []
        if strings:
            inner.append(Text(" ".join(strings), **text_kwargs))
        inner.extend(non_strings)
        return Box(*inner, **box_props)

    content = " ".join(strings)
    return Text(content, **text_kwargs)
