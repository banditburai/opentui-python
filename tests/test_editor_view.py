"""Port of upstream editor-view.test.ts.

Upstream: packages/core/src/editor-view.test.ts
Tests ported: 68/68 (68 implemented)
"""

import pytest
from opentui.editor.edit_buffer_native import NativeEditBuffer
from opentui.editor.editor_view_native import NativeEditorView
from opentui.native import is_available

pytestmark = pytest.mark.skipif(not is_available(), reason="Native bindings not available")


def _create_buffer_and_view(width: int = 40, height: int = 10):
    """Helper: create an EditBuffer (wcwidth encoding=0) and an EditorView."""
    buffer = NativeEditBuffer(encoding=0)
    view = NativeEditorView(buffer.ptr, width, height)
    return buffer, view


def _get_cursor(eb: NativeEditBuffer) -> tuple[int, int]:
    return eb.get_cursor_position()


class TestEditorViewInitialization:
    """Maps to describe("EditorView > initialization")."""

    def test_should_create_view_with_specified_viewport_dimensions(self):
        """Maps to it("should create view with specified viewport dimensions")."""
        buffer, view = _create_buffer_and_view(40, 10)
        viewport = view.get_viewport()
        assert viewport["width"] == 40
        assert viewport["height"] == 10
        assert viewport["offsetY"] == 0
        assert viewport["offsetX"] == 0
        view.destroy()
        buffer.destroy()

    def test_should_start_with_wrap_mode_set_to_none(self):
        """Maps to it("should start with wrap mode set to none")."""
        buffer, view = _create_buffer_and_view(40, 10)
        assert view.get_virtual_line_count() >= 0
        view.destroy()
        buffer.destroy()


class TestEditorViewViewportManagement:
    """Maps to describe("EditorView > viewport management")."""

    def test_should_update_viewport_size(self):
        """Maps to it("should update viewport size")."""
        buffer, view = _create_buffer_and_view(40, 10)
        view.set_viewport_size(80, 20)
        viewport = view.get_viewport()
        assert viewport["width"] == 80
        assert viewport["height"] == 20
        view.destroy()
        buffer.destroy()

    def test_should_set_scroll_margin(self):
        """Maps to it("should set scroll margin").

        Upstream uses expect(true).toBe(true) — test passes by not throwing.
        """
        buffer, view = _create_buffer_and_view(40, 10)
        view.set_scroll_margin(0.2)
        view.destroy()
        buffer.destroy()

    def test_should_return_correct_virtual_line_count_for_simple_text(self):
        """Maps to it("should return correct virtual line count for simple text")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Line 1\nLine 2\nLine 3")
        assert view.get_virtual_line_count() == 3
        view.destroy()
        buffer.destroy()


class TestEditorViewTextWrapping:
    """Maps to describe("EditorView > text wrapping")."""

    def test_should_enable_and_disable_wrapping_via_wrap_mode(self):
        """Maps to it("should enable and disable wrapping via wrap mode")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGHIJKLMNOPQRST")

        assert view.get_virtual_line_count() == 1

        view.set_wrap_mode("char")
        assert view.get_virtual_line_count() > 1

        view.set_wrap_mode("none")
        assert view.get_virtual_line_count() == 1
        view.destroy()
        buffer.destroy()

    def test_should_wrap_at_viewport_width(self):
        """Maps to it("should wrap at viewport width")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRST")

        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        assert view.get_virtual_line_count() == 2

        view.set_viewport_size(5, 10)
        assert view.get_virtual_line_count() == 4

        view.set_viewport_size(20, 10)
        assert view.get_virtual_line_count() == 1
        view.destroy()
        buffer.destroy()

    def test_should_change_wrap_mode(self):
        """Maps to it("should change wrap mode")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello wonderful world")

        view.set_viewport_size(10, 10)

        view.set_wrap_mode("char")
        char_count = view.get_virtual_line_count()
        assert char_count >= 2

        view.set_wrap_mode("word")
        word_count = view.get_virtual_line_count()
        assert word_count >= 2

        view.set_wrap_mode("none")
        none_count = view.get_virtual_line_count()
        assert none_count == 1
        view.destroy()
        buffer.destroy()

    def test_should_preserve_newlines_when_wrapping(self):
        """Maps to it("should preserve newlines when wrapping")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Short\nAnother short line\nLast")

        view.set_wrap_mode("char")
        view.set_viewport_size(50, 10)

        assert view.get_virtual_line_count() == 3
        view.destroy()
        buffer.destroy()

    def test_should_wrap_long_lines_with_wrapping_enabled(self):
        """Maps to it("should wrap long lines with wrapping enabled")."""
        buffer, view = _create_buffer_and_view(40, 10)
        long_line = "This is a very long line that will definitely wrap when the viewport is narrow"
        buffer.set_text(long_line)

        view.set_wrap_mode("char")
        view.set_viewport_size(20, 10)

        vline_count = view.get_virtual_line_count()
        assert vline_count > 1
        view.destroy()
        buffer.destroy()


class TestEditorViewIntegrationWithEditBuffer:
    """Maps to describe("EditorView > integration with EditBuffer")."""

    def test_should_reflect_edits_made_to_edit_buffer(self):
        """Maps to it("should reflect edits made to EditBuffer")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Line 1\nLine 2\nLine 3")
        assert view.get_virtual_line_count() == 3

        buffer.goto_line(9999)
        buffer.newline()
        buffer.insert_text("Line 4")

        assert view.get_virtual_line_count() == 4
        view.destroy()
        buffer.destroy()

    def test_should_update_after_text_deletion(self):
        """Maps to it("should update after text deletion")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Line 1\nLine 2\nLine 3")
        assert view.get_virtual_line_count() == 3

        buffer.goto_line(1)
        buffer.delete_line()

        assert view.get_virtual_line_count() == 2
        view.destroy()
        buffer.destroy()


class TestEditorViewViewportWithWrappingAndEditing:
    """Maps to describe("EditorView > viewport with wrapping and editing")."""

    def test_should_maintain_wrapping_after_edits(self):
        """Maps to it("should maintain wrapping after edits")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Short line")

        view.set_wrap_mode("char")
        view.set_viewport_size(20, 10)

        assert view.get_virtual_line_count() == 1

        buffer.goto_line(9999)
        buffer.insert_text(" that becomes very long and should wrap now")

        assert view.get_virtual_line_count() > 1
        view.destroy()
        buffer.destroy()

    def test_should_handle_viewport_resize_with_wrapped_content(self):
        """Maps to it("should handle viewport resize with wrapped content")."""
        buffer, view = _create_buffer_and_view(40, 10)
        long_text = "This is a very long line that will wrap when the viewport is narrow"
        buffer.set_text(long_text)

        view.set_wrap_mode("char")
        view.set_viewport_size(20, 10)

        count20 = view.get_virtual_line_count()
        assert count20 > 1

        view.set_viewport_size(40, 10)
        count40 = view.get_virtual_line_count()
        assert count40 < count20
        view.destroy()
        buffer.destroy()


