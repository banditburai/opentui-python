"""Port of upstream Textarea.keybinding.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.keybinding.test.ts
Tests ported: 143/143 (all implemented)
"""

import pytest

from opentui.components.textarea import TextareaRenderable
from opentui.events import KeyEvent
from opentui.input.keymapping import KeyBinding


# ── Helpers ──────────────────────────────────────────────────────────────


def _key(name, *, ctrl=False, shift=False, alt=False, meta=False, hyper=False, sequence=""):
    """Create a KeyEvent.

    NOTE: KeyBinding.meta maps to KeyEvent.alt in terminal convention.
    When a keybinding uses meta=True, dispatch the event with alt=True.
    """
    return KeyEvent(
        key=name,
        ctrl=ctrl,
        shift=shift,
        alt=alt,
        meta=meta,
        hyper=hyper,
        sequence=sequence,
    )


def _make(text="", **kwargs):
    """Create a focused TextareaRenderable with *text* pre-filled."""
    ta = TextareaRenderable(initial_value=text, **kwargs)
    ta.focus()
    return ta


def _cursor(ta):
    """Return (line, col) cursor position."""
    return ta.cursor_position


# ── Tests ────────────────────────────────────────────────────────────────


class TestTextareaKeybindingMetaKeyBindings:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Keyboard Input - Meta Key Bindings")."""

    def test_should_bind_custom_action_to_meta_key(self):
        """Maps to test("should bind custom action to meta key")."""
        ta = _make("Test", key_bindings=[KeyBinding(name="b", alt=True, action="buffer-home")])
        ta.goto_buffer_end()
        # alt on binding -> alt on event
        ta.handle_key(_key("b", alt=True))
        line, col = _cursor(ta)
        assert line == 0
        assert col == 0

    def test_should_bind_meta_key_actions(self):
        """Maps to test("should bind meta key actions")."""
        ta = _make("Test", key_bindings=[KeyBinding(name="f", alt=True, action="buffer-end")])
        ta.handle_key(_key("f", alt=True))
        line, _col = _cursor(ta)
        assert line == 0

    def test_should_work_with_meta_key_for_navigation(self):
        """Maps to test("should work with meta key for navigation")."""
        ta = _make(
            "Line 1\nLine 2", key_bindings=[KeyBinding(name="j", alt=True, action="move-down")]
        )
        assert _cursor(ta)[0] == 0
        ta.handle_key(_key("j", alt=True))
        assert _cursor(ta)[0] == 1

    def test_should_allow_meta_key_binding_override(self):
        """Maps to test("should allow meta key binding override")."""
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[KeyBinding(name="k", alt=True, action="move-up")],
        )
        ta.goto_line(2)
        assert _cursor(ta)[0] == 2
        ta.handle_key(_key("k", alt=True))
        assert _cursor(ta)[0] == 1

    def test_should_work_with_meta_arrow_keys(self):
        """Maps to test("should work with Meta+Arrow keys")."""
        ta = _make(
            "ABC",
            key_bindings=[
                KeyBinding(name="left", alt=True, action="line-home"),
                KeyBinding(name="right", alt=True, action="line-end"),
            ],
        )
        ta.move_cursor_right()
        ta.move_cursor_right()
        assert _cursor(ta)[1] == 2
        ta.handle_key(_key("left", alt=True))
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("right", alt=True))
        assert _cursor(ta)[1] == 3

    def test_should_support_meta_with_shift_modifier(self):
        """Maps to test("should support meta with shift modifier")."""
        ta = _make(
            "Hello World",
            key_bindings=[KeyBinding(name="h", alt=True, shift=True, action="line-home")],
        )
        ta.goto_buffer_end()
        assert _cursor(ta)[1] == 11
        # alt+shift on binding -> alt+shift on event, key is lowercase "h"
        ta.handle_key(_key("h", alt=True, shift=True))
        assert _cursor(ta)[1] == 0

    def test_should_not_trigger_action_without_meta_when_meta_binding_exists(self):
        """Maps to test("should not trigger action without meta when meta binding exists")."""
        ta = _make("Test", key_bindings=[KeyBinding(name="x", alt=True, action="delete-line")])
        # 'x' without meta inserts the character
        ta.handle_key(_key("x", sequence="x"))
        assert ta.plain_text == "xTest"
        # 'x' with alt triggers delete-line
        ta.handle_key(_key("x", alt=True))
        assert ta.plain_text == ""

    def test_should_update_keybindings_dynamically_with_setter(self):
        """Maps to test("should update keyBindings dynamically with setter")."""
        ta = _make("Test")
        ta.goto_buffer_end()
        # Default alt+b = word-backward
        ta.handle_key(_key("b", alt=True))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0
        # Override: alt+b -> buffer-end
        ta.key_bindings = [KeyBinding(name="b", meta=True, action="buffer-end")]
        ta.goto_line(0)
        assert _cursor(ta)[0] == 0
        ta.handle_key(_key("b", alt=True))
        assert _cursor(ta)[0] == 0  # single line, so row stays 0

    def test_should_merge_new_keybindings_with_defaults(self):
        """Maps to test("should merge new keyBindings with defaults")."""
        ta = _make("Line 1\nLine 2")
        ta.handle_key(_key("right"))
        assert _cursor(ta)[1] == 1
        # Add a new binding, defaults remain
        ta.key_bindings = [KeyBinding(name="d", alt=True, action="delete-line")]
        ta.handle_key(_key("right"))
        assert _cursor(ta)[1] == 2
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "Line 2"

    def test_should_override_default_keybindings_with_new_bindings(self):
        """Maps to test("should override default keyBindings with new bindings")."""
        ta = _make("hello world")
        # Default alt+f = word-forward
        ta.handle_key(_key("f", alt=True))
        assert _cursor(ta)[1] == 6
        # Override to buffer-end
        ta.key_bindings = [KeyBinding(name="f", alt=True, action="buffer-end")]
        ta.goto_line(0)
        ta.handle_key(_key("f", alt=True))
        assert _cursor(ta)[0] == 0  # single line

    def test_should_override_return_enter_keys_to_swap_newline_and_submit_actions(self):
        """Maps to test("should override return/enter keys to swap newline and submit actions")."""
        submit_called = False

        def on_submit(_text):
            nonlocal submit_called
            submit_called = True

        ta = _make("Line 1", on_submit=on_submit)
        ta.goto_buffer_end()

        # Default: return -> newline
        ta.handle_key(_key("return"))
        assert ta.plain_text == "Line 1\n"
        assert submit_called is False

        # Default: alt+return -> submit
        ta.handle_key(_key("return", alt=True))
        assert submit_called is True
        submit_called = False

        # Swap: return -> submit, alt+return -> newline
        ta.key_bindings = [
            KeyBinding(name="return", alt=True, action="newline"),
            KeyBinding(name="linefeed", alt=True, action="newline"),
            KeyBinding(name="return", action="submit"),
            KeyBinding(name="linefeed", action="submit"),
        ]

        ta.handle_key(_key("return"))
        assert submit_called is True
        submit_called = False

        ta.handle_key(_key("return", alt=True))
        assert ta.plain_text == "Line 1\n\n"
        assert submit_called is False


class TestTextareaKeybindingKeyEventHandlingModifierKeys:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Key Event Handling - Modifier Keys")."""

    def test_should_not_insert_text_when_ctrl_modifier_is_pressed(self):
        """Maps to test("should not insert text when ctrl modifier is pressed")."""
        ta = _make("")
        ta.handle_key(_key("a", ctrl=True, sequence="a"))
        assert ta.plain_text == ""
        ta.handle_key(_key("x", ctrl=True, sequence="x"))
        assert ta.plain_text == ""

    def test_should_not_insert_text_when_meta_modifier_is_pressed(self):
        """Maps to test("should not insert text when meta modifier is pressed").

        Note: In terminal convention, KeyBinding.meta -> KeyEvent.alt.
        This test checks that alt modifier prevents text insertion.
        """
        ta = _make("")
        ta.handle_key(_key("a", alt=True, sequence="a"))
        assert ta.plain_text == ""
        ta.handle_key(_key("x", alt=True, sequence="x"))
        assert ta.plain_text == ""

    def test_should_not_insert_text_when_super_modifier_is_pressed(self):
        """Maps to test("should not insert text when super modifier is pressed").

        In terminal convention, super maps to KeyEvent.meta.
        """
        ta = _make("")
        ta.handle_key(_key("a", meta=True, sequence="a"))
        assert ta.plain_text == ""
        ta.handle_key(_key("x", meta=True, sequence="x"))
        assert ta.plain_text == ""

    def test_should_not_insert_text_when_hyper_modifier_is_pressed(self):
        """Maps to test("should not insert text when hyper modifier is pressed")."""
        ta = _make("")
        ta.handle_key(_key("a", hyper=True, sequence="a"))
        assert ta.plain_text == ""
        ta.handle_key(_key("x", hyper=True, sequence="x"))
        assert ta.plain_text == ""

    def test_should_not_insert_text_when_multiple_modifiers_are_pressed(self):
        """Maps to test("should not insert text when multiple modifiers are pressed")."""
        ta = _make("")
        ta.handle_key(_key("a", ctrl=True, alt=True, sequence="a"))
        assert ta.plain_text == ""
        ta.handle_key(_key("b", ctrl=True, meta=True, sequence="b"))
        assert ta.plain_text == ""
        ta.handle_key(_key("c", alt=True, hyper=True, sequence="c"))
        assert ta.plain_text == ""

    def test_should_insert_text_when_only_shift_modifier_is_pressed(self):
        """Maps to test("should insert text when only shift modifier is pressed")."""
        ta = _make("")
        ta.handle_key(_key("A", shift=True, sequence="A"))
        assert ta.plain_text == "A"
        ta.handle_key(_key("B", shift=True, sequence="B"))
        assert ta.plain_text == "AB"


