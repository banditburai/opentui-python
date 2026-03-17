"""Port of upstream text-buffer-view.test.ts.

Upstream: packages/core/src/text-buffer-view.test.ts
Tests: 45 total (45 implemented)
"""

import pytest
from opentui.native import NativeTextBuffer, NativeTextBufferView, is_available

pytestmark = pytest.mark.skipif(not is_available(), reason="Native bindings not available")


def make_buffer_and_view(text: str = "") -> tuple[NativeTextBuffer, NativeTextBufferView]:
    """Helper to create a paired buffer and view."""
    buf = NativeTextBuffer()
    if text:
        buf.set_text(text)
    view = NativeTextBufferView(buf.ptr, text_buffer=buf)
    return buf, view


class TestTextBufferView:
    """TextBufferView"""

    class TestLineInfoGetterWithWrapping:
        """line_info getter with wrapping"""

        def test_should_return_line_info_for_empty_buffer(self):
            buffer, view = make_buffer_and_view("")

            info = view.get_line_info()
            assert info["start_cols"] == [0]
            assert info["width_cols"] == [0]

        def test_should_return_single_line_info_for_simple_text_without_newlines(self):
            buffer, view = make_buffer_and_view("Hello World")

            info = view.get_line_info()
            assert info["start_cols"] == [0]
            assert len(info["width_cols"]) == 1
            assert info["width_cols"][0] > 0

        def test_should_handle_single_newline_correctly(self):
            buffer, view = make_buffer_and_view("Hello\nWorld")

            info = view.get_line_info()
            # "Hello" (0-4) + newline (5) + "World" starts at col 6
            assert info["start_cols"] == [0, 6]
            assert len(info["width_cols"]) == 2
            assert info["width_cols"][0] > 0
            assert info["width_cols"][1] > 0

        def test_should_return_virtual_line_info_when_text_wrapping_is_enabled(self):
            long_text = (
                "This is a very long text that should wrap when the text wrapping is enabled."
            )
            buffer, view = make_buffer_and_view(long_text)

            unwrapped_info = view.get_line_info()
            assert unwrapped_info["start_cols"] == [0]
            assert len(unwrapped_info["width_cols"]) == 1
            assert unwrapped_info["width_cols"][0] == 76

            view.set_wrap_mode("char")
            view.set_wrap_width(20)

            wrapped_info = view.get_line_info()
            assert len(wrapped_info["start_cols"]) > 1
            assert len(wrapped_info["width_cols"]) > 1

            for width in wrapped_info["width_cols"]:
                assert width <= 20

            for i in range(1, len(wrapped_info["start_cols"])):
                assert wrapped_info["start_cols"][i] > wrapped_info["start_cols"][i - 1]

        def test_should_return_correct_line_info_for_word_wrapping(self):
            text = "Hello world this is a test"
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("word")
            view.set_wrap_width(12)

            info = view.get_line_info()
            assert len(info["start_cols"]) > 1

            for width in info["width_cols"]:
                assert width <= 12

        def test_should_return_correct_line_info_for_char_wrapping(self):
            text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("char")
            view.set_wrap_width(10)

            info = view.get_line_info()
            assert info["start_cols"] == [0, 10, 20]
            assert info["width_cols"] == [10, 10, 6]

        def test_should_update_line_info_when_wrap_width_changes(self):
            text = "The quick brown fox jumps over the lazy dog"
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("char")
            view.set_wrap_width(15)

            info1 = view.get_line_info()
            line_count1 = len(info1["start_cols"])

            view.set_wrap_width(30)

            info2 = view.get_line_info()
            line_count2 = len(info2["start_cols"])

            assert line_count2 < line_count1

        def test_should_return_original_line_info_when_wrap_is_disabled(self):
            text = "Line 1\nLine 2\nLine 3"
            buffer, view = make_buffer_and_view(text)

            original_info = view.get_line_info()
            # "Line 1" (0-5) + newline = 6 cols, "Line 2" starts at 7, "Line 3" at 14
            assert original_info["start_cols"] == [0, 7, 14]

            view.set_wrap_mode("char")
            view.set_wrap_width(5)

            wrapped_info = view.get_line_info()
            assert len(wrapped_info["start_cols"]) > 3

            view.set_wrap_mode("none")
            view.set_wrap_width(0)  # 0 = null in the Zig layer

            unwrapped_info = view.get_line_info()
            assert unwrapped_info["start_cols"] == [0, 7, 14]

        def test_should_return_extended_wrap_info(self):
            text = "Line 1 content\nLine 2"
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("char")
            view.set_wrap_width(10)

            # "Line 1 content" (14 chars) wraps into two lines:
            # "Line 1 con" (10) + "tent" (4)
            # "Line 2" (6 chars) fits on one line

            info = view.get_line_info()

            assert len(info["sources"]) == 3
            assert len(info["wraps"]) == 3

            # First visual line: source line 0, wrap 0
            assert info["sources"][0] == 0
            assert info["wraps"][0] == 0

            # Second visual line: source line 0, wrap 1 (continuation)
            assert info["sources"][1] == 0
            assert info["wraps"][1] == 1

            # Third visual line: source line 1, wrap 0
            assert info["sources"][2] == 1
            assert info["wraps"][2] == 0

    class TestGetSelectedText:
        """getSelectedText"""

        def test_should_return_empty_string_when_no_selection(self):
            buffer, view = make_buffer_and_view("Hello World")

            selected_text = view.get_selected_text()
            assert selected_text == ""

        def test_should_return_selected_text_for_simple_selection(self):
            buffer, view = make_buffer_and_view("Hello World")

            view.set_selection(6, 11)
            selected_text = view.get_selected_text()
            assert selected_text == "World"

        def test_should_return_selected_text_with_newlines(self):
            buffer, view = make_buffer_and_view("Line 1\nLine 2\nLine 3")

            # Rope offsets: "Line 1" (0-5) + newline (6) + "Line 2" (7-12)
            # Selection [0, 9) = "Line 1\nLi"
            view.set_selection(0, 9)
            selected_text = view.get_selected_text()
            assert selected_text == "Line 1\nLi"

        def test_should_handle_unicode_characters_in_selection(self):
            buffer, view = make_buffer_and_view("Hello 世界 🌟")

            view.set_selection(6, 12)
            selected_text = view.get_selected_text()
            assert selected_text == "世界 🌟"

        def test_should_handle_selection_reset(self):
            buffer, view = make_buffer_and_view("Hello World")

            view.set_selection(6, 11)
            assert view.get_selected_text() == "World"

            view.reset_selection()
            assert view.get_selected_text() == ""

    class TestSelectionState:
        """selection state"""

        def test_should_track_selection_state(self):
            buffer, view = make_buffer_and_view("Hello World")

            assert view.has_selection() is False

            view.set_selection(0, 5)
            assert view.has_selection() is True

            selection = view.get_selection()
            assert selection == {"start": 0, "end": 5}

            view.reset_selection()
            assert view.has_selection() is False

        def test_should_update_selection_end_position(self):
            buffer, view = make_buffer_and_view("Hello World")

            view.set_selection(0, 5)
            assert view.get_selected_text() == "Hello"

            view.update_selection(11)
            assert view.get_selected_text() == "Hello World"

            selection = view.get_selection()
            assert selection == {"start": 0, "end": 11}

        def test_should_shrink_selection_with_update_selection(self):
            buffer, view = make_buffer_and_view("Hello World")

            view.set_selection(0, 11)
            assert view.get_selected_text() == "Hello World"

            view.update_selection(5)
            assert view.get_selected_text() == "Hello"

            selection = view.get_selection()
            assert selection == {"start": 0, "end": 5}

        def test_should_do_nothing_when_update_selection_called_with_no_selection(self):
            buffer, view = make_buffer_and_view("Hello World")

            assert view.has_selection() is False

            view.update_selection(5)
            assert view.has_selection() is False
            assert view.get_selected_text() == ""

        def test_should_update_local_selection_focus_position(self):
            buffer, view = make_buffer_and_view("Hello World")

            changed1 = view.set_local_selection(0, 0, 5, 0)
            assert changed1 is True
            assert view.get_selected_text() == "Hello"

            changed2 = view.update_local_selection(0, 0, 11, 0)
            assert changed2 is True
            assert view.get_selected_text() == "Hello World"

        def test_should_update_local_selection_across_lines(self):
            buffer, view = make_buffer_and_view("Line 1\nLine 2\nLine 3")

            view.set_local_selection(2, 0, 2, 0)

            changed = view.update_local_selection(2, 0, 4, 1)
            assert changed is True

            selected_text = view.get_selected_text()
            assert "ne 1" in selected_text
            assert "Line" in selected_text

        def test_should_fallback_to_set_local_selection_when_no_existing_anchor(self):
            buffer, view = make_buffer_and_view("Hello World")

            changed = view.update_local_selection(0, 0, 5, 0)
            assert changed is True
            assert view.has_selection() is True
            assert view.get_selected_text() == "Hello"

        def test_should_preserve_anchor_when_updating_local_selection(self):
            buffer, view = make_buffer_and_view("Hello World")

            view.set_local_selection(0, 0, 5, 0)
            assert view.get_selected_text() == "Hello"

            view.update_local_selection(0, 0, 6, 0)
            assert view.get_selected_text() == "Hello "

            view.update_local_selection(0, 0, 11, 0)
            assert view.get_selected_text() == "Hello World"

            view.update_local_selection(0, 0, 3, 0)
            assert view.get_selected_text() == "Hel"

        def test_should_handle_backward_selection_with_update_local_selection(self):
            buffer, view = make_buffer_and_view("Hello World")

            view.set_local_selection(11, 0, 11, 0)

            changed = view.update_local_selection(11, 0, 6, 0)
            assert changed is True
            assert view.get_selected_text() == "World"

    class TestGetPlainText:
        """getPlainText"""

        def test_should_return_empty_string_for_empty_buffer(self):
            buffer, view = make_buffer_and_view("")

            plain_text = view.get_plain_text()
            assert plain_text == ""

        def test_should_return_plain_text_without_styling(self):
            buffer, view = make_buffer_and_view("Hello World")

            plain_text = view.get_plain_text()
            assert plain_text == "Hello World"

        def test_should_handle_text_with_newlines(self):
            buffer, view = make_buffer_and_view("Line 1\nLine 2\nLine 3")

            plain_text = view.get_plain_text()
            assert plain_text == "Line 1\nLine 2\nLine 3"

    class TestUndoRedoWithLineInfo:
        """undo/redo with line info"""

        def test_should_update_line_info_correctly_after_undo(self):
            buffer, view = make_buffer_and_view("Line 1 content\nLine 2")

            info_before = view.get_line_info()
            assert info_before["start_cols"] == [0, 15]
            assert info_before["width_cols"][0] == 14
            assert info_before["width_cols"][1] == 6

            # Modify the buffer (simulating edit)
            buffer.set_text("Line 1 \nLine 2")

            info_after_modify = view.get_line_info()
            assert info_after_modify["start_cols"] == [0, 8]
            assert info_after_modify["width_cols"][0] == 7

            # Restore original (simulating undo)
            buffer.set_text("Line 1 content\nLine 2")

            info_after_restore = view.get_line_info()
            assert info_after_restore["start_cols"] == [0, 15]
            assert info_after_restore["width_cols"][0] == 14

        def test_should_handle_line_info_correctly_through_multiple_undo_redo_cycles(self):
            buffer, view = make_buffer_and_view("Short\nLine 2")

            info1 = view.get_line_info()
            assert info1["width_cols"][0] == 5

            buffer.set_text("This is a longer line\nLine 2")
            info2 = view.get_line_info()
            assert info2["width_cols"][0] == 21

            buffer.set_text("X\nLine 2")
            info3 = view.get_line_info()
            assert info3["width_cols"][0] == 1

            # Go back to text2 (simulating undo)
            buffer.set_text("This is a longer line\nLine 2")
            info2_again = view.get_line_info()
            assert info2_again["width_cols"][0] == 21

            # Go back to text1 (simulating another undo)
            buffer.set_text("Short\nLine 2")
            info1_again = view.get_line_info()
            assert info1_again["width_cols"][0] == 5

            # Forward to text2 (simulating redo)
            buffer.set_text("This is a longer line\nLine 2")
            info2_redo = view.get_line_info()
            assert info2_redo["width_cols"][0] == 21

        def test_should_correctly_track_line_starts_after_undo_with_multiline_text(self):
            buffer, view = make_buffer_and_view("Line 1 content\nLine 2 content\nLine 3")

            original_info = view.get_line_info()
            assert original_info["start_cols"] == [0, 15, 30]

            buffer.set_text("Line 1 \nLine 2 content\nLine 3")
            modified_info = view.get_line_info()
            assert modified_info["start_cols"] == [0, 8, 23]

            # Restore (undo)
            buffer.set_text("Line 1 content\nLine 2 content\nLine 3")
            restored_info = view.get_line_info()
            assert restored_info["start_cols"] == [0, 15, 30]

    class TestWrappedViewOffsetStability:
        """wrapped view offset stability"""

        def test_should_return_line_info_for_empty_buffer(self):
            buffer, view = make_buffer_and_view("")

            info = view.get_line_info()
            assert info["start_cols"] == [0]
            assert info["width_cols"] == [0]

        def test_should_maintain_stable_char_offsets_with_wide_characters(self):
            text = "A世B界C"  # A(1) 世(2) B(1) 界(2) C(1) = 7 total width
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("char")
            view.set_wrap_width(4)

            info = view.get_line_info()
            assert info["start_cols"][0] == 0
            assert len(info["start_cols"]) > 1

            # Each line should respect wrap width in display columns
            for width in info["width_cols"]:
                assert width <= 4

        def test_should_maintain_stable_selection_with_wrapped_wide_characters(self):
            text = "世界世界世界"  # 6 CJK characters = 12 display width
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("char")
            view.set_wrap_width(6)

            # Select first 3 CJK characters (6 display width)
            view.set_selection(0, 6)
            selected = view.get_selected_text()
            assert selected == "世界世"

        def test_should_handle_tabs_correctly_in_wrapped_view(self):
            text = "A\tB\tC"
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("char")
            view.set_wrap_width(10)

            info = view.get_line_info()
            # Tabs expand to display width, offsets should account for this
            assert len(info["start_cols"]) >= 1

        def test_should_handle_emoji_in_wrapped_view(self):
            text = "\U0001f31f\U0001f31f\U0001f31f\U0001f31f\U0001f31f"  # 5 star emoji = 10 display width
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("char")
            view.set_wrap_width(6)

            info = view.get_line_info()
            assert len(info["start_cols"]) > 1

            # Each wrapped line should respect display width limits
            for width in info["width_cols"]:
                assert width <= 6

        def test_should_maintain_selection_across_wrapped_lines(self):
            text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            buffer, view = make_buffer_and_view(text)

            view.set_wrap_mode("char")
            view.set_wrap_width(10)

            # Select across wrap boundary: chars 8-12 (IJKLM)
            view.set_selection(8, 13)
            selected = view.get_selected_text()
            assert selected == "IJKLM"

    class TestMeasureForDimensions:
        """measureForDimensions"""

        def test_should_measure_without_modifying_cache(self):
            buffer, view = make_buffer_and_view("ABCDEFGHIJKLMNOPQRST")

            view.set_wrap_mode("char")
            view.set_wrap_width(100)  # Large width

            # Measure with different width
            measure_result = view.measure_for_dimensions(10, 10)
            assert measure_result is not None
            assert measure_result["lineCount"] == 2
            assert measure_result["widthColsMax"] == 10

            # Verify cache wasn't modified (should be 1 line with wrap width 100)
            # We can verify via virtual line count
            vlc = view.get_virtual_line_count()
            assert vlc == 1

        def test_should_measure_char_wrap_correctly(self):
            buffer, view = make_buffer_and_view("ABCDEFGHIJKLMNOPQRST")

            view.set_wrap_mode("char")

            # Test different widths
            result1 = view.measure_for_dimensions(10, 10)
            assert result1 is not None
            assert result1["lineCount"] == 2
            assert result1["widthColsMax"] == 10

            result2 = view.measure_for_dimensions(5, 10)
            assert result2 is not None
            assert result2["lineCount"] == 4
            assert result2["widthColsMax"] == 5

            result3 = view.measure_for_dimensions(20, 10)
            assert result3 is not None
            assert result3["lineCount"] == 1
            assert result3["widthColsMax"] == 20

        def test_should_handle_no_wrap_mode(self):
            buffer, view = make_buffer_and_view("Hello\nWorld\nTest")

            view.set_wrap_mode("none")

            result = view.measure_for_dimensions(3, 10)
            assert result is not None
            assert result["lineCount"] == 3
            assert result["widthColsMax"] >= 4

        def test_should_handle_word_wrap(self):
            buffer, view = make_buffer_and_view("Hello wonderful world")

            view.set_wrap_mode("word")

            result = view.measure_for_dimensions(10, 10)
            assert result is not None
            assert result["lineCount"] >= 2
            assert result["widthColsMax"] <= 10

        def test_should_handle_empty_buffer(self):
            buffer, view = make_buffer_and_view("")

            view.set_wrap_mode("char")

            result = view.measure_for_dimensions(10, 10)
            assert result is not None
            assert result["lineCount"] == 1
            assert result["widthColsMax"] == 0

        def test_should_handle_multiple_lines_with_wrapping(self):
            buffer, view = make_buffer_and_view("Short\nAVeryLongLineHere\nMedium")

            view.set_wrap_mode("char")

            result = view.measure_for_dimensions(10, 10)
            assert result is not None
            # "Short" (1), "AVeryLongLineHere" (2), "Medium" (1) = 4 lines
            assert result["lineCount"] == 4
            assert result["widthColsMax"] == 10

        def test_should_cache_measure_results_for_same_width(self):
            buffer, view = make_buffer_and_view("ABCDEFGHIJKLMNOPQRST")

            view.set_wrap_mode("char")

            # First call - cache miss
            result1 = view.measure_for_dimensions(10, 10)
            assert result1 is not None
            assert result1["lineCount"] == 2

            # Second call with same width - should return cached result
            result2 = view.measure_for_dimensions(10, 10)
            assert result2 is not None
            assert result2["lineCount"] == 2
            assert result2["widthColsMax"] == result1["widthColsMax"]

        def test_should_invalidate_cache_when_content_changes(self):
            buffer, view = make_buffer_and_view("ABCDEFGHIJ")

            view.set_wrap_mode("char")

            # Measure with width 5 - should be 2 lines
            result1 = view.measure_for_dimensions(5, 10)
            assert result1["lineCount"] == 2

            # Change content to be longer
            buffer.set_text("ABCDEFGHIJKLMNOPQRST")

            # Same width should now return different result
            result2 = view.measure_for_dimensions(5, 10)
            assert result2["lineCount"] == 4

        def test_should_invalidate_cache_when_wrap_mode_changes(self):
            buffer, view = make_buffer_and_view("Hello world test string here")

            view.set_wrap_mode("word")
            result_word = view.measure_for_dimensions(10, 10)

            view.set_wrap_mode("char")
            result_char = view.measure_for_dimensions(10, 10)

            # Word and char wrap should produce different results
            assert result_word["lineCount"] != result_char["lineCount"]

        def test_should_handle_width_0_for_intrinsic_measurement(self):
            buffer, view = make_buffer_and_view("Hello World")

            view.set_wrap_mode("word")

            # Width 0 means get intrinsic width (no wrapping)
            result = view.measure_for_dimensions(0, 10)
            assert result is not None
            assert result["lineCount"] == 1
            assert result["widthColsMax"] == 11  # "Hello World" = 11 chars
