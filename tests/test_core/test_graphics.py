"""Tests for graphics/image rendering."""

import pytest


class TestImageRenderer:
    """Tests for ImageRenderer class."""

    def test_image_renderer_accepts_capabilities(self):
        """Test that ImageRenderer accepts TerminalCapabilities."""
        from opentui.filters import ImageRenderer
        from opentui.renderer import Buffer, TerminalCapabilities

        class MockBuffer:
            def __init__(self):
                self._ptr = None
                self._native = None

        caps = TerminalCapabilities(sixel=True, kitty_graphics=True)
        renderer = ImageRenderer(MockBuffer(), caps)

        assert renderer._caps.sixel is True
        assert renderer._caps.kitty_graphics is True

    def test_image_renderer_defaults_capabilities(self):
        """Test that ImageRenderer defaults to empty capabilities."""
        from opentui.filters import ImageRenderer
        from opentui.renderer import Buffer

        class MockBuffer:
            def __init__(self):
                self._ptr = None
                self._native = None

        renderer = ImageRenderer(MockBuffer())

        assert renderer._caps.sixel is False
        assert renderer._caps.kitty_graphics is False

    def test_image_renderer_has_draw_methods(self):
        """Test that ImageRenderer has the draw methods."""
        from opentui.filters import ImageRenderer
        from opentui.renderer import TerminalCapabilities

        class MockBuffer:
            def __init__(self):
                self._ptr = None

        renderer = ImageRenderer(MockBuffer())

        assert hasattr(renderer, "draw_sixel")
        assert hasattr(renderer, "draw_kitty")
        assert hasattr(renderer, "draw_image")
        assert hasattr(renderer, "draw_grayscale")

    def test_image_renderer_checks_capabilities_for_draw(self):
        """Test that draw methods check capabilities."""
        from opentui.filters import ImageRenderer
        from opentui.renderer import TerminalCapabilities

        class MockBuffer:
            def __init__(self):
                self._ptr = None

        # No capabilities - should return False
        renderer = ImageRenderer(MockBuffer())

        result = renderer.draw_sixel(b"data", 0, 0, 10, 10)
        assert result is False

        result = renderer.draw_kitty(b"data", 0, 0, 10, 10)
        assert result is False


class TestImageConversion:
    """Tests for image data conversion utilities."""

    def test_convert_to_packed_basic(self):
        """Test basic RGBA to packed conversion."""
        from opentui.filters import _convert_to_packed

        # Simple 2x2 red image
        data = bytes([255, 0, 0, 255] * 4)  # 4 pixels, RGBA

        packed, pitch = _convert_to_packed(data, 2, 2)

        assert pitch == 8  # 2 * 4 bytes per pixel
        assert len(packed) == 16  # 2 * 2 * 4 bytes

    def test_convert_to_grayscale_basic(self):
        """Test RGBA to grayscale conversion."""
        from opentui.filters import _convert_to_grayscale

        # Red, Green, Blue, White pixels
        data = bytes(
            [
                255,
                0,
                0,
                255,  # Red
                0,
                255,
                0,
                255,  # Green
                0,
                0,
                255,
                255,  # Blue
                255,
                255,
                255,
                255,  # White
            ]
        )

        gray = _convert_to_grayscale(data, 2, 2)

        assert len(gray) == 8  # 4 pixels * 2 bytes (16-bit grayscale)


class TestClipboardHandler:
    """Tests for clipboard paste handling."""

    def test_clipboard_handler_detects_png(self):
        """Test that ClipboardHandler detects PNG data."""
        from opentui.filters import ClipboardHandler
        from opentui.renderer import TerminalCapabilities

        handler = ClipboardHandler(TerminalCapabilities())

        # PNG magic bytes (8 bytes)
        png_data = b"\x89PNG\r\n\x1a\n" + bytes(100)

        result = handler.is_image_data(png_data)
        assert result is True

    def test_clipboard_handler_detects_jpeg(self):
        """Test that ClipboardHandler detects JPEG data."""
        from opentui.filters import ClipboardHandler
        from opentui.renderer import TerminalCapabilities

        handler = ClipboardHandler(TerminalCapabilities())

        # JPEG magic bytes
        jpeg_data = b"\xff\xd8\xff\xe0" + bytes(100)

        result = handler.is_image_data(jpeg_data)
        assert result is True

    def test_clipboard_handler_rejects_text(self):
        """Test that ClipboardHandler rejects text data."""
        from opentui.filters import ClipboardHandler
        from opentui.renderer import TerminalCapabilities

        handler = ClipboardHandler(TerminalCapabilities())

        text_data = b"Hello, World!"

        result = handler.is_image_data(text_data)
        assert result is False