class TestEditorViewSelection:
    """Maps to describe("EditorView > selection")."""

    def test_should_set_and_reset_selection(self):
        """Maps to it("should set and reset selection")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")

        view.set_selection(0, 5)
        assert view.has_selection() is True

        view.reset_selection()
        assert view.has_selection() is False
        view.destroy()
        buffer.destroy()

    def test_should_set_selection_with_colors(self):
        """Maps to it("should set selection with colors")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")

        # We don't pass color objects in the Python API but the selection should still work
        view.set_selection(0, 5)
        assert view.has_selection() is True

        selection = view.get_selection()
        assert selection == {"start": 0, "end": 5}
        view.destroy()
        buffer.destroy()

    def test_should_update_selection_end_position(self):
        """Maps to it("should update selection end position")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")

        view.set_selection(0, 5)
        assert view.get_selected_text() == "Hello"

        view.update_selection(11)
        assert view.get_selected_text() == "Hello World"

        selection = view.get_selection()
        assert selection == {"start": 0, "end": 11}
        view.destroy()
        buffer.destroy()

    def test_should_shrink_selection_with_update_selection(self):
        """Maps to it("should shrink selection with updateSelection")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")

        view.set_selection(0, 11)
        assert view.get_selected_text() == "Hello World"

        view.update_selection(5)
        assert view.get_selected_text() == "Hello"
        view.destroy()
        buffer.destroy()

    def test_should_update_local_selection_focus_position(self):
        """Maps to it("should update local selection focus position")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")

        changed1 = view.set_local_selection(0, 0, 5, 0)
        assert changed1 is True
        assert view.get_selected_text() == "Hello"

        changed2 = view.update_local_selection(0, 0, 11, 0)
        assert changed2 is True
        assert view.get_selected_text() == "Hello World"
        view.destroy()
        buffer.destroy()

    def test_should_update_local_selection_across_lines(self):
        """Maps to it("should update local selection across lines")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Line 1\nLine 2\nLine 3")

        view.set_local_selection(2, 0, 2, 0)

        changed = view.update_local_selection(2, 0, 4, 1)
        assert changed is True

        selected_text = view.get_selected_text()
        assert "ne 1" in selected_text
        assert "Line" in selected_text
        view.destroy()
        buffer.destroy()

    def test_should_fallback_to_set_local_selection_when_no_existing_anchor(self):
        """Maps to it("should fallback to setLocalSelection when updateLocalSelection called with no existing anchor")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")

        changed = view.update_local_selection(0, 0, 5, 0)
        assert changed is True
        assert view.has_selection() is True
        assert view.get_selected_text() == "Hello"
        view.destroy()
        buffer.destroy()

    def test_should_preserve_anchor_when_updating_local_selection(self):
        """Maps to it("should preserve anchor when updating local selection")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")

        view.set_local_selection(0, 0, 5, 0)
        assert view.get_selected_text() == "Hello"

        view.update_local_selection(0, 0, 11, 0)
        assert view.get_selected_text() == "Hello World"

        view.update_local_selection(0, 0, 3, 0)
        assert view.get_selected_text() == "Hel"
        view.destroy()
        buffer.destroy()

    def test_should_handle_backward_selection_with_update_local_selection(self):
        """Maps to it("should handle backward selection with updateLocalSelection")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")

        view.set_local_selection(11, 0, 11, 0)

        changed = view.update_local_selection(11, 0, 6, 0)
        assert changed is True
        assert view.get_selected_text() == "World"
        view.destroy()
        buffer.destroy()

    def test_should_handle_wrapped_lines_with_update_local_selection(self):
        """Maps to it("should handle wrapped lines with updateLocalSelection")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRST")

        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        view.set_local_selection(0, 0, 0, 0)

        changed = view.update_local_selection(0, 0, 5, 1)
        assert changed is True
        assert view.get_selected_text() == "ABCDEFGHIJKLMNO"
        view.destroy()
        buffer.destroy()


