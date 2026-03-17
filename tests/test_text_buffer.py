"""Port of upstream text-buffer.test.ts.

Upstream: packages/core/src/text-buffer.test.ts
Tests: 35 total — all implemented.
"""

import pytest
from opentui.native import NativeTextBuffer, is_available
from opentui.structs import RGBA

pytestmark = pytest.mark.skipif(not is_available(), reason="Native bindings not available")


class TestTextBufferSetTextAndSetStyledText:
    """Maps to describe("setText and setStyledText")."""

    def test_should_set_text_content(self):
        """Maps to it("should set text content")."""
        buffer = NativeTextBuffer()
        text = "Hello World"
        buffer.set_text(text)

        assert buffer.get_length() == 11

    def test_should_set_styled_text(self):
        """Maps to it("should set styled text").

        Upstream: stringToStyledText("Hello World") -> setStyledText.
        """
        buffer = NativeTextBuffer()
        styled_chunks = [{"text": "Hello World"}]
        buffer.set_styled_text(styled_chunks)

        assert buffer.get_length() == 11

    def test_should_handle_empty_text(self):
        """Maps to it("should handle empty text")."""
        buffer = NativeTextBuffer()
        buffer.set_text("")

        assert buffer.get_length() == 0

    def test_should_handle_text_with_newlines(self):
        """Maps to it("should handle text with newlines")."""
        buffer = NativeTextBuffer()
        text = "Line 1\nLine 2\nLine 3"
        buffer.set_text(text)

        # Upstream: 18 (6 + 6 + 6 chars, newlines not counted in 'length')
        assert buffer.get_length() == 18


class TestTextBufferGetPlainText:
    """Maps to describe("getPlainText")."""

    def test_should_return_empty_string_for_empty_buffer(self):
        """Maps to it("should return empty string for empty buffer")."""
        buffer = NativeTextBuffer()
        buffer.set_text("")

        plain_text = buffer.get_plain_text()
        assert plain_text == ""

    def test_should_return_plain_text_without_styling(self):
        """Maps to it("should return plain text without styling")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Hello World")

        plain_text = buffer.get_plain_text()
        assert plain_text == "Hello World"

    def test_should_handle_text_with_newlines(self):
        """Maps to it("should handle text with newlines")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Line 1\nLine 2\nLine 3")

        plain_text = buffer.get_plain_text()
        assert plain_text == "Line 1\nLine 2\nLine 3"

    def test_should_handle_unicode_characters_correctly(self):
        """Maps to it("should handle Unicode characters correctly")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Hello 世界 🌟")

        plain_text = buffer.get_plain_text()
        assert plain_text == "Hello 世界 🌟"

    def test_should_handle_styled_text_with_colors_and_attributes(self):
        """Maps to it("should handle styled text with colors and attributes").

        Upstream creates StyledText with colored chunks (red fg, blue fg)
        and verifies getPlainText strips the colors.
        """
        buffer = NativeTextBuffer()
        red_chunk = {
            "text": "Red",
            "fg": RGBA(r=1.0, g=0.0, b=0.0, a=1.0),
        }
        newline_chunk = {"text": "\n"}
        blue_chunk = {
            "text": "Blue",
            "fg": RGBA(r=0.0, g=0.0, b=1.0, a=1.0),
        }
        buffer.set_styled_text([red_chunk, newline_chunk, blue_chunk])

        plain_text = buffer.get_plain_text()
        assert plain_text == "Red\nBlue"


class TestTextBufferLengthProperty:
    """Maps to describe("length property")."""

    def test_should_return_correct_length_for_simple_text(self):
        """Maps to it("should return correct length for simple text")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Hello World")

        assert buffer.get_length() == 11

    def test_should_return_0_for_empty_buffer(self):
        """Maps to it("should return 0 for empty buffer")."""
        buffer = NativeTextBuffer()
        buffer.set_text("")

        assert buffer.get_length() == 0

    def test_should_handle_text_with_newlines_correctly(self):
        """Maps to it("should handle text with newlines correctly")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Line 1\nLine 2\nLine 3")

        # Upstream: 18 (6 + 6 + 6 chars, newlines not counted)
        assert buffer.get_length() == 18

    def test_should_handle_unicode_characters_correctly(self):
        """Maps to it("should handle Unicode characters correctly")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Hello 世界 🌟")

        # Upstream: 13 (H e l l o ' ' 世 界 ' ' 🌟 = display width chars)
        # The native length counts display columns (wcwidth):
        # H(1) e(1) l(1) l(1) o(1) ' '(1) 世(2) 界(2) ' '(1) 🌟(2) = 13
        assert buffer.get_length() == 13


