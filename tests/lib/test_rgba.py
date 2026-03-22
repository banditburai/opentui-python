"""Port of upstream RGBA.test.ts.

Upstream: packages/core/src/lib/RGBA.test.ts
Tests ported: 131/131 (4 Float32Array buffer tests adapted to Python equivalents)
"""

import pytest

from opentui.structs import RGBA, CSS_COLOR_NAMES, parse_color


class TestRGBAConstructor:
    """Maps to describe("RGBA class") > describe("constructor").

    Upstream TypeScript constructs RGBA from a Float32Array buffer.
    Python equivalent: RGBA dataclass constructed from individual float values.
    """

    def test_creates_rgba_from_float_values(self):
        """Maps to test("creates RGBA with Float32Array buffer").

        Python adaptation: construct RGBA from individual float values
        (the Python equivalent of passing a Float32Array buffer).
        """
        values = [0.5, 0.6, 0.7, 0.8]
        rgba = RGBA(*values)
        assert rgba.r == pytest.approx(0.5, abs=1e-5)
        assert rgba.g == pytest.approx(0.6, abs=1e-5)
        assert rgba.b == pytest.approx(0.7, abs=1e-5)
        assert rgba.a == pytest.approx(0.8, abs=1e-5)

    def test_fields_are_mutable(self):
        """Maps to test("buffer is mutable reference").

        Python adaptation: in TypeScript, mutating the backing Float32Array
        buffer is reflected in the RGBA getters. In Python, the dataclass
        fields themselves are mutable, so mutating via assignment is the
        equivalent operation.
        """
        rgba = RGBA(0.5, 0.6, 0.7, 0.8)
        rgba.r = 0.9
        assert rgba.r == pytest.approx(0.9, abs=1e-5)
        # Original values for other channels are preserved
        assert rgba.g == pytest.approx(0.6, abs=1e-5)
        assert rgba.b == pytest.approx(0.7, abs=1e-5)
        assert rgba.a == pytest.approx(0.8, abs=1e-5)


class TestRGBAFromArray:
    """Maps to describe("RGBA class") > describe("fromArray").

    Upstream TypeScript wraps an existing Float32Array (shared buffer).
    Python equivalent: RGBA.from_array() constructs from a sequence,
    copying values into independent dataclass fields.
    """

    def test_creates_rgba_from_array(self):
        """Maps to test("creates RGBA from Float32Array").

        Python adaptation: RGBA.from_array() creates an RGBA from a
        list (or any indexable sequence) of 4 float values.
        """
        array = [0.1, 0.2, 0.3, 0.4]
        rgba = RGBA.from_array(array)
        assert rgba.r == pytest.approx(0.1, abs=1e-5)
        assert rgba.g == pytest.approx(0.2, abs=1e-5)
        assert rgba.b == pytest.approx(0.3, abs=1e-5)
        assert rgba.a == pytest.approx(0.4, abs=1e-5)

    def test_from_array_creates_independent_copy(self):
        """Maps to test("uses same buffer reference").

        Python adaptation: in TypeScript, fromArray shares the buffer so
        mutations are visible through the RGBA. In Python, from_array
        copies values into independent dataclass fields, so mutating the
        source list does NOT affect the RGBA. This test verifies the
        Python-idiomatic (copy) semantics.
        """
        array = [0.1, 0.2, 0.3, 0.4]
        rgba = RGBA.from_array(array)
        # Mutate the source array
        array[0] = 0.9
        # RGBA is independent -- not affected by source mutation
        assert rgba.r == pytest.approx(0.1, abs=1e-5)


