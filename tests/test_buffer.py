"""Port of upstream buffer.test.ts + bounds-checking error-path tests.

Upstream: packages/core/src/buffer.test.ts
Tests ported: 15/15 + bounds-checking tests for NativeOptimizedBuffer and renderer.Buffer
"""

import pytest

from opentui.native import NativeOptimizedBuffer, encode_unicode, is_available

pytestmark = pytest.mark.skipif(not is_available(), reason="native bindings not available")

# Colors: [r, g, b, a] in 0.0-1.0 range
WHITE = [1.0, 1.0, 1.0, 1.0]
BLACK = [0.0, 0.0, 0.0, 1.0]


class TestOptimizedBuffer:
    """Maps to describe("OptimizedBuffer")."""

    class TestEncodeUnicode:
        """Maps to describe("encodeUnicode").

        Note: Our standalone encode_unicode() calls freeUnicode immediately after
        copying the data to Python tuples. The width and char_code values are
        faithfully copied, but grapheme-pool handles (high-bit chars for emoji)
        become invalid after freeing. Therefore these tests only validate the
        encoding metadata (widths, char codes, lengths). Drawing emoji is tested
        via draw_text which handles encoding internally.
        """

        def test_should_encode_simple_ascii_text(self):
            """Maps to it("should encode simple ASCII text")."""
            encoded = encode_unicode("Hello")
            assert encoded is not None
            assert len(encoded) == 5
            # Each element is (width, char_code)
            assert encoded[0] == (1, 72)  # 'H'
            assert encoded[1] == (1, 101)  # 'e'
            assert encoded[2] == (1, 108)  # 'l'
            assert encoded[3] == (1, 108)  # 'l'
            assert encoded[4] == (1, 111)  # 'o'

        def test_should_encode_emoji_with_correct_width(self):
            """Maps to it("should encode emoji with correct width")."""
            encoded = encode_unicode("\U0001f44b")  # wave emoji
            assert encoded is not None
            assert len(encoded) == 1
            assert encoded[0][0] == 2  # width is 2 for emoji
            # Should be a packed grapheme (has high bit set)
            assert encoded[0][1] > 0x80000000

        def test_should_encode_mixed_ascii_and_emoji(self):
            """Maps to it("should encode mixed ASCII and emoji")."""
            encoded = encode_unicode("Hi \U0001f44b World")
            assert encoded is not None
            # H, i, space, emoji, space, W, o, r, l, d = 10 elements
            assert len(encoded) == 10

            # Check ASCII chars
            assert encoded[0][0] == 1  # width
            assert encoded[0][1] == 72  # 'H'

            # Check emoji
            assert encoded[3][0] == 2  # width is 2
            assert encoded[3][1] > 0x80000000  # packed grapheme

        def test_should_handle_empty_string(self):
            """Maps to it("should handle empty string")."""
            encoded = encode_unicode("")
            assert encoded is not None
            assert len(encoded) == 0

        def test_should_encode_monkey_emoji_frames_and_draw_in_a_line(self):
            """Maps to it("should encode monkey emoji frames and draw in a line").

            Upstream encodes each frame then draws char-by-char via drawChar. Our
            standalone encode_unicode frees grapheme handles immediately, so emoji
            handles become invalid. We use draw_text for emoji frames instead, which
            keeps grapheme handles alive internally, and verify the same output.
            """
            frames = ["\U0001f648 ", "\U0001f648 ", "\U0001f649 ", "\U0001f64a "]
            fg = WHITE
            bg = BLACK

            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-monkey")
            buf.clear(0.0)

            # Validate encoding metadata for each frame
            for frame in frames:
                encoded = encode_unicode(frame)
                assert encoded is not None
                # Each frame is emoji(width=2) + space(width=1) = 2 entries
                assert len(encoded) == 2
                assert encoded[0][0] == 2  # emoji width
                assert encoded[1][0] == 1  # space width

            # Draw using draw_text (which handles encoding internally)
            x = 0
            for frame in frames:
                buf.draw_text(frame, x, 0, fg, bg)
                # Each frame takes 3 columns (2 for emoji + 1 for space)
                x += 3

            frame_text = buf.get_rendered_text(add_line_breaks=False)
            assert "\U0001f648" in frame_text
            assert "\U0001f649" in frame_text
            assert "\U0001f64a" in frame_text

    class TestDrawChar:
        """Maps to describe("drawChar")."""

        def test_should_draw_a_simple_ascii_character(self):
            """Maps to it("should draw a simple ASCII character")."""
            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-draw-char")
            fg = WHITE
            bg = BLACK

            buf.draw_char(72, 0, 0, fg, bg)  # 'H'

            # Verify via rendered text
            text = buf.get_rendered_text(add_line_breaks=False)
            assert "H" in text

        def test_should_draw_encoded_characters_from_encode_unicode(self):
            """Maps to it("should draw encoded characters from encodeUnicode").

            For ASCII text, encode_unicode char codes are simple codepoints that
            remain valid after freeUnicode (no grapheme pool handles).
            """
            encoded = encode_unicode("Hello")
            assert encoded is not None

            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-draw-encoded")
            fg = WHITE
            bg = BLACK

            # Draw each character - safe for ASCII since char codes are codepoints
            for i, (width, char_code) in enumerate(encoded):
                buf.draw_char(char_code, i, 0, fg, bg)

            # Verify buffer content
            frame_text = buf.get_rendered_text(add_line_breaks=False)
            assert "Hello" in frame_text

        def test_should_draw_emoji_using_encoded_char(self):
            """Maps to it("should draw emoji using encoded char").

            Our standalone encode_unicode frees grapheme handles immediately, so
            emoji handles (high-bit chars) become stale. We use draw_text to test
            emoji drawing, which keeps handles alive internally.
            """
            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-draw-emoji")
            fg = WHITE
            bg = BLACK

            buf.draw_text("\U0001f44b", 0, 0, fg, bg)

            frame_text = buf.get_rendered_text(add_line_breaks=False)
            assert "\U0001f44b" in frame_text

    class TestSnapshotTestsWithUnicodeEncoding:
        """Maps to describe("snapshot tests with unicode encoding")."""

        def test_should_render_ascii_text_correctly(self):
            """Maps to it("should render ASCII text correctly")."""
            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-ascii-snap")
            buf.clear(0.0)

            encoded = encode_unicode("Hello")
            assert encoded is not None

            fg = WHITE
            bg = BLACK

            x = 0
            for width, char_code in encoded:
                buf.draw_char(char_code, x, 0, fg, bg)
                x += width

            frame_text = buf.get_rendered_text(add_line_breaks=True)
            # First line should start with "Hello"
            lines = frame_text.split("\n")
            assert lines[0].startswith("Hello")

        def test_should_render_emoji_text_correctly(self):
            """Maps to it("should render emoji text correctly").

            Uses draw_text for emoji content since our standalone encode_unicode
            frees grapheme handles before draw_char can use them.
            """
            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-emoji-snap")
            buf.clear(0.0)

            fg = WHITE
            bg = BLACK

            buf.draw_text("Hi \U0001f44b \U0001f30d", 0, 0, fg, bg)

            frame_text = buf.get_rendered_text(add_line_breaks=True)
            lines = frame_text.split("\n")
            assert "Hi" in lines[0]
            assert "\U0001f44b" in lines[0]
            assert "\U0001f30d" in lines[0]

        def test_should_handle_multiline_text_with_unicode(self):
            """Maps to it("should handle multiline text with unicode")."""
            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-multiline")
            buf.clear(0.0)

            text_lines = ["Hi \u4e16\u754c", "\U0001f31f Star"]
            fg = WHITE
            bg = BLACK

            for y, line in enumerate(text_lines):
                buf.draw_text(line, 0, y, fg, bg)

            frame_text = buf.get_rendered_text(add_line_breaks=True)
            output_lines = frame_text.split("\n")
            # Line 0 should contain "Hi" and the CJK characters
            assert "Hi" in output_lines[0]
            assert "\u4e16" in output_lines[0]
            assert "\u754c" in output_lines[0]
            # Line 1 should contain the star and "Star"
            assert "\U0001f31f" in output_lines[1]
            assert "Star" in output_lines[1]

        def test_should_respect_character_widths_in_positioning(self):
            """Maps to it("should respect character widths in positioning").

            The upstream test places 'A' at x=0, emoji at x=1 (width 2), 'B' at x=3.
            We use draw_char for ASCII codepoints and draw_text for the emoji.
            """
            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-widths")
            fg = WHITE
            bg = BLACK

            # 'A' at x=0 via draw_char (ASCII codepoint)
            buf.draw_char(ord("A"), 0, 0, fg, bg)
            # emoji at x=1 via draw_text (handles encoding internally)
            buf.draw_text("\U0001f44b", 1, 0, fg, bg)
            # 'B' at x=3 via draw_char (ASCII codepoint)
            buf.draw_char(ord("B"), 3, 0, fg, bg)

            frame_text = buf.get_rendered_text(add_line_breaks=False)
            assert "A\U0001f44bB" in frame_text

    class TestDrawCharWithAlphaBlending:
        """Maps to describe("drawChar with alpha blending")."""

        def test_should_blend_semi_transparent_foreground(self):
            """Maps to it("should blend semi-transparent foreground")."""
            buf = NativeOptimizedBuffer(20, 5, buffer_id="test-alpha-fg")

            fg = [1.0, 0.0, 0.0, 0.5]  # semi-transparent red
            bg = BLACK

            buf.draw_char(65, 0, 0, fg, bg)  # 'A'

            # Verify the operation didn't crash and produced output
            text = buf.get_rendered_text(add_line_breaks=False)
            assert "A" in text

            # Upstream: expect(fgBuffer[0]).toBeLessThan(1.0)
            # The red channel should be blended down from 1.0 due to 0.5 alpha
            fg_color = buf.get_fg_color(0, 0)
            assert fg_color[0] < 1.0, f"expected blended fg red channel < 1.0, got {fg_color[0]}"

        def test_should_blend_semi_transparent_background(self):
            """Maps to it("should blend semi-transparent background")."""
            buf = NativeOptimizedBuffer(20, 5, respect_alpha=True, buffer_id="test-alpha-bg")
            buf.set_respect_alpha(True)

            fg = WHITE
            bg = [1.0, 0.0, 0.0, 0.5]  # semi-transparent red background

            buf.draw_char(65, 0, 0, fg, bg)  # 'A'

            # Verify the operation didn't crash and produced output
            text = buf.get_rendered_text(add_line_breaks=False)
            assert "A" in text

            # Upstream: expect(bgBuffer[3]).toBeLessThan(1.0)
            # The alpha channel should reflect the semi-transparent background
            bg_color = buf.get_bg_color(0, 0)
            assert bg_color[3] < 1.0, f"expected bg alpha channel < 1.0, got {bg_color[3]}"

    class TestGraphemePoolChurnAcrossDrawFrameBuffer:
        """Maps to describe("grapheme pool churn across drawFrameBuffer").

        The upstream test uses parent.drawFrameBuffer(0, 0, child) which composites
        child onto parent. Our C++ binding only has drawFrameBuffer(buffer) which is
        the self.drawFrame() variant. We adapt by drawing text 50 times and calling
        draw_frame each cycle to exercise the grapheme pool, verifying no crash.

        NOTE: The Python bindings do not expose drawFrameBuffer(x, y, child) —
        the two-buffer compositing variant. Only drawFrameBuffer(buffer) (i.e.
        self.drawFrame()) is available. This means we cannot fully replicate the
        upstream parent/child compositing pattern. The test below exercises the
        grapheme pool churn via single-buffer redraws instead.
        """

        def test_should_not_crash_with_wrong_generation_after_many_grapheme_alloc_cycles(self):
            """Maps to it("should not crash with WrongGeneration after many grapheme alloc cycles").

            The upstream test uses parent.drawFrameBuffer(0, 0, child) which composites
            child onto parent. Our C++ binding only exposes drawFrameBuffer(buffer)
            (the self.drawFrame() variant without child compositing). We verify the
            grapheme pool doesn't crash by drawing text 50 times with alternating
            content and reading the rendered text each cycle.
            """
            buf = NativeOptimizedBuffer(40, 5, buffer_id="churn-test")

            fg = WHITE
            bg = BLACK

            for cycle in range(50):
                buf.clear(0.0)

                if cycle % 2 == 0:
                    buf.draw_text(
                        "\u256d\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u256e",
                        0,
                        0,
                        fg,
                        bg,
                    )
                    buf.draw_text(
                        "\u2502 \u25c7 Select Files \u25ab src/ \u25aa file.ts   \u2502",
                        0,
                        1,
                        fg,
                        bg,
                    )
                    buf.draw_text(
                        "\u2502 \u2191\u2193 navigate  \u23ce select  esc close  \u2502",
                        0,
                        2,
                        fg,
                        bg,
                    )
                    buf.draw_text(
                        "\u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u256f",
                        0,
                        3,
                        fg,
                        bg,
                    )
                else:
                    buf.draw_text("  Your Name                              ", 0, 0, fg, bg)
                    buf.draw_text("  John Doe                               ", 0, 1, fg, bg)
                    buf.draw_text("                                         ", 0, 2, fg, bg)
                    buf.draw_text("  Select Files                           ", 0, 3, fg, bg)

                text = buf.get_rendered_text(add_line_breaks=True)
                assert len(text) > 0

    class TestBoundsChecking:
        """Verify _check_bounds raises IndexError for out-of-range cell access."""

        def _make_buf(self):
            return NativeOptimizedBuffer(10, 5, buffer_id="bounds-test")

        @pytest.mark.parametrize(
            "method", ["get_fg_color", "get_bg_color", "get_attributes", "get_char"]
        )
        def test_negative_x(self, method):
            buf = self._make_buf()
            with pytest.raises(IndexError, match="out of bounds"):
                getattr(buf, method)(-1, 0)

        @pytest.mark.parametrize(
            "method", ["get_fg_color", "get_bg_color", "get_attributes", "get_char"]
        )
        def test_negative_y(self, method):
            buf = self._make_buf()
            with pytest.raises(IndexError, match="out of bounds"):
                getattr(buf, method)(0, -1)

        @pytest.mark.parametrize(
            "method", ["get_fg_color", "get_bg_color", "get_attributes", "get_char"]
        )
        def test_x_at_width(self, method):
            buf = self._make_buf()
            with pytest.raises(IndexError, match="out of bounds"):
                getattr(buf, method)(10, 0)  # width is 10, so x=10 is OOB

        @pytest.mark.parametrize(
            "method", ["get_fg_color", "get_bg_color", "get_attributes", "get_char"]
        )
        def test_y_at_height(self, method):
            buf = self._make_buf()
            with pytest.raises(IndexError, match="out of bounds"):
                getattr(buf, method)(0, 5)  # height is 5, so y=5 is OOB

        @pytest.mark.parametrize(
            "method", ["get_fg_color", "get_bg_color", "get_attributes", "get_char"]
        )
        def test_valid_corner(self, method):
            """Last valid cell (width-1, height-1) should not raise."""
            buf = self._make_buf()
            getattr(buf, method)(9, 4)  # should not raise


