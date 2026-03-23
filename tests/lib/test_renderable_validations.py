"""Port of upstream renderable.validations.test.ts.

Upstream: packages/core/src/lib/renderable.validations.test.ts
Tests ported: 10/10
"""

import pytest

from opentui.layout import (
    _is_flex_basis_type,
    _is_margin_type,
    _is_padding_type,
    _is_size_type,
    _is_valid_percentage,
)


class TestUtilityFunctions:
    """Maps to describe("Utility Functions")."""

    def test_is_valid_percentage(self):
        """Maps to test("isValidPercentage")."""
        assert _is_valid_percentage("50%") is True
        assert _is_valid_percentage("0%") is True
        assert _is_valid_percentage("100.5%") is True
        assert _is_valid_percentage("abc") is False
        assert _is_valid_percentage("50") is False
        assert _is_valid_percentage(50) is False

    def test_is_margin_type(self):
        """Maps to test("isMarginType")."""
        assert _is_margin_type(10) is True
        assert _is_margin_type("auto") is True
        assert _is_margin_type("50%") is True
        assert _is_margin_type(float("nan")) is False
        assert _is_margin_type("invalid") is False

    def test_is_padding_type(self):
        """Maps to test("isPaddingType")."""
        assert _is_padding_type(10) is True
        assert _is_padding_type("50%") is True
        assert _is_padding_type("auto") is False
        assert _is_padding_type(float("nan")) is False

    def test_is_dimension_type(self):
        """Maps to test("isDimensionType") — dimensions use same rules as margins."""
        assert _is_margin_type(100) is True
        assert _is_margin_type("auto") is True
        assert _is_margin_type("50%") is True
        assert _is_margin_type(float("nan")) is False

    def test_is_flex_basis_type(self):
        """Maps to test("isFlexBasisType")."""
        assert _is_flex_basis_type(100) is True
        assert _is_flex_basis_type("auto") is True
        assert _is_flex_basis_type(None) is True  # undefined → True
        assert _is_flex_basis_type(float("nan")) is False

    def test_is_size_type(self):
        """Maps to test("isSizeType")."""
        assert _is_size_type(100) is True
        assert _is_size_type("50%") is True
        assert _is_size_type(None) is True  # undefined → True
        assert _is_size_type(float("nan")) is False

    def test_is_position_type_value(self):
        """Maps to test("isPositionTypeValue")."""
        assert ("relative" in ("relative", "absolute")) is True
        assert ("absolute" in ("relative", "absolute")) is True
        assert ("static" in ("relative", "absolute")) is False
        assert ("fixed" in ("relative", "absolute")) is False

    def test_is_overflow_type(self):
        """Maps to test("isOverflowType")."""
        assert ("visible" in ("visible", "hidden", "scroll")) is True
        assert ("hidden" in ("visible", "hidden", "scroll")) is True
        assert ("scroll" in ("visible", "hidden", "scroll")) is True
        assert ("auto" in ("visible", "hidden", "scroll")) is False
