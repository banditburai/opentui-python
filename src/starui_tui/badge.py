"""Badge component — TUI equivalent of starui Badge."""

from __future__ import annotations

from typing import Any, Literal

from opentui.components import Text

from .props import TEXT_KEYS
from .theme import resolve_props

BadgeVariant = Literal["default", "secondary", "destructive", "outline"]

# Props that Text accepts directly
_TEXT_PROPS = TEXT_KEYS | {"fg", "bg"}


def Badge(
    *children: Any,
    variant: BadgeVariant = "default",
    **kwargs: Any,
) -> Text:
    """Inline styled badge. Returns a Text node with themed colors."""
    props = {**resolve_props("badge", variant=variant), **kwargs}

    # Extract only Text-compatible props, ignore Box-only props (border, padding, etc.)
    text_kwargs = {k: v for k, v in props.items() if k in _TEXT_PROPS}

    content = " ".join(str(c) for c in children if isinstance(c, str))
    return Text(content, **text_kwargs)
