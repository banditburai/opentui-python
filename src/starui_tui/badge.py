"""Badge component — TUI equivalent of starui Badge."""

from __future__ import annotations

from typing import Any, Literal

from opentui.components import Text

from .theme import resolve_props

BadgeVariant = Literal["default", "secondary", "destructive", "outline"]


def Badge(
    *children: Any,
    variant: BadgeVariant = "default",
    **kwargs: Any,
) -> Text:
    """Inline styled badge. Returns a Text node with themed colors."""
    props = {**resolve_props("badge", variant=variant), **kwargs}

    # Extract Text-compatible props
    text_kwargs: dict[str, Any] = {}
    if "fg" in props:
        text_kwargs["fg"] = props["fg"]
    if "bg" in props:
        text_kwargs["bg"] = props["bg"]

    content = " ".join(str(c) for c in children if isinstance(c, str))
    return Text(content, **text_kwargs)