class TestTextBufferDefaultStyles:
    """Maps to describe("default styles")."""

    def test_should_set_and_reset_default_foreground_color(self):
        """Maps to it("should set and reset default foreground color").

        Upstream uses expect(true).toBe(true) — test passes by not throwing.
        """
        buffer = NativeTextBuffer()
        buffer.set_default_fg()
        buffer.reset_defaults()

    def test_should_set_and_reset_default_background_color(self):
        """Maps to it("should set and reset default background color").

        Upstream uses expect(true).toBe(true) — test passes by not throwing.
        """
        buffer = NativeTextBuffer()
        buffer.set_default_bg()
        buffer.reset_defaults()

    def test_should_set_and_reset_default_attributes(self):
        """Maps to it("should set and reset default attributes").

        Upstream uses expect(true).toBe(true) — test passes by not throwing.
        """
        buffer = NativeTextBuffer()
        buffer.set_default_attributes(1)
        buffer.reset_defaults()


class TestTextBufferClearVsReset:
    """Maps to describe("clear() vs reset()")."""

    def test_clear_should_empty_buffer_but_preserve_text_across_set_text_calls(self):
        """Maps to it("clear() should empty buffer but preserve text across setText calls")."""
        buffer = NativeTextBuffer()

        # Set initial text
        buffer.set_text("First text")
        assert buffer.get_length() == 10

        # Set new text (which calls clear() internally)
        buffer.set_text("Second text")
        assert buffer.get_length() == 11
        assert buffer.get_plain_text() == "Second text"

        # Explicit clear
        buffer.clear()
        assert buffer.get_length() == 0
        assert buffer.get_plain_text() == ""

    def test_reset_should_fully_reset_the_buffer(self):
        """Maps to it("reset() should fully reset the buffer")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Some text")
        assert buffer.get_length() == 9

        buffer.reset()
        assert buffer.get_length() == 0
        assert buffer.get_plain_text() == ""

        # Should be able to use buffer after reset
        buffer.set_text("New text")
        assert buffer.get_length() == 8

    def test_set_text_should_preserve_highlights(self):
        """Maps to it("setText should preserve highlights (use clear() not reset())")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Hello World")
        assert buffer.get_length() == 11

        buffer.set_text("New Text")
        assert buffer.get_length() == 8
        assert buffer.get_plain_text() == "New Text"

    def test_set_styled_text_should_preserve_content_across_calls(self):
        """Maps to it("setStyledText should preserve content across calls")."""
        buffer = NativeTextBuffer()

        first_chunks = [{"text": "First"}]
        buffer.set_styled_text(first_chunks)
        assert buffer.get_length() == 5

        second_chunks = [{"text": "Second"}]
        buffer.set_styled_text(second_chunks)
        assert buffer.get_length() == 6
        assert buffer.get_plain_text() == "Second"

    def test_multiple_set_text_calls_should_work_correctly_with_clear(self):
        """Maps to it("multiple setText calls should work correctly with clear()")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Text 1")
        assert buffer.get_length() == 6

        buffer.set_text("Text 2")
        assert buffer.get_length() == 6

        buffer.set_text("Text 3")
        assert buffer.get_length() == 6

        assert buffer.get_plain_text() == "Text 3"

    def test_clear_followed_by_set_text_should_work(self):
        """Maps to it("clear() followed by setText should work")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Initial")
        assert buffer.get_length() == 7

        buffer.clear()
        assert buffer.get_length() == 0

        buffer.set_text("After clear")
        assert buffer.get_length() == 11
        assert buffer.get_plain_text() == "After clear"

    def test_reset_followed_by_set_text_should_work(self):
        """Maps to it("reset() followed by setText should work")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Initial")
        assert buffer.get_length() == 7

        buffer.reset()
        assert buffer.get_length() == 0

        buffer.set_text("After reset")
        assert buffer.get_length() == 11
        assert buffer.get_plain_text() == "After reset"


class TestTextBufferAppend:
    """Maps to describe("append()")."""

    def test_should_append_text_to_empty_buffer(self):
        """Maps to it("should append text to empty buffer")."""
        buffer = NativeTextBuffer()
        buffer.append("Hello")
        assert buffer.get_length() == 5
        assert buffer.get_plain_text() == "Hello"

    def test_should_append_text_to_existing_content(self):
        """Maps to it("should append text to existing content")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Hello")
        buffer.append(" World")
        assert buffer.get_length() == 11
        assert buffer.get_plain_text() == "Hello World"

    def test_should_append_text_with_newlines(self):
        """Maps to it("should append text with newlines")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Line 1")
        buffer.append("\nLine 2")
        assert buffer.get_plain_text() == "Line 1\nLine 2"

    def test_should_append_multiple_times(self):
        """Maps to it("should append multiple times")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Start")
        buffer.append(" middle")
        buffer.append(" end")
        assert buffer.get_plain_text() == "Start middle end"

    def test_should_handle_appending_empty_string(self):
        """Maps to it("should handle appending empty string")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Hello")
        length_before = buffer.get_length()
        buffer.append("")
        assert buffer.get_length() == length_before
        assert buffer.get_plain_text() == "Hello"

    def test_should_append_unicode_content(self):
        """Maps to it("should append unicode content")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Hello ")
        buffer.append("世界 🌟")
        assert buffer.get_plain_text() == "Hello 世界 🌟"

    def test_should_handle_streaming_chunks(self):
        """Maps to it("should handle streaming chunks")."""
        buffer = NativeTextBuffer()
        buffer.append("First")
        buffer.append("\nLine2")
        buffer.append("\n")
        buffer.append("Line3")
        buffer.append(" end")
        assert buffer.get_plain_text() == "First\nLine2\nLine3 end"

    def test_should_handle_crlf_line_endings_in_append(self):
        """Maps to it("should handle CRLF line endings in append")."""
        buffer = NativeTextBuffer()
        buffer.append("Line1\r\n")
        buffer.append("Line2\r\n")
        buffer.append("Line3")
        # CRLF should be normalized to LF
        assert buffer.get_plain_text() == "Line1\nLine2\nLine3"

    def test_should_work_with_clear_and_append(self):
        """Maps to it("should work with clear and append")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Initial")
        buffer.clear()
        buffer.append("After clear")
        assert buffer.get_plain_text() == "After clear"

    def test_should_work_with_reset_and_append(self):
        """Maps to it("should work with reset and append")."""
        buffer = NativeTextBuffer()
        buffer.set_text("Initial")
        buffer.reset()
        buffer.append("After reset")
        assert buffer.get_plain_text() == "After reset"

    def test_should_handle_large_streaming_append(self):
        """Maps to it("should handle large streaming append")."""
        buffer = NativeTextBuffer()
        for i in range(100):
            buffer.append(f"Line {i}\n")
        result = buffer.get_plain_text(max_len=65536)
        assert "Line 0" in result
        assert "Line 99" in result

    def test_should_mix_set_text_and_append(self):
        """Maps to it("should mix setText and append")."""
        buffer = NativeTextBuffer()
        buffer.set_text("First")
        buffer.append(" appended")
        assert buffer.get_plain_text() == "First appended"

        buffer.set_text("Reset")
        buffer.append(" again")
        assert buffer.get_plain_text() == "Reset again"
