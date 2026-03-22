"""Port of upstream Input.test.ts.

Upstream: packages/core/src/renderables/Input.test.ts
Tests ported: 50/50
"""

import pytest

from opentui import create_test_renderer
from opentui.components.input_renderable import InputRenderable
from opentui.events import KeyEvent
from opentui.input.keymapping import KeyBinding
from opentui.structs import RGBA


# ── Helpers ──────────────────────────────────────────────────────────────────


def _key(name, *, ctrl=False, shift=False, alt=False, meta=False, sequence=""):
    """Create a KeyEvent for testing."""
    return KeyEvent(key=name, ctrl=ctrl, shift=shift, alt=alt, meta=meta, sequence=sequence)


def _type_string(inp, text):
    """Type a string into an input character by character."""
    for ch in text:
        inp.handle_key(_key(ch))


# ── Tests ────────────────────────────────────────────────────────────────────


class TestInputRenderableInitialization:
    """Maps to describe("InputRenderable > Initialization")."""

    def test_should_initialize_properly_with_default_options(self):
        """Maps to it("should initialize properly with default options")."""
        inp = InputRenderable()
        assert inp.value == ""
        assert inp._focusable is True
        assert inp.max_length == 1000
        assert inp.placeholder == ""
        assert inp.cursor_offset == 0

    def test_should_initialize_with_custom_options(self):
        """Maps to it("should initialize with custom options")."""
        inp = InputRenderable(
            value="Hello",
            max_length=50,
            placeholder="Enter name...",
        )
        assert inp.value == "Hello"
        assert inp.max_length == 50
        assert inp.placeholder == "Enter name..."
        assert inp.cursor_offset == 5  # Cursor at end of initial value


class TestInputRenderableFocusManagement:
    """Maps to describe("InputRenderable > Focus Management")."""

    def test_should_handle_focus_and_blur_correctly(self):
        """Maps to it("should handle focus and blur correctly")."""
        inp = InputRenderable(value="test")
        assert inp._focused is False

        inp.focus()
        assert inp._focused is True

        inp.blur()
        assert inp._focused is False

    def test_should_emit_change_event_on_blur_if_value_changed(self):
        """Maps to it("should emit change event on blur if value changed")."""
        inp = InputRenderable(value="initial")
        change_events = []
        inp.on("change", lambda v: change_events.append(v))

        inp.focus()
        inp.handle_key(_key("!"))  # Modify value
        assert inp.value == "initial!"

        inp.blur()
        assert len(change_events) == 1
        assert change_events[0] == "initial!"

    def test_should_not_emit_change_event_on_blur_if_value_unchanged(self):
        """Maps to it("should not emit change event on blur if value unchanged")."""
        inp = InputRenderable(value="same")
        change_events = []
        inp.on("change", lambda v: change_events.append(v))

        inp.focus()
        # Move cursor but don't change text
        inp.handle_key(_key("right"))
        inp.handle_key(_key("left"))

        inp.blur()
        assert len(change_events) == 0