class TestRendererBufferBoundsChecking:
    """Verify renderer.Buffer._check_bounds raises IndexError before any native call.

    Uses a mock native module — we only need width/height to test the guard.
    """

    @staticmethod
    def _make_buf(w=10, h=5):
        from opentui.renderer import Buffer

        class _FakeNative:
            def get_buffer_width(self, _ptr):
                return w

            def get_buffer_height(self, _ptr):
                return h

        return Buffer(ptr=None, native=_FakeNative())

    @pytest.mark.parametrize(
        "method", ["get_bg_color", "get_fg_color", "get_attributes", "get_char_code"]
    )
    def test_negative_x(self, method):
        buf = self._make_buf()
        with pytest.raises(IndexError, match="out of bounds"):
            getattr(buf, method)(-1, 0)

    @pytest.mark.parametrize(
        "method", ["get_bg_color", "get_fg_color", "get_attributes", "get_char_code"]
    )
    def test_negative_y(self, method):
        buf = self._make_buf()
        with pytest.raises(IndexError, match="out of bounds"):
            getattr(buf, method)(0, -1)

    @pytest.mark.parametrize(
        "method", ["get_bg_color", "get_fg_color", "get_attributes", "get_char_code"]
    )
    def test_x_at_width(self, method):
        buf = self._make_buf()
        with pytest.raises(IndexError, match="out of bounds"):
            getattr(buf, method)(10, 0)

    @pytest.mark.parametrize(
        "method", ["get_bg_color", "get_fg_color", "get_attributes", "get_char_code"]
    )
    def test_y_at_height(self, method):
        buf = self._make_buf()
        with pytest.raises(IndexError, match="out of bounds"):
            getattr(buf, method)(0, 5)