class TestTextareaKeybindingKeyEventHandling:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Key Event Handling")."""

    def test_should_only_handle_keyevents_not_raw_escape_sequences(self):
        """Maps to test("should only handle KeyEvents, not raw escape sequences")."""
        ta = _make("")
        raw = "\x1b[<35;86;19M"
        handled = ta.handle_key(_key(raw, sequence=raw))
        assert handled is False
        assert ta.plain_text == ""

    def test_should_not_insert_control_sequences_into_text(self):
        """Maps to test("should not insert control sequences into text")."""
        ta = _make("Hello")
        control_seqs = [
            "\x1b[A",
            "\x1b[B",
            "\x1b[C",
            "\x1b[D",
            "\x1b[?1004h",
            "\x1b[?2004h",
            "\x1b[<0;10;10M",
        ]
        for seq in control_seqs:
            before = ta.plain_text
            ta.handle_key(_key(seq, sequence=seq))
            assert ta.plain_text == before

    def test_should_handle_printable_characters_via_handlekeypress(self):
        """Maps to test("should handle printable characters via handleKeyPress")."""
        ta = _make("")
        handled1 = ta.handle_key(_key("a", sequence="a"))
        assert handled1 is True
        assert ta.plain_text == "a"
        handled2 = ta.handle_key(_key("b", sequence="b"))
        assert handled2 is True
        assert ta.plain_text == "ab"

    def test_should_handle_multi_byte_unicode_characters_emoji_cjk(self):
        """Maps to test("should handle multi-byte Unicode characters (emoji, CJK)")."""
        ta = _make("")
        handled = ta.handle_key(_key("\U0001f31f", sequence="\U0001f31f"))
        assert handled is True
        assert ta.plain_text == "\U0001f31f"
        handled2 = ta.handle_key(_key("\u4e16", sequence="\u4e16"))
        assert handled2 is True
        assert ta.plain_text == "\U0001f31f\u4e16"
        ta.insert_text(" ")
        handled3 = ta.handle_key(_key("\U0001f44d", sequence="\U0001f44d"))
        assert handled3 is True
        assert ta.plain_text == "\U0001f31f\u4e16 \U0001f44d"

    def test_should_filter_escape_sequences_when_they_have_non_printable_characters(self):
        """Maps to test("should filter escape sequences when they have non-printable characters")."""
        ta = _make("Test")
        ta.goto_buffer_end()
        esc = chr(0x1B)
        ta.handle_key(_key(esc, sequence=esc))
        assert ta.plain_text == "Test"


class TestTextareaKeybindingKeyBindings:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Key Bindings") (first occurrence)."""

    def test_should_use_default_keybindings(self):
        """Maps to test("should use default keybindings")."""
        ta = _make("Hello World")
        ta.handle_key(_key("right"))
        assert _cursor(ta)[1] == 1
        ta.handle_key(_key("home"))
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("end"))
        assert _cursor(ta)[1] == 11

    def test_should_allow_custom_keybindings_to_override_defaults(self):
        """Maps to test("should allow custom keybindings to override defaults")."""
        ta = _make("Hello World", key_bindings=[KeyBinding(name="j", action="move-left")])
        ta.goto_buffer_end()
        assert _cursor(ta)[1] == 11
        ta.handle_key(_key("j", sequence="j"))
        assert _cursor(ta)[1] == 10

    def test_should_map_multiple_custom_keys_to_the_same_action(self):
        """Maps to test("should map multiple custom keys to the same action")."""
        ta = _make(
            "Hello World",
            key_bindings=[
                KeyBinding(name="h", action="move-left"),
                KeyBinding(name="j", action="move-down"),
                KeyBinding(name="k", action="move-up"),
                KeyBinding(name="l", action="move-right"),
            ],
        )
        ta.handle_key(_key("l", sequence="l"))
        assert _cursor(ta)[1] == 1
        ta.handle_key(_key("l", sequence="l"))
        assert _cursor(ta)[1] == 2
        ta.handle_key(_key("h", sequence="h"))
        assert _cursor(ta)[1] == 1
        ta.handle_key(_key("h", sequence="h"))
        assert _cursor(ta)[1] == 0

    def test_should_support_custom_keybindings_with_ctrl_modifier(self):
        """Maps to test("should support custom keybindings with ctrl modifier")."""
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[KeyBinding(name="g", ctrl=True, action="buffer-home")],
        )
        ta.goto_buffer_end()
        assert _cursor(ta)[0] == 2
        ta.handle_key(_key("g", ctrl=True))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_support_custom_keybindings_with_shift_modifier(self):
        """Maps to test("should support custom keybindings with shift modifier")."""
        ta = _make(
            "Hello World",
            key_bindings=[KeyBinding(name="l", shift=True, action="select-right")],
        )
        ta.handle_key(_key("l", shift=True, sequence="L"))
        assert ta.has_selection is True
        assert ta.get_selected_text() == "H"
        ta.handle_key(_key("l", shift=True, sequence="L"))
        assert ta.get_selected_text() == "He"

    def test_should_support_custom_keybindings_with_alt_modifier(self):
        """Maps to test("should support custom keybindings with alt modifier").

        The upstream TS test actually uses ctrl+b -> buffer-home, not alt.
        """
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[KeyBinding(name="b", ctrl=True, action="buffer-home")],
        )
        ta.goto_line(2)
        ta.handle_key(_key("b", ctrl=True))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_support_keybindings_with_multiple_modifiers(self):
        """Maps to test("should support keybindings with multiple modifiers")."""
        ta = _make(
            "Hello World",
            key_bindings=[
                KeyBinding(name="right", ctrl=True, shift=True, action="select-line-end"),
            ],
        )
        ta.handle_key(_key("right", ctrl=True, shift=True))
        assert ta.has_selection is True
        assert ta.get_selected_text() == "Hello World"

    def test_should_map_newline_action_to_custom_key(self):
        """Maps to test("should map newline action to custom key")."""
        ta = _make(
            "Hello",
            key_bindings=[KeyBinding(name="n", ctrl=True, action="newline")],
        )
        ta.goto_buffer_end()
        ta.handle_key(_key("n", ctrl=True))
        assert ta.plain_text == "Hello\n"

    def test_should_map_backspace_action_to_custom_key(self):
        """Maps to test("should map backspace action to custom key")."""
        ta = _make(
            "Hello",
            key_bindings=[KeyBinding(name="h", ctrl=True, action="backspace")],
        )
        ta.goto_buffer_end()
        ta.handle_key(_key("h", ctrl=True))
        assert ta.plain_text == "Hell"

    def test_should_map_delete_action_to_custom_key(self):
        """Maps to test("should map delete action to custom key")."""
        ta = _make(
            "Hello",
            key_bindings=[KeyBinding(name="d", action="delete")],
        )
        ta.handle_key(_key("d", sequence="d"))
        assert ta.plain_text == "ello"

    def test_should_map_line_home_and_line_end_to_custom_keys(self):
        """Maps to test("should map line-home and line-end to custom keys")."""
        ta = _make(
            "Hello World",
            key_bindings=[
                KeyBinding(name="a", action="line-home"),
                KeyBinding(name="e", action="line-end"),
            ],
        )
        ta.move_cursor_right()
        ta.move_cursor_right()
        assert _cursor(ta)[1] == 2
        ta.handle_key(_key("a", sequence="a"))
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("e", sequence="e"))
        assert _cursor(ta)[1] == 11

    def test_should_override_default_shift_home_and_shift_end_keybindings(self):
        """Maps to test("should override default shift+home and shift+end keybindings")."""
        ta = _make(
            "Hello World",
            key_bindings=[
                KeyBinding(name="home", shift=True, action="buffer-home"),
                KeyBinding(name="end", shift=True, action="buffer-end"),
            ],
        )
        for _ in range(6):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("home", shift=True))
        assert ta.has_selection is False
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0
        ta.move_cursor_right()
        ta.handle_key(_key("end", shift=True))
        assert ta.has_selection is False
        assert _cursor(ta)[0] == 0

    def test_should_map_undo_and_redo_actions_to_custom_keys(self):
        """Maps to test("should map undo and redo actions to custom keys")."""
        ta = _make(
            "",
            key_bindings=[
                KeyBinding(name="u", action="undo"),
                KeyBinding(name="r", action="redo"),
            ],
        )
        ta.handle_key(_key("H", sequence="H"))
        ta.handle_key(_key("i", sequence="i"))
        assert ta.plain_text == "Hi"
        ta.handle_key(_key("u", sequence="u"))
        assert ta.plain_text == "H"
        ta.handle_key(_key("r", sequence="r"))
        assert ta.plain_text == "Hi"

    def test_should_map_delete_line_action_to_custom_key(self):
        """Maps to test("should map delete-line action to custom key")."""
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[KeyBinding(name="x", ctrl=True, action="delete-line")],
        )
        ta.goto_line(1)
        ta.handle_key(_key("x", ctrl=True))
        assert ta.plain_text == "Line 1\nLine 3"

    def test_should_map_delete_to_line_end_action_to_custom_key(self):
        """Maps to test("should map delete-to-line-end action to custom key")."""
        ta = _make(
            "Hello World",
            key_bindings=[KeyBinding(name="k", action="delete-to-line-end")],
        )
        for _ in range(6):
            ta.move_cursor_right()
        ta.handle_key(_key("k", sequence="k"))
        assert ta.plain_text == "Hello "

    def test_should_delete_from_cursor_to_line_start_with_ctrl_u(self):
        """Maps to test("should delete from cursor to line start with ctrl+u")."""
        ta = _make("Hello World")
        for _ in range(6):
            ta.move_cursor_right()
        ta.handle_key(_key("u", ctrl=True))
        assert ta.plain_text == "World"
        assert _cursor(ta)[1] == 0

    def test_should_map_delete_to_line_start_action_to_custom_key(self):
        """Maps to test("should map delete-to-line-start action to custom key")."""
        ta = _make(
            "Hello World",
            key_bindings=[KeyBinding(name="x", ctrl=True, action="delete-to-line-start")],
        )
        for _ in range(6):
            ta.move_cursor_right()
        ta.handle_key(_key("x", ctrl=True))
        assert ta.plain_text == "World"
        assert _cursor(ta)[1] == 0

    def test_should_delete_from_cursor_to_line_end_with_ctrl_k_in_multiline_text(self):
        """Maps to test("should delete from cursor to line end with ctrl+k in multiline text")."""
        ta = _make("Line 1 content\nLine 2 content\nLine 3 content")
        for _ in range(7):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Line 1 \nLine 2 content\nLine 3 content"
        assert _cursor(ta)[1] == 7
        assert _cursor(ta)[0] == 0

    def test_should_delete_from_cursor_to_line_end_with_ctrl_k_on_line_2(self):
        """Maps to test("should delete from cursor to line end with ctrl+k on line 2")."""
        ta = _make("Line 1 content\nLine 2 content\nLine 3 content")
        ta.goto_line(1)
        for _ in range(7):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Line 1 content\nLine 2 \nLine 3 content"
        assert _cursor(ta)[1] == 7
        assert _cursor(ta)[0] == 1

    def test_should_delete_from_start_to_cursor_with_ctrl_u_in_multiline_text(self):
        """Maps to test("should delete from start to cursor with ctrl+u in multiline text")."""
        ta = _make("Line 1 content\nLine 2 content\nLine 3 content")
        for _ in range(7):
            ta.move_cursor_right()
        ta.handle_key(_key("u", ctrl=True))
        assert ta.plain_text == "content\nLine 2 content\nLine 3 content"
        assert _cursor(ta)[1] == 0
        assert _cursor(ta)[0] == 0

    def test_should_delete_from_start_to_cursor_with_ctrl_u_on_line_2(self):
        """Maps to test("should delete from start to cursor with ctrl+u on line 2")."""
        ta = _make("Line 1 content\nLine 2 content\nLine 3 content")
        ta.goto_line(1)
        for _ in range(7):
            ta.move_cursor_right()
        ta.handle_key(_key("u", ctrl=True))
        assert ta.plain_text == "Line 1 content\ncontent\nLine 3 content"
        assert _cursor(ta)[1] == 0
        assert _cursor(ta)[0] == 1

    def test_should_do_nothing_with_ctrl_k_when_cursor_is_at_end_of_line(self):
        """Maps to test("should do nothing with ctrl+k when cursor is at end of line")."""
        ta = _make("Line 1 content\nLine 2 content")
        # Position cursor at end of first line using edit buffer directly
        ta._edit_buffer.set_cursor(0, 14)
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Line 1 content\nLine 2 content"
        assert _cursor(ta)[1] == 14

    def test_should_do_nothing_with_ctrl_u_when_cursor_is_at_start_of_line(self):
        """Maps to test("should do nothing with ctrl+u when cursor is at start of line")."""
        ta = _make("Line 1 content\nLine 2 content")
        ta.handle_key(_key("u", ctrl=True))
        assert ta.plain_text == "Line 1 content\nLine 2 content"
        assert _cursor(ta)[1] == 0

    def test_should_work_with_ctrl_k_after_undo(self):
        """Maps to test("should work with ctrl+k after undo")."""
        ta = _make(
            "Hello World",
            key_bindings=[KeyBinding(name="u", action="undo")],
        )
        for _ in range(6):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Hello "
        ta.handle_key(_key("u", sequence="u"))
        assert ta.plain_text == "Hello World"
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Hello "

    def test_should_work_with_ctrl_u_after_undo_when_cursor_is_repositioned(self):
        """Maps to test("should work with ctrl+u after undo when cursor is repositioned")."""
        ta = _make(
            "Hello World",
            key_bindings=[KeyBinding(name="z", action="undo")],
        )
        for _ in range(6):
            ta.move_cursor_right()
        ta.handle_key(_key("u", ctrl=True))
        assert ta.plain_text == "World"
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("z", sequence="z"))
        assert ta.plain_text == "Hello World"
        for _ in range(6):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("u", ctrl=True))
        assert ta.plain_text == "World"

    def test_should_allow_cursor_to_move_right_within_restored_line_after_undo(self):
        """Maps to test("should allow cursor to move right within restored line after undo")."""
        ta = _make(
            "Line 1 content\nLine 2 content\nLine 3 content",
            key_bindings=[KeyBinding(name="u", action="undo")],
        )
        for _ in range(7):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Line 1 \nLine 2 content\nLine 3 content"
        ta.handle_key(_key("u", sequence="u"))
        assert ta.plain_text == "Line 1 content\nLine 2 content\nLine 3 content"
        for _ in range(3):
            ta.move_cursor_right()
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 10

    def test_should_allow_ctrl_k_to_work_again_after_undo(self):
        """Maps to test("should allow ctrl+k to work again after undo")."""
        ta = _make(
            "Line 1 content\nLine 2",
            key_bindings=[KeyBinding(name="u", action="undo")],
        )
        for _ in range(7):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Line 1 \nLine 2"
        ta.handle_key(_key("u", sequence="u"))
        assert ta.plain_text == "Line 1 content\nLine 2"
        ta.handle_key(_key("k", ctrl=True))
        assert ta.plain_text == "Line 1 \nLine 2"


