"""Textarea component — TUI equivalent of starui Textarea."""

from __future__ import annotations

from typing import Any, Callable, Literal

from opentui.components import Textarea as TUITextarea

from .props import split_props
from .theme import resolve_props

TextareaVariant = Literal["default"]


def Textarea(
    value: str | None = None,
    *,
    variant: TextareaVariant = "default",
    placeholder: str = "",
    rows: int = 3,
    disabled: bool = False,
    on_change: Callable[[str], None] | None = None,
    on_submit: Callable[[str], None] | None = None,
    on_input: Callable[[str], None] | None = None,
    **kwargs: Any,
) -> TUITextarea:
    """Create a themed Textarea component.

    Same function signature as starui.Textarea but returns OpenTUI Textarea.
    """
    props = {**resolve_props("textarea", variant=variant), **kwargs}
    text_props, box_props = split_props(props)

    if disabled:
        text_props["fg"] = "#666666"

    return TUITextarea(
        value=value,
        placeholder=placeholder,
        rows=rows,
        on_change=on_change if not disabled else None,
        on_submit=on_submit if not disabled else None,
        on_input=on_input if not disabled else None,
        **text_props,
        **box_props,
    )
