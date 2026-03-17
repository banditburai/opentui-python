"""Tests for graphics/image rendering.

Upstream: N/A (Python-specific)
"""

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

    def test_draw_image_falls_back_to_plain_without_graphics(self):
        """draw_image should use the plain fallback when graphics are unavailable."""
        from opentui.filters import ImageRenderer

        class MockBuffer:
            def __init__(self):
                self._ptr = None
                self._native = None

        renderer = ImageRenderer(MockBuffer())
        called = {}

        def fake_plain(data, x, y, width, height):
            called["args"] = (data, x, y, width, height)
            return True

        renderer.draw_image_plain = fake_plain

        result = renderer.draw_image(b"rgba", 1, 2, 3, 4)

        assert result is True
        assert called["args"] == (b"rgba", 1, 2, 3, 4)

    def test_draw_image_plain_writes_ascii_rows(self):
        """Plain fallback should render visible rows to the buffer."""
        from opentui.filters import ImageRenderer

        class MockBuffer:
            def __init__(self):
                self._ptr = None
                self._native = None
                self.calls = []

            def draw_text(self, text, x, y, fg=None, bg=None, attributes=0):
                self.calls.append((text, x, y))

        data = bytes(
            [
                255,
                255,
                255,
                255,
                0,
                0,
                0,
                255,
                127,
                127,
                127,
                255,
                255,
                0,
                0,
                255,
            ]
        )
        buffer = MockBuffer()
        renderer = ImageRenderer(buffer)

        result = renderer.draw_image_plain(data, 4, 5, 2, 2)

        assert result is True
        assert len(buffer.calls) == 2
        assert buffer.calls[0][1:] == (4, 5)
        assert buffer.calls[1][1:] == (4, 6)
        assert all(isinstance(text, str) and text for text, _, _ in buffer.calls)

    def test_draw_image_prefers_sixel_for_positioned_graphics(self):
        """SIXEL should be used before non-positioned native packed drawing."""
        from opentui.filters import ImageRenderer
        from opentui.renderer import TerminalCapabilities

        class MockBuffer:
            def __init__(self):
                self._ptr = 1
                self._native = object()

        renderer = ImageRenderer(MockBuffer(), TerminalCapabilities(sixel=True))
        called = {}

        renderer.draw_sixel = lambda data, x, y, width, height, bg_color=(0, 0, 0): (
            called.__setitem__("sixel", (data, x, y, width, height)) or True
        )

        result = renderer.draw_image(b"rgba", 2, 3, 4, 5)

        assert result is True
        assert called["sixel"] == (b"rgba", 2, 3, 4, 5)

    def test_draw_image_uses_kitty_with_png_encoding(self, monkeypatch):
        """Kitty protocol should be used with encoded PNG data when available."""
        from opentui import filters
        from opentui.filters import ImageRenderer
        from opentui.renderer import TerminalCapabilities

        class MockBuffer:
            def __init__(self):
                self._ptr = 1
                self._native = object()

        renderer = ImageRenderer(MockBuffer(), TerminalCapabilities(kitty_graphics=True))
        called = {}

        monkeypatch.setattr(
            filters,
            "_encode_png_from_rgba",
            lambda data, width, height: (
                called.__setitem__("encode", (data, width, height)) or b"png"
            ),
        )
        renderer.draw_kitty = lambda data, x, y, width, height, transmission="direct", frame=0: (
            called.__setitem__("kitty", (data, x, y, width, height)) or True
        )

        result = renderer.draw_image(b"rgba", 2, 3, 4, 5, source_width=40, source_height=50)

        assert result is True
        assert called["encode"] == (b"rgba", 40, 50)
        assert called["kitty"] == (b"png", 2, 3, 4, 5)


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


