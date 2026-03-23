"""Native edit buffer wrapper."""

from __future__ import annotations

import contextlib
import ctypes
from typing import Any

from ..native import _decode, _nb


class NativeEditBuffer:
    """Wrapper for native edit buffer using nanobind bindings."""

    def __init__(self, encoding: int = 0):
        self._ptr: Any = _nb.edit_buffer.create_edit_buffer(encoding)
        self._text_buffer_ptr: Any = _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)
        self._single_text_mem_id: int | None = None
        self._single_text_bytes: bytes | None = None  # prevent GC while Zig holds pointer
        self._event_listeners: dict[str, list] = {"cursor_changed": [], "content_changed": []}
        self._destroyed = False

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.edit_buffer.destroy_edit_buffer(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> Any:
        return self._ptr

    def insert_text(self, text: str) -> None:
        _nb.edit_buffer.edit_buffer_insert_text(self._ptr, text)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def delete_char(self) -> None:
        _nb.edit_buffer.edit_buffer_delete_char(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def delete_char_backward(self) -> None:
        _nb.edit_buffer.edit_buffer_delete_char_backward(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def set_text(self, text: str) -> None:
        if self._ptr is None:
            raise RuntimeError("EditBuffer is destroyed")
        text_bytes = text.encode("utf-8")
        tb = self._text_buffer_ptr
        if self._single_text_mem_id is not None:
            _nb.text_buffer.text_buffer_replace_mem_buffer(
                tb,
                self._single_text_mem_id,
                text_bytes,
                len(text_bytes),
                False,
            )
        else:
            self._single_text_mem_id = _nb.text_buffer.text_buffer_register_mem_buffer(
                tb,
                text_bytes,
                len(text_bytes),
                False,
            )
        self._single_text_bytes = text_bytes  # prevent GC while Zig holds pointer
        _nb.edit_buffer.edit_buffer_set_text_from_mem(self._ptr, self._single_text_mem_id)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def move_cursor_left(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_left(self._ptr)
        self._emit("cursor_changed")

    def move_cursor_right(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_right(self._ptr)
        self._emit("cursor_changed")

    def move_cursor_up(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_up(self._ptr)
        self._emit("cursor_changed")

    def move_cursor_down(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_down(self._ptr)
        self._emit("cursor_changed")

    def goto_line(self, line: int) -> None:
        _nb.edit_buffer.edit_buffer_goto_line(self._ptr, line)
        self._emit("cursor_changed")

    def can_undo(self) -> bool:
        return _nb.edit_buffer.edit_buffer_can_undo(self._ptr)

    def can_redo(self) -> bool:
        return _nb.edit_buffer.edit_buffer_can_redo(self._ptr)

    def undo(self, max_len: int = 0) -> str:
        if max_len <= 0:
            tb_ptr = _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)
            max_len = _nb.text_buffer.text_buffer_get_byte_size(tb_ptr) + 1
        result = _nb.edit_buffer.edit_buffer_undo(self._ptr, max_len)
        result = _decode(result)
        self._emit("content_changed")
        self._emit("cursor_changed")
        return result

    def redo(self, max_len: int = 0) -> str:
        if max_len <= 0:
            tb_ptr = _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)
            max_len = _nb.text_buffer.text_buffer_get_byte_size(tb_ptr) + 1
        result = _nb.edit_buffer.edit_buffer_redo(self._ptr, max_len)
        result = _decode(result)
        self._emit("content_changed")
        self._emit("cursor_changed")
        return result

    def get_text(self, max_len: int = 0) -> str:
        if max_len <= 0:
            tb_ptr = _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)
            max_len = _nb.text_buffer.text_buffer_get_byte_size(tb_ptr) + 1
        result = _nb.edit_buffer.edit_buffer_get_text(self._ptr, max_len)
        return _decode(result)

    def set_cursor(self, line: int, col: int) -> None:
        _nb.edit_buffer.edit_buffer_set_cursor(self._ptr, line, col)
        self._emit("cursor_changed")

    def get_cursor_position(self) -> tuple[int, int]:
        # The native API writes (line, col) as two consecutive int32 values
        # into the first capsule pointer (8 bytes total).
        ctypes.pythonapi.PyCapsule_New.restype = ctypes.py_object
        ctypes.pythonapi.PyCapsule_New.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_void_p,
        ]
        buf = (ctypes.c_int32 * 2)(0, 0)
        dummy = ctypes.c_int64(0)
        buf_cap = ctypes.pythonapi.PyCapsule_New(ctypes.addressof(buf), b"nb_handle", None)
        dummy_cap = ctypes.pythonapi.PyCapsule_New(ctypes.addressof(dummy), b"nb_handle", None)
        _nb.edit_buffer.edit_buffer_get_cursor_position(self._ptr, buf_cap, dummy_cap)
        return (buf[0], buf[1])

    def delete_range(self, start_line: int, start_col: int, end_line: int, end_col: int) -> None:
        _nb.edit_buffer.edit_buffer_delete_range(
            self._ptr, start_line, start_col, end_line, end_col
        )
        self._emit("content_changed")
        self._emit("cursor_changed")

    def newline(self) -> None:
        _nb.edit_buffer.edit_buffer_new_line(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def destroy(self) -> None:
        self._destroyed = True
        self._event_listeners = {"cursor_changed": [], "content_changed": []}
        if self._ptr:
            _nb.edit_buffer.destroy_edit_buffer(self._ptr)
            self._ptr = None

    # -- Event system --

    def on(self, event: str, callback) -> None:
        if event in self._event_listeners:
            self._event_listeners[event].append(callback)

    def off(self, event: str, callback) -> None:
        if event in self._event_listeners:
            with contextlib.suppress(ValueError):
                self._event_listeners[event].remove(callback)

    def _emit(self, event: str, *args) -> None:
        if self._destroyed:
            return
        for listener in self._event_listeners.get(event, []):
            listener(*args)

    # -- Python-level wrapper methods --

    def clear(self) -> None:
        self.set_text("")
        self.set_cursor(0, 0)

    def move_to_line_start(self) -> None:
        line, _ = self.get_cursor_position()
        self.set_cursor(line, 0)

    def move_to_line_end(self) -> None:
        line, _ = self.get_cursor_position()
        text = self.get_text()
        lines = text.split("\n")
        if line < len(lines):
            self.set_cursor(line, len(lines[line]))
        else:
            self.set_cursor(line, 0)

    def delete_line(self, line: int | None = None) -> None:
        if line is None:
            line, _ = self.get_cursor_position()
        text = self.get_text()
        lines = text.split("\n")
        if line < 0 or line >= len(lines):
            return
        if len(lines) == 1:
            self.set_text("")
            self.set_cursor(0, 0)
        elif line == len(lines) - 1:
            self.delete_range(line - 1, len(lines[line - 1]), line, len(lines[line]))
            self.set_cursor(line - 1 if line > 0 else 0, 0)
        else:
            self.delete_range(line, 0, line + 1, 0)
            self.set_cursor(min(line, len(lines) - 2), 0)

    def delete_to_line_end(self) -> None:
        line, col = self.get_cursor_position()
        text = self.get_text()
        lines = text.split("\n")
        if line < len(lines):
            line_len = len(lines[line])
            if col < line_len:
                self.delete_range(line, col, line, line_len)

    def get_line_count(self) -> int:
        text = self.get_text()
        if not text:
            return 1
        return text.count("\n") + 1

    def get_line(self, line: int) -> str:
        text = self.get_text()
        lines = text.split("\n")
        if 0 <= line < len(lines):
            return lines[line]
        return ""

    def get_line_length(self, line: int) -> int:
        return len(self.get_line(line))

    def get_next_word_boundary(self, line: int, col: int) -> tuple[int, int]:
        text = self.get_text()
        lines = text.split("\n")
        if line >= len(lines):
            return (line, col)

        current_line = lines[line]
        pos = col

        while (
            pos < len(current_line)
            and not current_line[pos].isspace()
            and current_line[pos].isalnum()
        ):
            pos += 1
        while pos < len(current_line) and (
            current_line[pos].isspace() or not current_line[pos].isalnum()
        ):
            pos += 1

        if pos < len(current_line):
            return (line, pos)
        if line + 1 < len(lines):
            return (line + 1, 0)
        return (line, len(current_line))

    def get_previous_word_boundary(self, line: int, col: int) -> tuple[int, int]:
        text = self.get_text()
        lines = text.split("\n")
        if line >= len(lines):
            return (line, col)

        current_line = lines[line]
        pos = col

        if pos <= 0:
            if line > 0:
                prev_line = lines[line - 1]
                return (line - 1, len(prev_line))
            return (0, 0)

        pos -= 1
        while pos > 0 and (current_line[pos].isspace() or not current_line[pos].isalnum()):
            pos -= 1
        while pos > 0 and current_line[pos - 1].isalnum():
            pos -= 1

        return (line, pos)

    def offset_to_position(self, offset: int) -> tuple[int, int] | None:
        text = self.get_text()
        if offset < 0 or offset > len(text):
            return None
        prefix = text[:offset]
        line = prefix.count("\n")
        last_nl = prefix.rfind("\n")
        col = offset - (last_nl + 1)
        return (line, col)

    def position_to_offset(self, line: int, col: int) -> int:
        text = self.get_text()
        lines = text.split("\n")
        if line < 0 or line >= len(lines):
            return -1
        offset = sum(len(lines[i]) + 1 for i in range(line)) + col
        return offset

    def get_line_start_offset(self, line: int) -> int:
        text = self.get_text()
        lines = text.split("\n")
        if line < 0 or line >= len(lines):
            return -1
        return sum(len(lines[i]) + 1 for i in range(line))

    def get_eol(self, line: int) -> int:
        text = self.get_text()
        lines = text.split("\n")
        if 0 <= line < len(lines):
            return len(lines[line])
        return 0

    def replace_text(
        self, start_line: int, start_col: int, end_line: int, end_col: int, text: str
    ) -> None:
        self.delete_range(start_line, start_col, end_line, end_col)
        self.set_cursor(start_line, start_col)
        self.insert_text(text)

    # -- Native-backed methods (use Zig implementation instead of Python) --

    def get_text_buffer_ptr(self) -> Any:
        return _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)

    def set_cursor_by_offset(self, offset: int) -> None:
        _nb.edit_buffer.edit_buffer_set_cursor_by_offset(self._ptr, offset)
        self._emit("cursor_changed")

    def get_cursor_native(self) -> tuple[int, int]:
        return _nb.edit_buffer.edit_buffer_get_cursor(self._ptr)

    def get_next_word_boundary_native(self) -> tuple[int, int, int]:
        return _nb.edit_buffer.edit_buffer_get_next_word_boundary(self._ptr)

    def get_prev_word_boundary_native(self) -> tuple[int, int, int]:
        return _nb.edit_buffer.edit_buffer_get_prev_word_boundary(self._ptr)

    def get_eol_native(self) -> tuple[int, int, int]:
        return _nb.edit_buffer.edit_buffer_get_eol(self._ptr)

    def offset_to_position_native(self, offset: int) -> tuple[int, int, int] | None:
        result = _nb.edit_buffer.edit_buffer_offset_to_position(self._ptr, offset)
        return result

    def position_to_offset_native(self, row: int, col: int) -> int:
        return _nb.edit_buffer.edit_buffer_position_to_offset(self._ptr, row, col)

    def get_line_start_offset_native(self, row: int) -> int:
        return _nb.edit_buffer.edit_buffer_get_line_start_offset(self._ptr, row)

    def get_text_range_native(self, start_offset: int, end_offset: int, max_len: int = 0) -> str:
        if max_len <= 0:
            max_len = (end_offset - start_offset) + 1
        result = _nb.edit_buffer.edit_buffer_get_text_range(
            self._ptr, start_offset, end_offset, max_len
        )
        return _decode(result)

    def get_text_range_by_coords_native(
        self, start_row: int, start_col: int, end_row: int, end_col: int, max_len: int = 65_536
    ) -> str:
        result = _nb.edit_buffer.edit_buffer_get_text_range_by_coords(
            self._ptr, start_row, start_col, end_row, end_col, max_len
        )
        return _decode(result)

    def replace_text_native(self, text: str) -> None:
        _nb.edit_buffer.edit_buffer_replace_text(self._ptr, text)
        self._emit("content_changed")

    def clear_native(self) -> None:
        _nb.edit_buffer.edit_buffer_clear(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def clear_history(self) -> None:
        _nb.edit_buffer.edit_buffer_clear_history(self._ptr)

    def delete_line_native(self) -> None:
        _nb.edit_buffer.edit_buffer_delete_line(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def insert_char(self, ch: str) -> None:
        _nb.edit_buffer.edit_buffer_insert_char(self._ptr, ch)
        self._emit("content_changed")
        self._emit("cursor_changed")
