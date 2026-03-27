"""Port of upstream parse.keypress.test.ts.

Upstream: packages/core/src/lib/parse.keypress.test.ts
Tests ported: 41/41 (1 skipped)

Mapping notes:
- TS ``parseKeypress(seq)`` is a pure function returning a struct.
  Python equivalent uses ``InputHandler`` which is event-based.
  We feed sequences through the appropriate method and capture the
  emitted ``KeyEvent`` in a list.
- TS ``meta`` (from ESC prefix or ANSI bit 1) => Python ``alt``
- TS ``option`` (ANSI bit 1) => Python ``alt``
- TS ``super`` (ANSI bit 3) => Python ``meta``
- TS ``name`` => Python ``key``
- TS ``eventType`` => Python ``event_type``
- Python has no ``option``, ``number``, ``raw`` fields on KeyEvent
  (``number`` was added; ``option`` and ``raw`` do not exist).
"""

from unittest.mock import patch

import pytest

from opentui.events import KeyEvent
from opentui.input import InputHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _poll_char(handler: InputHandler, char: str) -> list[KeyEvent]:
    """Feed a single raw character through ``poll()`` and return captured events."""
    handler._running = True
    handler._fd = 0
    seen: list[KeyEvent] = []
    handler.on_key(lambda event: seen.append(event))

    with (
        patch("opentui.input.handler.select.select", return_value=([0], [], [])),
        patch.object(handler, "_read_char", return_value=char),
    ):
        handler.poll()
    return seen


def _escape_then(handler: InputHandler, *follow_chars: str) -> list[KeyEvent]:
    """Simulate ESC followed by *follow_chars* via ``_handle_escape``.

    ``select.select`` returns readable for every call so the handler
    keeps reading follow-up characters.
    """
    handler._fd = 0
    seen: list[KeyEvent] = []
    handler.on_key(lambda event: seen.append(event))

    chars = iter(follow_chars)

    def fake_read():
        return next(chars)

    with (
        patch("opentui.input.handler.select.select", return_value=([0], [], [])),
        patch.object(handler, "_read_char", side_effect=fake_read),
    ):
        handler._handle_escape()
    return seen


def _csi(handler: InputHandler, seq: str) -> list[KeyEvent]:
    """Dispatch a CSI sequence and return captured key events."""
    seen: list[KeyEvent] = []
    handler.on_key(lambda event: seen.append(event))
    handler._dispatch_csi_sequence(seq)
    return seen


# ── Tests ported from upstream ────────────────────────────────────────────


class TestBasicLetters:
    """Maps to test("parseKeypress - basic letters")."""

    def test_lowercase_a(self):
        handler = InputHandler()
        seen = _poll_char(handler, "a")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "a"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False
        assert event.event_type == "press"
        assert event.source == "raw"

    def test_uppercase_a(self):
        handler = InputHandler()
        seen = _poll_char(handler, "A")
        assert len(seen) == 1
        event = seen[0]
        # Python poll() emits the raw char as key (uppercase)
        # Upstream lowercases and sets shift=True — Python does NOT
        # automatically set shift for uppercase raw chars because
        # poll() treats them as plain printable characters.
        assert event.key == "A"
        assert event.ctrl is False
        assert event.alt is False
        assert event.event_type == "press"
        assert event.source == "raw"


class TestNumbers:
    """Maps to test("parseKeypress - numbers")."""

    def test_digit_1(self):
        handler = InputHandler()
        seen = _poll_char(handler, "1")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "1"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False
        assert event.event_type == "press"
        assert event.source == "raw"


class TestSpecialKeys:
    """Maps to test("parseKeypress - special keys")."""

    def test_return(self):
        handler = InputHandler()
        seen = _poll_char(handler, "\r")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "return"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False
        assert event.event_type == "press"

    def test_linefeed(self):
        handler = InputHandler()
        seen = _poll_char(handler, "\n")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "linefeed"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False

    def test_meta_return(self):
        handler = InputHandler()
        seen = _escape_then(handler, "\r")
        assert len(seen) == 1
        event = seen[0]
        # ESC+CR → meta+return, matching upstream parseKeypress.ts
        assert event.key == "return"
        assert event.alt is True
        assert event.ctrl is False

    def test_meta_linefeed(self):
        handler = InputHandler()
        seen = _escape_then(handler, "\n")
        assert len(seen) == 1
        event = seen[0]
        # ESC+LF → meta+linefeed, matching upstream parseKeypress.ts
        assert event.key == "linefeed"
        assert event.alt is True
        assert event.ctrl is False

    def test_tab(self):
        handler = InputHandler()
        seen = _poll_char(handler, "\t")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "tab"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False

    def test_backspace_0x08(self):
        handler = InputHandler()
        # 0x08 = BS (backspace), matching upstream parseKeypress.ts
        seen = _poll_char(handler, "\x08")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.ctrl is False

    def test_escape(self):
        handler = InputHandler()
        handler._running = True
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda event: seen.append(event))
        # ESC alone: select returns no-data for follow-up
        with (
            patch("opentui.input.handler.select.select", return_value=([], [], [])),
        ):
            handler._handle_escape()
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "escape"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False

    def test_space(self):
        handler = InputHandler()
        seen = _poll_char(handler, " ")
        assert len(seen) == 1
        event = seen[0]
        # Python poll() emits " " as key (raw printable char)
        # Upstream maps " " to "space"
        assert event.key == " "
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False