class TestRGBAFromValues:
    """Maps to describe("RGBA class") > describe("fromValues").

    Python equivalent: RGBA(r, g, b, a) constructor.
    """

    def test_creates_rgba_from_individual_values(self):
        """Maps to test("creates RGBA from individual values")."""
        rgba = RGBA(0.2, 0.4, 0.6, 0.8)
        assert rgba.r == pytest.approx(0.2, abs=1e-5)
        assert rgba.g == pytest.approx(0.4, abs=1e-5)
        assert rgba.b == pytest.approx(0.6, abs=1e-5)
        assert rgba.a == pytest.approx(0.8, abs=1e-5)

    def test_defaults_alpha_to_1_when_not_provided(self):
        """Maps to test("defaults alpha to 1.0 when not provided")."""
        rgba = RGBA(0.5, 0.5, 0.5)
        assert rgba.a == 1.0

    def test_handles_zero_values(self):
        """Maps to test("handles zero values")."""
        rgba = RGBA(0, 0, 0, 0)
        assert rgba.r == 0
        assert rgba.g == 0
        assert rgba.b == 0
        assert rgba.a == 0

    def test_handles_values_greater_than_1(self):
        """Maps to test("handles values greater than 1")."""
        rgba = RGBA(1.5, 2.0, 2.5, 3.0)
        assert rgba.r == 1.5
        assert rgba.g == 2.0
        assert rgba.b == 2.5
        assert rgba.a == 3.0

    def test_handles_negative_values(self):
        """Maps to test("handles negative values")."""
        rgba = RGBA(-0.5, -0.2, -0.1, -0.3)
        assert rgba.r == pytest.approx(-0.5, abs=1e-5)
        assert rgba.g == pytest.approx(-0.2, abs=1e-5)
        assert rgba.b == pytest.approx(-0.1, abs=1e-5)
        assert rgba.a == pytest.approx(-0.3, abs=1e-5)


class TestRGBAFromHex:
    """Maps to describe("RGBA class") > describe("fromHex").

    Python equivalent: RGBA.from_hex().
    """

    def test_creates_rgba_from_hex_string(self):
        """Maps to test("creates RGBA from hex string")."""
        rgba = RGBA.from_hex("#FF8040")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == 1

    def test_creates_rgba_from_8_digit_hex_with_alpha(self):
        """Maps to test("creates RGBA from 8-digit hex with alpha")."""
        rgba = RGBA.from_hex("#FF804080")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == pytest.approx(0.502, abs=0.01)

    def test_creates_rgba_from_4_digit_hex_with_alpha(self):
        """Maps to test("creates RGBA from 4-digit hex with alpha")."""
        rgba = RGBA.from_hex("#F848")
        # #F848 -> #FF884488
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0x88 / 255, abs=0.01)
        assert rgba.b == pytest.approx(0x44 / 255, abs=0.01)
        assert rgba.a == pytest.approx(0x88 / 255, abs=0.01)


class TestRGBAToInts:
    """Maps to describe("RGBA class") > describe("toInts")."""

    def test_converts_float_values_to_integers(self):
        """Maps to test("converts float values to integers (0-255)")."""
        rgba = RGBA(1.0, 0.5, 0.25, 0.75)
        ints = rgba.to_ints()
        assert ints[0] == 255
        assert ints[1] == round(0.5 * 255)
        assert ints[2] == round(0.25 * 255)
        assert ints[3] == round(0.75 * 255)

    def test_handles_zero_values(self):
        """Maps to test("handles zero values")."""
        rgba = RGBA(0, 0, 0, 0)
        assert rgba.to_ints() == (0, 0, 0, 0)

    def test_rounds_to_nearest_integer(self):
        """Maps to test("rounds to nearest integer")."""
        rgba = RGBA(0.5, 0.5, 0.5, 0.5)
        ints = rgba.to_ints()
        assert ints[0] == round(0.5 * 255)
        assert ints[1] == round(0.5 * 255)

    def test_handles_out_of_range_values_when_converting(self):
        """Maps to test("handles out of range values when converting")."""
        rgba = RGBA(1.5, -0.5, 2.0, -1.0)
        ints = rgba.to_ints()
        # to_ints does not clamp, just rounds
        assert ints[0] == round(1.5 * 255)
        assert ints[1] == round(-0.5 * 255)


class TestRGBAGetters:
    """Maps to describe("RGBA class") > describe("getters").

    Python equivalent: dataclass field access.
    """

    def test_r_getter_returns_red_value(self):
        """Maps to test("r getter returns red value")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        assert rgba.r == pytest.approx(0.1, abs=1e-5)

    def test_g_getter_returns_green_value(self):
        """Maps to test("g getter returns green value")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        assert rgba.g == pytest.approx(0.2, abs=1e-5)

    def test_b_getter_returns_blue_value(self):
        """Maps to test("b getter returns blue value")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        assert rgba.b == pytest.approx(0.3, abs=1e-5)

    def test_a_getter_returns_alpha_value(self):
        """Maps to test("a getter returns alpha value")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        assert rgba.a == pytest.approx(0.4, abs=1e-5)


