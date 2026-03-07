"""Switch and Toggle components — TUI equivalents of starui."""

from __future__ import annotations

from typing import Any, Callable

from opentui.components import Box, Text

from .signals import Signal


def _resolve_value(v: Any) -> Any:
    """Get current value from a Signal or plain value."""
    return v() if isinstance(v, Signal) else v


def Switch(
    *,
    checked: bool | Signal = False,
    on_change: Callable[[bool], None] | None = None,
    **kwargs: Any,
) -> Box:
    """Toggle switch with [●○] / [○●] visual."""
    is_on = _resolve_value(checked)
    indicator = "[●○]" if is_on else "[○●]"

    box = Box(Text(indicator), flex_direction="row", **kwargs)

    if on_change is not None:
        def _toggle(_evt: Any) -> None:
            new_val = not _resolve_value(checked)
            if isinstance(checked, Signal):
                checked.set(new_val)
            if on_change:
                on_change(new_val)
        box.on_mouse_down = _toggle

    return box


def Toggle(
    label: str = "",
    *,
    pressed: bool | Signal = False,
    on_change: Callable[[bool], None] | None = None,
    **kwargs: Any,
) -> Box:
    """Toggle button — highlighted when pressed."""
    is_pressed = _resolve_value(pressed)
    fg = "#ffffff" if is_pressed else "#888888"
    bg = "#3498db" if is_pressed else None

    text_kwargs: dict[str, Any] = {"fg": fg}
    if bg:
        text_kwargs["bg"] = bg

    box = Box(Text(label, **text_kwargs), flex_direction="row", **kwargs)

    if on_change is not None:
        def _toggle(_evt: Any) -> None:
            new_val = not _resolve_value(pressed)
            if isinstance(pressed, Signal):
                pressed.set(new_val)
            if on_change:
                on_change(new_val)
        box.on_mouse_down = _toggle

    return box