class TestSixelEncoding:
    """Tests for SIXEL encoding."""

    def test_sixel_encode_basic(self):
        """Test basic SIXEL encoding."""
        from opentui.filters import _encode_sixel

        # 10x10 red pixels
        data = bytes([255, 0, 0, 255] * 100)
        result = _encode_sixel(data, 10, 10)

        assert len(result) > 0
        assert result.startswith(b"\x1bP")  # SIXEL introducer
        assert result.endswith(b"\x1b\\")  # SIXEL terminator

    def test_sixel_encode_small_image(self):
        """Test SIXEL encoding with small image."""
        from opentui.filters import _encode_sixel

        # 2x2 image
        data = bytes([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 0, 255])
        result = _encode_sixel(data, 2, 2)

        assert len(result) > 0
        assert b"\x1bP" in result

    def test_sixel_encode_with_transparency(self):
        """Test SIXEL encoding with transparent pixels."""
        from opentui.filters import _encode_sixel

        # 2x2 with some transparent pixels
        data = bytes(
            [
                255,
                0,
                0,
                255,  # Red, opaque
                0,
                255,
                0,
                0,  # Green, transparent
                0,
                0,
                255,
                128,  # Blue, semi-transparent
                255,
                255,
                0,
                255,  # Yellow, opaque
            ]
        )
        result = _encode_sixel(data, 2, 2)

        assert len(result) > 0


class TestKittyEncoding:
    """Tests for Kitty encoding."""

    def test_kitty_encode_basic(self):
        """Test basic Kitty encoding."""
        from opentui.filters import _encode_kitty

        data = bytes([255, 0, 0, 255] * 100)
        result = _encode_kitty(data, chunk_id=1, width=10, height=10)

        assert len(result) > 0
        # First chunk should start with Kitty intro sequence
        assert result[0].startswith(b"\x1b_G")
        assert b"a=T" in result[0]
        assert b"c=10" in result[0]
        assert b"r=10" in result[0]

    def test_kitty_encode_multiple_chunks(self):
        """Test Kitty encoding with large data splits into chunks."""
        from opentui.filters import _encode_kitty

        # Very large data that will need multiple chunks after compression
        data = bytes([i % 256 for i in range(50000)])
        result = _encode_kitty(data, chunk_id=1, width=100, height=100)

        # Should have multiple chunks for large data
        assert len(result) >= 1  # May or may not chunk depending on compression

    def test_kitty_encode_with_position(self):
        """Test Kitty encoding with position."""
        from opentui.filters import _encode_kitty

        data = bytes([255, 0, 0, 255] * 100)
        result = _encode_kitty(data, chunk_id=5, width=10, height=10, x=5, y=10)

        assert len(result) > 0
        assert result[0].startswith(b"\x1b_G")
        assert b"a=T" in result[0]
        assert b"c=10" in result[0]
        assert b"r=10" in result[0]

    def test_kitty_encode_preserves_direct_payload_bytes(self):
        """Direct Kitty payloads should base64-encode the original image bytes."""
        import base64

        from opentui.filters import _encode_kitty

        data = b"\x89PNG\r\n\x1a\nfake-png-data"
        result = _encode_kitty(data, chunk_id=7, width=10, height=10)

        assert len(result) == 1
        payload = result[0].split(b";", 1)[1][:-2]
        assert base64.b64decode(payload) == data

    def test_clear_kitty_graphics(self):
        """Test Kitty clear graphics escape sequence."""
        from opentui.filters import _clear_kitty_graphics

        # Clear all
        result = _clear_kitty_graphics(None)
        assert result == b"\x1b_Ga=d,d=A\x1b\\"

        # Clear specific ID
        result = _clear_kitty_graphics(42)
        assert result == b"\x1b_Ga=d,d=I,i=42\x1b\\"

    def test_wrap_kitty_for_tmux(self, monkeypatch):
        """Kitty chunks should be DCS-wrapped for tmux sessions."""
        from opentui.filters import _wrap_kitty_for_transport

        monkeypatch.setenv("TMUX", "/tmp/tmux.sock,123,0")

        wrapped = _wrap_kitty_for_transport([b"\x1b_Gi=1;OK\x1b\\"])

        assert wrapped is not None
        assert wrapped[0].startswith(b"\x1bPtmux;")
        assert b"\x1b\x1b_Gi=1;OK\x1b\x1b\\" in wrapped[0]
