"""Port of upstream Textarea.stress.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.stress.test.ts
Tests: 21 (21 real, 0 skipped)

In the upstream TypeScript tests, mouse events are injected as raw stdin bytes
and the tests verify that those bytes never corrupt the textarea buffer. In our
Python implementation, mouse events are handled at the renderer level and never
reach the TextareaRenderable's text buffer directly. So these tests verify the
same invariant: after various sequences of operations (typing, undo/redo,
focus/blur, pasting, etc.), the text buffer contains only valid typed content
and never contains escape sequences or raw mouse bytes.
"""

import re

from opentui.components.textarea import TextareaRenderable
from opentui.events import KeyEvent, PasteEvent


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


def _assert_no_corruption(ta: TextareaRenderable) -> None:
    """Assert that the text buffer does not contain escape sequences or mouse bytes."""
    text = ta.plain_text
    assert "\x1b" not in text, f"Found escape character in text: {text!r}"
    assert "[<" not in text, f"Found '[<' mouse prefix in text: {text!r}"


def _assert_no_mouse_pattern(text: str) -> None:
    """Assert the text does not contain mouse SGR coordinate patterns."""
    assert "\x1b" not in text
    assert "[<" not in text
    assert not re.search(r"\d+;\d+;\d+", text), f"Found coordinate pattern in: {text!r}"


# ═══════════════════════════════════════════════════════════════════════