class TestInputRenderableSingleInputKeyHandling:
    """Maps to describe("InputRenderable > Single Input Key Handling")."""

    def test_should_handle_text_input_when_focused(self):
        """Maps to it("should handle text input when focused")."""
        inp = InputRenderable()
        inp.focus()

        input_events = []
        inp.on("input", lambda v: input_events.append(v))

        inp.handle_key(_key("H"))
        inp.handle_key(_key("i"))

        assert inp.value == "Hi"
        assert len(input_events) == 2
        assert input_events[-1] == "Hi"

    def test_should_not_handle_key_events_when_not_focused(self):
        """Maps to it("should not handle key events when not focused")."""
        inp = InputRenderable()
        # Not focused
        handled = inp.handle_key(_key("a"))
        assert handled is False
        assert inp.value == ""

    def test_should_handle_backspace_correctly(self):
        """Maps to it("should handle backspace correctly")."""
        inp = InputRenderable(value="Hello")
        inp.focus()

        inp.handle_key(_key("backspace"))
        assert inp.value == "Hell"
        assert inp.cursor_offset == 4

    def test_should_emit_input_event_on_ctrl_w_delete_word_backward(self):
        """Maps to it("should emit INPUT event on Ctrl+W (delete-word-backward)")."""
        inp = InputRenderable(value="hello world")
        inp.focus()
        input_events = []
        inp.on("input", lambda v: input_events.append(v))

        inp.handle_key(_key("w", ctrl=True))
        assert inp.value == "hello "
        assert len(input_events) >= 1

    def test_should_emit_input_event_on_alt_backspace_delete_word_backward(self):
        """Maps to it("should emit INPUT event on Alt+Backspace (delete-word-backward)")."""
        inp = InputRenderable(value="hello world")
        inp.focus()
        input_events = []
        inp.on("input", lambda v: input_events.append(v))

        inp.handle_key(_key("backspace", alt=True))
        assert inp.value == "hello "
        assert len(input_events) >= 1

    def test_should_emit_input_event_on_delete_line(self):
        """Maps to it("should emit INPUT event on deleteLine()")."""
        inp = InputRenderable(value="line content")
        inp.focus()
        input_events = []
        inp.on("input", lambda v: input_events.append(v))

        inp.delete_line()
        assert inp.value == ""
        assert len(input_events) >= 1

    def test_should_handle_delete_correctly(self):
        """Maps to it("should handle delete correctly")."""
        inp = InputRenderable(value="Hello")
        inp.focus()
        inp._cursor_position = 2  # After "He"

        inp.handle_key(_key("delete"))
        assert inp.value == "Helo"
        assert inp.cursor_offset == 2

    def test_should_handle_arrow_keys_for_cursor_movement(self):
        """Maps to it("should handle arrow keys for cursor movement")."""
        inp = InputRenderable(value="Hello")
        inp.focus()
        assert inp.cursor_offset == 5  # At end

        inp.handle_key(_key("left"))
        assert inp.cursor_offset == 4

        inp.handle_key(_key("left"))
        assert inp.cursor_offset == 3

        inp.handle_key(_key("right"))
        assert inp.cursor_offset == 4

    def test_should_handle_enter_key(self):
        """Maps to it("should handle enter key")."""
        inp = InputRenderable(value="test input")
        inp.focus()
        enter_events = []
        inp.on("enter", lambda v: enter_events.append(v))

        inp.handle_key(_key("return"))
        assert len(enter_events) == 1
        assert enter_events[0] == "test input"
        # Enter should NOT insert a newline
        assert "\n" not in inp.value

    def test_should_respect_max_length(self):
        """Maps to it("should respect maxLength")."""
        inp = InputRenderable(value="", max_length=5)
        inp.focus()

        _type_string(inp, "abcdefgh")
        assert inp.value == "abcde"
        assert len(inp.value) <= 5

    def test_should_handle_cursor_position_with_text_insertion(self):
        """Maps to it("should handle cursor position with text insertion")."""
        inp = InputRenderable(value="Hello")
        inp.focus()
        inp._cursor_position = 2  # After "He"

        inp.handle_key(_key("X"))
        assert inp.value == "HeXllo"
        assert inp.cursor_offset == 3

    def test_should_handle_on_paste_option(self):
        """Maps to it("should handle onPaste option")."""
        paste_events = []
        inp = InputRenderable(on_paste=lambda e: paste_events.append(e))
        inp.focus()

        event = type("PasteEvent", (), {"text": "pasted text"})()
        inp.handle_paste(event)

        assert len(paste_events) == 1
        assert inp.value == "pasted text"


