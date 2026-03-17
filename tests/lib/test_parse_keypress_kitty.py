"""Port of upstream parse.keypress-kitty.test.ts.

Upstream: packages/core/src/lib/parse.keypress-kitty.test.ts
Tests ported: 34/34 (0 skipped, 1 sub-test skipped)

Previously skipped, now implemented with Python-specific adaptations:
  - "Kitty keyboard protocol disabled by default" — uses InputHandler(use_kitty_keyboard=False)
  - "Kitty keyboard invalid codepoint" — _handle_kitty_keyboard rejects invalid codepoints

Skipped sub-tests:
  - empty event type in "invalid event types" — _KITTY_KEY_RE requires digit after colon

Name differences between upstream TS and Python _KITTY_KEY_MAP:
  - kpminus/kpplus -> kpsubtract/kpadd
  - leftctrl/rightctrl -> leftcontrol/rightcontrol
  - medianext/mediaprev -> mediatracknext/mediatrackprevious
  - volumedown/volumeup/mute -> lowervolume/raisevolume/mutevolume
  - iso_level3_shift/iso_level5_shift -> isolevel3shift/isolevel5shift
"""

import pytest

from opentui.events import KeyEvent
from opentui.input import InputHandler


def _parse_kitty(csi_body: str) -> KeyEvent | None:
    """Feed a kitty CSI-u sequence body to InputHandler and return the KeyEvent.

    The *csi_body* is the part after ESC[ — e.g. "97u" or "97;5u".
    Returns None if no key event was emitted.
    """
    handler = InputHandler()
    captured: list[KeyEvent] = []
    handler.on_key(lambda ev: captured.append(ev))
    handler._dispatch_csi_sequence(csi_body)
    return captured[0] if captured else None


# ── Test: Kitty keyboard protocol disabled by default ────────────


class TestKittyKeyboardProtocolDisabledByDefault:
    """Maps to test("parseKeypress - Kitty keyboard protocol disabled by default").

    Upstream: when ``useKittyKeyboard`` is not set, kitty CSI-u sequences
    fall through to regular parsing and the key is unrecognised (name="",
    code=undefined).

    Python adaptation: ``InputHandler(use_kitty_keyboard=False)`` skips
    kitty parsing.  The CSI body ``"97u"`` does not match any legacy
    handler, so it falls through to the catch-all which emits
    ``key="unknown-97u"``.
    """

    def test_kitty_disabled_by_default(self):
        handler = InputHandler(use_kitty_keyboard=False)
        captured: list[KeyEvent] = []
        handler.on_key(lambda ev: captured.append(ev))
        handler._dispatch_csi_sequence("97u")
        assert len(captured) == 1
        result = captured[0]
        # Kitty parsing was skipped — the sequence is not recognised by
        # legacy handlers, so the key name is the catch-all "unknown-…".
        assert result.key == "unknown-97u"
        assert result.source == "raw"


# ── Test: Kitty keyboard basic key ───────────────────────────────


class TestKittyKeyboardBasicKey:
    """Maps to test("parseKeypress - Kitty keyboard basic key")."""

    def test_basic_key_a(self):
        result = _parse_kitty("97u")
        assert result is not None
        assert result.key == "a"
        assert result.sequence == "a"
        assert result.ctrl is False
        assert result.alt is False
        assert result.shift is False


# ── Test: Kitty keyboard shift+a ─────────────────────────────────


class TestKittyKeyboardShiftA:
    """Maps to test("parseKeypress - Kitty keyboard shift+a")."""

    def test_shift_a(self):
        result = _parse_kitty("97:65;2u")
        assert result is not None
        assert result.key == "a"
        assert result.sequence == "A"
        assert result.shift is True
        assert result.ctrl is False
        assert result.alt is False


# ── Test: Kitty keyboard ctrl+a ──────────────────────────────────


class TestKittyKeyboardCtrlA:
    """Maps to test("parseKeypress - Kitty keyboard ctrl+a")."""

    def test_ctrl_a(self):
        result = _parse_kitty("97;5u")
        assert result is not None
        assert result.key == "a"
        assert result.ctrl is True
        assert result.shift is False
        assert result.alt is False


# ── Test: Kitty keyboard alt+a ───────────────────────────────────


class TestKittyKeyboardAltA:
    """Maps to test("parseKeypress - Kitty keyboard alt+a")."""

    def test_alt_a(self):
        # modifier 3 - 1 = 2 = alt bit
        result = _parse_kitty("97;3u")
        assert result is not None
        assert result.key == "a"
        assert result.alt is True  # TS: meta=true, option=true; Python: alt=true
        assert result.ctrl is False
        assert result.shift is False