class TestTextareaStress:
    """Textarea - Stress Tests"""

    def test_stress_rapid_mouse_movements_not_in_textarea_buffer(self):
        """Hundreds of rapid operations should not corrupt text buffer."""
        ta = _make("Initial text content")
        initial_text = ta.plain_text

        # Simulate 500 rapid cursor move operations (analogous to mouse moves
        # that in upstream are handled at renderer level)
        for i in range(500):
            # These operations don't modify text
            ta.move_cursor_right()
            ta.move_cursor_left()

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_thousands_mouse_events_per_second_no_corruption(self):
        """Thousands of non-editing operations should not corrupt textarea."""
        ta = _make("Test content")
        initial_text = ta.plain_text

        # 2000 cursor movement operations (mouse events don't reach textarea)
        for i in range(2000):
            ta.move_cursor_right()

        assert ta.plain_text == initial_text
        assert not re.search(r"\x1b|\[<|\d+;\d+", ta.plain_text)
        ta.destroy()

    def test_stress_mouse_movements_while_typing_no_mouse_bytes(self):
        """Interleaved typing should produce only typed characters."""
        ta = _make("")

        for i in range(100):
            ta.handle_key(_key("a"))
            # Cursor movement between keystrokes (analogous to mouse moves)
            ta.move_cursor_left()
            ta.move_cursor_right()
            ta.handle_key(_key("b"))
            ta.move_cursor_left()
            ta.move_cursor_right()

        # Should only contain typed characters
        assert re.match(r"^[ab]+$", ta.plain_text)
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_rapid_mouse_drags_no_byte_leak(self):
        """Rapid selection operations should not leak bytes into buffer."""
        ta = _make("Original")
        initial_text = ta.plain_text

        # Simulate drag operations (select and deselect)
        for i in range(10):
            start_col = i % 5
            end_col = (i + 3) % 8
            ta.set_selection(start_col, end_col)
            ta.clear_selection()

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_mouse_clicks_during_rapid_typing_no_corruption(self):
        """Typing with cursor repositioning should not corrupt buffer."""
        ta = _make("Start")

        for i in range(10):
            if i % 3 == 0:
                ta.handle_key(_key("x"))
            # Cursor repositioning (analogous to mouse click)
            line, col = ta.cursor_position
            ta._edit_buffer.set_cursor(0, i % 6)
            if i % 5 == 0:
                ta.handle_key(_key("y"))

        text = ta.plain_text
        assert "\x1b[<" not in text
        assert not re.search(r"\d+;\d+;\d+", text)
        ta.destroy()

    def test_stress_high_frequency_mouse_scroll_no_byte_injection(self):
        """Rapid cursor navigation (analogous to scroll) should not inject bytes."""
        ta = _make("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
        initial_text = ta.plain_text

        # Rapid up/down navigation (analogous to scroll)
        for i in range(500):
            if i % 2 == 0:
                ta.move_cursor_down()
            else:
                ta.move_cursor_up()

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_raw_stdin_mouse_sgr_sequences_filtered(self):
        """Raw mouse SGR-like strings passed as key events should not corrupt text.

        In Python, mouse events never reach the textarea. If someone tried to
        pass raw escape sequences as key names, handle_key would reject them
        because they aren't printable single characters.
        """
        ta = _make("Clean text")
        initial_text = ta.plain_text

        raw_mouse_sequences = [
            "\x1b[<35;20;5m",
            "\x1b[<0;10;3M",
            "\x1b[<0;10;3m",
            "\x1b[<35;25;7m",
            "\x1b[<64;15;2M",
            "\x1b[<65;15;2M",
        ]

        for _ in range(10):
            for seq in raw_mouse_sequences:
                # These would be rejected by handle_key (not printable single char)
                result = ta.handle_key(_key(seq))
                assert result is False

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_simultaneous_typing_and_mouse_flood(self):
        """Typing with frequent rejected events should produce correct text."""
        ta = _make("")

        typed_text = "hello world"
        type_index = 0

        for i in range(1000):
            # Every 100 iterations, type one character
            if i % 100 == 0 and type_index < len(typed_text):
                ta.handle_key(_key(typed_text[type_index]))
                type_index += 1

            # Rejected events (analogous to mouse flood -- mouse events
            # never reach textarea in Python; use multi-char key names
            # that handle_key rejects)
            raw_seq = f"\x1b[<35;{(i % 40) + 1};{(i % 10) + 1}m"
            ta.handle_key(_key(raw_seq))

        # Type remaining characters
        while type_index < len(typed_text):
            ta.handle_key(_key(typed_text[type_index]))
            type_index += 1

        assert ta.plain_text == typed_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_mouse_events_during_multiline_editing(self):
        """Multi-line editing with navigation should not corrupt buffer."""
        ta = _make("Line1\nLine2\nLine3")

        for i in range(500):
            if i % 100 == 0:
                ta.handle_key(_key("down"))
            if i % 150 == 0:
                ta.handle_key(_key("X"))
            # Cursor movement
            ta.move_cursor_right()
            ta.move_cursor_left()

        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_10000_raw_mouse_byte_injections_without_delay(self):
        """10000 rejected key events should not modify buffer."""
        ta = _make("Protected")
        initial_text = ta.plain_text

        for i in range(10000):
            x = (i % 40) + 1
            y = (i % 10) + 1
            raw_seq = f"\x1b[<35;{x};{y}m"
            result = ta.handle_key(_key(raw_seq))
            assert result is False

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        assert "35;" not in ta.plain_text
        ta.destroy()

    def test_stress_inject_mouse_bytes_between_every_character_typed(self):
        """Rejected events between typed characters should not affect text."""
        ta = _make("")

        to_type = "HelloWorld"
        for ch in to_type:
            # Inject 100 rejected key events before each character
            for j in range(100):
                raw_seq = f"\x1b[<35;{(j % 40) + 1};{(j % 10) + 1}m"
                ta.handle_key(_key(raw_seq))

            ta.handle_key(_key(ch))

            # Inject 100 rejected key events after each character
            for j in range(100):
                raw_seq = f"\x1b[<35;{(j % 40) + 1};{(j % 10) + 1}m"
                ta.handle_key(_key(raw_seq))

        assert ta.plain_text == to_type
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_extreme_burst_50000_mouse_events(self):
        """50000 rejected key events should not corrupt text."""
        ta = _make("Stable content")
        initial_text = ta.plain_text

        for i in range(50000):
            x = ((i * 17) % 40) + 1
            y = ((i * 11) % 10) + 1
            button_code = 35 + (i % 4)
            raw_seq = f"\x1b[<{button_code};{x};{y}m"
            ta.handle_key(_key(raw_seq))

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_partial_malformed_mouse_sequences(self):
        """Partial/malformed escape sequences should not corrupt text."""
        ta = _make("Clean")
        initial_text = ta.plain_text

        partial_sequences = [
            "\x1b[<35;",
            "\x1b[<35;20",
            "\x1b[<35;20;",
            "\x1b[<35;20;5",
            "\x1b",
            "\x1b[",
            "\x1b[<",
            "\x1b[<35;20;5m\x1b[<35;",
        ]

        for i in range(1000):
            seq = partial_sequences[i % len(partial_sequences)]
            ta.handle_key(_key(seq))

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_mouse_events_mixed_with_paste_operations(self):
        """Paste operations mixed with rejected events should only contain paste text."""
        ta = _make("")

        for i in range(100):
            # Rejected key events (analogous to mouse bytes)
            for j in range(50):
                raw_seq = f"\x1b[<35;{(j % 40) + 1};{(j % 10) + 1}m"
                ta.handle_key(_key(raw_seq))

            # Paste some text
            paste_text = f"Paste{i}"
            ta.insert_text(paste_text)

            # More rejected key events
            for j in range(50):
                raw_seq = f"\x1b[<0;{(j % 40) + 1};{(j % 10) + 1}M"
                ta.handle_key(_key(raw_seq))

        _assert_no_corruption(ta)
        assert "Paste" in ta.plain_text
        ta.destroy()

    def test_stress_focused_vs_unfocused_with_mouse_flood(self):
        """Focus/unfocus cycles with rejected events should not corrupt text."""
        ta = _make("Content")
        initial_text = ta.plain_text

        # Flood while unfocused
        ta.blur()
        for i in range(5000):
            raw_seq = f"\x1b[<35;{(i % 40) + 1};{(i % 10) + 1}m"
            ta.handle_key(_key(raw_seq))

        assert ta.plain_text == initial_text

        # Focus and flood
        ta.focus()
        for i in range(5000):
            raw_seq = f"\x1b[<35;{(i % 40) + 1};{(i % 10) + 1}m"
            ta.handle_key(_key(raw_seq))

        assert ta.plain_text == initial_text

        # Blur and flood again
        ta.blur()
        for i in range(5000):
            raw_seq = f"\x1b[<35;{(i % 40) + 1};{(i % 10) + 1}m"
            ta.handle_key(_key(raw_seq))

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_all_mouse_button_types_with_modifiers(self):
        """All button codes with all modifier combos should not corrupt text."""
        ta = _make("Test")
        initial_text = ta.plain_text

        button_codes = [0, 1, 2, 3, 32, 33, 34, 35, 36, 37, 38, 39, 64, 65, 66, 67]
        modifiers = [0, 4, 8, 12, 16, 20, 24, 28]

        for i in range(10000):
            button = button_codes[i % len(button_codes)]
            modifier = modifiers[int(i / len(button_codes)) % len(modifiers)]
            code = button | modifier
            x = (i % 40) + 1
            y = (i % 10) + 1
            suffix = "M" if i % 2 == 0 else "m"
            raw_seq = f"\x1b[<{code};{x};{y}{suffix}"
            ta.handle_key(_key(raw_seq))

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_mouse_data_split_across_multiple_buffers(self):
        """Split escape sequence fragments passed as complete sequences should not
        corrupt text.

        In the upstream TypeScript implementation, raw stdin bytes are split across
        multiple data events and the input parser reassembles and filters them. In
        Python, mouse events are handled at the renderer level. This test verifies
        that complete mouse SGR sequences (as multi-character key names) are
        correctly rejected by handle_key and never inserted into the buffer.
        """
        ta = _make("Original")
        initial_text = ta.plain_text

        # Send complete mouse SGR sequences as key names -- multi-character
        # key names are rejected by handle_key's printable-character gate
        complete_seqs = [
            "\x1b[<35;20;5m",
            "\x1b[<35;20;5M",
            "\x1b[<0;10;3m",
            "\x1b[<64;15;2M",
        ]
        for seq in complete_seqs:
            result = ta.handle_key(_key(seq))
            assert result is False

        assert ta.plain_text == initial_text
        assert "[<" not in ta.plain_text
        ta.destroy()

    def test_stress_alternating_mouse_and_keyboard_at_high_frequency(self):
        """Alternating rejected and accepted key events should produce correct text."""
        ta = _make("")

        chars = "abcdefghij"
        for i in range(1000):
            # Rejected event (analogous to mouse)
            raw_seq = f"\x1b[<35;{(i % 40) + 1};{(i % 10) + 1}m"
            ta.handle_key(_key(raw_seq))

            # Actual keyboard event
            if i % 100 == 0:
                ta.handle_key(_key(chars[int(i / 100) % len(chars)]))

            # Another rejected event
            raw_seq2 = f"\x1b[<0;{(i % 20) + 1};{(i % 5) + 1}M"
            ta.handle_key(_key(raw_seq2))

        assert re.match(r"^[a-j]*$", ta.plain_text)
        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_mouse_during_undo_redo_operations(self):
        """Undo/redo with rejected events interspersed should not corrupt text."""
        ta = _make("Start")

        # Make some edits with rejected events
        for i in range(100):
            ta.handle_key(_key("x"))
            for j in range(50):
                raw_seq = f"\x1b[<35;{(j % 40) + 1};{(j % 10) + 1}m"
                ta.handle_key(_key(raw_seq))

        # Undo with rejected events
        for i in range(50):
            ta.handle_key(_key("z", ctrl=True))
            for j in range(100):
                raw_seq = f"\x1b[<35;{(j % 40) + 1};{(j % 10) + 1}m"
                ta.handle_key(_key(raw_seq))

        _assert_no_corruption(ta)
        ta.destroy()

    def test_stress_100000_mouse_events_ultimate_stress(self):
        """100000 rejected key events - ultimate stress test."""
        ta = _make("Extreme test")
        initial_text = ta.plain_text

        for i in range(100000):
            x = ((i * 19) % 40) + 1
            y = ((i * 13) % 10) + 1
            code = 32 + (i % 8)
            raw_seq = f"\x1b[<{code};{x};{y}m"
            ta.handle_key(_key(raw_seq))

        assert ta.plain_text == initial_text
        _assert_no_corruption(ta)

        # Verify cursor position is still valid
        line, col = ta.cursor_position
        assert isinstance(line, int)
        assert isinstance(col, int)
        ta.destroy()

    def test_stress_concurrent_mouse_events_on_multiple_textareas(self):
        """Multiple textareas under stress should both maintain integrity."""
        ta1 = _make("Editor 1")
        ta2 = TextareaRenderable(initial_value="Editor 2")

        ta1.focus()
        text1 = ta1.plain_text
        text2 = ta2.plain_text

        for i in range(10000):
            raw_seq = f"\x1b[<35;{(i % 40) + 1};{(i % 10) + 1}m"
            ta1.handle_key(_key(raw_seq))
            ta2.handle_key(_key(raw_seq))

            # Switch focus occasionally
            if i % 500 == 0:
                if i % 1000 == 0:
                    ta2.blur()
                    ta1.focus()
                else:
                    ta1.blur()
                    ta2.focus()

        assert ta1.plain_text == text1
        assert ta2.plain_text == text2
        _assert_no_corruption(ta1)
        _assert_no_corruption(ta2)
        ta1.destroy()
        ta2.destroy()
