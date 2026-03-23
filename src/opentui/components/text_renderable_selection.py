"""Selection helpers for TextRenderable."""

from __future__ import annotations

import contextlib


def has_selection(text) -> bool:
    if text._cross_renderable_selection_active:
        try:
            if text._text_buffer_view.has_selection():
                return True
        except Exception:
            pass
    return text._current_selection is not None


def get_selection(text) -> dict[str, int] | None:
    if text._cross_renderable_selection_active:
        try:
            native_sel = text._text_buffer_view.get_selection()
            if native_sel is not None:
                return native_sel
        except Exception:
            pass
    return text._current_selection


def get_selected_text(text) -> str:
    if text._cross_renderable_selection_active:
        try:
            native_text = text._text_buffer_view.get_selected_text()
            if native_text:
                return native_text
        except Exception:
            pass
    selection = text._current_selection
    if selection is None:
        return ""
    start = selection["start"]
    end = selection["end"]
    if start >= end:
        return ""
    plain_text = text._text_buffer.get_plain_text()
    return plain_text[start:end]


def on_selection_changed(text, selection) -> bool:
    from ..selection import convert_global_to_local_selection
    from .text_renderable_utils import get_scroll_adjusted_position

    screen_x, screen_y = get_scroll_adjusted_position(text)
    local_sel = convert_global_to_local_selection(selection, screen_x, screen_y)

    if local_sel is None or not local_sel.is_active:
        text._cross_renderable_selection_active = False
        text._text_buffer_view.reset_local_selection()
        text._current_selection = None
        text.mark_paint_dirty()
        return False

    text._cross_renderable_selection_active = True

    if selection is not None and selection.is_start:
        changed = text._text_buffer_view.set_local_selection(
            local_sel.anchor_x,
            local_sel.anchor_y,
            local_sel.focus_x,
            local_sel.focus_y,
            bg_color=text._selection_bg_color,
            fg_color=text._selection_fg_color,
        )
    else:
        changed = text._text_buffer_view.update_local_selection(
            local_sel.anchor_x,
            local_sel.anchor_y,
            local_sel.focus_x,
            local_sel.focus_y,
            bg_color=text._selection_bg_color,
            fg_color=text._selection_fg_color,
        )

    if changed:
        text.mark_paint_dirty()

    return has_selection(text)


def set_selection(text, start: int, end: int) -> None:
    if start > end:
        start, end = end, start
    plain_text = text._text_buffer.get_plain_text()
    text_len = len(plain_text)
    start = max(0, min(start, text_len))
    end = max(0, min(end, text_len))
    if start == end:
        text._current_selection = None
    else:
        text._current_selection = {"start": start, "end": end}
    with contextlib.suppress(Exception):
        text._text_buffer_view.set_selection(start, end)
    text.mark_paint_dirty()


def clear_selection(text) -> None:
    text._current_selection = None
    text._cross_renderable_selection_active = False
    with contextlib.suppress(Exception):
        text._text_buffer_view.reset_selection()
    with contextlib.suppress(Exception):
        text._text_buffer_view.reset_local_selection()
    text.mark_paint_dirty()


__all__ = [
    "clear_selection",
    "get_selected_text",
    "get_selection",
    "has_selection",
    "on_selection_changed",
    "set_selection",
]