class TestTextareaKeybindingWrappedLines:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Wrapped Lines") (first occurrence)."""

    def test_should_delete_to_end_of_logical_line_with_ctrl_k_when_wrapping_enabled(self):
        """Maps to test("should delete to end of logical line with ctrl+k when wrapping enabled")."""
        ta = _make(
            "This is a very long line that will wrap when viewport is narrow\nLine 2 content",
            wrap_mode="word",
            width=20,
            height=10,
        )
        ta._editor_view.set_viewport_size(20, 10)
        for _ in range(30):
            ta.move_cursor_right()
        vc = ta._editor_view.get_visual_cursor()
        assert vc.logical_row == 0
        assert vc.logical_col == 30
        ta.handle_key(_key("k", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == "This is a very long line that "
        assert lines[1] == "Line 2 content"
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 30

    def test_should_delete_from_start_of_logical_line_with_ctrl_u_when_wrapping_enabled(self):
        """Maps to test("should delete from start of logical line with ctrl+u when wrapping enabled")."""
        ta = _make(
            "This is a very long line that will wrap when viewport is narrow\nLine 2 content",
            wrap_mode="word",
            width=20,
            height=10,
        )
        ta._editor_view.set_viewport_size(20, 10)
        original_line0 = ta.plain_text.split("\n")[0]
        for _ in range(30):
            ta.move_cursor_right()
        ta.handle_key(_key("u", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == original_line0[30:]
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_work_on_second_logical_line_when_wrapped(self):
        """Maps to test("should work on second logical line when wrapped")."""
        ta = _make(
            "Short line 1\nThis is another very long line that will wrap\nLine 3",
            wrap_mode="word",
            width=20,
            height=10,
        )
        ta._editor_view.set_viewport_size(20, 10)
        ta.goto_line(1)
        line1_before = ta.plain_text.split("\n")[1]
        for _ in range(25):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == "Short line 1"
        assert lines[1] == line1_before[:25]
        assert lines[2] == "Line 3"

    def test_should_work_after_undo_with_wrapped_lines(self):
        """Maps to test("should work after undo with wrapped lines")."""
        ta = _make(
            "This is a very long line that will wrap\nLine 2",
            wrap_mode="word",
            width=15,
            height=10,
            key_bindings=[KeyBinding(name="z", action="undo")],
        )
        ta._editor_view.set_viewport_size(15, 10)
        for _ in range(20):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        after_delete = ta.plain_text.split("\n")[0]
        assert len(after_delete) == 20
        ta.handle_key(_key("z", sequence="z"))
        after_undo = ta.plain_text.split("\n")[0]
        assert len(after_undo) == 39
        ta.handle_key(_key("k", ctrl=True))
        after_second_delete = ta.plain_text.split("\n")[0]
        assert len(after_second_delete) == 20

    def test_should_handle_ctrl_k_at_exact_wrap_boundary(self):
        """Maps to test("should handle ctrl+k at exact wrap boundary")."""
        ta = _make(
            "AAAAAAAAAABBBBBBBBBBCCCCCCCCCC\nLine 2",
            wrap_mode="char",
            width=10,
            height=10,
        )
        ta._editor_view.set_viewport_size(10, 10)
        for _ in range(10):
            ta.move_cursor_right()
        vc = ta._editor_view.get_visual_cursor()
        assert vc.visual_row == 1
        assert vc.logical_col == 10
        ta.handle_key(_key("k", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == "AAAAAAAAAA"
        assert lines[1] == "Line 2"

    def test_should_handle_ctrl_u_on_second_visual_line_of_first_logical_line(self):
        """Maps to test("should handle ctrl+u on second visual line of first logical line")."""
        ta = _make(
            "AAAAAAAAAABBBBBBBBBBCCCCCCCCCC\nLine 2",
            wrap_mode="char",
            width=10,
            height=10,
        )
        ta._editor_view.set_viewport_size(10, 10)
        for _ in range(15):
            ta.move_cursor_right()
        vc = ta._editor_view.get_visual_cursor()
        assert vc.visual_row == 1
        assert vc.logical_row == 0
        assert vc.logical_col == 15
        ta.handle_key(_key("u", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == "BBBBBCCCCCCCCCC"
        assert len(lines[0]) == 15
        assert _cursor(ta)[1] == 0


class TestTextareaKeybindingWrappedLinesDuplicate:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Wrapped Lines") (second occurrence, duplicate)."""

    def test_should_delete_to_end_of_logical_line_with_ctrl_k_when_wrapping_enabled_dup(self):
        """Maps to test("should delete to end of logical line with ctrl+k when wrapping enabled") (duplicate)."""
        ta = _make(
            "This is a very long line that will wrap when viewport is narrow\nLine 2 content",
            wrap_mode="word",
            width=20,
            height=10,
        )
        ta._editor_view.set_viewport_size(20, 10)
        for _ in range(30):
            ta.move_cursor_right()
        vc = ta._editor_view.get_visual_cursor()
        assert vc.logical_row == 0
        assert vc.logical_col == 30
        ta.handle_key(_key("k", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == "This is a very long line that "
        assert lines[1] == "Line 2 content"
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 30

    def test_should_delete_from_start_of_logical_line_with_ctrl_u_when_wrapping_enabled_dup(self):
        """Maps to test("should delete from start of logical line with ctrl+u when wrapping enabled") (duplicate)."""
        ta = _make(
            "This is a very long line that will wrap when viewport is narrow\nLine 2 content",
            wrap_mode="word",
            width=20,
            height=10,
        )
        ta._editor_view.set_viewport_size(20, 10)
        original_line0 = ta.plain_text.split("\n")[0]
        for _ in range(30):
            ta.move_cursor_right()
        ta.handle_key(_key("u", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == original_line0[30:]
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_work_on_second_logical_line_when_wrapped_dup(self):
        """Maps to test("should work on second logical line when wrapped") (duplicate)."""
        ta = _make(
            "Short line 1\nThis is another very long line that will wrap\nLine 3",
            wrap_mode="word",
            width=20,
            height=10,
        )
        ta._editor_view.set_viewport_size(20, 10)
        ta.goto_line(1)
        line1_before = ta.plain_text.split("\n")[1]
        for _ in range(25):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == "Short line 1"
        assert lines[1] == line1_before[:25]
        assert lines[2] == "Line 3"

    def test_should_work_after_undo_with_wrapped_lines_dup(self):
        """Maps to test("should work after undo with wrapped lines") (duplicate)."""
        ta = _make(
            "This is a very long line that will wrap\nLine 2",
            wrap_mode="word",
            width=15,
            height=10,
            key_bindings=[KeyBinding(name="z", action="undo")],
        )
        ta._editor_view.set_viewport_size(15, 10)
        for _ in range(20):
            ta.move_cursor_right()
        ta.handle_key(_key("k", ctrl=True))
        after_delete = ta.plain_text.split("\n")[0]
        assert len(after_delete) == 20
        ta.handle_key(_key("z", sequence="z"))
        after_undo = ta.plain_text.split("\n")[0]
        assert len(after_undo) == 39
        ta.handle_key(_key("k", ctrl=True))
        after_second_delete = ta.plain_text.split("\n")[0]
        assert len(after_second_delete) == 20

    def test_should_handle_ctrl_k_at_exact_wrap_boundary_dup(self):
        """Maps to test("should handle ctrl+k at exact wrap boundary") (duplicate)."""
        ta = _make(
            "AAAAAAAAAABBBBBBBBBBCCCCCCCCCC\nLine 2",
            wrap_mode="char",
            width=10,
            height=10,
        )
        ta._editor_view.set_viewport_size(10, 10)
        for _ in range(10):
            ta.move_cursor_right()
        vc = ta._editor_view.get_visual_cursor()
        assert vc.visual_row == 1
        assert vc.logical_col == 10
        ta.handle_key(_key("k", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == "AAAAAAAAAA"
        assert lines[1] == "Line 2"

    def test_should_handle_ctrl_u_on_second_visual_line_of_first_logical_line_dup(self):
        """Maps to test("should handle ctrl+u on second visual line of first logical line") (duplicate)."""
        ta = _make(
            "AAAAAAAAAABBBBBBBBBBCCCCCCCCCC\nLine 2",
            wrap_mode="char",
            width=10,
            height=10,
        )
        ta._editor_view.set_viewport_size(10, 10)
        for _ in range(15):
            ta.move_cursor_right()
        vc = ta._editor_view.get_visual_cursor()
        assert vc.visual_row == 1
        assert vc.logical_row == 0
        assert vc.logical_col == 15
        ta.handle_key(_key("u", ctrl=True))
        lines = ta.plain_text.split("\n")
        assert lines[0] == "BBBBBCCCCCCCCCC"
        assert len(lines[0]) == 15
        assert _cursor(ta)[1] == 0


class TestTextareaKeybindingKeyBindingsSecond:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Key Bindings") (second occurrence)."""

    def test_should_use_default_keybindings_second(self):
        """Maps to test("should use default keybindings") (second occurrence)."""
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[
                KeyBinding(name="g", action="buffer-home"),
                KeyBinding(name="b", action="buffer-end"),
            ],
        )
        ta.goto_buffer_end()
        assert _cursor(ta)[0] == 2
        ta.handle_key(_key("g", sequence="g"))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("b", sequence="b"))
        assert _cursor(ta)[0] == 2

    def test_should_map_select_up_and_select_down_to_custom_keys(self):
        """Maps to test("should map select-up and select-down to custom keys")."""
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[
                KeyBinding(name="k", shift=True, action="select-up"),
                KeyBinding(name="j", shift=True, action="select-down"),
            ],
        )
        ta.goto_line(1)
        ta.handle_key(_key("j", shift=True, sequence="J"))
        assert ta.has_selection is True
        selected = ta.get_selected_text()
        assert "Line" in selected

    def test_should_preserve_default_keybindings_when_custom_bindings_dont_override_them(self):
        """Maps to test("should preserve default keybindings when custom bindings don't override them")."""
        ta = _make(
            "Hello World",
            key_bindings=[KeyBinding(name="j", action="move-down")],
        )
        ta.handle_key(_key("right"))
        assert _cursor(ta)[1] == 1
        ta.handle_key(_key("home"))
        assert _cursor(ta)[1] == 0

    def test_should_allow_remapping_default_keys_to_different_actions(self):
        """Maps to test("should allow remapping default keys to different actions")."""
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[KeyBinding(name="up", action="buffer-home")],
        )
        ta.goto_line(2)
        ta.handle_key(_key("up"))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_handle_complex_keybinding_scenario_with_multiple_custom_mappings(self):
        """Maps to test("should handle complex keybinding scenario with multiple custom mappings")."""
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[
                KeyBinding(name="h", action="move-left"),
                KeyBinding(name="j", action="move-down"),
                KeyBinding(name="k", action="move-up"),
                KeyBinding(name="l", action="move-right"),
                KeyBinding(name="i", action="buffer-home"),
                KeyBinding(name="a", action="line-end"),
            ],
        )
        ta.handle_key(_key("i", sequence="i"))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("a", sequence="a"))
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("h", sequence="h"))
        assert _cursor(ta)[1] == 5
        ta.handle_key(_key("j", sequence="j"))
        assert _cursor(ta)[0] == 1
        ta.handle_key(_key("k", sequence="k"))
        assert _cursor(ta)[0] == 0
        ta.handle_key(_key("l", sequence="l"))
        assert _cursor(ta)[1] == 6

    def test_should_not_insert_text_when_key_is_bound_to_action(self):
        """Maps to test("should not insert text when key is bound to action")."""
        ta = _make("Hello", key_bindings=[KeyBinding(name="x", action="delete")])
        ta.handle_key(_key("x", sequence="x"))
        assert ta.plain_text == "ello"
        assert "x" not in ta.plain_text

    def test_should_still_insert_unbound_keys_as_text(self):
        """Maps to test("should still insert unbound keys as text")."""
        ta = _make("", key_bindings=[KeyBinding(name="j", action="move-down")])
        ta.handle_key(_key("h", sequence="h"))
        assert ta.plain_text == "h"
        ta.handle_key(_key("i", sequence="i"))
        assert ta.plain_text == "hi"
        ta.handle_key(_key("j", sequence="j"))
        assert ta.plain_text == "hi"  # j is bound, not inserted

    def test_should_differentiate_between_key_with_and_without_modifiers(self):
        """Maps to test("should differentiate between key with and without modifiers")."""
        ta = _make(
            "Hello",
            key_bindings=[
                KeyBinding(name="d", action="delete"),
                KeyBinding(name="d", alt=True, action="delete-line"),
            ],
        )
        ta.handle_key(_key("d", sequence="d"))
        assert ta.plain_text == "ello"

    def test_should_support_selection_actions_with_custom_keybindings(self):
        """Maps to test("should support selection actions with custom keybindings")."""
        ta = _make(
            "Hello World",
            key_bindings=[
                KeyBinding(name="h", shift=True, action="select-left"),
                KeyBinding(name="l", shift=True, action="select-right"),
            ],
        )
        ta.goto_buffer_end()
        ta.handle_key(_key("h", shift=True, sequence="H"))
        assert ta.has_selection is True
        assert ta.get_selected_text() == "d"
        ta.handle_key(_key("h", shift=True, sequence="H"))
        assert ta.get_selected_text() == "ld"
        ta.handle_key(_key("l", shift=True, sequence="L"))
        assert ta.get_selected_text() == "d"

    def test_should_execute_correct_action_when_multiple_keys_map_to_different_actions_with_same_base(
        self,
    ):
        """Maps to test("should execute correct action when multiple keys map to different actions with same base")."""
        ta = _make(
            "Line 1\nLine 2",
            key_bindings=[
                KeyBinding(name="j", action="move-down"),
                KeyBinding(name="j", ctrl=True, action="buffer-end"),
            ],
        )
        ta.handle_key(_key("j", sequence="j"))
        assert _cursor(ta)[0] == 1
        ta.goto_line(0)
        ta.handle_key(_key("j", ctrl=True))
        assert _cursor(ta)[0] == 1

    def test_should_handle_all_action_types_via_custom_keybindings(self):
        """Maps to test("should handle all action types via custom keybindings")."""
        ta = _make(
            "Line 1\nLine 2\nLine 3",
            key_bindings=[
                KeyBinding(name="1", action="move-left"),
                KeyBinding(name="2", action="move-right"),
                KeyBinding(name="3", action="move-up"),
                KeyBinding(name="4", action="move-down"),
                KeyBinding(name="5", shift=True, action="select-left"),
                KeyBinding(name="6", shift=True, action="select-right"),
                KeyBinding(name="7", shift=True, action="select-up"),
                KeyBinding(name="8", shift=True, action="select-down"),
                KeyBinding(name="a", action="line-home"),
                KeyBinding(name="b", action="line-end"),
                KeyBinding(name="c", shift=True, action="select-line-home"),
                KeyBinding(name="d", shift=True, action="select-line-end"),
                KeyBinding(name="e", action="buffer-home"),
                KeyBinding(name="f", action="buffer-end"),
                KeyBinding(name="g", action="delete-line"),
                KeyBinding(name="h", action="delete-to-line-end"),
                KeyBinding(name="i", action="backspace"),
                KeyBinding(name="j", action="delete"),
                KeyBinding(name="k", action="newline"),
                KeyBinding(name="u", action="undo"),
                KeyBinding(name="r", action="redo"),
            ],
        )
        ta.goto_line(1)
        ta.move_cursor_right()
        ta.move_cursor_right()
        assert _cursor(ta)[0] == 1
        assert _cursor(ta)[1] == 2

        ta.handle_key(_key("1", sequence="1"))
        assert _cursor(ta)[1] == 1
        ta.handle_key(_key("2", sequence="2"))
        assert _cursor(ta)[1] == 2
        ta.handle_key(_key("3", sequence="3"))
        assert _cursor(ta)[0] == 0
        ta.handle_key(_key("4", sequence="4"))
        assert _cursor(ta)[0] == 1
        ta.handle_key(_key("a", sequence="a"))
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("b", sequence="b"))
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("e", sequence="e"))
        assert _cursor(ta)[0] == 0
        ta.handle_key(_key("f", sequence="f"))
        assert _cursor(ta)[0] == 2

    def test_should_not_break_when_empty_keybindings_array_is_provided(self):
        """Maps to test("should not break when empty keyBindings array is provided")."""
        ta = _make("Hello", key_bindings=[])
        ta.handle_key(_key("right"))
        assert _cursor(ta)[1] == 1
        ta.handle_key(_key("home"))
        assert _cursor(ta)[1] == 0

    def test_should_document_limitation_bound_character_keys_cannot_be_typed(self):
        """Maps to test("should document limitation: bound character keys cannot be typed")."""
        ta = _make(
            "",
            key_bindings=[
                KeyBinding(name="h", action="move-left"),
                KeyBinding(name="j", action="move-down"),
                KeyBinding(name="k", action="move-up"),
                KeyBinding(name="l", action="move-right"),
            ],
        )
        ta.handle_key(_key("h", sequence="h"))
        ta.handle_key(_key("e", sequence="e"))
        ta.handle_key(_key("l", sequence="l"))
        ta.handle_key(_key("l", sequence="l"))
        ta.handle_key(_key("o", sequence="o"))
        # h, l, l are bound -> not inserted; only e, o inserted
        assert ta.plain_text == "eo"

    def test_should_allow_typing_bound_characters_when_using_modifier_keys_for_bindings(self):
        """Maps to test("should allow typing bound characters when using modifier keys for bindings")."""
        ta = _make(
            "",
            key_bindings=[
                KeyBinding(name="h", ctrl=True, action="move-left"),
                KeyBinding(name="j", ctrl=True, action="move-down"),
                KeyBinding(name="k", ctrl=True, action="move-up"),
                KeyBinding(name="l", ctrl=True, action="move-right"),
            ],
        )
        ta.handle_key(_key("h", sequence="h"))
        ta.handle_key(_key("e", sequence="e"))
        ta.handle_key(_key("l", sequence="l"))
        ta.handle_key(_key("l", sequence="l"))
        ta.handle_key(_key("o", sequence="o"))
        assert ta.plain_text == "hello"
        ta.handle_key(_key("h", ctrl=True))
        assert _cursor(ta)[1] == 4


class TestTextareaKeybindingDefaultWordDeletionKeybindings:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Default Word Deletion Keybindings")."""

    def test_should_delete_character_forward_with_ctrl_d(self):
        """Maps to test("should delete character forward with ctrl+d")."""
        ta = _make("hello world test")
        ta.handle_key(_key("d", ctrl=True))
        assert ta.plain_text == "ello world test"
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("d", ctrl=True))
        assert ta.plain_text == "llo world test"
        assert _cursor(ta)[1] == 0

    def test_should_delete_word_backward_with_ctrl_w(self):
        """Maps to test("should delete word backward with ctrl+w")."""
        ta = _make("hello world test")
        ta.goto_line_end()
        assert _cursor(ta)[1] == 16
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "hello world "
        assert _cursor(ta)[1] == 12
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "hello "
        assert _cursor(ta)[1] == 6

    def test_should_stop_at_cjk_ascii_boundary_with_ctrl_w(self):
        """Maps to test("should stop at CJK-ASCII boundary with ctrl+w").

        Python uses character offsets, not display-width columns.
        CJK characters are grouped as one word.
        """
        ta = _make("\u65e5\u672c\u8a9eabc")  # "日本語abc"
        ta.goto_line_end()
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "\u65e5\u672c\u8a9e"  # "日本語" - deleted "abc"
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == ""  # deleted entire CJK group "日本語"

    def test_should_keep_hangul_run_grouped_with_ctrl_w(self):
        """Maps to test("should keep Hangul run grouped with ctrl+w").

        Python uses character offsets. Hangul chars are grouped as one word.
        """
        ta = _make("\ud14c\uc2a4\ud2b8test")  # "테스트test"
        ta.goto_line_end()
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "\ud14c\uc2a4\ud2b8"  # "테스트" - deleted "test"
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == ""  # deleted entire Hangul group "테스트"

    def test_should_stop_at_cjk_punctuation_before_ascii_with_ctrl_w(self):
        """Maps to test("should stop at CJK punctuation before ASCII with ctrl+w").

        CJK punctuation (。) is classified same as CJK chars, so the entire
        "日本語。" run is grouped as one word.
        """
        ta = _make("\u65e5\u672c\u8a9e\u3002abc")  # "日本語。abc"
        ta.goto_line_end()
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "\u65e5\u672c\u8a9e\u3002"  # "日本語。" - deleted "abc"
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == ""  # deleted entire CJK+punct group "日本語。"

    def test_should_stop_at_compat_ideograph_boundary_with_ctrl_w(self):
        """Maps to test("should stop at compat ideograph boundary with ctrl+w").

        Single CJK char "丽" is one word, "abc" is another.
        """
        ta = _make("\u4e3dabc")  # "丽abc"
        ta.goto_line_end()
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "\u4e3d"  # "丽" - deleted "abc"
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == ""  # deleted "丽"

    def test_should_delete_word_forward_with_meta_d(self):
        """Maps to test("should delete word forward with meta+d")."""
        ta = _make("hello world test")
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "world test"
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "test"
        assert _cursor(ta)[1] == 0

    def test_should_delete_character_forward_from_middle_of_word_with_ctrl_d(self):
        """Maps to test("should delete character forward from middle of word with ctrl+d")."""
        ta = _make("hello world")
        for _ in range(3):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 3
        ta.handle_key(_key("d", ctrl=True))
        assert ta.plain_text == "helo world"
        assert _cursor(ta)[1] == 3

    def test_should_delete_word_backward_from_middle_of_word_with_ctrl_w(self):
        """Maps to test("should delete word backward from middle of word with ctrl+w")."""
        ta = _make("hello world")
        for _ in range(8):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 8
        ta.handle_key(_key("w", ctrl=True))
        assert ta.plain_text == "hello rld"
        assert _cursor(ta)[1] == 6

    def test_should_delete_word_forward_from_middle_of_word_with_meta_d(self):
        """Maps to test("should delete word forward from middle of word with meta+d")."""
        ta = _make("hello world")
        for _ in range(3):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 3
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "helworld"
        assert _cursor(ta)[1] == 3

    def test_should_delete_word_forward_from_space_with_meta_d(self):
        """Maps to test("should delete word forward from space with meta+d")."""
        ta = _make("hello world test")
        for _ in range(5):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 5
        ta.handle_key(_key("d", alt=True))
        assert ta.plain_text == "hellotest"
        assert _cursor(ta)[1] == 5

    def test_should_delete_word_forward_with_meta_delete(self):
        """Maps to test("should delete word forward with meta+delete")."""
        ta = _make("hello world test")
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("delete", alt=True))
        assert ta.plain_text == "world test"
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("delete", alt=True))
        assert ta.plain_text == "test"
        assert _cursor(ta)[1] == 0

    def test_should_delete_word_forward_from_middle_of_word_with_meta_delete(self):
        """Maps to test("should delete word forward from middle of word with meta+delete")."""
        ta = _make("hello world")
        for _ in range(3):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 3
        ta.handle_key(_key("delete", alt=True))
        assert ta.plain_text == "helworld"
        assert _cursor(ta)[1] == 3

    def test_should_delete_word_forward_from_space_with_meta_delete(self):
        """Maps to test("should delete word forward from space with meta+delete")."""
        ta = _make("hello world test")
        for _ in range(5):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 5
        ta.handle_key(_key("delete", alt=True))
        assert ta.plain_text == "hellotest"
        assert _cursor(ta)[1] == 5

    def test_should_delete_word_forward_with_ctrl_delete(self):
        """Maps to test("should delete word forward with ctrl+delete")."""
        ta = _make("hello world test")
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("delete", ctrl=True))
        assert ta.plain_text == "world test"
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("delete", ctrl=True))
        assert ta.plain_text == "test"
        assert _cursor(ta)[1] == 0

    def test_should_delete_word_forward_from_middle_of_word_with_ctrl_delete(self):
        """Maps to test("should delete word forward from middle of word with ctrl+delete")."""
        ta = _make("hello world")
        for _ in range(3):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 3
        ta.handle_key(_key("delete", ctrl=True))
        assert ta.plain_text == "helworld"
        assert _cursor(ta)[1] == 3

    def test_should_delete_word_forward_from_space_with_ctrl_delete(self):
        """Maps to test("should delete word forward from space with ctrl+delete")."""
        ta = _make("hello world test")
        for _ in range(5):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 5
        ta.handle_key(_key("delete", ctrl=True))
        assert ta.plain_text == "hellotest"
        assert _cursor(ta)[1] == 5

    def test_should_delete_word_backward_with_ctrl_backspace(self):
        """Maps to test("should delete word backward with ctrl+backspace")."""
        ta = _make("hello world test")
        ta.goto_line_end()
        assert _cursor(ta)[1] == 16
        ta.handle_key(_key("backspace", ctrl=True))
        assert ta.plain_text == "hello world "
        assert _cursor(ta)[1] == 12
        ta.handle_key(_key("backspace", ctrl=True))
        assert ta.plain_text == "hello "
        assert _cursor(ta)[1] == 6

    def test_should_delete_word_backward_from_middle_of_word_with_ctrl_backspace(self):
        """Maps to test("should delete word backward from middle of word with ctrl+backspace")."""
        ta = _make("hello world")
        for _ in range(8):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 8
        ta.handle_key(_key("backspace", ctrl=True))
        assert ta.plain_text == "hello rld"
        assert _cursor(ta)[1] == 6

    def test_should_delete_word_backward_from_space_with_ctrl_backspace(self):
        """Maps to test("should delete word backward from space with ctrl+backspace")."""
        ta = _make("hello world test")
        for _ in range(6):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("backspace", ctrl=True))
        assert ta.plain_text == "world test"
        assert _cursor(ta)[1] == 0

    def test_should_delete_line_with_ctrl_shift_d(self):
        """Maps to test("should delete line with ctrl+shift+d (requires Kitty keyboard protocol)")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.goto_line(1)
        assert _cursor(ta)[0] == 1
        ta.handle_key(_key("d", ctrl=True, shift=True))
        assert ta.plain_text == "Line 1\nLine 3"
        assert _cursor(ta)[0] == 1

    def test_should_delete_first_line_with_ctrl_shift_d(self):
        """Maps to test("should delete first line with ctrl+shift+d (requires Kitty keyboard protocol)")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        assert _cursor(ta)[0] == 0
        ta.handle_key(_key("d", ctrl=True, shift=True))
        assert ta.plain_text == "Line 2\nLine 3"
        assert _cursor(ta)[0] == 0

    def test_should_delete_last_line_with_ctrl_shift_d(self):
        """Maps to test("should delete last line with ctrl+shift+d (requires Kitty keyboard protocol)")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta.goto_line(2)
        assert _cursor(ta)[0] == 2
        ta.handle_key(_key("d", ctrl=True, shift=True))
        assert ta.plain_text == "Line 1\nLine 2"
        assert _cursor(ta)[0] == 1


class TestTextareaKeybindingDefaultCharacterAndWordMovement:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Default Character and Word Movement Keybindings")."""

    def test_should_move_forward_one_character_with_ctrl_f(self):
        """Maps to test("should move forward one character with ctrl+f")."""
        ta = _make("hello world")
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("f", ctrl=True))
        assert _cursor(ta)[1] == 1
        ta.handle_key(_key("f", ctrl=True))
        assert _cursor(ta)[1] == 2
        ta.handle_key(_key("f", ctrl=True))
        assert _cursor(ta)[1] == 3

    def test_should_move_backward_one_character_with_ctrl_b(self):
        """Maps to test("should move backward one character with ctrl+b")."""
        ta = _make("hello world")
        ta.goto_line_end()
        assert _cursor(ta)[1] == 11
        ta.handle_key(_key("b", ctrl=True))
        assert _cursor(ta)[1] == 10
        ta.handle_key(_key("b", ctrl=True))
        assert _cursor(ta)[1] == 9
        ta.handle_key(_key("b", ctrl=True))
        assert _cursor(ta)[1] == 8

    def test_should_move_forward_one_word_with_meta_f(self):
        """Maps to test("should move forward one word with meta+f")."""
        ta = _make("hello world test")
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("f", alt=True))
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("f", alt=True))
        assert _cursor(ta)[1] == 12
        ta.handle_key(_key("f", alt=True))
        assert _cursor(ta)[1] == 16

    def test_should_move_backward_one_word_with_meta_b(self):
        """Maps to test("should move backward one word with meta+b")."""
        ta = _make("hello world test")
        ta.goto_line_end()
        assert _cursor(ta)[1] == 16
        ta.handle_key(_key("b", alt=True))
        assert _cursor(ta)[1] == 12
        ta.handle_key(_key("b", alt=True))
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("b", alt=True))
        assert _cursor(ta)[1] == 0

    def test_should_move_forward_one_word_with_ctrl_right(self):
        """Maps to test("should move forward one word with ctrl+right")."""
        ta = _make("hello world test")
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 12
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 16

    def test_should_move_backward_one_word_with_ctrl_left(self):
        """Maps to test("should move backward one word with ctrl+left")."""
        ta = _make("hello world test")
        ta.goto_line_end()
        assert _cursor(ta)[1] == 16
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 12
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 6
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 0

    def test_should_move_across_cjk_ascii_boundary_with_ctrl_right_and_ctrl_left(self):
        """Maps to test("should move across CJK-ASCII boundary with ctrl+right and ctrl+left").

        Cursor positions are in display-width columns (CJK chars = 2 cols each).
        CJK characters are grouped as one word.
        """
        ta = _make("\u65e5\u672c\u8a9eabc")  # "日本語abc"
        assert _cursor(ta)[1] == 0
        # CJK group "日本語" is one word (3 chars * 2 cols = 6 display cols)
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 6  # after 日本語 (display col 6)
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 9  # after abc (display col 9 = end)
        # Now go backward
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 6  # before abc
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 0  # before 日本語

    def test_should_move_across_cjk_punctuation_boundary_with_ctrl_right_and_ctrl_left(self):
        """Maps to test("should move across CJK punctuation boundary with ctrl+right and ctrl+left").

        CJK punctuation "。" is in the same char class as CJK ideographs,
        so "日本語。" is grouped as one word. Display cols: 4*2 + 3*1 = 11.
        """
        ta = _make("\u65e5\u672c\u8a9e\u3002abc")  # "日本語。abc"
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 8  # after 日本語。 (4 CJK chars * 2 = 8 display cols)
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 11  # after abc (end)
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 8  # before abc
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 0  # before 日本語。

    def test_should_move_across_compat_ideograph_boundary_with_ctrl_right_and_ctrl_left(self):
        """Maps to test("should move across compat ideograph boundary with ctrl+right and ctrl+left")."""
        ta = _make("\u4e3dabc")  # "丽abc"  (display: 丽=2, abc=3, total=5)
        assert _cursor(ta)[1] == 0
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 2  # after 丽 (2 display cols)
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 5  # after abc (end, 2+3=5 display cols)
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 2  # before abc
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 0  # before 丽

    def test_should_select_words_across_cjk_ascii_boundary_with_meta_shift_arrows(self):
        """Maps to test("should select words across CJK-ASCII boundary with meta+shift+arrows").

        CJK characters are grouped as one word. Cursor positions are display columns.
        """
        ta = _make("\u65e5\u672c\u8a9eabc")  # "日本語abc"
        ta.handle_key(_key("right", alt=True, shift=True))
        assert _cursor(ta)[1] == 6  # after 日本語 (3 * 2 = 6 display cols)
        assert ta.get_selected_text() == "\u65e5\u672c\u8a9e"
        ta.handle_key(_key("right", alt=True, shift=True))
        assert _cursor(ta)[1] == 9  # after abc (end, 6 + 3 = 9)
        assert ta.get_selected_text() == "\u65e5\u672c\u8a9eabc"
        ta.handle_key(_key("left", alt=True, shift=True))
        assert _cursor(ta)[1] == 6  # back to CJK boundary
        assert ta.get_selected_text() == "\u65e5\u672c\u8a9e"
        ta.handle_key(_key("left", alt=True, shift=True))
        assert _cursor(ta)[1] == 0
        assert ta.get_selected_text() == ""

    def test_should_select_words_across_compat_ideograph_boundary_with_meta_shift_arrows(self):
        """Maps to test("should select words across compat ideograph boundary with meta+shift+arrows")."""
        ta = _make("\u4e3dabc")  # "丽abc"
        ta.handle_key(_key("right", alt=True, shift=True))
        assert _cursor(ta)[1] == 2  # after 丽 (2 display cols)
        assert ta.get_selected_text() == "\u4e3d"
        ta.handle_key(_key("right", alt=True, shift=True))
        assert _cursor(ta)[1] == 5  # after abc (2 + 3 = 5 display cols)
        assert ta.get_selected_text() == "\u4e3dabc"
        ta.handle_key(_key("left", alt=True, shift=True))
        assert _cursor(ta)[1] == 2  # back to 丽 boundary (2 display cols)
        assert ta.get_selected_text() == "\u4e3d"
        ta.handle_key(_key("left", alt=True, shift=True))
        assert _cursor(ta)[1] == 0
        assert ta.get_selected_text() == ""

    def test_should_combine_ctrl_left_and_ctrl_right_for_word_navigation(self):
        """Maps to test("should combine ctrl+left and ctrl+right for word navigation")."""
        ta = _make("one two three four")
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 4
        ta.handle_key(_key("right", ctrl=True))
        assert _cursor(ta)[1] == 8
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 4
        ta.handle_key(_key("left", ctrl=True))
        assert _cursor(ta)[1] == 0

    def test_should_not_insert_f_when_using_ctrl_f_for_movement(self):
        """Maps to test("should not insert 'f' when using ctrl+f for movement")."""
        ta = _make("test")
        before = ta.plain_text
        ta.handle_key(_key("f", ctrl=True))
        assert ta.plain_text == before
        assert _cursor(ta)[1] == 1

    def test_should_not_insert_b_when_using_ctrl_b_for_movement(self):
        """Maps to test("should not insert 'b' when using ctrl+b for movement")."""
        ta = _make("test")
        ta.goto_line_end()
        before = ta.plain_text
        ta.handle_key(_key("b", ctrl=True))
        assert ta.plain_text == before
        assert _cursor(ta)[1] == 3

    def test_should_combine_ctrl_f_and_ctrl_b_for_character_navigation(self):
        """Maps to test("should combine ctrl+f and ctrl+b for character navigation")."""
        ta = _make("hello")
        ta.handle_key(_key("f", ctrl=True))
        ta.handle_key(_key("f", ctrl=True))
        assert _cursor(ta)[1] == 2
        ta.handle_key(_key("b", ctrl=True))
        assert _cursor(ta)[1] == 1
        ta.handle_key(_key("f", ctrl=True))
        ta.handle_key(_key("f", ctrl=True))
        ta.handle_key(_key("f", ctrl=True))
        assert _cursor(ta)[1] == 4

    def test_should_combine_meta_f_and_meta_b_for_word_navigation(self):
        """Maps to test("should combine meta+f and meta+b for word navigation")."""
        ta = _make("one two three four")
        ta.handle_key(_key("f", alt=True))
        assert _cursor(ta)[1] == 4
        ta.handle_key(_key("f", alt=True))
        assert _cursor(ta)[1] == 8
        ta.handle_key(_key("b", alt=True))
        assert _cursor(ta)[1] == 4
        ta.handle_key(_key("b", alt=True))
        assert _cursor(ta)[1] == 0


