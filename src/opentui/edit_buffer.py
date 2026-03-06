"""EditBuffer and EditorView classes for text editing."""

from __future__ import annotations

from . import ffi
from .ffi import c_uint8, c_uint32, get_library


class EditBuffer:
    """Wrapper around native EditBuffer for text editing with cursor."""

    def __init__(self, ptr: int, lib: ffi.OpenTUILibrary | ffi.NanobindLibrary):
        self._ptr = ptr
        self._lib = lib

    def insert_text(self, text: str) -> None:
        """Insert text at cursor position."""
        if isinstance(text, str):
            text_bytes = text.encode("utf-8")
        else:
            text_bytes = text

        if hasattr(self._lib, "editBufferInsertText"):
            self._lib.editBufferInsertText(self._ptr, text_bytes, len(text_bytes))

    def get_text(self) -> str:
        """Get the current text content."""
        if hasattr(self._lib, "editBufferGetText"):
            buf = b"\x00" * 65536
            length = self._lib.editBufferGetText(self._ptr, buf, len(buf))
            return buf[:length].decode("utf-8", errors="replace")
        return ""

    def set_text(self, text: str) -> None:
        """Set the text content."""
        if hasattr(self._lib, "editBufferSetText"):
            if isinstance(text, str):
                text_bytes = text.encode("utf-8")
            else:
                text_bytes = text
            self._lib.editBufferSetText(self._ptr, text_bytes, len(text_bytes))

    def delete_char(self) -> None:
        """Delete character at cursor."""
        if hasattr(self._lib, "editBufferDeleteChar"):
            self._lib.editBufferDeleteChar(self._ptr)

    def delete_char_backward(self) -> None:
        """Delete character before cursor (backspace)."""
        if hasattr(self._lib, "editBufferDeleteCharBackward"):
            self._lib.editBufferDeleteCharBackward(self._ptr)

    def delete_range(self, start_line: int, start_col: int, end_line: int, end_col: int) -> None:
        """Delete a range of text."""
        if hasattr(self._lib, "editBufferDeleteRange"):
            self._lib.editBufferDeleteRange(
                self._ptr,
                c_uint32(start_line),
                c_uint32(start_col),
                c_uint32(end_line),
                c_uint32(end_col),
            )

    def newline(self) -> None:
        """Insert a newline at cursor."""
        if hasattr(self._lib, "editBufferNewLine"):
            self._lib.editBufferNewLine(self._ptr)

    def move_cursor_left(self) -> None:
        """Move cursor left."""
        if hasattr(self._lib, "editBufferMoveCursorLeft"):
            self._lib.editBufferMoveCursorLeft(self._ptr)

    def move_cursor_right(self) -> None:
        """Move cursor right."""
        if hasattr(self._lib, "editBufferMoveCursorRight"):
            self._lib.editBufferMoveCursorRight(self._ptr)

    def move_cursor_up(self) -> None:
        """Move cursor up."""
        if hasattr(self._lib, "editBufferMoveCursorUp"):
            self._lib.editBufferMoveCursorUp(self._ptr)

    def move_cursor_down(self) -> None:
        """Move cursor down."""
        if hasattr(self._lib, "editBufferMoveCursorDown"):
            self._lib.editBufferMoveCursorDown(self._ptr)

    def goto_line(self, line: int) -> None:
        """Go to a specific line."""
        if hasattr(self._lib, "editBufferGotoLine"):
            self._lib.editBufferGotoLine(self._ptr, c_uint32(line))

    def set_cursor(self, line: int, col: int) -> None:
        """Set cursor position."""
        if hasattr(self._lib, "editBufferSetCursor"):
            self._lib.editBufferSetCursor(self._ptr, c_uint32(line), c_uint32(col))

    def get_cursor_position(self) -> tuple[int, int]:
        """Get current cursor position as (line, col)."""
        if hasattr(self._lib, "editBufferGetCursorPosition"):
            import ctypes

            line = ctypes.c_uint32()
            col = ctypes.c_uint32()
            self._lib.editBufferGetCursorPosition(self._ptr, ctypes.byref(line), ctypes.byref(col))
            return (line.value, col.value)
        return (0, 0)

    def can_undo(self) -> bool:
        """Check if undo is available."""
        if hasattr(self._lib, "editBufferCanUndo"):
            return self._lib.editBufferCanUndo(self._ptr)
        return False

    def can_redo(self) -> bool:
        """Check if redo is available."""
        if hasattr(self._lib, "editBufferCanRedo"):
            return self._lib.editBufferCanRedo(self._ptr)
        return False

    def undo(self) -> bool:
        """Undo last action."""
        if hasattr(self._lib, "editBufferUndo"):

            buf = b"\x00" * 1024
            length = self._lib.editBufferUndo(self._ptr, buf, len(buf))
            return length > 0
        return False

    def redo(self) -> bool:
        """Redo last undone action."""
        if hasattr(self._lib, "editBufferRedo"):

            buf = b"\x00" * 1024
            length = self._lib.editBufferRedo(self._ptr, buf, len(buf))
            return length > 0
        return False

    def destroy(self) -> None:
        """Destroy the edit buffer and free resources."""
        if self._ptr and hasattr(self._lib, "destroyEditBuffer"):
            self._lib.destroyEditBuffer(self._ptr)
            self._ptr = None

    @property
    def ptr(self) -> int | None:
        """Get the raw pointer."""
        return self._ptr