# ── Test: Kitty keyboard function key ────────────────────────────


class TestKittyKeyboardFunctionKey:
    """Maps to test("parseKeypress - Kitty keyboard function key")."""

    def test_f1(self):
        result = _parse_kitty("57364u")
        assert result is not None
        assert result.key == "f1"
        assert result.code == "\x1b[57364u"


# ── Test: Kitty keyboard arrow key ───────────────────────────────


class TestKittyKeyboardArrowKey:
    """Maps to test("parseKeypress - Kitty keyboard arrow key")."""

    def test_up(self):
        result = _parse_kitty("57352u")
        assert result is not None
        assert result.key == "up"
        assert result.code == "\x1b[57352u"


# ── Test: Kitty keyboard shift+space ─────────────────────────────


class TestKittyKeyboardShiftSpace:
    """Maps to test("parseKeypress - Kitty keyboard shift+space")."""

    def test_shift_space(self):
        result = _parse_kitty("32;2u")
        assert result is not None
        assert result.key == "space"
        assert result.sequence == " "
        assert result.shift is True


# ── Test: Kitty keyboard event types ─────────────────────────────


class TestKittyKeyboardEventTypes:
    """Maps to test("parseKeypress - Kitty keyboard event types")."""

    def test_press_explicit(self):
        result = _parse_kitty("97;1:1u")
        assert result is not None
        assert result.key == "a"
        assert result.event_type == "press"

    def test_press_default(self):
        result = _parse_kitty("97u")
        assert result is not None
        assert result.key == "a"
        assert result.event_type == "press"

    def test_press_with_modifier(self):
        # Ctrl+a, no explicit event type
        result = _parse_kitty("97;5u")
        assert result is not None
        assert result.key == "a"
        assert result.ctrl is True
        assert result.event_type == "press"

    def test_repeat_event(self):
        result = _parse_kitty("97;1:2u")
        assert result is not None
        assert result.key == "a"
        assert result.event_type == "press"
        assert result.repeated is True

    def test_release_event(self):
        result = _parse_kitty("97;1:3u")
        assert result is not None
        assert result.key == "a"
        assert result.event_type == "release"

    def test_repeat_with_ctrl(self):
        result = _parse_kitty("97;5:2u")
        assert result is not None
        assert result.key == "a"
        assert result.ctrl is True
        assert result.event_type == "press"
        assert result.repeated is True

    def test_release_with_shift(self):
        result = _parse_kitty("97;2:3u")
        assert result is not None
        assert result.key == "a"
        assert result.shift is True
        assert result.event_type == "release"


# ── Test: Kitty keyboard with text ───────────────────────────────


class TestKittyKeyboardWithText:
    """Maps to test("parseKeypress - Kitty keyboard with text")."""

    def test_with_text_field(self):
        result = _parse_kitty("97;1;97u")
        assert result is not None
        assert result.key == "a"


# ── Test: Kitty keyboard ctrl+shift+a ────────────────────────────


class TestKittyKeyboardCtrlShiftA:
    """Maps to test("parseKeypress - Kitty keyboard ctrl+shift+a")."""

    def test_ctrl_shift_a(self):
        result = _parse_kitty("97;6u")
        assert result is not None
        assert result.key == "a"
        assert result.ctrl is True
        assert result.shift is True
        assert result.alt is False


# ── Test: Kitty keyboard alt+shift+a ─────────────────────────────


class TestKittyKeyboardAltShiftA:
    """Maps to test("parseKeypress - Kitty keyboard alt+shift+a")."""

    def test_alt_shift_a(self):
        result = _parse_kitty("97;4u")
        assert result is not None
        assert result.key == "a"
        assert result.alt is True  # TS: meta=true, option=true
        assert result.shift is True
        assert result.ctrl is False


# ── Test: Kitty keyboard super+a ─────────────────────────────────


class TestKittyKeyboardSuperA:
    """Maps to test("parseKeypress - Kitty keyboard super+a")."""

    def test_super_a(self):
        # modifier 9 - 1 = 8 = super/meta bit
        # Python maps kitty super (bit 3) to meta field
        result = _parse_kitty("97;9u")
        assert result is not None
        assert result.key == "a"
        assert result.meta is True


# ── Test: Kitty keyboard hyper+a ─────────────────────────────────


