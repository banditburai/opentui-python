"""ExtmarksController for tracking marked regions of text in an EditBuffer.

The ExtmarksController wraps an EditBuffer and EditorView, intercepting
text-mutation and cursor-movement methods so that extmark positions are
automatically adjusted as text is inserted or deleted.  It also provides
undo/redo history for extmark state.
"""

from dataclasses import dataclass
from typing import Any

from ..structs import display_width as _string_width
from .extmarks_wrappers import (
    install_cursor_wrappers,
    install_delete_selected_text_wrapper,
    install_deletion_wrappers,
    install_insertion_wrappers,
    install_undo_redo_wrappers,
)


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
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)


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


_SENTINEL = object()


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

        install_cursor_wrappers(self, edit_buffer, editor_view)
        install_deletion_wrappers(self, edit_buffer, editor_view)
        install_insertion_wrappers(self, edit_buffer, editor_view)
        install_delete_selected_text_wrapper(self, editor_view)
        install_undo_redo_wrappers(self, edit_buffer)

    def _undo_or_redo(self, *, direction: str) -> str | None:
        if direction == "undo":
            orig_fn = self._orig_undo
            can_fn = self._history.can_undo
            pop_fn = self._history.undo
            push_fn = self._history.push_redo
        else:
            orig_fn = self._orig_redo
            can_fn = self._history.can_redo
            pop_fn = self._history.redo
            push_fn = self._history.push_undo

        if self._destroyed or not can_fn():
            return orig_fn()

        current_snapshot = ExtmarksSnapshot(
            extmarks={eid: _clone_extmark(em) for eid, em in self._extmarks.items()},
            next_id=self._next_id,
        )
        push_fn(current_snapshot)

        snapshot = pop_fn()
        assert snapshot is not None
        self._restore_snapshot(snapshot)

        return orig_fn()

    def _delete_virtual_extmark_range(self, virtual_em: Extmark) -> None:
        start_cursor = self._offset_to_position(virtual_em.start)
        end_cursor = self._offset_to_position(virtual_em.end)
        delete_offset = virtual_em.start
        delete_length = virtual_em.end - virtual_em.start

        self._delete_extmark_by_id(virtual_em.id)

        self._orig_delete_range(
            start_cursor["row"],
            start_cursor["col"],
            end_cursor["row"],
            end_cursor["col"],
        )
        self.adjust_extmarks_after_deletion(delete_offset, delete_length)
        self._update_highlights()

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
            if em.virtual and em.start <= offset < em.end:
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
        to_delete: list[int] = []
        end = delete_offset + length

        for em in self._extmarks.values():
            if em.end <= delete_offset:
                continue

            if em.start >= end:
                # Entirely after deletion — shift left
                em.start -= length
                em.end -= length
            elif em.start >= delete_offset and em.end <= end:
                # Entirely within deletion — remove
                to_delete.append(em.id)
            elif em.start < delete_offset and em.end > end:
                # Deletion inside extmark — shrink
                em.end -= length
            elif em.start < delete_offset and em.end > delete_offset:
                # Deletion overlaps extmark's end — truncate
                em.end -= min(em.end, end) - delete_offset
            elif em.start < end and em.end > end:
                # Deletion overlaps extmark's start — collapse start
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
        """Returns the unique extmark id."""
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
        if self._destroyed:
            raise RuntimeError("ExtmarksController is destroyed")

        em = self._extmarks.get(eid)
        if em is None:
            return False

        self._delete_extmark_by_id(eid)
        self._update_highlights()
        return True

    def get(self, eid: int) -> Extmark | None:
        if self._destroyed:
            return None
        return self._extmarks.get(eid)

    def get_all(self) -> list[Extmark]:
        if self._destroyed:
            return []
        return list(self._extmarks.values())

    def get_virtual(self) -> list[Extmark]:
        if self._destroyed:
            return []
        return [em for em in self._extmarks.values() if em.virtual]

    def get_at_offset(self, offset: int) -> list[Extmark]:
        if self._destroyed:
            return []
        return [em for em in self._extmarks.values() if em.start <= offset < em.end]

    def get_all_for_type_id(self, type_id: int) -> list[Extmark]:
        if self._destroyed:
            return []
        ids = self._extmarks_by_type_id.get(type_id)
        if ids is None:
            return []
        return [self._extmarks[eid] for eid in ids if eid in self._extmarks]

    def clear(self) -> None:
        if self._destroyed:
            return
        self._extmarks.clear()
        self._extmarks_by_type_id.clear()
        self._metadata.clear()
        self._update_highlights()

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

    def get_metadata_for(self, extmark_id: int) -> Any:
        """Return the metadata stored for *extmark_id*, or ``None``."""
        if self._destroyed:
            return None
        return self._metadata.get(extmark_id)

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


__all__ = [
    "Extmark",
    "ExtmarksController",
    "ExtmarksHistory",
    "ExtmarksSnapshot",
]