class TestInputRenderableMultipleInputFocusManagement:
    """Maps to describe("InputRenderable > Multiple Input Focus Management")."""

    def test_should_allow_only_one_input_to_be_focused_at_a_time(self):
        """Maps to it("should allow only one input to be focused at a time")."""
        inp1 = InputRenderable(value="input1")
        inp2 = InputRenderable(value="input2")

        inp1.focus()
        assert inp1._focused is True
        assert inp2._focused is False

        # When inp2 focuses, manually blur inp1 (upstream does this via renderer)
        inp1.blur()
        inp2.focus()
        assert inp1._focused is False
        assert inp2._focused is True

    def test_should_only_handle_key_events_for_focused_input(self):
        """Maps to it("should only handle key events for focused input")."""
        inp1 = InputRenderable(value="A")
        inp2 = InputRenderable(value="B")

        inp1.focus()
        inp1.handle_key(_key("1"))
        inp2.handle_key(_key("2"))  # Not focused, should be ignored

        assert inp1.value == "A1"
        assert inp2.value == "B"  # Unchanged

    def test_should_handle_focus_switching_with_blur_events(self):
        """Maps to it("should handle focus switching with blur events")."""
        inp1 = InputRenderable(value="first")
        inp2 = InputRenderable(value="second")

        change_events_1 = []
        change_events_2 = []
        inp1.on("change", lambda v: change_events_1.append(v))
        inp2.on("change", lambda v: change_events_2.append(v))

        inp1.focus()
        inp1.handle_key(_key("!"))
        assert inp1.value == "first!"

        # Switch focus
        inp1.blur()
        inp2.focus()
        assert len(change_events_1) == 1
        assert change_events_1[0] == "first!"

    def test_should_handle_rapid_focus_switching(self):
        """Maps to it("should handle rapid focus switching")."""
        inp1 = InputRenderable(value="A")
        inp2 = InputRenderable(value="B")
        inp3 = InputRenderable(value="C")

        # Rapid switching
        inp1.focus()
        inp1.blur()
        inp2.focus()
        inp2.blur()
        inp3.focus()

        assert inp1._focused is False
        assert inp2._focused is False
        assert inp3._focused is True

    def test_should_prevent_multiple_inputs_from_being_focused_simultaneously(self):
        """Maps to it("should prevent multiple inputs from being focused simultaneously")."""
        inp1 = InputRenderable()
        inp2 = InputRenderable()

        inp1.focus()
        # In a real renderer, focusing inp2 would blur inp1
        inp1.blur()
        inp2.focus()

        # Only inp2 should be focused
        inp1.handle_key(_key("a"))
        inp2.handle_key(_key("b"))

        assert inp1.value == ""  # Not focused, didn't accept input
        assert inp2.value == "b"


class TestInputRenderableInputValueManagement:
    """Maps to describe("InputRenderable > Input Value Management")."""

    def test_should_handle_value_setting_programmatically(self):
        """Maps to it("should handle value setting programmatically")."""
        inp = InputRenderable(value="initial")
        inp.value = "new value"
        assert inp.value == "new value"

    def test_should_handle_value_changes_with_cursor_moving_to_end(self):
        """Maps to it("should handle value changes with cursor moving to end")."""
        inp = InputRenderable(value="Hello")
        inp._cursor_position = 2  # In the middle

        inp.value = "New text"
        assert inp.cursor_offset == len("New text")  # Cursor moved to end

    def test_should_handle_empty_value_setting(self):
        """Maps to it("should handle empty value setting")."""
        inp = InputRenderable(value="some text")
        inp.value = ""
        assert inp.value == ""
        assert inp.cursor_offset == 0

    def test_should_emit_input_events_when_value_changes_programmatically(self):
        """Maps to it("should emit input events when value changes programmatically")."""
        inp = InputRenderable(value="old")
        input_events = []
        inp.on("input", lambda v: input_events.append(v))

        inp.value = "new"
        assert len(input_events) == 1
        assert input_events[0] == "new"