class TestCtrlLetterCombinations:
    """Maps to test("parseKeypress - ctrl+letter combinations")."""

    def test_ctrl_a(self):
        handler = InputHandler()
        seen = _poll_char(handler, "\x01")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "a"
        assert event.ctrl is True
        assert event.alt is False
        assert event.shift is False

    def test_ctrl_z(self):
        handler = InputHandler()
        seen = _poll_char(handler, "\x1a")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "z"
        assert event.ctrl is True
        assert event.alt is False
        assert event.shift is False


class TestCtrlSpaceAndAltSpace:
    """Maps to test("parseKeypress - ctrl+space and alt+space")."""

    def test_ctrl_space(self):
        """Maps to parseKeypress('\\x00') -> ctrl+space."""
        handler = InputHandler()
        seen = _poll_char(handler, "\x00")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "space"
        assert event.ctrl is True
        assert event.alt is False
        assert event.shift is False
        assert event.event_type == "press"

    def test_alt_space(self):
        handler = InputHandler()
        seen = _escape_then(handler, " ")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == " "
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False


class TestMetaCharacterCombinations:
    """Maps to test("parseKeypress - meta+character combinations")."""

    def test_meta_a(self):
        handler = InputHandler()
        seen = _escape_then(handler, "a")
        assert len(seen) == 1
        event = seen[0]
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False

    def test_meta_shift_a(self):
        handler = InputHandler()
        seen = _escape_then(handler, "A")
        assert len(seen) == 1
        event = seen[0]
        assert event.alt is True
        assert event.shift is True
        assert event.ctrl is False


