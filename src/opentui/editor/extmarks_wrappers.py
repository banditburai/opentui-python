"""Installer functions that monkey-patch EditBuffer/EditorView for extmark tracking.

Each ``install_*`` function takes an ``ExtmarksController`` instance plus
the ``edit_buffer`` and/or ``editor_view`` objects, saves their original
methods, creates closures that delegate to the controller, and patches the
methods in-place.

These were originally ``_wrap_*`` methods on ``ExtmarksController``; they
are extracted here so the controller class stays focused on data management.
"""

from __future__ import annotations

from typing import Any

from ..structs import display_width as _string_width


def install_cursor_wrappers(controller: Any, eb: Any, ev: Any) -> None:
    def move_cursor_left() -> None:
        if controller._destroyed:
            controller._orig_move_cursor_left()
            return

        current_offset = ev.get_visual_cursor().offset
        has_selection = ev.has_selection()

        if has_selection:
            controller._orig_move_cursor_left()
            return

        target_offset = current_offset - 1
        if target_offset < 0:
            controller._orig_move_cursor_left()
            return

        virtual_em = controller._find_virtual_extmark_containing(target_offset)
        if virtual_em and current_offset >= virtual_em.end:
            eb.set_cursor_by_offset(virtual_em.start - 1)
            return

        controller._orig_move_cursor_left()

    def move_cursor_right() -> None:
        if controller._destroyed:
            controller._orig_move_cursor_right()
            return

        current_offset = ev.get_visual_cursor().offset
        has_selection = ev.has_selection()

        if has_selection:
            controller._orig_move_cursor_right()
            return

        target_offset = current_offset + 1
        text_length = len(eb.get_text())

        if target_offset > text_length:
            controller._orig_move_cursor_right()
            return

        virtual_em = controller._find_virtual_extmark_containing(target_offset)
        if virtual_em and current_offset <= virtual_em.start:
            eb.set_cursor_by_offset(virtual_em.end)
            return

        controller._orig_move_cursor_right()

    def set_cursor_by_offset(offset: int) -> None:
        if controller._destroyed:
            controller._orig_set_cursor_by_offset(offset)
            return

        current_offset = ev.get_visual_cursor().offset
        has_selection = ev.has_selection()

        if has_selection:
            controller._orig_set_cursor_by_offset(offset)
            return

        moving_forward = offset > current_offset

        if moving_forward:
            virtual_em = controller._find_virtual_extmark_containing(offset)
            if virtual_em and current_offset <= virtual_em.start:
                controller._orig_set_cursor_by_offset(virtual_em.end)
                return
        else:
            for em in controller._extmarks.values():
                if (
                    em.virtual
                    and current_offset >= em.end
                    and offset < em.end
                    and offset >= em.start
                ):
                    controller._orig_set_cursor_by_offset(em.start - 1)
                    return

        controller._orig_set_cursor_by_offset(offset)

    def move_up_visual() -> None:
        if controller._destroyed:
            controller._orig_move_up_visual()
            return

        has_selection = ev.has_selection()

        if has_selection:
            controller._orig_move_up_visual()
            return

        controller._orig_move_up_visual()
        new_offset = ev.get_visual_cursor().offset

        virtual_em = controller._find_virtual_extmark_containing(new_offset)
        if virtual_em:
            distance_to_start = new_offset - virtual_em.start
            distance_to_end = virtual_em.end - new_offset

            if distance_to_start < distance_to_end:
                ev.set_cursor_by_offset(virtual_em.start - 1)
            else:
                ev.set_cursor_by_offset(virtual_em.end)

    def move_down_visual() -> None:
        if controller._destroyed:
            controller._orig_move_down_visual()
            return

        has_selection = ev.has_selection()

        if has_selection:
            controller._orig_move_down_visual()
            return

        current_offset = ev.get_visual_cursor().offset
        controller._orig_move_down_visual()
        new_offset = ev.get_visual_cursor().offset

        virtual_em = controller._find_virtual_extmark_containing(new_offset)
        if virtual_em:
            distance_to_start = new_offset - virtual_em.start
            distance_to_end = virtual_em.end - new_offset

            if distance_to_start < distance_to_end:
                adjusted_offset = virtual_em.start - 1
                target_offset = (
                    virtual_em.end if adjusted_offset <= current_offset else adjusted_offset
                )
                ev.set_cursor_by_offset(target_offset)
            else:
                ev.set_cursor_by_offset(virtual_em.end)

    eb.move_cursor_left = move_cursor_left
    eb.move_cursor_right = move_cursor_right
    eb.set_cursor_by_offset = set_cursor_by_offset
    ev.move_up_visual = move_up_visual
    ev.move_down_visual = move_down_visual