class TestKittyKeyboardHyperA:
    """Maps to test("parseKeypress - Kitty keyboard hyper+a")."""

    def test_hyper_a(self):
        # modifier 17 - 1 = 16 = hyper bit
        result = _parse_kitty("97;17u")
        assert result is not None
        assert result.key == "a"
        assert result.hyper is True


# ── Test: Kitty keyboard with shifted codepoint ──────────────────


class TestKittyKeyboardWithShiftedCodepoint:
    """Maps to test("parseKeypress - Kitty keyboard with shifted codepoint")."""

    def test_shifted_codepoint_no_shift(self):
        result = _parse_kitty("97:65u")
        assert result is not None
        assert result.key == "a"
        assert result.sequence == "a"  # No shift pressed, so base character
        assert result.shift is False


# ── Test: Kitty keyboard with base layout codepoint ──────────────


class TestKittyKeyboardWithBaseLayoutCodepoint:
    """Maps to test("parseKeypress - Kitty keyboard with base layout codepoint")."""

    def test_base_layout_codepoint(self):
        """Upstream: parseKeypress('\\x1b[97:65:97u') -> baseCode == 97."""
        result = _parse_kitty("97:65:97u")
        assert result is not None
        assert result.key == "a"
        assert result.sequence == "a"  # No shift, so base character
        assert result.shift is False
        assert result.base_code == 97  # Base layout codepoint is 'a'


# ── Test: Kitty keyboard different layout (AZERTY) ───────────────


class TestKittyKeyboardDifferentLayout:
    """Maps to test("parseKeypress - Kitty keyboard different layout (QWERTY A key on AZERTY)")."""

    def test_azerty_layout(self):
        """Upstream: parseKeypress('\\x1b[97:65:113u') -> baseCode == 113."""
        # On AZERTY, Q key produces 'a', but base layout says it's Q position
        result = _parse_kitty("97:65:113u")  # 113 = 'q'
        assert result is not None
        assert result.key == "a"  # Actual character produced
        assert result.sequence == "a"
        assert result.base_code == 113  # Physical key position is Q


# ── Test: Kitty keyboard caps lock ───────────────────────────────


class TestKittyKeyboardCapsLock:
    """Maps to test("parseKeypress - Kitty keyboard caps lock")."""

    def test_caps_lock(self):
        # modifier 65 - 1 = 64 = caps lock bit
        result = _parse_kitty("97;65u")
        assert result is not None
        assert result.key == "a"
        assert result.caps_lock is True


# ── Test: Kitty keyboard num lock ────────────────────────────────


class TestKittyKeyboardNumLock:
    """Maps to test("parseKeypress - Kitty keyboard num lock")."""

    def test_num_lock(self):
        # modifier 129 - 1 = 128 = num lock bit
        result = _parse_kitty("97;129u")
        assert result is not None
        assert result.key == "a"
        assert result.num_lock is True


# ── Test: Kitty keyboard unicode character ───────────────────────


class TestKittyKeyboardUnicodeCharacter:
    """Maps to test("parseKeypress - Kitty keyboard unicode character")."""

    def test_unicode_e_acute(self):
        # 233 = e with acute (U+00E9)
        result = _parse_kitty("233u")
        assert result is not None
        assert result.key == "\u00e9"
        assert result.sequence == "\u00e9"


# ── Test: Kitty keyboard emoji ───────────────────────────────────


class TestKittyKeyboardEmoji:
    """Maps to test("parseKeypress - Kitty keyboard emoji")."""

    def test_emoji_grinning_face(self):
        # 128512 = U+1F600
        result = _parse_kitty("128512u")
        assert result is not None
        assert result.key == "\U0001f600"
        assert result.sequence == "\U0001f600"


# ── Test: Kitty keyboard invalid codepoint ───────────────────────


class TestKittyKeyboardInvalidCodepoint:
    """Maps to test("parseKeypress - Kitty keyboard invalid codepoint").

    Upstream: ``parseKittyKeyboard`` returns ``null`` for codepoints
    above ``0x10FFFF``, causing ``parseKeypress`` to fall back to the
    legacy regex parser which produces ``name=""``, ``ctrl=true``, etc.

    Python adaptation: ``_handle_kitty_keyboard`` returns ``False`` for
    invalid codepoints, and the CSI dispatcher falls through to the
    catch-all handler which emits ``key="unknown-1114112u"`` with
    ``source="raw"``.  We verify the kitty parser correctly rejects the
    invalid codepoint (source is NOT "kitty") and that the fallback
    produces a result.
    """

    def test_invalid_codepoint(self):
        result = _parse_kitty("1114112u")
        assert result is not None
        # The kitty parser rejected the invalid codepoint (> 0x10FFFF),
        # so the event comes from the fallback legacy handler.
        assert result.source == "raw"
        assert result.key == "unknown-1114112u"