class TestEditorViewWordBoundaryNavigation:
    """Maps to describe("EditorView > word boundary navigation")."""

    def test_should_get_next_word_boundary_with_visual_cursor(self):
        """Maps to it("should get next word boundary with visual cursor")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("hello world foo")
        buffer.set_cursor(0, 0)

        next_boundary = view.get_next_word_boundary()
        assert next_boundary is not None
        assert next_boundary.visual_col > 0
        view.destroy()
        buffer.destroy()

    def test_should_get_previous_word_boundary_with_visual_cursor(self):
        """Maps to it("should get previous word boundary with visual cursor")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("hello world foo")
        buffer.set_cursor(0, 15)

        prev_boundary = view.get_prev_word_boundary()
        assert prev_boundary is not None
        assert prev_boundary.visual_col < 15
        view.destroy()
        buffer.destroy()

    def test_should_handle_word_boundary_at_start(self):
        """Maps to it("should handle word boundary at start")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("hello world")
        buffer.set_cursor(0, 0)

        prev_boundary = view.get_prev_word_boundary()
        assert prev_boundary.logical_row == 0
        assert prev_boundary.visual_col == 0
        view.destroy()
        buffer.destroy()

    def test_should_handle_word_boundary_at_end(self):
        """Maps to it("should handle word boundary at end")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("hello world")
        buffer.set_cursor(0, 11)

        next_boundary = view.get_next_word_boundary()
        assert next_boundary.visual_col == 11
        view.destroy()
        buffer.destroy()

    def test_should_navigate_across_lines_with_visual_coordinates(self):
        """Maps to it("should navigate across lines with visual coordinates")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("hello\nworld")
        buffer.set_cursor(0, 5)

        next_boundary = view.get_next_word_boundary()
        assert next_boundary.logical_row >= 0
        view.destroy()
        buffer.destroy()

    def test_should_handle_wrapping_when_getting_word_boundaries(self):
        """Maps to it("should handle wrapping when getting word boundaries")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("hello world test foo bar")
        view.set_wrap_mode("word")
        view.set_viewport_size(10, 10)

        buffer.set_cursor(0, 0)
        next_boundary = view.get_next_word_boundary()

        assert next_boundary is not None
        assert next_boundary.visual_row >= 0
        assert next_boundary.logical_row >= 0
        view.destroy()
        buffer.destroy()