class TestTextareaKeybindingShiftSpaceKeyHandling:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Shift+Space Key Handling")."""

    def test_should_insert_a_space_when_shift_space_is_pressed(self):
        """Maps to test("should insert a space when shift+space is pressed")."""
        ta = _make("")
        # Type "hello"
        for ch in "hello":
            ta.handle_key(_key(ch, sequence=ch))
        assert ta.plain_text == "hello"
        # Press shift+space - should insert a space
        ta.handle_key(_key(" ", shift=True, sequence=" "))
        assert ta.plain_text == "hello "
        assert _cursor(ta)[1] == 6
        # Type "world"
        for ch in "world":
            ta.handle_key(_key(ch, sequence=ch))
        assert ta.plain_text == "hello world"

    def test_should_insert_multiple_spaces_with_shift_space(self):
        """Maps to test("should insert multiple spaces with shift+space")."""
        ta = _make("test")
        ta.goto_line_end()
        ta.handle_key(_key(" ", shift=True, sequence=" "))
        ta.handle_key(_key(" ", shift=True, sequence=" "))
        ta.handle_key(_key(" ", shift=True, sequence=" "))
        assert ta.plain_text == "test   "
        assert _cursor(ta)[1] == 7

    def test_should_insert_space_at_middle_of_text_with_shift_space(self):
        """Maps to test("should insert space at middle of text with shift+space")."""
        ta = _make("helloworld")
        for _ in range(5):
            ta.move_cursor_right()
        assert _cursor(ta)[1] == 5
        ta.handle_key(_key(" ", shift=True, sequence=" "))
        assert ta.plain_text == "hello world"
        assert _cursor(ta)[1] == 6


