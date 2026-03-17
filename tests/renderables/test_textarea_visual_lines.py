"""Port of upstream Textarea.visual-lines.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.visual-lines.test.ts
Tests ported: 13/13 (13 real implementations)
"""

from opentui.components.textarea_renderable import TextareaRenderable


# ── Helpers ──────────────────────────────────────────────────────────────


def _make(text="", *, wrap_mode="none", width=80, height=24, **kwargs):
    """Create a focused TextareaRenderable with *text* pre-filled and viewport sized."""
    ta = TextareaRenderable(
        initial_value=text,
        wrap_mode=wrap_mode,
        width=width,
        height=height,
        **kwargs,
    )
    ta._editor_view.set_viewport_size(width, height)
    ta.focus()
    return ta


def _cursor(ta):
    """Return (line, col) cursor position."""
    return ta.cursor_position


# ── Tests ────────────────────────────────────────────────────────────────


class TestTextareaVisualLineNavigationWithoutWrapping:
    """Maps to describe("without wrapping")."""

    def test_goto_visual_line_home_should_go_to_start_of_line(self):
        """Maps to it("goto_visual_line_home should go to start of line")."""
        ta = _make("Hello World", wrap_mode="none", width=40, height=10)
        ta._edit_buffer.set_cursor(0, 6)
        ta.goto_visual_line_home()
        line, col = _cursor(ta)
        assert line == 0
        assert col == 0

    def test_goto_visual_line_end_should_go_to_end_of_line(self):
        """Maps to it("goto_visual_line_end should go to end of line")."""
        ta = _make("Hello World", wrap_mode="none", width=40, height=10)
        ta._edit_buffer.set_cursor(0, 6)
        ta.goto_visual_line_end()
        line, col = _cursor(ta)
        assert line == 0
        assert col == 11

    def test_should_support_selection_with_visual_line_home(self):
        """Maps to it("should support selection with visual line home")."""
        ta = _make("Hello World", width=40, height=10)
        ta._edit_buffer.set_cursor(0, 11)
        ta.goto_visual_line_home(select=True)
        sel = ta.selection
        assert sel is not None
        assert sel[0] == 0
        assert sel[1] == 11
        assert ta.get_selected_text() == "Hello World"

    def test_should_support_selection_with_visual_line_end(self):
        """Maps to it("should support selection with visual line end")."""
        ta = _make("Hello World", width=40, height=10)
        ta._edit_buffer.set_cursor(0, 0)
        ta.goto_visual_line_end(select=True)
        sel = ta.selection
        assert sel is not None
        assert sel[0] == 0
        assert sel[1] == 11
        assert ta.get_selected_text() == "Hello World"