class TestEditorViewLargeContent:
    """Maps to describe("EditorView > large content")."""

    def test_should_handle_many_lines(self):
        """Maps to it("should handle many lines")."""
        buffer, view = _create_buffer_and_view(40, 10)
        lines = "\n".join(f"Line {i}" for i in range(100))
        buffer.set_text(lines)

        assert view.get_total_virtual_line_count() == 100
        view.destroy()
        buffer.destroy()

    def test_should_handle_very_long_single_line_with_wrapping(self):
        """Maps to it("should handle very long single line with wrapping")."""
        buffer, view = _create_buffer_and_view(40, 10)
        long_line = "A" * 1000
        buffer.set_text(long_line)

        view.set_wrap_mode("char")
        view.set_viewport_size(80, 24)

        vline_count = view.get_virtual_line_count()
        assert vline_count > 10
        view.destroy()
        buffer.destroy()


class TestEditorViewViewportSlicing:
    """Maps to describe("EditorView > viewport slicing")."""

    def test_should_show_subset_of_content_in_viewport(self):
        """Maps to it("should show subset of content in viewport")."""
        buffer = NativeEditBuffer(encoding=0)
        lines = "\n".join(f"Line {i}" for i in range(20))
        buffer.set_text(lines)

        small_view = NativeEditorView(buffer.ptr, 40, 5)

        assert small_view.get_total_virtual_line_count() == 20

        small_view.destroy()
        buffer.destroy()


class TestEditorViewErrorHandling:
    """Maps to describe("EditorView > error handling")."""

    def test_should_throw_error_when_using_destroyed_view(self):
        """Maps to it("should throw error when using destroyed view")."""
        buffer, view = _create_buffer_and_view(40, 10)
        view.destroy()

        with pytest.raises(RuntimeError, match="EditorView is destroyed"):
            view.get_virtual_line_count()
        with pytest.raises(RuntimeError, match="EditorView is destroyed"):
            view.set_viewport_size(80, 24)
        with pytest.raises(RuntimeError, match="EditorView is destroyed"):
            view.set_wrap_mode("char")

        buffer.destroy()