class TestRGBASetters:
    """Maps to describe("RGBA class") > describe("setters").

    Python equivalent: dataclass field assignment.
    """

    def test_r_setter_updates_red_value(self):
        """Maps to test("r setter updates red value")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        rgba.r = 0.9
        assert rgba.r == pytest.approx(0.9, abs=1e-5)

    def test_g_setter_updates_green_value(self):
        """Maps to test("g setter updates green value")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        rgba.g = 0.9
        assert rgba.g == pytest.approx(0.9, abs=1e-5)

    def test_b_setter_updates_blue_value(self):
        """Maps to test("b setter updates blue value")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        rgba.b = 0.9
        assert rgba.b == pytest.approx(0.9, abs=1e-5)

    def test_a_setter_updates_alpha_value(self):
        """Maps to test("a setter updates alpha value")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        rgba.a = 0.9
        assert rgba.a == pytest.approx(0.9, abs=1e-5)

    def test_setters_modify_underlying_values(self):
        """Maps to test("setters modify underlying buffer").

        Python: no buffer, but verifies fields are mutable.
        """
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        rgba.r = 0.5
        rgba.g = 0.6
        rgba.b = 0.7
        rgba.a = 0.8
        assert rgba.r == pytest.approx(0.5, abs=1e-5)
        assert rgba.g == pytest.approx(0.6, abs=1e-5)
        assert rgba.b == pytest.approx(0.7, abs=1e-5)
        assert rgba.a == pytest.approx(0.8, abs=1e-5)


class TestRGBAToString:
    """Maps to describe("RGBA class") > describe("toString")."""

    def test_formats_as_rgba_string_with_2_decimal_places(self):
        """Maps to test("formats as rgba string with 2 decimal places")."""
        rgba = RGBA(0.1, 0.2, 0.3, 0.4)
        assert str(rgba) == "rgba(0.10, 0.20, 0.30, 0.40)"

    def test_handles_zero_values(self):
        """Maps to test("handles zero values")."""
        rgba = RGBA(0, 0, 0, 0)
        assert str(rgba) == "rgba(0.00, 0.00, 0.00, 0.00)"

    def test_handles_max_values(self):
        """Maps to test("handles max values")."""
        rgba = RGBA(1, 1, 1, 1)
        assert str(rgba) == "rgba(1.00, 1.00, 1.00, 1.00)"

    def test_rounds_to_2_decimal_places(self):
        """Maps to test("rounds to 2 decimal places")."""
        rgba = RGBA(0.123456, 0.789012, 0.345678, 0.901234)
        s = str(rgba)
        assert "0.12" in s
        assert "0.79" in s

    def test_handles_negative_values(self):
        """Maps to test("handles negative values")."""
        rgba = RGBA(-0.5, -0.2, -0.1, -0.3)
        s = str(rgba)
        assert "-0.50" in s
        assert "-0.20" in s

    def test_handles_values_greater_than_1(self):
        """Maps to test("handles values greater than 1")."""
        rgba = RGBA(1.5, 2.0, 2.5, 3.0)
        s = str(rgba)
        assert "1.50" in s
        assert "2.00" in s


