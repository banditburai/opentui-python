"""ExtmarksController for tracking marked regions of text in an EditBuffer.

The ExtmarksController wraps an EditBuffer and EditorView, intercepting
text-mutation and cursor-movement methods so that extmark positions are
automatically adjusted as text is inserted or deleted.  It also provides
undo/redo history for extmark state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .structs import display_width as _string_width

# ---------------------------------------------------------------------------
# Protocols for the EditBuffer / EditorView objects we wrap.
# Using protocols allows the controller to work with both real native objects
# and lightweight test stubs.
# ---------------------------------------------------------------------------


class CursorPosition(Protocol):
    @property
    def row(self) -> int: ...

    @property
    def col(self) -> int: ...

    @property
    def offset(self) -> int: ...


class SelectionRange(Protocol):
    @property
    def start(self) -> int: ...

    @property
    def end(self) -> int: ...


class HighlightSpec(Protocol):
    start: int
    end: int
    style_id: int
    priority: int
    hl_ref: int


class EditBufferLike(Protocol):
    """Minimal interface an EditBuffer must satisfy."""

    def move_cursor_left(self) -> None: ...
    def move_cursor_right(self) -> None: ...
    def set_cursor_by_offset(self, offset: int) -> None: ...
    def delete_char_backward(self) -> None: ...
    def delete_char(self) -> None: ...
    def insert_text(self, text: str) -> None: ...
    def insert_char(self, char: str) -> None: ...
    def delete_range(
        self, start_line: int, start_col: int, end_line: int, end_col: int
    ) -> None: ...
    def set_text(self, text: str) -> None: ...
    def replace_text(self, text: str) -> None: ...
    def clear(self) -> None: ...
    def new_line(self) -> None: ...
    def delete_line(self) -> None: ...
    def undo(self) -> str | None: ...
    def redo(self) -> str | None: ...
    def get_text(self) -> str: ...
    def offset_to_position(self, offset: int) -> dict[str, int] | None: ...
    def position_to_offset(self, row: int, col: int) -> int: ...
    def clear_all_highlights(self) -> None: ...
    def add_highlight_by_char_range(self, spec: dict[str, Any]) -> None: ...


class EditorViewLike(Protocol):
    """Minimal interface an EditorView must satisfy."""

    def get_visual_cursor(self) -> Any: ...
    def has_selection(self) -> bool: ...
    def get_selection(self) -> Any | None: ...
    def move_up_visual(self) -> None: ...
    def move_down_visual(self) -> None: ...
    def delete_selected_text(self) -> None: ...
    def set_cursor_by_offset(self, offset: int) -> None: ...


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Extmark:
    id: int
    start: int  # Display-width offset (including newlines)
    end: int  # Display-width offset (including newlines)
    virtual: bool = False
    style_id: int | None = None
    priority: int | None = None
    data: Any = None
    type_id: int = 0


@dataclass
class ExtmarkOptions:
    start: int
    end: int
    virtual: bool = False
    style_id: int | None = None
    priority: int | None = None
    data: Any = None
    type_id: int | None = None
    metadata: Any = field(default=None, repr=False)

    # Sentinel to distinguish "not provided" from None
    _metadata_set: bool = field(default=False, repr=False, init=False)

    def __post_init__(self) -> None:
        # We track whether metadata was explicitly passed
        pass


# ---------------------------------------------------------------------------
# ExtmarksSnapshot & ExtmarksHistory
# ---------------------------------------------------------------------------


@dataclass
class ExtmarksSnapshot:
    extmarks: dict[int, Extmark]
    next_id: int


class ExtmarksHistory:
    def __init__(self) -> None:
        self._undo_stack: list[ExtmarksSnapshot] = []
        self._redo_stack: list[ExtmarksSnapshot] = []

    def save_snapshot(self, extmarks: dict[int, Extmark], next_id: int) -> None:
        snapshot = ExtmarksSnapshot(
            extmarks={eid: _clone_extmark(em) for eid, em in extmarks.items()},
            next_id=next_id,
        )
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()

    def undo(self) -> ExtmarksSnapshot | None:
        if not self._undo_stack:
            return None
        return self._undo_stack.pop()

    def redo(self) -> ExtmarksSnapshot | None:
        if not self._redo_stack:
            return None
        return self._redo_stack.pop()

    def push_redo(self, snapshot: ExtmarksSnapshot) -> None:
        self._redo_stack.append(snapshot)

    def push_undo(self, snapshot: ExtmarksSnapshot) -> None:
        self._undo_stack.append(snapshot)

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0


def _clone_extmark(em: Extmark) -> Extmark:
    return Extmark(
        id=em.id,
        start=em.start,
        end=em.end,
        virtual=em.virtual,
        style_id=em.style_id,
        priority=em.priority,
        data=em.data,
        type_id=em.type_id,
    )


# ---------------------------------------------------------------------------
# Sentinel for "metadata not provided"
# ---------------------------------------------------------------------------


class _SentinelType:
    """A unique sentinel object to distinguish 'not passed' from None."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<SENTINEL>"

    def __bool__(self) -> bool:
        return False


