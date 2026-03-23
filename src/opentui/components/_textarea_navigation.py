"""Navigation, editing, and undo/redo mixin for TextareaRenderable."""

from __future__ import annotations

import contextlib

from .textarea_text_utils import (
    line_col_to_offset,
    next_word_boundary,
    offset_to_line_col,
    prev_word_boundary,
    str_display_width,
)


class _NavigationMixin:
    """Cursor movement, text editing, and undo/redo operations.

    Expects host class to provide: _edit_buffer, _editor_view, _wrap_mode,
    _yoga_node, _on_content_change, _on_cursor_change, and selection mixin methods.
    """

    def move_cursor_left(self, select: bool = False) -> None:
        if select:
            text = self.plain_text
            offset = line_col_to_offset(text, *self.cursor_position)
            new_offset = max(0, offset - 1)
            self._extend_selection(offset, new_offset)
        else:
            self.clear_selection()
        self._edit_buffer.move_cursor_left()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def move_cursor_right(self, select: bool = False) -> None:
        if select:
            text = self.plain_text
            offset = line_col_to_offset(text, *self.cursor_position)
            new_offset = min(len(text), offset + 1)
            self._extend_selection(offset, new_offset)
        else:
            self.clear_selection()
        self._edit_buffer.move_cursor_right()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def _move_cursor_vertical(self, direction: str, select: bool = False) -> None:
        if direction == "up":
            visual_fn = self._editor_view.move_up_visual
            buffer_fn = self._edit_buffer.move_cursor_up
        else:
            visual_fn = self._editor_view.move_down_visual
            buffer_fn = self._edit_buffer.move_cursor_down
        move = visual_fn if self._wrap_mode != "none" else buffer_fn
        if select:
            text = self.plain_text
            old_offset = line_col_to_offset(text, *self.cursor_position)
            move()
            new_offset = line_col_to_offset(text, *self.cursor_position)
            self._extend_selection(old_offset, new_offset)
        else:
            self.clear_selection()
            move()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def move_cursor_up(self, select: bool = False) -> None:
        self._move_cursor_vertical("up", select)

    def move_cursor_down(self, select: bool = False) -> None:
        self._move_cursor_vertical("down", select)

    def move_word_forward(self, select: bool = False) -> None:
        text = self.plain_text
        offset = line_col_to_offset(text, *self.cursor_position)
        new_offset = next_word_boundary(text, offset)
        if select:
            self._extend_selection(offset, new_offset)
        else:
            self.clear_selection()
        new_pos = offset_to_line_col(text, new_offset)
        self._edit_buffer.set_cursor(new_pos[0], new_pos[1])
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def move_word_backward(self, select: bool = False) -> None:
        text = self.plain_text
        offset = line_col_to_offset(text, *self.cursor_position)
        new_offset = prev_word_boundary(text, offset)
        if select:
            self._extend_selection(offset, new_offset)
        else:
            self.clear_selection()
        new_pos = offset_to_line_col(text, new_offset)
        self._edit_buffer.set_cursor(new_pos[0], new_pos[1])
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def delete_char(self) -> None:
        if self.has_selection:
            self._delete_selection()
            return
        self._edit_buffer.delete_char()
        self._notify_content_changed()
        self.mark_dirty()

    def delete_char_backward(self) -> None:
        if self.has_selection:
            self._delete_selection()
            return
        self._edit_buffer.delete_char_backward()
        self._notify_content_changed()
        self._notify_cursor_changed()
        self.mark_dirty()

    def newline(self) -> None:
        if self.has_selection:
            self._delete_selection()
        self._edit_buffer.newline()
        self._notify_content_changed()
        self._notify_cursor_changed()
        self.mark_dirty()

    def delete_line(self) -> None:
        line, col = self.cursor_position
        text = self.plain_text
        lines = text.split("\n")
        if line >= len(lines):
            return
        line_start = sum(len(lines[i]) + 1 for i in range(line))
        line_end = line_start + len(lines[line])
        if line < len(lines) - 1:
            line_end += 1  # include \n
        elif line > 0:
            line_start -= 1
        start_pos = offset_to_line_col(text, line_start)
        end_pos = offset_to_line_col(text, line_end)
        self._edit_buffer.delete_range(start_pos[0], start_pos[1], end_pos[0], end_pos[1])
        new_text = self._edit_buffer.get_text()
        new_lines = new_text.split("\n")
        new_line = min(line, len(new_lines) - 1)
        new_col = min(col, len(new_lines[new_line]) if new_lines else 0)
        self._edit_buffer.set_cursor(new_line, new_col)
        self._notify_content_changed()
        self.mark_dirty()

    def delete_to_line_end(self) -> None:
        line, col = self.cursor_position
        text = self.plain_text
        lines = text.split("\n")
        if line >= len(lines):
            return
        line_display_width = str_display_width(lines[line])
        if col >= line_display_width:
            return
        self._edit_buffer.delete_range(line, col, line, line_display_width)
        self._notify_content_changed()
        self.mark_dirty()

    def delete_to_line_start(self) -> None:
        line, col = self.cursor_position
        if col <= 0:
            return
        self._edit_buffer.delete_range(line, 0, line, col)
        self._edit_buffer.set_cursor(line, 0)
        self._notify_content_changed()
        self.mark_dirty()

    def delete_word_forward(self) -> None:
        text = self.plain_text
        offset = line_col_to_offset(text, *self.cursor_position)
        end_offset = next_word_boundary(text, offset)
        if end_offset == offset:
            return
        end_pos = offset_to_line_col(text, end_offset)
        line, col = self.cursor_position
        self._edit_buffer.delete_range(line, col, end_pos[0], end_pos[1])
        self._notify_content_changed()
        self.mark_dirty()

    def delete_word_backward(self) -> None:
        text = self.plain_text
        offset = line_col_to_offset(text, *self.cursor_position)
        start_offset = prev_word_boundary(text, offset)
        if start_offset == offset:
            return
        start_pos = offset_to_line_col(text, start_offset)
        line, col = self.cursor_position
        self._edit_buffer.delete_range(start_pos[0], start_pos[1], line, col)
        self._edit_buffer.set_cursor(start_pos[0], start_pos[1])
        self._notify_content_changed()
        self.mark_dirty()

    def goto_line_home(self, select: bool = False) -> None:
        """Move cursor to start of current line.

        If already at col 0 and not on the first line, wraps to the end of the
        previous line.
        """
        line, col = self.cursor_position
        text = self.plain_text
        lines = text.split("\n")

        if col == 0 and line > 0:
            target_line = line - 1
            target_col = str_display_width(lines[target_line])
            if select:
                old_offset = line_col_to_offset(text, line, col)
                new_offset = line_col_to_offset(text, target_line, target_col)
                self._extend_selection(old_offset, new_offset)
            else:
                self.clear_selection()
            self._edit_buffer.set_cursor(target_line, target_col)
        else:
            if select:
                old_offset = line_col_to_offset(text, line, col)
                new_offset = line_col_to_offset(text, line, 0)
                self._extend_selection(old_offset, new_offset)
            else:
                self.clear_selection()
            self._edit_buffer.set_cursor(line, 0)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_line_end(self, select: bool = False) -> None:
        """Move cursor to end of current line.

        If already at end of line and not on the last line, wraps to the start
        of the next line.
        """
        line, col = self.cursor_position
        text = self.plain_text
        lines = text.split("\n")
        if line >= len(lines):
            return
        line_display_width = str_display_width(lines[line])

        if col >= line_display_width and line < len(lines) - 1:
            target_line = line + 1
            target_col = 0
            if select:
                old_offset = line_col_to_offset(text, line, col)
                new_offset = line_col_to_offset(text, target_line, target_col)
                self._extend_selection(old_offset, new_offset)
            else:
                self.clear_selection()
            self._edit_buffer.set_cursor(target_line, target_col)
        else:
            if select:
                old_offset = line_col_to_offset(text, line, col)
                new_offset = line_col_to_offset(text, line, line_display_width)
                self._extend_selection(old_offset, new_offset)
            else:
                self.clear_selection()
            self._edit_buffer.set_cursor(line, line_display_width)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_visual_line_home(self, select: bool = False) -> None:
        """Move cursor to start of the current visual line.

        When wrapping is enabled, this goes to the start of the visual (wrapped)
        line, not the logical line. Without wrapping, behaves same as line-home
        (without wrap-around behavior).
        """
        text = self.plain_text
        old_offset = line_col_to_offset(text, *self.cursor_position)

        sol = self._editor_view.get_visual_sol()
        target_line = sol.logical_row
        target_col = sol.logical_col

        if select:
            new_offset = line_col_to_offset(text, target_line, target_col)
            self._extend_selection(old_offset, new_offset)
        else:
            self.clear_selection()

        self._edit_buffer.set_cursor(target_line, target_col)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_visual_line_end(self, select: bool = False) -> None:
        """Move cursor to end of the current visual line.

        When wrapping is enabled, this goes to the end of the visual (wrapped)
        line, not the logical line. Without wrapping, behaves same as line-end
        (without wrap-around behavior).
        """
        text = self.plain_text
        old_offset = line_col_to_offset(text, *self.cursor_position)

        eol = self._editor_view.get_visual_eol()
        target_line = eol.logical_row
        target_col = eol.logical_col

        if select:
            new_offset = line_col_to_offset(text, target_line, target_col)
            self._extend_selection(old_offset, new_offset)
        else:
            self.clear_selection()

        self._edit_buffer.set_cursor(target_line, target_col)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_buffer_home(self, select: bool = False) -> None:
        if select:
            text = self.plain_text
            old_offset = line_col_to_offset(text, *self.cursor_position)
            self._extend_selection(old_offset, 0)
        else:
            self.clear_selection()
        self._edit_buffer.set_cursor(0, 0)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_buffer_end(self, select: bool = False) -> None:
        text = self.plain_text
        lines = text.split("\n")
        last_line = max(0, len(lines) - 1)
        last_col = str_display_width(lines[last_line]) if lines else 0
        if select:
            old_offset = line_col_to_offset(text, *self.cursor_position)
            self._extend_selection(old_offset, len(text))
        else:
            self.clear_selection()
        self._edit_buffer.set_cursor(last_line, last_col)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_line(self, line_num: int) -> None:
        """Go to a specific line number (0-based).

        Uses the native gotoLine which moves to the END of the target line.
        """
        self._edit_buffer.goto_line(line_num)
        self._follow_cursor()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def undo(self) -> bool:
        self.clear_selection()
        result = self._edit_buffer.undo()
        if result:
            self._notify_content_changed()
            self._notify_cursor_changed()
            self.mark_dirty()
        return bool(result)

    def redo(self) -> bool:
        self.clear_selection()
        result = self._edit_buffer.redo()
        if result:
            self._notify_content_changed()
            self._notify_cursor_changed()
            self.mark_dirty()
        return bool(result)

    def _notify_content_changed(self) -> None:
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self._follow_cursor()
        self.emit("contentChanged", self.plain_text)
        if self._on_content_change:
            self._on_content_change(self.plain_text)

    def _notify_cursor_changed(self) -> None:
        self._follow_cursor()
        pos = self.cursor_position
        self.emit("cursorChanged", pos)
        if self._on_cursor_change:
            self._on_cursor_change(pos)

    def _follow_cursor(self) -> None:
        with contextlib.suppress(Exception):
            self._editor_view.get_visual_cursor()