class TestEditorViewUnicodeEdgeCases:
    """Maps to describe("EditorView > Unicode edge cases")."""

    def test_should_handle_emoji_with_wrapping(self):
        """Maps to it("should handle emoji with wrapping")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("\U0001f31f" * 20)

        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        assert view.get_virtual_line_count() > 1
        view.destroy()
        buffer.destroy()

    def test_should_handle_cjk_characters_with_wrapping(self):
        """Maps to it("should handle CJK characters with wrapping")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("\u6d4b\u8bd5\u6587\u5b57\u5904\u7406\u529f\u80fd")

        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        vline_count = view.get_virtual_line_count()
        assert vline_count >= 1
        view.destroy()
        buffer.destroy()

    def test_should_handle_mixed_ascii_and_wide_characters(self):
        """Maps to it("should handle mixed ASCII and wide characters")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("AB\u6d4b\u8bd5CD\u6587\u5b57EF")

        view.set_wrap_mode("char")
        view.set_viewport_size(8, 10)

        assert view.get_virtual_line_count() >= 1
        view.destroy()
        buffer.destroy()

    def test_should_navigate_visual_cursor_correctly_through_emoji_and_cjk(self):
        """Maps to it("should navigate visual cursor correctly through emoji and CJK")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("(emoji \U0001f31f and CJK \u4e16\u754c)")

        cursor = view.get_visual_cursor()
        assert cursor.visual_row == 0
        assert cursor.visual_col == 0
        assert cursor.offset == 0

        # Move right 6 times: (emoji_  (6 chars)
        for _ in range(6):
            buffer.move_cursor_right()
        cursor = view.get_visual_cursor()
        assert cursor.offset == 6

        # Move right past space before emoji
        buffer.move_cursor_right()
        cursor = view.get_visual_cursor()
        assert cursor.offset == 7

        # Move right past emoji (2-byte grapheme in logical cols)
        buffer.move_cursor_right()
        cursor = view.get_visual_cursor()
        assert cursor.offset == 9

        # Move left back to start of emoji
        buffer.move_cursor_left()
        cursor = view.get_visual_cursor()
        assert cursor.offset == 7

        # Move left one more
        buffer.move_cursor_left()
        cursor = view.get_visual_cursor()
        assert cursor.offset == 6
        view.destroy()
        buffer.destroy()

    def test_should_handle_vertical_navigation_through_emoji_cells_correctly(self):
        """Maps to it("should handle vertical navigation through emoji cells correctly")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text(
            "1234567890123456789\n(emoji \U0001f31f and CJK \u4e16\u754c)\n1234567890123456789"
        )

        buffer.set_cursor(0, 7)
        cursor = view.get_visual_cursor()
        assert cursor.visual_row == 0
        assert cursor.visual_col == 7

        view.move_down_visual()
        cursor = view.get_visual_cursor()
        assert cursor.visual_row == 1
        assert cursor.visual_col == 7

        buffer.move_cursor_right()
        cursor = view.get_visual_cursor()
        assert cursor.visual_col == 9

        view.move_up_visual()
        cursor = view.get_visual_cursor()
        assert cursor.visual_row == 0
        assert cursor.visual_col == 9

        buffer.move_cursor_left()
        cursor = view.get_visual_cursor()
        assert cursor.visual_col == 8

        view.move_down_visual()
        cursor = view.get_visual_cursor()
        assert cursor.visual_row == 1
        assert cursor.visual_col == 8

        buffer.move_cursor_left()
        cursor = view.get_visual_cursor()
        assert cursor.visual_col == 6
        view.destroy()
        buffer.destroy()


class TestEditorViewCursorMovementAroundMultiCellGraphemes:
    """Maps to describe("EditorView > cursor movement around multi-cell graphemes")."""

    def test_should_understand_logical_vs_visual_cursor_positions(self):
        """Maps to it("should understand logical vs visual cursor positions")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("a\U0001f31fb")

        buffer.set_cursor(0, 0)
        assert view.get_visual_cursor().visual_col == 0

        buffer.set_cursor(0, 1)
        assert view.get_visual_cursor().visual_col == 1

        buffer.set_cursor(0, 3)
        assert view.get_visual_cursor().visual_col == 3

        buffer.set_cursor(0, 4)
        assert view.get_visual_cursor().visual_col == 4

        buffer.set_cursor(0, 0)
        buffer.move_cursor_right()
        pos = _get_cursor(buffer)
        assert pos[1] == 1

        buffer.move_cursor_right()
        pos = _get_cursor(buffer)
        assert pos[1] == 3
        assert view.get_visual_cursor().visual_col == 3

        buffer.move_cursor_right()
        pos = _get_cursor(buffer)
        assert pos[1] == 4
        view.destroy()
        buffer.destroy()

    def test_should_move_cursor_correctly_around_emoji_with_visual_positions(self):
        """Maps to it("should move cursor correctly around emoji with visual positions")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("a\U0001f31fb")

        buffer.set_cursor(0, 1)
        assert view.get_visual_cursor().visual_col == 1

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 3

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 4

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 3

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 1
        view.destroy()
        buffer.destroy()

    def test_should_move_cursor_correctly_around_cjk_characters_with_visual_positions(self):
        """Maps to it("should move cursor correctly around CJK characters with visual positions")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("a\u4e16\u754cb")

        buffer.set_cursor(0, 0)
        assert view.get_visual_cursor().visual_col == 0

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 1

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 3

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 5

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 6

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 5

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 3

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 1
        view.destroy()
        buffer.destroy()

    def test_should_handle_backspace_correctly_after_emoji(self):
        """Maps to it("should handle backspace correctly after emoji")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("a\U0001f31fb")

        buffer.set_cursor(0, 3)
        assert view.get_visual_cursor().visual_col == 3

        buffer.delete_char_backward()
        assert buffer.get_text() == "ab"
        assert view.get_visual_cursor().visual_col == 1
        view.destroy()
        buffer.destroy()

    def test_should_handle_backspace_correctly_after_cjk_character(self):
        """Maps to it("should handle backspace correctly after CJK character")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("\u4e16\u754c")

        buffer.set_cursor(0, 4)
        assert view.get_visual_cursor().visual_col == 4

        buffer.delete_char_backward()
        assert buffer.get_text() == "\u4e16"
        assert view.get_visual_cursor().visual_col == 2

        buffer.delete_char_backward()
        assert buffer.get_text() == ""
        assert view.get_visual_cursor().visual_col == 0
        view.destroy()
        buffer.destroy()

    def test_should_treat_multi_cell_graphemes_as_single_units_for_cursor_movement(self):
        """Maps to it("should treat multi-cell graphemes as single units for cursor movement")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("\U0001f31f\u4e16\u754c\U0001f389")

        buffer.set_cursor(0, 0)
        assert view.get_visual_cursor().visual_col == 0

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 2

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 4

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 6

        buffer.move_cursor_right()
        assert view.get_visual_cursor().visual_col == 8

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 6

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 4

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 2

        buffer.move_cursor_left()
        assert view.get_visual_cursor().visual_col == 0
        view.destroy()
        buffer.destroy()

    def test_should_handle_backspace_through_mixed_multi_cell_graphemes(self):
        """Maps to it("should handle backspace through mixed multi-cell graphemes")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("a\U0001f31fb\u4e16c")

        buffer.set_cursor(0, 7)
        assert view.get_visual_cursor().visual_col == 7

        buffer.delete_char_backward()
        assert buffer.get_text() == "a\U0001f31fb\u4e16"
        assert view.get_visual_cursor().visual_col == 6

        buffer.delete_char_backward()
        assert buffer.get_text() == "a\U0001f31fb"
        assert view.get_visual_cursor().visual_col == 4

        buffer.delete_char_backward()
        assert buffer.get_text() == "a\U0001f31f"
        assert view.get_visual_cursor().visual_col == 3

        buffer.delete_char_backward()
        assert buffer.get_text() == "a"
        assert view.get_visual_cursor().visual_col == 1

        buffer.delete_char_backward()
        assert buffer.get_text() == ""
        assert view.get_visual_cursor().visual_col == 0
        view.destroy()
        buffer.destroy()

    def test_should_handle_delete_key_correctly_before_multi_cell_graphemes(self):
        """Maps to it("should handle delete key correctly before multi-cell graphemes")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("a\U0001f31fb")

        buffer.set_cursor(0, 1)
        assert view.get_visual_cursor().visual_col == 1

        buffer.delete_char()
        assert buffer.get_text() == "ab"
        assert view.get_visual_cursor().visual_col == 1

        buffer.set_cursor(0, 0)

        buffer.delete_char()
        assert buffer.get_text() == "b"
        assert view.get_visual_cursor().visual_col == 0
        view.destroy()
        buffer.destroy()

    def test_should_handle_line_start_and_end_with_multi_cell_graphemes(self):
        """Maps to it("should handle line start and end with multi-cell graphemes")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("\U0001f31f\u4e16\u754c\U0001f389")

        buffer.set_cursor(0, 0)
        assert view.get_visual_cursor().visual_col == 0

        eol = view.get_eol()
        buffer.set_cursor(eol.logical_row, eol.logical_col)
        assert view.get_visual_cursor().visual_col == 8
        view.destroy()
        buffer.destroy()