_SENTINEL = _SentinelType()


# ---------------------------------------------------------------------------
# ExtmarksController
# ---------------------------------------------------------------------------


class ExtmarksController:
    """Controller that tracks extmarks (marked text regions) on an edit buffer.

    It monkey-patches cursor movement, insertion, and deletion methods on the
    provided ``edit_buffer`` and ``editor_view`` so that extmark positions are
    automatically kept in sync with the text content.
    """

    def __init__(self, edit_buffer: Any, editor_view: Any) -> None:
        self._edit_buffer = edit_buffer
        self._editor_view = editor_view

        self._extmarks: dict[int, Extmark] = {}
        self._extmarks_by_type_id: dict[int, set[int]] = {}
        self._metadata: dict[int, Any] = {}
        self._next_id: int = 1
        self._destroyed: bool = False
        self._history = ExtmarksHistory()

        self._type_name_to_id: dict[str, int] = {}
        self._type_id_to_name: dict[int, str] = {}
        self._next_type_id: int = 1

        # -- Save originals --------------------------------------------------
        self._orig_move_cursor_left = edit_buffer.move_cursor_left
        self._orig_move_cursor_right = edit_buffer.move_cursor_right
        self._orig_set_cursor_by_offset = edit_buffer.set_cursor_by_offset
        self._orig_move_up_visual = editor_view.move_up_visual
        self._orig_move_down_visual = editor_view.move_down_visual
        self._orig_delete_char_backward = edit_buffer.delete_char_backward
        self._orig_delete_char = edit_buffer.delete_char
        self._orig_insert_text = edit_buffer.insert_text
        self._orig_insert_char = edit_buffer.insert_char
        self._orig_delete_range = edit_buffer.delete_range
        self._orig_set_text = edit_buffer.set_text
        self._orig_replace_text = edit_buffer.replace_text
        self._orig_clear = edit_buffer.clear
        self._orig_new_line = edit_buffer.new_line
        self._orig_delete_line = edit_buffer.delete_line
        self._orig_delete_selected_text = editor_view.delete_selected_text
        self._orig_undo = edit_buffer.undo
        self._orig_redo = edit_buffer.redo

        # -- Patch methods ----------------------------------------------------
        self._wrap_cursor_movement()
        self._wrap_deletion()
        self._wrap_insertion()
        self._wrap_editor_view_delete_selected_text()
        self._wrap_undo_redo()

    # -----------------------------------------------------------------------
    # Cursor movement wrappers
    # -----------------------------------------------------------------------

    def _wrap_cursor_movement(self) -> None:
        controller = self
        eb = self._edit_buffer
        ev = self._editor_view

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

            _current_offset = ev.get_visual_cursor().offset  # noqa: F841
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

    # -----------------------------------------------------------------------
    # Deletion wrappers
    # -----------------------------------------------------------------------

    def _wrap_deletion(self) -> None:
        controller = self
        eb = self._edit_buffer
        ev = self._editor_view

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
                start_cursor = controller._offset_to_position(virtual_em.start)
                end_cursor = controller._offset_to_position(virtual_em.end)
                delete_offset = virtual_em.start
                delete_length = virtual_em.end - virtual_em.start

                controller._delete_extmark_by_id(virtual_em.id)

                controller._orig_delete_range(
                    start_cursor["row"],
                    start_cursor["col"],
                    end_cursor["row"],
                    end_cursor["col"],
                )
                controller.adjust_extmarks_after_deletion(delete_offset, delete_length)
                controller._update_highlights()
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
                start_cursor = controller._offset_to_position(virtual_em.start)
                end_cursor = controller._offset_to_position(virtual_em.end)
                delete_offset = virtual_em.start
                delete_length = virtual_em.end - virtual_em.start

                controller._delete_extmark_by_id(virtual_em.id)

                controller._orig_delete_range(
                    start_cursor["row"],
                    start_cursor["col"],
                    end_cursor["row"],
                    end_cursor["col"],
                )
                controller.adjust_extmarks_after_deletion(delete_offset, delete_length)
                controller._update_highlights()
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

    # -----------------------------------------------------------------------
    # Insertion wrappers
    # -----------------------------------------------------------------------

    def _wrap_insertion(self) -> None:
        controller = self
        eb = self._edit_buffer
        ev = self._editor_view
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

    # -----------------------------------------------------------------------
    # Editor view delete-selected-text wrapper
    # -----------------------------------------------------------------------

    def _wrap_editor_view_delete_selected_text(self) -> None:
        controller = self
        ev = self._editor_view

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

    # -----------------------------------------------------------------------
    # Undo / Redo wrappers
    # -----------------------------------------------------------------------

    def _wrap_undo_redo(self) -> None:
        controller = self
        eb = self._edit_buffer

        def undo() -> str | None:
            if controller._destroyed:
                return controller._orig_undo()

            if not controller._history.can_undo():
                return controller._orig_undo()

            current_snapshot = ExtmarksSnapshot(
                extmarks={eid: _clone_extmark(em) for eid, em in controller._extmarks.items()},
                next_id=controller._next_id,
            )
            controller._history.push_redo(current_snapshot)

            snapshot = controller._history.undo()
            assert snapshot is not None
            controller._restore_snapshot(snapshot)

            return controller._orig_undo()

        def redo() -> str | None:
            if controller._destroyed:
                return controller._orig_redo()

            if not controller._history.can_redo():
                return controller._orig_redo()

            current_snapshot = ExtmarksSnapshot(
                extmarks={eid: _clone_extmark(em) for eid, em in controller._extmarks.items()},
                next_id=controller._next_id,
            )
            controller._history.push_undo(current_snapshot)

            snapshot = controller._history.redo()
            assert snapshot is not None
            controller._restore_snapshot(snapshot)

            return controller._orig_redo()

        eb.undo = undo
        eb.redo = redo

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _delete_extmark_by_id(self, eid: int) -> None:
        em = self._extmarks.get(eid)
        if em is not None:
            del self._extmarks[eid]
            type_set = self._extmarks_by_type_id.get(em.type_id)
            if type_set is not None:
                type_set.discard(eid)
            self._metadata.pop(eid, None)

    def _find_virtual_extmark_containing(self, offset: int) -> Extmark | None:
        for em in self._extmarks.values():
            if em.virtual and offset >= em.start and offset < em.end:
                return em
        return None

    def _adjust_extmarks_after_insertion(self, insert_offset: int, length: int) -> None:
        for em in self._extmarks.values():
            if em.start >= insert_offset:
                em.start += length
                em.end += length
            elif em.end > insert_offset:
                em.end += length
        self._update_highlights()

    def adjust_extmarks_after_deletion(self, delete_offset: int, length: int) -> None:
        """Adjust extmark positions after a deletion.  Public for use in tests."""
        to_delete: list[int] = []

        for em in self._extmarks.values():
            if em.end <= delete_offset:
                continue

            if em.start >= delete_offset + length:
                em.start -= length
                em.end -= length
            elif em.start >= delete_offset and em.end <= delete_offset + length:
                to_delete.append(em.id)
            elif em.start < delete_offset and em.end > delete_offset + length:
                em.end -= length
            elif em.start < delete_offset and em.end > delete_offset:
                em.end -= min(em.end, delete_offset + length) - delete_offset
            elif em.start < delete_offset + length and em.end > delete_offset + length:
                em.start = delete_offset
                em.end -= length

        for eid in to_delete:
            self._delete_extmark_by_id(eid)

        self._update_highlights()

    def _offset_to_position(self, offset: int) -> dict[str, int]:
        result = self._edit_buffer.offset_to_position(offset)
        if result is None:
            return {"row": 0, "col": 0}
        return result

    def _position_to_offset(self, row: int, col: int) -> int:
        return self._edit_buffer.position_to_offset(row, col)

    def _update_highlights(self) -> None:
        self._edit_buffer.clear_all_highlights()

        for em in self._extmarks.values():
            if em.style_id is not None:
                start_no_nl = self._offset_excluding_newlines(em.start)
                end_no_nl = self._offset_excluding_newlines(em.end)

                self._edit_buffer.add_highlight_by_char_range(
                    {
                        "start": start_no_nl,
                        "end": end_no_nl,
                        "style_id": em.style_id,
                        "priority": em.priority if em.priority is not None else 0,
                        "hl_ref": em.id,
                    }
                )

    def _offset_excluding_newlines(self, offset: int) -> int:
        """Convert a display-width offset that includes newlines to one excluding them."""
        text = self._edit_buffer.get_text()
        display_width_so_far = 0
        newline_count = 0

        i = 0
        while i < len(text) and display_width_so_far < offset:
            if text[i] == "\n":
                display_width_so_far += 1
                newline_count += 1
                i += 1
            else:
                # Find the next newline or end of string
                j = i
                while j < len(text) and text[j] != "\n":
                    j += 1
                chunk = text[i:j]
                chunk_width = _string_width(chunk)

                if display_width_so_far + chunk_width < offset:
                    display_width_so_far += chunk_width
                    i = j
                else:
                    # Walk character by character
                    for k in range(i, j):
                        if display_width_so_far >= offset:
                            break
                        char_width = _string_width(text[k])
                        display_width_so_far += char_width
                    break

        return offset - newline_count

    def _save_snapshot(self) -> None:
        self._history.save_snapshot(self._extmarks, self._next_id)

    def _restore_snapshot(self, snapshot: ExtmarksSnapshot) -> None:
        self._extmarks = {eid: _clone_extmark(em) for eid, em in snapshot.extmarks.items()}
        self._next_id = snapshot.next_id
        self._update_highlights()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def create(
        self,
        *,
        start: int,
        end: int,
        virtual: bool = False,
        style_id: int | None = None,
        priority: int | None = None,
        data: Any = None,
        type_id: int | None = None,
        metadata: Any = _SENTINEL,
    ) -> int:
        """Create a new extmark.  Returns the unique extmark id."""
        if self._destroyed:
            raise RuntimeError("ExtmarksController is destroyed")

        eid = self._next_id
        self._next_id += 1
        tid = type_id if type_id is not None else 0

        em = Extmark(
            id=eid,
            start=start,
            end=end,
            virtual=virtual,
            style_id=style_id,
            priority=priority,
            data=data,
            type_id=tid,
        )
        self._extmarks[eid] = em

        if tid not in self._extmarks_by_type_id:
            self._extmarks_by_type_id[tid] = set()
        self._extmarks_by_type_id[tid].add(eid)

        if metadata is not _SENTINEL and metadata is not None:
            self._metadata[eid] = metadata
        elif metadata is None:
            # Explicitly passed None -- store it
            self._metadata[eid] = None

        self._update_highlights()
        return eid

    def delete(self, eid: int) -> bool:
        """Delete an extmark by id.  Returns True if it existed."""
        if self._destroyed:
            raise RuntimeError("ExtmarksController is destroyed")

        em = self._extmarks.get(eid)
        if em is None:
            return False

        self._delete_extmark_by_id(eid)
        self._update_highlights()
        return True

    def get(self, eid: int) -> Extmark | None:
        """Get an extmark by id."""
        if self._destroyed:
            return None
        return self._extmarks.get(eid)

    def get_all(self) -> list[Extmark]:
        """Get all extmarks."""
        if self._destroyed:
            return []
        return list(self._extmarks.values())

    def get_virtual(self) -> list[Extmark]:
        """Get all virtual extmarks."""
        if self._destroyed:
            return []
        return [em for em in self._extmarks.values() if em.virtual]

    def get_at_offset(self, offset: int) -> list[Extmark]:
        """Get all extmarks containing the given offset."""
        if self._destroyed:
            return []
        return [em for em in self._extmarks.values() if offset >= em.start and offset < em.end]

    def get_all_for_type_id(self, type_id: int) -> list[Extmark]:
        """Get all extmarks with the given type_id."""
        if self._destroyed:
            return []
        ids = self._extmarks_by_type_id.get(type_id)
        if ids is None:
            return []
        return [self._extmarks[eid] for eid in ids if eid in self._extmarks]

    def clear(self) -> None:
        """Remove all extmarks and metadata."""
        if self._destroyed:
            return
        self._extmarks.clear()
        self._extmarks_by_type_id.clear()
        self._metadata.clear()
        self._update_highlights()

    # -----------------------------------------------------------------------
    # Type registry
    # -----------------------------------------------------------------------

    def register_type(self, type_name: str) -> int:
        """Register a type name and return a unique type_id.

        If the name is already registered the existing id is returned.
        """
        if self._destroyed:
            raise RuntimeError("ExtmarksController is destroyed")

        existing = self._type_name_to_id.get(type_name)
        if existing is not None:
            return existing

        tid = self._next_type_id
        self._next_type_id += 1
        self._type_name_to_id[type_name] = tid
        self._type_id_to_name[tid] = type_name
        return tid

    def get_type_id(self, type_name: str) -> int | None:
        if self._destroyed:
            return None
        return self._type_name_to_id.get(type_name)

    def get_type_name(self, type_id: int) -> str | None:
        if self._destroyed:
            return None
        return self._type_id_to_name.get(type_id)

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------

    def get_metadata_for(self, extmark_id: int) -> Any:
        """Return the metadata stored for *extmark_id*, or ``None``."""
        if self._destroyed:
            return None
        return self._metadata.get(extmark_id)

    # -----------------------------------------------------------------------
    # Destroy
    # -----------------------------------------------------------------------

    def destroy(self) -> None:
        if self._destroyed:
            return

        eb = self._edit_buffer
        ev = self._editor_view

        eb.move_cursor_left = self._orig_move_cursor_left
        eb.move_cursor_right = self._orig_move_cursor_right
        eb.set_cursor_by_offset = self._orig_set_cursor_by_offset
        ev.move_up_visual = self._orig_move_up_visual
        ev.move_down_visual = self._orig_move_down_visual
        eb.delete_char_backward = self._orig_delete_char_backward
        eb.delete_char = self._orig_delete_char
        eb.insert_text = self._orig_insert_text
        eb.insert_char = self._orig_insert_char
        eb.delete_range = self._orig_delete_range
        eb.set_text = self._orig_set_text
        eb.replace_text = self._orig_replace_text
        eb.clear = self._orig_clear
        eb.new_line = self._orig_new_line
        eb.delete_line = self._orig_delete_line
        ev.delete_selected_text = self._orig_delete_selected_text
        eb.undo = self._orig_undo
        eb.redo = self._orig_redo

        self._extmarks.clear()
        self._extmarks_by_type_id.clear()
        self._metadata.clear()
        self._type_name_to_id.clear()
        self._type_id_to_name.clear()
        self._history.clear()
        self._destroyed = True


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_extmarks_controller(edit_buffer: Any, editor_view: Any) -> ExtmarksController:
    return ExtmarksController(edit_buffer, editor_view)


__all__ = [
    "Extmark",
    "ExtmarkOptions",
    "ExtmarksController",
    "ExtmarksHistory",
    "ExtmarksSnapshot",
    "create_extmarks_controller",
]