# ── Test: Kitty keyboard keypad keys ─────────────────────────────


class TestKittyKeyboardKeypadKeys:
    """Maps to test("parseKeypress - Kitty keyboard keypad keys")."""

    def test_kp0(self):
        result = _parse_kitty("57399u")
        assert result is not None
        assert result.key == "kp0"

    def test_kpenter(self):
        result = _parse_kitty("57414u")
        assert result is not None
        assert result.key == "kpenter"


# ── Test: Kitty keyboard media keys ──────────────────────────────


class TestKittyKeyboardMediaKeys:
    """Maps to test("parseKeypress - Kitty keyboard media keys")."""

    def test_mediaplay(self):
        result = _parse_kitty("57428u")
        assert result is not None
        assert result.key == "mediaplay"

    def test_volumeup(self):
        # Python maps 57439 to "raisevolume" (upstream: "volumeup")
        result = _parse_kitty("57439u")
        assert result is not None
        assert result.key == "raisevolume"


# ── Test: Kitty keyboard modifier keys ───────────────────────────


class TestKittyKeyboardModifierKeys:
    """Maps to test("parseKeypress - Kitty keyboard modifier keys")."""

    def test_leftshift(self):
        result = _parse_kitty("57441u")
        assert result is not None
        assert result.key == "leftshift"
        assert result.event_type == "press"

    def test_rightctrl(self):
        # Python maps 57448 to "rightcontrol" (upstream: "rightctrl")
        result = _parse_kitty("57448u")
        assert result is not None
        assert result.key == "rightcontrol"
        assert result.event_type == "press"


# ── Test: Kitty keyboard function keys with event types ──────────


class TestKittyKeyboardFunctionKeysWithEventTypes:
    """Maps to test("parseKeypress - Kitty keyboard function keys with event types")."""

    def test_f1_press(self):
        result = _parse_kitty("57364u")
        assert result is not None
        assert result.key == "f1"
        assert result.event_type == "press"

    def test_f1_repeat(self):
        result = _parse_kitty("57364;1:2u")
        assert result is not None
        assert result.key == "f1"
        assert result.event_type == "press"
        assert result.repeated is True

    def test_f1_release(self):
        result = _parse_kitty("57364;1:3u")
        assert result is not None
        assert result.key == "f1"
        assert result.event_type == "release"


# ── Test: Kitty keyboard arrow keys with event types ─────────────


class TestKittyKeyboardArrowKeysWithEventTypes:
    """Maps to test("parseKeypress - Kitty keyboard arrow keys with event types")."""

    def test_up_press(self):
        result = _parse_kitty("57352u")
        assert result is not None
        assert result.key == "up"
        assert result.event_type == "press"

    def test_up_repeat_ctrl(self):
        result = _parse_kitty("57352;5:2u")
        assert result is not None
        assert result.key == "up"
        assert result.ctrl is True
        assert result.event_type == "press"
        assert result.repeated is True

    def test_down_release(self):
        result = _parse_kitty("57353;1:3u")
        assert result is not None
        assert result.key == "down"
        assert result.event_type == "release"


# ── Test: Kitty functional keys with event types ─────────────────
# (CSI 1;modifier:event_type LETTER — dispatched via xterm modified key path)


class TestKittyFunctionalKeysWithEventTypes:
    """Maps to test("parseKeypress - Kitty functional keys with event types")."""

    def test_up_press(self):
        result = _parse_kitty("1;1:1A")
        assert result is not None
        assert result.key == "up"
        assert result.event_type == "press"

    def test_up_release(self):
        result = _parse_kitty("1;1:3A")
        assert result is not None
        assert result.key == "up"
        assert result.event_type == "release"

    def test_down_repeat(self):
        result = _parse_kitty("1;1:2B")
        assert result is not None
        assert result.key == "down"
        assert result.event_type == "press"
        assert result.repeated is True

    def test_left_press(self):
        result = _parse_kitty("1;1:1D")
        assert result is not None
        assert result.key == "left"
        assert result.event_type == "press"

    def test_right_release(self):
        result = _parse_kitty("1;1:3C")
        assert result is not None
        assert result.key == "right"
        assert result.event_type == "release"

    def test_shift_up_press(self):
        result = _parse_kitty("1;2:1A")
        assert result is not None
        assert result.key == "up"
        assert result.shift is True
        assert result.event_type == "press"

    def test_ctrl_down_release(self):
        result = _parse_kitty("1;5:3B")
        assert result is not None
        assert result.key == "down"
        assert result.ctrl is True
        assert result.event_type == "release"


