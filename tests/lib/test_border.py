"""Port of upstream border.test.ts.

Upstream: packages/core/src/lib/border.test.ts
Tests ported: 7/7 (0 skipped)
"""

import warnings

from opentui.structs import is_valid_border_style, parse_border_style


class TestIsValidBorderStyle:
    """Maps to describe("isValidBorderStyle")."""

    def test_returns_true_for_valid_border_styles(self):
        """Maps to test("returns true for valid border styles")."""
        assert is_valid_border_style("single") is True
        assert is_valid_border_style("double") is True
        assert is_valid_border_style("rounded") is True
        assert is_valid_border_style("heavy") is True

    def test_returns_false_for_invalid_border_styles(self):
        """Maps to test("returns false for invalid border styles")."""
        assert is_valid_border_style("invalid") is False
        assert is_valid_border_style("") is False
        assert is_valid_border_style(None) is False
        assert is_valid_border_style(42) is False
        assert is_valid_border_style(True) is False


class TestParseBorderStyle:
    """Maps to describe("parseBorderStyle")."""

    def test_returns_valid_border_styles_unchanged(self):
        """Maps to test("returns valid border styles unchanged")."""
        assert parse_border_style("single") == "single"
        assert parse_border_style("double") == "double"
        assert parse_border_style("rounded") == "rounded"
        assert parse_border_style("heavy") == "heavy"

    def test_falls_back_to_single_for_invalid_string_values(self):
        """Maps to test("falls back to 'single' for invalid string values")."""
        assert parse_border_style("invalid") == "single"
        assert parse_border_style("") == "single"

    def test_falls_back_to_custom_fallback_for_invalid_values(self):
        """Maps to test("falls back to custom fallback for invalid values")."""
        assert parse_border_style("invalid", "double") == "double"
        assert parse_border_style("", "heavy") == "heavy"

    def test_falls_back_silently_for_none_without_warning(self):
        """Maps to test("falls back silently for undefined/null without warning")."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_border_style(None)
            assert result == "single"
            assert len(w) == 0

    def test_logs_warning_for_invalid_non_none_values(self):
        """Maps to test("logs warning for invalid non-null/undefined values")."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            parse_border_style("bogus")
            assert len(w) == 1
            assert "Invalid borderStyle" in str(w[0].message)


class TestParseBorderStyleRegression:
    """Maps to describe("parseBorderStyle") > describe("regression: does not crash...")."""

    def test_handles_invalid_values(self):
        """Maps to test("handles invalid values")."""
        # Should not crash for any of these
        parse_border_style(42)
        parse_border_style(True)
        parse_border_style([])
        parse_border_style({})