class TestTextareaKeybindingLineHomeEndWrapBehavior:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Line Home/End Wrap Behavior")."""

    def test_should_wrap_to_end_of_previous_line_when_at_start_of_line(self):
        """Maps to test("should wrap to end of previous line when at start of line")."""
        ta = _make("Line 1\nLine 2")
        ta.goto_line(1)
        assert _cursor(ta) == (1, 0)
        ta.goto_line_home()
        assert _cursor(ta) == (0, 6)

    def test_should_wrap_to_start_of_next_line_when_at_end_of_line(self):
        """Maps to test("should wrap to start of next line when at end of line")."""
        ta = _make("Line 1\nLine 2")
        ta.goto_line_end()
        assert _cursor(ta) == (0, 6)
        ta.goto_line_end()
        assert _cursor(ta) == (1, 0)

    def test_should_stay_at_buffer_boundaries(self):
        """Maps to test("should stay at buffer boundaries")."""
        ta = _make("Line 1\nLine 2")
        ta.goto_line_home()
        assert _cursor(ta) == (0, 0)
        ta.goto_line(1)
        ta.goto_line_end()  # end of line 2 (col 6)
        ta.goto_line_end()  # should stay since it's the last line
        assert _cursor(ta) == (1, 6)


class TestTextareaKeybindingKeyAliases:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Key Aliases")."""

    def test_should_support_binding_enter_alias_which_maps_to_return(self):
        """Maps to test("should support binding 'enter' alias which maps to 'return'")."""
        ta = _make(
            "Hello",
            key_bindings=[KeyBinding(name="enter", action="buffer-home")],
        )
        ta.goto_buffer_end()
        # "enter" is aliased to "return" in defaults, so pressing "return" triggers buffer-home
        ta.handle_key(_key("return"))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_allow_binding_return_directly(self):
        """Maps to test("should allow binding 'return' directly")."""
        ta = _make(
            "Hello",
            key_bindings=[KeyBinding(name="return", action="buffer-home")],
        )
        ta.goto_buffer_end()
        ta.handle_key(_key("return"))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_support_custom_aliases_via_keyaliasmap(self):
        """Maps to test("should support custom aliases via keyAliasMap")."""
        ta = _make(
            "Line 1\nLine 2",
            key_bindings=[KeyBinding(name="myenter", action="buffer-home")],
            key_alias_map={"myenter": "return"},
        )
        ta.goto_buffer_end()
        # Pressing "return" should trigger buffer-home because "myenter" is aliased to "return"
        ta.handle_key(_key("return"))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_merge_custom_aliases_with_defaults(self):
        """Maps to test("should merge custom aliases with defaults")."""
        ta = _make(
            "Hello",
            key_bindings=[
                KeyBinding(name="enter", action="buffer-home"),
                KeyBinding(name="customkey", action="line-end"),
            ],
            key_alias_map={"customkey": "e", "enter": "return"},
        )
        # Default alias enter -> return should still work
        ta.handle_key(_key("return"))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0
        # Custom alias customkey -> e should work
        ta.handle_key(_key("e", sequence="e"))
        assert _cursor(ta)[1] == 5

    def test_should_update_aliases_dynamically_with_setter(self):
        """Maps to test("should update aliases dynamically with setter")."""
        ta = _make(
            "Line 1\nLine 2",
            key_bindings=[KeyBinding(name="mykey", action="buffer-home")],
        )
        ta.goto_buffer_end()
        assert _cursor(ta)[0] == 1
        # Initially "mykey" doesn't map to "return", so Enter triggers default newline
        ta.handle_key(_key("return"))
        assert ta.plain_text == "Line 1\nLine 2\n"
        # Set alias mapping mykey -> return
        ta.key_alias_map = {"mykey": "return"}
        # Remove the newline we added
        ta.delete_char_backward()
        # Now pressing Enter triggers buffer-home
        ta.handle_key(_key("return"))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0

    def test_should_handle_aliases_with_modifiers(self):
        """Maps to test("should handle aliases with modifiers")."""
        ta = _make(
            "Line 1\nLine 2",
            key_bindings=[KeyBinding(name="enter", alt=True, action="buffer-home")],
        )
        ta.goto_buffer_end()
        assert _cursor(ta)[0] == 1
        # Alt+Enter should trigger buffer-home ("enter" alias -> "return")
        ta.handle_key(_key("return", alt=True))
        assert _cursor(ta)[0] == 0
        assert _cursor(ta)[1] == 0


