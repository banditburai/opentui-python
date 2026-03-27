"""Tests for Text component cross-renderable selection interface."""

import pytest

from opentui.components.text import Text


def _make_text(content: str, width: int = 40, wrap: str = "word") -> Text:
    """Create a Text with layout dimensions set for testing."""
    t = Text(content, wrap_mode=wrap)
    t._layout_width = width
    t._padding_left = 0
    t._padding_right = 0
    t._padding_top = 0
    t._padding_bottom = 0
    return t


class TestCoordToOffset:
    """Tests for _coord_to_offset — visual (col, row) → character offset."""

    def test_simple_no_wrap(self):
        t = _make_text("hello", wrap="none")
        assert t._coord_to_offset(0, 0) == 0
        assert t._coord_to_offset(4, 0) == 4

    def test_past_end_clamps(self):
        t = _make_text("hello", width=20)
        assert t._coord_to_offset(20, 0) == 5

    def test_negative_col_gives_zero(self):
        t = _make_text("hello")
        assert t._coord_to_offset(-1, 0) == 0

    def test_row_clamp_to_last(self):
        t = _make_text("hello", width=20)
        # Only 1 row; row 5 clamps to row 0
        assert t._coord_to_offset(0, 5) == 0

    def test_empty_content(self):
        t = _make_text("")
        assert t._coord_to_offset(5, 3) == 0

    def test_word_wrap_consumed_space(self):
        # "hello world foo" wraps to ["hello world", "foo"] at width 11
        t = _make_text("hello world foo", width=11)
        # Row 0: "hello world" → offsets 0-10
        assert t._coord_to_offset(0, 0) == 0
        assert t._coord_to_offset(5, 0) == 5  # space between hello/world
        # Row 1: "foo" → offsets 12-14 (space at 11 consumed)
        assert t._coord_to_offset(0, 1) == 12
        assert t._coord_to_offset(2, 1) == 14

    def test_newline_separator(self):
        t = _make_text("abc\ndef", width=20)
        assert t._coord_to_offset(0, 0) == 0
        assert t._coord_to_offset(2, 0) == 2  # 'c'
        assert t._coord_to_offset(0, 1) == 4  # 'd' (skips \n at 3)
        assert t._coord_to_offset(2, 1) == 6  # 'f'

    def test_newline_and_wrap_combined(self):
        # "hello world\nfoo bar" at width 5
        # wrap_text splits on \n first → ["hello world", "foo bar"]
        # Then wraps each: "hello world" → ["hello", "world"], "foo bar" → ["foo", "bar"]
        # Result: ["hello", "world", "foo", "bar"]
        t = _make_text("hello world\nfoo bar", width=5)
        assert t._coord_to_offset(0, 0) == 0  # 'h'
        assert t._coord_to_offset(0, 1) == 6  # 'w' (space at 5 consumed)
        assert t._coord_to_offset(0, 2) == 12  # 'f' (newline at 11 consumed)
        assert t._coord_to_offset(0, 3) == 16  # 'b' (space at 15 consumed)

    def test_char_wrap_no_space_consumed(self):
        t = _make_text("abcdefgh", width=3, wrap="char")
        # Wraps to ["abc", "def", "gh"]
        assert t._coord_to_offset(0, 0) == 0
        assert t._coord_to_offset(0, 1) == 3  # no separator consumed
        assert t._coord_to_offset(0, 2) == 6

    def test_cjk_wide_chars(self):
        # 你(2-wide) 好(2-wide) a(1-wide) → display cols: 你(0-1) 好(2-3) a(4)
        t = _make_text("你好a", width=20, wrap="none")
        assert t._coord_to_offset(0, 0) == 0  # '你'
        assert t._coord_to_offset(2, 0) == 1  # '好'
        assert t._coord_to_offset(4, 0) == 2  # 'a'

    def test_cjk_mid_char_click(self):
        # Clicking at display col 1 (middle of '你') should still map to char 0
        t = _make_text("你好a", width=20, wrap="none")
        assert t._coord_to_offset(1, 0) == 1  # past '你' width, lands on '好'