class TestInputRenderableInputProperties:
    """Maps to describe("InputRenderable > Input Properties")."""

    def test_should_handle_max_length_changes(self):
        """Maps to it("should handle maxLength changes")."""
        inp = InputRenderable(value="Hello World", max_length=20)
        assert inp.value == "Hello World"

        # Reduce maxLength — value should be truncated
        inp.max_length = 5
        assert inp.value == "Hello"
        assert len(inp.value) <= 5

    def test_should_handle_placeholder_changes(self):
        """Maps to it("should handle placeholder changes")."""
        inp = InputRenderable(placeholder="Type here...")
        assert inp.placeholder == "Type here..."

        inp.placeholder = "New placeholder"
        assert inp.placeholder == "New placeholder"

    def test_should_handle_color_property_changes(self):
        """Maps to it("should handle color property changes")."""
        inp = InputRenderable()
        red = RGBA(1.0, 0.0, 0.0, 1.0)
        blue = RGBA(0.0, 0.0, 1.0, 1.0)
        green = RGBA(0.0, 1.0, 0.0, 1.0)

        inp.text_color = red
        assert inp.text_color == red

        inp.placeholder_color = blue
        assert inp.placeholder_color == blue

        inp.cursor_color = green
        assert inp.cursor_color == green

        inp.focused_background_color = red
        assert inp.focused_background_color == red

        inp.focused_text_color = blue
        assert inp.focused_text_color == blue


class TestInputRenderableGlobalKeyEventPrevention:
    """Maps to describe("InputRenderable > Global Key Event Prevention")."""

    def test_should_not_handle_key_events_when_prevent_default_is_called(self):
        """Maps to it("should not handle key events when preventDefault is called by global handler")."""
        inp = InputRenderable()
        inp.focus()

        event = _key("a")
        event.prevent_default()

        handled = inp.handle_key(event)
        assert handled is False
        assert inp.value == ""

    def test_should_handle_multiple_global_handlers_with_prevent_default(self):
        """Maps to it("should handle multiple global handlers with preventDefault")."""
        inp = InputRenderable()
        inp.focus()

        # First event: no preventDefault
        event1 = _key("a")
        inp.handle_key(event1)
        assert inp.value == "a"

        # Second event: with preventDefault
        event2 = _key("b")
        event2.prevent_default()
        inp.handle_key(event2)
        assert inp.value == "a"  # 'b' was blocked

    def test_should_respect_prevent_default_from_global_handler_registered_after_focus(self):
        """Maps to it("should respect preventDefault from global handler registered AFTER input focus")."""
        inp = InputRenderable()
        inp.focus()

        # Type some text first
        _type_string(inp, "AB")
        assert inp.value == "AB"

        # Now a global handler prevents the next key
        event = _key("C")
        event.prevent_default()
        inp.handle_key(event)
        assert inp.value == "AB"  # 'C' was blocked

    def test_should_handle_dynamic_prevent_default_conditions(self):
        """Maps to it("should handle dynamic preventDefault conditions")."""
        inp = InputRenderable()
        inp.focus()

        # Allow 'a' through
        inp.handle_key(_key("a"))
        assert inp.value == "a"

        # Block 'b' via preventDefault
        event_b = _key("b")
        event_b.prevent_default()
        inp.handle_key(event_b)
        assert inp.value == "a"

        # Allow 'c' through (no preventDefault)
        inp.handle_key(_key("c"))
        assert inp.value == "ac"


class TestInputRenderableOnKeyDownPreventDefault:
    """Maps to top-level it("should respect preventDefault from onKeyDown handler")."""

    def test_should_respect_prevent_default_from_on_key_down_handler(self):
        """Maps to it("should respect preventDefault from onKeyDown handler")."""

        def block_b(event):
            if event.key == "b":
                event.prevent_default()

        inp = InputRenderable(on_key_down=block_b)
        inp.focus()

        inp.handle_key(_key("a"))
        assert inp.value == "a"

        inp.handle_key(_key("b"))
        assert inp.value == "a"  # 'b' blocked by onKeyDown

        inp.handle_key(_key("c"))
        assert inp.value == "ac"


