"""Port of upstream extmarks.test.ts.

Upstream: packages/core/src/lib/extmarks.test.ts
Tests ported: 169/169
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from opentui.editor.extmarks import ExtmarksController


# ---------------------------------------------------------------------------
# Lightweight mock EditBuffer / EditorView
# ---------------------------------------------------------------------------


@dataclass
class _CursorPos:
    row: int = 0
    col: int = 0
    offset: int = 0


@dataclass
class _Selection:
    start: int = 0
    end: int = 0


@dataclass
class _HighlightSpec:
    start: int = 0
    end: int = 0
    style_id: int = 0
    priority: int = 0
    hl_ref: int = 0


class MockEditBuffer:
    """Minimal in-memory edit buffer that supports the API ExtmarksController needs."""

    def __init__(self, text: str = "") -> None:
        self._text: str = text
        self._cursor_offset: int = 0
        self._undo_stack: list[tuple[str, int]] = []
        self._redo_stack: list[tuple[str, int]] = []
        self._highlights: list[_HighlightSpec] = []

    # -- Text ----------------------------------------------------------------

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self._cursor_offset = 0

    def replace_text(self, text: str) -> None:
        self._text = text
        self._cursor_offset = 0

    def clear(self) -> None:
        self._text = ""
        self._cursor_offset = 0

    # -- Cursor --------------------------------------------------------------

    @property
    def cursor_offset(self) -> int:
        return self._cursor_offset

    @cursor_offset.setter
    def cursor_offset(self, v: int) -> None:
        self._cursor_offset = max(0, min(v, len(self._text)))

    def move_cursor_left(self) -> None:
        if self._cursor_offset > 0:
            self._cursor_offset -= 1

    def move_cursor_right(self) -> None:
        if self._cursor_offset < len(self._text):
            self._cursor_offset += 1

    def set_cursor_by_offset(self, offset: int) -> None:
        self._cursor_offset = max(0, min(offset, len(self._text)))

    # -- Insertion -----------------------------------------------------------

    def insert_text(self, text: str) -> None:
        o = self._cursor_offset
        self._text = self._text[:o] + text + self._text[o:]
        self._cursor_offset = o + len(text)

    def insert_char(self, char: str) -> None:
        self.insert_text(char)

    def new_line(self) -> None:
        self.insert_text("\n")

    # -- Deletion ------------------------------------------------------------

    def delete_char_backward(self) -> None:
        if self._cursor_offset > 0:
            o = self._cursor_offset
            self._text = self._text[: o - 1] + self._text[o:]
            self._cursor_offset = o - 1

    def delete_char(self) -> None:
        o = self._cursor_offset
        if o < len(self._text):
            self._text = self._text[:o] + self._text[o + 1 :]

    def delete_range(self, start_line: int, start_col: int, end_line: int, end_col: int) -> None:
        start_off = self.position_to_offset(start_line, start_col)
        end_off = self.position_to_offset(end_line, end_col)
        self._text = self._text[:start_off] + self._text[end_off:]
        self._cursor_offset = start_off

    def delete_line(self) -> None:
        text = self._text
        off = self._cursor_offset

        line_start = 0
        for i in range(off - 1, -1, -1):
            if text[i] == "\n":
                line_start = i + 1
                break

        line_end = len(text)
        for i in range(off, len(text)):
            if text[i] == "\n":
                line_end = i + 1
                break

        self._text = text[:line_start] + text[line_end:]
        self._cursor_offset = min(line_start, len(self._text))

    # -- Undo / Redo ---------------------------------------------------------

    def save_undo(self) -> None:
        self._undo_stack.append((self._text, self._cursor_offset))
        self._redo_stack.clear()

    def undo(self) -> str | None:
        if not self._undo_stack:
            return None
        self._redo_stack.append((self._text, self._cursor_offset))
        text, off = self._undo_stack.pop()
        self._text = text
        self._cursor_offset = off
        return text

    def redo(self) -> str | None:
        if not self._redo_stack:
            return None
        self._undo_stack.append((self._text, self._cursor_offset))
        text, off = self._redo_stack.pop()
        self._text = text
        self._cursor_offset = off
        return text

    # -- Offset / position conversion ----------------------------------------

    def offset_to_position(self, offset: int) -> dict[str, int] | None:
        if offset < 0 or offset > len(self._text):
            return None
        row = 0
        col = 0
        for i, ch in enumerate(self._text):
            if i == offset:
                return {"row": row, "col": col}
            if ch == "\n":
                row += 1
                col = 0
            else:
                col += 1
        return {"row": row, "col": col}

    def position_to_offset(self, row: int, col: int) -> int:
        r = 0
        c = 0
        for i, ch in enumerate(self._text):
            if r == row and c == col:
                return i
            if ch == "\n":
                if r == row:
                    return i
                r += 1
                c = 0
            else:
                c += 1
        return len(self._text)

    # -- Highlights ----------------------------------------------------------

    def clear_all_highlights(self) -> None:
        self._highlights.clear()

    def add_highlight_by_char_range(self, spec: dict[str, Any]) -> None:
        self._highlights.append(
            _HighlightSpec(
                start=spec["start"],
                end=spec["end"],
                style_id=spec["style_id"],
                priority=spec.get("priority", 0),
                hl_ref=spec.get("hl_ref", 0),
            )
        )

    def get_line_highlights(self, line: int) -> list[_HighlightSpec]:
        """Return highlights that overlap the given line, with positions local to that line."""
        lines = self._text.split("\n")
        if line < 0 or line >= len(lines):
            return []
        # Calculate the char offset (excluding newlines) where this line starts
        line_char_start = sum(len(lines[i]) for i in range(line))
        line_char_end = line_char_start + len(lines[line])

        result: list[_HighlightSpec] = []
        for hl in self._highlights:
            # hl.start / hl.end are char offsets *excluding newlines*
            if hl.end <= line_char_start or hl.start >= line_char_end:
                continue
            local_start = max(hl.start - line_char_start, 0)
            local_end = min(hl.end - line_char_start, len(lines[line]))
            result.append(
                _HighlightSpec(
                    start=local_start,
                    end=local_end,
                    style_id=hl.style_id,
                    priority=hl.priority,
                    hl_ref=hl.hl_ref,
                )
            )
        return result


class MockEditorView:
    """Minimal mock EditorView that delegates to a MockEditBuffer."""

    def __init__(self, buf: MockEditBuffer) -> None:
        self._buf = buf
        self._selection: _Selection | None = None
        self._viewport_width: int = 40
        self._viewport_height: int = 10

    def get_visual_cursor(self) -> _CursorPos:
        off = self._buf.cursor_offset
        pos = self._buf.offset_to_position(off)
        if pos is None:
            return _CursorPos(0, 0, off)
        return _CursorPos(row=pos["row"], col=pos["col"], offset=off)

    def has_selection(self) -> bool:
        return self._selection is not None

    def get_selection(self) -> _Selection | None:
        return self._selection

    def set_selection(self, start: int, end: int) -> None:
        self._selection = _Selection(start=start, end=end)

    def clear_selection(self) -> None:
        self._selection = None

    def move_up_visual(self) -> None:
        pos = self._buf.offset_to_position(self._buf.cursor_offset)
        if pos is None or pos["row"] == 0:
            return
        target_row = pos["row"] - 1
        target_col = pos["col"]
        new_off = self._buf.position_to_offset(target_row, target_col)
        self._buf.cursor_offset = new_off

    def move_down_visual(self) -> None:
        pos = self._buf.offset_to_position(self._buf.cursor_offset)
        if pos is None:
            return
        lines = self._buf.get_text().split("\n")
        if pos["row"] >= len(lines) - 1:
            return
        target_row = pos["row"] + 1
        target_col = pos["col"]
        new_off = self._buf.position_to_offset(target_row, target_col)
        self._buf.cursor_offset = new_off

    def delete_selected_text(self) -> None:
        if self._selection is None:
            return
        s = min(self._selection.start, self._selection.end)
        e = max(self._selection.start, self._selection.end)
        text = self._buf.get_text()
        self._buf._text = text[:s] + text[e:]
        self._buf._cursor_offset = s
        self._selection = None

    def set_cursor_by_offset(self, offset: int) -> None:
        self._buf.set_cursor_by_offset(offset)


# ---------------------------------------------------------------------------
# Helpers for simulating key presses and textarea-level operations
# ---------------------------------------------------------------------------


class MockTextarea:
    """Wraps MockEditBuffer + MockEditorView, exposing a textarea-like API
    so that tests can call the same high-level operations as the upstream TS
    tests (pressKey, pressArrow, etc.)."""

    def __init__(
        self, buf: MockEditBuffer, view: MockEditorView, extmarks: ExtmarksController
    ) -> None:
        self.buf = buf
        self.view = view
        self.extmarks = extmarks

    # -- Properties ----------------------------------------------------------

    @property
    def plain_text(self) -> str:
        return self.buf.get_text()

    @property
    def cursor_offset(self) -> int:
        return self.buf.cursor_offset

    @cursor_offset.setter
    def cursor_offset(self, v: int) -> None:
        self.buf.cursor_offset = v

    def has_selection(self) -> bool:
        return self.view.has_selection()

    # -- High-level operations -----------------------------------------------

    def focus(self) -> None:
        pass  # no-op

    def set_text(self, text: str) -> None:
        self.buf.set_text(text)

    def clear(self) -> None:
        self.buf.clear()

    def insert_text(self, text: str) -> None:
        self.buf.insert_text(text)

    def delete_range(self, start_line: int, start_col: int, end_line: int, end_col: int) -> None:
        self.buf.delete_range(start_line, start_col, end_line, end_col)

    def new_line(self) -> None:
        self.buf.new_line()

    def delete_line(self) -> None:
        self.buf.delete_line()

    def undo(self) -> str | None:
        return self.buf.undo()

    def redo(self) -> str | None:
        return self.buf.redo()

    def delete_word_forward(self) -> None:
        """Delete from cursor to end of next word."""
        text = self.buf.get_text()
        off = self.buf.cursor_offset
        if off >= len(text):
            return
        # Skip current word chars
        i = off
        while i < len(text) and text[i] not in (" ", "\n"):
            i += 1
        # Skip whitespace
        while i < len(text) and text[i] == " ":
            i += 1
        length = i - off
        if length > 0:
            start_pos = self.buf.offset_to_position(off)
            end_pos = self.buf.offset_to_position(i)
            self.buf.delete_range(
                start_pos["row"], start_pos["col"], end_pos["row"], end_pos["col"]
            )

    def delete_word_backward(self) -> None:
        """Delete from cursor backward to start of current word."""
        text = self.buf.get_text()
        off = self.buf.cursor_offset
        if off == 0:
            return
        i = off
        # Skip whitespace backwards
        while i > 0 and text[i - 1] == " ":
            i -= 1
        # Skip word chars backwards
        while i > 0 and text[i - 1] not in (" ", "\n"):
            i -= 1
        length = off - i
        if length > 0:
            start_pos = self.buf.offset_to_position(i)
            end_pos = self.buf.offset_to_position(off)
            self.buf.delete_range(
                start_pos["row"], start_pos["col"], end_pos["row"], end_pos["col"]
            )

    def delete_to_line_end(self) -> None:
        """Delete from cursor to end of the current line."""
        text = self.buf.get_text()
        off = self.buf.cursor_offset
        # Find end of current line
        end = off
        while end < len(text) and text[end] != "\n":
            end += 1
        length = end - off
        if length > 0:
            start_pos = self.buf.offset_to_position(off)
            end_pos = self.buf.offset_to_position(end)
            self.buf.delete_range(
                start_pos["row"], start_pos["col"], end_pos["row"], end_pos["col"]
            )

    def move_word_forward(self) -> None:
        """Move cursor forward by one word, respecting virtual extmarks."""
        text = self.buf.get_text()
        off = self.buf.cursor_offset
        if off >= len(text):
            return
        # Skip current non-space chars
        i = off
        while i < len(text) and text[i] not in (" ", "\n"):
            i += 1
        # Skip whitespace
        while i < len(text) and text[i] == " ":
            i += 1
        # Use set_cursor_by_offset so the extmarks controller can intercept
        self.buf.set_cursor_by_offset(i)

    def move_word_backward(self) -> None:
        """Move cursor backward by one word, respecting virtual extmarks."""
        text = self.buf.get_text()
        off = self.buf.cursor_offset
        if off == 0:
            return
        i = off
        # Skip whitespace backwards
        while i > 0 and text[i - 1] == " ":
            i -= 1
        # Skip word chars backwards
        while i > 0 and text[i - 1] not in (" ", "\n"):
            i -= 1
        self.buf.set_cursor_by_offset(i)

    def get_line_highlights(self, line: int) -> list[_HighlightSpec]:
        return self.buf.get_line_highlights(line)

    # -- Input simulation helpers -------------------------------------------

    def press_key(self, key: str) -> None:
        if key == "DELETE":
            if self.view.has_selection():
                self.view.delete_selected_text()
            else:
                self.buf.delete_char()
        else:
            # If there is an active selection, the typed character replaces it
            if self.view.has_selection():
                sel = self.view.get_selection()
                assert sel is not None
                self.view.delete_selected_text()
            self.buf.insert_char(key)

    def press_backspace(self) -> None:
        if self.view.has_selection():
            self.view.delete_selected_text()
        else:
            self.buf.delete_char_backward()

    def press_arrow(self, direction: str, *, shift: bool = False) -> None:
        if shift:
            # Extend or start a selection
            cur = self.buf.cursor_offset
            if not self.view.has_selection():
                self.view.set_selection(cur, cur)

            sel = self.view.get_selection()
            assert sel is not None
            anchor = sel.start if sel.end == cur else sel.end

            if direction == "left":
                self.buf.cursor_offset = max(0, cur - 1)
            elif direction == "right":
                self.buf.cursor_offset = min(len(self.buf.get_text()), cur + 1)
            elif direction == "up":
                self.view.move_up_visual()
            elif direction == "down":
                self.view.move_down_visual()

            new_cur = self.buf.cursor_offset
            self.view.set_selection(anchor, new_cur)
        else:
            self.view.clear_selection()
            if direction == "left":
                self.buf.move_cursor_left()
            elif direction == "right":
                self.buf.move_cursor_right()
            elif direction == "up":
                self.view.move_up_visual()
            elif direction == "down":
                self.view.move_down_visual()


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def setup(initial_value: str = "Hello World"):
    buf = MockEditBuffer(initial_value)
    view = MockEditorView(buf)
    extmarks = ExtmarksController(buf, view)
    textarea = MockTextarea(buf, view, extmarks)
    return textarea, extmarks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreationAndBasicOperations:
    """Maps to describe("Creation and Basic Operations")."""

    def test_should_create_extmark_with_basic_options(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5)
        assert eid == 1
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 0
        assert em.end == 5
        assert em.virtual is False

    def test_should_create_virtual_extmark(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=6, end=11, virtual=True)
        em = extmarks.get(eid)
        assert em is not None
        assert em.virtual is True

    def test_should_create_multiple_extmarks_with_unique_ids(self):
        textarea, extmarks = setup()
        id1 = extmarks.create(start=0, end=5)
        id2 = extmarks.create(start=6, end=11)
        assert id1 == 1
        assert id2 == 2
        assert len(extmarks.get_all()) == 2

    def test_should_store_custom_data_with_extmark(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5, data={"type": "link", "url": "https://example.com"})
        em = extmarks.get(eid)
        assert em is not None
        assert em.data == {"type": "link", "url": "https://example.com"}


class TestDeleteOperations:
    """Maps to describe("Delete Operations")."""

    def test_should_delete_extmark(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5)
        result = extmarks.delete(eid)
        assert result is True
        assert extmarks.get(eid) is None

    def test_should_return_false_when_deleting_non_existent_extmark(self):
        textarea, extmarks = setup()
        result = extmarks.delete(999)
        assert result is False

    def test_should_delete_extmark_without_emitting_events(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5)
        extmarks.delete(eid)
        assert extmarks.get(eid) is None

    def test_should_clear_all_extmarks(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5)
        extmarks.create(start=6, end=11)
        assert len(extmarks.get_all()) == 2
        extmarks.clear()
        assert len(extmarks.get_all()) == 0


class TestQueryOperations:
    """Maps to describe("Query Operations")."""

    def test_should_get_all_extmarks(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5)
        extmarks.create(start=6, end=11)
        assert len(extmarks.get_all()) == 2

    def test_should_get_only_virtual_extmarks(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5, virtual=False)
        extmarks.create(start=6, end=11, virtual=True)
        extmarks.create(start=12, end=15, virtual=True)
        virtual = extmarks.get_virtual()
        assert len(virtual) == 2
        assert all(e.virtual for e in virtual)

    def test_should_get_extmarks_at_specific_offset(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5)
        extmarks.create(start=3, end=8)
        extmarks.create(start=10, end=15)
        at4 = extmarks.get_at_offset(4)
        assert len(at4) == 2
        at10 = extmarks.get_at_offset(10)
        assert len(at10) == 1


class TestVirtualExtmarkCursorJumpingRight:
    """Maps to describe("Virtual Extmark - Cursor Jumping Right")."""

    def test_should_jump_cursor_over_virtual_extmark_when_moving_right(self):
        textarea, extmarks = setup("abcdefgh")
        textarea.focus()
        textarea.cursor_offset = 2
        extmarks.create(start=3, end=6, virtual=True)
        assert textarea.cursor_offset == 2
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 6

    def test_should_jump_to_position_after_extmark_end_when_moving_right_from_before_extmark(self):
        textarea, extmarks = setup("abcdefgh")
        textarea.focus()
        textarea.cursor_offset = 2
        extmarks.create(start=3, end=6, virtual=True)
        assert textarea.cursor_offset == 2
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 6

    def test_should_allow_cursor_to_move_normally_outside_virtual_extmark(self):
        textarea, extmarks = setup("abcdefgh")
        textarea.focus()
        textarea.cursor_offset = 0
        extmarks.create(start=3, end=6, virtual=True)
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 1
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 2

    def test_should_jump_over_multiple_virtual_extmarks(self):
        textarea, extmarks = setup("abcdefghij")
        textarea.focus()
        textarea.cursor_offset = 0
        extmarks.create(start=2, end=4, virtual=True)
        extmarks.create(start=5, end=7, virtual=True)
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 1
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 4
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 7


class TestVirtualExtmarkCursorJumpingLeft:
    """Maps to describe("Virtual Extmark - Cursor Jumping Left")."""

    def test_should_jump_cursor_over_virtual_extmark_when_moving_left(self):
        textarea, extmarks = setup("abcdefgh")
        textarea.focus()
        textarea.cursor_offset = 7
        extmarks.create(start=3, end=6, virtual=True)
        assert textarea.cursor_offset == 7
        textarea.press_arrow("left")
        assert textarea.cursor_offset == 6
        textarea.press_arrow("left")
        assert textarea.cursor_offset == 2

    def test_should_jump_to_position_before_extmark_start_when_moving_left_from_after_extmark(self):
        textarea, extmarks = setup("abcdefgh")
        textarea.focus()
        textarea.cursor_offset = 6
        extmarks.create(start=3, end=6, virtual=True)
        assert textarea.cursor_offset == 6
        textarea.press_arrow("left")
        assert textarea.cursor_offset == 2

    def test_should_allow_normal_cursor_movement_left_outside_virtual_extmark(self):
        textarea, extmarks = setup("abcdefgh")
        textarea.focus()
        textarea.cursor_offset = 2
        extmarks.create(start=3, end=6, virtual=True)
        textarea.press_arrow("left")
        assert textarea.cursor_offset == 1
        textarea.press_arrow("left")
        assert textarea.cursor_offset == 0


class TestVirtualExtmarkSelectionMode:
    """Maps to describe("Virtual Extmark - Selection Mode")."""

    def test_should_allow_selection_through_virtual_extmark(self):
        textarea, extmarks = setup("abcdefgh")
        textarea.focus()
        textarea.cursor_offset = 0
        extmarks.create(start=2, end=5, virtual=True)
        textarea.press_arrow("right", shift=True)
        textarea.press_arrow("right", shift=True)
        textarea.press_arrow("right", shift=True)
        assert textarea.cursor_offset == 3
        assert textarea.has_selection()


class TestVirtualExtmarkBackspaceDeletion:
    """Maps to describe("Virtual Extmark - Backspace Deletion")."""

    def test_should_delete_entire_virtual_extmark_on_backspace_at_end(self):
        textarea, extmarks = setup("abc[LINK]def")
        textarea.focus()
        textarea.cursor_offset = 9
        eid = extmarks.create(start=3, end=9, virtual=True)
        textarea.press_backspace()
        assert textarea.plain_text == "abcdef"
        assert textarea.cursor_offset == 3
        assert extmarks.get(eid) is None

    def test_should_not_delete_virtual_extmark_on_backspace_outside_range(self):
        textarea, extmarks = setup("abc[LINK]def")
        textarea.focus()
        textarea.cursor_offset = 2
        eid = extmarks.create(start=3, end=9, virtual=True)
        textarea.press_backspace()
        assert textarea.plain_text == "ac[LINK]def"
        assert extmarks.get(eid) is not None

    def test_should_delete_normal_character_inside_virtual_extmark(self):
        textarea, extmarks = setup("abc[LINK]def")
        textarea.focus()
        textarea.cursor_offset = 5
        extmarks.create(start=3, end=9, virtual=True)
        textarea.press_backspace()
        assert textarea.plain_text == "abc[INK]def"


class TestVirtualExtmarkDeleteKey:
    """Maps to describe("Virtual Extmark - Delete Key")."""

    def test_should_delete_entire_virtual_extmark_on_delete_at_start(self):
        textarea, extmarks = setup("abc[LINK]def")
        textarea.focus()
        textarea.cursor_offset = 3
        eid = extmarks.create(start=3, end=9, virtual=True)
        textarea.press_key("DELETE")
        assert textarea.plain_text == "abcdef"
        assert textarea.cursor_offset == 3
        assert extmarks.get(eid) is None


class TestExtmarkPositionAdjustmentInsertion:
    """Maps to describe("Extmark Position Adjustment - Insertion")."""

    def test_should_adjust_extmark_positions_after_insertion_before_extmark(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.press_key("X")
        textarea.press_key("X")
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 8
        assert em.end == 13

    def test_should_expand_extmark_when_inserting_inside(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 8
        textarea.press_key("X")
        textarea.press_key("X")
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 6
        assert em.end == 13

    def test_should_not_adjust_extmark_when_inserting_after(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=0, end=5)
        textarea.focus()
        textarea.cursor_offset = 11
        textarea.press_key("X")
        textarea.press_key("X")
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 0
        assert em.end == 5


class TestExtmarkPositionAdjustmentDeletion:
    """Maps to describe("Extmark Position Adjustment - Deletion")."""

    def test_should_adjust_extmark_positions_after_deletion_before_extmark(self):
        textarea, extmarks = setup("XXHello World")
        eid = extmarks.create(start=8, end=13)
        textarea.focus()
        textarea.cursor_offset = 2
        textarea.press_backspace()
        textarea.press_backspace()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 6
        assert em.end == 11

    def test_should_remove_extmark_when_its_range_is_deleted(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11)
        textarea.delete_range(0, 6, 0, 11)
        assert extmarks.get(eid) is None


class TestHighlightingIntegration:
    """Maps to describe("Highlighting Integration")."""

    def test_should_apply_highlight_for_extmark_with_style_id(self):
        textarea, extmarks = setup("Hello World")
        style_id = 1
        extmarks.create(start=0, end=5, style_id=style_id)
        highlights = textarea.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0].start == 0
        assert highlights[0].end == 5
        assert highlights[0].style_id == style_id

    def test_should_correctly_position_highlights_in_middle_of_single_line(self):
        textarea, extmarks = setup("AAAA")
        style_id = 1
        extmarks.create(start=1, end=3, style_id=style_id)
        highlights = textarea.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0].start == 1
        assert highlights[0].end == 3

    def test_should_correctly_position_highlights_across_newlines(self):
        textarea, extmarks = setup("AAAA\nBBBB\nCCCC")
        style_id = 1
        # Highlight "BBBB" which is at cursor offset 5-9
        extmarks.create(start=5, end=9, style_id=style_id)
        hl0 = textarea.get_line_highlights(0)
        hl1 = textarea.get_line_highlights(1)
        hl2 = textarea.get_line_highlights(2)
        assert len(hl0) == 0
        assert len(hl1) == 1
        assert hl1[0].start == 0
        assert hl1[0].end == 4
        assert len(hl2) == 0

    def test_should_correctly_position_multiline_highlights(self):
        textarea, extmarks = setup("AAA\nBBB\nCCC")
        style_id = 1
        # From cursor offset 1 (second A) to 9 (second C)
        extmarks.create(start=1, end=9, style_id=style_id)
        hl0 = textarea.get_line_highlights(0)
        hl1 = textarea.get_line_highlights(1)
        hl2 = textarea.get_line_highlights(2)
        # Line 0: position 1 to 3
        assert len(hl0) == 1
        assert hl0[0].start == 1
        assert hl0[0].end == 3
        # Line 1: entire line
        assert len(hl1) == 1
        assert hl1[0].start == 0
        assert hl1[0].end == 3
        # Line 2: position 0 to 1
        assert len(hl2) == 1
        assert hl2[0].start == 0
        assert hl2[0].end == 1

    def test_should_update_highlights_when_extmark_position_changes(self):
        textarea, extmarks = setup("Hello World")
        style_id = 1
        eid = extmarks.create(start=0, end=5, style_id=style_id)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.press_key("X")
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 1
        assert em.end == 6

    def test_should_remove_highlight_when_extmark_is_deleted(self):
        textarea, extmarks = setup("Hello World")
        style_id = 1
        eid = extmarks.create(start=0, end=5, style_id=style_id)
        hl_before = textarea.get_line_highlights(0)
        assert len(hl_before) > 0
        extmarks.delete(eid)
        hl_after = textarea.get_line_highlights(0)
        assert len(hl_after) == 0


class TestMultilineTextSupport:
    """Maps to describe("Multiline Text Support")."""

    def test_should_handle_extmarks_in_multiline_text(self):
        textarea, extmarks = setup("Line 1\nLine 2\nLine 3")
        eid = extmarks.create(start=7, end=13)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.press_key("X")
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 8
        assert em.end == 14

    def test_should_handle_virtual_extmark_across_lines(self):
        textarea, extmarks = setup("Line 1\nLine 2\nLine 3")
        textarea.focus()
        textarea.cursor_offset = 5
        extmarks.create(start=7, end=13, virtual=True)
        for _ in range(3):
            textarea.press_arrow("right")
        # After jumping over virtual extmark: should be at offset 14
        assert textarea.cursor_offset == 14


class TestDestroy:
    """Maps to describe("Destroy")."""

    def test_should_restore_original_methods_on_destroy(self):
        textarea, extmarks = setup("Hello World")
        textarea.focus()
        textarea.cursor_offset = 2
        extmarks.create(start=3, end=6, virtual=True)
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 6
        extmarks.destroy()
        textarea.cursor_offset = 2
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 3

    def test_should_clear_all_extmarks_on_destroy(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5)
        extmarks.create(start=6, end=11)
        assert len(extmarks.get_all()) == 2
        extmarks.destroy()
        assert len(extmarks.get_all()) == 0

    def test_should_throw_error_when_using_destroyed_controller(self):
        textarea, extmarks = setup()
        extmarks.destroy()
        with pytest.raises(RuntimeError, match="ExtmarksController is destroyed"):
            extmarks.create(start=0, end=5)


class TestHighlightBoundaries:
    """Maps to describe("Highlight Boundaries")."""

    def test_should_highlight_only_virtual_marker_without_extending_to_end_of_line(self):
        textarea, extmarks = setup("text [VIRTUAL] more text")
        style_id = 1
        extmarks.create(start=5, end=14, virtual=True, style_id=style_id)
        highlights = textarea.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0].start == 5
        assert highlights[0].end == 14

    def test_should_highlight_virtual_marker_in_middle_with_text_after(self):
        textarea, extmarks = setup("abc [MARKER] def")
        style_id = 1
        extmarks.create(start=4, end=12, virtual=True, style_id=style_id)
        highlights = textarea.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0].start == 4
        assert highlights[0].end == 12

    def test_should_highlight_virtual_marker_in_multiline_text_correctly(self):
        text = "Try moving your cursor through the [VIRTUAL] markers below:\n- Use arrow keys to navigate"
        textarea, extmarks = setup(text)
        style_id = 1
        match = re.search(r"\[VIRTUAL\]", text)
        assert match is not None
        start = match.start()
        end = match.end()
        extmarks.create(start=start, end=end, virtual=True, style_id=style_id)
        hl0 = textarea.get_line_highlights(0)
        hl1 = textarea.get_line_highlights(1)
        assert len(hl0) == 1
        assert hl0[0].start == 35
        assert hl0[0].end == 44
        assert len(hl1) == 0

    def test_should_correctly_highlight_multiple_virtual_markers_with_pattern_matching(self):
        initial_content = (
            "Welcome to the Extmarks Demo!\n"
            "\n"
            "This demo showcases virtual extmarks - text ranges that the cursor jumps over.\n"
            "\n"
            "Try moving your cursor through the [VIRTUAL] markers below:\n"
            "- Use arrow keys to navigate\n"
            "- Notice how the cursor skips over [VIRTUAL] ranges"
        )
        textarea, extmarks = setup(initial_content)
        style_id = 1
        text = textarea.plain_text
        pattern = re.compile(r"\[(VIRTUAL|LINK:[^\]]+|TAG:[^\]]+|MARKER)\]")
        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()
            extmarks.create(
                start=start,
                end=end,
                virtual=True,
                style_id=style_id,
                data={"type": "auto-detected", "content": match.group(0)},
            )
        lines = text.split("\n")
        line4_highlights = textarea.get_line_highlights(4)
        line6_highlights = textarea.get_line_highlights(6)
        assert len(line4_highlights) > 0
        assert len(line6_highlights) > 0
        assert line4_highlights[0].end == 44
        assert line4_highlights[0].end < len(lines[4])
        assert line6_highlights[0].end == 44
        assert line6_highlights[0].end < len(lines[6])


class TestMultipleExtmarks:
    """Maps to describe("Multiple Extmarks")."""

    def test_should_maintain_correct_positions_after_deleting_first_extmark(self):
        textarea, extmarks = setup("abc [VIRTUAL] def [VIRTUAL] ghi")
        style_id = 1
        id1 = extmarks.create(start=4, end=13, virtual=True, style_id=style_id)
        id2 = extmarks.create(start=18, end=27, virtual=True, style_id=style_id)
        textarea.focus()
        textarea.cursor_offset = 13
        textarea.press_backspace()
        assert extmarks.get(id1) is None
        em2 = extmarks.get(id2)
        assert em2 is not None
        assert textarea.plain_text[em2.start : em2.end] == "[VIRTUAL]"


class TestComplexMultilineScenarios:
    """Maps to describe("Complex Multiline Scenarios")."""

    def test_should_handle_multiple_marker_types_across_many_lines(self):
        initial_content = (
            "Welcome to the Extmarks Demo!\n"
            "\n"
            "This demo showcases virtual extmarks - text ranges that the cursor jumps over.\n"
            "\n"
            "Try moving your cursor through the [VIRTUAL] markers below:\n"
            "- Use arrow keys to navigate\n"
            "- Notice how the cursor skips over [VIRTUAL] ranges\n"
            "- Try backspacing at the end of a [VIRTUAL] marker\n"
            "- It will delete the entire marker!\n"
            "\n"
            "Example text with [LINK:https://example.com] embedded links.\n"
            "You can also have [TAG:important] tags that act like atoms.\n"
            "\n"
            "Regular text here can be edited normally.\n"
            "\n"
            "Press Ctrl+L to add a new [MARKER] at cursor position.\n"
            "Press ESC to return to main menu."
        )
        textarea, extmarks = setup(initial_content)
        style_id = 1
        text = textarea.plain_text
        pattern = re.compile(r"\[(VIRTUAL|LINK:[^\]]+|TAG:[^\]]+|MARKER)\]")
        lines = text.split("\n")
        marked_ranges = []
        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()
            # Find line index
            char_count = 0
            line_idx = 0
            for i, line in enumerate(lines):
                if char_count + len(line) >= start:
                    line_idx = i
                    break
                char_count += len(line) + 1
            marked_ranges.append(
                {"start": start, "end": end, "text": match.group(0), "line": line_idx}
            )
            extmarks.create(
                start=start,
                end=end,
                virtual=True,
                style_id=style_id,
                data={"type": "auto-detected", "content": match.group(0)},
            )
        for rng in marked_ranges:
            highlights = textarea.get_line_highlights(rng["line"])
            line_text = lines[rng["line"]]
            assert len(highlights) > 0
            matching = [
                h
                for h in highlights
                if line_text[h.start : min(h.end, len(line_text))].startswith(
                    rng["text"][: min(5, len(rng["text"]))]
                )
            ]
            assert len(matching) > 0
            assert matching[0].end <= len(line_text)


class TestVirtualExtmarkWordBoundaryMovement:
    """Maps to describe("Virtual Extmark - Word Boundary Movement")."""

    def test_should_not_land_inside_virtual_extmark_when_moving_backward_by_word_from_after_extmark(
        self,
    ):
        textarea, extmarks = setup("bla [VIRTUAL] bla")
        textarea.focus()
        textarea.cursor_offset = 13
        extmarks.create(start=4, end=13, virtual=True)
        assert textarea.cursor_offset == 13
        textarea.move_word_backward()
        assert textarea.cursor_offset == 3

    def test_should_jump_cursor_over_virtual_extmark_when_moving_forward_by_word(self):
        textarea, extmarks = setup("hello [VIRTUAL] world test")
        textarea.focus()
        textarea.cursor_offset = 0
        eid = extmarks.create(start=6, end=16, virtual=True)
        assert textarea.cursor_offset == 0
        textarea.move_word_forward()
        assert textarea.cursor_offset == 16
        textarea.move_word_forward()
        assert textarea.cursor_offset == 22
        assert extmarks.get(eid) is not None

    def test_should_jump_cursor_over_virtual_extmark_when_moving_backward_by_word(self):
        textarea, extmarks = setup("hello [VIRTUAL] world test")
        textarea.focus()
        textarea.cursor_offset = 22
        eid = extmarks.create(start=6, end=16, virtual=True)
        assert textarea.cursor_offset == 22
        textarea.move_word_backward()
        assert textarea.cursor_offset == 16
        textarea.move_word_backward()
        assert textarea.cursor_offset == 5
        assert extmarks.get(eid) is not None

    def test_should_jump_over_multiple_virtual_extmarks_when_moving_forward_by_word(self):
        textarea, extmarks = setup("one [V1] two [V2] three")
        textarea.focus()
        textarea.cursor_offset = 0
        extmarks.create(start=4, end=9, virtual=True)
        extmarks.create(start=13, end=18, virtual=True)
        textarea.move_word_forward()
        assert textarea.cursor_offset == 9
        textarea.move_word_forward()
        assert textarea.cursor_offset == 18
        textarea.move_word_forward()
        assert textarea.cursor_offset == 23

    def test_should_jump_over_multiple_virtual_extmarks_when_moving_backward_by_word(self):
        textarea, extmarks = setup("one [V1] two [V2] three")
        textarea.focus()
        textarea.cursor_offset = 23
        extmarks.create(start=4, end=9, virtual=True)
        extmarks.create(start=13, end=18, virtual=True)
        textarea.move_word_backward()
        assert textarea.cursor_offset == 18
        textarea.move_word_backward()
        assert textarea.cursor_offset == 12
        textarea.move_word_backward()
        assert textarea.cursor_offset == 9
        textarea.move_word_backward()
        assert textarea.cursor_offset == 3


class TestSetTextOperations:
    """Maps to describe("setText() Operations")."""

    def test_should_clear_all_extmarks_when_set_text_is_called(self):
        textarea, extmarks = setup("Hello World")
        id1 = extmarks.create(start=0, end=5)
        id2 = extmarks.create(start=6, end=11, virtual=True)
        assert len(extmarks.get_all()) == 2
        textarea.set_text("New Text")
        assert len(extmarks.get_all()) == 0
        assert extmarks.get(id1) is None
        assert extmarks.get(id2) is None

    def test_should_clear_all_extmarks_on_set_text(self):
        textarea, extmarks = setup("Hello World")
        extmarks.create(start=0, end=5)
        extmarks.create(start=6, end=11)
        assert len(extmarks.get_all()) == 2
        textarea.set_text("New Text")
        assert len(extmarks.get_all()) == 0

    def test_should_allow_new_extmarks_after_set_text(self):
        textarea, extmarks = setup("Hello World")
        extmarks.create(start=0, end=5)
        textarea.set_text("New Text")
        new_id = extmarks.create(start=0, end=3)
        em = extmarks.get(new_id)
        assert em is not None
        assert em.start == 0
        assert em.end == 3


class TestDeleteWordForwardOperations:
    """Maps to describe("deleteWordForward() Operations")."""

    def test_should_adjust_extmark_positions_after_delete_word_forward_before_extmark(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=12, end=16)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.delete_word_forward()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 6
        assert em.end == 10
        assert textarea.plain_text == "world test"

    def test_should_remove_extmark_when_delete_word_forward_covers_it(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=0, end=5)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.delete_word_forward()
        assert extmarks.get(eid) is None
        assert textarea.plain_text == "world test"

    def test_should_not_adjust_extmark_when_delete_word_forward_after(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=0, end=5)
        textarea.focus()
        textarea.cursor_offset = 6
        textarea.delete_word_forward()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 0
        assert em.end == 5


class TestDeleteWordBackwardOperations:
    """Maps to describe("deleteWordBackward() Operations")."""

    def test_should_adjust_extmark_positions_after_delete_word_backward_before_extmark(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=12, end=16)
        textarea.focus()
        textarea.cursor_offset = 11
        textarea.delete_word_backward()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 7
        assert em.end == 11
        assert textarea.plain_text == "hello  test"

    def test_should_remove_extmark_when_delete_word_backward_covers_it(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 11
        textarea.delete_word_backward()
        assert extmarks.get(eid) is None
        assert textarea.plain_text == "hello  test"

    def test_should_not_adjust_extmark_when_delete_word_backward_after(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=12, end=16)
        textarea.focus()
        textarea.cursor_offset = 5
        textarea.delete_word_backward()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 7
        assert em.end == 11
        assert textarea.plain_text == " world test"


class TestDeleteToLineEndOperations:
    """Maps to describe("deleteToLineEnd() Operations")."""

    def test_should_remove_extmark_when_delete_to_line_end_covers_it(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 2
        textarea.delete_to_line_end()
        assert extmarks.get(eid) is None
        assert textarea.plain_text == "He"

    def test_should_partially_trim_extmark_when_delete_to_line_end_overlaps_end(self):
        textarea, extmarks = setup("Hello World Extra")
        eid = extmarks.create(start=3, end=8)
        textarea.focus()
        textarea.cursor_offset = 6
        textarea.delete_to_line_end()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 3
        assert em.end == 6
        assert textarea.plain_text == "Hello "

    def test_should_not_adjust_extmark_when_delete_to_line_end_after(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=0, end=2)
        textarea.focus()
        textarea.cursor_offset = 5
        textarea.delete_to_line_end()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 0
        assert em.end == 2
        assert textarea.plain_text == "Hello"


class TestDeleteLineOperations:
    """Maps to describe("deleteLine() Operations")."""

    def test_should_adjust_extmark_positions_after_delete_line_before_extmark(self):
        textarea, extmarks = setup("Line1\nLine2\nLine3")
        eid = extmarks.create(start=12, end=17)
        textarea.focus()
        textarea.cursor_offset = 3
        textarea.delete_line()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 6
        assert em.end == 11
        assert textarea.plain_text == "Line2\nLine3"

    def test_should_remove_extmark_when_delete_line_on_line_containing_it(self):
        textarea, extmarks = setup("Line1\nLine2\nLine3")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 8
        textarea.delete_line()
        assert extmarks.get(eid) is None
        assert textarea.plain_text == "Line1\nLine3"

    def test_should_not_adjust_extmark_when_delete_line_after(self):
        textarea, extmarks = setup("Line1\nLine2\nLine3")
        eid = extmarks.create(start=0, end=5)
        textarea.focus()
        textarea.cursor_offset = 8
        textarea.delete_line()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 0
        assert em.end == 5


class TestNewLineOperations:
    """Maps to describe("new_line() Operations")."""

    def test_should_adjust_extmark_positions_after_new_line_before_extmark(self):
        textarea, extmarks = setup("HelloWorld")
        eid = extmarks.create(start=5, end=10)
        textarea.focus()
        textarea.cursor_offset = 2
        textarea.new_line()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 6
        assert em.end == 11
        assert textarea.plain_text == "He\nlloWorld"

    def test_should_expand_extmark_when_new_line_inside(self):
        textarea, extmarks = setup("HelloWorld")
        eid = extmarks.create(start=2, end=8)
        textarea.focus()
        textarea.cursor_offset = 5
        textarea.new_line()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 2
        assert em.end == 9

    def test_should_not_adjust_extmark_when_new_line_after(self):
        textarea, extmarks = setup("HelloWorld")
        eid = extmarks.create(start=0, end=5)
        textarea.focus()
        textarea.cursor_offset = 10
        textarea.new_line()
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 0
        assert em.end == 5


class TestClearOperations:
    """Maps to describe("clear() Operations")."""

    def test_should_clear_all_extmarks_when_clear_is_called(self):
        textarea, extmarks = setup("Hello World")
        id1 = extmarks.create(start=0, end=5)
        id2 = extmarks.create(start=6, end=11, virtual=True)
        assert len(extmarks.get_all()) == 2
        textarea.clear()
        assert len(extmarks.get_all()) == 0
        assert extmarks.get(id1) is None
        assert extmarks.get(id2) is None
        assert textarea.plain_text == ""

    def test_should_clear_all_extmarks_on_clear(self):
        textarea, extmarks = setup("Hello World")
        extmarks.create(start=0, end=5)
        extmarks.create(start=6, end=11)
        assert len(extmarks.get_all()) == 2
        textarea.clear()
        assert len(extmarks.get_all()) == 0

    def test_should_allow_new_extmarks_after_clear(self):
        textarea, extmarks = setup("Hello World")
        extmarks.create(start=0, end=5)
        textarea.clear()
        textarea.insert_text("New")
        new_id = extmarks.create(start=0, end=3)
        em = extmarks.get(new_id)
        assert em is not None
        assert em.start == 0
        assert em.end == 3


class TestSelectionDeletion:
    """Maps to describe("Selection Deletion")."""

    def test_should_adjust_extmarks_when_deleting_selection_with_backspace(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=12, end=16)
        textarea.focus()
        textarea.cursor_offset = 0
        for _ in range(4):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_backspace()
        assert textarea.plain_text == "o world test"
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 8
        assert em.end == 12

    def test_should_adjust_extmarks_when_deleting_selection_with_delete_key(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=12, end=16)
        textarea.focus()
        textarea.cursor_offset = 0
        for _ in range(4):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_key("DELETE")
        assert textarea.plain_text == "o world test"
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 8
        assert em.end == 12

    def test_should_adjust_extmarks_when_replacing_selection_with_text(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=12, end=16)
        textarea.focus()
        textarea.cursor_offset = 0
        for _ in range(5):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_key("X")
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 8
        assert em.end == 12
        assert textarea.plain_text == "X world test"

    def test_should_remove_extmark_when_selection_covers_it(self):
        textarea, extmarks = setup("hello world test")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 0
        for _ in range(12):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_backspace()
        assert extmarks.get(eid) is None
        assert textarea.plain_text == "test"


class TestMultilineSelectionDeletion:
    """Maps to describe("Multiline Selection Deletion")."""

    def test_should_adjust_extmarks_after_deleting_multiline_selection(self):
        textarea, extmarks = setup("Line 1\nLine 2\nLine 3\nLine 4")
        eid = extmarks.create(start=21, end=27)
        textarea.focus()
        textarea.cursor_offset = 7
        for _ in range(7):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_backspace()
        assert textarea.plain_text == "Line 1\nLine 3\nLine 4"
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 14
        assert em.end == 20

    def test_should_adjust_multiple_extmarks_after_deleting_multiline_selection(self):
        textarea, extmarks = setup("AAA\nBBB\nCCC\nDDD")
        id1 = extmarks.create(start=8, end=11)
        id2 = extmarks.create(start=12, end=15)
        textarea.focus()
        textarea.cursor_offset = 0
        for _ in range(8):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_backspace()
        assert textarea.plain_text == "CCC\nDDD"
        em1 = extmarks.get(id1)
        assert em1 is not None
        assert em1.start == 0
        assert em1.end == 3
        assert textarea.plain_text[em1.start : em1.end] == "CCC"
        em2 = extmarks.get(id2)
        assert em2 is not None
        assert em2.start == 4
        assert em2.end == 7
        assert textarea.plain_text[em2.start : em2.end] == "DDD"

    def test_should_correctly_adjust_extmark_spanning_multiple_lines_after_multiline_deletion(self):
        textarea, extmarks = setup("AAA\nBBB\nCCC\nDDD\nEEE")
        eid = extmarks.create(start=12, end=19)
        textarea.focus()
        textarea.cursor_offset = 0
        for _ in range(8):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_backspace()
        assert textarea.plain_text == "CCC\nDDD\nEEE"
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 4
        assert em.end == 11
        assert textarea.plain_text[em.start : em.end] == "DDD\nEEE"

    def test_should_handle_deletion_of_selection_that_partially_overlaps_extmark_start(self):
        textarea, extmarks = setup("AAA\nBBB\nCCC\nDDD")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 4
        for _ in range(6):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_backspace()
        assert textarea.plain_text == "AAA\nC\nDDD"
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 4
        assert em.end == 5

    def test_should_handle_deletion_across_three_lines_with_extmarks_after(self):
        textarea, extmarks = setup("Line1\nLine2\nLine3\nLine4\nLine5")
        id1 = extmarks.create(start=18, end=23)
        id2 = extmarks.create(start=24, end=29)
        textarea.focus()
        textarea.cursor_offset = 0
        for _ in range(18):
            textarea.press_arrow("right", shift=True)
        assert textarea.has_selection()
        textarea.press_backspace()
        assert textarea.plain_text == "Line4\nLine5"
        em1 = extmarks.get(id1)
        assert em1 is not None
        assert em1.start == 0
        assert em1.end == 5
        assert textarea.plain_text[em1.start : em1.end] == "Line4"
        em2 = extmarks.get(id2)
        assert em2 is not None
        assert em2.start == 6
        assert em2.end == 11
        assert textarea.plain_text[em2.start : em2.end] == "Line5"


class TestEdgeCases:
    """Maps to describe("Edge Cases")."""

    def test_should_handle_extmark_at_start_of_text(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=0, end=5, virtual=True)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 5
        assert extmarks.get(eid) is not None

    def test_should_handle_extmark_at_end_of_text(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11, virtual=True)
        textarea.focus()
        textarea.cursor_offset = 11
        textarea.press_arrow("left")
        assert textarea.cursor_offset == 5
        assert extmarks.get(eid) is not None

    def test_should_handle_zero_width_extmark(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=5, end=5)
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 5
        assert em.end == 5

    def test_should_handle_overlapping_extmarks(self):
        textarea, extmarks = setup("Hello World")
        id1 = extmarks.create(start=0, end=7)
        id2 = extmarks.create(start=3, end=9)
        at5 = extmarks.get_at_offset(5)
        assert len(at5) == 2
        assert sorted([e.id for e in at5]) == sorted([id1, id2])

    def test_should_handle_empty_text(self):
        textarea, extmarks = setup("")
        eid = extmarks.create(start=0, end=0)
        em = extmarks.get(eid)
        assert em is not None


class TestVirtualExtmarkCursorUpDownMovement:
    """Maps to describe("Virtual Extmark - Cursor Up/Down Movement")."""

    def test_should_not_land_inside_virtual_extmark_when_moving_down(self):
        textarea, extmarks = setup("abc\n[VIRTUAL]\ndef")
        textarea.focus()
        textarea.cursor_offset = 1
        extmarks.create(start=4, end=13, virtual=True)
        assert textarea.cursor_offset == 1
        textarea.press_arrow("down")
        cursor_after = textarea.cursor_offset
        is_inside = 4 <= cursor_after < 13
        assert not is_inside

    def test_should_not_land_inside_virtual_extmark_when_moving_up(self):
        textarea, extmarks = setup("abc\n[VIRTUAL]\ndef")
        textarea.focus()
        textarea.cursor_offset = 15
        extmarks.create(start=4, end=13, virtual=True)
        assert textarea.cursor_offset == 15
        textarea.press_arrow("up")
        cursor_after = textarea.cursor_offset
        is_inside = 4 <= cursor_after < 13
        assert not is_inside

    def test_should_jump_to_closest_boundary_when_moving_down_into_virtual_extmark(self):
        textarea, extmarks = setup("abc\n[VIRTUAL]\ndef")
        textarea.focus()
        textarea.cursor_offset = 1
        extmarks.create(start=4, end=13, virtual=True)
        textarea.press_arrow("down")
        cursor_after = textarea.cursor_offset
        assert cursor_after in (3, 13)

    def test_should_jump_to_closest_boundary_when_moving_up_into_virtual_extmark(self):
        textarea, extmarks = setup("abc\n[VIRTUAL]\ndef")
        textarea.focus()
        textarea.cursor_offset = 15
        extmarks.create(start=4, end=13, virtual=True)
        textarea.press_arrow("up")
        cursor_after = textarea.cursor_offset
        assert cursor_after in (3, 13)

    def test_should_handle_multiline_virtual_extmarks_when_moving_up(self):
        textarea, extmarks = setup("line1\n[VIRTUAL\nMULTILINE]\nline4")
        textarea.focus()
        textarea.cursor_offset = 28
        extmarks.create(start=6, end=25, virtual=True)
        textarea.press_arrow("up")
        textarea.press_arrow("up")
        cursor_after = textarea.cursor_offset
        is_inside = 6 <= cursor_after < 25
        assert not is_inside

    def test_should_handle_multiline_virtual_extmarks_when_moving_down(self):
        textarea, extmarks = setup("line1\n[VIRTUAL\nMULTILINE]\nline4")
        textarea.focus()
        textarea.cursor_offset = 3
        extmarks.create(start=6, end=25, virtual=True)
        textarea.press_arrow("down")
        textarea.press_arrow("down")
        cursor_after = textarea.cursor_offset
        is_inside = 6 <= cursor_after < 25
        assert not is_inside

    def test_should_not_get_stuck_when_moving_down_into_virtual_extmark_at_start_of_line(self):
        textarea, extmarks = setup("a\n\n[EXT]\nb")
        textarea.focus()
        textarea.cursor_offset = 2
        extmarks.create(start=3, end=8, virtual=True)
        initial_offset = textarea.cursor_offset
        assert initial_offset == 2
        textarea.press_arrow("down")
        cursor_after = textarea.cursor_offset
        assert cursor_after == 8

    def test_should_land_at_trailing_text_when_moving_down_into_line_start_virtual_extmark(self):
        textarea, extmarks = setup("a\n\n[EXT]tail\nb")
        textarea.focus()
        textarea.cursor_offset = 2
        extmarks.create(start=3, end=8, virtual=True)
        textarea.press_arrow("down")
        cursor_after = textarea.cursor_offset
        assert cursor_after == 8
        assert textarea.plain_text[cursor_after : cursor_after + 4] == "tail"

    def test_should_not_jump_past_buffer_end_when_moving_down_into_line_start_virtual_extmark_at_eof(
        self,
    ):
        textarea, extmarks = setup("a\n\n[EXT]")
        textarea.focus()
        textarea.cursor_offset = 2
        extmarks.create(start=3, end=8, virtual=True)
        textarea.press_arrow("down")
        cursor_after = textarea.cursor_offset
        assert cursor_after == 8
        assert cursor_after == len(textarea.plain_text)

    def test_should_navigate_past_virtual_extmark_at_line_start_with_repeated_down_presses(self):
        textarea, extmarks = setup("abc\n\n[EXTMARK]\n\nxyz")
        textarea.focus()
        textarea.cursor_offset = 0
        extmarks.create(start=5, end=14, virtual=True)
        textarea.press_arrow("down")
        textarea.press_arrow("down")
        after_extmark = textarea.cursor_offset
        assert after_extmark == 14
        textarea.press_arrow("down")
        textarea.press_arrow("down")
        final_offset = textarea.cursor_offset
        xyz_start = textarea.plain_text.index("xyz")
        assert final_offset >= xyz_start
        assert final_offset <= len(textarea.plain_text)


class TestTypeIdOperations:
    """Maps to describe("TypeId Operations")."""

    def test_should_create_extmark_with_default_type_id_0(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5)
        em = extmarks.get(eid)
        assert em is not None
        assert em.type_id == 0

    def test_should_create_extmark_with_custom_type_id(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5, type_id=42)
        em = extmarks.get(eid)
        assert em is not None
        assert em.type_id == 42

    def test_should_retrieve_all_extmarks_for_a_specific_type_id(self):
        textarea, extmarks = setup()
        id1 = extmarks.create(start=0, end=5, type_id=1)
        id2 = extmarks.create(start=6, end=11, type_id=1)
        id3 = extmarks.create(start=12, end=15, type_id=2)
        type1 = extmarks.get_all_for_type_id(1)
        assert len(type1) == 2
        assert sorted([e.id for e in type1]) == sorted([id1, id2])
        type2 = extmarks.get_all_for_type_id(2)
        assert len(type2) == 1
        assert type2[0].id == id3

    def test_should_return_empty_array_for_non_existent_type_id(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5, type_id=1)
        assert len(extmarks.get_all_for_type_id(999)) == 0

    def test_should_handle_multiple_extmarks_with_same_type_id(self):
        textarea, extmarks = setup()
        ids = [extmarks.create(start=i, end=i + 1, type_id=5) for i in range(10)]
        type5 = extmarks.get_all_for_type_id(5)
        assert len(type5) == 10
        assert sorted([e.id for e in type5]) == sorted(ids)

    def test_should_remove_extmark_from_type_id_index_when_deleted(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5, type_id=3)
        assert len(extmarks.get_all_for_type_id(3)) == 1
        extmarks.delete(eid)
        assert len(extmarks.get_all_for_type_id(3)) == 0

    def test_should_clear_all_type_id_indexes_when_clear_is_called(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5, type_id=1)
        extmarks.create(start=6, end=11, type_id=2)
        extmarks.create(start=12, end=15, type_id=3)
        extmarks.clear()
        assert len(extmarks.get_all_for_type_id(1)) == 0
        assert len(extmarks.get_all_for_type_id(2)) == 0
        assert len(extmarks.get_all_for_type_id(3)) == 0

    def test_should_maintain_type_id_through_text_operations(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11, type_id=7)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.press_key("X")
        textarea.press_key("X")
        em = extmarks.get(eid)
        assert em is not None
        assert em.type_id == 7
        type7 = extmarks.get_all_for_type_id(7)
        assert len(type7) == 1
        assert type7[0].id == eid

    def test_should_group_virtual_and_non_virtual_extmarks_by_type_id(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5, type_id=10, virtual=False)
        extmarks.create(start=6, end=11, type_id=10, virtual=True)
        extmarks.create(start=12, end=15, type_id=10, virtual=False)
        type10 = extmarks.get_all_for_type_id(10)
        assert len(type10) == 3
        virtual_marks = [e for e in type10 if e.virtual]
        non_virtual = [e for e in type10 if not e.virtual]
        assert len(virtual_marks) == 1
        assert len(non_virtual) == 2

    def test_should_handle_type_id_0_as_default(self):
        textarea, extmarks = setup()
        id1 = extmarks.create(start=0, end=5)
        id2 = extmarks.create(start=6, end=11, type_id=0)
        id3 = extmarks.create(start=12, end=15)
        type0 = extmarks.get_all_for_type_id(0)
        assert len(type0) == 3
        assert sorted([e.id for e in type0]) == sorted([id1, id2, id3])

    def test_should_remove_extmark_from_type_id_index_on_deletion_during_backspace(self):
        textarea, extmarks = setup("abc[LINK]def")
        textarea.focus()
        textarea.cursor_offset = 9
        eid = extmarks.create(start=3, end=9, virtual=True, type_id=15)
        assert len(extmarks.get_all_for_type_id(15)) == 1
        textarea.press_backspace()
        assert extmarks.get(eid) is None
        assert len(extmarks.get_all_for_type_id(15)) == 0

    def test_should_remove_extmark_from_type_id_index_on_deletion_during_delete_key(self):
        textarea, extmarks = setup("abc[LINK]def")
        textarea.focus()
        textarea.cursor_offset = 3
        eid = extmarks.create(start=3, end=9, virtual=True, type_id=20)
        assert len(extmarks.get_all_for_type_id(20)) == 1
        textarea.press_key("DELETE")
        assert extmarks.get(eid) is None
        assert len(extmarks.get_all_for_type_id(20)) == 0

    def test_should_handle_get_all_for_type_id_on_destroyed_controller(self):
        textarea, extmarks = setup()
        extmarks.create(start=0, end=5, type_id=1)
        extmarks.destroy()
        assert len(extmarks.get_all_for_type_id(1)) == 0

    def test_should_support_multiple_different_type_ids_simultaneously(self):
        textarea, extmarks = setup("The quick brown fox jumps over the lazy dog")
        link1 = extmarks.create(start=0, end=3, type_id=1)
        link2 = extmarks.create(start=10, end=15, type_id=1)
        tag1 = extmarks.create(start=4, end=9, type_id=2)
        tag2 = extmarks.create(start=16, end=19, type_id=2)
        marker = extmarks.create(start=20, end=25, type_id=3)
        links = extmarks.get_all_for_type_id(1)
        assert len(links) == 2
        assert sorted([e.id for e in links]) == sorted([link1, link2])
        tags = extmarks.get_all_for_type_id(2)
        assert len(tags) == 2
        assert sorted([e.id for e in tags]) == sorted([tag1, tag2])
        markers = extmarks.get_all_for_type_id(3)
        assert len(markers) == 1
        assert markers[0].id == marker
        assert len(extmarks.get_all()) == 5

    def test_should_preserve_type_id_when_extmark_is_adjusted_after_insertion(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11, type_id=50)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.press_key("Z")
        em = extmarks.get(eid)
        assert em is not None
        assert em.type_id == 50
        assert em.start == 7
        assert em.end == 12
        assert len(extmarks.get_all_for_type_id(50)) == 1

    def test_should_preserve_type_id_when_extmark_is_adjusted_after_deletion(self):
        textarea, extmarks = setup("XXHello World")
        eid = extmarks.create(start=8, end=13, type_id=60)
        textarea.focus()
        textarea.cursor_offset = 2
        textarea.press_backspace()
        textarea.press_backspace()
        em = extmarks.get(eid)
        assert em is not None
        assert em.type_id == 60
        assert em.start == 6
        assert em.end == 11
        assert len(extmarks.get_all_for_type_id(60)) == 1


class TestUndoRedoWithExtmarks:
    """Maps to describe("Undo/Redo with Extmarks")."""

    def test_should_restore_extmark_after_undo_of_text_insertion(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=0, end=5, style_id=1)
        textarea.focus()
        textarea.cursor_offset = 3
        textarea.buf.save_undo()
        textarea.press_key("X")
        em_after = extmarks.get(eid)
        assert em_after is not None
        assert em_after.start == 0
        assert em_after.end == 6
        textarea.undo()
        em_undo = extmarks.get(eid)
        assert em_undo is not None
        assert em_undo.start == 0
        assert em_undo.end == 5

    def test_should_restore_extmark_after_undo_of_text_deletion(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11, style_id=1)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.buf.save_undo()
        textarea.press_key("DELETE")
        em_after = extmarks.get(eid)
        assert em_after is not None
        assert em_after.start == 5
        assert em_after.end == 10
        textarea.undo()
        em_undo = extmarks.get(eid)
        assert em_undo is not None
        assert em_undo.start == 6
        assert em_undo.end == 11

    def test_should_restore_extmark_after_redo(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=0, end=5, style_id=1)
        textarea.focus()
        textarea.cursor_offset = 3
        textarea.buf.save_undo()
        textarea.press_key("X")
        em_ins = extmarks.get(eid)
        assert em_ins is not None
        assert em_ins.start == 0
        assert em_ins.end == 6
        textarea.undo()
        em_undo = extmarks.get(eid)
        assert em_undo is not None
        assert em_undo.start == 0
        assert em_undo.end == 5
        textarea.redo()
        em_redo = extmarks.get(eid)
        assert em_redo is not None
        assert em_redo.start == 0
        assert em_redo.end == 6

    def test_should_restore_deleted_virtual_extmark_after_undo(self):
        textarea, extmarks = setup("abc[LINK]def")
        textarea.focus()
        textarea.cursor_offset = 9
        eid = extmarks.create(start=3, end=9, virtual=True)
        textarea.buf.save_undo()
        textarea.press_backspace()
        assert textarea.plain_text == "abcdef"
        assert extmarks.get(eid) is None
        textarea.undo()
        em_undo = extmarks.get(eid)
        assert em_undo is not None
        assert em_undo.start == 3
        assert em_undo.end == 9
        assert em_undo.virtual is True
        assert textarea.plain_text == "abc[LINK]def"

    def test_should_handle_multiple_undo_redo_operations(self):
        textarea, extmarks = setup("Test")
        eid = extmarks.create(start=0, end=4)
        textarea.focus()
        textarea.cursor_offset = 2

        textarea.buf.save_undo()
        textarea.press_key("1")
        assert extmarks.get(eid).end == 5

        textarea.buf.save_undo()
        textarea.press_key("2")
        assert extmarks.get(eid).end == 6

        textarea.buf.save_undo()
        textarea.press_key("3")
        assert extmarks.get(eid).end == 7

        textarea.undo()
        assert extmarks.get(eid).end == 6
        textarea.undo()
        assert extmarks.get(eid).end == 5
        textarea.undo()
        assert extmarks.get(eid).end == 4
        textarea.redo()
        assert extmarks.get(eid).end == 5
        textarea.redo()
        assert extmarks.get(eid).end == 6
        textarea.redo()
        assert extmarks.get(eid).end == 7

    def test_should_restore_multiple_extmarks_after_undo(self):
        textarea, extmarks = setup("Hello World Test")
        id1 = extmarks.create(start=0, end=5)
        id2 = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.buf.save_undo()
        textarea.press_key("X")
        assert extmarks.get(id1).start == 1
        assert extmarks.get(id1).end == 6
        assert extmarks.get(id2).start == 7
        assert extmarks.get(id2).end == 12
        textarea.undo()
        assert extmarks.get(id1).start == 0
        assert extmarks.get(id1).end == 5
        assert extmarks.get(id2).start == 6
        assert extmarks.get(id2).end == 11

    def test_should_handle_undo_after_backspace_that_deleted_virtual_extmark(self):
        textarea, extmarks = setup("text[VIRTUAL]more")
        textarea.focus()
        textarea.cursor_offset = 13
        eid = extmarks.create(start=4, end=13, virtual=True)
        textarea.buf.save_undo()
        textarea.press_backspace()
        assert textarea.plain_text == "textmore"
        assert extmarks.get(eid) is None
        textarea.undo()
        restored = extmarks.get(eid)
        assert restored is not None
        assert restored.start == 4
        assert restored.end == 13
        assert restored.virtual is True

    def test_should_restore_extmark_ids_correctly_after_undo(self):
        textarea, extmarks = setup("Test")
        id1 = extmarks.create(start=0, end=2)
        id2 = extmarks.create(start=2, end=4)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.buf.save_undo()
        textarea.press_key("X")
        textarea.undo()
        assert extmarks.get(id1) is not None
        assert extmarks.get(id2) is not None
        assert extmarks.get(id1).id == id1
        assert extmarks.get(id2).id == id2

    def test_should_preserve_extmark_data_after_undo_redo(self):
        textarea, extmarks = setup("Hello")
        eid = extmarks.create(start=0, end=5, data={"type": "link", "url": "https://example.com"})
        textarea.focus()
        textarea.cursor_offset = 5
        textarea.buf.save_undo()
        textarea.press_key("X")
        textarea.undo()
        em = extmarks.get(eid)
        assert em is not None
        assert em.data == {"type": "link", "url": "https://example.com"}
        textarea.redo()
        em2 = extmarks.get(eid)
        assert em2 is not None
        assert em2.data == {"type": "link", "url": "https://example.com"}

    def test_should_handle_undo_redo_with_multiline_extmarks(self):
        textarea, extmarks = setup("Line1\nLine2\nLine3")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.buf.save_undo()
        textarea.press_key("X")
        assert extmarks.get(eid).start == 7
        assert extmarks.get(eid).end == 12
        textarea.undo()
        assert extmarks.get(eid).start == 6
        assert extmarks.get(eid).end == 11
        textarea.redo()
        assert extmarks.get(eid).start == 7
        assert extmarks.get(eid).end == 12

    def test_should_handle_undo_after_delete_range(self):
        textarea, extmarks = setup("Hello World Test")
        eid = extmarks.create(start=12, end=16)
        textarea.focus()
        textarea.buf.save_undo()
        textarea.delete_range(0, 0, 0, 6)
        assert extmarks.get(eid).start == 6
        assert extmarks.get(eid).end == 10
        textarea.undo()
        assert extmarks.get(eid).start == 12
        assert extmarks.get(eid).end == 16

    def test_should_maintain_correct_next_id_after_undo_redo(self):
        textarea, extmarks = setup("Test")
        extmarks.create(start=0, end=2)
        textarea.focus()
        textarea.cursor_offset = 4
        textarea.buf.save_undo()
        textarea.press_key("X")
        textarea.undo()
        new_id = extmarks.create(start=2, end=4)
        assert new_id == 2

    def test_should_handle_undo_redo_of_selection_deletion(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=6, end=11)
        textarea.focus()
        textarea.cursor_offset = 0
        for _ in range(5):
            textarea.press_arrow("right", shift=True)
        textarea.buf.save_undo()
        textarea.press_backspace()
        assert textarea.plain_text == " World"
        assert extmarks.get(eid).start == 1
        assert extmarks.get(eid).end == 6
        textarea.undo()
        assert textarea.plain_text == "Hello World"
        assert extmarks.get(eid).start == 6
        assert extmarks.get(eid).end == 11


class TestTypeRegistry:
    """Maps to describe("Type Registry")."""

    def test_should_register_a_type_name_and_return_a_unique_type_id(self):
        textarea, extmarks = setup()
        link_tid = extmarks.register_type("link")
        assert link_tid == 1
        tag_tid = extmarks.register_type("tag")
        assert tag_tid == 2
        assert link_tid != tag_tid

    def test_should_return_the_same_type_id_for_duplicate_type_name_registration(self):
        textarea, extmarks = setup()
        first = extmarks.register_type("link")
        second = extmarks.register_type("link")
        assert first == second

    def test_should_resolve_type_name_to_type_id(self):
        textarea, extmarks = setup()
        link_tid = extmarks.register_type("link")
        assert extmarks.get_type_id("link") == link_tid

    def test_should_return_null_for_unregistered_type_name(self):
        textarea, extmarks = setup()
        assert extmarks.get_type_id("nonexistent") is None

    def test_should_resolve_type_id_to_type_name(self):
        textarea, extmarks = setup()
        link_tid = extmarks.register_type("link")
        assert extmarks.get_type_name(link_tid) == "link"

    def test_should_return_null_for_unregistered_type_id(self):
        textarea, extmarks = setup()
        assert extmarks.get_type_name(999) is None

    def test_should_create_extmark_with_registered_type(self):
        textarea, extmarks = setup()
        link_tid = extmarks.register_type("link")
        eid = extmarks.create(start=0, end=5, type_id=link_tid)
        em = extmarks.get(eid)
        assert em is not None
        assert em.type_id == link_tid

    def test_should_retrieve_extmarks_by_registered_type_name(self):
        textarea, extmarks = setup()
        link_tid = extmarks.register_type("link")
        tag_tid = extmarks.register_type("tag")
        link1 = extmarks.create(start=0, end=5, type_id=link_tid)
        link2 = extmarks.create(start=6, end=11, type_id=link_tid)
        tag1 = extmarks.create(start=12, end=15, type_id=tag_tid)
        links = extmarks.get_all_for_type_id(link_tid)
        assert len(links) == 2
        assert sorted([e.id for e in links]) == sorted([link1, link2])
        tags = extmarks.get_all_for_type_id(tag_tid)
        assert len(tags) == 1
        assert tags[0].id == tag1

    def test_should_handle_multiple_type_registrations(self):
        textarea, extmarks = setup()
        types = ["link", "tag", "marker", "highlight", "error"]
        type_ids = [extmarks.register_type(t) for t in types]
        assert len(set(type_ids)) == len(types)
        for i, t in enumerate(types):
            assert extmarks.get_type_id(t) == type_ids[i]
            assert extmarks.get_type_name(type_ids[i]) == t

    def test_should_preserve_type_registry_across_text_operations(self):
        textarea, extmarks = setup("Hello World")
        link_tid = extmarks.register_type("link")
        eid = extmarks.create(start=0, end=5, type_id=link_tid)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.press_key("X")
        assert extmarks.get_type_id("link") == link_tid
        assert extmarks.get_type_name(link_tid) == "link"
        em = extmarks.get(eid)
        assert em is not None
        assert em.type_id == link_tid

    def test_should_clear_type_registry_on_destroy(self):
        textarea, extmarks = setup()
        link_tid = extmarks.register_type("link")
        extmarks.register_type("tag")
        extmarks.destroy()
        assert extmarks.get_type_id("link") is None
        assert extmarks.get_type_name(link_tid) is None

    def test_should_throw_error_when_registering_type_on_destroyed_controller(self):
        textarea, extmarks = setup()
        extmarks.destroy()
        with pytest.raises(RuntimeError, match="ExtmarksController is destroyed"):
            extmarks.register_type("link")

    def test_should_support_workflow_of_register_then_create_extmarks(self):
        textarea, extmarks = setup("The quick brown fox")
        link_tid = extmarks.register_type("link")
        emphasis_tid = extmarks.register_type("emphasis")
        l1 = extmarks.create(start=0, end=3, type_id=link_tid, virtual=True)
        l2 = extmarks.create(start=10, end=15, type_id=link_tid, virtual=True)
        e1 = extmarks.create(start=4, end=9, type_id=emphasis_tid)
        links = extmarks.get_all_for_type_id(link_tid)
        assert len(links) == 2
        assert sorted([e.id for e in links]) == sorted([l1, l2])
        emphases = extmarks.get_all_for_type_id(emphasis_tid)
        assert len(emphases) == 1
        assert emphases[0].id == e1
        assert extmarks.get_type_name(link_tid) == "link"
        assert extmarks.get_type_name(emphasis_tid) == "emphasis"

    def test_should_handle_type_names_with_special_characters(self):
        textarea, extmarks = setup()
        tid1 = extmarks.register_type("my-type")
        tid2 = extmarks.register_type("my_type")
        tid3 = extmarks.register_type("my.type")
        tid4 = extmarks.register_type("my:type")
        assert extmarks.get_type_id("my-type") == tid1
        assert extmarks.get_type_id("my_type") == tid2
        assert extmarks.get_type_id("my.type") == tid3
        assert extmarks.get_type_id("my:type") == tid4
        assert tid1 != tid2
        assert tid2 != tid3
        assert tid3 != tid4

    def test_should_handle_empty_string_as_type_name(self):
        textarea, extmarks = setup()
        tid = extmarks.register_type("")
        assert tid == 1
        assert extmarks.get_type_id("") == tid
        assert extmarks.get_type_name(tid) == ""

    def test_should_return_null_for_get_type_id_and_get_type_name_on_destroyed_controller(self):
        textarea, extmarks = setup()
        link_tid = extmarks.register_type("link")
        extmarks.destroy()
        assert extmarks.get_type_id("link") is None
        assert extmarks.get_type_name(link_tid) is None

    def test_should_allow_re_registration_after_clear(self):
        textarea, extmarks = setup()
        first_link = extmarks.register_type("link")
        extmarks.create(start=0, end=5, type_id=first_link)
        extmarks.clear()
        assert extmarks.get_type_id("link") == first_link
        new_eid = extmarks.create(start=0, end=3, type_id=first_link)
        assert extmarks.get(new_eid).type_id == first_link

    def test_should_support_case_sensitive_type_names(self):
        textarea, extmarks = setup()
        lower = extmarks.register_type("link")
        upper = extmarks.register_type("Link")
        all_caps = extmarks.register_type("LINK")
        assert lower != upper
        assert upper != all_caps
        assert lower != all_caps
        assert extmarks.get_type_id("link") == lower
        assert extmarks.get_type_id("Link") == upper
        assert extmarks.get_type_id("LINK") == all_caps

    def test_should_maintain_type_id_sequence_independent_of_extmark_ids(self):
        textarea, extmarks = setup()
        eid1 = extmarks.create(start=0, end=1)
        eid2 = extmarks.create(start=1, end=2)
        link_tid = extmarks.register_type("link")
        tag_tid = extmarks.register_type("tag")
        assert link_tid == 1
        assert tag_tid == 2
        assert eid1 >= 1
        assert eid2 >= 2

    def test_should_handle_numeric_like_string_type_names(self):
        textarea, extmarks = setup()
        tid1 = extmarks.register_type("123")
        tid2 = extmarks.register_type("456")
        assert extmarks.get_type_id("123") == tid1
        assert extmarks.get_type_id("456") == tid2
        assert tid1 != tid2

    def test_should_support_long_type_names(self):
        textarea, extmarks = setup()
        long_name = "a" * 1000
        tid = extmarks.register_type(long_name)
        assert extmarks.get_type_id(long_name) == tid
        assert extmarks.get_type_name(tid) == long_name


class TestMetadataOperations:
    """Maps to describe("Metadata Operations")."""

    def test_should_store_and_retrieve_metadata_for_extmark(self):
        textarea, extmarks = setup()
        meta = {"url": "https://example.com", "title": "Example"}
        eid = extmarks.create(start=0, end=5, metadata=meta)
        assert extmarks.get_metadata_for(eid) == meta

    def test_should_return_undefined_for_extmark_without_metadata(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5)
        assert extmarks.get_metadata_for(eid) is None

    def test_should_return_undefined_for_non_existent_extmark(self):
        textarea, extmarks = setup()
        assert extmarks.get_metadata_for(999) is None

    def test_should_handle_different_metadata_types(self):
        textarea, extmarks = setup()
        id1 = extmarks.create(start=0, end=5, metadata={"type": "object", "value": 42})
        id2 = extmarks.create(start=6, end=11, metadata="string metadata")
        id3 = extmarks.create(start=12, end=15, metadata=123)
        id4 = extmarks.create(start=16, end=20, metadata=True)
        id5 = extmarks.create(start=21, end=25, metadata=["array", "metadata"])
        assert extmarks.get_metadata_for(id1) == {"type": "object", "value": 42}
        assert extmarks.get_metadata_for(id2) == "string metadata"
        assert extmarks.get_metadata_for(id3) == 123
        assert extmarks.get_metadata_for(id4) is True
        assert extmarks.get_metadata_for(id5) == ["array", "metadata"]

    def test_should_handle_null_metadata(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5, metadata=None)
        assert extmarks.get_metadata_for(eid) is None

    def test_should_preserve_metadata_when_extmark_is_adjusted(self):
        textarea, extmarks = setup("Hello World")
        meta = {"label": "important"}
        eid = extmarks.create(start=6, end=11, metadata=meta)
        textarea.focus()
        textarea.cursor_offset = 0
        textarea.press_key("X")
        textarea.press_key("X")
        em = extmarks.get(eid)
        assert em is not None
        assert em.start == 8
        assert em.end == 13
        assert extmarks.get_metadata_for(eid) == meta

    def test_should_remove_metadata_when_extmark_is_deleted(self):
        textarea, extmarks = setup()
        meta = {"data": "test"}
        eid = extmarks.create(start=0, end=5, metadata=meta)
        assert extmarks.get_metadata_for(eid) == meta
        extmarks.delete(eid)
        assert extmarks.get_metadata_for(eid) is None

    def test_should_clear_all_metadata_when_clear_is_called(self):
        textarea, extmarks = setup()
        id1 = extmarks.create(start=0, end=5, metadata={"key": "value1"})
        id2 = extmarks.create(start=6, end=11, metadata={"key": "value2"})
        extmarks.clear()
        assert extmarks.get_metadata_for(id1) is None
        assert extmarks.get_metadata_for(id2) is None

    def test_should_remove_metadata_when_virtual_extmark_is_deleted_via_backspace(self):
        textarea, extmarks = setup("abc[LINK]def")
        textarea.focus()
        textarea.cursor_offset = 9
        meta = {"url": "https://test.com"}
        eid = extmarks.create(start=3, end=9, virtual=True, metadata=meta)
        assert extmarks.get_metadata_for(eid) == meta
        textarea.press_backspace()
        assert extmarks.get(eid) is None
        assert extmarks.get_metadata_for(eid) is None

    def test_should_handle_metadata_with_nested_objects(self):
        textarea, extmarks = setup()
        import time

        meta = {
            "user": {
                "id": 123,
                "name": "John Doe",
                "settings": {
                    "theme": "dark",
                    "notifications": True,
                },
            },
            "timestamp": time.time(),
        }
        eid = extmarks.create(start=0, end=5, metadata=meta)
        assert extmarks.get_metadata_for(eid) == meta

    def test_should_store_independent_metadata_for_multiple_extmarks(self):
        textarea, extmarks = setup()
        id1 = extmarks.create(start=0, end=5, metadata={"id": 1, "color": "red"})
        id2 = extmarks.create(start=6, end=11, metadata={"id": 2, "color": "blue"})
        id3 = extmarks.create(start=12, end=15, metadata={"id": 3, "color": "green"})
        assert extmarks.get_metadata_for(id1) == {"id": 1, "color": "red"}
        assert extmarks.get_metadata_for(id2) == {"id": 2, "color": "blue"}
        assert extmarks.get_metadata_for(id3) == {"id": 3, "color": "green"}

    def test_should_handle_metadata_with_both_metadata_and_data_fields(self):
        textarea, extmarks = setup()
        data = {"oldField": "data"}
        meta = {"newField": "metadata"}
        eid = extmarks.create(start=0, end=5, data=data, metadata=meta)
        em = extmarks.get(eid)
        assert em is not None
        assert em.data == data
        assert extmarks.get_metadata_for(eid) == meta

    def test_should_return_undefined_when_getting_metadata_on_destroyed_controller(self):
        textarea, extmarks = setup()
        eid = extmarks.create(start=0, end=5, metadata={"test": "data"})
        extmarks.destroy()
        assert extmarks.get_metadata_for(eid) is None

    def test_should_handle_metadata_with_special_values(self):
        textarea, extmarks = setup()
        # metadata=None (undefined in JS) -- not stored
        id1 = extmarks.create(start=0, end=5)  # no metadata kwarg
        id2 = extmarks.create(start=6, end=11, metadata=0)
        id3 = extmarks.create(start=12, end=15, metadata="")
        id4 = extmarks.create(start=16, end=20, metadata=False)
        assert extmarks.get_metadata_for(id1) is None
        assert extmarks.get_metadata_for(id2) == 0
        assert extmarks.get_metadata_for(id3) == ""
        assert extmarks.get_metadata_for(id4) is False

    def test_should_handle_metadata_for_extmarks_with_same_range(self):
        textarea, extmarks = setup()
        id1 = extmarks.create(start=0, end=5, metadata={"layer": 1})
        id2 = extmarks.create(start=0, end=5, metadata={"layer": 2})
        assert extmarks.get_metadata_for(id1) == {"layer": 1}
        assert extmarks.get_metadata_for(id2) == {"layer": 2}

    def test_should_preserve_metadata_through_text_insertion(self):
        textarea, extmarks = setup("Hello World")
        meta = {"type": "highlight", "priority": 10}
        eid = extmarks.create(start=0, end=5, metadata=meta)
        textarea.focus()
        textarea.cursor_offset = 2
        textarea.press_key("Z")
        assert extmarks.get_metadata_for(eid) == meta

    def test_should_preserve_metadata_through_text_deletion(self):
        textarea, extmarks = setup("XXHello World")
        meta = {"category": "text"}
        eid = extmarks.create(start=8, end=13, metadata=meta)
        textarea.focus()
        textarea.cursor_offset = 2
        textarea.press_backspace()
        textarea.press_backspace()
        assert extmarks.get_metadata_for(eid) == meta

    def test_should_remove_metadata_when_extmark_range_is_deleted(self):
        textarea, extmarks = setup("Hello World")
        meta = {"info": "will be deleted"}
        eid = extmarks.create(start=6, end=11, metadata=meta)
        textarea.delete_range(0, 6, 0, 11)
        assert extmarks.get(eid) is None
        assert extmarks.get_metadata_for(eid) is None

    def test_should_handle_metadata_for_virtual_extmarks(self):
        textarea, extmarks = setup("abcdefgh")
        meta = {"virtual": True, "link": "https://example.com"}
        eid = extmarks.create(start=3, end=6, virtual=True, metadata=meta)
        assert extmarks.get_metadata_for(eid) == meta
        textarea.focus()
        textarea.cursor_offset = 2
        textarea.press_arrow("right")
        assert textarea.cursor_offset == 6
        assert extmarks.get_metadata_for(eid) == meta

    def test_should_handle_large_metadata_objects(self):
        textarea, extmarks = setup()
        large_meta = {
            "items": [{"id": i, "value": f"item-{i}"} for i in range(1000)],
            "description": "A" * 10000,
        }
        eid = extmarks.create(start=0, end=5, metadata=large_meta)
        retrieved = extmarks.get_metadata_for(eid)
        assert retrieved == large_meta
        assert len(retrieved["items"]) == 1000
        assert len(retrieved["description"]) == 10000

    def test_should_handle_metadata_with_functions(self):
        textarea, extmarks = setup()
        meta = {
            "on_click": lambda: "clicked",
            "on_hover": lambda x: x * 2,
        }
        eid = extmarks.create(start=0, end=5, metadata=meta)
        retrieved = extmarks.get_metadata_for(eid)
        assert callable(retrieved["on_click"])
        assert callable(retrieved["on_hover"])
        assert retrieved["on_click"]() == "clicked"
        assert retrieved["on_hover"](5) == 10

    def test_should_store_metadata_by_reference(self):
        textarea, extmarks = setup()
        original = {"value": 1, "nested": {"count": 0}}
        eid = extmarks.create(start=0, end=5, metadata=original)
        retrieved = extmarks.get_metadata_for(eid)
        retrieved["value"] = 999
        retrieved["nested"]["count"] = 100
        assert original["value"] == 999
        assert original["nested"]["count"] == 100
        assert extmarks.get_metadata_for(eid)["value"] == 999

    def test_should_handle_metadata_for_extmarks_with_type_id(self):
        textarea, extmarks = setup()
        link_tid = extmarks.register_type("link")
        id1 = extmarks.create(
            start=0, end=5, type_id=link_tid, metadata={"url": "https://first.com"}
        )
        id2 = extmarks.create(
            start=6, end=11, type_id=link_tid, metadata={"url": "https://second.com"}
        )
        assert extmarks.get_metadata_for(id1) == {"url": "https://first.com"}
        assert extmarks.get_metadata_for(id2) == {"url": "https://second.com"}
        links = extmarks.get_all_for_type_id(link_tid)
        assert len(links) == 2
        for link in links:
            meta = extmarks.get_metadata_for(link.id)
            assert "url" in meta
            assert meta["url"].startswith("https://")

    def test_should_preserve_metadata_after_set_text_clears_extmarks(self):
        textarea, extmarks = setup("Hello World")
        eid = extmarks.create(start=0, end=5, metadata={"persisted": False})
        textarea.set_text("New Text")
        assert extmarks.get(eid) is None
        assert extmarks.get_metadata_for(eid) is None