def install_deletion_wrappers(controller: Any, eb: Any, ev: Any) -> None:
    def delete_char_backward() -> None:
        if controller._destroyed:
            controller._orig_delete_char_backward()
            return

        controller._save_snapshot()

        current_offset = ev.get_visual_cursor().offset
        had_selection = ev.has_selection()

        if current_offset == 0:
            controller._orig_delete_char_backward()
            return

        if had_selection:
            controller._orig_delete_char_backward()
            return

        target_offset = current_offset - 1
        virtual_em = controller._find_virtual_extmark_containing(target_offset)

        if virtual_em and current_offset == virtual_em.end:
            controller._delete_virtual_extmark_range(virtual_em)
            return

        controller._orig_delete_char_backward()
        controller.adjust_extmarks_after_deletion(target_offset, 1)

    def delete_char() -> None:
        if controller._destroyed:
            controller._orig_delete_char()
            return

        controller._save_snapshot()

        current_offset = ev.get_visual_cursor().offset
        text_length = len(eb.get_text())
        had_selection = ev.has_selection()

        if current_offset >= text_length:
            controller._orig_delete_char()
            return

        if had_selection:
            controller._orig_delete_char()
            return

        target_offset = current_offset
        virtual_em = controller._find_virtual_extmark_containing(target_offset)

        if virtual_em and current_offset == virtual_em.start:
            controller._delete_virtual_extmark_range(virtual_em)
            return

        controller._orig_delete_char()
        controller.adjust_extmarks_after_deletion(target_offset, 1)

    def delete_range(start_line: int, start_col: int, end_line: int, end_col: int) -> None:
        if controller._destroyed:
            controller._orig_delete_range(start_line, start_col, end_line, end_col)
            return

        controller._save_snapshot()

        start_offset = controller._position_to_offset(start_line, start_col)
        end_offset = controller._position_to_offset(end_line, end_col)
        length = end_offset - start_offset

        controller._orig_delete_range(start_line, start_col, end_line, end_col)
        controller.adjust_extmarks_after_deletion(start_offset, length)

    def delete_line() -> None:
        if controller._destroyed:
            controller._orig_delete_line()
            return

        controller._save_snapshot()

        text = eb.get_text()
        current_offset = ev.get_visual_cursor().offset

        line_start = 0
        for i in range(current_offset - 1, -1, -1):
            if text[i] == "\n":
                line_start = i + 1
                break

        line_end = len(text)
        for i in range(current_offset, len(text)):
            if text[i] == "\n":
                line_end = i + 1
                break

        delete_length = line_end - line_start

        controller._orig_delete_line()
        controller.adjust_extmarks_after_deletion(line_start, delete_length)

    eb.delete_char_backward = delete_char_backward
    eb.delete_char = delete_char
    eb.delete_range = delete_range
    eb.delete_line = delete_line


def install_insertion_wrappers(controller: Any, eb: Any, ev: Any) -> None:
    # Guard against re-entry: insert_char/new_line may internally call
    # insert_text (e.g. MockEditBuffer.insert_char delegates to insert_text).
    # Without this guard, extmark positions would be adjusted twice.
    _inserting = [False]

    def insert_text(text: str) -> None:
        if _inserting[0] or controller._destroyed:
            controller._orig_insert_text(text)
            return

        _inserting[0] = True
        try:
            controller._save_snapshot()
            current_offset = ev.get_visual_cursor().offset
            controller._orig_insert_text(text)
            controller._adjust_extmarks_after_insertion(current_offset, _string_width(text))
        finally:
            _inserting[0] = False

    def insert_char(char: str) -> None:
        if _inserting[0] or controller._destroyed:
            controller._orig_insert_char(char)
            return

        _inserting[0] = True
        try:
            controller._save_snapshot()
            current_offset = ev.get_visual_cursor().offset
            controller._orig_insert_char(char)
            controller._adjust_extmarks_after_insertion(current_offset, _string_width(char))
        finally:
            _inserting[0] = False

    def set_text(text: str) -> None:
        if controller._destroyed:
            controller._orig_set_text(text)
            return

        controller.clear()
        controller._orig_set_text(text)

    def replace_text(text: str) -> None:
        if controller._destroyed:
            controller._orig_replace_text(text)
            return

        controller._save_snapshot()
        controller.clear()
        controller._orig_replace_text(text)

    def clear_buf() -> None:
        if controller._destroyed:
            controller._orig_clear()
            return

        controller._save_snapshot()
        controller.clear()
        controller._orig_clear()

    def new_line() -> None:
        if _inserting[0] or controller._destroyed:
            controller._orig_new_line()
            return

        _inserting[0] = True
        try:
            controller._save_snapshot()
            current_offset = ev.get_visual_cursor().offset
            controller._orig_new_line()
            controller._adjust_extmarks_after_insertion(current_offset, 1)
        finally:
            _inserting[0] = False

    eb.insert_text = insert_text
    eb.insert_char = insert_char
    eb.set_text = set_text
    eb.replace_text = replace_text
    eb.clear = clear_buf
    eb.new_line = new_line


def install_delete_selected_text_wrapper(controller: Any, ev: Any) -> None:
    def delete_selected_text() -> None:
        if controller._destroyed:
            controller._orig_delete_selected_text()
            return

        controller._save_snapshot()

        selection = ev.get_selection()
        if selection is None:
            controller._orig_delete_selected_text()
            return

        delete_offset = min(selection.start, selection.end)
        delete_length = abs(selection.end - selection.start)

        controller._orig_delete_selected_text()

        if delete_length > 0:
            controller.adjust_extmarks_after_deletion(delete_offset, delete_length)

    ev.delete_selected_text = delete_selected_text


def install_undo_redo_wrappers(controller: Any, eb: Any) -> None:
    """Create closures and monkey-patch undo/redo methods onto *eb*."""

    def undo() -> str | None:
        return controller._undo_or_redo(direction="undo")

    def redo() -> str | None:
        return controller._undo_or_redo(direction="redo")

    eb.undo = undo
    eb.redo = redo
