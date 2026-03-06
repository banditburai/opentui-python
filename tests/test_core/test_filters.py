"""Tests for filter implementations."""

import pytest

from opentui.filters import (
    BlurFilter,
    BrightnessFilter,
    ContrastFilter,
    Filter,
    FilterChain,
    GrayscaleFilter,
    InvertFilter,
    SepiaFilter,
)


class TestGrayscaleFilter:
    """Tests for GrayscaleFilter."""

    def test_rgba_grayscale(self):
        """Test grayscale conversion on RGBA data."""
        data = bytes([255, 0, 0, 255] * 10)  # Red pixels with alpha
        filter_ = GrayscaleFilter()
        result = filter_.apply(data, format="RGBA")

        # Red (255, 0, 0) should convert to ~76 (luminance)
        assert result[0] == 76
        assert result[4] == 76

    def test_rgb_grayscale(self):
        """Test grayscale conversion on RGB data."""
        data = bytes([255, 0, 0] * 10)  # Red pixels
        filter_ = GrayscaleFilter()
        result = filter_.apply(data, format="RGB")

        assert result[0] == 76

    def test_grayscale_preserves_alpha(self):
        """Test that grayscale preserves alpha channel."""
        data = bytes([255, 0, 0, 128] * 10)
        filter_ = GrayscaleFilter()
        result = filter_.apply(data, format="RGBA")

        assert result[3] == 128  # Alpha preserved
        assert result[7] == 128

    def test_grayscale_too_short(self):
        """Test that short data is returned as-is."""
        data = bytes([255, 0])
        filter_ = GrayscaleFilter()
        result = filter_.apply(data, format="RGBA")

        assert result == data


class TestBrightnessFilter:
    """Tests for BrightnessFilter."""

    def test_brighten(self):
        """Test brightening an image."""
        data = bytes([100, 100, 100, 255] * 10)
        filter_ = BrightnessFilter(factor=1.5)
        result = filter_.apply(data, format="RGBA")

        assert result[0] == 150  # 100 * 1.5

    def test_darken(self):
        """Test darkening an image."""
        data = bytes([100, 100, 100, 255] * 10)
        filter_ = BrightnessFilter(factor=0.5)
        result = filter_.apply(data, format="RGBA")

        assert result[0] == 50  # 100 * 0.5

    def test_brightness_clamp(self):
        """Test that brightness clamps at 255."""
        data = bytes([200, 200, 200, 255] * 10)
        filter_ = BrightnessFilter(factor=2.0)
        result = filter_.apply(data, format="RGBA")

        assert result[0] == 255  # Capped at 255


class TestContrastFilter:
    """Tests for ContrastFilter."""

    def test_increase_contrast(self):
        """Test increasing contrast."""
        data = bytes([100, 100, 100, 255] * 10)  # Mid-gray
        filter_ = ContrastFilter(factor=2.0)
        result = filter_.apply(data, format="RGBA")

        # Mid-gray (128) should stay at 128, 100 should move toward extremes
        assert result[0] < 100 or result[0] > 100

    def test_decrease_contrast(self):
        """Test decreasing contrast."""
        data = bytes([0, 255, 0, 255] * 10)  # Black and green
        filter_ = ContrastFilter(factor=0.5)
        result = filter_.apply(data, format="RGBA")

        # Values should move toward midpoint (128)
        assert result[0] > 0  # Black becomes gray
        assert result[4] < 255  # Green becomes gray


class TestSepiaFilter:
    """Tests for SepiaFilter."""

    def test_sepia_red(self):
        """Test sepia filter on red pixel."""
        data = bytes([255, 0, 0, 255])
        filter_ = SepiaFilter()
        result = filter_.apply(data, format="RGBA")

        # Red should become warm brownish
        # Sepia: R' = 0.393*R + 0.769*G + 0.189*B = 0.393*255 ≈ 100
        assert result[0] == 100  # Red becomes ~100
        assert result[1] == 0  # Green becomes 0
        assert result[2] == 0  # Blue becomes 0

    def test_sepia_preserves_alpha(self):
        """Test that sepia preserves alpha."""
        data = bytes([255, 0, 0, 128])
        filter_ = SepiaFilter()
        result = filter_.apply(data, format="RGBA")

        assert result[3] == 128


class TestInvertFilter:
    """Tests for InvertFilter."""

    def test_invert_black(self):
        """Test inverting black."""
        data = bytes([0, 0, 0, 255])
        filter_ = InvertFilter()
        result = filter_.apply(data, format="RGBA")

        assert result[0] == 255

    def test_invert_white(self):
        """Test inverting white."""
        data = bytes([255, 255, 255, 255])
        filter_ = InvertFilter()
        result = filter_.apply(data, format="RGBA")

        assert result[0] == 0

    def test_invert_preserves_alpha(self):
        """Test that invert preserves alpha."""
        data = bytes([0, 0, 0, 128])
        filter_ = InvertFilter()
        result = filter_.apply(data, format="RGBA")

        assert result[3] == 128


class TestBlurFilter:
    """Tests for BlurFilter."""

    def test_blur_small_radius(self):
        """Test blur with small radius."""
        data = bytes([255, 0, 0, 255] * 4)  # 2x2 image
        filter_ = BlurFilter(radius=1.0)
        result = filter_.apply(data, width=2, height=2, format="RGBA")

        # Should have some red from neighbors
        assert result[0] > 0

    def test_blur_zero_radius_returns_original(self):
        """Test that zero radius returns original data."""
        data = bytes([255, 0, 0, 255] * 4)
        filter_ = BlurFilter(radius=0)
        result = filter_.apply(data, width=2, height=2, format="RGBA")

        assert result == data

    def test_blur_invalid_dimensions_raises(self):
        """Test that invalid dimensions raise error."""
        data = bytes([255, 0, 0, 255] * 10)  # 10 bytes = 2.5 pixels
        filter_ = BlurFilter(radius=1.0)

        with pytest.raises(ValueError):
            filter_.apply(data, width=2, height=2, format="RGBA")


class TestFilterChain:
    """Tests for FilterChain."""

    def test_chain_multiple_filters(self):
        """Test chaining multiple filters."""
        data = bytes([200, 200, 200, 255] * 10)
        chain = FilterChain(
            [
                BrightnessFilter(factor=1.5),
                ContrastFilter(factor=1.2),
            ]
        )
        result = chain.apply(data, format="RGBA")

        # Should have been processed by both filters
        assert result != data

    def test_chain_add_method(self):
        """Test using add method for chaining."""
        data = bytes([200, 200, 200, 255] * 10)
        chain = FilterChain()
        chain.add(BrightnessFilter(factor=1.5))
        chain.add(ContrastFilter(factor=1.2))
        result = chain.apply(data, format="RGBA")

        assert result != data

    def test_chain_clear(self):
        """Test clearing filter chain."""
        chain = FilterChain(
            [
                BrightnessFilter(factor=1.5),
            ]
        )
        chain.clear()

        data = bytes([200, 200, 200, 255] * 10)
        result = chain.apply(data, format="RGBA")

        assert result == data  # No filters = unchanged


class TestFilterBase:
    """Tests for Filter base class."""

    def test_base_filter_returns_input(self):
        """Test that base Filter returns input unchanged."""
        data = bytes([1, 2, 3, 4])
        filter_ = Filter()
        result = filter_.apply(data)

        assert result == data