# ── Test: Kitty tilde keys with event types ──────────────────────


class TestKittyTildeKeysWithEventTypes:
    """Maps to test("parseKeypress - Kitty tilde keys with event types")."""

    def test_pageup_press(self):
        result = _parse_kitty("5;1:1~")
        assert result is not None
        assert result.key == "pageup"
        assert result.event_type == "press"

    def test_pageup_repeat(self):
        result = _parse_kitty("5;1:2~")
        assert result is not None
        assert result.key == "pageup"
        assert result.event_type == "press"
        assert result.repeated is True

    def test_pageup_release(self):
        result = _parse_kitty("5;1:3~")
        assert result is not None
        assert result.key == "pageup"
        assert result.event_type == "release"

    def test_pagedown_repeat(self):
        result = _parse_kitty("6;1:2~")
        assert result is not None
        assert result.key == "pagedown"
        assert result.repeated is True

    def test_shift_insert(self):
        result = _parse_kitty("2;2:1~")
        assert result is not None
        assert result.key == "insert"
        assert result.shift is True
        assert result.event_type == "press"

    def test_ctrl_delete(self):
        result = _parse_kitty("3;5:1~")
        assert result is not None
        assert result.key == "delete"
        assert result.ctrl is True

    def test_home_press(self):
        result = _parse_kitty("1;1:1~")
        assert result is not None
        assert result.key == "home"

    def test_end_release(self):
        result = _parse_kitty("4;1:3~")
        assert result is not None
        assert result.key == "end"
        assert result.event_type == "release"

    def test_f5_press(self):
        result = _parse_kitty("15;1:1~")
        assert result is not None
        assert result.key == "f5"

    def test_f12_repeat(self):
        result = _parse_kitty("24;1:2~")
        assert result is not None
        assert result.key == "f12"
        assert result.repeated is True


# ── Test: Kitty keyboard invalid event types ─────────────────────


class TestKittyKeyboardInvalidEventTypes:
    """Maps to test("parseKeypress - Kitty keyboard invalid event types")."""

    def test_unknown_event_type_defaults_to_press(self):
        result = _parse_kitty("97;1:9u")
        assert result is not None
        assert result.key == "a"
        assert result.event_type == "press"

    def test_empty_event_type_defaults_to_press(self):
        """Upstream: '97;1:u' with empty event_type after colon defaults to press."""
        result = _parse_kitty("97;1:u")
        assert result is not None
        assert result.key == "a"
        assert result.event_type == "press"


# ── Test: Kitty progressive enhancement fallback ─────────────────


class TestKittyProgressiveEnhancementFallback:
    """Maps to test("parseKeypress - Kitty progressive enhancement fallback")."""

    def test_shift_up_xterm_format(self):
        # CSI 1;2A = Shift+Up (standard xterm modified key)
        result = _parse_kitty("1;2A")
        assert result is not None
        assert result.key == "up"
        assert result.shift is True


# ── Test: Kitty sequences bypass terminal response filters ───────


