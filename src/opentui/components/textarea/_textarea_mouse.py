"""Mouse interaction mixin for TextareaRenderable."""

from __future__ import annotations

import contextlib
from typing import Any

from .textarea_text_utils import (
    line_col_to_offset,
    str_display_width,
)


class _MouseMixin:
    """Handles mouse down/drag/up, scroll events, and auto-scroll during drag.

    Expects host class to provide: _edit_buffer, _editor_view, _selectable,
    _x, _y, _layout_width, _layout_height, _wrap_mode, _scroll_margin,
    _drag_anchor_*, _drag_focus_*, _is_dragging_selection, _auto_scroll_*,
    _scroll_speed, _selection_start, _selection_end, _selection_bg_color,
    _selection_fg_color, _destroyed.
    """

    def _screen_to_buffer_pos(self, screen_x: int, screen_y: int) -> tuple[int, int]:
        local_x = screen_x - self._x
        local_y = screen_y - self._y

        viewport = self._editor_view.get_viewport()
        offset_x = viewport.get("offsetX", 0)
        offset_y = viewport.get("offsetY", 0)

        buf_line = local_y + offset_y
        buf_col = local_x + offset_x

        text = self.plain_text
        lines = text.split("\n")
        max_line = max(0, len(lines) - 1)
        buf_line = max(0, min(buf_line, max_line))

        if buf_line < len(lines):
            line_width = str_display_width(lines[buf_line])
            buf_col = max(0, min(buf_col, line_width))
        else:
            buf_col = 0

        return (buf_line, buf_col)

    def _handle_mouse_down(self, event: Any) -> None:
        if self._destroyed:
            return
        if not self._selectable:
            return

        line, col = self._screen_to_buffer_pos(event.x, event.y)
        self._edit_buffer.set_cursor(line, col)
        self._notify_cursor_changed()

        self.clear_selection()

        self._drag_anchor_x = event.x - self._x
        self._drag_anchor_y = event.y - self._y
        self._drag_focus_x = self._drag_anchor_x
        self._drag_focus_y = self._drag_anchor_y
        self._is_dragging_selection = False
        self._drag_anchor_line = line
        self._drag_anchor_col = col

        self.mark_paint_dirty()

    def _handle_mouse_drag(self, event: Any) -> None:
        if self._destroyed:
            return
        if not self._selectable:
            return
        if self._drag_anchor_x is None:
            return

        self._is_dragging_selection = True

        viewport = self._editor_view.get_viewport()
        offset_x = viewport.get("offsetX", 0)
        offset_y = viewport.get("offsetY", 0)
        vp_height = viewport.get("height", self._layout_height or 1)

        local_x = event.x - self._x
        local_y = event.y - self._y
        self._drag_focus_x = local_x
        self._drag_focus_y = local_y

        text = self.plain_text
        lines = text.split("\n")
        max_line = max(0, len(lines) - 1)

        focus_line = local_y + offset_y
        focus_col = local_x + offset_x

        focus_line = max(0, min(focus_line, max_line))
        if focus_line < len(lines):
            line_width = str_display_width(lines[focus_line])
            focus_col = max(0, min(focus_col, line_width))
        else:
            focus_col = 0

        anchor_line = self._drag_anchor_line
        anchor_col = self._drag_anchor_col
        anchor_line = max(0, min(anchor_line, max_line))
        if anchor_line < len(lines):
            anchor_col = max(0, min(anchor_col, str_display_width(lines[anchor_line])))
        else:
            anchor_col = 0

        if self._drag_anchor_x is None or self._drag_anchor_y is None:
            return
        try:
            self._editor_view.set_local_selection(
                self._drag_anchor_x,
                self._drag_anchor_y,
                local_x,
                local_y,
                update_cursor=True,
                follow_cursor=False,
                bg_color=self._selection_bg_color,
                fg_color=self._selection_fg_color,
            )
            ev_sel = self._editor_view.get_selection()
            if ev_sel is not None:
                self._selection_start = ev_sel.get("start", 0)
                self._selection_end = ev_sel.get("end", 0)
            else:
                self._selection_start = None
                self._selection_end = None
        except Exception:
            anchor_offset = line_col_to_offset(text, anchor_line, anchor_col)
            focus_offset = line_col_to_offset(text, focus_line, focus_col)
            self._selection_start = min(anchor_offset, focus_offset)
            self._selection_end = max(anchor_offset, focus_offset)

        self._edit_buffer.set_cursor(focus_line, focus_col)

        scroll_margin = max(1, int(vp_height * self._scroll_margin))
        if local_y < scroll_margin:
            self._auto_scroll_velocity = -self._scroll_speed
        elif local_y >= vp_height - scroll_margin:
            self._auto_scroll_velocity = self._scroll_speed
        else:
            self._auto_scroll_velocity = 0

        self.mark_paint_dirty()

    def _handle_mouse_drag_end(self, event: Any) -> None:
        if self._destroyed:
            return
        self._is_dragging_selection = False
        self._auto_scroll_velocity = 0.0
        self._auto_scroll_accumulator = 0.0

    def _handle_mouse_up(self, event: Any) -> None:
        if self._destroyed:
            return
        self._is_dragging_selection = False
        self._auto_scroll_velocity = 0.0
        self._auto_scroll_accumulator = 0.0
        self._drag_anchor_x = None
        self._drag_anchor_y = None

    def _handle_scroll_event(self, event: Any) -> None:
        if self._destroyed:
            return

        direction = getattr(event, "scroll_direction", None)
        if direction is None:
            delta = getattr(event, "scroll_delta", 0)
            direction = "down" if delta > 0 else "up"

        viewport = self._editor_view.get_viewport()
        offset_x = viewport.get("offsetX", 0)
        offset_y = viewport.get("offsetY", 0)
        vp_width = viewport.get("width", self._layout_width or 80)
        vp_height = viewport.get("height", self._layout_height or 24)

        if direction in ("up", "down"):
            scroll_delta = 1 if direction == "down" else -1
            total_virtual = len(self.plain_text.split("\n"))
            with contextlib.suppress(Exception):
                total_virtual = self._editor_view.get_total_virtual_line_count()
            max_offset_y = max(0, total_virtual - vp_height)
            new_offset_y = max(0, min(offset_y + scroll_delta, max_offset_y))

            if new_offset_y != offset_y:
                cursor_line, cursor_col = self.cursor_position
                if cursor_line < new_offset_y:
                    self._edit_buffer.set_cursor(new_offset_y, cursor_col)
                elif cursor_line >= new_offset_y + vp_height:
                    self._edit_buffer.set_cursor(new_offset_y + vp_height - 1, cursor_col)

                self._editor_view.set_viewport(offset_x, new_offset_y, vp_width, vp_height)
                self.mark_paint_dirty()

        elif direction in ("left", "right"):
            if self._wrap_mode != "none":
                return

            scroll_delta = 1 if direction == "right" else -1
            new_offset_x = max(0, offset_x + scroll_delta)

            if new_offset_x != offset_x:
                self._editor_view.set_viewport(new_offset_x, offset_y, vp_width, vp_height)
                self.mark_paint_dirty()

    def handle_scroll_event(self, event: Any) -> None:
        self._handle_scroll_event(event)

    def _tick_auto_scroll(self, delta_time: float) -> None:
        """Advance auto-scroll accumulator and scroll the viewport.

        Advances auto-scroll during drag selection.
        ``delta_time`` is in seconds (render frames pass 1/60 by default).
        Our ``_scroll_speed``
        is already in lines-per-second so we work in seconds here.
        """
        if self._auto_scroll_velocity == 0.0:
            return
        if not self.has_selection:
            return

        self._auto_scroll_accumulator += self._auto_scroll_velocity * delta_time

        lines_to_scroll = int(abs(self._auto_scroll_accumulator))
        if lines_to_scroll > 0:
            direction = 1 if self._auto_scroll_velocity > 0 else -1
            viewport = self._editor_view.get_viewport()
            offset_x = viewport.get("offsetX", 0)
            offset_y = viewport.get("offsetY", 0)
            vp_width = viewport.get("width", self._layout_width or 80)
            vp_height = viewport.get("height", self._layout_height or 24)

            total_virtual = self._editor_view.get_total_virtual_line_count()
            max_offset_y = max(0, total_virtual - vp_height)
            new_offset_y = max(0, min(offset_y + direction * lines_to_scroll, max_offset_y))

            if new_offset_y != offset_y:
                self._editor_view.set_viewport(offset_x, new_offset_y, vp_width, vp_height)

                if self._is_dragging_selection and self._drag_focus_y is not None:
                    self._update_drag_selection_after_scroll()

            self._auto_scroll_accumulator -= direction * lines_to_scroll

    def _update_drag_selection_after_scroll(self) -> None:
        """Re-apply drag selection after auto-scroll moved the viewport."""
        if self._drag_anchor_x is None or self._drag_focus_y is None:
            return

        viewport = self._editor_view.get_viewport()
        offset_x = viewport.get("offsetX", 0)
        offset_y = viewport.get("offsetY", 0)

        text = self.plain_text
        lines = text.split("\n")
        max_line = max(0, len(lines) - 1)

        focus_line = self._drag_focus_y + offset_y
        focus_col = (self._drag_focus_x or 0) + offset_x

        focus_line = max(0, min(focus_line, max_line))
        if focus_line < len(lines):
            line_width = str_display_width(lines[focus_line])
            focus_col = max(0, min(focus_col, line_width))
        else:
            focus_col = 0

        anchor_line = self._drag_anchor_line
        anchor_col = self._drag_anchor_col

        anchor_offset = line_col_to_offset(text, anchor_line, anchor_col)
        focus_offset = line_col_to_offset(text, focus_line, focus_col)
        self._selection_start = min(anchor_offset, focus_offset)
        self._selection_end = max(anchor_offset, focus_offset)

        self._edit_buffer.set_cursor(focus_line, focus_col)
        self.mark_paint_dirty()
