"""Small utility functions that reduce common boilerplate when building component trees."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ._signal_types import Signal, _ComputedSignal


def pick[T](
    condition: bool | Signal | _ComputedSignal | Callable[[], Any],
    if_true: T,
    if_false: T | None = None,
) -> T | Callable[[], T]:
    """Return *if_true* or *if_false* based on *condition*.

    When *condition* is a static ``bool``, returns the value directly.
    When *condition* is reactive (Signal, ComputedSignal, or callable),
    returns a callable suitable for reactive prop binding::

        Box(
            fg=pick(is_active, "green", "gray"),           # reactive
            border_color=pick(True, "blue", "red"),        # static
        )
    """
    if isinstance(condition, bool):
        return if_true if condition else if_false  # type: ignore[return-value]

    if isinstance(condition, Signal | _ComputedSignal):
        return lambda: if_true if condition() else if_false  # type: ignore[return-value]

    if callable(condition):
        return lambda: if_true if condition() else if_false  # type: ignore[return-value]

    # Truthy/falsy fallback for non-bool static values
    return if_true if condition else if_false  # type: ignore[return-value]


def panel(
    *,
    border: bool = True,
    border_style: str = "rounded",
    background_color: str | None = None,
    bg: str | None = None,
    border_color: str | None = None,
    padding: int | None = None,
    padding_x: int | None = None,
    padding_y: int | None = None,
    title: str | None = None,
    title_alignment: str = "left",
    focused_border_color: str | None = None,
    overflow: str = "hidden",
) -> dict[str, Any]:
    """Return a style dict for a common bordered panel pattern.

    Spread into any Box-like constructor with ``**``::

        Box("content", **panel(bg="#1a1a2e", border_color="#555"))
        Box("content", **panel(title="Settings", padding=2))
    """
    resolved_bg = bg if bg is not None else background_color
    d: dict[str, Any] = {
        "border": border,
        "border_style": border_style,
        "overflow": overflow,
    }
    if padding is not None:
        d["padding"] = padding
    if padding_x is not None:
        d["padding_x"] = padding_x
    if padding_y is not None:
        d["padding_y"] = padding_y
    if resolved_bg is not None:
        d["background_color"] = resolved_bg
    if border_color is not None:
        d["border_color"] = border_color
    if title is not None:
        d["title"] = title
    if title_alignment != "left":
        d["title_alignment"] = title_alignment
    if focused_border_color is not None:
        d["focused_border_color"] = focused_border_color
    return d