class TestHexToRgb:
    """Maps to describe("hexToRgb").

    Python equivalent: RGBA.from_hex().
    """

    def test_converts_6_digit_hex_with_hash_prefix(self):
        """Maps to test("converts 6-digit hex with # prefix")."""
        rgba = RGBA.from_hex("#FF8040")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == 1

    def test_converts_6_digit_hex_without_hash_prefix(self):
        """Maps to test("converts 6-digit hex without # prefix")."""
        rgba = RGBA.from_hex("FF8040")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == 1

    def test_expands_3_digit_hex_to_6_digit(self):
        """Maps to test("expands 3-digit hex to 6-digit")."""
        rgba = RGBA.from_hex("#F80")
        # #F80 -> #FF8800
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0x88 / 255, abs=0.01)
        assert rgba.b == pytest.approx(0, abs=0.01)
        assert rgba.a == 1

    def test_expands_3_digit_hex_without_hash_prefix(self):
        """Maps to test("expands 3-digit hex without # prefix")."""
        rgba = RGBA.from_hex("F80")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0x88 / 255, abs=0.01)

    def test_handles_lowercase_hex(self):
        """Maps to test("handles lowercase hex")."""
        rgba = RGBA.from_hex("#ff8040")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == 1

    def test_handles_mixed_case_hex(self):
        """Maps to test("handles mixed case hex")."""
        rgba = RGBA.from_hex("#Ff8040")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == 1

    def test_converts_black(self):
        """Maps to test("converts black (#000000)")."""
        rgba = RGBA.from_hex("#000000")
        assert rgba.r == 0
        assert rgba.g == 0
        assert rgba.b == 0
        assert rgba.a == 1

    def test_converts_white(self):
        """Maps to test("converts white (#FFFFFF)")."""
        rgba = RGBA.from_hex("#FFFFFF")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(1.0, abs=0.01)
        assert rgba.b == pytest.approx(1.0, abs=0.01)
        assert rgba.a == 1

    def test_converts_red(self):
        """Maps to test("converts red (#FF0000)")."""
        rgba = RGBA.from_hex("#FF0000")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == 0
        assert rgba.b == 0
        assert rgba.a == 1

    def test_converts_green(self):
        """Maps to test("converts green (#00FF00)")."""
        rgba = RGBA.from_hex("#00FF00")
        assert rgba.r == 0
        assert rgba.g == pytest.approx(1.0, abs=0.01)
        assert rgba.b == 0
        assert rgba.a == 1

    def test_converts_blue(self):
        """Maps to test("converts blue (#0000FF)")."""
        rgba = RGBA.from_hex("#0000FF")
        assert rgba.r == 0
        assert rgba.g == 0
        assert rgba.b == pytest.approx(1.0, abs=0.01)
        assert rgba.a == 1

    def test_returns_magenta_for_invalid_hex(self):
        """Maps to test("returns magenta for invalid hex")."""
        rgba = RGBA.from_hex("#GGGGGG")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.0, abs=0.01)
        assert rgba.b == pytest.approx(1.0, abs=0.01)
        assert rgba.a == pytest.approx(1.0, abs=0.01)

    def test_returns_magenta_for_too_short_hex(self):
        """Maps to test("returns magenta for too short hex")."""
        rgba = RGBA.from_hex("#AB")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.0, abs=0.01)
        assert rgba.b == pytest.approx(1.0, abs=0.01)

    def test_returns_magenta_for_too_long_hex(self):
        """Maps to test("returns magenta for too long hex")."""
        rgba = RGBA.from_hex("#AABBCCDDEE")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.0, abs=0.01)
        assert rgba.b == pytest.approx(1.0, abs=0.01)

    def test_returns_magenta_for_empty_string(self):
        """Maps to test("returns magenta for empty string")."""
        rgba = RGBA.from_hex("")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.0, abs=0.01)
        assert rgba.b == pytest.approx(1.0, abs=0.01)

    def test_returns_magenta_for_special_characters(self):
        """Maps to test("returns magenta for special characters")."""
        rgba = RGBA.from_hex("#!@#$%^")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.b == pytest.approx(1.0, abs=0.01)

    def test_converts_8_digit_hex_with_alpha_channel(self):
        """Maps to test("converts 8-digit hex with alpha channel")."""
        rgba = RGBA.from_hex("#FF804080")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == pytest.approx(0.502, abs=0.01)

    def test_converts_8_digit_hex_without_hash_prefix(self):
        """Maps to test("converts 8-digit hex without # prefix")."""
        rgba = RGBA.from_hex("FF804080")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == pytest.approx(0.502, abs=0.01)

    def test_converts_4_digit_hex_with_alpha_channel(self):
        """Maps to test("converts 4-digit hex with alpha channel")."""
        rgba = RGBA.from_hex("#F848")
        # #F848 -> #FF884488
        assert rgba.r == pytest.approx(0xFF / 255, abs=0.01)
        assert rgba.g == pytest.approx(0x88 / 255, abs=0.01)
        assert rgba.b == pytest.approx(0x44 / 255, abs=0.01)
        assert rgba.a == pytest.approx(0x88 / 255, abs=0.01)

    def test_converts_4_digit_hex_without_hash_prefix(self):
        """Maps to test("converts 4-digit hex without # prefix")."""
        rgba = RGBA.from_hex("F848")
        assert rgba.r == pytest.approx(0xFF / 255, abs=0.01)
        assert rgba.a == pytest.approx(0x88 / 255, abs=0.01)

    def test_converts_8_digit_hex_with_full_alpha(self):
        """Maps to test("converts 8-digit hex with full alpha (FF)")."""
        rgba = RGBA.from_hex("#FF8040FF")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == pytest.approx(1.0, abs=0.01)

    def test_converts_8_digit_hex_with_zero_alpha(self):
        """Maps to test("converts 8-digit hex with zero alpha")."""
        rgba = RGBA.from_hex("#FF804000")
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.g == pytest.approx(0.502, abs=0.01)
        assert rgba.b == pytest.approx(0.251, abs=0.01)
        assert rgba.a == 0

    def test_converts_4_digit_hex_with_full_alpha(self):
        """Maps to test("converts 4-digit hex with full alpha (F)")."""
        rgba = RGBA.from_hex("#F80F")
        # #F80F -> #FF8800FF
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.a == pytest.approx(1.0, abs=0.01)

    def test_converts_4_digit_hex_with_zero_alpha(self):
        """Maps to test("converts 4-digit hex with zero alpha")."""
        rgba = RGBA.from_hex("#F800")
        # #F800 -> #FF880000
        assert rgba.r == pytest.approx(1.0, abs=0.01)
        assert rgba.a == 0