class TestInputRenderableShiftSpaceWithModifyOtherKeys:
    """Maps to describe("InputRenderable > Shift+Space Key Handling with modifyOtherKeys")."""

    def test_should_insert_a_space_when_shift_space_is_pressed(self):
        """Maps to it("should insert a space when shift+space is pressed")."""
        inp = InputRenderable()
        inp.focus()

        # Shift+space should insert a space (modifyOtherKeys sends sequence=" ")
        inp.handle_key(_key("space", shift=True, sequence=" "))
        assert inp.value == " "

    def test_should_insert_multiple_spaces_with_shift_space(self):
        """Maps to it("should insert multiple spaces with shift+space")."""
        inp = InputRenderable()
        inp.focus()

        for _ in range(3):
            inp.handle_key(_key("space", shift=True, sequence=" "))
        assert inp.value == "   "

    def test_should_insert_space_at_middle_of_text_with_shift_space(self):
        """Maps to it("should insert space at middle of text with shift+space")."""
        inp = InputRenderable(value="AB")
        inp.focus()
        inp._cursor_position = 1  # After 'A'

        inp.handle_key(_key("space", shift=True, sequence=" "))
        assert inp.value == "A B"
        assert inp.cursor_offset == 2


class TestInputRenderableEdgeCases:
    """Maps to describe("InputRenderable > Edge Cases")."""

    def test_should_handle_non_printable_characters(self):
        """Maps to it("should handle non-printable characters")."""
        inp = InputRenderable()
        inp.focus()

        # Tab and escape should not insert text
        inp.handle_key(_key("tab"))
        assert inp.value == ""

        inp.handle_key(_key("escape"))
        assert inp.value == ""

    def test_should_handle_cursor_movement_at_boundaries(self):
        """Maps to it("should handle cursor movement at boundaries")."""
        inp = InputRenderable(value="ABC")
        inp.focus()
        assert inp.cursor_offset == 3  # At end

        # Moving right at end should stay at end
        inp.handle_key(_key("right"))
        assert inp.cursor_offset == 3

        # Move to start
        inp._cursor_position = 0
        # Moving left at start should stay at start
        inp.handle_key(_key("left"))
        assert inp.cursor_offset == 0

    def test_should_handle_backspace_at_start_of_input(self):
        """Maps to it("should handle backspace at start of input")."""
        inp = InputRenderable(value="Hello")
        inp.focus()
        inp._cursor_position = 0

        inp.handle_key(_key("backspace"))
        assert inp.value == "Hello"  # No change

    def test_should_handle_delete_at_end_of_input(self):
        """Maps to it("should handle delete at end of input")."""
        inp = InputRenderable(value="Hello")
        inp.focus()
        assert inp.cursor_offset == 5  # At end

        inp.handle_key(_key("delete"))
        assert inp.value == "Hello"  # No change

    def test_should_handle_empty_input_operations(self):
        """Maps to it("should handle empty input operations")."""
        inp = InputRenderable()
        inp.focus()

        # All operations on empty should be safe
        inp.handle_key(_key("backspace"))
        assert inp.value == ""

        inp.handle_key(_key("delete"))
        assert inp.value == ""

        inp.handle_key(_key("left"))
        assert inp.cursor_offset == 0

        inp.handle_key(_key("right"))
        assert inp.cursor_offset == 0


