"""Select component — TUI equivalent of starui Select."""

from __future__ import annotations

from typing import Any, Callable

from opentui.components import Box, Text

from .props import split_props, resolve_value
from .signals import Signal
from .theme import resolve_props


class SelectItem:
    """Data holder for a select option."""
    __slots__ = ("value", "label")

    def __init__(self, value: str, label: str) -> None:
        self.value = value
        self.label = label


def Select(
    *items: SelectItem,
    value: str | Signal = "",
    placeholder: str = "Select...",
    on_change: Callable[[str], None] | None = None,
    **kwargs: Any,
) -> Box:
    """Create a themed Select dropdown.

    Renders as a bordered box showing the selected value,
    with click handlers on each item for selection.
    """
    props = {**resolve_props("select", variant="default"), **kwargs}
    _, box_props = split_props(props)

    selected = resolve_value(value)

    # Find selected item label
    display = placeholder
    for item in items:
        if item.value == selected:
            display = item.label
            break

    # Build trigger (shows current selection)
    trigger = Text(f"{display} ▼")

    # Build item list
    children: list[Any] = [trigger]
    for item in items:
        is_selected = item.value == selected
        prefix = "● " if is_selected else "  "
        item_text = Text(f"{prefix}{item.label}")
        item_row = Box(item_text, flex_direction="row")

        def _make_handler(val: str) -> Callable:
            def _select(_evt: Any) -> None:
                if isinstance(value, Signal):
                    value.set(val)
                if on_change:
                    on_change(val)
            return _select

        item_row.on_mouse_down = _make_handler(item.value)
        children.append(item_row)

    return Box(*children, flex_direction="column", **box_props)