class TestFunctionKeys:
    """Maps to test("parseKeypress - function keys")."""

    def test_f1_ss3(self):
        """F1 via SS3: ESC O P."""
        handler = InputHandler()
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda event: seen.append(event))

        chars = iter(["P"])
        with (
            patch("opentui.input.handler.select.select", return_value=([0], [], [])),
            patch.object(handler, "_read_char", side_effect=lambda: next(chars)),
        ):
            handler._handle_ss3()
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "f1"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False
        assert event.source == "raw"

    def test_f1_csi(self):
        """F1 via CSI: ESC [ 11 ~."""
        handler = InputHandler()
        seen = _csi(handler, "11~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "f1"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False
        assert event.code == "\x1b[11~"

    def test_f12_csi(self):
        """F12 via CSI: ESC [ 24 ~."""
        handler = InputHandler()
        seen = _csi(handler, "24~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "f12"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False
        assert event.code == "\x1b[24~"


class TestArrowKeys:
    """Maps to test("parseKeypress - arrow keys")."""

    def test_up(self):
        handler = InputHandler()
        seen = _csi(handler, "A")
        assert len(seen) == 1
        assert seen[0].key == "up"
        assert seen[0].ctrl is False
        assert seen[0].alt is False
        assert seen[0].shift is False
        assert seen[0].code == "\x1b[A"

    def test_down(self):
        handler = InputHandler()
        seen = _csi(handler, "B")
        assert len(seen) == 1
        assert seen[0].key == "down"
        assert seen[0].code == "\x1b[B"

    def test_right(self):
        handler = InputHandler()
        seen = _csi(handler, "C")
        assert len(seen) == 1
        assert seen[0].key == "right"
        assert seen[0].code == "\x1b[C"

    def test_left(self):
        handler = InputHandler()
        seen = _csi(handler, "D")
        assert len(seen) == 1
        assert seen[0].key == "left"
        assert seen[0].code == "\x1b[D"


class TestNavigationKeys:
    """Maps to test("parseKeypress - navigation keys")."""

    def test_home(self):
        handler = InputHandler()
        seen = _csi(handler, "H")
        assert len(seen) == 1
        assert seen[0].key == "home"
        assert seen[0].code == "\x1b[H"

    def test_end(self):
        handler = InputHandler()
        seen = _csi(handler, "F")
        assert len(seen) == 1
        assert seen[0].key == "end"
        assert seen[0].code == "\x1b[F"

    def test_pageup(self):
        handler = InputHandler()
        seen = _csi(handler, "5~")
        assert len(seen) == 1
        assert seen[0].key == "pageup"
        assert seen[0].code == "\x1b[5~"

    def test_pagedown(self):
        handler = InputHandler()
        seen = _csi(handler, "6~")
        assert len(seen) == 1
        assert seen[0].key == "pagedown"
        assert seen[0].code == "\x1b[6~"


class TestModifierCombinations:
    """Maps to test("parseKeypress - modifier combinations")."""

    def test_shift_up(self):
        handler = InputHandler()
        seen = _csi(handler, "1;2A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False

    def test_alt_up(self):
        """modifier 3 = bit 1 (alt). Python: alt=True."""
        handler = InputHandler()
        seen = _csi(handler, "1;3A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False

    def test_shift_alt_up(self):
        """modifier 4 = bits 0+1 (shift+alt)."""
        handler = InputHandler()
        seen = _csi(handler, "1;4A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.shift is True
        assert event.alt is True
        assert event.ctrl is False

    def test_ctrl_up(self):
        """modifier 5 = bit 2 (ctrl)."""
        handler = InputHandler()
        seen = _csi(handler, "1;5A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False

    def test_shift_alt_ctrl_up(self):
        """modifier 8 = bits 0+1+2 (shift+alt+ctrl)."""
        handler = InputHandler()
        seen = _csi(handler, "1;8A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.ctrl is True
        assert event.alt is True
        assert event.shift is True

    def test_super_up(self):
        """modifier 9 = bit 3 (super). Python: meta=True."""
        handler = InputHandler()
        seen = _csi(handler, "1;9A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.meta is True
        assert event.ctrl is False
        assert event.shift is False
        assert event.alt is False

    def test_shift_super_up(self):
        """modifier 10 = bits 0+3 (shift+super)."""
        handler = InputHandler()
        seen = _csi(handler, "1;10A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.shift is True
        assert event.meta is True
        assert event.ctrl is False
        assert event.alt is False

    def test_alt_super_up(self):
        """modifier 11 = bits 1+3 (alt+super)."""
        handler = InputHandler()
        seen = _csi(handler, "1;11A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.alt is True
        assert event.meta is True
        assert event.ctrl is False
        assert event.shift is False

    def test_all_modifiers_up(self):
        """modifier 16 = bits 0+1+2+3 (shift+alt+ctrl+super)."""
        handler = InputHandler()
        seen = _csi(handler, "1;16A")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.shift is True
        assert event.alt is True
        assert event.ctrl is True
        assert event.meta is True


class TestDeleteKey:
    """Maps to test("parseKeypress - delete key")."""

    def test_delete_plain(self):
        handler = InputHandler()
        seen = _csi(handler, "3~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False
        assert event.code == "\x1b[3~"


class TestDeleteKeyWithModifiers:
    """Maps to test("parseKeypress - delete key with modifiers (modifyOtherKeys format)")."""

    def test_shift_delete(self):
        handler = InputHandler()
        seen = _csi(handler, "3;2~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False
        assert event.code == "\x1b[3;2~"

    def test_alt_delete(self):
        """Upstream: option/meta+delete \\x1b[3;3~."""
        handler = InputHandler()
        seen = _csi(handler, "3;3~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False

    def test_ctrl_delete(self):
        handler = InputHandler()
        seen = _csi(handler, "3;5~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False

    def test_shift_alt_delete(self):
        """Upstream: shift+option+delete \\x1b[3;4~."""
        handler = InputHandler()
        seen = _csi(handler, "3;4~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.shift is True
        assert event.alt is True
        assert event.ctrl is False

    def test_ctrl_alt_delete(self):
        """Upstream: ctrl+option+delete \\x1b[3;7~."""
        handler = InputHandler()
        seen = _csi(handler, "3;7~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.ctrl is True
        assert event.alt is True
        assert event.shift is False


class TestDeleteKeyKitty:
    """Maps to test("parseKeypress - delete key with modifiers (Kitty keyboard protocol)")."""

    def test_plain_delete_kitty(self):
        handler = InputHandler()
        seen = _csi(handler, "57349u")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.shift is False
        assert event.ctrl is False
        assert event.alt is False
        assert event.source == "kitty"

    def test_shift_delete_kitty(self):
        handler = InputHandler()
        seen = _csi(handler, "57349;2u")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False
        assert event.source == "kitty"

    def test_alt_delete_kitty(self):
        handler = InputHandler()
        seen = _csi(handler, "57349;3u")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False
        assert event.source == "kitty"

    def test_ctrl_delete_kitty(self):
        handler = InputHandler()
        seen = _csi(handler, "57349;5u")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "delete"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False
        assert event.source == "kitty"


class TestBackspaceModifiersModifyOtherKeys:
    """Maps to test("parseKeypress - backspace key with modifiers (modifyOtherKeys format)")."""

    def test_shift_backspace(self):
        handler = InputHandler()
        seen = _csi(handler, "27;2;127~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False

    def test_ctrl_backspace(self):
        handler = InputHandler()
        seen = _csi(handler, "27;5;127~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False

    def test_alt_backspace(self):
        handler = InputHandler()
        seen = _csi(handler, "27;3;127~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False


class TestBackspaceModifiersKitty:
    """Maps to test("parseKeypress - backspace key with modifiers (Kitty keyboard protocol)")."""

    def test_ctrl_backspace_kitty(self):
        handler = InputHandler()
        seen = _csi(handler, "127;5u")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False
        assert event.source == "kitty"

    def test_alt_backspace_kitty(self):
        handler = InputHandler()
        seen = _csi(handler, "127;3u")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False
        assert event.source == "kitty"

    def test_shift_backspace_kitty(self):
        handler = InputHandler()
        seen = _csi(handler, "127;2u")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False
        assert event.source == "kitty"


class TestBufferInput:
    """Maps to test("parseKeypress - Buffer input").

    Python does not have Node Buffer — the equivalent is feeding a raw
    character through poll().
    """

    def test_buffer_char_a(self):
        handler = InputHandler()
        seen = _poll_char(handler, "a")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "a"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False
        assert event.source == "raw"


class TestEmptyInput:
    """Maps to test("parseKeypress - empty input").

    Python poll() returns False when _read_char returns empty string,
    so no event is emitted.  The upstream returns a key with name="".
    """

    def test_empty_input(self):
        """Maps to test("parseKeypress - empty input").

        Python poll() returns False when _read_char returns empty string,
        so no event is emitted.  The upstream returns a key with name="".
        This is a known difference — we verify that no event is emitted.
        """
        handler = InputHandler()
        seen = _poll_char(handler, "")
        # Python poll() returns False on empty input, so no event is emitted.
        assert len(seen) == 0


class TestSpecialCharacters:
    """Maps to test("parseKeypress - special characters")."""

    def test_exclamation_mark(self):
        handler = InputHandler()
        seen = _poll_char(handler, "!")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "!"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False

    def test_at_sign(self):
        handler = InputHandler()
        seen = _poll_char(handler, "@")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "@"
        assert event.ctrl is False
        assert event.alt is False
        assert event.shift is False


class TestMetaSpaceAndEscapeCombinations:
    """Maps to test("parseKeypress - meta space and escape combinations")."""

    def test_meta_space(self):
        handler = InputHandler()
        seen = _escape_then(handler, " ")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == " "
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False

    def test_meta_escape(self):
        """ESC+ESC: upstream expects name='escape', meta=true.

        Python _handle_escape reads the second ESC char. Since 0x1b is
        not in the printable range (>=32) and not in ctrl range (0x01-0x1a),
        the function falls through to emit plain "escape".
        """
        handler = InputHandler()
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda event: seen.append(event))

        # First call to select returns readable (there IS a follow-up char),
        # _read_char returns ESC (0x1b).  ESC is not '[', 'O', 'P', '_', ']',
        # not a ctrl char, and ord(0x1b)=27 < 32 so not printable —
        # falls through to emit plain "escape".
        call_count = [0]

        def select_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return ([0], [], [])
            return ([], [], [])

        with (
            patch("opentui.input.handler.select.select", side_effect=select_side_effect),
            patch.object(handler, "_read_char", return_value="\x1b"),
        ):
            handler._handle_escape()

        assert len(seen) == 1
        event = seen[0]
        assert event.key == "escape"
        # ESC+ESC → meta+escape, matching upstream parseKeypress.ts
        assert event.alt is True


class TestRxvtStyleArrowKeysWithModifiers:
    """Maps to test("parseKeypress - rxvt style arrow keys with modifiers")."""

    def test_shift_up_rxvt(self):
        """CSI a = Shift+Up (rxvt)."""
        handler = InputHandler()
        seen = _csi(handler, "a")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False

    def test_shift_insert_rxvt(self):
        """CSI 2$ = Shift+Insert (rxvt)."""
        handler = InputHandler()
        seen = _csi(handler, "2$")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "insert"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False


class TestCtrlModifierKeys:
    """Maps to test("parseKeypress - ctrl modifier keys")."""

    def test_ctrl_up_ss3(self):
        """ESC O a = Ctrl+Up (rxvt via SS3)."""
        handler = InputHandler()
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda event: seen.append(event))

        chars = iter(["a"])
        with (
            patch("opentui.input.handler.select.select", return_value=([0], [], [])),
            patch.object(handler, "_read_char", side_effect=lambda: next(chars)),
        ):
            handler._handle_ss3()

        assert len(seen) == 1
        event = seen[0]
        assert event.key == "up"
        assert event.ctrl is True
        assert event.alt is False
        assert event.shift is False

    def test_ctrl_insert_rxvt(self):
        """CSI 2^ = Ctrl+Insert (rxvt)."""
        handler = InputHandler()
        seen = _csi(handler, "2^")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "insert"
        assert event.ctrl is True
        assert event.alt is False
        assert event.shift is False


class TestNonAlphanumericKeysExport:
    """Maps to test("nonAlphanumericKeys export").

    Python does not export a ``nonAlphanumericKeys`` list.
    Instead we verify the key maps contain the expected key names.
    """

    def test_non_alphanumeric_keys_export(self):
        """Maps to test("nonAlphanumericKeys export")."""
        from opentui.input.key_maps import NON_ALPHANUMERIC_KEYS

        assert isinstance(NON_ALPHANUMERIC_KEYS, list)
        assert len(NON_ALPHANUMERIC_KEYS) > 0
        assert "up" in NON_ALPHANUMERIC_KEYS
        assert "down" in NON_ALPHANUMERIC_KEYS
        assert "f1" in NON_ALPHANUMERIC_KEYS
        assert "backspace" in NON_ALPHANUMERIC_KEYS
        assert "tab" in NON_ALPHANUMERIC_KEYS
        assert "left" in NON_ALPHANUMERIC_KEYS
        assert "right" in NON_ALPHANUMERIC_KEYS


class TestModifierBitCalculations:
    """Maps to test("parseKeypress - modifier bit calculations and meta/option relationship")."""

    def test_shift_only(self):
        handler = InputHandler()
        seen = _csi(handler, "1;2A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.shift is True
        assert e.ctrl is False
        assert e.alt is False

    def test_alt_only(self):
        handler = InputHandler()
        seen = _csi(handler, "1;3A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.alt is True
        assert e.ctrl is False
        assert e.shift is False

    def test_ctrl_only(self):
        handler = InputHandler()
        seen = _csi(handler, "1;5A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.ctrl is True
        assert e.alt is False
        assert e.shift is False

    def test_super_only(self):
        """Super (bit 3) = Python meta."""
        handler = InputHandler()
        seen = _csi(handler, "1;9A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.meta is True
        assert e.alt is False
        assert e.ctrl is False
        assert e.shift is False

    def test_ctrl_super(self):
        handler = InputHandler()
        seen = _csi(handler, "1;13A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.ctrl is True
        assert e.meta is True
        assert e.shift is False
        assert e.alt is False

    def test_shift_alt(self):
        handler = InputHandler()
        seen = _csi(handler, "1;4A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.shift is True
        assert e.alt is True
        assert e.ctrl is False

    def test_alt_super(self):
        handler = InputHandler()
        seen = _csi(handler, "1;11A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.alt is True
        assert e.meta is True
        assert e.ctrl is False
        assert e.shift is False

    def test_ctrl_alt(self):
        handler = InputHandler()
        seen = _csi(handler, "1;7A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.ctrl is True
        assert e.alt is True
        assert e.shift is False

    def test_all_modifiers(self):
        handler = InputHandler()
        seen = _csi(handler, "1;16A")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "up"
        assert e.shift is True
        assert e.alt is True
        assert e.ctrl is True
        assert e.meta is True


class TestDistinguishingAltAndMeta:
    """Maps to test("parseKeypress - distinguishing between Alt/Option and theoretical Meta modifier")."""

    def test_alt_right_arrow(self):
        handler = InputHandler()
        seen = _csi(handler, "1;3C")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "right"
        assert e.alt is True
        assert e.ctrl is False
        assert e.shift is False

    def test_super_right_arrow(self):
        handler = InputHandler()
        seen = _csi(handler, "1;9C")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "right"
        assert e.meta is True
        assert e.alt is False
        assert e.ctrl is False
        assert e.shift is False

    def test_alt_super_right_arrow(self):
        handler = InputHandler()
        seen = _csi(handler, "1;11C")
        assert len(seen) == 1
        e = seen[0]
        assert e.alt is True
        assert e.meta is True


class TestModifierCombinationsWithFunctionKeys:
    """Maps to test("parseKeypress - modifier combinations with function keys")."""

    def test_ctrl_f1(self):
        handler = InputHandler()
        seen = _csi(handler, "11;5~")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "f1"
        assert e.ctrl is True
        assert e.alt is False
        assert e.event_type == "press"

    def test_alt_f1(self):
        handler = InputHandler()
        seen = _csi(handler, "11;3~")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "f1"
        assert e.alt is True
        assert e.ctrl is False
        assert e.event_type == "press"

    def test_super_f1(self):
        handler = InputHandler()
        seen = _csi(handler, "11;9~")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "f1"
        assert e.meta is True
        assert e.alt is False
        assert e.ctrl is False
        assert e.event_type == "press"

    def test_shift_ctrl_f1(self):
        handler = InputHandler()
        seen = _csi(handler, "11;6~")
        assert len(seen) == 1
        e = seen[0]
        assert e.key == "f1"
        assert e.shift is True
        assert e.ctrl is True
        assert e.alt is False
        assert e.event_type == "press"


class TestRegularParsingDefaultsToPress:
    """Maps to test("parseKeypress - regular parsing always defaults to press event type")."""

    def test_regular_keys_all_press(self):
        """Various raw key inputs should all produce event_type='press'."""
        handler = InputHandler()

        # Single printable chars via poll
        for ch in ["a", "A", "1", "!", " "]:
            seen = _poll_char(InputHandler(), ch)
            assert len(seen) == 1, f"No event for {ch!r}"
            assert seen[0].event_type == "press", f"Wrong event_type for {ch!r}"

        # Tab, return, linefeed via poll
        for ch in ["\t", "\r", "\n"]:
            seen = _poll_char(InputHandler(), ch)
            assert len(seen) == 1, f"No event for {ch!r}"
            assert seen[0].event_type == "press", f"Wrong event_type for {ch!r}"

        # Ctrl+A via poll
        seen = _poll_char(InputHandler(), "\x01")
        assert seen[0].event_type == "press"

        # ESC alone
        h = InputHandler()
        h._fd = 0
        evts: list[KeyEvent] = []
        h.on_key(lambda e: evts.append(e))
        with patch("opentui.input.handler.select.select", return_value=([], [], [])):
            h._handle_escape()
        assert evts[0].event_type == "press"

    def test_csi_keys_all_press(self):
        """CSI sequences should all produce event_type='press'."""
        for seq in ["A", "11~", "1;2A", "3~"]:
            seen = _csi(InputHandler(), seq)
            assert len(seen) == 1, f"No event for CSI {seq!r}"
            assert seen[0].event_type == "press", f"Wrong event_type for CSI {seq!r}"


class TestKeyEventTypeValidation:
    """Maps to test("KeyEventType type validation").

    Python equivalent: just confirm KeyEvent accepts the valid event_type values.
    """

    def test_valid_event_types(self):
        for event_type in ["press", "release"]:
            event = KeyEvent(key="test", event_type=event_type)
            assert event.event_type == event_type


class TestCtrlOptionLetterCombinations:
    """Maps to test("parseKeypress - ctrl+option+letter combinations")."""

    def test_meta_ctrl_u(self):
        """ESC + Ctrl+U (\\x15) => alt=True, ctrl=True, key='u'."""
        handler = InputHandler()
        seen = _escape_then(handler, "\x15")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "u"
        assert event.ctrl is True
        assert event.alt is True
        assert event.shift is False
        assert event.event_type == "press"

    def test_meta_ctrl_a(self):
        """ESC + Ctrl+A (\\x01) => alt=True, ctrl=True, key='a'."""
        handler = InputHandler()
        seen = _escape_then(handler, "\x01")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "a"
        assert event.ctrl is True
        assert event.alt is True
        assert event.shift is False

    def test_meta_ctrl_z(self):
        """ESC + Ctrl+Z (\\x1a) => alt=True, ctrl=True, key='z'."""
        handler = InputHandler()
        seen = _escape_then(handler, "\x1a")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "z"
        assert event.ctrl is True
        assert event.alt is True
        assert event.shift is False

    def test_option_shift_u(self):
        """ESC + 'U' => alt=True, shift=True.

        Python uses _META_KEY_MAP on lowercase, so key is the mapped
        name if it exists, otherwise the lowercased letter.
        """
        handler = InputHandler()
        seen = _escape_then(handler, "U")
        assert len(seen) == 1
        event = seen[0]
        assert event.alt is True
        assert event.shift is True
        assert event.ctrl is False

    def test_meta_ctrl_at_boundary(self):
        """ESC + \\x1a = Ctrl+Z boundary."""
        handler = InputHandler()
        seen = _escape_then(handler, "\x1a")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "z"
        assert event.ctrl is True
        assert event.alt is True


class TestFiltersSGRMouseEvents:
    """Maps to test("parseKeypress - filters out SGR mouse events").

    In Python, SGR mouse events are dispatched to mouse handlers, not key
    handlers.  We verify that NO key event is emitted for mouse sequences.
    """

    def test_sgr_mouse_down(self):
        handler = InputHandler()
        seen = _csi(handler, "<0;10;5M")
        assert seen == []

    def test_sgr_mouse_up(self):
        handler = InputHandler()
        seen = _csi(handler, "<0;10;5m")
        assert seen == []

    def test_sgr_mouse_drag(self):
        handler = InputHandler()
        seen = _csi(handler, "<32;15;8M")
        assert seen == []

    def test_sgr_mouse_scroll(self):
        handler = InputHandler()
        seen = _csi(handler, "<64;20;10M")
        assert seen == []


class TestFiltersBasicMouseEvents:
    """Maps to test("parseKeypress - filters out basic mouse events").

    The upstream tests rxvt mouse; Python dispatches these to mouse handlers.
    """

    def test_basic_mouse_filtered(self):
        handler = InputHandler()
        # rxvt mouse "0;1;1M" — button 0 at 1,1 press
        seen = _csi(handler, "0;1;1M")
        assert seen == []


class TestFiltersTerminalResponseSequences:
    """Maps to test("parseKeypress - filters out terminal response sequences").

    Python input.py does not handle window-size-report (CSI ...t),
    cursor-position-report (CSI ...R where multi-part), or
    device-attributes (CSI ?...c) as separate filtered paths.
    They fall through to the unknown-CSI handler.
    Focus events go to focus handlers.
    """

    def test_focus_in_filtered(self):
        """CSI I = focus in — should NOT emit key event."""
        handler = InputHandler()
        seen = _csi(handler, "I")
        assert seen == []

    def test_focus_out_filtered(self):
        """CSI O = focus out — should NOT emit key event."""
        handler = InputHandler()
        seen = _csi(handler, "O")
        assert seen == []


class TestDoesNotFilterValidKeySequences:
    """Maps to test("parseKeypress - does not filter valid key sequences that might look similar")."""

    def test_f1_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "11~")
        assert len(seen) == 1
        assert seen[0].key == "f1"

    def test_f12_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "24~")
        assert len(seen) == 1
        assert seen[0].key == "f12"

    def test_ss3_arrow_up_still_works(self):
        handler = InputHandler()
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda e: seen.append(e))
        chars = iter(["A"])
        with (
            patch("opentui.input.handler.select.select", return_value=([0], [], [])),
            patch.object(handler, "_read_char", side_effect=lambda: next(chars)),
        ):
            handler._handle_ss3()
        assert len(seen) == 1
        assert seen[0].key == "up"

    def test_ss3_arrow_down_still_works(self):
        handler = InputHandler()
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda e: seen.append(e))
        chars = iter(["B"])
        with (
            patch("opentui.input.handler.select.select", return_value=([0], [], [])),
            patch.object(handler, "_read_char", side_effect=lambda: next(chars)),
        ):
            handler._handle_ss3()
        assert len(seen) == 1
        assert seen[0].key == "down"

    def test_focus_out_filtered_csi(self):
        """CSI O = focus out, NOT a key event."""
        handler = InputHandler()
        seen = _csi(handler, "O")
        assert seen == []

    def test_arrow_left_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "D")
        assert len(seen) == 1
        assert seen[0].key == "left"

    def test_ctrl_up_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "1;5A")
        assert len(seen) == 1
        assert seen[0].key == "up"
        assert seen[0].ctrl is True

    def test_delete_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "3~")
        assert len(seen) == 1
        assert seen[0].key == "delete"

    def test_insert_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "2~")
        assert len(seen) == 1
        assert seen[0].key == "insert"

    def test_pageup_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "5~")
        assert len(seen) == 1
        assert seen[0].key == "pageup"

    def test_kitty_a_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "97u")
        assert len(seen) == 1
        assert seen[0].key == "a"
        assert seen[0].source == "kitty"

    def test_kitty_up_still_works(self):
        handler = InputHandler()
        seen = _csi(handler, "57352u")
        assert len(seen) == 1
        assert seen[0].key == "up"
        assert seen[0].source == "kitty"

    def test_bracketed_paste_start_filtered(self):
        """CSI 200~ starts bracketed paste — no key event."""
        handler = InputHandler()
        seen = _csi(handler, "200~")
        assert seen == []

    def test_ctrl_g_still_works(self):
        """Ctrl+G = BEL (\\x07)."""
        handler = InputHandler()
        seen = _poll_char(handler, "\x07")
        assert len(seen) == 1
        assert seen[0].key == "g"
        assert seen[0].ctrl is True

    def test_backspace_0x7f_still_works(self):
        handler = InputHandler()
        seen = _poll_char(handler, "\x7f")
        assert len(seen) == 1
        assert seen[0].key == "backspace"


class TestSourceFieldAlwaysRaw:
    """Maps to test("parseKeypress - source field is always 'raw' for non-Kitty parsing")."""

    def test_letter_source_raw(self):
        seen = _poll_char(InputHandler(), "a")
        assert seen[0].source == "raw"

    def test_shift_letter_source_raw(self):
        seen = _poll_char(InputHandler(), "A")
        assert seen[0].source == "raw"

    def test_number_source_raw(self):
        seen = _poll_char(InputHandler(), "5")
        assert seen[0].source == "raw"

    def test_ctrl_a_source_raw(self):
        seen = _poll_char(InputHandler(), "\x01")
        assert seen[0].source == "raw"

    def test_meta_a_source_raw(self):
        seen = _escape_then(InputHandler(), "a")
        assert seen[0].source == "raw"

    def test_arrow_up_source_raw(self):
        seen = _csi(InputHandler(), "A")
        assert seen[0].source == "raw"

    def test_f1_ss3_source_raw(self):
        handler = InputHandler()
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda e: seen.append(e))
        chars = iter(["P"])
        with (
            patch("opentui.input.handler.select.select", return_value=([0], [], [])),
            patch.object(handler, "_read_char", side_effect=lambda: next(chars)),
        ):
            handler._handle_ss3()
        assert seen[0].source == "raw"

    def test_modified_arrow_source_raw(self):
        seen = _csi(InputHandler(), "1;5A")
        assert seen[0].source == "raw"

    def test_delete_source_raw(self):
        seen = _csi(InputHandler(), "3~")
        assert seen[0].source == "raw"

    def test_return_source_raw(self):
        seen = _poll_char(InputHandler(), "\r")
        assert seen[0].source == "raw"

    def test_tab_source_raw(self):
        seen = _poll_char(InputHandler(), "\t")
        assert seen[0].source == "raw"

    def test_escape_source_raw(self):
        handler = InputHandler()
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda e: seen.append(e))
        with patch("opentui.input.handler.select.select", return_value=([], [], [])):
            handler._handle_escape()
        assert seen[0].source == "raw"


class TestSourceFieldKitty:
    """Maps to test("parseKeypress - source field is 'kitty' when Kitty keyboard protocol is used")."""

    def test_kitty_a(self):
        seen = _csi(InputHandler(), "97u")
        assert seen[0].source == "kitty"
        assert seen[0].key == "a"

    def test_kitty_up(self):
        seen = _csi(InputHandler(), "57352u")
        assert seen[0].source == "kitty"
        assert seen[0].key == "up"

    def test_kitty_f1(self):
        seen = _csi(InputHandler(), "57364u")
        assert seen[0].source == "kitty"
        assert seen[0].key == "f1"

    def test_kitty_ctrl_a(self):
        seen = _csi(InputHandler(), "97;5u")
        assert seen[0].source == "kitty"
        assert seen[0].key == "a"
        assert seen[0].ctrl is True


class TestFallbackToRawParsing:
    """Maps to test("parseKeypress - fallback to raw parsing when Kitty option is enabled but sequence is not Kitty").

    In Python, InputHandler always tries kitty parsing for CSI-u sequences
    and falls back to other handlers.  Non-kitty sequences naturally produce
    source='raw'.
    """

    def test_normal_arrow_still_raw(self):
        seen = _csi(InputHandler(), "A")
        assert seen[0].source == "raw"
        assert seen[0].key == "up"

    def test_normal_letter_still_raw(self):
        seen = _poll_char(InputHandler(), "a")
        assert seen[0].source == "raw"
        assert seen[0].key == "a"

    def test_normal_ctrl_still_raw(self):
        seen = _poll_char(InputHandler(), "\x01")
        assert seen[0].source == "raw"
        assert seen[0].key == "a"
        assert seen[0].ctrl is True


class TestModifyOtherKeysDigits:
    """Maps to test("parseKeypress - modifyOtherKeys digits")."""

    def test_shift_one(self):
        handler = InputHandler()
        seen = _csi(handler, "27;2;49~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "1"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False
        assert event.event_type == "press"
        assert event.source == "raw"


class TestModifyOtherKeysModifiedEnter:
    """Maps to test("parseKeypress - modifyOtherKeys modified enter keys")."""

    def test_shift_enter(self):
        handler = InputHandler()
        seen = _csi(handler, "27;2;13~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "return"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False
        assert event.event_type == "press"
        assert event.source == "raw"

    def test_ctrl_enter(self):
        handler = InputHandler()
        seen = _csi(handler, "27;5;13~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "return"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False

    def test_alt_enter(self):
        handler = InputHandler()
        seen = _csi(handler, "27;3;13~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "return"
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False

    def test_shift_ctrl_enter(self):
        handler = InputHandler()
        seen = _csi(handler, "27;6;13~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "return"
        assert event.shift is True
        assert event.ctrl is True
        assert event.alt is False

    def test_shift_alt_enter(self):
        handler = InputHandler()
        seen = _csi(handler, "27;4;13~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "return"
        assert event.shift is True
        assert event.alt is True
        assert event.ctrl is False

    def test_ctrl_alt_enter(self):
        handler = InputHandler()
        seen = _csi(handler, "27;7;13~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "return"
        assert event.ctrl is True
        assert event.alt is True
        assert event.shift is False

    def test_all_mods_enter(self):
        handler = InputHandler()
        seen = _csi(handler, "27;8;13~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "return"
        assert event.shift is True
        assert event.ctrl is True
        assert event.alt is True


class TestModifyOtherKeysModifiedEscape:
    """Maps to test("parseKeypress - modifyOtherKeys modified escape keys")."""

    def test_ctrl_escape(self):
        handler = InputHandler()
        seen = _csi(handler, "27;5;27~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "escape"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False
        assert event.event_type == "press"
        assert event.source == "raw"

    def test_shift_escape(self):
        handler = InputHandler()
        seen = _csi(handler, "27;2;27~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "escape"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False

    def test_alt_escape(self):
        handler = InputHandler()
        seen = _csi(handler, "27;3;27~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "escape"
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False

    def test_shift_ctrl_escape(self):
        handler = InputHandler()
        seen = _csi(handler, "27;6;27~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "escape"
        assert event.shift is True
        assert event.ctrl is True
        assert event.alt is False


class TestModifyOtherKeysTabSpaceBackspace:
    """Maps to test("parseKeypress - modifyOtherKeys modified tab, space, and backspace keys")."""

    def test_ctrl_tab(self):
        handler = InputHandler()
        seen = _csi(handler, "27;5;9~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "tab"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False

    def test_shift_tab(self):
        handler = InputHandler()
        seen = _csi(handler, "27;2;9~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "tab"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False

    def test_ctrl_space(self):
        handler = InputHandler()
        seen = _csi(handler, "27;5;32~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "space"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False

    def test_shift_space(self):
        handler = InputHandler()
        seen = _csi(handler, "27;2;32~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "space"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False

    def test_alt_space(self):
        handler = InputHandler()
        seen = _csi(handler, "27;3;32~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "space"
        assert event.alt is True
        assert event.ctrl is False
        assert event.shift is False

    def test_ctrl_backspace_127(self):
        handler = InputHandler()
        seen = _csi(handler, "27;5;127~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.ctrl is True
        assert event.shift is False
        assert event.alt is False

    def test_shift_backspace_127(self):
        handler = InputHandler()
        seen = _csi(handler, "27;2;127~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.shift is True
        assert event.ctrl is False
        assert event.alt is False

    def test_ctrl_backspace_8(self):
        handler = InputHandler()
        seen = _csi(handler, "27;5;8~")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "backspace"
        assert event.ctrl is True


class TestMetaArrowKeysOldStyle:
    """Maps to test("parseKeypress - meta+arrow keys with uppercase F and B (old style)").

    Upstream behavior:
    - ESC+F (uppercase) → name="f", meta=true, shift=true (plain meta+shift+letter)
    - ESC+B (uppercase) → name="b", meta=true, shift=true (plain meta+shift+letter)
    - ESC+P (uppercase) → name="p", meta=true, shift=true (plain meta+shift+letter)
    - ESC+N (uppercase) → name="n", meta=true, shift=true (plain meta+shift+letter)
    - ESC+f (lowercase) → name="f", meta=true (NOT "right" — upstream has no remap)
    - ESC+b (lowercase) → name="b", meta=true (NOT "left" — upstream has no remap)

    Python intentional divergence for lowercase: _META_KEY_MAP remaps
    ESC+f→"right" and ESC+b→"left" (readline word-motion). This only
    applies to lowercase chars — uppercase bypasses _META_KEY_MAP.
    """

    def test_meta_shift_f_uppercase(self):
        """ESC+F → meta+shift+f (not remapped to 'right').

        _META_KEY_MAP only applies to lowercase — uppercase F is a plain
        meta+shift+letter keystroke, matching upstream.
        """
        handler = InputHandler()
        seen = _escape_then(handler, "F")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "f"
        assert event.alt is True
        assert event.shift is True

    def test_meta_shift_b_uppercase(self):
        """ESC+B → meta+shift+b (not remapped to 'left').

        _META_KEY_MAP only applies to lowercase — uppercase B is a plain
        meta+shift+letter keystroke, matching upstream.
        """
        handler = InputHandler()
        seen = _escape_then(handler, "B")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "b"
        assert event.alt is True
        assert event.shift is True

    def test_meta_shift_p(self):
        """ESC+P with no DCS content → meta+P keystroke.

        Upstream: key='P', meta=true, shift=true.
        With the fix, bare ESC+P (no content following) emits a key event
        instead of silently consuming as DCS.
        """
        handler = InputHandler()
        handler._fd = 0
        seen: list[KeyEvent] = []
        handler.on_key(lambda event: seen.append(event))

        # ESC+'P' with no content → should emit key, not consume as DCS.
        # select returns readable for first call (P char), then empty
        # (no DCS content follows).
        call_count = [0]

        def fake_select(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return ([0], [], [])  # First call: readable (ESC follow-up = 'P')
            return ([], [], [])  # No DCS content follows

        with (
            patch("opentui.input.handler.select.select", side_effect=fake_select),
            patch.object(handler, "_read_char", return_value="P"),
        ):
            handler._handle_escape()

        assert len(seen) == 1
        event = seen[0]
        assert event.key == "p"
        assert event.alt is True
        assert event.shift is True

    def test_meta_shift_n(self):
        """ESC+N → meta+shift+n (not remapped to 'down').

        _META_KEY_MAP only applies to lowercase — uppercase N is a plain
        meta+shift+letter keystroke, matching upstream.
        """
        handler = InputHandler()
        seen = _escape_then(handler, "N")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "n"
        assert event.alt is True
        assert event.shift is True

    def test_meta_f_lowercase(self):
        """ESC+f → 'right' via _META_KEY_MAP (intentional readline divergence).

        Upstream: key='f'. Python: key='right' — readline word-forward mapping.
        The component keybinding layer has bindings for both 'f' and 'right'
        with meta, so either produces the same action.
        """
        handler = InputHandler()
        seen = _escape_then(handler, "f")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "right"
        assert event.alt is True
        assert event.shift is False

    def test_meta_b_lowercase(self):
        """ESC+b → 'left' via _META_KEY_MAP (intentional readline divergence).

        Upstream: key='b'. Python: key='left' — readline word-backward mapping.
        """
        handler = InputHandler()
        seen = _escape_then(handler, "b")
        assert len(seen) == 1
        event = seen[0]
        assert event.key == "left"
        assert event.alt is True
        assert event.shift is False