class TestTextareaVisualLineNavigationWithWrapping:
    """Maps to describe("with wrapping")."""

    def test_goto_visual_line_home_should_go_to_start_of_visual_line(self):
        """Maps to it("goto_visual_line_home should go to start of visual line, not logical line")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._edit_buffer.set_cursor(0, 22)
        ta.goto_visual_line_home()
        line, col = _cursor(ta)
        assert line == 0
        assert col == 20

    def test_goto_visual_line_end_should_go_to_end_of_visual_line(self):
        """Maps to it("goto_visual_line_end should go to end of visual line, not logical line")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._edit_buffer.set_cursor(0, 5)
        ta.goto_visual_line_end()
        line, col = _cursor(ta)
        assert line == 0
        assert col == 19

    def test_should_navigate_between_visual_lines_correctly(self):
        """Maps to it("should navigate between visual lines correctly")."""
        ta = _make("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)

        # First visual line
        ta._edit_buffer.set_cursor(0, 10)
        ta.goto_visual_line_home()
        assert _cursor(ta)[1] == 0

        ta.goto_visual_line_end()
        assert _cursor(ta)[1] == 19

        # Move to second visual line
        ta._edit_buffer.move_cursor_right()

        ta.goto_visual_line_home()
        assert _cursor(ta)[1] == 20

        ta.goto_visual_line_end()
        col = _cursor(ta)[1]
        assert col > 20

    def test_should_handle_word_wrapping_correctly(self):
        """Maps to it("should handle word wrapping correctly")."""
        ta = _make("Hello wonderful world of wrapped text", wrap_mode="word", width=20, height=10)
        ta._edit_buffer.set_cursor(0, 25)

        vc = ta._editor_view.get_visual_cursor()
        assert vc.visual_row > 0

        ta.goto_visual_line_home()
        sol_col = _cursor(ta)[1]
        assert sol_col > 0

        ta.goto_visual_line_end()
        eol_col = _cursor(ta)[1]
        assert eol_col < 37

    def test_should_select_within_visual_line_boundaries(self):
        """Maps to it("should select within visual line boundaries")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._edit_buffer.set_cursor(0, 10)

        ta.goto_visual_line_end(select=True)

        selected = ta.get_selected_text()
        assert selected == "KLMNOPQRS"
        assert len(selected) == 9


class TestTextareaVisualLineNavigationMultiByteCharacters:
    """Maps to describe("with multi-byte characters")."""

    def test_should_handle_wrapped_emoji_correctly(self):
        """Maps to it("should handle wrapped emoji correctly")."""
        # Each star emoji is 2 display columns wide. With width=15,
        # we can fit 7 emoji (14 cols) on the first visual line.
        ta = _make(
            "\U0001f31f\U0001f31f\U0001f31f\U0001f31f\U0001f31f"
            "\U0001f31f\U0001f31f\U0001f31f\U0001f31f\U0001f31f",
            wrap_mode="char",
            width=15,
            height=10,
        )

        # First visual line - cursor at display col 2 (after first emoji)
        ta._edit_buffer.set_cursor(0, 2)
        ta.goto_visual_line_home()
        assert _cursor(ta)[1] == 0

        ta.goto_visual_line_end()
        first_line_end = _cursor(ta)[1]
        assert first_line_end > 0
        assert first_line_end < 20

        # Move to second visual line - set cursor past first visual line
        ta._edit_buffer.set_cursor(0, 16)
        vc = ta._editor_view.get_visual_cursor()

        # Only test visual line navigation if we actually moved to second visual line
        if vc.visual_row > 0:
            ta.goto_visual_line_home()
            second_line_start = _cursor(ta)[1]
            assert second_line_start >= first_line_end - 1


class TestTextareaVisualLineComparisonWithLogical:
    """Maps to describe("comparison with logical line navigation")."""

    def test_visual_home_should_differ_from_logical_home_when_wrapped(self):
        """Maps to it("visual home should differ from logical home when wrapped")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._edit_buffer.set_cursor(0, 22)

        ta.goto_visual_line_home()
        visual_home_col = _cursor(ta)[1]
        assert visual_home_col == 20

        ta._edit_buffer.set_cursor(0, 22)
        # goto_line_home when not at col 0 goes to col 0 of current line
        ta.goto_line_home()
        logical_home_col = _cursor(ta)[1]
        assert logical_home_col == 0

        assert visual_home_col != logical_home_col

    def test_visual_end_should_differ_from_logical_end_when_wrapped(self):
        """Maps to it("visual end should differ from logical end when wrapped")."""
        ta = _make("ABCDEFGHIJKLMNOPQRSTUVWXYZ", wrap_mode="char", width=20, height=10)
        ta._edit_buffer.set_cursor(0, 5)

        ta.goto_visual_line_end()
        visual_end_col = _cursor(ta)[1]
        assert visual_end_col == 19

        ta._edit_buffer.set_cursor(0, 5)
        # goto_line_end when not at end goes to end of logical line (col 26)
        ta.goto_line_end()
        logical_end_col = _cursor(ta)[1]
        assert logical_end_col == 26

        assert visual_end_col != logical_end_col

    def test_without_wrapping_visual_and_logical_should_be_the_same(self):
        """Maps to it("without wrapping, visual and logical should be the same")."""
        ta = _make("Hello World", wrap_mode="none", width=40, height=10)

        # Test home
        ta._edit_buffer.set_cursor(0, 6)
        ta.goto_visual_line_home()
        visual_home_col = _cursor(ta)[1]

        ta._edit_buffer.set_cursor(0, 6)
        ta.goto_line_home()
        logical_home_col = _cursor(ta)[1]

        assert visual_home_col == logical_home_col

        # Test end
        ta._edit_buffer.set_cursor(0, 6)
        ta.goto_visual_line_end()
        visual_end_col = _cursor(ta)[1]

        ta._edit_buffer.set_cursor(0, 6)
        ta.goto_line_end()
        logical_end_col = _cursor(ta)[1]

        assert visual_end_col == logical_end_col