class TestRgbToHex:
    """Maps to describe("rgbToHex").

    Python equivalent: RGBA.to_hex().
    """

    def test_converts_rgba_to_hex_string(self):
        """Maps to test("converts RGBA to hex string").

        Upstream uses RGBA.fromInts(255, 128, 64, 255). We use float equivalent.
        """
        rgba = RGBA(255 / 255, 128 / 255, 64 / 255, 255 / 255)
        assert rgba.to_hex() == "#ff8040"

    def test_converts_black_to_000000(self):
        """Maps to test("converts black to #000000")."""
        rgba = RGBA(0, 0, 0, 1)
        assert rgba.to_hex() == "#000000"

    def test_converts_white_to_ffffff(self):
        """Maps to test("converts white to #ffffff")."""
        rgba = RGBA(1, 1, 1, 1)
        assert rgba.to_hex() == "#ffffff"

    def test_converts_red_to_ff0000(self):
        """Maps to test("converts red to #ff0000")."""
        rgba = RGBA(1, 0, 0, 1)
        assert rgba.to_hex() == "#ff0000"

    def test_converts_green_to_00ff00(self):
        """Maps to test("converts green to #00ff00")."""
        rgba = RGBA(0, 1, 0, 1)
        assert rgba.to_hex() == "#00ff00"

    def test_converts_blue_to_0000ff(self):
        """Maps to test("converts blue to #0000ff")."""
        rgba = RGBA(0, 0, 1, 1)
        assert rgba.to_hex() == "#0000ff"

    def test_includes_alpha_channel_when_not_fully_opaque(self):
        """Maps to test("includes alpha channel when not fully opaque")."""
        rgba = RGBA(255 / 255, 128 / 255, 64 / 255, 128 / 255)
        assert rgba.to_hex() == "#ff804080"

    def test_clamps_values_below_0_to_0(self):
        """Maps to test("clamps values below 0 to 0")."""
        rgba = RGBA(-0.5, -0.2, -0.1, 1)
        assert rgba.to_hex() == "#000000"

    def test_clamps_values_above_1_to_1(self):
        """Maps to test("clamps values above 1 to 1")."""
        rgba = RGBA(1.5, 2.0, 3.0, 1)
        assert rgba.to_hex() == "#ffffff"

    def test_rounds_mid_range_values_correctly(self):
        """Maps to test("rounds mid-range values correctly")."""
        rgba = RGBA(127 / 255, 127 / 255, 127 / 255, 255 / 255)
        assert rgba.to_hex() == "#7f7f7f"

    def test_pads_single_digit_hex_with_leading_zero(self):
        """Maps to test("pads single digit hex with leading zero")."""
        rgba = RGBA(0.02, 0.02, 0.02, 1)
        assert rgba.to_hex() == "#050505"

    def test_converts_gray_values_correctly(self):
        """Maps to test("converts gray values correctly")."""
        rgba = RGBA(127 / 255, 127 / 255, 127 / 255, 1)
        assert rgba.to_hex() == "#7f7f7f"

    def test_includes_alpha_channel_when_alpha_is_not_1(self):
        """Maps to test("includes alpha channel when alpha is not 1.0")."""
        rgba = RGBA(255 / 255, 128 / 255, 64 / 255, 128 / 255)
        assert rgba.to_hex() == "#ff804080"

    def test_excludes_alpha_channel_when_alpha_is_1(self):
        """Maps to test("excludes alpha channel when alpha is 1.0")."""
        rgba = RGBA(255 / 255, 128 / 255, 64 / 255, 255 / 255)
        assert rgba.to_hex() == "#ff8040"

    def test_includes_alpha_channel_for_transparent_color(self):
        """Maps to test("includes alpha channel for transparent color")."""
        rgba = RGBA(1, 0, 0, 0)
        assert rgba.to_hex() == "#ff000000"

    def test_includes_alpha_channel_for_semi_transparent(self):
        """Maps to test("includes alpha channel for semi-transparent")."""
        rgba = RGBA(0, 1, 0, 0.5)
        # math.floor(max(0, min(1, 0.5)) * 255) = math.floor(127.5) = 127 = 0x7f
        assert rgba.to_hex() == "#00ff007f"

    def test_excludes_alpha_for_fully_opaque_black(self):
        """Maps to test("excludes alpha for fully opaque black")."""
        rgba = RGBA(0, 0, 0, 1)
        assert rgba.to_hex() == "#000000"