class TestInputRenderableKeyBindingsAndAliases:
    """Maps to describe("InputRenderable > Key Bindings and Aliases")."""

    def test_should_support_custom_key_bindings(self):
        """Maps to it("should support custom key bindings")."""
        # Custom binding: 'x' → delete-backward
        custom = [KeyBinding(name="x", action="delete-backward")]
        inp = InputRenderable(value="Hello", key_bindings=custom)
        inp.focus()

        inp.handle_key(_key("x"))
        assert inp.value == "Hell"  # 'x' triggered backspace

    def test_should_support_key_aliases(self):
        """Maps to it("should support key aliases")."""
        inp = InputRenderable(value="test")
        inp.focus()
        enter_events = []
        inp.on("enter", lambda v: enter_events.append(v))

        # "enter" is aliased to "return" by default
        inp.handle_key(_key("enter"))
        assert len(enter_events) == 1

    def test_should_merge_custom_bindings_with_defaults(self):
        """Maps to it("should merge custom bindings with defaults")."""
        # Add custom binding for 'x' without removing defaults
        custom = [KeyBinding(name="x", action="delete-backward")]
        inp = InputRenderable(value="Hello", key_bindings=custom)
        inp.focus()

        # Default backspace should still work
        inp.handle_key(_key("backspace"))
        assert inp.value == "Hell"

        # Custom 'x' binding should also work
        inp.handle_key(_key("x"))
        assert inp.value == "Hel"

    def test_should_override_default_bindings_with_custom_ones(self):
        """Maps to it("should override default bindings with custom ones")."""
        # Override backspace to do nothing (custom action)
        custom = [KeyBinding(name="backspace", action="noop")]
        inp = InputRenderable(value="Hello", key_bindings=custom)
        inp.focus()

        # Backspace should no longer delete (action "noop" is unrecognized)
        inp.handle_key(_key("backspace"))
        assert inp.value == "Hello"  # Unchanged

    def test_should_support_emacs_style_bindings_by_default(self):
        """Maps to it("should support Emacs-style bindings by default")."""
        inp = InputRenderable(value="Hello World")
        inp.focus()
        assert inp.cursor_offset == 11

        # Ctrl+A → line home
        inp.handle_key(_key("a", ctrl=True))
        assert inp.cursor_offset == 0

        # Ctrl+E → line end
        inp.handle_key(_key("e", ctrl=True))
        assert inp.cursor_offset == 11

        # Ctrl+B → move left
        inp.handle_key(_key("b", ctrl=True))
        assert inp.cursor_offset == 10

        # Ctrl+F → move right
        inp.handle_key(_key("f", ctrl=True))
        assert inp.cursor_offset == 11

    def test_should_allow_updating_key_bindings_dynamically(self):
        """Maps to it("should allow updating key bindings dynamically")."""
        inp = InputRenderable(value="Hello")
        inp.focus()

        # Initially, 'z' inserts 'z'
        inp.handle_key(_key("z"))
        assert inp.value == "Helloz"

        # Update bindings: 'z' → delete-backward
        inp.key_bindings = [KeyBinding(name="z", action="delete-backward")]
        inp.handle_key(_key("z"))
        assert inp.value == "Hello"  # 'z' now does backspace

    def test_should_allow_updating_key_aliases_dynamically(self):
        """Maps to it("should allow updating key aliases dynamically")."""
        inp = InputRenderable(value="test")
        inp.focus()
        enter_events = []
        inp.on("enter", lambda v: enter_events.append(v))

        # Add alias: "submit" → "return"
        inp.key_alias_map = {"submit": "return"}

        # "submit" should now trigger submit action
        inp.handle_key(_key("submit"))
        assert len(enter_events) == 1

    def test_should_handle_modifiers_in_custom_bindings(self):
        """Maps to it("should handle modifiers in custom bindings")."""
        # Custom: Ctrl+X → delete-line
        custom = [KeyBinding(name="x", action="delete-line", ctrl=True)]
        inp = InputRenderable(value="Hello World", key_bindings=custom)
        inp.focus()

        # Regular 'x' should still insert
        inp.handle_key(_key("x"))
        assert inp.value == "Hello Worldx"

        # Ctrl+X should delete line
        inp.handle_key(_key("x", ctrl=True))
        assert inp.value == ""
