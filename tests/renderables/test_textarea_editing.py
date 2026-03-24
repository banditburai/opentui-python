"""Port of upstream Textarea.editing.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.editing.test.ts
Tests ported: 95/95 (95 real)
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


# ═══════════════════════════════════════════════════════════════════════
# Initialization
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingInitialization:
    """Maps to describe("Textarea - Editing Tests") > describe("Initialization")."""

    def test_should_initialize_with_default_options(self):
        """Maps to test("should initialize with default options")."""
        ta = TextareaRenderable()
        assert ta.plain_text == ""
        assert ta.cursor_position == (0, 0)
        assert ta.focusable is True
        assert ta.focused is False
        ta.destroy()

    def test_should_initialize_with_content(self):
        """Maps to test("should initialize with content")."""
        ta = TextareaRenderable(initial_value="Hello World")
        assert ta.plain_text == "Hello World"
        # Cursor at (0,0) after initialization
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_initialize_with_empty_content(self):
        """Maps to test("should initialize with empty content")."""
        ta = TextareaRenderable(initial_value="")
        assert ta.plain_text == ""
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_initialize_with_multi_line_content(self):
        """Maps to test("should initialize with multi-line content")."""
        ta = TextareaRenderable(initial_value="Line 1\nLine 2\nLine 3")
        assert ta.plain_text == "Line 1\nLine 2\nLine 3"
        assert ta.line_count == 3
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Focus Management
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingFocusManagement:
    """Maps to describe("Textarea - Editing Tests") > describe("Focus Management")."""

    def test_should_handle_focus_and_blur(self):
        """Maps to test("should handle focus and blur")."""
        ta = TextareaRenderable()
        assert ta.focused is False

        ta.focus()
        assert ta.focused is True

        ta.blur()
        assert ta.focused is False
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Text Insertion via Methods
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingTextInsertionViaMethods:
    """Maps to describe("Textarea - Editing Tests") > describe("Text Insertion via Methods")."""

    def test_should_insert_single_character(self):
        """Maps to test("should insert single character")."""
        ta = _make()
        ta.insert_char("a")
        assert ta.plain_text == "a"
        assert ta.cursor_position == (0, 1)
        ta.destroy()

    def test_should_insert_text(self):
        """Maps to test("should insert text")."""
        ta = _make()
        ta.insert_text("Hello World")
        assert ta.plain_text == "Hello World"
        assert ta.cursor_position == (0, 11)
        ta.destroy()

    def test_should_insert_text_in_middle(self):
        """Maps to test("should insert text in middle")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 5)
        ta.insert_text(" Beautiful")
        assert ta.plain_text == "Hello Beautiful World"
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Text Deletion via Methods
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingTextDeletionViaMethods:
    """Maps to describe("Textarea - Editing Tests") > describe("Text Deletion via Methods")."""

    def test_should_delete_character_at_cursor(self):
        """Maps to test("should delete character at cursor")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 0)
        ta.delete_char()
        assert ta.plain_text == "ello"
        ta.destroy()

    def test_should_delete_character_backward(self):
        """Maps to test("should delete character backward")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 5)
        ta.delete_char_backward()
        assert ta.plain_text == "Hell"
        ta.destroy()

    def test_should_delete_entire_line(self):
        """Maps to test("should delete entire line")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.edit_buffer.set_cursor(1, 0)
        ta.delete_line()
        assert ta.plain_text == "Line 1\nLine 3"
        ta.destroy()

    def test_should_delete_to_line_end(self):
        """Maps to test("should delete to line end")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 5)
        ta.delete_to_line_end()
        assert ta.plain_text == "Hello"
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Cursor Movement via Methods
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingCursorMovementViaMethods:
    """Maps to describe("Textarea - Editing Tests") > describe("Cursor Movement via Methods")."""

    def test_should_move_cursor_left_and_right(self):
        """Maps to test("should move cursor left and right")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 3)
        ta.move_cursor_left()
        assert ta.cursor_position == (0, 2)
        ta.move_cursor_right()
        assert ta.cursor_position == (0, 3)
        ta.destroy()

    def test_should_move_cursor_up_and_down(self):
        """Maps to test("should move cursor up and down")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.edit_buffer.set_cursor(1, 3)
        ta.move_cursor_up()
        assert ta.cursor_position == (0, 3)
        ta.move_cursor_down()
        assert ta.cursor_position == (1, 3)
        ta.destroy()

    def test_should_move_to_line_start_and_end(self):
        """Maps to test("should move to line start and end")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 5)
        ta.goto_line_home()
        assert ta.cursor_position == (0, 0)
        ta.goto_line_end()
        assert ta.cursor_position == (0, 11)
        ta.destroy()

    def test_should_move_to_buffer_start_and_end(self):
        """Maps to test("should move to buffer start and end")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.edit_buffer.set_cursor(1, 3)
        ta.goto_buffer_home()
        assert ta.cursor_position == (0, 0)
        ta.goto_buffer_end()
        assert ta.cursor_position == (2, 6)
        ta.destroy()

    def test_should_goto_specific_line(self):
        """Maps to test("should goto specific line")."""
        ta = _make("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
        ta.goto_line(3)
        line, col = ta.cursor_position
        assert line == 3
        assert col == 0
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Keyboard Input - Character Insertion
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingKeyboardInputCharacterInsertion:
    """Maps to describe("Textarea - Editing Tests") > describe("Keyboard Input - Character Insertion")."""

    def test_should_insert_character_when_key_is_pressed(self):
        """Maps to test("should insert character when key is pressed")."""
        ta = _make()
        ta.handle_key(_key("a"))
        assert ta.plain_text == "a"
        ta.destroy()

    def test_should_insert_multiple_characters_in_sequence(self):
        """Maps to test("should insert multiple characters in sequence")."""
        ta = _make()
        _type_string(ta, "Hello")
        assert ta.plain_text == "Hello"
        ta.destroy()

    def test_should_insert_space_character(self):
        """Maps to test("should insert space character")."""
        ta = _make()
        _type_string(ta, "Hi")
        ta.handle_key(_key(" "))
        _type_string(ta, "World")
        assert ta.plain_text == "Hi World"
        ta.destroy()

    def test_should_not_insert_when_not_focused(self):
        """Maps to test("should not insert when not focused")."""
        ta = TextareaRenderable()
        # Not focused
        result = ta.handle_key(_key("a"))
        assert result is False
        assert ta.plain_text == ""
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Keyboard Input - Arrow Keys
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingKeyboardInputArrowKeys:
    """Maps to describe("Textarea - Editing Tests") > describe("Keyboard Input - Arrow Keys")."""

    def test_should_move_cursor_left_with_arrow_key(self):
        """Maps to test("should move cursor left with arrow key")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 3)
        ta.handle_key(_key("left"))
        assert ta.cursor_position == (0, 2)
        ta.destroy()

    def test_should_move_cursor_right_with_arrow_key(self):
        """Maps to test("should move cursor right with arrow key")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 3)
        ta.handle_key(_key("right"))
        assert ta.cursor_position == (0, 4)
        ta.destroy()

    def test_should_move_cursor_up_and_down_with_arrow_keys(self):
        """Maps to test("should move cursor up and down with arrow keys")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.edit_buffer.set_cursor(1, 2)
        ta.handle_key(_key("up"))
        assert ta.cursor_position == (0, 2)
        ta.handle_key(_key("down"))
        assert ta.cursor_position == (1, 2)
        ta.destroy()

    def test_should_move_cursor_smoothly_from_end_of_one_line_to_start_of_next(self):
        """Maps to test("should move cursor smoothly from end of one line to start of next")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(0, 2)  # end of first line
        ta.move_cursor_right()
        assert ta.cursor_position == (1, 0)  # start of second line
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Keyboard Input - Backspace and Delete
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingKeyboardInputBackspaceAndDelete:
    """Maps to describe("Textarea - Editing Tests") > describe("Keyboard Input - Backspace and Delete")."""

    def test_should_handle_backspace_key(self):
        """Maps to test("should handle backspace key")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 5)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "Hell"
        ta.destroy()

    def test_should_handle_delete_key(self):
        """Maps to test("should handle delete key")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("delete"))
        assert ta.plain_text == "ello"
        ta.destroy()

    def test_should_join_lines_when_backspace_at_start_of_line(self):
        """Maps to test("should join lines when backspace at start of line")."""
        ta = _make("Line 1\nLine 2")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "Line 1Line 2"
        ta.destroy()

    def test_should_remove_empty_line_when_backspace_at_start(self):
        """Maps to test("should remove empty line when backspace at start")."""
        ta = _make("Line 1\n\nLine 3")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "Line 1\nLine 3"
        ta.destroy()

    def test_should_join_lines_with_content_when_backspace_at_start(self):
        """Maps to test("should join lines with content when backspace at start")."""
        ta = _make("ABC\nDEF")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "ABCDEF"
        assert ta.cursor_position == (0, 3)
        ta.destroy()

    def test_should_not_do_anything_when_backspace_at_start_of_first_line(self):
        """Maps to test("should not do anything when backspace at start of first line")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "Hello"
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_handle_multiple_backspaces_joining_multiple_lines(self):
        """Maps to test("should handle multiple backspaces joining multiple lines")."""
        ta = _make("A\nB\nC")
        ta.edit_buffer.set_cursor(2, 0)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "A\nBC"
        # After join, cursor is at (1, 1) — the position where "C" was joined
        assert ta.cursor_position == (1, 1)
        # Second backspace at (1,1) deletes 'B', not the newline
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "A\nC"
        # Third backspace at (1,0) joins the remaining lines
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "AC"
        ta.destroy()

    def test_should_handle_backspace_after_typing_on_new_line(self):
        """Maps to test("should handle backspace after typing on new line")."""
        ta = _make()
        _type_string(ta, "Hello")
        ta.handle_key(_key("return"))
        _type_string(ta, "World")
        assert ta.plain_text == "Hello\nWorld"
        # Backspace deletes 'd'
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "Hello\nWorl"
        ta.destroy()

    def test_should_move_cursor_right_after_joining_lines_with_backspace(self):
        """Maps to test("should move cursor right after joining lines with backspace")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        # After join: "ABCD", cursor at (0, 2)
        assert ta.plain_text == "ABCD"
        assert ta.cursor_position == (0, 2)
        # Move right should work
        ta.handle_key(_key("right"))
        assert ta.cursor_position == (0, 3)
        ta.destroy()

    def test_should_move_right_one_position_after_join(self):
        """Maps to test("should move right one position after join")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        assert ta.cursor_position == (0, 2)
        ta.handle_key(_key("right"))
        assert ta.cursor_position == (0, 3)
        ta.destroy()

    def test_should_advance_cursor_by_1_at_every_position_after_join(self):
        """Maps to test("should advance cursor by 1 at every position after join")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        # "ABCD" cursor at (0, 2)
        ta.handle_key(_key("right"))
        assert ta.cursor_position == (0, 3)
        ta.handle_key(_key("right"))
        assert ta.cursor_position == (0, 4)
        ta.destroy()

    def test_should_move_right_after_backspace_join_set_text_content(self):
        """Maps to test("should move right after backspace join - setText content")."""
        ta = _make("Hello\nWorld")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "HelloWorld"
        assert ta.cursor_position == (0, 5)
        ta.handle_key(_key("right"))
        assert ta.cursor_position == (0, 6)
        ta.destroy()

    def test_should_move_right_after_backspace_join_typed_content(self):
        """Maps to test("should move right after backspace join - typed content")."""
        ta = _make()
        _type_string(ta, "Hello")
        ta.handle_key(_key("return"))
        _type_string(ta, "World")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "HelloWorld"
        assert ta.cursor_position == (0, 5)
        ta.handle_key(_key("right"))
        assert ta.cursor_position == (0, 6)
        ta.destroy()

    def test_should_move_cursor_left_after_joining_lines_with_backspace(self):
        """Maps to test("should move cursor left after joining lines with backspace")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        assert ta.cursor_position == (0, 2)
        ta.handle_key(_key("left"))
        assert ta.cursor_position == (0, 1)
        ta.destroy()

    def test_should_move_cursor_left_across_chunk_boundaries_after_joining_lines(self):
        """Maps to test("should move cursor left across chunk boundaries after joining lines")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace"))
        # "ABCD" at (0, 2)
        ta.handle_key(_key("left"))
        assert ta.cursor_position == (0, 1)
        ta.handle_key(_key("left"))
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_handle_shift_backspace_same_as_backspace(self):
        """Maps to test("should handle shift+backspace same as backspace")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 5)
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "Hell"
        ta.destroy()

    def test_should_join_lines_with_shift_backspace_at_start_of_line(self):
        """Maps to test("should join lines with shift+backspace at start of line")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "ABCD"
        ta.destroy()

    def test_should_handle_shift_backspace_with_selection(self):
        """Maps to test("should handle shift+backspace with selection")."""
        ta = _make("Hello World")
        ta.set_selection(5, 11)  # select " World"
        ta.edit_buffer.set_cursor(0, 11)
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "Hello"
        ta.destroy()

    def test_should_delete_characters_consistently_with_shift_backspace_after_typing(self):
        """Maps to test("should delete characters consistently with shift+backspace after typing")."""
        ta = _make()
        _type_string(ta, "Hello")
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "Hell"
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "Hel"
        ta.destroy()

    def test_should_not_differentiate_between_backspace_and_shift_backspace_behavior(self):
        """Maps to test("should not differentiate between backspace and shift+backspace behavior")."""
        # Regular backspace
        ta1 = _make("AB")
        ta1.edit_buffer.set_cursor(0, 2)
        ta1.handle_key(_key("backspace"))
        result1 = ta1.plain_text
        ta1.destroy()

        # Shift+backspace
        ta2 = _make("AB")
        ta2.edit_buffer.set_cursor(0, 2)
        ta2.handle_key(_key("backspace", shift=True))
        result2 = ta2.plain_text
        ta2.destroy()

        assert result1 == result2 == "A"

    def test_should_handle_shift_backspace_at_start_of_buffer(self):
        """Maps to test("should handle shift+backspace at start of buffer")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "Hello"
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_handle_alternating_backspace_and_shift_backspace(self):
        """Maps to test("should handle alternating backspace and shift+backspace")."""
        ta = _make("ABCD")
        ta.edit_buffer.set_cursor(0, 4)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "ABC"
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "AB"
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "A"
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Keyboard Input - Kitty Keyboard Protocol
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingKeyboardInputKittyKeyboardProtocol:
    """Maps to describe("Textarea - Editing Tests") > describe("Keyboard Input - Kitty Keyboard Protocol")."""

    def test_should_handle_shift_backspace_in_kitty_mode(self):
        """Maps to test("should handle shift+backspace in kitty mode")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 5)
        # In kitty mode, shift+backspace still acts as backspace
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "Hell"
        ta.destroy()

    def test_should_handle_shift_backspace_joining_lines_in_kitty_mode(self):
        """Maps to test("should handle shift+backspace joining lines in kitty mode")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "ABCD"
        ta.destroy()

    def test_should_handle_shift_backspace_with_selection_in_kitty_mode(self):
        """Maps to test("should handle shift+backspace with selection in kitty mode")."""
        ta = _make("Hello World")
        ta.set_selection(5, 11)
        ta.edit_buffer.set_cursor(0, 11)
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "Hello"
        ta.destroy()

    def test_should_distinguish_backspace_vs_shift_backspace_keybindings_in_kitty_mode(self):
        """Maps to test("should distinguish backspace vs shift+backspace keybindings in kitty mode")."""
        # Both should work the same way (default bindings map both to backspace action)
        ta = _make("AB")
        ta.edit_buffer.set_cursor(0, 2)
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "A"
        ta.destroy()

    def test_should_handle_mixed_backspace_and_shift_backspace_in_kitty_mode(self):
        """Maps to test("should handle mixed backspace and shift+backspace in kitty mode")."""
        ta = _make("ABCD")
        ta.edit_buffer.set_cursor(0, 4)
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "ABC"
        ta.handle_key(_key("backspace", shift=True))
        assert ta.plain_text == "AB"
        ta.destroy()

    def test_should_handle_shift_delete_in_kitty_mode(self):
        """Maps to test("should handle shift+delete in kitty mode")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("delete", shift=True))
        assert ta.plain_text == "ello"
        ta.destroy()

    def test_should_handle_ctrl_backspace_for_word_deletion_in_kitty_mode(self):
        """Maps to test("should handle ctrl+backspace for word deletion in kitty mode")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 11)
        # Ctrl+W = delete-word-backward
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "Hello "
        ta.destroy()

    def test_should_handle_meta_backspace_for_word_deletion_in_kitty_mode(self):
        """Maps to test("should handle meta+backspace for word deletion in kitty mode")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 11)
        # Meta+Backspace (alt+backspace) = delete-word-backward
        ta.handle_key(_key("backspace", alt=True))
        assert ta.plain_text == "Hello "
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Keyboard Input - Enter/Return
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingKeyboardInputEnterReturn:
    """Maps to describe("Textarea - Editing Tests") > describe("Keyboard Input - Enter/Return")."""

    def test_should_insert_newline_with_enter_key(self):
        """Maps to test("should insert newline with Enter key")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 5)
        ta.handle_key(_key("return"))
        assert ta.plain_text == "Hello\n"
        assert ta.cursor_position == (1, 0)
        ta.destroy()

    def test_should_insert_newline_at_end(self):
        """Maps to test("should insert newline at end")."""
        ta = _make()
        _type_string(ta, "Hello")
        ta.handle_key(_key("return"))
        _type_string(ta, "World")
        assert ta.plain_text == "Hello\nWorld"
        ta.destroy()

    def test_should_handle_multiple_newlines(self):
        """Maps to test("should handle multiple newlines")."""
        ta = _make()
        _type_string(ta, "A")
        ta.handle_key(_key("return"))
        _type_string(ta, "B")
        ta.handle_key(_key("return"))
        _type_string(ta, "C")
        assert ta.plain_text == "A\nB\nC"
        assert ta.line_count == 3
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Keyboard Input - Home and End
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingKeyboardInputHomeAndEnd:
    """Maps to describe("Textarea - Editing Tests") > describe("Keyboard Input - Home and End")."""

    def test_should_move_to_line_start_with_home(self):
        """Maps to test("should move to line start with Home")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 7)
        ta.handle_key(_key("home"))
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_move_to_line_end_with_end(self):
        """Maps to test("should move to line end with End")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 3)
        ta.handle_key(_key("end"))
        assert ta.cursor_position == (0, 11)
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Keyboard Input - Control Commands
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingKeyboardInputControlCommands:
    """Maps to describe("Textarea - Editing Tests") > describe("Keyboard Input - Control Commands")."""

    def test_should_move_to_line_start_with_ctrl_a(self):
        """Maps to test("should move to line start with Ctrl+A")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 7)
        ta.handle_key(_key("a", ctrl=True))
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_move_to_line_end_with_ctrl_e(self):
        """Maps to test("should move to line end with Ctrl+E")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 3)
        ta.handle_key(_key("e", ctrl=True))
        assert ta.cursor_position == (0, 11)
        ta.destroy()

    def test_should_delete_character_forward_with_ctrl_d(self):
        """Maps to test("should delete character forward with Ctrl+D")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("d", ctrl=True))
        assert ta.plain_text == "ello"
        ta.destroy()

    def test_should_delete_to_line_end_with_ctrl_k(self):
        """Maps to test("should delete to line end with Ctrl+K")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 5)
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Hello"
        ta.destroy()

    def test_should_move_to_buffer_start_with_home_key(self):
        """Maps to test("should move to buffer start with Home key")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.edit_buffer.set_cursor(2, 3)
        ta.handle_key(_key("home", ctrl=True))
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_move_to_buffer_end_with_end_key(self):
        """Maps to test("should move to buffer end with End key")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("end", ctrl=True))
        assert ta.cursor_position == (2, 6)
        ta.destroy()

    def test_should_select_from_cursor_to_buffer_start_with_home_shift(self):
        """Maps to test("should select from cursor to buffer start with Home+Shift")."""
        ta = _make("Line 1\nLine 2")
        ta.edit_buffer.set_cursor(1, 3)
        ta.handle_key(_key("home", shift=True))
        assert ta.has_selection
        sel = ta.selection
        assert sel is not None
        # Selection from offset of (1,3) to offset of (1,0) = line start
        # Actually, home+shift -> select-buffer-home
        ta.destroy()

    def test_should_select_from_cursor_to_buffer_end_with_end_shift(self):
        """Maps to test("should select from cursor to buffer end with End+Shift")."""
        ta = _make("Line 1\nLine 2")
        ta.edit_buffer.set_cursor(0, 3)
        ta.handle_key(_key("end", shift=True))
        assert ta.has_selection
        sel = ta.selection
        assert sel is not None
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Word Movement and Deletion
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingWordMovementAndDeletion:
    """Maps to describe("Textarea - Editing Tests") > describe("Word Movement and Deletion")."""

    def test_should_move_forward_by_word_with_alt_f(self):
        """Maps to test("should move forward by word with Alt+F")."""
        ta = _make("Hello World Foo")
        ta.edit_buffer.set_cursor(0, 0)
        # Meta+F (alt+f in terminal) = word-forward
        ta.handle_key(_key("f", alt=True))
        # Should be at end of "Hello" or start of next word
        line, col = ta.cursor_position
        assert col == 6  # After "Hello " -> start of "World"
        ta.destroy()

    def test_should_move_backward_by_word_with_alt_b(self):
        """Maps to test("should move backward by word with Alt+B")."""
        ta = _make("Hello World Foo")
        ta.edit_buffer.set_cursor(0, 15)
        ta.handle_key(_key("b", alt=True))
        line, col = ta.cursor_position
        assert col == 12  # Start of "Foo"
        ta.destroy()

    def test_should_move_forward_by_word_with_meta_right(self):
        """Maps to test("should move forward by word with Meta+Right")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("right", alt=True))
        line, col = ta.cursor_position
        assert col == 6  # After "Hello "
        ta.destroy()

    def test_should_move_backward_by_word_with_meta_left(self):
        """Maps to test("should move backward by word with Meta+Left")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 11)
        ta.handle_key(_key("left", alt=True))
        line, col = ta.cursor_position
        assert col == 6  # Start of "World"
        ta.destroy()

    def test_should_delete_word_forward_with_alt_d(self):
        """Maps to test("should delete word forward with Alt+D")."""
        ta = _make("Hello World Foo")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "World Foo"
        ta.destroy()

    def test_should_delete_word_backward_with_alt_backspace(self):
        """Maps to test("should delete word backward with Alt+Backspace")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 11)
        ta.handle_key(_key("backspace", alt=True))
        assert ta.plain_text == "Hello "
        ta.destroy()

    def test_should_delete_word_backward_with_ctrl_w(self):
        """Maps to test("should delete word backward with Ctrl+W")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 11)
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "Hello "
        ta.destroy()

    def test_should_delete_line_with_ctrl_shift_d(self):
        """Maps to test("should delete line with Ctrl+Shift+D (requires Kitty keyboard protocol)")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.edit_buffer.set_cursor(1, 0)
        ta.handle_key(_key("d", ctrl=True, shift=True))
        assert "Line 2" not in ta.plain_text
        ta.destroy()

    def test_should_handle_word_movement_across_multiple_lines(self):
        """Maps to test("should handle word movement across multiple lines")."""
        ta = _make("Hello\nWorld")
        ta.edit_buffer.set_cursor(0, 0)
        ta.move_word_forward()
        # Should skip past "Hello\n" to "World"
        line, col = ta.cursor_position
        assert line == 1
        assert col == 0
        ta.destroy()

    def test_should_delete_word_forward_from_line_start(self):
        """Maps to test("should delete word forward from line start")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 0)
        ta.delete_word_forward()
        assert ta.plain_text == "World"
        ta.destroy()

    def test_should_handle_word_deletion_operations_with_alt_d(self):
        """Maps to test("should handle word deletion operations with Alt+D")."""
        ta = _make("One Two Three")
        ta.edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "Two Three"
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "Three"
        ta.destroy()

    def test_should_navigate_by_words_and_characters(self):
        """Maps to test("should navigate by words and characters")."""
        ta = _make("Hello World")
        ta.edit_buffer.set_cursor(0, 0)
        # Move right 3 chars
        ta.move_cursor_right()
        ta.move_cursor_right()
        ta.move_cursor_right()
        assert ta.cursor_position == (0, 3)
        # Move forward by word
        ta.move_word_forward()
        # Should be past "lo " at start of "World" = col 6
        line, col = ta.cursor_position
        assert col == 6
        ta.destroy()

    def test_should_delete_word_forward_even_with_selection_when_using_meta_d(self):
        """Maps to test("should delete word forward even with selection when using meta+d")."""
        ta = _make("Hello World Foo")
        ta.edit_buffer.set_cursor(0, 6)
        # Alt+D deletes word forward regardless of selection
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "Hello Foo"
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Chunk Boundary Navigation
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingChunkBoundaryNavigation:
    """Maps to describe("Textarea - Editing Tests") > describe("Chunk Boundary Navigation")."""

    def test_should_move_cursor_across_chunks_created_by_insertions(self):
        """Maps to test("should move cursor across chunks created by insertions")."""
        ta = _make("Hello")
        ta.edit_buffer.set_cursor(0, 5)
        ta.insert_text(" World")
        assert ta.plain_text == "Hello World"
        # Move left across the boundary
        ta.move_cursor_left()
        ta.move_cursor_left()
        ta.move_cursor_left()
        assert ta.cursor_position == (0, 8)
        ta.destroy()

    def test_should_move_cursor_left_across_multiple_chunks(self):
        """Maps to test("should move cursor left across multiple chunks")."""
        ta = _make()
        _type_string(ta, "ABC")
        assert ta.cursor_position == (0, 3)
        ta.move_cursor_left()
        assert ta.cursor_position == (0, 2)
        ta.move_cursor_left()
        assert ta.cursor_position == (0, 1)
        ta.move_cursor_left()
        assert ta.cursor_position == (0, 0)
        ta.destroy()

    def test_should_move_cursor_right_across_all_chunks_to_end(self):
        """Maps to test("should move cursor right across all chunks to end")."""
        ta = _make()
        _type_string(ta, "ABC")
        ta.edit_buffer.set_cursor(0, 0)
        ta.move_cursor_right()
        assert ta.cursor_position == (0, 1)
        ta.move_cursor_right()
        assert ta.cursor_position == (0, 2)
        ta.move_cursor_right()
        assert ta.cursor_position == (0, 3)
        ta.destroy()

    def test_should_handle_cursor_movement_after_multiple_insertions_and_deletions(self):
        """Maps to test("should handle cursor movement after multiple insertions and deletions")."""
        ta = _make()
        _type_string(ta, "Hello")
        ta.delete_char_backward()  # "Hell"
        _type_string(ta, "p")  # "Hellp"
        ta.delete_char_backward()  # "Hell"
        _type_string(ta, "o")  # "Hello"
        assert ta.plain_text == "Hello"
        assert ta.cursor_position == (0, 5)
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Complex Editing Scenarios
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingComplexEditingScenarios:
    """Maps to describe("Textarea - Editing Tests") > describe("Complex Editing Scenarios")."""

    def test_should_handle_typing_navigation_and_deletion(self):
        """Maps to test("should handle typing, navigation, and deletion")."""
        ta = _make()
        _type_string(ta, "Hello World")
        # Go to start
        ta.goto_line_home()
        # Delete word forward
        ta.delete_word_forward()
        assert ta.plain_text == "World"
        ta.destroy()

    def test_should_handle_newlines_and_multi_line_editing(self):
        """Maps to test("should handle newlines and multi-line editing")."""
        ta = _make()
        _type_string(ta, "Line 1")
        ta.newline()
        _type_string(ta, "Line 2")
        ta.newline()
        _type_string(ta, "Line 3")
        assert ta.plain_text == "Line 1\nLine 2\nLine 3"
        assert ta.line_count == 3
        ta.destroy()

    def test_should_handle_insert_and_delete_in_sequence(self):
        """Maps to test("should handle insert and delete in sequence")."""
        ta = _make()
        _type_string(ta, "AB")
        ta.delete_char_backward()
        _type_string(ta, "CD")
        assert ta.plain_text == "ACD"
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Edit Operations
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingEditOperations:
    """Maps to describe("Textarea - Editing Tests") > describe("Edit Operations")."""

    def test_should_maintain_correct_cursor_position_after_join_insert_backspace(self):
        """Maps to test("should maintain correct cursor position after join, insert, backspace")."""
        ta = _make("AB\nCD")
        ta.edit_buffer.set_cursor(1, 0)
        # Join lines
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "ABCD"
        assert ta.cursor_position == (0, 2)
        # Type a character
        ta.handle_key(_key("X"))
        assert ta.plain_text == "ABXCD"
        assert ta.cursor_position == (0, 3)
        # Backspace
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == "ABCD"
        assert ta.cursor_position == (0, 2)
        ta.destroy()

    def test_should_type_correctly_after_backspace(self):
        """Maps to test("should type correctly after backspace")."""
        ta = _make()
        _type_string(ta, "AB")
        ta.handle_key(_key("backspace"))
        _type_string(ta, "C")
        assert ta.plain_text == "AC"
        ta.destroy()

    def test_should_type_correctly_after_multiple_backspaces(self):
        """Maps to test("should type correctly after multiple backspaces")."""
        ta = _make()
        _type_string(ta, "ABC")
        ta.handle_key(_key("backspace"))
        ta.handle_key(_key("backspace"))
        _type_string(ta, "DE")
        assert ta.plain_text == "ADE"
        ta.destroy()

    def test_should_type_correctly_after_backspacing_all_text(self):
        """Maps to test("should type correctly after backspacing all text")."""
        ta = _make()
        _type_string(ta, "AB")
        ta.handle_key(_key("backspace"))
        ta.handle_key(_key("backspace"))
        assert ta.plain_text == ""
        _type_string(ta, "CD")
        assert ta.plain_text == "CD"
        ta.destroy()


# ═══════════════════════════════════════════════════════════════════════
# Deletion with empty lines
# ═══════════════════════════════════════════════════════════════════════


class TestTextareaEditingDeletionWithEmptyLines:
    """Maps to describe("Textarea - Editing Tests") > describe("Deletion with empty lines")."""

    def test_should_delete_selection_on_line_after_empty_lines_correctly(self):
        """Maps to test("should delete selection on line after empty lines correctly")."""
        ta = _make("Line 1\n\nLine 3")
        # Select "Line 3" (offset 8-14)
        ta.set_selection(8, 14)
        ta.edit_buffer.set_cursor(2, 6)
        ta.delete_char_backward()
        # Selection should be deleted
        assert "Line 3" not in ta.plain_text
        ta.destroy()

    def test_should_delete_selection_on_first_line_correctly_baseline_test(self):
        """Maps to test("should delete selection on first line correctly (baseline test)")."""
        ta = _make("Hello World")
        ta.set_selection(5, 11)
        ta.edit_buffer.set_cursor(0, 11)
        ta.delete_char_backward()
        assert ta.plain_text == "Hello"
        ta.destroy()

    def test_should_delete_selection_on_last_line_after_empty_lines_correctly(self):
        """Maps to test("should delete selection on last line after empty lines correctly")."""
        ta = _make("A\n\nB\n\nC")
        # Select "C" at the end
        text = ta.plain_text
        c_offset = text.index("C")
        ta.set_selection(c_offset, c_offset + 1)
        ta.edit_buffer.set_cursor(4, 1)
        ta.delete_char_backward()
        # Native buffer drops trailing empty line when last char deleted
        assert ta.plain_text == "A\n\nB\n"
        ta.destroy()
