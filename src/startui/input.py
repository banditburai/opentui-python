"""Input component — TUI equivalent of starui Input."""

from __future__ import annotations

from typing import Any, Callable, Literal

from opentui.components import Input as TUIInput

from .props import split_props
from .theme import resolve_props

InputVariant = Literal["default"]


def Input(
    value: str | None = None,
    *,
    variant: InputVariant = "default",
    placeholder: str = "",
    disabled: bool = False,
    on_change: Callable[[str], None] | None = None,
    on_submit: Callable[[str], None] | None = None,
    on_input: Callable[[str], None] | None = None,
    **kwargs: Any,
) -> TUIInput:
    """Create a themed Input component.

    Same function signature as starui.Input but returns OpenTUI Input.
    """
    props = {**resolve_props("input", variant=variant), **kwargs}
    text_props, box_props = split_props(props)

    if disabled:
        text_props["fg"] = "#666666"

    return TUIInput(
        value=value,
        placeholder=placeholder,
        on_change=on_change if not disabled else None,
        on_submit=on_submit if not disabled else None,
        on_input=on_input if not disabled else None,
        **text_props,
        **box_props,
    )
