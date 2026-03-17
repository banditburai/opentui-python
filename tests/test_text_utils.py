"""Tests for text measurement utilities.

Upstream: N/A (Python-specific)
"""

from opentui.text_utils import measure_text, wrap_text


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


class TestWrapText:
    def test_empty(self):
        assert wrap_text("", 80) == [""]

    def test_no_wrap_mode(self):
        assert wrap_text("hello world", 80, "none") == ["hello world"]

    def test_fits_within_width(self):
        assert wrap_text("hello world", 80, "word") == ["hello world"]

    def test_word_wrap_breaks(self):
        lines = wrap_text("hello world", 6, "word")
        assert lines == ["hello", "world"]

    def test_word_wrap_long_sentence(self):
        lines = wrap_text("the quick brown fox", 10, "word")
        assert lines == ["the quick", "brown fox"]

    def test_char_wrap(self):
        lines = wrap_text("abcdefghij", 4, "char")
        assert lines == ["abcd", "efgh", "ij"]

    def test_newlines_preserved(self):
        lines = wrap_text("line1\nline2", 80, "word")
        assert lines == ["line1", "line2"]

    def test_newlines_with_wrap(self):
        lines = wrap_text("hello world\nfoo bar", 6, "word")
        assert lines == ["hello", "world", "foo", "bar"]

    def test_zero_width(self):
        lines = wrap_text("hello world", 0, "word")
        assert lines == ["hello world"]  # No wrapping
