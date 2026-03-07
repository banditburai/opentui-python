"""Pagination component — TUI equivalent of starui Pagination."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from .signals import Signal


def Pagination(
    *,
    total_pages: int,
    signal: Signal,
    **kwargs: Any,
) -> Box:
    """Pagination with prev/next and page number buttons."""
    current = signal()

    def _make_page_handler(page: int):
        def _handler(_evt: Any) -> None:
            signal.set(page)
        return _handler

    def _prev(_evt: Any) -> None:
        cur = signal()
        if cur > 1:
            signal.set(cur - 1)

    def _next(_evt: Any) -> None:
        cur = signal()
        if cur < total_pages:
            signal.set(cur + 1)

    prev_btn = Box(Text("<", fg="#cccccc"), padding_left=1, padding_right=1)
    prev_btn.on_mouse_down = _prev

    children: list[Any] = [prev_btn]

    for page in range(1, total_pages + 1):
        is_active = page == current
        text = Text(
            str(page),
            fg="#ffffff" if is_active else "#888888",
            bold=is_active,
        )
        btn = Box(text, padding_left=0, padding_right=1)
        btn.on_mouse_down = _make_page_handler(page)
        children.append(btn)

    next_btn = Box(Text(">", fg="#cccccc"), padding_left=1, padding_right=1)
    next_btn.on_mouse_down = _next
    children.append(next_btn)

    return Box(*children, flex_direction="row", **kwargs)
