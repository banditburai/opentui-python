"""Port of upstream mock-keys.test.ts.

Upstream: packages/core/src/testing/mock-keys.test.ts
Tests ported: 113/113 (0 skipped)
"""

import time

import pytest

from opentui.testing.input import KeyCodes, MockKeys, MockRenderer, create_mock_keys


# ===========================================================================
# describe("mock-keys")
# ===========================================================================


class TestMockKeys:
    """Top-level describe('mock-keys')."""

    # ---- basic key emission -----------------------------------------------

    def test_press_keys_with_string_keys(self):
        """Maps to test("pressKeys with string keys")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_keys(["h", "e", "l", "l", "o"])
        assert mr.get_emitted_data() == "hello"

    def test_press_keys_with_key_codes(self):
        """Maps to test("pressKeys with KeyCodes")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_keys([KeyCodes.RETURN, KeyCodes.TAB])
        assert mr.get_emitted_data() == "\r\t"

    def test_press_key_with_string(self):
        """Maps to test("pressKey with string")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("a")
        assert mr.get_emitted_data() == "a"

    def test_press_key_with_key_code(self):
        """Maps to test("pressKey with KeyCode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ESCAPE)
        assert mr.get_emitted_data() == "\x1b"

    def test_type_text(self):
        """Maps to test("typeText")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.type_text("hello world")
        assert mr.get_emitted_data() == "hello world"

    def test_convenience_methods(self):
        """Maps to test("convenience methods")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_enter()
        mk.press_escape()
        mk.press_tab()
        mk.press_backspace()
        assert mr.get_emitted_data() == "\r\x1b\t\b"

    def test_press_arrow(self):
        """Maps to test("pressArrow")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_arrow("up")
        mk.press_arrow("down")
        mk.press_arrow("left")
        mk.press_arrow("right")
        assert mr.get_emitted_data() == "\x1b[A\x1b[B\x1b[D\x1b[C"

    def test_press_ctrl_c(self):
        """Maps to test("pressCtrlC")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_ctrl_c()
        assert mr.get_emitted_data() == "\x03"

    def test_arbitrary_string_keys_work(self):
        """Maps to test("arbitrary string keys work")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("x")
        mk.press_key("y")
        mk.press_key("z")
        assert mr.get_emitted_data() == "xyz"

    def test_key_codes_enum_values_work(self):
        """Maps to test("KeyCodes enum values work")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.RETURN)
        mk.press_key(KeyCodes.TAB)
        mk.press_key(KeyCodes.ESCAPE)
        assert mr.get_emitted_data() == "\r\t\x1b"

    # ---- data events / accumulation ---------------------------------------

    def test_data_events_are_properly_emitted(self):
        """Maps to test("data events are properly emitted")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        received: list[str] = []
        mr.stdin.on("data", lambda chunk: received.append(chunk))
        mk.press_key("a")
        mk.press_key(KeyCodes.RETURN)
        assert len(received) == 2
        assert received[0] == "a"
        assert received[1] == "\r"

    def test_multiple_data_events_accumulate_correctly(self):
        """Maps to test("multiple data events accumulate correctly")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        received: list[str] = []
        mr.stdin.on("data", lambda chunk: received.append(chunk))
        mk.type_text("hello")
        mk.press_enter()
        assert received == ["h", "e", "l", "l", "o", "\r"]

    def test_stream_write_method_emits_data_events_correctly(self):
        """Maps to test("stream write method emits data events correctly")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        emitted_chunks: list[str] = []
        mr.stdin.on("data", lambda chunk: emitted_chunks.append(chunk))
        mr.stdin.write("test")
        mr.stdin.write(KeyCodes.RETURN)
        assert len(emitted_chunks) == 2
        assert emitted_chunks[0] == "test"
        assert emitted_chunks[1] == "\r"

    def test_press_keys_with_delay_works(self):
        """Maps to test("pressKeys with delay works")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        timestamps: list[float] = []
        mr.stdin.on("data", lambda _: timestamps.append(time.time()))
        start_time = time.time()
        mk.press_keys(["a", "b"], 10)  # 10ms delay between keys
        total_elapsed = (time.time() - start_time) * 1000
        assert len(timestamps) == 2
        assert (timestamps[1] - timestamps[0]) * 1000 >= 8  # tolerance
        assert total_elapsed >= 8  # at least one delay interval

    # ---- modifier tests (regular mode) ------------------------------------

    def test_press_key_with_shift_modifier(self):
        """Maps to test("pressKey with shift modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_RIGHT, {"shift": True})
        assert mr.get_emitted_data() == "\x1b[1;2C"

    def test_press_key_with_ctrl_modifier(self):
        """Maps to test("pressKey with ctrl modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_LEFT, {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[1;5D"

    def test_press_key_with_shift_ctrl_modifiers(self):
        """Maps to test("pressKey with shift+ctrl modifiers")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_UP, {"shift": True, "ctrl": True})
        assert mr.get_emitted_data() == "\x1b[1;6A"

    def test_press_key_with_meta_modifier(self):
        """Maps to test("pressKey with meta modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_DOWN, {"meta": True})
        assert mr.get_emitted_data() == "\x1b[1;3B"

    def test_press_key_with_super_modifier(self):
        """Maps to test("pressKey with super modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_UP, {"super": True})
        assert mr.get_emitted_data() == "\x1b[1;9A"

    def test_press_key_with_hyper_modifier(self):
        """Maps to test("pressKey with hyper modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_LEFT, {"hyper": True})
        assert mr.get_emitted_data() == "\x1b[1;17D"

    def test_press_key_with_super_hyper_modifiers(self):
        """Maps to test("pressKey with super+hyper modifiers")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_RIGHT, {"super": True, "hyper": True})
        assert mr.get_emitted_data() == "\x1b[1;25C"

    def test_press_arrow_with_shift_modifier(self):
        """Maps to test("pressArrow with shift modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_arrow("right", {"shift": True})
        assert mr.get_emitted_data() == "\x1b[1;2C"

    def test_press_arrow_without_modifiers_still_works(self):
        """Maps to test("pressArrow without modifiers still works")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_arrow("left")
        assert mr.get_emitted_data() == "\x1b[D"

    def test_press_key_with_modifiers_on_home_key(self):
        """Maps to test("pressKey with modifiers on HOME key")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.HOME, {"shift": True})
        assert mr.get_emitted_data() == "\x1b[1;2H"

    def test_press_key_with_modifiers_on_end_key(self):
        """Maps to test("pressKey with modifiers on END key")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.END, {"shift": True})
        assert mr.get_emitted_data() == "\x1b[1;2F"

    def test_press_key_with_meta_on_regular_character(self):
        """Maps to test("pressKey with meta on regular character")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("a", {"meta": True})
        assert mr.get_emitted_data() == "\x1ba"

    def test_press_key_with_meta_shift_on_character(self):
        """Maps to test("pressKey with meta+shift on character")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("a", {"meta": True, "shift": True})
        assert mr.get_emitted_data() == "\x1bA"

    def test_press_key_with_meta_ctrl_on_arrow(self):
        """Maps to test("pressKey with meta+ctrl on arrow")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_RIGHT, {"meta": True, "ctrl": True})
        assert mr.get_emitted_data() == "\x1b[1;7C"

    def test_press_key_with_meta_shift_ctrl_on_arrow(self):
        """Maps to test("pressKey with meta+shift+ctrl on arrow")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key(KeyCodes.ARROW_UP, {"meta": True, "shift": True, "ctrl": True})
        assert mr.get_emitted_data() == "\x1b[1;8A"

    def test_press_arrow_with_meta_modifier(self):
        """Maps to test("pressArrow with meta modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_arrow("left", {"meta": True})
        assert mr.get_emitted_data() == "\x1b[1;3D"

    def test_press_arrow_with_meta_shift_modifiers(self):
        """Maps to test("pressArrow with meta+shift modifiers")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_arrow("down", {"meta": True, "shift": True})
        assert mr.get_emitted_data() == "\x1b[1;4B"

    def test_meta_modifier_produces_escape_sequences(self):
        """Maps to test("meta modifier produces escape sequences") (line 359)."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("a", {"meta": True})
        mk.press_key("z", {"meta": True})
        assert mr.get_emitted_data() == "\x1ba\x1bz"

    # ---- convenience method modifiers -------------------------------------

    def test_press_enter_with_modifiers(self):
        """Maps to test("pressEnter with modifiers")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_enter({"meta": True})
        assert mr.get_emitted_data() == "\x1b\r"

    def test_press_tab_with_shift_modifier(self):
        """Maps to test("pressTab with shift modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_tab({"shift": True})
        assert mr.get_emitted_data() == "\t"

    def test_press_escape_with_ctrl_modifier(self):
        """Maps to test("pressEscape with ctrl modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_escape({"ctrl": True})
        assert mr.get_emitted_data() == "\x1b"

    def test_press_backspace_with_meta_modifier(self):
        """Maps to test("pressBackspace with meta modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_backspace({"meta": True})
        assert mr.get_emitted_data() == "\x1b\b"

    # ---- ctrl on letters --------------------------------------------------

    def test_press_key_with_ctrl_on_letter_produces_control_code(self):
        """Maps to test("pressKey with ctrl on letter produces control code")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("a", {"ctrl": True})
        mk.press_key("z", {"ctrl": True})
        assert mr.get_emitted_data() == "\x01\x1a"

    def test_press_key_with_ctrl_on_uppercase_letter(self):
        """Maps to test("pressKey with ctrl on uppercase letter")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("A", {"ctrl": True})
        assert mr.get_emitted_data() == "\x01"

    def test_press_key_with_ctrl_meta_combination(self):
        """Maps to test("pressKey with ctrl+meta combination")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("a", {"ctrl": True, "meta": True})
        assert mr.get_emitted_data() == "\x1b\x01"

    def test_ctrl_modifier_produces_control_codes(self):
        """Maps to test("ctrl modifier produces control codes")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("a", {"ctrl": True})
        mk.press_key("c", {"ctrl": True})
        mk.press_key("d", {"ctrl": True})
        assert mr.get_emitted_data() == "\x01\x03\x04"

    def test_meta_modifier_produces_escape_sequences_duplicate(self):
        """Maps to test("meta modifier produces escape sequences") (line 444)."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("a", {"meta": True})
        mk.press_key("z", {"meta": True})
        assert mr.get_emitted_data() == "\x1ba\x1bz"

    def test_all_ctrl_letters_produce_correct_control_codes(self):
        """Maps to test("all CTRL_* letters produce correct control codes")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        letters = "abcdefghijklmnopqrstuvwxyz"
        for letter in letters:
            mk.press_key(letter, {"ctrl": True})
        expected = "".join(chr(ord(c) - 96) for c in letters)
        assert mr.get_emitted_data() == expected

    def test_press_key_with_ctrl_modifier_produces_control_code(self):
        """Maps to test("pressKey with ctrl modifier produces control code")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("c", {"ctrl": True})
        assert mr.get_emitted_data() == "\x03"

    def test_press_key_with_meta_modifier_on_letters_produces_escape_sequences(self):
        """Maps to test("pressKey with meta modifier on letters produces escape sequences")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("x", {"meta": True})
        assert mr.get_emitted_data() == "\x1bx"

    # ---- ctrl on special characters ---------------------------------------

    def test_press_key_with_ctrl_modifier_on_special_characters(self):
        """Maps to test("pressKey with ctrl modifier on special characters")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)

        # Ctrl+- -> \u001f (US, 31)
        mr.emitted_data = []
        mk.press_key("-", {"ctrl": True})
        assert mr.get_emitted_data() == "\u001f"

        # Ctrl+. -> \u001e (RS, 30)
        mr.emitted_data = []
        mk.press_key(".", {"ctrl": True})
        assert mr.get_emitted_data() == "\u001e"

        # Ctrl+, -> \u001c (FS, 28)
        mr.emitted_data = []
        mk.press_key(",", {"ctrl": True})
        assert mr.get_emitted_data() == "\u001c"

        # Ctrl+] -> \u001d (GS, 29)
        mr.emitted_data = []
        mk.press_key("]", {"ctrl": True})
        assert mr.get_emitted_data() == "\u001d"

        # Ctrl+[ -> \x1b (ESC, 27)
        mr.emitted_data = []
        mk.press_key("[", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b"

        # Ctrl+/ -> \u001f (US, 31)
        mr.emitted_data = []
        mk.press_key("/", {"ctrl": True})
        assert mr.get_emitted_data() == "\u001f"

        # Ctrl+_ -> \u001f (US, 31)
        mr.emitted_data = []
        mk.press_key("_", {"ctrl": True})
        assert mr.get_emitted_data() == "\u001f"

    def test_press_key_with_ctrl_modifier_on_all_special_control_characters(self):
        """Maps to test("pressKey with ctrl modifier on all special control characters")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)

        tests = [
            ("[", "\x1b"),  # ESC
            ("\\", "\x1c"),  # FS
            ("]", "\x1d"),  # GS
            ("^", "\x1e"),  # RS
            ("_", "\x1f"),  # US
            ("?", "\x7f"),  # DEL
            ("@", "\x00"),  # NUL
            (" ", "\x00"),  # NUL (Ctrl+Space)
        ]
        for key, expected in tests:
            mr.emitted_data = []
            mk.press_key(key, {"ctrl": True})
            assert mr.get_emitted_data() == expected, f"Ctrl+{key!r}"

    def test_press_key_with_ctrl_meta_on_special_characters(self):
        """Maps to test("pressKey with ctrl+meta on special characters")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)

        # Ctrl+Meta+- -> ESC + \u001f
        mr.emitted_data = []
        mk.press_key("-", {"ctrl": True, "meta": True})
        assert mr.get_emitted_data() == "\x1b\u001f"

        # Ctrl+Meta+] -> ESC + \u001d
        mr.emitted_data = []
        mk.press_key("]", {"ctrl": True, "meta": True})
        assert mr.get_emitted_data() == "\x1b\u001d"

    def test_press_key_with_ctrl_on_special_chars_does_not_use_kitty_keyboard(self):
        """Maps to test("pressKey with ctrl on special chars does NOT use kitty keyboard")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": False})
        mk.press_key("-", {"ctrl": True})
        data = mr.get_emitted_data()
        assert data == "\u001f"
        assert "[" not in data
        assert "u" not in data

    def test_comprehensive_all_punctuation_keys_with_ctrl_modifier(self):
        """Maps to test("comprehensive test: all punctuation keys work with ctrl modifier")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("-", {"ctrl": True})
        mk.press_key(".", {"ctrl": True})
        mk.press_key(",", {"ctrl": True})
        mk.press_key("]", {"ctrl": True})
        mk.press_key("[", {"ctrl": True})
        expected = "\u001f\u001e\u001c\u001d\x1b"
        assert mr.get_emitted_data() == expected

    def test_ctrl_modifier_with_non_mapped_characters_preserves_original(self):
        """Maps to test("ctrl modifier with non-mapped characters preserves original")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("(", {"ctrl": True})
        assert mr.get_emitted_data() == "("


# ===========================================================================
# describe("Kitty Keyboard Protocol Mode")
# ===========================================================================


class TestKittyKeyboardProtocolMode:
    """Maps to describe('Kitty Keyboard Protocol Mode')."""

    def test_basic_character_in_kitty_mode(self):
        """Maps to test("basic character in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("a")
        assert mr.get_emitted_data() == "\x1b[97u"

    def test_backspace_without_modifiers_in_kitty_mode(self):
        """Maps to test("backspace without modifiers in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_backspace()
        assert mr.get_emitted_data() == "\x1b[127u"

    def test_backspace_with_shift_in_kitty_mode(self):
        """Maps to test("backspace with shift in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_backspace({"shift": True})
        assert mr.get_emitted_data() == "\x1b[127;2u"

    def test_backspace_with_ctrl_in_kitty_mode(self):
        """Maps to test("backspace with ctrl in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_backspace({"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[127;5u"

    def test_backspace_with_meta_in_kitty_mode(self):
        """Maps to test("backspace with meta in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_backspace({"meta": True})
        assert mr.get_emitted_data() == "\x1b[127;3u"

    def test_backspace_with_shift_meta_in_kitty_mode(self):
        """Maps to test("backspace with shift+meta in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_backspace({"shift": True, "meta": True})
        assert mr.get_emitted_data() == "\x1b[127;4u"

    def test_delete_key_in_kitty_mode(self):
        """Maps to test("delete key in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("DELETE")
        assert mr.get_emitted_data() == "\x1b[57349u"

    def test_arrow_keys_in_kitty_mode(self):
        """Maps to test("arrow keys in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_arrow("up")
        mk.press_arrow("down")
        mk.press_arrow("left")
        mk.press_arrow("right")
        assert mr.get_emitted_data() == "\x1b[57352u\x1b[57353u\x1b[57350u\x1b[57351u"

    def test_arrow_key_with_shift_in_kitty_mode(self):
        """Maps to test("arrow key with shift in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_arrow("right", {"shift": True})
        assert mr.get_emitted_data() == "\x1b[57351;2u"

    def test_arrow_key_with_ctrl_in_kitty_mode(self):
        """Maps to test("arrow key with ctrl in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_arrow("left", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[57350;5u"

    def test_arrow_key_with_meta_in_kitty_mode(self):
        """Maps to test("arrow key with meta in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_arrow("down", {"meta": True})
        assert mr.get_emitted_data() == "\x1b[57353;3u"

    def test_arrow_key_with_shift_ctrl_meta_in_kitty_mode(self):
        """Maps to test("arrow key with shift+ctrl+meta in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_arrow("up", {"shift": True, "ctrl": True, "meta": True})
        # shift(1) + meta(2) + ctrl(4) = 7, +1 = 8
        assert mr.get_emitted_data() == "\x1b[57352;8u"

    def test_enter_return_in_kitty_mode(self):
        """Maps to test("enter/return in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_enter()
        assert mr.get_emitted_data() == "\x1b[13u"

    def test_enter_with_meta_in_kitty_mode(self):
        """Maps to test("enter with meta in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_enter({"meta": True})
        assert mr.get_emitted_data() == "\x1b[13;3u"

    def test_tab_in_kitty_mode(self):
        """Maps to test("tab in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_tab()
        assert mr.get_emitted_data() == "\x1b[9u"

    def test_tab_with_shift_in_kitty_mode(self):
        """Maps to test("tab with shift in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_tab({"shift": True})
        assert mr.get_emitted_data() == "\x1b[9;2u"

    def test_escape_in_kitty_mode(self):
        """Maps to test("escape in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_escape()
        assert mr.get_emitted_data() == "\x1b[27u"

    def test_home_key_in_kitty_mode(self):
        """Maps to test("home key in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("HOME")
        assert mr.get_emitted_data() == "\x1b[57356u"

    def test_home_with_shift_in_kitty_mode(self):
        """Maps to test("home with shift in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("HOME", {"shift": True})
        assert mr.get_emitted_data() == "\x1b[57356;2u"

    def test_end_key_in_kitty_mode(self):
        """Maps to test("end key in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("END")
        assert mr.get_emitted_data() == "\x1b[57357u"

    def test_function_keys_in_kitty_mode(self):
        """Maps to test("function keys in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("F1")
        mk.press_key("F2")
        mk.press_key("F12")
        assert mr.get_emitted_data() == "\x1b[57364u\x1b[57365u\x1b[57375u"

    def test_regular_characters_with_shift_in_kitty_mode(self):
        """Maps to test("regular characters with shift in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("a", {"shift": True})
        assert mr.get_emitted_data() == "\x1b[97;2u"

    def test_regular_characters_with_ctrl_in_kitty_mode(self):
        """Maps to test("regular characters with ctrl in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("c", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[99;5u"

    def test_regular_characters_with_meta_in_kitty_mode(self):
        """Maps to test("regular characters with meta in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("x", {"meta": True})
        assert mr.get_emitted_data() == "\x1b[120;3u"

    def test_multiple_keys_in_sequence_in_kitty_mode(self):
        """Maps to test("multiple keys in sequence in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("h")
        mk.press_key("i")
        assert mr.get_emitted_data() == "\x1b[104u\x1b[105u"

    def test_mixed_modifier_combinations_in_kitty_mode(self):
        """Maps to test("mixed modifier combinations in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("a")
        mk.press_key("a", {"shift": True})
        mk.press_key("a", {"ctrl": True})
        mk.press_key("a", {"meta": True})
        mk.press_key("a", {"shift": True, "ctrl": True})
        expected = (
            "\x1b[97u"  # no mods
            + "\x1b[97;2u"  # shift
            + "\x1b[97;5u"  # ctrl
            + "\x1b[97;3u"  # meta
            + "\x1b[97;6u"  # shift+ctrl
        )
        assert mr.get_emitted_data() == expected

    def test_character_with_super_modifier_in_kitty_mode(self):
        """Maps to test("character with super modifier in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("a", {"super": True})
        assert mr.get_emitted_data() == "\x1b[97;9u"

    def test_character_with_hyper_modifier_in_kitty_mode(self):
        """Maps to test("character with hyper modifier in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("a", {"hyper": True})
        assert mr.get_emitted_data() == "\x1b[97;17u"

    def test_character_with_super_hyper_modifiers_in_kitty_mode(self):
        """Maps to test("character with super+hyper modifiers in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("a", {"super": True, "hyper": True})
        assert mr.get_emitted_data() == "\x1b[97;25u"

    def test_character_with_all_modifiers_in_kitty_mode(self):
        """Maps to test("character with all modifiers in kitty mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("a", {"shift": True, "ctrl": True, "meta": True, "super": True, "hyper": True})
        # shift(1)+meta(2)+ctrl(4)+super(8)+hyper(16) = 31, +1 = 32
        assert mr.get_emitted_data() == "\x1b[97;32u"

    def test_kitty_mode_vs_regular_mode_comparison(self):
        """Maps to test("kitty mode vs regular mode comparison")."""
        kitty_mr = MockRenderer()
        regular_mr = MockRenderer()
        kitty_keys = create_mock_keys(kitty_mr, {"kittyKeyboard": True})
        regular_keys = create_mock_keys(regular_mr, {"kittyKeyboard": False})

        kitty_keys.press_backspace({"shift": True})
        regular_keys.press_backspace({"shift": True})

        assert kitty_mr.get_emitted_data() == "\x1b[127;2u"
        assert regular_mr.get_emitted_data() == "\b"

    def test_special_characters_with_ctrl_in_kitty_mode(self):
        """Maps to test("special characters with ctrl in kitty mode")."""
        kitty_mr = MockRenderer()
        regular_mr = MockRenderer()
        kitty_keys = create_mock_keys(kitty_mr, {"kittyKeyboard": True})
        regular_keys = create_mock_keys(regular_mr, {"kittyKeyboard": False})

        kitty_keys.press_key("-", {"ctrl": True})
        regular_keys.press_key("-", {"ctrl": True})

        # Kitty: '-' codepoint 45, ctrl modifier 4+1=5
        assert kitty_mr.get_emitted_data() == "\x1b[45;5u"
        assert regular_mr.get_emitted_data() == "\u001f"

    def test_various_special_characters_with_ctrl_in_kitty_mode(self):
        """Maps to test("various special characters with ctrl in kitty mode")."""
        kitty_mr = MockRenderer()
        kitty_keys = create_mock_keys(kitty_mr, {"kittyKeyboard": True})

        kitty_mr.emitted_data = []
        kitty_keys.press_key(".", {"ctrl": True})
        assert kitty_mr.get_emitted_data() == "\x1b[46;5u"  # '.' = 46

        kitty_mr.emitted_data = []
        kitty_keys.press_key(",", {"ctrl": True})
        assert kitty_mr.get_emitted_data() == "\x1b[44;5u"  # ',' = 44

        kitty_mr.emitted_data = []
        kitty_keys.press_key("]", {"ctrl": True})
        assert kitty_mr.get_emitted_data() == "\x1b[93;5u"  # ']' = 93


# ===========================================================================
# describe("modifyOtherKeys Mode (CSI u variant)")
# ===========================================================================


class TestModifyOtherKeysMode:
    """Maps to describe('modifyOtherKeys Mode (CSI u variant)')."""

    def test_modify_other_keys_sequences_can_be_parsed_by_parse_keypress(self):
        """Maps to test("modifyOtherKeys sequences can be parsed by parseKeypress").

        The upstream test uses parseKeypress from ../lib/parse.keypress.
        Python equivalent: opentui.input.InputHandler._handle_modify_other_keys
        via _dispatch_csi_sequence.
        """
        from opentui.input import InputHandler

        tests = [
            {"seq": "27;5;97~", "expected_name": "a", "expected_ctrl": True},
            {"seq": "27;2;13~", "expected_name": "return", "expected_shift": True},
            {"seq": "27;5;27~", "expected_name": "escape", "expected_ctrl": True},
            {"seq": "27;2;9~", "expected_name": "tab", "expected_shift": True},
            {"seq": "27;5;32~", "expected_name": "space", "expected_ctrl": True},
            {
                "seq": "27;6;97~",
                "expected_name": "a",
                "expected_shift": True,
                "expected_ctrl": True,
            },
        ]

        for t in tests:
            handler = InputHandler()
            results: list = []
            handler.on_key(lambda ev, _r=results: _r.append(ev))
            handler._dispatch_csi_sequence(t["seq"])
            assert len(results) == 1, f"Expected 1 event for seq {t['seq']}, got {len(results)}"
            ev = results[0]
            assert ev.key == t["expected_name"], f"seq={t['seq']}: key"
            if "expected_ctrl" in t:
                assert ev.ctrl == t["expected_ctrl"], f"seq={t['seq']}: ctrl"
            if "expected_shift" in t:
                assert ev.shift == t["expected_shift"], f"seq={t['seq']}: shift"

    def test_basic_character_without_modifiers_in_modify_other_keys_mode(self):
        """Maps to test("basic character without modifiers in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a")
        assert mr.get_emitted_data() == "a"

    def test_character_with_ctrl_in_modify_other_keys_mode(self):
        """Maps to test("character with ctrl in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;97~"

    def test_character_with_shift_in_modify_other_keys_mode(self):
        """Maps to test("character with shift in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a", {"shift": True})
        assert mr.get_emitted_data() == "\x1b[27;2;97~"

    def test_character_with_meta_in_modify_other_keys_mode(self):
        """Maps to test("character with meta in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a", {"meta": True})
        assert mr.get_emitted_data() == "\x1b[27;3;97~"

    def test_return_enter_with_ctrl_in_modify_other_keys_mode(self):
        """Maps to test("return/enter with ctrl in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_enter({"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;13~"

    def test_return_with_shift_in_modify_other_keys_mode(self):
        """Maps to test("return with shift in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_enter({"shift": True})
        assert mr.get_emitted_data() == "\x1b[27;2;13~"

    def test_escape_with_ctrl_in_modify_other_keys_mode(self):
        """Maps to test("escape with ctrl in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_escape({"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;27~"

    def test_tab_with_ctrl_in_modify_other_keys_mode(self):
        """Maps to test("tab with ctrl in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_tab({"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;9~"

    def test_tab_with_shift_in_modify_other_keys_mode(self):
        """Maps to test("tab with shift in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_tab({"shift": True})
        assert mr.get_emitted_data() == "\x1b[27;2;9~"

    def test_backspace_with_ctrl_in_modify_other_keys_mode(self):
        """Maps to test("backspace with ctrl in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_backspace({"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;127~"

    def test_backspace_with_meta_in_modify_other_keys_mode(self):
        """Maps to test("backspace with meta in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_backspace({"meta": True})
        assert mr.get_emitted_data() == "\x1b[27;3;127~"

    def test_space_with_ctrl_in_modify_other_keys_mode(self):
        """Maps to test("space with ctrl in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key(" ", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;32~"

    def test_special_characters_with_ctrl_in_modify_other_keys_mode(self):
        """Maps to test("special characters with ctrl in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})

        mr.emitted_data = []
        mk.press_key("-", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;45~"  # '-' = 45

        mr.emitted_data = []
        mk.press_key(".", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;46~"  # '.' = 46

        mr.emitted_data = []
        mk.press_key(",", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;44~"  # ',' = 44

        mr.emitted_data = []
        mk.press_key("]", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;93~"  # ']' = 93

    def test_multiple_modifier_combinations_in_modify_other_keys_mode(self):
        """Maps to test("multiple modifier combinations in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})

        # shift + ctrl: 1+4 = 5, +1 = 6
        mr.emitted_data = []
        mk.press_key("a", {"shift": True, "ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;6;97~"

        # shift + meta: 1+2 = 3, +1 = 4
        mr.emitted_data = []
        mk.press_key("a", {"shift": True, "meta": True})
        assert mr.get_emitted_data() == "\x1b[27;4;97~"

        # ctrl + meta: 4+2 = 6, +1 = 7
        mr.emitted_data = []
        mk.press_key("a", {"ctrl": True, "meta": True})
        assert mr.get_emitted_data() == "\x1b[27;7;97~"

        # shift + ctrl + meta: 1+4+2 = 7, +1 = 8
        mr.emitted_data = []
        mk.press_key("a", {"shift": True, "ctrl": True, "meta": True})
        assert mr.get_emitted_data() == "\x1b[27;8;97~"

    def test_character_with_super_modifier_in_modify_other_keys_mode(self):
        """Maps to test("character with super modifier in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a", {"super": True})
        assert mr.get_emitted_data() == "\x1b[27;9;97~"

    def test_character_with_hyper_modifier_in_modify_other_keys_mode(self):
        """Maps to test("character with hyper modifier in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a", {"hyper": True})
        assert mr.get_emitted_data() == "\x1b[27;17;97~"

    def test_character_with_super_hyper_modifiers_in_modify_other_keys_mode(self):
        """Maps to test("character with super+hyper modifiers in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a", {"super": True, "hyper": True})
        assert mr.get_emitted_data() == "\x1b[27;25;97~"

    def test_character_with_all_modifiers_in_modify_other_keys_mode(self):
        """Maps to test("character with all modifiers in modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a", {"shift": True, "ctrl": True, "meta": True, "super": True, "hyper": True})
        # shift(1)+meta(2)+ctrl(4)+super(8)+hyper(16) = 31, +1 = 32
        assert mr.get_emitted_data() == "\x1b[27;32;97~"

    def test_arrow_keys_with_modifiers_fall_through_to_regular_mode(self):
        """Maps to test("arrow keys with modifiers fall through to regular mode in modifyOtherKeys")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_arrow("right", {"shift": True})
        assert mr.get_emitted_data() == "\x1b[1;2C"

    def test_kitty_mode_takes_precedence_over_modify_other_keys_mode(self):
        """Maps to test("kitty mode takes precedence over modifyOtherKeys mode")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True, "otherModifiersMode": True})
        mk.press_key("a", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[97;5u"

    def test_modify_other_keys_vs_regular_mode_comparison(self):
        """Maps to test("modifyOtherKeys vs regular mode comparison")."""
        mok_mr = MockRenderer()
        regular_mr = MockRenderer()
        mok_keys = create_mock_keys(mok_mr, {"otherModifiersMode": True})
        regular_keys = create_mock_keys(regular_mr, {"otherModifiersMode": False})

        mok_keys.press_key("-", {"ctrl": True})
        regular_keys.press_key("-", {"ctrl": True})

        assert mok_mr.get_emitted_data() == "\x1b[27;5;45~"
        assert regular_mr.get_emitted_data() == "\u001f"

    def test_characters_without_modifiers_dont_use_modify_other_keys_format(self):
        """Maps to test("characters without modifiers don't use modifyOtherKeys format")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a")
        mk.press_key("b")
        mk.press_enter()
        assert mr.get_emitted_data() == "ab\r"

    def test_modify_other_keys_with_all_printable_characters(self):
        """Maps to test("modifyOtherKeys with all printable characters")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})

        chars = "abcdefghijklmnopqrstuvwxyz0123456789-=[]\\;',./`"
        for char in chars:
            mr.emitted_data = []
            mk.press_key(char, {"ctrl": True})
            char_code = ord(char)
            assert mr.get_emitted_data() == f"\x1b[27;5;{char_code}~", f"char={char!r}"

    def test_modify_other_keys_mode_can_be_parsed_back_correctly(self):
        """Maps to test("modifyOtherKeys mode can be parsed back correctly")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})

        tests = [
            {"key": "a", "mods": {"ctrl": True}, "expected_seq": "\x1b[27;5;97~"},
            {"key": "-", "mods": {"ctrl": True}, "expected_seq": "\x1b[27;5;45~"},
            {"key": KeyCodes.RETURN, "mods": {"shift": True}, "expected_seq": "\x1b[27;2;13~"},
            {"key": KeyCodes.ESCAPE, "mods": {"ctrl": True}, "expected_seq": "\x1b[27;5;27~"},
            {"key": KeyCodes.TAB, "mods": {"shift": True}, "expected_seq": "\x1b[27;2;9~"},
            {"key": " ", "mods": {"ctrl": True}, "expected_seq": "\x1b[27;5;32~"},
        ]
        for t in tests:
            mr.emitted_data = []
            mk.press_key(t["key"], t["mods"])
            assert mr.get_emitted_data() == t["expected_seq"], f"key={t['key']!r}"

    def test_comprehensive_three_mode_comparison(self):
        """Maps to test("comprehensive three-mode comparison: regular vs modifyOtherKeys vs kitty")."""
        regular_mr = MockRenderer()
        mok_mr = MockRenderer()
        kitty_mr = MockRenderer()

        regular_keys = create_mock_keys(
            regular_mr, {"kittyKeyboard": False, "otherModifiersMode": False}
        )
        mok_keys = create_mock_keys(mok_mr, {"otherModifiersMode": True})
        kitty_keys = create_mock_keys(kitty_mr, {"kittyKeyboard": True})

        # Test Ctrl+- in all three modes
        regular_keys.press_key("-", {"ctrl": True})
        mok_keys.press_key("-", {"ctrl": True})
        kitty_keys.press_key("-", {"ctrl": True})

        assert regular_mr.get_emitted_data() == "\u001f"
        assert mok_mr.get_emitted_data() == "\x1b[27;5;45~"
        assert kitty_mr.get_emitted_data() == "\x1b[45;5u"

        # Test Shift+Enter in all three modes
        regular_mr.emitted_data = []
        mok_mr.emitted_data = []
        kitty_mr.emitted_data = []

        regular_keys.press_enter({"shift": True})
        mok_keys.press_enter({"shift": True})
        kitty_keys.press_enter({"shift": True})

        assert regular_mr.get_emitted_data() == "\r"
        assert mok_mr.get_emitted_data() == "\x1b[27;2;13~"
        assert kitty_mr.get_emitted_data() == "\x1b[13;2u"


# ===========================================================================
# describe("Mode selection and precedence")
# ===========================================================================


class TestModeSelectionAndPrecedence:
    """Maps to describe('Mode selection and precedence')."""

    def test_default_mode_no_options(self):
        """Maps to test("default mode (no options)")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr)
        mk.press_key("-", {"ctrl": True})
        assert mr.get_emitted_data() == "\u001f"

    def test_only_kitty_keyboard_enabled(self):
        """Maps to test("only kittyKeyboard enabled")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True})
        mk.press_key("a", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[97;5u"

    def test_only_other_modifiers_mode_enabled(self):
        """Maps to test("only otherModifiersMode enabled")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"otherModifiersMode": True})
        mk.press_key("a", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[27;5;97~"

    def test_both_kitty_keyboard_and_other_modifiers_mode_enabled_kitty_wins(self):
        """Maps to test("both kittyKeyboard and otherModifiersMode enabled (kitty wins)")."""
        mr = MockRenderer()
        mk = create_mock_keys(mr, {"kittyKeyboard": True, "otherModifiersMode": True})
        mk.press_key("a", {"ctrl": True})
        assert mr.get_emitted_data() == "\x1b[97;5u"
        assert "27;5;97~" not in mr.get_emitted_data()