class TestSelectionInterface:
    """Tests for should_start_selection, has_selection, get_selected_text, clear_selection."""

    def test_selectable_default_true(self):
        t = Text("hello")
        assert t._selectable is True
        assert t.should_start_selection(0, 0) is True

    def test_selectable_false(self):
        t = Text("hello", selectable=False)
        assert t.should_start_selection(0, 0) is False

    def test_no_selection_by_default(self):
        t = Text("hello")
        assert t.has_selection() is False
        assert t.get_selected_text() == ""

    def test_manual_selection(self):
        t = _make_text("hello world")
        t._sel_start = 0
        t._sel_end = 5
        assert t.has_selection() is True
        assert t.get_selected_text() == "hello"

    def test_selection_across_word_wrap(self):
        t = _make_text("hello world foo", width=11)
        # Select from 'w' (offset 6) through 'o' (offset 14)
        t._sel_start = 6
        t._sel_end = 14
        assert t.get_selected_text() == "world fo"

    def test_selection_across_newline(self):
        t = _make_text("abc\ndef")
        t._sel_start = 2
        t._sel_end = 5
        assert t.get_selected_text() == "c\nd"

    def test_clear_selection(self):
        t = _make_text("hello")
        t._sel_start = 0
        t._sel_end = 3
        assert t.has_selection()
        t.clear_selection()
        assert not t.has_selection()
        assert t._sel_start is None
        assert t._sel_end is None

    def test_content_change_clears_selection(self):
        t = _make_text("hello")
        t._sel_start = 0
        t._sel_end = 3
        t.content = "new content"
        assert t._sel_start is None
        assert t._sel_end is None

    def test_zero_width_selection_not_active(self):
        t = _make_text("hello")
        t._sel_start = 3
        t._sel_end = 3
        assert t.has_selection() is False

    def test_has_selection_requires_both_endpoints(self):
        t = _make_text("hello")
        t._sel_start = 0
        t._sel_end = None
        assert t.has_selection() is False
        t._sel_start = None
        t._sel_end = 5
        assert t.has_selection() is False


class TestNativeSelectionSync:
    """Tests that cross-renderable selection syncs to native _selection_start/_selection_end."""

    def test_on_selection_changed_sets_native_attrs(self):
        """Verify on_selection_changed syncs _sel_start/_sel_end to _selection_start/_selection_end."""
        t = _make_text("hello world", width=20)
        t._sel_start = 3
        t._sel_end = 8
        t._selection_start = 3
        t._selection_end = 8
        assert t._selection_start == 3
        assert t._selection_end == 8

    def test_clear_selection_clears_native_attrs(self):
        """Verify clear_selection clears _selection_start/_selection_end."""
        t = _make_text("hello world", width=20)
        t._sel_start = 3
        t._sel_end = 8
        t._selection_start = 3
        t._selection_end = 8
        t.clear_selection()
        assert t._sel_start is None
        assert t._sel_end is None
        assert t._selection_start is None
        assert t._selection_end is None

    def test_mark_dirty_restores_native_selection(self):
        """Verify mark_dirty restores _selection_start from _sel_start after reconciliation-like clearing."""
        t = _make_text("hello world", width=20)
        t._sel_start = 2
        t._sel_end = 7
        t._selection_start = 2
        t._selection_end = 7
        # Simulate reconciliation clearing native attrs
        t._selection_start = None
        t._selection_end = None
        # mark_dirty should restore from _sel_start/_sel_end
        t.mark_dirty()
        assert t._selection_start == 2
        assert t._selection_end == 7

    def test_has_selection_false_during_cross_selection(self):
        """_has_selection returns False when _sel_start is set (cross-renderable active)."""
        t = _make_text("hello world", width=20)
        t._sel_start = 0
        t._sel_end = 5
        t._selection_start = 0
        t._selection_end = 5
        # _has_selection should be False — cross-renderable selection is active
        assert t._has_selection is False

    def test_has_selection_true_for_programmatic_selection(self):
        """_has_selection returns True for programmatic selection (no _sel_start)."""
        t = _make_text("hello world", width=20)
        t._selection_start = 0
        t._selection_end = 5
        assert t._sel_start is None
        assert t._has_selection is True
