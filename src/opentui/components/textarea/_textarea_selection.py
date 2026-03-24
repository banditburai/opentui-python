"""Selection management mixin for TextareaRenderable."""

from __future__ import annotations

import contextlib

from ..text_renderable_utils import get_scroll_adjusted_position
from .textarea_text_utils import (
    offset_to_line_col,
)


class _SelectionMixin:
    """Manages text selection state, selection changes, and selection queries.

    Expects host class to provide: _selection_start, _selection_end,
    _cross_renderable_selection_active, _is_dragging_selection,
    _keyboard_selection_active, _editor_view, _edit_buffer,
    _selection_bg_color, _selection_fg_color, _x, _y.
    """

    @property
    def has_selection(self) -> bool:
        if self._cross_renderable_selection_active:
            try:
                if self._editor_view.has_selection():
                    return True
            except Exception:
                pass
        return (
            self._selection_start is not None
            and self._selection_end is not None
            and self._selection_start != self._selection_end
        )

    @property
    def selection(self) -> tuple[int, int] | None:
        if self._cross_renderable_selection_active:
            try:
                native_sel = self._editor_view.get_selection()
                if native_sel is not None:
                    return (native_sel["start"], native_sel["end"])
            except Exception:
                pass
        if self._selection_start is None or self._selection_end is None:
            return None
        s_start = min(self._selection_start, self._selection_end)
        s_end = max(self._selection_start, self._selection_end)
        if s_start == s_end:
            return None
        return (s_start, s_end)

    def set_selection(self, start: int, end: int) -> None:
        text = self.plain_text
        text_len = len(text)
        self._selection_start = max(0, min(start, text_len))
        self._selection_end = max(0, min(end, text_len))
        self.mark_paint_dirty()

    def clear_selection(self) -> None:
        self._selection_start = None
        self._selection_end = None
        if self._cross_renderable_selection_active:
            self._cross_renderable_selection_active = False
            with contextlib.suppress(Exception):
                self._editor_view.reset_local_selection()
        self.mark_paint_dirty()

    def get_selected_text(self) -> str:
        if self._cross_renderable_selection_active:
            try:
                native_text = self._editor_view.get_selected_text()
                if native_text:
                    return native_text
            except Exception:
                pass
        sel = self.selection
        if sel is None:
            return ""
        text = self.plain_text
        return text[sel[0] : sel[1]]

    def on_selection_changed(self, selection) -> bool:
        """Converts global selection coordinates to local and applies via the
        native editor view's local selection API.  Returns True if this
        renderable has a selection after the change.

        When the textarea is managing its own drag selection internally
        (e.g., single-renderable mouse drag within the textarea), defer
        to the internal path rather than applying cross-renderable
        selection on top.
        """
        if self._is_dragging_selection:
            return self.has_selection

        from ...selection import convert_global_to_local_selection

        screen_x, screen_y = get_scroll_adjusted_position(self)
        local_sel = convert_global_to_local_selection(selection, screen_x, screen_y)

        update_cursor = True
        follow_cursor = self._keyboard_selection_active

        if local_sel is None or not local_sel.is_active:
            self._keyboard_selection_active = False
            self._cross_renderable_selection_active = False
            self._editor_view.reset_local_selection()
            self._selection_start = None
            self._selection_end = None
            self.mark_paint_dirty()
            return False

        self._cross_renderable_selection_active = True

        changed: bool
        if selection is not None and selection.is_start:
            changed = self._editor_view.set_local_selection(
                local_sel.anchor_x,
                local_sel.anchor_y,
                local_sel.focus_x,
                local_sel.focus_y,
                update_cursor=update_cursor,
                follow_cursor=follow_cursor,
                bg_color=self._selection_bg_color,
                fg_color=self._selection_fg_color,
            )
        else:
            changed = self._editor_view.update_local_selection(
                local_sel.anchor_x,
                local_sel.anchor_y,
                local_sel.focus_x,
                local_sel.focus_y,
                update_cursor=update_cursor,
                follow_cursor=follow_cursor,
                bg_color=self._selection_bg_color,
                fg_color=self._selection_fg_color,
            )

        if changed:
            self.mark_paint_dirty()

        return self.has_selection

    def select_all(self) -> None:
        text = self.plain_text
        self._selection_start = 0
        self._selection_end = len(text)
        lines = text.split("\n")
        last_line = len(lines) - 1
        last_col = len(lines[-1]) if lines else 0
        self._edit_buffer.set_cursor(last_line, last_col)
        self.mark_paint_dirty()

    def _delete_selection(self) -> bool:
        sel = self.selection
        if sel is None:
            return False
        text = self.plain_text
        start_pos = offset_to_line_col(text, sel[0])
        end_pos = offset_to_line_col(text, sel[1])
        self._edit_buffer.delete_range(start_pos[0], start_pos[1], end_pos[0], end_pos[1])
        self._edit_buffer.set_cursor(start_pos[0], start_pos[1])
        self.clear_selection()
        self._notify_content_changed()
        return True

    def _extend_selection(self, old_offset: int, new_offset: int) -> None:
        if self._selection_start is None:
            self._selection_start = old_offset
        self._selection_end = new_offset

    def get_selection_dict(self) -> dict[str, int] | None:
        sel = self.selection
        if sel is None:
            return None
        return {"start": sel[0], "end": sel[1]}
