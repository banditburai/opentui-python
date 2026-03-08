"""Breadcrumb component — TUI equivalent of starui Breadcrumb."""

from __future__ import annotations

from typing import Any, Callable

from opentui.components import Box, Text

from .theme import resolve_props


def Breadcrumb(
    *items: Any,
    separator: str = ">",
    **kwargs: Any,
) -> Box:
    """Breadcrumb navigation trail with separators between items."""
    sep_props = resolve_props("breadcrumb_separator", variant="default")
    sep_fg = sep_props.get("fg", "#666666")

    children: list[Any] = []
    for i, item in enumerate(items):
        if i > 0:
            children.append(Text(f" {separator} ", fg=sep_fg))
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
    item_props = resolve_props("breadcrumb_item", variant="default")
    link_fg = item_props.get("fg", "#3498db")

    if on_click is not None:
        text = Text(label, fg=link_fg, bold=is_current)
        box = Box(text, **kwargs)
        box.on_mouse_down = lambda _evt: on_click()
        return box

    return Text(label, bold=is_current, **kwargs)