class TestKittySequencesBypassFilters:
    """Maps to test("parseKeypress - Kitty sequences are NOT filtered by terminal response filters")."""

    @pytest.mark.parametrize(
        "letter,code",
        [
            ("a", 97),
            ("z", 122),
            ("A", 65),
            ("Z", 90),
            ("0", 48),
            ("9", 57),
        ],
    )
    def test_basic_letters_have_kitty_source(self, letter, code):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            (27, "escape"),
            (9, "tab"),
            (13, "return"),
            (127, "backspace"),
        ],
    )
    def test_standard_keys(self, code, expected_name):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == expected_name

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            (57350, "left"),
            (57351, "right"),
            (57352, "up"),
            (57353, "down"),
        ],
    )
    def test_arrow_keys(self, code, expected_name):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == expected_name

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            (57348, "insert"),
            (57349, "delete"),
            (57354, "pageup"),
            (57355, "pagedown"),
            (57356, "home"),
            (57357, "end"),
        ],
    )
    def test_navigation_keys(self, code, expected_name):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == expected_name

    @pytest.mark.parametrize("i", range(1, 36))
    def test_function_keys_f1_to_f35(self, i):
        code = 57363 + i
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == f"f{i}"

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            (57399, "kp0"),
            (57400, "kp1"),
            (57408, "kp9"),
            (57409, "kpdecimal"),
            (57410, "kpdivide"),
            (57411, "kpmultiply"),
            # Upstream: kpminus/kpplus; Python: kpsubtract/kpadd
            (57412, "kpsubtract"),
            (57413, "kpadd"),
            (57414, "kpenter"),
            (57415, "kpequal"),
        ],
    )
    def test_keypad_keys(self, code, expected_name):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == expected_name

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            (57428, "mediaplay"),
            (57429, "mediapause"),
            (57430, "mediaplaypause"),
            (57431, "mediareverse"),
            (57432, "mediastop"),
            (57433, "mediafastforward"),
            (57434, "mediarewind"),
            # Upstream: medianext/mediaprev; Python: mediatracknext/mediatrackprevious
            (57435, "mediatracknext"),
            (57436, "mediatrackprevious"),
            (57437, "mediarecord"),
        ],
    )
    def test_media_keys(self, code, expected_name):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == expected_name

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            # Upstream: volumedown/volumeup/mute; Python: lowervolume/raisevolume/mutevolume
            (57438, "lowervolume"),
            (57439, "raisevolume"),
            (57440, "mutevolume"),
        ],
    )
    def test_volume_keys(self, code, expected_name):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == expected_name

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            (57441, "leftshift"),
            # Upstream: leftctrl/rightctrl; Python: leftcontrol/rightcontrol
            (57442, "leftcontrol"),
            (57443, "leftalt"),
            (57444, "leftsuper"),
            (57445, "lefthyper"),
            (57446, "leftmeta"),
            (57447, "rightshift"),
            (57448, "rightcontrol"),
            (57449, "rightalt"),
            (57450, "rightsuper"),
            (57451, "righthyper"),
            (57452, "rightmeta"),
        ],
    )
    def test_modifier_keys(self, code, expected_name):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == expected_name

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            # Upstream: iso_level3_shift/iso_level5_shift; Python: isolevel3shift/isolevel5shift
            (57453, "isolevel3shift"),
            (57454, "isolevel5shift"),
        ],
    )
    def test_iso_keys(self, code, expected_name):
        result = _parse_kitty(f"{code}u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == expected_name

    def test_key_with_ctrl_modifier(self):
        # Ctrl+a = 97;5u
        result = _parse_kitty("97;5u")
        assert result is not None
        assert result.source == "kitty"
        assert result.ctrl is True

    def test_key_with_release_event_type(self):
        # 'a' release = 97;1:3u
        result = _parse_kitty("97;1:3u")
        assert result is not None
        assert result.source == "kitty"
        assert result.event_type == "release"

    def test_complex_sequence_all_fields(self):
        # unicode:shifted:base ; modifiers:event ; text = 97:65:113;5:2;97u
        result = _parse_kitty("97:65:113;5:2;97u")
        assert result is not None
        assert result.source == "kitty"
        assert result.ctrl is True
        assert result.event_type == "press"
        assert result.repeated is True

    def test_unicode_character(self):
        # 233 = e with acute (U+00E9)
        result = _parse_kitty("233u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == "\u00e9"

    def test_emoji(self):
        # 128512 = U+1F600
        result = _parse_kitty("128512u")
        assert result is not None
        assert result.source == "kitty"
        assert result.key == "\U0001f600"


# ── Test: Kitty keyboard shift+letter without shifted codepoint ──


class TestKittyKeyboardShiftLetterWithoutShiftedCodepoint:
    """Maps to test("parseKeypress - Kitty keyboard shift+letter without shifted codepoint")."""

    def test_shift_a_no_shifted_codepoint(self):
        result = _parse_kitty("97;2u")
        assert result is not None
        assert result.key == "a"
        assert result.shift is True
        assert result.sequence == "A"


# ── Test: Kitty keyboard shift+Cyrillic without shifted codepoint


class TestKittyKeyboardShiftCyrillicWithoutShiftedCodepoint:
    """Maps to test("parseKeypress - Kitty keyboard shift+Cyrillic without shifted codepoint")."""

    def test_shift_cyrillic_a(self):
        # 1072 = Cyrillic small letter A (U+0430)
        result = _parse_kitty("1072;2u")
        assert result is not None
        assert result.key == "\u0430"  # Cyrillic small 'a'
        assert result.shift is True
        assert result.sequence == "\u0410"  # Cyrillic capital 'A'
