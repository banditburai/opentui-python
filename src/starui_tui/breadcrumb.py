"""Breadcrumb component — TUI equivalent of starui Breadcrumb."""

from __future__ import annotations

from typing import Any, Callable

from opentui.components import Box, Text


def Breadcrumb(
    *items: Any,
    separator: str = ">",
    **kwargs: Any,
) -> Box:
    """Breadcrumb navigation trail with separators between items."""
    children: list[Any] = []
    for i, item in enumerate(items):
        if i > 0:
            children.append(Text(f" {separator} ", fg="#666666"))
        children.append(item)

    return Box(*children, flex_direction="row", **kwargs)


def BreadcrumbItem(
    label: str,
    *,
    on_click: Callable[[], None] | None = None,
    is_current: bool = False,
    **kwargs: Any,
) -> Text | Box:
    """Breadcrumb item — text or clickable box."""
    if on_click is not None:
        text = Text(label, fg="#3498db", bold=is_current)
        box = Box(text, **kwargs)
        box.on_mouse_down = lambda _evt: on_click()
        return box

    return Text(label, bold=is_current, **kwargs)