class EditorView:
    """View for editing text with viewport control."""

    def __init__(self, edit_buffer: EditBuffer, width: int, height: int):
        self._edit_buffer = edit_buffer
        self._lib = edit_buffer._lib

        if hasattr(self._lib, "createEditorView"):
            ptr = self._lib.createEditorView(edit_buffer.ptr, c_uint32(width), c_uint32(height))
            self._ptr = ptr
        else:
            self._ptr = None

    def set_viewport_size(self, width: int, height: int) -> None:
        """Set the viewport dimensions."""
        if self._ptr and hasattr(self._lib, "editorViewSetViewportSize"):
            self._lib.editorViewSetViewportSize(self._ptr, c_uint32(width), c_uint32(height))

    def set_viewport(
        self, scroll_x: int, scroll_y: int, width: int, height: int, smooth: bool = False
    ) -> None:
        """Set the viewport position and size."""
        if self._ptr and hasattr(self._lib, "editorViewSetViewport"):
            self._lib.editorViewSetViewport(
                self._ptr,
                c_uint32(scroll_x),
                c_uint32(scroll_y),
                c_uint32(width),
                c_uint32(height),
                smooth,
            )

    def get_viewport(self) -> tuple[int, int, int, int]:
        """Get the viewport as (scroll_x, scroll_y, width, height)."""
        if self._ptr and hasattr(self._lib, "editorViewGetViewport"):
            import ctypes

            scroll_x = ctypes.c_uint32()
            scroll_y = ctypes.c_uint32()
            width = ctypes.c_uint32()
            height = ctypes.c_uint32()
            self._lib.editorViewGetViewport(
                self._ptr,
                ctypes.byref(scroll_x),
                ctypes.byref(scroll_y),
                ctypes.byref(width),
                ctypes.byref(height),
            )
            return (scroll_x.value, scroll_y.value, width.value, height.value)
        return (0, 0, 80, 24)

    def destroy(self) -> None:
        """Destroy the editor view and free resources."""
        if self._ptr and hasattr(self._lib, "destroyEditorView"):
            self._lib.destroyEditorView(self._ptr)
            self._ptr = None

    @property
    def ptr(self) -> int | None:
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
    lib = get_library()

    if hasattr(lib, "createEditBuffer"):
        ptr = lib.createEditBuffer(c_uint8(default_attributes))
        return EditBuffer(ptr, lib)

    raise RuntimeError("createEditBuffer not available")


__all__ = [
    "EditBuffer",
    "EditorView",
    "create_edit_buffer",
]
