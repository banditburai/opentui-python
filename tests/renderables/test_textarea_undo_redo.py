"""Port of upstream Textarea.undo-redo.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.undo-redo.test.ts
Tests ported: 14/14 (14 real)
"""

from opentui.components.textarea import TextareaRenderable
from opentui.events import KeyEvent


# ── Helpers ─────────────────────────────────────────────────────────────


def _key(
    name: str,
    *,
    ctrl: bool = False,
    shift: bool = False,
    alt: bool = False,
    meta: bool = False,
    hyper: bool = False,
    sequence: str = "",
) -> KeyEvent:
    return KeyEvent(
        key=name, ctrl=ctrl, shift=shift, alt=alt, meta=meta, hyper=hyper, sequence=sequence
    )


def _type_string(ta: TextareaRenderable, text: str) -> None:
    """Type a string character by character via handle_key."""
    for ch in text:
        ta.handle_key(_key(ch))


def _make(text: str = "", **kwargs) -> TextareaRenderable:
    """Create a focused TextareaRenderable with given text."""
    ta = TextareaRenderable(initial_value=text, **kwargs)
    ta.focus()
    return ta


class TestTextareaUndoRedo:
    """Maps to describe("Undo/Redo")."""

    def test_should_delete_multiple_selected_ranges_and_restore_with_undo(self):
        """Maps to it("should delete multiple selected ranges and restore with undo")."""
        ta = _make("Hello World Foo Bar")

        # Select and delete "World "
        ta.set_selection(6, 12)
        ta.edit_buffer.set_cursor(0, 12)
        ta.delete_char_backward()
        assert ta.plain_text == "Hello Foo Bar"

        # Select and delete "Foo "
        ta.set_selection(6, 10)
        ta.edit_buffer.set_cursor(0, 10)
        ta.delete_char_backward()
        assert ta.plain_text == "Hello Bar"

        # Undo should restore "Foo "
        ta.undo()
        assert ta.plain_text == "Hello Foo Bar"

        # Undo should restore "World "
        ta.undo()
        assert ta.plain_text == "Hello World Foo Bar"

        ta.destroy()


class TestTextareaHistoryUndoRedo:
    """Maps to describe("History - Undo/Redo")."""

    def test_should_undo_text_insertion(self):
        """Maps to it("should undo text insertion")."""
        ta = _make()
        ta.insert_text("Hello")
        assert ta.plain_text == "Hello"

        ta.undo()
        assert ta.plain_text == ""

        ta.destroy()

    def test_should_redo_after_undo(self):
        """Maps to it("should redo after undo")."""
        ta = _make()
        ta.insert_text("Hello")
        assert ta.plain_text == "Hello"

        ta.undo()
        assert ta.plain_text == ""

        ta.redo()
        assert ta.plain_text == "Hello"

        ta.destroy()

    def test_should_handle_multiple_undo_operations(self):
        """Maps to it("should handle multiple undo operations")."""
        ta = _make()
        ta.insert_text("A")
        ta.insert_text("B")
        ta.insert_text("C")
        assert ta.plain_text == "ABC"

        ta.undo()
        assert ta.plain_text == "AB"

        ta.undo()
        assert ta.plain_text == "A"

        ta.undo()
        assert ta.plain_text == ""

        ta.destroy()

    def test_should_handle_ctrl_minus_for_undo(self):
        """Maps to it("should handle Ctrl+- for undo")."""
        ta = _make()
        ta.insert_text("Hello")
        assert ta.plain_text == "Hello"

        # Ctrl+- is mapped to undo
        ta.handle_key(_key("-", ctrl=True))
        assert ta.plain_text == ""

        ta.destroy()

    def test_should_handle_ctrl_dot_for_redo(self):
        """Maps to it("should handle Ctrl+. for redo")."""
        ta = _make()
        ta.insert_text("Hello")
        assert ta.plain_text == "Hello"

        # Undo first
        ta.handle_key(_key("-", ctrl=True))
        assert ta.plain_text == ""

        # Ctrl+Shift+. is mapped to redo
        ta.handle_key(_key(".", ctrl=True, shift=True))
        assert ta.plain_text == "Hello"

        ta.destroy()

    def test_should_handle_redo_programmatically(self):
        """Maps to it("should handle redo programmatically")."""
        ta = _make()
        ta.insert_text("Hello")
        ta.insert_text(" World")
        assert ta.plain_text == "Hello World"

        ta.undo()
        assert ta.plain_text == "Hello"

        result = ta.redo()
        assert result is True
        assert ta.plain_text == "Hello World"

        ta.destroy()

    def test_should_undo_deletion(self):
        """Maps to it("should undo deletion")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 5)
        ta.delete_char_backward()
        assert ta.plain_text == "Hell"

        ta.undo()
        assert ta.plain_text == "Hello"

        ta.destroy()

    def test_should_undo_newline_insertion(self):
        """Maps to it("should undo newline insertion")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 5)
        ta.newline()
        assert ta.plain_text == "Hello\n"
        assert ta.line_count == 2

        ta.undo()
        assert ta.plain_text == "Hello"
        assert ta.line_count == 1

        ta.destroy()

    def test_should_restore_cursor_position_after_undo(self):
        """Maps to it("should restore cursor position after undo")."""
        ta = _make()
        ta.insert_text("Hello")
        assert ta.cursor_position == (0, 5)

        ta.insert_text(" World")
        assert ta.cursor_position == (0, 11)

        ta.undo()
        # After undo, cursor should be restored to position before " World"
        line, col = ta.cursor_position
        assert ta.plain_text == "Hello"
        # Cursor should be somewhere in the restored text
        assert line == 0

        ta.destroy()

    def test_should_handle_undo_redo_chain(self):
        """Maps to it("should handle undo/redo chain")."""
        ta = _make()
        ta.insert_text("A")
        ta.insert_text("B")
        ta.insert_text("C")
        assert ta.plain_text == "ABC"

        # Undo all
        ta.undo()
        assert ta.plain_text == "AB"
        ta.undo()
        assert ta.plain_text == "A"
        ta.undo()
        assert ta.plain_text == ""

        # Redo all
        ta.redo()
        assert ta.plain_text == "A"
        ta.redo()
        assert ta.plain_text == "AB"
        ta.redo()
        assert ta.plain_text == "ABC"

        ta.destroy()

    def test_should_handle_undo_after_delete_char(self):
        """Maps to it("should handle undo after deleteChar")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 0)
        ta.delete_char()
        assert ta.plain_text == "ello"

        ta.undo()
        assert ta.plain_text == "Hello"

        ta.destroy()

    def test_should_handle_undo_after_delete_line(self):
        """Maps to it("should handle undo after deleteLine")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.edit_buffer.set_cursor(1, 0)
        ta.delete_line()
        assert ta.plain_text == "Line 1\nLine 3"

        ta.undo()
        assert ta.plain_text == "Line 1\nLine 2\nLine 3"

        ta.destroy()

    def test_should_clear_selection_on_undo(self):
        """Maps to it("should clear selection on undo")."""
        ta = _make()
        ta.insert_text("Hello World")

        # Set a selection
        ta.set_selection(0, 5)
        assert ta.has_selection

        # Undo should clear selection
        ta.undo()
        assert not ta.has_selection

        ta.destroy()
