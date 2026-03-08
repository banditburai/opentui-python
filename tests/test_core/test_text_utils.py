"""Tests for text measurement utilities."""

from opentui.text_utils import measure_text


class TestMeasureText:
    def test_empty(self):
        w, h = measure_text("", max_width=80)
        assert w == 0
        assert h == 1

    def test_no_wrap(self):
        w, h = measure_text("hello world", max_width=80, wrap="none")
        assert w == 11
        assert h == 1

    def test_word_wrap_fits(self):
        w, h = measure_text("hello world", max_width=80, wrap="word")
        assert w == 11
        assert h == 1

    def test_word_wrap_breaks(self):
        w, h = measure_text("hello world", max_width=6, wrap="word")
        assert h == 2  # "hello" + "world" on separate lines

    def test_char_wrap_fits(self):
        w, h = measure_text("hello", max_width=10, wrap="char")
        assert w == 5
        assert h == 1

    def test_char_wrap_breaks(self):
        w, h = measure_text("abcdefghij", max_width=4, wrap="char")
        assert w == 4
        assert h >= 3  # 10 chars at width 4

    def test_multiline_input(self):
        w, h = measure_text("line1\nline2", max_width=80, wrap="word")
        assert h >= 2

    def test_zero_max_width_word(self):
        w, h = measure_text("hello world", max_width=0, wrap="word")
        assert w == 11  # No wrapping when max_width=0
