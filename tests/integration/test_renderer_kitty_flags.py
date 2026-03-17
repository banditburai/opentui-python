"""Port of upstream renderer.kitty-flags.test.ts.

Upstream: packages/core/src/tests/renderer.kitty-flags.test.ts
Tests ported: 17/17 (0 skipped)
"""

from opentui.renderer import (
    KITTY_FLAG_ALL_KEYS_AS_ESCAPES,
    KITTY_FLAG_ALTERNATE_KEYS,
    KITTY_FLAG_DISAMBIGUATE,
    KITTY_FLAG_EVENT_TYPES,
    KITTY_FLAG_REPORT_TEXT,
    build_kitty_keyboard_flags,
)


class TestBuildKittyKeyboardFlags:
    """Maps to top-level test() calls for buildKittyKeyboardFlags."""

    def test_null_undefined_returns_0(self):
        """Maps to test("buildKittyKeyboardFlags - null/undefined returns 0")."""
        assert build_kitty_keyboard_flags(None) == 0

    def test_empty_object_returns_disambiguate_alternate_keys(self):
        """Maps to test("buildKittyKeyboardFlags - empty object returns DISAMBIGUATE | ALTERNATE_KEYS (0b101)")."""
        expected = KITTY_FLAG_DISAMBIGUATE | KITTY_FLAG_ALTERNATE_KEYS
        assert build_kitty_keyboard_flags({}) == expected
        assert build_kitty_keyboard_flags({}) == 0b101
        assert build_kitty_keyboard_flags({}) == 5

    def test_events_false_returns_disambiguate_alternate_keys(self):
        """Maps to test("buildKittyKeyboardFlags - events: false returns DISAMBIGUATE | ALTERNATE_KEYS (0b101)")."""
        expected = KITTY_FLAG_DISAMBIGUATE | KITTY_FLAG_ALTERNATE_KEYS
        assert build_kitty_keyboard_flags({"events": False}) == expected
        assert build_kitty_keyboard_flags({"events": False}) == 0b101
        assert build_kitty_keyboard_flags({"events": False}) == 5

    def test_events_true_returns_disambiguate_alternate_keys_event_types(self):
        """Maps to test("buildKittyKeyboardFlags - events: true returns DISAMBIGUATE | ALTERNATE_KEYS | EVENT_TYPES (0b111)")."""
        expected = KITTY_FLAG_DISAMBIGUATE | KITTY_FLAG_ALTERNATE_KEYS | KITTY_FLAG_EVENT_TYPES
        assert build_kitty_keyboard_flags({"events": True}) == expected
        assert build_kitty_keyboard_flags({"events": True}) == 0b111
        assert build_kitty_keyboard_flags({"events": True}) == 7

    def test_flag_values_match_kitty_spec_constants(self):
        """Maps to test("buildKittyKeyboardFlags - flag values match kitty spec constants")."""
        assert build_kitty_keyboard_flags({}) == KITTY_FLAG_DISAMBIGUATE | KITTY_FLAG_ALTERNATE_KEYS
        assert build_kitty_keyboard_flags({"events": True}) == (
            KITTY_FLAG_DISAMBIGUATE | KITTY_FLAG_ALTERNATE_KEYS | KITTY_FLAG_EVENT_TYPES
        )

    def test_kitty_flag_constants_match_spec_bit_positions(self):
        """Maps to test("kitty flag constants match spec bit positions")."""
        assert KITTY_FLAG_DISAMBIGUATE == 1
        assert KITTY_FLAG_EVENT_TYPES == 2
        assert KITTY_FLAG_ALTERNATE_KEYS == 4
        assert KITTY_FLAG_ALL_KEYS_AS_ESCAPES == 8
        assert KITTY_FLAG_REPORT_TEXT == 16

    def test_flag_bit_positions_are_correct_powers_of_2(self):
        """Maps to test("flag bit positions are correct powers of 2")."""
        assert KITTY_FLAG_DISAMBIGUATE == 1 << 0
        assert KITTY_FLAG_EVENT_TYPES == 1 << 1
        assert KITTY_FLAG_ALTERNATE_KEYS == 1 << 2
        assert KITTY_FLAG_ALL_KEYS_AS_ESCAPES == 1 << 3
        assert KITTY_FLAG_REPORT_TEXT == 1 << 4

    def test_flags_can_be_combined_with_bitwise_or(self):
        """Maps to test("flags can be combined with bitwise OR")."""
        combined = KITTY_FLAG_ALTERNATE_KEYS | KITTY_FLAG_EVENT_TYPES
        assert combined == 0b110
        assert combined == 6
        assert combined & KITTY_FLAG_ALTERNATE_KEYS
        assert combined & KITTY_FLAG_EVENT_TYPES
        assert not (combined & KITTY_FLAG_DISAMBIGUATE)

    def test_escape_sequences_match_kitty_spec_format(self):
        """Maps to test("escape sequences match kitty spec format")."""
        default_flags = build_kitty_keyboard_flags({})
        assert default_flags == 5  # \x1b[>5u

        with_events_flags = build_kitty_keyboard_flags({"events": True})
        assert with_events_flags == 7  # \x1b[>7u

    def test_default_config_enables_disambiguate_and_alternate_keys(self):
        """Maps to test("default config enables disambiguate and alternate keys")."""
        flags = build_kitty_keyboard_flags({})
        assert flags & KITTY_FLAG_DISAMBIGUATE
        assert flags & KITTY_FLAG_ALTERNATE_KEYS
        assert not (flags & KITTY_FLAG_EVENT_TYPES)
        assert not (flags & KITTY_FLAG_ALL_KEYS_AS_ESCAPES)
        assert not (flags & KITTY_FLAG_REPORT_TEXT)

    def test_events_config_adds_event_type_reporting(self):
        """Maps to test("events config adds event type reporting")."""
        flags = build_kitty_keyboard_flags({"events": True})
        assert flags & KITTY_FLAG_DISAMBIGUATE
        assert flags & KITTY_FLAG_ALTERNATE_KEYS
        assert flags & KITTY_FLAG_EVENT_TYPES
        assert not (flags & KITTY_FLAG_ALL_KEYS_AS_ESCAPES)
        assert not (flags & KITTY_FLAG_REPORT_TEXT)

    def test_disambiguate_flag_solves_key_ambiguity_issues(self):
        """Maps to test("disambiguate flag solves key ambiguity issues")."""
        flags = build_kitty_keyboard_flags({})
        assert flags & KITTY_FLAG_DISAMBIGUATE

    def test_can_explicitly_disable_disambiguate(self):
        """Maps to test("can explicitly disable disambiguate")."""
        flags = build_kitty_keyboard_flags({"disambiguate": False})
        assert not (flags & KITTY_FLAG_DISAMBIGUATE)
        assert flags & KITTY_FLAG_ALTERNATE_KEYS  # still enabled by default

    def test_can_explicitly_disable_alternate_keys(self):
        """Maps to test("can explicitly disable alternateKeys")."""
        flags = build_kitty_keyboard_flags({"alternateKeys": False})
        assert not (flags & KITTY_FLAG_ALTERNATE_KEYS)
        assert flags & KITTY_FLAG_DISAMBIGUATE  # still enabled by default

    def test_can_disable_both_disambiguate_and_alternate_keys(self):
        """Maps to test("can disable both disambiguate and alternateKeys")."""
        flags = build_kitty_keyboard_flags({"disambiguate": False, "alternateKeys": False})
        assert flags == 0

    def test_can_enable_all_flags(self):
        """Maps to test("can enable all flags")."""
        flags = build_kitty_keyboard_flags(
            {
                "disambiguate": True,
                "alternateKeys": True,
                "events": True,
                "allKeysAsEscapes": True,
                "reportText": True,
            }
        )
        expected = (
            KITTY_FLAG_DISAMBIGUATE
            | KITTY_FLAG_ALTERNATE_KEYS
            | KITTY_FLAG_EVENT_TYPES
            | KITTY_FLAG_ALL_KEYS_AS_ESCAPES
            | KITTY_FLAG_REPORT_TEXT
        )
        assert flags == expected
        assert flags == 0b11111
        assert flags == 31

    def test_optional_flags_default_to_false(self):
        """Maps to test("optional flags default to false")."""
        flags = build_kitty_keyboard_flags({})
        # These default to True
        assert flags & KITTY_FLAG_DISAMBIGUATE
        assert flags & KITTY_FLAG_ALTERNATE_KEYS
        # These default to False
        assert not (flags & KITTY_FLAG_EVENT_TYPES)
        assert not (flags & KITTY_FLAG_ALL_KEYS_AS_ESCAPES)
        assert not (flags & KITTY_FLAG_REPORT_TEXT)
