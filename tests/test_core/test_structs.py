"""Tests for struct definitions."""

from opentui.structs import RGBA


class TestRGBA:
    def test_from_hex_rgb(self):
        c = RGBA.from_hex("#FF0000")
        assert c.r == 1.0
        assert c.g == 0.0
        assert c.b == 0.0
        assert c.a == 1.0

    def test_from_hex_rgba(self):
        c = RGBA.from_hex("#FF000080")
        assert c.r == 1.0
        assert c.g == 0.0
        assert c.b == 0.0
        assert abs(c.a - 128 / 255) < 0.01

    def test_from_hex_no_hash(self):
        c = RGBA.from_hex("00FF00")
        assert c.g == 1.0

    def test_from_hex_invalid_length(self):
        import pytest
        with pytest.raises(ValueError):
            RGBA.from_hex("#FFF")

    def test_to_hex_rgb(self):
        c = RGBA(1.0, 0.0, 0.0, 1.0)
        assert c.to_hex() == "#ff0000"

    def test_to_hex_rgba(self):
        c = RGBA(1.0, 0.0, 0.0, 0.5)
        result = c.to_hex()
        assert result.startswith("#ff0000")
        assert len(result) == 9  # #rrggbbaa

    def test_roundtrip(self):
        original = RGBA(0.5, 0.25, 0.75, 1.0)
        hex_str = original.to_hex()
        restored = RGBA.from_hex(hex_str)
        assert abs(original.r - restored.r) < 0.01
        assert abs(original.g - restored.g) < 0.01
        assert abs(original.b - restored.b) < 0.01

    def test_to_hex_uses_round(self):
        """Verify round() is used (not int()) for correct rounding."""
        # 0.498 * 255 = 126.99 -> round gives 127, int gives 126
        c = RGBA(0.498, 0.0, 0.0, 1.0)
        hex_str = c.to_hex()
        r_val = int(hex_str[1:3], 16)
        assert r_val == 127
