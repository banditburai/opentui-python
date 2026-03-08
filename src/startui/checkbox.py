"""Checkbox and RadioGroup components — TUI equivalents of starui."""

from __future__ import annotations

from typing import Any, Callable

from opentui.components import Box, Text

from .props import resolve_value
from .signals import Signal
from .theme import resolve_props


def Checkbox(
    *,
    checked: bool | Signal = False,
    label: str = "",
    on_change: Callable[[bool], None] | None = None,
    **kwargs: Any,
) -> Box:
    """Checkbox with [x]/[ ] indicator and optional label."""
    is_checked = resolve_value(checked)
    indicator = "[x]" if is_checked else "[ ]"

    children: list[Any] = [Text(indicator)]
    if label:
        children.append(Text(f" {label}"))

    box = Box(*children, flex_direction="row", **kwargs)

    if on_change is not None:
        def _toggle(_evt: Any) -> None:
            new_val = not resolve_value(checked)
            if isinstance(checked, Signal):
                checked.set(new_val)
            if on_change:
                on_change(new_val)
        box.on_mouse_down = _toggle

    return box


class RadioGroupItem:
    """Data holder for a radio option."""
    __slots__ = ("value", "label")

    def __init__(self, value: str, label: str) -> None:
        self.value = value
        self.label = label


def RadioGroup(
    *items: RadioGroupItem,
    value: str | Signal = "",
    on_change: Callable[[str], None] | None = None,
    **kwargs: Any,
) -> Box:
    """Radio button group with (o)/( ) indicators and exclusive selection."""
    selected = resolve_value(value)

    children = []
    for item in items:
        is_selected = item.value == selected
        indicator = "(o)" if is_selected else "( )"
        row = Box(
            Text(indicator),
            Text(f" {item.label}"),
            flex_direction="row",
        )

        def _make_handler(val: str) -> Callable:
            def _select(_evt: Any) -> None:
                if isinstance(value, Signal):
                    value.set(val)
                if on_change:
                    on_change(val)
            return _select

        row.on_mouse_down = _make_handler(item.value)
        children.append(row)

    return Box(*children, flex_direction="column", **kwargs)
