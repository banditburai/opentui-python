"""Port of upstream renderable.validations.test.ts.

Upstream: packages/core/src/lib/renderable.validations.test.ts
Tests ported: 10/10
"""

import math

import pytest

from opentui.layout import (
    is_dimension_type,
    is_flex_basis_type,
    is_margin_type,
    is_overflow_type,
    is_padding_type,
    is_position_type,
    is_position_type_value,
    is_size_type,
    is_valid_percentage,
    validate_options,
)


class TestUtilityFunctions:
    """Maps to describe("Utility Functions")."""

    def test_validate_options(self):
        """Maps to test("validateOptions")."""
        # Valid options - should not raise
        validate_options("test", {"width": 100, "height": 100})

        # Negative width - should raise ValueError
        with pytest.raises(ValueError):
            validate_options("test", {"width": -100, "height": 100})

        # Negative height - should raise ValueError
        with pytest.raises(ValueError):
            validate_options("test", {"width": 100, "height": -100})

    def test_is_valid_percentage(self):
        """Maps to test("isValidPercentage")."""
        assert is_valid_percentage("50%") is True
        assert is_valid_percentage("0%") is True
        assert is_valid_percentage("100.5%") is True
        assert is_valid_percentage("abc") is False
        assert is_valid_percentage("50") is False
        assert is_valid_percentage(50) is False

    def test_is_margin_type(self):
        """Maps to test("isMarginType")."""
        assert is_margin_type(10) is True
        assert is_margin_type("auto") is True
        assert is_margin_type("50%") is True
        assert is_margin_type(float("nan")) is False
        assert is_margin_type("invalid") is False

    def test_is_padding_type(self):
        """Maps to test("isPaddingType")."""
        assert is_padding_type(10) is True
        assert is_padding_type("50%") is True
        assert is_padding_type("auto") is False
        assert is_padding_type(float("nan")) is False

    def test_is_position_type(self):
        """Maps to test("isPositionType")."""
        assert is_position_type(10) is True
        assert is_position_type("auto") is True
        assert is_position_type("50%") is True
        assert is_position_type(float("nan")) is False

    def test_is_dimension_type(self):
        """Maps to test("isDimensionType")."""
        assert is_dimension_type(100) is True
        assert is_dimension_type("auto") is True
        assert is_dimension_type("50%") is True
        assert is_dimension_type(float("nan")) is False

    def test_is_flex_basis_type(self):
        """Maps to test("isFlexBasisType")."""
        assert is_flex_basis_type(100) is True
        assert is_flex_basis_type("auto") is True
        assert is_flex_basis_type(None) is True  # undefined → True
        assert is_flex_basis_type(float("nan")) is False

    def test_is_size_type(self):
        """Maps to test("isSizeType")."""
        assert is_size_type(100) is True
        assert is_size_type("50%") is True
        assert is_size_type(None) is True  # undefined → True
        assert is_size_type(float("nan")) is False

    def test_is_position_type_value(self):
        """Maps to test("isPositionTypeValue")."""
        assert is_position_type_value("relative") is True
        assert is_position_type_value("absolute") is True
        assert is_position_type_value("static") is False
        assert is_position_type_value("fixed") is False

    def test_is_overflow_type(self):
        """Maps to test("isOverflowType")."""
        assert is_overflow_type("visible") is True
        assert is_overflow_type("hidden") is True
        assert is_overflow_type("scroll") is True
        assert is_overflow_type("auto") is False