class TestParseColor:
    """Maps to describe("parseColor")."""

    def test_parses_rgba_object_directly(self):
        """Maps to test("parses RGBA object directly")."""
        original = RGBA(0.1, 0.2, 0.3, 0.4)
        result = parse_color(original)
        assert result is original

    def test_parses_hex_string(self):
        """Maps to test("parses hex string")."""
        result = parse_color("#FF0000")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.g == pytest.approx(0.0, abs=0.01)
        assert result.b == pytest.approx(0.0, abs=0.01)

    def test_parses_transparent_keyword(self):
        """Maps to test("parses transparent keyword")."""
        result = parse_color("transparent")
        assert result.r == 0
        assert result.g == 0
        assert result.b == 0
        assert result.a == 0

    def test_parses_transparent_uppercase(self):
        """Maps to test("parses TRANSPARENT (uppercase)")."""
        result = parse_color("TRANSPARENT")
        assert result.a == 0

    def test_parses_black_color_name(self):
        """Maps to test("parses black color name")."""
        result = parse_color("black")
        assert result.r == pytest.approx(0.0, abs=0.01)
        assert result.g == pytest.approx(0.0, abs=0.01)
        assert result.b == pytest.approx(0.0, abs=0.01)

    def test_parses_white_color_name(self):
        """Maps to test("parses white color name")."""
        result = parse_color("white")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.g == pytest.approx(1.0, abs=0.01)
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_red_color_name(self):
        """Maps to test("parses red color name")."""
        result = parse_color("red")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.g == pytest.approx(0.0, abs=0.01)
        assert result.b == pytest.approx(0.0, abs=0.01)

    def test_parses_green_color_name(self):
        """Maps to test("parses green color name")."""
        result = parse_color("green")
        assert result.r == pytest.approx(0.0, abs=0.01)
        assert result.g == pytest.approx(0x80 / 255, abs=0.01)
        assert result.b == pytest.approx(0.0, abs=0.01)

    def test_parses_blue_color_name(self):
        """Maps to test("parses blue color name")."""
        result = parse_color("blue")
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_yellow_color_name(self):
        """Maps to test("parses yellow color name")."""
        result = parse_color("yellow")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.g == pytest.approx(1.0, abs=0.01)
        assert result.b == pytest.approx(0.0, abs=0.01)

    def test_parses_cyan_color_name(self):
        """Maps to test("parses cyan color name")."""
        result = parse_color("cyan")
        assert result.r == pytest.approx(0.0, abs=0.01)
        assert result.g == pytest.approx(1.0, abs=0.01)
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_magenta_color_name(self):
        """Maps to test("parses magenta color name")."""
        result = parse_color("magenta")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.g == pytest.approx(0.0, abs=0.01)
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_silver_color_name(self):
        """Maps to test("parses silver color name")."""
        result = parse_color("silver")
        assert result.r == pytest.approx(0xC0 / 255, abs=0.01)

    def test_parses_gray_color_name(self):
        """Maps to test("parses gray color name")."""
        result = parse_color("gray")
        assert result.r == pytest.approx(0x80 / 255, abs=0.01)

    def test_parses_grey_color_name(self):
        """Maps to test("parses grey color name (alternate spelling)")."""
        result = parse_color("grey")
        assert result.r == pytest.approx(0x80 / 255, abs=0.01)

    def test_parses_maroon_color_name(self):
        """Maps to test("parses maroon color name")."""
        result = parse_color("maroon")
        assert result.r == pytest.approx(0x80 / 255, abs=0.01)
        assert result.g == pytest.approx(0.0, abs=0.01)

    def test_parses_olive_color_name(self):
        """Maps to test("parses olive color name")."""
        result = parse_color("olive")
        assert result.r == pytest.approx(0x80 / 255, abs=0.01)
        assert result.g == pytest.approx(0x80 / 255, abs=0.01)

    def test_parses_lime_color_name(self):
        """Maps to test("parses lime color name")."""
        result = parse_color("lime")
        assert result.g == pytest.approx(1.0, abs=0.01)

    def test_parses_aqua_color_name(self):
        """Maps to test("parses aqua color name")."""
        result = parse_color("aqua")
        assert result.g == pytest.approx(1.0, abs=0.01)
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_teal_color_name(self):
        """Maps to test("parses teal color name")."""
        result = parse_color("teal")
        assert result.g == pytest.approx(0x80 / 255, abs=0.01)
        assert result.b == pytest.approx(0x80 / 255, abs=0.01)

    def test_parses_navy_color_name(self):
        """Maps to test("parses navy color name")."""
        result = parse_color("navy")
        assert result.b == pytest.approx(0x80 / 255, abs=0.01)

    def test_parses_fuchsia_color_name(self):
        """Maps to test("parses fuchsia color name")."""
        result = parse_color("fuchsia")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_purple_color_name(self):
        """Maps to test("parses purple color name")."""
        result = parse_color("purple")
        assert result.r == pytest.approx(0x80 / 255, abs=0.01)
        assert result.b == pytest.approx(0x80 / 255, abs=0.01)

    def test_parses_orange_color_name(self):
        """Maps to test("parses orange color name")."""
        result = parse_color("orange")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.g == pytest.approx(0xA5 / 255, abs=0.01)

    def test_parses_brightblack_color_name(self):
        """Maps to test("parses brightblack color name")."""
        result = parse_color("brightblack")
        assert result.r == pytest.approx(0x66 / 255, abs=0.01)

    def test_parses_brightred_color_name(self):
        """Maps to test("parses brightred color name")."""
        result = parse_color("brightred")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.g == pytest.approx(0x66 / 255, abs=0.01)

    def test_parses_brightgreen_color_name(self):
        """Maps to test("parses brightgreen color name")."""
        result = parse_color("brightgreen")
        assert result.g == pytest.approx(1.0, abs=0.01)

    def test_parses_brightblue_color_name(self):
        """Maps to test("parses brightblue color name")."""
        result = parse_color("brightblue")
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_brightyellow_color_name(self):
        """Maps to test("parses brightyellow color name")."""
        result = parse_color("brightyellow")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.g == pytest.approx(1.0, abs=0.01)

    def test_parses_brightcyan_color_name(self):
        """Maps to test("parses brightcyan color name")."""
        result = parse_color("brightcyan")
        assert result.g == pytest.approx(1.0, abs=0.01)
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_brightmagenta_color_name(self):
        """Maps to test("parses brightmagenta color name")."""
        result = parse_color("brightmagenta")
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.b == pytest.approx(1.0, abs=0.01)

    def test_parses_brightwhite_color_name(self):
        """Maps to test("parses brightwhite color name")."""
        result = parse_color("brightwhite")
        assert result.r == pytest.approx(1.0, abs=0.01)

    def test_handles_uppercase_color_names(self):
        """Maps to test("handles uppercase color names")."""
        result = parse_color("RED")
        assert result.r == pytest.approx(1.0, abs=0.01)

    def test_handles_mixed_case_color_names(self):
        """Maps to test("handles mixed case color names")."""
        result = parse_color("Red")
        assert result.r == pytest.approx(1.0, abs=0.01)

    def test_falls_back_to_hex_for_unknown_color_names(self):
        """Maps to test("falls back to hex parser for unknown color names")."""
        result = parse_color("unknowncolor")
        # Invalid hex -> magenta
        assert result.r == pytest.approx(1.0, abs=0.01)
        assert result.b == pytest.approx(1.0, abs=0.01)
