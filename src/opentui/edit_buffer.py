"""EditBuffer and EditorView classes for text editing using nanobind."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ffi import NanobindLibrary


class EditBuffer:
    """Wrapper around native EditBuffer for text editing with cursor."""

    def __init__(self, ptr: Any, native: NanobindLibrary):
        self._ptr = ptr
        self._native = native

    def insert_text(self, text: str) -> None:
        """Insert text at cursor position."""
        if isinstance(text, str):
            text_bytes = text.encode("utf-8")
        else:
            text_bytes = text
        self._native.edit_buffer.insert_text(self._ptr, text_bytes, len(text_bytes))

    def get_text(self) -> str:
        """Get the current text content."""
        buf_size = 4096
        while True:
            buf = b"\x00" * buf_size
            length = self._native.edit_buffer.get_text(self._ptr, buf, len(buf))
            if length < buf_size:
                return buf[:length].decode("utf-8", errors="replace")
            # Buffer was too small, double and retry
            buf_size *= 2

    def set_text(self, text: str) -> None:
        """Set the text content."""
        if isinstance(text, str):
            text_bytes = text.encode("utf-8")
        else:
            text_bytes = text
        self._native.edit_buffer.set_text(self._ptr, text_bytes, len(text_bytes))

    def delete_char(self) -> None:
        """Delete character at cursor."""
        self._native.edit_buffer.delete_char(self._ptr)

    def delete_char_backward(self) -> None:
        """Delete character before cursor (backspace)."""
        self._native.edit_buffer.delete_char_backward(self._ptr)

    def delete_range(self, start_line: int, start_col: int, end_line: int, end_col: int) -> None:
        """Delete a range of text."""
        self._native.edit_buffer.delete_range(self._ptr, start_line, start_col, end_line, end_col)

    def newline(self) -> None:
        """Insert a newline at cursor."""
        self._native.edit_buffer.newline(self._ptr)

    def move_cursor_left(self) -> None:
        """Move cursor left."""
        self._native.edit_buffer.move_cursor_left(self._ptr)

    def move_cursor_right(self) -> None:
        """Move cursor right."""
        self._native.edit_buffer.move_cursor_right(self._ptr)

    def move_cursor_up(self) -> None:
        """Move cursor up."""
        self._native.edit_buffer.move_cursor_up(self._ptr)

    def move_cursor_down(self) -> None:
        """Move cursor down."""
        self._native.edit_buffer.move_cursor_down(self._ptr)

    def goto_line(self, line: int) -> None:
        """Go to a specific line."""
        self._native.edit_buffer.goto_line(self._ptr, line)

    def set_cursor(self, line: int, col: int) -> None:
        """Set cursor position."""
        self._native.edit_buffer.set_cursor(self._ptr, line, col)

    def get_cursor_position(self) -> tuple[int, int]:
        """Get current cursor position as (line, col)."""
        result = self._native.edit_buffer.get_cursor_position(self._ptr)
        return (result[0], result[1])

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self._native.edit_buffer.can_undo(self._ptr)

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self._native.edit_buffer.can_redo(self._ptr)

    def undo(self) -> bool:
        """Undo last action."""
        buf = b"\x00" * 1024
        length = self._native.edit_buffer.undo(self._ptr, buf, len(buf))
        return length > 0

    def redo(self) -> bool:
        """Redo last undone action."""
        buf = b"\x00" * 1024
        length = self._native.edit_buffer.redo(self._ptr, buf, len(buf))
        return length > 0

    def destroy(self) -> None:
        """Destroy the edit buffer and free resources."""
        if self._ptr:
            self._native.edit_buffer.destroy(self._ptr)
            self._ptr = None

    @property
    def ptr(self) -> Any:
        """Get the raw pointer."""
        return self._ptr


class EditorView:
    """View for editing text with viewport control."""

    def __init__(self, edit_buffer: EditBuffer, width: int, height: int):
        self._edit_buffer = edit_buffer
        self._native = edit_buffer._native
        self._valid = False

        ptr = self._native.editor_view.create(edit_buffer.ptr, width, height)
        self._ptr = ptr
        self._valid = True

    def set_viewport_size(self, width: int, height: int) -> None:
        """Set the viewport dimensions."""
        if self._ptr:
            self._native.editor_view.set_viewport_size(self._ptr, width, height)

    def set_viewport(
        self, scroll_x: int, scroll_y: int, width: int, height: int, smooth: bool = False
    ) -> None:
        """Set the viewport position and size."""
        if self._ptr:
            self._native.editor_view.set_viewport(
                self._ptr, scroll_x, scroll_y, width, height, smooth
            )

    def get_viewport(self) -> tuple[int, int, int, int]:
        """Get the viewport as (scroll_x, scroll_y, width, height)."""
        if self._ptr:
            result = self._native.editor_view.get_viewport(self._ptr)
            return (result[0], result[1], result[2], result[3])
        return (0, 0, 80, 24)

    def destroy(self) -> None:
        """Destroy the editor view and free resources."""
        if self._ptr:
            self._native.editor_view.destroy(self._ptr)
            self._ptr = None

    @property
    def ptr(self) -> Any:
        """Get the raw pointer."""
        return self._ptr

    @property
    def edit_buffer(self) -> EditBuffer:
        """Get the associated edit buffer."""
        return self._edit_buffer


def create_edit_buffer(default_attributes: int = 0) -> EditBuffer:
    """Create a new EditBuffer.

    Args:
        default_attributes: Default text attributes

    Returns:
        EditBuffer instance
    """
    from .ffi import get_native

    native = get_native()
    if native is None:
        raise RuntimeError("Native bindings not available")

    ptr = native.edit_buffer.create(default_attributes)
    return EditBuffer(ptr, native)


__all__ = [
    "EditBuffer",
    "EditorView",
    "create_edit_buffer",
]