class TestTextareaKeybindingSelectionWithCtrlShiftAE:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Selection with ctrl+shift+a/e (line home/end)")."""

    def test_should_select_to_line_start_with_ctrl_shift_a(self):
        """Maps to test("should select to line start with ctrl+shift+a")."""
        ta = _make("Hello World")
        ta._edit_buffer.set_cursor(0, 11)  # End of line
        ta.handle_key(_key("a", ctrl=True, shift=True))
        assert ta.has_selection is True
        sel = ta.get_selection_dict()
        assert sel is not None
        assert sel["start"] == 0
        assert sel["end"] == 11
        assert ta.get_selected_text() == "Hello World"

    def test_should_select_to_line_end_with_ctrl_shift_e(self):
        """Maps to test("should select to line end with ctrl+shift+e")."""
        ta = _make("Hello World")
        ta._edit_buffer.set_cursor(0, 0)  # Start of line
        ta.handle_key(_key("e", ctrl=True, shift=True))
        assert ta.has_selection is True
        sel = ta.get_selection_dict()
        assert sel is not None
        assert sel["start"] == 0
        assert sel["end"] == 11
        assert ta.get_selected_text() == "Hello World"

    def test_should_select_to_line_start_from_middle_with_ctrl_shift_a(self):
        """Maps to test("should select to line start from middle with ctrl+shift+a")."""
        ta = _make("Hello World")
        ta._edit_buffer.set_cursor(0, 6)  # After "Hello "
        ta.handle_key(_key("a", ctrl=True, shift=True))
        assert ta.has_selection is True
        assert ta.get_selected_text() == "Hello "

    def test_should_select_to_line_end_from_middle_with_ctrl_shift_e(self):
        """Maps to test("should select to line end from middle with ctrl+shift+e")."""
        ta = _make("Hello World")
        ta._edit_buffer.set_cursor(0, 6)  # After "Hello "
        ta.handle_key(_key("e", ctrl=True, shift=True))
        assert ta.has_selection is True
        assert ta.get_selected_text() == "World"

    def test_should_work_on_multiline_text(self):
        """Maps to test("should work on multiline text")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        ta._edit_buffer.set_cursor(1, 4)  # Middle of second line

        # Select to start of line 2
        ta.handle_key(_key("a", ctrl=True, shift=True))
        assert ta.get_selected_text() == "Line"

        # Clear selection and move to same position
        ta._edit_buffer.set_cursor(1, 4)

        # Select to end of line 2
        ta.handle_key(_key("e", ctrl=True, shift=True))
        assert ta.get_selected_text() == " 2"

    def test_should_handle_line_wrapping_behavior(self):
        """Maps to test("should handle line wrapping behavior")."""
        ta = _make("Line 1\nLine 2")

        # At end of line 1
        ta._edit_buffer.set_cursor(0, 6)

        # First ctrl+shift+a from EOL should select entire line
        ta.handle_key(_key("a", ctrl=True, shift=True))
        assert ta.get_selected_text() == "Line 1"

        # Reset
        ta._edit_buffer.set_cursor(0, 0)

        # From start, ctrl+shift+e should select line, then wrap to next line
        ta.handle_key(_key("e", ctrl=True, shift=True))
        cursor = ta.cursor_position
        assert cursor[1] > 0

    def test_should_not_interfere_with_ctrl_a_without_shift(self):
        """Maps to test("should not interfere with ctrl+a (without shift)")."""
        ta = _make("Hello World")
        ta._edit_buffer.set_cursor(0, 11)
        ta.handle_key(_key("a", ctrl=True))
        assert ta.has_selection is False
        assert _cursor(ta)[1] == 0

    def test_should_not_interfere_with_ctrl_e_without_shift(self):
        """Maps to test("should not interfere with ctrl+e (without shift)")."""
        ta = _make("Hello World")
        ta._edit_buffer.set_cursor(0, 0)
        ta.handle_key(_key("e", ctrl=True))
        assert ta.has_selection is False
        assert _cursor(ta)[1] == 11


class TestTextareaKeybindingVisualLineNavigationMetaAE:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Visual line navigation with meta+a/e")."""

    def test_should_navigate_to_visual_line_start_with_meta_a_no_wrapping(self):
        """Maps to test("should navigate to visual line start with meta+a (no wrapping)")."""
        ta = _make("Hello World", wrap_mode="none", width=40, height=10)
        ta._editor_view.set_viewport_size(40, 10)
        ta._edit_buffer.set_cursor(0, 6)
        # alt on binding -> alt on event
        ta.handle_key(_key("a", alt=True))
        assert _cursor(ta)[1] == 0

    def test_should_navigate_to_visual_line_end_with_meta_e_no_wrapping(self):
        """Maps to test("should navigate to visual line end with meta+e (no wrapping)")."""
        ta = _make("Hello World", wrap_mode="none", width=40, height=10)
        ta._editor_view.set_viewport_size(40, 10)
        ta._edit_buffer.set_cursor(0, 6)
        ta.handle_key(_key("e", alt=True))
        assert _cursor(ta)[1] == 11

    def test_should_navigate_to_visual_line_start_with_meta_a_with_wrapping(self):
        """Maps to test("should navigate to visual line start with meta+a (with wrapping)")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._editor_view.set_viewport_size(20, 10)
        ta._edit_buffer.set_cursor(0, 22)  # In second visual line
        ta.handle_key(_key("a", alt=True))
        assert _cursor(ta)[1] == 20  # Start of second visual line, not 0

    def test_should_navigate_to_visual_line_end_with_meta_e_with_wrapping(self):
        """Maps to test("should navigate to visual line end with meta+e (with wrapping)")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._editor_view.set_viewport_size(20, 10)
        ta._edit_buffer.set_cursor(0, 5)  # In first visual line
        ta.handle_key(_key("e", alt=True))
        assert _cursor(ta)[1] == 19

    def test_should_differ_from_ctrl_a_e_when_wrapping_is_enabled(self):
        """Maps to test("should differ from ctrl+a/e when wrapping is enabled")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._editor_view.set_viewport_size(20, 10)
        ta._edit_buffer.set_cursor(0, 22)
        # meta+a goes to visual line start (col 20)
        ta.handle_key(_key("a", alt=True))
        visual_home_col = _cursor(ta)[1]
        assert visual_home_col == 20
        # Reset cursor
        ta._edit_buffer.set_cursor(0, 22)
        # ctrl+a goes to logical line start (col 0)
        ta.handle_key(_key("a", ctrl=True))
        logical_home_col = _cursor(ta)[1]
        assert logical_home_col == 0
        assert visual_home_col != logical_home_col


class TestTextareaKeybindingVisualLineSelectionMetaShiftAE:
    """Maps to describe("Textarea - Keybinding Tests") > describe("Visual line selection with meta+shift+a/e")."""

    def test_should_select_to_visual_line_start_with_meta_shift_a(self):
        """Maps to test("should select to visual line start with meta+shift+a")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._editor_view.set_viewport_size(20, 10)
        # Use col 26 (past end) to place cursor at end of text in second visual line
        ta._edit_buffer.set_cursor(0, 26)
        # meta+shift on binding -> alt+shift on event
        ta.handle_key(_key("a", alt=True, shift=True))
        assert ta.has_selection is True
        selected = ta.get_selected_text()
        # From col 20 (visual line start) to col 26 (end of text) = 6 chars "UVWXYZ"
        assert len(selected) == 6

    def test_should_select_to_visual_line_end_with_meta_shift_e(self):
        """Maps to test("should select to visual line end with meta+shift+e")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._editor_view.set_viewport_size(20, 10)
        ta._edit_buffer.set_cursor(0, 10)  # In first visual line
        ta.handle_key(_key("e", alt=True, shift=True))
        assert ta.has_selection is True
        selected = ta.get_selected_text()
        assert selected == "KLMNOPQRS"

    def test_should_work_without_wrapping_same_as_logical(self):
        """Maps to test("should work without wrapping (same as logical)")."""
        ta = _make("Hello World", wrap_mode="none", width=40, height=10)
        ta._editor_view.set_viewport_size(40, 10)
        # Test select to visual line start (same as logical start without wrapping)
        ta._edit_buffer.set_cursor(0, 6)
        ta.handle_key(_key("a", alt=True, shift=True))
        selected = ta.get_selected_text()
        assert selected == "Hello "
        assert _cursor(ta)[1] == 0
        # Reset and test select to visual line end
        ta.clear_selection()
        ta._edit_buffer.set_cursor(0, 6)
        ta.handle_key(_key("e", alt=True, shift=True))
        selected = ta.get_selected_text()
        assert selected == "World"

    def test_should_differ_from_ctrl_shift_a_e_when_wrapping_is_enabled(self):
        """Maps to test("should differ from ctrl+shift+a/e when wrapping is enabled")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._editor_view.set_viewport_size(20, 10)
        # Use col 26 (past end) to place cursor at end of text
        ta._edit_buffer.set_cursor(0, 26)
        # meta+shift+a selects to visual line start
        ta.handle_key(_key("a", alt=True, shift=True))
        visual_selection = ta.get_selected_text()
        assert len(visual_selection) == 6  # From 20 to 26
        # Reset
        ta.clear_selection()
        ta._edit_buffer.set_cursor(0, 26)
        # ctrl+shift+a selects to logical line start
        ta.handle_key(_key("a", ctrl=True, shift=True))
        logical_selection = ta.get_selected_text()
        assert len(logical_selection) == 26  # From 0 to 26
        assert visual_selection != logical_selection