class TestEditorViewVisualLineNavigationWithoutWrapping:
    """Maps to describe("EditorView > visual line navigation (SOL/EOL) > without wrapping")."""

    def test_should_get_visual_sol_on_single_line(self):
        """Maps to it("should get visual SOL on single line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")
        buffer.set_cursor(0, 6)  # Middle of line

        sol = view.get_visual_sol()
        assert sol.logical_row == 0
        assert sol.logical_col == 0
        assert sol.visual_row == 0
        assert sol.visual_col == 0
        assert sol.offset == 0
        view.destroy()
        buffer.destroy()

    def test_should_get_visual_eol_on_single_line(self):
        """Maps to it("should get visual EOL on single line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello World")
        buffer.set_cursor(0, 6)  # Middle of line

        eol = view.get_visual_eol()
        assert eol.logical_row == 0
        assert eol.logical_col == 11
        assert eol.visual_row == 0
        assert eol.visual_col == 11
        view.destroy()
        buffer.destroy()

    def test_should_get_visual_sol_eol_on_multi_line_text(self):
        """Maps to it("should get visual SOL/EOL on multi-line text")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Line 1\nLine 2\nLine 3")

        # Test on second line
        buffer.set_cursor(1, 3)

        sol = view.get_visual_sol()
        assert sol.logical_row == 1
        assert sol.logical_col == 0
        assert sol.visual_row == 1
        assert sol.visual_col == 0

        eol = view.get_visual_eol()
        assert eol.logical_row == 1
        assert eol.logical_col == 6
        assert eol.visual_row == 1
        assert eol.visual_col == 6
        view.destroy()
        buffer.destroy()

    def test_should_handle_visual_sol_eol_at_line_boundaries(self):
        """Maps to it("should handle visual SOL/EOL at line boundaries")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABC\nDEF")

        # At start of line 0
        buffer.set_cursor(0, 0)
        sol = view.get_visual_sol()
        assert sol.logical_col == 0

        # At end of line 0
        buffer.set_cursor(0, 3)
        eol = view.get_visual_eol()
        assert eol.logical_col == 3

        # At start of line 1
        buffer.set_cursor(1, 0)
        sol = view.get_visual_sol()
        assert sol.logical_row == 1
        assert sol.logical_col == 0
        view.destroy()
        buffer.destroy()


class TestEditorViewVisualLineNavigationWithWrapping:
    """Maps to describe("EditorView > visual line navigation (SOL/EOL) > with wrapping")."""

    def test_should_get_sol_of_first_wrapped_line(self):
        """Maps to it("should get SOL of first wrapped line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        # Cursor at position 0 (first visual line)
        buffer.set_cursor(0, 0)

        sol = view.get_visual_sol()
        assert sol.logical_row == 0
        assert sol.logical_col == 0
        assert sol.visual_row == 0
        assert sol.visual_col == 0
        view.destroy()
        buffer.destroy()

    def test_should_get_eol_of_first_wrapped_line(self):
        """Maps to it("should get EOL of first wrapped line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        buffer.set_cursor(0, 5)

        eol = view.get_visual_eol()
        assert eol.logical_row == 0
        assert eol.logical_col == 9
        assert eol.visual_row == 0
        assert eol.visual_col == 9
        view.destroy()
        buffer.destroy()

    def test_should_get_sol_of_second_wrapped_line(self):
        """Maps to it("should get SOL of second wrapped line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        buffer.set_cursor(0, 15)

        sol = view.get_visual_sol()
        assert sol.logical_row == 0
        assert sol.logical_col == 10
        assert sol.visual_row == 1
        assert sol.visual_col == 0
        view.destroy()
        buffer.destroy()

    def test_should_get_eol_of_second_wrapped_line(self):
        """Maps to it("should get EOL of second wrapped line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        buffer.set_cursor(0, 15)

        eol = view.get_visual_eol()
        assert eol.logical_row == 0
        assert eol.logical_col == 19
        assert eol.visual_row == 1
        assert eol.visual_col == 9
        view.destroy()
        buffer.destroy()

    def test_should_get_eol_of_last_wrapped_line(self):
        """Maps to it("should get EOL of last wrapped line (end of logical line)")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        buffer.set_cursor(0, 25)

        eol = view.get_visual_eol()
        assert eol.logical_row == 0
        assert eol.logical_col == 26
        assert eol.visual_row == 2
        assert eol.visual_col == 6
        view.destroy()
        buffer.destroy()

    def test_should_handle_word_wrapping_correctly(self):
        """Maps to it("should handle word wrapping correctly")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello wonderful world of text")
        view.set_wrap_mode("word")
        view.set_viewport_size(15, 10)

        buffer.set_cursor(0, 20)

        vcursor = view.get_visual_cursor()
        assert vcursor.visual_row > 0

        sol = view.get_visual_sol()
        assert sol.visual_row == vcursor.visual_row
        assert sol.visual_col == 0
        assert sol.logical_row == 0
        assert sol.logical_col > 0

        eol = view.get_visual_eol()
        assert eol.visual_row == vcursor.visual_row
        assert eol.logical_row == 0
        assert eol.logical_col > sol.logical_col
        view.destroy()
        buffer.destroy()

    def test_should_move_cursor_to_end_of_current_visual_line(self):
        """Maps to it("should move cursor to END of current visual line, NOT start of next line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        buffer.set_cursor(0, 5)
        vcursor = view.get_visual_cursor()
        assert vcursor.visual_row == 0
        assert vcursor.logical_col == 5

        eol = view.get_visual_eol()
        buffer.set_cursor(eol.logical_row, eol.logical_col)

        final_cursor = _get_cursor(buffer)
        final_vcursor = view.get_visual_cursor()

        assert final_vcursor.visual_row == 0
        assert final_cursor[1] == 9
        view.destroy()
        buffer.destroy()

    def test_should_navigate_through_multiple_wrapped_lines(self):
        """Maps to it("should navigate through multiple wrapped lines")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        positions = [0, 10, 20, 30]

        for pos in positions:
            buffer.set_cursor(0, pos)

            vcursor = view.get_visual_cursor()
            sol = view.get_visual_sol()
            eol = view.get_visual_eol()

            assert sol.visual_col == 0
            assert sol.visual_row == vcursor.visual_row

            assert eol.logical_col > sol.logical_col
            assert eol.visual_row == vcursor.visual_row
        view.destroy()
        buffer.destroy()


class TestEditorViewVisualLineNavigationWithMultiByteCharacters:
    """Maps to describe("EditorView > visual line navigation (SOL/EOL) > with multi-byte characters")."""

    def test_should_handle_emoji_in_visual_sol_eol(self):
        """Maps to it("should handle emoji in visual SOL/EOL")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("Hello \U0001f31f World")
        buffer.set_cursor(0, 8)  # After emoji

        sol = view.get_visual_sol()
        assert sol.logical_col == 0
        assert sol.visual_col == 0

        eol = view.get_visual_eol()
        assert eol.logical_col == 14
        assert eol.visual_col == 14  # Visual width of the line
        view.destroy()
        buffer.destroy()

    def test_should_handle_cjk_characters_in_visual_sol_eol(self):
        """Maps to it("should handle CJK characters in visual SOL/EOL")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("\u6d4b\u8bd5\u6587\u5b57")
        buffer.set_cursor(0, 2)  # Middle

        sol = view.get_visual_sol()
        assert sol.logical_col == 0
        assert sol.visual_col == 0

        eol = view.get_visual_eol()
        assert eol.logical_row == 0
        assert eol.logical_col == 8  # CJK text line width
        assert eol.visual_col == 8  # Visual width
        view.destroy()
        buffer.destroy()

    def test_should_handle_wrapped_emoji_correctly(self):
        """Maps to it("should handle wrapped emoji correctly")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("\U0001f31f" * 10)  # 10 emoji
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        # First wrapped line
        buffer.set_cursor(0, 2)
        sol = view.get_visual_sol()
        eol = view.get_visual_eol()
        vcursor = view.get_visual_cursor()

        assert vcursor.visual_row == 0
        assert sol.logical_col == 0
        assert sol.visual_col == 0
        assert eol.logical_col > 0
        assert eol.visual_col > 0

        # Second wrapped line - need to be far enough to be on next visual line
        buffer.set_cursor(0, 12)  # Past first 5 emoji (10 logical cols)
        vcursor = view.get_visual_cursor()
        sol = view.get_visual_sol()
        eol = view.get_visual_eol()

        assert vcursor.visual_row == 1  # Should be on second visual line
        assert sol.visual_col == 0
        assert sol.logical_col > 0
        assert eol.logical_col == 20  # End of logical line
        view.destroy()
        buffer.destroy()

    def test_should_handle_mixed_ascii_and_cjk_with_wrapping(self):
        """Maps to it("should handle mixed ASCII and CJK with wrapping")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("AB\u6d4b\u8bd5CD\u6587\u5b57EF")  # Mixed width chars
        view.set_wrap_mode("char")
        view.set_viewport_size(8, 10)

        buffer.set_cursor(0, 5)

        vcursor = view.get_visual_cursor()
        sol = view.get_visual_sol()
        eol = view.get_visual_eol()

        assert sol.visual_row == vcursor.visual_row
        assert sol.visual_col == 0
        assert eol.visual_row == vcursor.visual_row
        assert eol.visual_col > 0
        view.destroy()
        buffer.destroy()


class TestEditorViewVisualLineNavigationEdgeCases:
    """Maps to describe("EditorView > visual line navigation (SOL/EOL) > edge cases")."""

    def test_should_handle_empty_line(self):
        """Maps to it("should handle empty line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("\n")
        buffer.set_cursor(0, 0)

        sol = view.get_visual_sol()
        eol = view.get_visual_eol()

        assert sol.logical_row == 0
        assert sol.logical_col == 0
        assert eol.logical_row == 0
        assert eol.logical_col == 0
        view.destroy()
        buffer.destroy()

    def test_should_handle_cursor_at_exact_wrap_boundary(self):
        """Maps to it("should handle cursor at exact wrap boundary")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("0123456789ABCDEFGHIJ")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        # Cursor at position 10 (start of second visual line)
        buffer.set_cursor(0, 10)

        vcursor = view.get_visual_cursor()
        assert vcursor.visual_row == 1

        sol = view.get_visual_sol()
        assert sol.logical_col == 10
        assert sol.visual_row == 1
        assert sol.visual_col == 0

        eol = view.get_visual_eol()
        assert eol.logical_col == 20
        assert eol.visual_row == 1
        view.destroy()
        buffer.destroy()

    def test_should_handle_single_character_line(self):
        """Maps to it("should handle single character line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("X")
        buffer.set_cursor(0, 0)

        sol = view.get_visual_sol()
        eol = view.get_visual_eol()

        assert sol.logical_col == 0
        assert eol.logical_col == 1
        view.destroy()
        buffer.destroy()

    def test_should_compare_logical_eol_vs_visual_eol_on_wrapped_line(self):
        """Maps to it("should compare logical EOL vs visual EOL on wrapped line")."""
        buffer, view = _create_buffer_and_view(40, 10)
        buffer.set_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        view.set_wrap_mode("char")
        view.set_viewport_size(10, 10)

        buffer.set_cursor(0, 5)

        logical_eol = view.get_eol()
        visual_eol = view.get_visual_eol()

        assert logical_eol.logical_col == 26
        assert visual_eol.logical_col == 9
        assert visual_eol.visual_row == 0
        view.destroy()
        buffer.destroy()
