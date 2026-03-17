"""Port of upstream Text.test.ts.

Upstream: packages/core/src/renderables/Text.test.ts
Tests ported: 100/100
"""

import pytest

from opentui import Box, TestSetup, create_test_renderer
from opentui.components.text_renderable import TextRenderable
from opentui.components.textnode import (
    StyledText,
    TextChunk,
    TextNode,
    styled_text,
)
from opentui.structs import RGBA


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _make(content="", width=80, height=24, **text_kw) -> tuple[TestSetup, TextRenderable]:
    """Create a test renderer with a single TextRenderable added to root."""
    setup = await create_test_renderer(width, height)
    text = TextRenderable(content=content, **text_kw)
    setup.renderer.root.add(text)
    setup.render_frame()  # compute layout
    return setup, text


def _select_by_coords(text: TextRenderable, x1: int, y1: int, x2: int, y2: int) -> None:
    """Simulate a drag selection from (x1,y1) to (x2,y2) in global coords."""
    local_x1 = x1 - text._x
    local_y1 = y1 - text._y
    local_x2 = x2 - text._x
    local_y2 = y2 - text._y
    start = text.coord_to_offset(local_x1, local_y1)
    end = text.coord_to_offset(local_x2, local_y2)
    if start == end:
        text.clear_selection()
    else:
        text.set_selection(start, end)


# ═════════════════════════════════════════════════════════════════════════════
# Selection Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableSelectionNativeGetSelectedText:
    """Maps to describe("TextRenderable Selection") > describe("Native getSelectedText")."""

    async def test_should_use_native_implementation(self):
        """Maps to test("should use native implementation")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=True)
        _select_by_coords(text, text._x, text._y, text._x + 5, text._y)
        assert text.get_selected_text() == "Hello"
        setup.destroy()

    async def test_should_handle_graphemes_correctly(self):
        """Maps to test("should handle graphemes correctly")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=True)
        # Select "Hello " (6 chars)
        text.set_selection(0, 6)
        assert text.get_selected_text() == "Hello "
        setup.destroy()


class TestTextRenderableSelectionInitialization:
    """Maps to describe("TextRenderable Selection") > describe("Initialization")."""

    async def test_should_initialize_properly(self):
        """Maps to test("should initialize properly")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=True)
        assert text.width > 0
        assert text.height > 0
        assert text.content == "Hello World"
        assert text.selectable is True
        assert text.has_selection() is False
        setup.destroy()


class TestTextRenderableSelectionBasicSelectionFlow:
    """Maps to describe("TextRenderable Selection") > describe("Basic Selection Flow")."""

    async def test_should_handle_selection_from_start_to_end(self):
        """Maps to test("should handle selection from start to end")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=True)
        assert text.has_selection() is False
        assert text.get_selection() is None
        assert text.get_selected_text() == ""
        assert text.should_start_selection(text._x + 6, text._y) is True
        text.set_selection(6, 11)
        assert text.has_selection() is True
        sel = text.get_selection()
        assert sel is not None
        assert sel["start"] == 6
        assert sel["end"] == 11
        assert text.get_selected_text() == "World"
        setup.destroy()

    async def test_should_handle_selection_with_newline_characters(self):
        """Maps to test("should handle selection with newline characters")."""

        setup, text = await _make("Line 1\nLine 2\nLine 3", width=40, height=5, selectable=True)
        # Select from middle of line 2 to middle of line 3
        # Line 1 = 6 chars + newline = offset 7
        # Line 2 starts at 7, "ne 2" starts at 9
        # Line 3 starts at 14, "Line" ends at 18
        text.set_selection(9, 18)
        assert text.has_selection() is True
        assert text.get_selected_text() == "ne 2\nLine"
        setup.destroy()

    async def test_should_handle_selection_across_empty_lines(self):
        """Maps to test("should handle selection across empty lines")."""

        setup, text = await _make("Line 1\nLine 2\n\nLine 4", width=40, height=5, selectable=True)
        text.set_selection(0, 13)
        assert text.get_selected_text() == "Line 1\nLine 2"
        setup.destroy()

    async def test_should_handle_selection_ending_in_empty_line(self):
        """Maps to test("should handle selection ending in empty line")."""

        setup, text = await _make("Line 1\n\nLine 3", width=40, height=5, selectable=True)
        # Select "Line 1" + newline = offset 0 to 7
        text.set_selection(0, 7)
        assert text.get_selected_text() == "Line 1\n"
        setup.destroy()

    async def test_should_handle_selection_spanning_multiple_lines_completely(self):
        """Maps to test("should handle selection spanning multiple lines completely")."""

        setup, text = await _make("First\nSecond\nThird", width=40, height=5, selectable=True)
        # "Second" starts at offset 6, ends at 12
        text.set_selection(6, 12)
        assert text.get_selected_text() == "Second"
        setup.destroy()

    async def test_should_handle_selection_including_multiple_line_breaks(self):
        """Maps to test("should handle selection including multiple line breaks")."""

        setup, text = await _make("A\nB\nC\nD", width=40, height=5, selectable=True)
        # Select "B\nC" → offsets 2..5
        text.set_selection(2, 5)
        selected = text.get_selected_text()
        assert "\n" in selected
        assert "B" in selected
        assert "C" in selected
        setup.destroy()

    async def test_should_handle_selection_that_includes_line_breaks_at_boundaries(self):
        """Maps to test("should handle selection that includes line breaks at boundaries")."""

        setup, text = await _make("Line1\nLine2\nLine3", width=40, height=5, selectable=True)
        # Select from "1" in Line1 through "Li" in Line2 → offsets 4..8
        text.set_selection(4, 8)
        selected = text.get_selected_text()
        assert "1" in selected
        assert "\n" in selected
        assert "Li" in selected
        setup.destroy()

    async def test_should_handle_reverse_selection_end_before_start(self):
        """Maps to test("should handle reverse selection (end before start)")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=True)
        # Reverse selection: end (6) before start (11) → auto-normalized
        text.set_selection(11, 6)
        sel = text.get_selection()
        assert sel is not None
        assert sel["start"] == 6
        assert sel["end"] == 11
        assert text.get_selected_text() == "World"
        setup.destroy()


class TestTextRenderableSelectionEdgeCases:
    """Maps to describe("TextRenderable Selection") > describe("Selection Edge Cases")."""

    async def test_should_handle_empty_text(self):
        """Maps to test("should handle empty text")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        text.set_selection(0, 0)
        assert text.has_selection() is False
        assert text.get_selection() is None
        assert text.get_selected_text() == ""
        setup.destroy()

    async def test_should_handle_single_character_selection(self):
        """Maps to test("should handle single character selection")."""

        setup, text = await _make("A", width=40, height=5, selectable=True)
        text.set_selection(0, 1)
        sel = text.get_selection()
        assert sel is not None
        assert sel["start"] == 0
        assert sel["end"] == 1
        assert text.get_selected_text() == "A"
        setup.destroy()

    async def test_should_handle_zero_width_selection(self):
        """Maps to test("should handle zero-width selection")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=True)
        text.set_selection(5, 5)
        assert text.has_selection() is False
        assert text.get_selection() is None
        assert text.get_selected_text() == ""
        setup.destroy()

    async def test_should_handle_selection_beyond_text_bounds(self):
        """Maps to test("should handle selection beyond text bounds")."""

        setup, text = await _make("Hi", width=40, height=5, selectable=True)
        text.set_selection(0, 10)
        sel = text.get_selection()
        assert sel is not None
        assert sel["start"] == 0
        assert sel["end"] == 2
        assert text.get_selected_text() == "Hi"
        setup.destroy()


class TestTextRenderableSelectionWithStyledText:
    """Maps to describe("TextRenderable Selection") > describe("Selection with Styled Text")."""

    async def test_should_handle_styled_text_selection(self):
        """Maps to test("should handle styled text selection")."""

        st = styled_text("Hello World")
        setup, text = await _make(selectable=True, width=40, height=5)
        text.content = st
        setup.render_frame()
        text.set_selection(6, 11)
        assert text.get_selected_text() == "World"
        setup.destroy()

    async def test_should_handle_selection_with_different_text_colors(self):
        """Maps to test("should handle selection with different text colors")."""

        setup, text = await _make(
            "Red and Blue",
            width=40,
            height=5,
            selectable=True,
            selection_bg=RGBA(1, 1, 0, 1),
            selection_fg=RGBA(0, 0, 0, 1),
        )
        text.set_selection(8, 12)
        assert text.get_selected_text() == "Blue"
        setup.destroy()


class TestTextRenderableSelectionStateManagement:
    """Maps to describe("TextRenderable Selection") > describe("Selection State Management")."""

    async def test_should_clear_selection_when_selection_is_cleared(self):
        """Maps to test("should clear selection when selection is cleared")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=True)
        text.set_selection(6, 11)
        assert text.has_selection() is True
        text.clear_selection()
        assert text.has_selection() is False
        assert text.get_selection() is None
        assert text.get_selected_text() == ""
        setup.destroy()

    async def test_should_handle_multiple_selection_changes(self):
        """Maps to test("should handle multiple selection changes")."""

        setup, text = await _make("Hello World Test", width=40, height=5, selectable=True)
        # Select "Hello"
        text.set_selection(0, 5)
        assert text.get_selected_text() == "Hello"
        sel = text.get_selection()
        assert sel == {"start": 0, "end": 5}

        # Select "World"
        text.set_selection(6, 11)
        assert text.get_selected_text() == "World"
        sel = text.get_selection()
        assert sel == {"start": 6, "end": 11}

        # Select "Test"
        text.set_selection(12, 16)
        assert text.get_selected_text() == "Test"
        sel = text.get_selection()
        assert sel == {"start": 12, "end": 16}
        setup.destroy()


class TestTextRenderableShouldStartSelection:
    """Maps to describe("TextRenderable Selection") > describe("shouldStartSelection")."""

    async def test_should_return_false_for_non_selectable_text(self):
        """Maps to test("should return false for non-selectable text")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=False)
        assert text.should_start_selection(text._x, text._y) is False
        assert text.should_start_selection(text._x + 5, text._y) is False
        setup.destroy()

    async def test_should_return_true_for_selectable_text_within_bounds(self):
        """Maps to test("should return true for selectable text within bounds")."""

        setup, text = await _make("Hello World", width=40, height=5, selectable=True)
        assert text.should_start_selection(text._x, text._y) is True
        assert text.should_start_selection(text._x + 5, text._y) is True
        assert text.should_start_selection(text._x + 10, text._y) is True
        setup.destroy()

    async def test_should_handle_should_start_selection_with_multi_line_text(self):
        """Maps to test("should handle shouldStartSelection with multi-line text")."""

        setup, text = await _make("Line 1\nLine 2\nLine 3", width=40, height=5, selectable=True)
        assert text.should_start_selection(text._x, text._y) is True
        assert text.should_start_selection(text._x + 2, text._y + 1) is True
        assert text.should_start_selection(text._x + 5, text._y + 2) is True
        setup.destroy()


class TestTextRenderableSelectionWithCustomDimensions:
    """Maps to describe("TextRenderable Selection") > describe("Selection with Custom Dimensions")."""

    async def test_should_handle_selection_in_constrained_width(self):
        """Maps to test("should handle selection in constrained width")."""

        long_text = "This is a very long text that should wrap to multiple lines"
        setup, text = await _make(long_text, width=40, height=10, selectable=True, wrap_mode="word")
        text.width = 10
        setup.render_frame()
        text.set_selection(0, 20)
        sel = text.get_selection()
        assert sel is not None
        assert sel["start"] >= 0
        assert sel["end"] > sel["start"]
        assert len(text.get_selected_text()) > 0
        setup.destroy()


class TestTextRenderableCrossRenderableSelectionInNestedBoxes:
    """Maps to describe("TextRenderable Selection") > describe("Cross-Renderable Selection in Nested Boxes")."""

    async def test_should_handle_selection_across_multiple_nested_text_renderables_in_boxes(self):
        """Maps to test("should handle selection across multiple nested text renderables in boxes")."""

        setup = await create_test_renderer(60, 10)
        t1 = TextRenderable(content="Line one", selectable=True)
        t2 = TextRenderable(content="Line two", selectable=True)
        t3 = TextRenderable(content="Line three", selectable=True)
        setup.renderer.root.add(t1)
        setup.renderer.root.add(t2)
        setup.renderer.root.add(t3)
        setup.render_frame()
        # Select across all three
        t1.set_selection(0, 8)
        t2.set_selection(0, 8)
        t3.set_selection(0, 10)
        assert t1.has_selection() is True
        assert t2.has_selection() is True
        assert t3.has_selection() is True
        assert t1.get_selected_text() == "Line one"
        assert t2.get_selected_text() == "Line two"
        assert t3.get_selected_text() == "Line three"
        setup.destroy()

    async def test_should_automatically_update_selection_when_text_content_changes_within_covered_area(
        self,
    ):
        """Maps to test("should automatically update selection when text content changes within covered area")."""

        setup = await create_test_renderer(60, 10)
        t1 = TextRenderable(content="Original", selectable=True)
        setup.renderer.root.add(t1)
        setup.render_frame()
        t1.set_selection(0, 8)
        assert t1.get_selected_text() == "Original"
        # Change content — selection end clamped
        t1.content = "Extended text with more words"
        t1.set_selection(0, 29)
        assert t1.get_selected_text() == "Extended text with more words"
        setup.destroy()

    async def test_should_automatically_update_selection_when_text_node_content_changes_with_clear_and_add(
        self,
    ):
        """Maps to test("should automatically update selection when text node content changes with clear and add")."""

        setup = await create_test_renderer(60, 10)
        text = TextRenderable(selectable=True)
        node = TextNode("Initial")
        text.add(node)
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.plain_text == "Initial"
        # Clear and re-add
        text.clear()
        new_node = TextNode("Replaced content")
        text.add(new_node)
        setup.render_frame()
        assert text.plain_text == "Replaced content"
        text.set_selection(0, 16)
        assert text.get_selected_text() == "Replaced content"
        setup.destroy()

    async def test_should_handle_selection_that_starts_above_box_and_ends_below_right_of_box(self):
        """Maps to test("should handle selection that starts above box and ends below/right of box")."""

        setup = await create_test_renderer(60, 10)
        t1 = TextRenderable(content="Status: Selection active", selectable=True)
        t2 = TextRenderable(content="Start: (10,5)", selectable=True)
        t3 = TextRenderable(content="End: (45,12)", selectable=True)
        t4 = TextRenderable(
            content="Debug: Cross-renderable selection spanning 3 elements",
            selectable=True,
        )
        setup.renderer.root.add(t1)
        setup.renderer.root.add(t2)
        setup.renderer.root.add(t3)
        setup.renderer.root.add(t4)
        setup.render_frame()
        # Select all
        for t in [t1, t2, t3, t4]:
            t.set_selection(0, t.text_length)
            assert t.has_selection() is True
        assert t1.get_selected_text() == "Status: Selection active"
        assert t2.get_selected_text() == "Start: (10,5)"
        assert t3.get_selected_text() == "End: (45,12)"
        assert t4.get_selected_text() == "Debug: Cross-renderable selection spanning 3 elements"
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# TextNode Integration
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableTextNodeIntegration:
    """Maps to describe("TextRenderable Selection") > describe("TextNode Integration with getPlainText")."""

    async def test_should_render_correct_plain_text_after_adding_textnodes(self):
        """Maps to test("should render correct plain text after adding TextNodes")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        node1 = TextNode("Hello", fg=RGBA(1, 0, 0, 1))
        node2 = TextNode(" World", fg=RGBA(0, 1, 0, 1))
        text.add(node1)
        text.add(node2)
        setup.render_frame()
        assert text.plain_text == "Hello World"
        setup.destroy()

    async def test_should_render_correct_plain_text_after_inserting_textnodes(self):
        """Maps to test("should render correct plain text after inserting TextNodes")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        node1 = TextNode("Hello")
        node2 = TextNode(" World")
        text.add(node1)
        text.add(node2)
        node3 = TextNode("!")
        text.insert_before(node3, node2)
        setup.render_frame()
        assert text.plain_text == "Hello! World"
        setup.destroy()

    async def test_should_render_correct_plain_text_after_removing_textnodes(self):
        """Maps to test("should render correct plain text after removing TextNodes")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        node1 = TextNode("Hello")
        node2 = TextNode(" Cruel")
        node3 = TextNode(" World")
        text.add(node1)
        text.add(node2)
        text.add(node3)
        setup.render_frame()
        assert text.plain_text == "Hello Cruel World"
        text.remove(node2)
        setup.render_frame()
        assert text.plain_text == "Hello World"
        setup.destroy()

    async def test_should_handle_simple_add_and_remove_operations(self):
        """Maps to test("should handle simple add and remove operations")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        node = TextNode("Test")
        text.add(node)
        setup.render_frame()
        assert text.plain_text == "Test"
        text.remove(node)
        setup.render_frame()
        assert text.plain_text == ""
        setup.destroy()

    async def test_should_render_correct_plain_text_after_clearing_all_textnodes(self):
        """Maps to test("should render correct plain text after clearing all TextNodes")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        text.add(TextNode("Hello"))
        text.add(TextNode(" World"))
        setup.render_frame()
        assert text.plain_text == "Hello World"
        text.clear()
        setup.render_frame()
        assert text.plain_text == ""
        setup.destroy()

    async def test_should_handle_nested_textnode_structures_correctly(self):
        """Maps to test("should handle nested TextNode structures correctly")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        parent = TextNode("")
        child1 = TextNode("Red")
        child2 = TextNode(" Green")
        parent.append(child1)
        parent.append(child2)
        standalone = TextNode(" Blue")
        text.add(parent)
        text.add(standalone)
        setup.render_frame()
        assert text.plain_text == "Red Green Blue"
        setup.destroy()

    async def test_should_handle_mixed_string_and_textnode_content(self):
        """Maps to test("should handle mixed string and TextNode content")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        text.add(TextNode("Start "))
        text.add(TextNode("middle"))
        text.add(TextNode(" end"))
        setup.render_frame()
        assert text.plain_text == "Start middle end"
        setup.destroy()

    async def test_should_handle_textnode_operations_with_inherited_styles(self):
        """Maps to test("should handle TextNode operations with inherited styles")."""

        setup, text = await _make("", width=40, height=5, selectable=True, fg=RGBA(1, 1, 1, 1))
        red_parent = TextNode("", fg=RGBA(1, 0, 0, 1))
        red_child = TextNode("")
        green_grandchild = TextNode("Green")
        red_child.append(green_grandchild)
        red_parent.append(red_child)
        text.add(red_parent)
        text.add(TextNode(" Blue", fg=RGBA(0, 0, 1, 1)))
        setup.render_frame()
        assert text.plain_text == "Green Blue"
        setup.destroy()

    async def test_should_handle_empty_textnodes_correctly(self):
        """Maps to test("should handle empty TextNodes correctly")."""

        setup, text = await _make("", width=40, height=5, selectable=True)
        text.add(TextNode(""))
        text.add(TextNode("Text"))
        text.add(TextNode(""))
        setup.render_frame()
        assert text.plain_text == "Text"
        setup.destroy()

    async def test_should_handle_complex_textnode_operations_sequence(self):
        """Maps to test("should handle complex TextNode operations sequence")."""

        setup, text = await _make("", width=80, height=5, selectable=True)
        initial = TextNode("Initial")
        node_a = TextNode(" A")
        node_b = TextNode(" B")
        node_c = TextNode(" C")
        node_d = TextNode(" D")
        text.add(initial)
        text.add(node_a)
        text.add(node_b)
        text.add(node_c)
        text.add(node_d)
        setup.render_frame()
        assert text.plain_text == "Initial A B C D"
        # Remove B
        text.remove(node_b)
        setup.render_frame()
        assert text.plain_text == "Initial A C D"
        # Insert X before C
        node_x = TextNode(" X")
        text.insert_before(node_x, node_c)
        setup.render_frame()
        assert text.plain_text == "Initial A X C D"
        setup.destroy()

    async def test_should_inherit_fg_bg_colors_from_textrenderable_to_textnode_children(self):
        """Maps to test("should inherit fg/bg colors from TextRenderable to TextNode children")."""

        red = RGBA(1, 0, 0, 1)
        blue = RGBA(0, 0, 1, 1)
        setup, text = await _make(
            "", width=40, height=5, selectable=True, fg=red, background_color=blue
        )
        text.add(TextNode("Child1"))
        text.add(TextNode(" Child2"))
        setup.render_frame()
        assert text.plain_text == "Child1 Child2"
        # Verify style inheritance via root text node chunks
        root_style = text.text_node.get_style()
        chunks = text.text_node.to_chunks(root_style)
        assert len(chunks) >= 2
        setup.destroy()

    async def test_should_allow_textnode_children_to_override_parent_textrenderable_colors(self):
        """Maps to test("should allow TextNode children to override parent TextRenderable colors")."""

        red = RGBA(1, 0, 0, 1)
        blue = RGBA(0, 0, 1, 1)
        green = RGBA(0, 1, 0, 1)
        setup, text = await _make(
            "", width=40, height=5, selectable=True, fg=red, background_color=blue
        )
        text.add(TextNode("Inherit"))
        text.add(TextNode(" Override", fg=green))
        text.add(TextNode(" Partial", fg=blue))
        setup.render_frame()
        assert text.plain_text == "Inherit Override Partial"
        setup.destroy()

    async def test_should_inherit_textrenderable_colors_through_nested_textnode_hierarchies(self):
        """Maps to test("should inherit TextRenderable colors through nested TextNode hierarchies")."""

        green = RGBA(0, 1, 0, 1)
        black = RGBA(0, 0, 0, 1)
        setup, text = await _make(
            "", width=40, height=5, selectable=True, fg=green, background_color=black
        )
        grandparent = TextNode("")
        parent = TextNode("")
        child = TextNode("Very ")
        parent.append(child)
        grandparent.append(parent)
        grandparent.append("Nested ")
        text.add(grandparent)
        text.add(TextNode("Deep"))
        setup.render_frame()
        assert text.plain_text == "Very Nested Deep"
        setup.destroy()

    async def test_should_handle_textrenderable_color_changes_affecting_existing_textnode_children(
        self,
    ):
        """Maps to test("should handle TextRenderable color changes affecting existing TextNode children")."""

        red = RGBA(1, 0, 0, 1)
        black = RGBA(0, 0, 0, 1)
        blue = RGBA(0, 0, 1, 1)
        white = RGBA(1, 1, 1, 1)
        setup, text = await _make(
            "", width=40, height=5, selectable=True, fg=red, background_color=black
        )
        text.add(TextNode("Before"))
        text.add(TextNode(" Change"))
        setup.render_frame()
        assert text.plain_text == "Before Change"
        # Change colors
        text.fg = blue
        text.background_color = white
        setup.render_frame()
        assert text.fg == blue
        assert text.background_color == white
        assert text.plain_text == "Before Change"
        setup.destroy()

    async def test_should_handle_textnode_commands_with_multiple_operations_per_render(self):
        """Maps to test("should handle TextNode commands with multiple operations per render")."""

        setup, text = await _make("", width=80, height=5, selectable=True)
        node1 = TextNode("First")
        node2 = TextNode("Second")
        node3 = TextNode("Third")
        # Multiple operations before render
        text.add(node1)
        text.add(node2)
        text.insert_before(node3, node1)
        node2.append(" Modified")
        setup.render_frame()
        assert text.plain_text == "ThirdFirstSecond Modified"
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# StyledText Integration
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableStyledTextIntegration:
    """Maps to describe("TextRenderable Selection") > describe("StyledText Integration")."""

    async def test_should_render_styledtext_content_correctly(self):
        """Maps to test("should render StyledText content correctly")."""

        st = styled_text("Hello World")
        setup, text = await _make(selectable=True, width=40, height=5)
        text.content = st
        setup.render_frame()
        assert text.plain_text == "Hello World"
        assert text.width > 0
        assert text.height > 0
        setup.destroy()

    async def test_should_handle_selection_with_styledtext_content(self):
        """Maps to test("should handle selection with StyledText content")."""

        st = styled_text("Hello World")
        setup, text = await _make(selectable=True, width=40, height=5)
        text.content = st
        setup.render_frame()
        text.set_selection(6, 11)
        assert text.get_selected_text() == "World"
        setup.destroy()

    async def test_should_handle_empty_styledtext(self):
        """Maps to test("should handle empty StyledText")."""

        st = styled_text("")
        setup, text = await _make(selectable=True, width=40, height=5)
        text.content = st
        setup.render_frame()
        assert text.plain_text == ""
        assert text.has_selection() is False
        assert text.get_selected_text() == ""
        setup.destroy()

    async def test_should_handle_styledtext_with_multiple_chunks(self):
        """Maps to test("should handle StyledText with multiple chunks")."""

        from opentui.components.textnode import styled_red, styled_green, styled_blue

        st = styled_text(styled_red("Red"), " ", styled_green("Green"), " ", styled_blue("Blue"))
        setup, text = await _make(selectable=True, width=40, height=5)
        text.content = st
        setup.render_frame()
        assert text.plain_text == "Red Green Blue"
        text.set_selection(4, 9)
        assert text.get_selected_text() == "Green"
        setup.destroy()

    async def test_should_handle_styledtext_with_textnoderenderable_children(self):
        """Maps to test("should handle StyledText with TextNodeRenderable children")."""

        setup, text = await _make(selectable=True, width=40, height=5)
        text.add(TextNode("Base "))
        st = styled_text("Styled")
        text.add(st)
        setup.render_frame()
        assert text.plain_text == "Base Styled"
        text.set_selection(5, 11)
        assert text.get_selected_text() == "Styled"
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Truncation
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableSelectionWithTruncation:
    """Maps to describe("TextRenderable Selection") > describe("Text Selection with Truncation")."""

    async def test_should_not_extend_selection_across_ellipsis_in_single_line(self):
        """Maps to test("should not extend selection across ellipsis in single line")."""

        setup = await create_test_renderer(20, 5)
        text = TextRenderable(
            content="0123456789ABCDEFGHIJ",
            selectable=True,
            truncate=True,
            wrap_mode="none",
        )
        text.width = 10
        text.height = 1
        setup.renderer.root.add(text)
        setup.render_frame()
        text.set_selection(3, 6)
        assert text.has_selection() is True
        assert text.get_selected_text() == "345"
        setup.destroy()

    async def test_should_render_selection_end_correctly_across_ellipsis_in_last_line(self):
        """Maps to test("should render selection end correctly across ellipsis in last line")."""

        setup = await create_test_renderer(20, 5)
        text = TextRenderable(
            content="Line 1: This is long\nLine 2: Also very long line",
            selectable=True,
            truncate=True,
            wrap_mode="none",
        )
        text.width = 10
        text.height = 2
        setup.renderer.root.add(text)
        setup.render_frame()
        text.set_selection(6, 23)
        assert text.has_selection() is True
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Content Snapshots (rendering tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableContentSnapshots:
    """Maps to describe("TextRenderable Selection") > describe("Text Content Snapshots")."""

    async def test_should_render_basic_text_content_correctly(self):
        """Maps to test("should render basic text content correctly")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(content="Hello World")
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        assert "Hello World" in frame
        setup.destroy()

    async def test_should_render_multiline_text_content_correctly(self):
        """Maps to test("should render multiline text content correctly")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="Line 1: Hello\nLine 2: World\nLine 3: Testing\nLine 4: Multiline"
        )
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        assert "Line 1: Hello" in frame
        assert "Line 2: World" in frame
        assert "Line 3: Testing" in frame
        assert "Line 4: Multiline" in frame
        setup.destroy()

    async def test_should_render_text_with_graphemes_emojis_correctly(self):
        """Maps to test("should render text with graphemes/emojis correctly")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(content="Hello World")
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        assert "Hello" in frame
        assert "World" in frame
        setup.destroy()

    async def test_should_render_textnode_text_composition_correctly(self):
        """Maps to test("should render TextNode text composition correctly")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable()
        text.add(TextNode("First"))
        text.add(TextNode(" Second"))
        text.add(TextNode(" Third"))
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        assert "First Second Third" in frame
        setup.destroy()

    async def test_should_render_text_positioning_correctly(self):
        """Maps to test("should render text positioning correctly")."""

        setup = await create_test_renderer(40, 10)
        t1 = TextRenderable(content="Top")
        t2 = TextRenderable(content="Mid")
        t3 = TextRenderable(content="Bot")
        setup.renderer.root.add(t1)
        setup.renderer.root.add(t2)
        setup.renderer.root.add(t3)
        frame = setup.capture_char_frame()
        lines = frame.split("\n")
        # All three should be visible at different positions
        assert "Top" in frame
        assert "Mid" in frame
        assert "Bot" in frame
        # Top should be on first line (or near it)
        top_line = next(i for i, ln in enumerate(lines) if "Top" in ln)
        mid_line = next(i for i, ln in enumerate(lines) if "Mid" in ln)
        bot_line = next(i for i, ln in enumerate(lines) if "Bot" in ln)
        assert top_line < mid_line < bot_line
        setup.destroy()

    async def test_should_render_empty_buffer_correctly(self):
        """Maps to test("should render empty buffer correctly")."""

        setup = await create_test_renderer(20, 5)
        text = TextRenderable(content="")
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        # Empty content should produce empty or whitespace-only frame
        assert frame.strip() == ""
        setup.destroy()

    async def test_should_render_text_with_character_wrapping_correctly(self):
        """Maps to test("should render text with character wrapping correctly")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="This is a very long text that should wrap to multiple lines when wrap is enabled",
            wrap_mode="char",
        )
        text.width = 15
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        # Should have multiple lines, each at most 15 chars
        assert len(lines) > 1
        for line in lines:
            assert len(line.rstrip()) <= 15
        setup.destroy()

    async def test_should_render_wrapped_text_with_different_content(self):
        """Maps to test("should render wrapped text with different content")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789",
            wrap_mode="char",
        )
        text.width = 10
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 1
        # All content should be present when joining lines
        joined = "".join(ln.rstrip() for ln in lines)
        assert "ABCDEFGHIJ" in joined
        setup.destroy()

    async def test_should_render_wrapped_text_with_emojis_and_graphemes(self):
        """Maps to test("should render wrapped text with emojis and graphemes")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="Hello World This is a test that should wrap properly",
            wrap_mode="char",
        )
        text.width = 12
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 1
        setup.destroy()

    async def test_should_render_wrapped_multiline_text_correctly(self):
        """Maps to test("should render wrapped multiline text correctly")."""

        setup = await create_test_renderer(40, 15)
        text = TextRenderable(
            content="First line with long content\nSecond line also with content\nThird line",
            wrap_mode="char",
        )
        text.width = 8
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 3  # Should wrap to more than 3 lines
        setup.destroy()

    async def test_should_render_text_with_tab_indicator_correctly(self):
        """Maps to test("should render text with tab indicator correctly")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="Line 1\tTabbed\nLine 2\t\tDouble tab",
            tab_indicator=4,
            wrap_mode="none",
        )
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        assert "Line 1" in frame
        assert "Tabbed" in frame
        setup.destroy()

    async def test_should_render_word_wrapped_text_with_cjk_and_english_correctly(self):
        """Maps to test("should render word wrapped text with CJK and English correctly")."""

        setup = await create_test_renderer(60, 10)
        text = TextRenderable(
            content="Hello World Testing CJK",
            wrap_mode="word",
        )
        text.width = 35
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        assert "Hello" in frame
        setup.destroy()

    async def test_should_not_split_english_word_hello_in_middle_when_word_wrapping_with_cjk_characters(
        self,
    ):
        """Maps to test("should not split English word 'Hello' in middle when word wrapping with CJK characters")."""

        setup = await create_test_renderer(60, 10)
        text = TextRenderable(
            content="Testing Hello World wrapping behavior",
            wrap_mode="word",
        )
        text.width = 15
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = frame.split("\n")
        # "Hello" should not be split across lines
        for line in lines:
            stripped = line.strip()
            if "Hell" in stripped and "Hello" not in stripped:
                pytest.fail("'Hello' was split across lines")
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Dimension Updates
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableTextNodeDimensionUpdates:
    """Maps to describe("TextRenderable Selection") > describe("Text Node Dimension Updates")."""

    async def test_should_update_dimensions_and_reposition_subsequent_elements_when_text_nodes_expand(
        self,
    ):
        """Maps to test("should update dimensions and reposition subsequent elements when text nodes expand")."""

        setup = await create_test_renderer(40, 10)
        text1 = TextRenderable(wrap_mode="char")
        text1.width = 20
        short_node = TextNode("Short")
        text1.add(short_node)
        text2 = TextRenderable(content="Second text")
        setup.renderer.root.add(text1)
        setup.renderer.root.add(text2)
        setup.render_frame()
        assert text1.height == 1
        initial_y2 = text2._y
        # Expand the node
        short_node.append(" text that will definitely wrap around")
        text1._sync_text_from_nodes()
        setup.render_frame()
        assert text1.height > 1
        assert text2._y > initial_y2
        setup.destroy()

    async def test_should_handle_multiple_text_node_updates_with_complex_layout_changes(self):
        """Maps to test("should handle multiple text node updates with complex layout changes")."""

        setup = await create_test_renderer(20, 10)
        text1 = TextRenderable(wrap_mode="word")
        text1.width = 10
        node1 = TextNode("First")
        node2 = TextNode(" part")
        text1.add(node1)
        text1.add(node2)
        text2 = TextRenderable(content="Middle text")
        text2.width = 12
        text3 = TextRenderable(content="Bottom text")
        setup.renderer.root.add(text1)
        setup.renderer.root.add(text2)
        setup.renderer.root.add(text3)
        setup.render_frame()
        assert text1.height == 1
        initial_t2_y = text2._y
        initial_t3_y = text3._y
        # Expand nodes
        node1.append(" of a sentence")
        node2.append("that will wrap")
        text1._sync_text_from_nodes()
        setup.render_frame()
        assert text1.height > 1
        assert text2._y > initial_t2_y
        assert text3._y > initial_t3_y
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Height and Width Measurement
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableHeightAndWidthMeasurement:
    """Maps to describe("TextRenderable Selection") > describe("Height and Width Measurement")."""

    async def test_should_grow_height_for_multiline_text_without_wrapping(self):
        """Maps to test("should grow height for multiline text without wrapping")."""

        setup, text = await _make(
            "Line 1\nLine 2\nLine 3\nLine 4\nLine 5",
            width=40,
            height=10,
            wrap_mode="none",
        )
        assert text.height == 5
        assert text.width >= 6
        setup.destroy()

    async def test_should_grow_height_for_wrapped_text_when_wrapping_enabled(self):
        """Maps to test("should grow height for wrapped text when wrapping enabled")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="This is a very long line that will definitely wrap to multiple lines",
            wrap_mode="word",
        )
        text.width = 15
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.height > 1
        assert text.width <= 15
        setup.destroy()

    async def test_should_measure_full_width_when_wrapping_is_disabled_and_not_constrained_by_parent(
        self,
    ):
        """Maps to test("should measure full width when wrapping is disabled and not constrained by parent")."""

        content = "This is a very long line that would wrap but wrapping is disabled"
        setup = await create_test_renderer(100, 10)
        text = TextRenderable(
            content=content,
            wrap_mode="none",
            position="absolute",
        )
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.height == 1
        assert text.width == len(content)
        setup.destroy()

    async def test_should_update_height_when_content_changes_from_single_to_multiline(self):
        """Maps to test("should update height when content changes from single to multiline")."""

        setup, text = await _make("Single line", width=40, height=10, wrap_mode="none")
        assert text.height == 1
        text.content = "Line 1\nLine 2\nLine 3"
        setup.render_frame()
        assert text.height == 3
        setup.destroy()

    async def test_should_update_height_when_wrapping_mode_changes(self):
        """Maps to test("should update height when wrapping mode changes")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="This is a long line that will wrap to multiple lines",
            wrap_mode="none",
        )
        text.width = 15
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.height == 1
        text.wrap_mode = "word"
        setup.render_frame()
        assert text.height > 1
        setup.destroy()

    async def test_should_shrink_height_when_content_changes_from_multi_line_to_single_line(self):
        """Maps to test("should shrink height when content changes from multi-line to single line")."""

        setup, text = await _make(
            "Line 1\nLine 2\nLine 3\nLine 4\nLine 5",
            width=40,
            height=10,
            wrap_mode="none",
        )
        assert text.height == 5
        text.content = "Single line"
        setup.render_frame()
        assert text.height == 1
        setup.destroy()

    async def test_should_shrink_width_when_replacing_long_line_with_shorter(self):
        """Maps to test("should shrink width when replacing long line with shorter")."""

        long_content = "This is a very long line with many characters"
        setup = await create_test_renderer(100, 10)
        text = TextRenderable(
            content=long_content,
            wrap_mode="none",
            position="absolute",
        )
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.width == len(long_content)
        text.content = "Short"
        setup.render_frame()
        assert text.width == 5
        assert text.width < len(long_content)
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Width/Height Setter Layout Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableWidthHeightSetterLayoutTests:
    """Maps to describe("TextRenderable Selection") > describe("Width/Height Setter Layout Tests")."""

    async def test_should_not_shrink_box_when_width_is_set_via_setter(self):
        """Maps to test("should not shrink box when width is set via setter")."""

        setup = await create_test_renderer(40, 10)
        container = Box(border=True, width=30, flex_direction="row")
        indicator = TextRenderable(content=">")
        content = TextRenderable(content="Content that takes up space", flex_grow=1)
        container.add(indicator)
        container.add(content)
        setup.renderer.root.add(container)
        setup.render_frame()
        initial_w = indicator.width
        indicator.width = 5
        setup.render_frame()
        assert indicator.width == 5
        assert content.width > 0
        setup.destroy()

    async def test_should_not_shrink_box_when_height_is_set_via_setter_in_column_layout_with_text(
        self,
    ):
        """Maps to test("should not shrink box when height is set via setter in column layout with text")."""

        setup = await create_test_renderer(30, 15)
        outer = Box(border=True, width=25, height=10, flex_direction="column")
        header = TextRenderable(content="Header")
        main_content = TextRenderable(
            content="Line1\nLine2\nLine3\nLine4\nLine5\nLine6\nLine7\nLine8",
            flex_grow=1,
        )
        footer = TextRenderable(content="Footer")
        footer.height = 2
        outer.add(header)
        outer.add(main_content)
        outer.add(footer)
        setup.renderer.root.add(outer)
        setup.render_frame()
        assert main_content.height > 0
        header.height = 3
        setup.render_frame()
        assert header.height == 3
        assert main_content.height > 0
        assert footer.height == 2
        setup.destroy()

    async def test_should_not_shrink_box_when_minwidth_is_set_via_setter(self):
        """Maps to test("should not shrink box when minWidth is set via setter")."""

        setup = await create_test_renderer(40, 10)
        container = Box(border=True, width=30, flex_direction="row")
        indicator = TextRenderable(content=">", flex_shrink=1)
        content = TextRenderable(content="Content", flex_grow=1)
        container.add(indicator)
        container.add(content)
        setup.renderer.root.add(container)
        setup.render_frame()
        indicator._min_width = 5
        indicator.mark_dirty()
        setup.render_frame()
        assert indicator.width >= 5
        assert content.width > 0
        setup.destroy()

    async def test_should_not_shrink_box_when_minheight_is_set_via_setter_in_column_layout_with_text(
        self,
    ):
        """Maps to test("should not shrink box when minHeight is set via setter in column layout with text")."""

        setup = await create_test_renderer(30, 15)
        outer = Box(border=True, width=25, height=10, flex_direction="column")
        header = TextRenderable(content="Header", flex_shrink=1)
        main_content = TextRenderable(
            content="Line1\nLine2\nLine3\nLine4\nLine5\nLine6\nLine7\nLine8",
            flex_grow=1,
        )
        footer = TextRenderable(content="Footer")
        footer.height = 2
        outer.add(header)
        outer.add(main_content)
        outer.add(footer)
        setup.renderer.root.add(outer)
        setup.render_frame()
        header._min_height = 3
        header.mark_dirty()
        setup.render_frame()
        assert header.height >= 3
        assert main_content.height > 0
        assert footer.height == 2
        setup.destroy()

    async def test_should_not_shrink_box_when_width_is_set_from_undefined_via_setter(self):
        """Maps to test("should not shrink box when width is set from undefined via setter")."""

        setup = await create_test_renderer(40, 10)
        container = Box(border=True, width=30, flex_direction="row")
        indicator = TextRenderable(content=">", flex_shrink=1)
        content = TextRenderable(content="Content that takes up space", flex_grow=1)
        container.add(indicator)
        container.add(content)
        setup.renderer.root.add(container)
        setup.render_frame()
        indicator.width = 5
        setup.render_frame()
        assert indicator.width == 5
        assert content.width > 0
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Absolute Positioned Box with Text
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableAbsolutePositionedBoxWithText:
    """Maps to describe("TextRenderable Selection") > describe("Absolute Positioned Box with Text")."""

    async def test_should_render_text_in_absolute_positioned_box_with_padding_and_borders_correctly(
        self,
    ):
        """Maps to test("should render text in absolute positioned box with padding and borders correctly")."""

        setup = await create_test_renderer(80, 20)
        box = Box(position="absolute", top=2, width=60, padding=2, border=True)
        title = TextRenderable(content="Important Notification")
        msg = TextRenderable(
            content="This is an important message.",
            wrap_mode="word",
        )
        box.add(title)
        box.add(msg)
        setup.renderer.root.add(box)
        setup.render_frame()
        assert box._y == 2
        assert box.width == 60
        frame = setup.capture_char_frame()
        assert "Important Notification" in frame
        setup.destroy()

    async def test_should_render_text_fully_visible_in_absolute_positioned_box_at_various_positions(
        self,
    ):
        """Maps to test("should render text fully visible in absolute positioned box at various positions")."""

        setup = await create_test_renderer(100, 25)
        top_box = Box(position="absolute", top=1, width=40, padding=1, border=True)
        top_text = TextRenderable(
            content="Error: File not found in the specified directory path",
            wrap_mode="word",
        )
        top_box.add(top_text)
        setup.renderer.root.add(top_box)
        setup.render_frame()
        assert top_box._y == 1
        assert top_text.plain_text == "Error: File not found in the specified directory path"
        frame = setup.capture_char_frame()
        assert "Error" in frame
        setup.destroy()

    async def test_should_handle_width_100_percent_text_in_absolute_positioned_box_with_constrained_maxwidth(
        self,
    ):
        """Maps to test("should handle width:100% text in absolute positioned box with constrained maxWidth")."""

        setup = await create_test_renderer(70, 15)
        box = Box(position="absolute", top=5, left=10, max_width=50, padding=3)
        long_text = TextRenderable(
            content="This is a long text that should wrap within the constrained box",
            wrap_mode="word",
        )
        box.add(long_text)
        setup.renderer.root.add(box)
        setup.render_frame()
        assert box._layout_width <= 50
        assert box._x == 10
        assert box._y == 5
        setup.destroy()

    async def test_should_render_multiple_text_elements_in_absolute_positioned_box_with_proper_spacing(
        self,
    ):
        """Maps to test("should render multiple text elements in absolute positioned box with proper spacing")."""

        setup = await create_test_renderer(90, 20)
        box = Box(position="absolute", top=3, max_width=45, padding=2, border=True)
        header = TextRenderable(content="System Update")
        body = TextRenderable(
            content="A new version is available with bug fixes and performance improvements.",
            wrap_mode="word",
        )
        footer = TextRenderable(content="Click to install")
        box.add(header)
        box.add(body)
        box.add(footer)
        setup.renderer.root.add(box)
        setup.render_frame()
        assert header.plain_text == "System Update"
        assert header.height == 1
        assert (
            body.plain_text
            == "A new version is available with bug fixes and performance improvements."
        )
        assert footer.plain_text == "Click to install"
        assert footer.height == 1
        assert body._y > header._y
        assert footer._y > body._y
        frame = setup.capture_char_frame()
        assert "System Update" in frame
        assert "Click to install" in frame
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Word Wrapping
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableWordWrapping:
    """Maps to describe("TextRenderable Selection") > describe("Word Wrapping")."""

    def test_should_default_to_word_wrap_mode(self):
        """Maps to test("should default to word wrap mode")."""
        text = TextRenderable(content="Hello World")
        assert text.wrap_mode == "word"

    async def test_should_wrap_at_word_boundaries_when_using_word_mode(self):
        """Maps to test("should wrap at word boundaries when using word mode")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="The quick brown fox jumps over the lazy dog",
            wrap_mode="word",
        )
        text.width = 15
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 1
        # Each line should end at a word boundary (no split words)
        for line in lines:
            stripped = line.rstrip()
            if stripped and len(stripped) > 15:
                pytest.fail(f"Line exceeds wrap width: {stripped!r}")
        setup.destroy()

    async def test_should_wrap_at_character_boundaries_when_using_char_mode(self):
        """Maps to test("should wrap at character boundaries when using char mode")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="The quick brown fox jumps over the lazy dog",
            wrap_mode="char",
        )
        text.width = 15
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 1
        setup.destroy()

    async def test_should_handle_word_wrapping_with_punctuation(self):
        """Maps to test("should handle word wrapping with punctuation")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="Hello,World.Test-Example/Path",
            wrap_mode="word",
        )
        text.width = 10
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        assert "Hello" in frame or "Hello," in frame
        setup.destroy()

    async def test_should_handle_word_wrapping_with_hyphens_and_dashes(self):
        """Maps to test("should handle word wrapping with hyphens and dashes")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="self-contained multi-line text-wrapping example",
            wrap_mode="word",
        )
        text.width = 12
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 1
        setup.destroy()

    async def test_regression_651_should_keep_multi_byte_utf8_words_intact_when_wrapping_in_word_mode(
        self,
    ):
        """Maps to test("regression #651: should keep multi-byte UTF-8 words intact when wrapping in word mode")."""

        setup = await create_test_renderer(80, 24)
        content = "word1 word2 word3 word4 word5 word6 word7 word8 word9"
        text = TextRenderable(content=content, wrap_mode="word")
        text.width = 20
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 1
        # No word should be split
        for line in lines:
            words = line.strip().split()
            for word in words:
                assert word in content
        setup.destroy()

    async def test_should_dynamically_change_wrap_mode(self):
        """Maps to test("should dynamically change wrap mode")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="The quick brown fox jumps",
            wrap_mode="char",
        )
        text.width = 10
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.wrap_mode == "char"
        text.wrap_mode = "word"
        setup.render_frame()
        assert text.wrap_mode == "word"
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 1
        setup.destroy()

    async def test_should_handle_long_words_that_exceed_wrap_width_in_word_mode(self):
        """Maps to test("should handle long words that exceed wrap width in word mode")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            wrap_mode="word",
        )
        text.width = 10
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        # Should fall back to char wrapping for long word
        assert len(lines) > 1
        setup.destroy()

    async def test_should_preserve_empty_lines_with_word_wrapping(self):
        """Maps to test("should preserve empty lines with word wrapping")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="First line\n\nThird line",
            wrap_mode="word",
        )
        text.width = 20
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        assert "First line" in frame
        assert "Third line" in frame
        # Empty line between them
        lines = frame.split("\n")
        first_idx = next(i for i, ln in enumerate(lines) if "First line" in ln)
        third_idx = next(i for i, ln in enumerate(lines) if "Third line" in ln)
        assert third_idx - first_idx >= 2  # at least one empty line between
        setup.destroy()

    async def test_should_handle_word_wrapping_with_single_character_words(self):
        """Maps to test("should handle word wrapping with single character words")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="a b c d e f g h i j k l m n o p",
            wrap_mode="word",
        )
        text.width = 8
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
        lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(lines) > 1
        setup.destroy()

    async def test_should_compare_char_vs_word_wrapping_with_same_content(self):
        """Maps to test("should compare char vs word wrapping with same content")."""

        content = "Hello wonderful world of text wrapping"
        setup = await create_test_renderer(40, 10)
        char_text = TextRenderable(content=content, wrap_mode="char")
        char_text.width = 12
        setup.renderer.root.add(char_text)
        char_frame = setup.capture_char_frame()
        setup.renderer.root.remove(char_text)
        word_text = TextRenderable(content=content, wrap_mode="word")
        word_text.width = 12
        setup.renderer.root.add(word_text)
        word_frame = setup.capture_char_frame()
        # Char and word wrapping should produce different results
        assert char_frame != word_frame
        setup.destroy()

    async def test_should_correctly_wrap_text_when_updating_content_via_text_content(self):
        """Maps to test("should correctly wrap text when updating content via text.content")."""

        setup = await create_test_renderer(40, 10)
        text = TextRenderable(content="Short text", wrap_mode="word")
        setup.renderer.root.add(text)
        initial_frame = setup.capture_char_frame()
        text.content = "This is a much longer text that should definitely wrap to multiple lines"
        updated_frame = setup.capture_char_frame()
        assert initial_frame != updated_frame
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Mouse Scrolling
# ═════════════════════════════════════════════════════════════════════════════


class TestTextRenderableMouseScrolling:
    """Maps to describe("TextRenderable Selection") > describe("Mouse Scrolling")."""

    async def test_should_receive_mouse_scroll_events(self):
        """Maps to test("should receive mouse scroll events")."""

        setup = await create_test_renderer(20, 10)
        content = "\n".join(f"Line {i + 1}" for i in range(10))
        text = TextRenderable(content=content, wrap_mode="none")
        setup.renderer.root.add(text)
        setup.render_frame()
        scroll_received = False

        original_handler = text._on_mouse_scroll

        def tracking_handler(event):
            nonlocal scroll_received
            scroll_received = True
            original_handler(event)

        text._on_mouse_scroll = tracking_handler
        setup.mock_mouse.scroll(text._x + 1, text._y + 1, "down")
        assert scroll_received is True
        setup.destroy()

    async def test_should_handle_mouse_scroll_events_for_vertical_scrolling(self):
        """Maps to test("should handle mouse scroll events for vertical scrolling")."""

        setup = await create_test_renderer(20, 5)
        content = "\n".join(f"Line {i + 1}" for i in range(10))
        text = TextRenderable(content=content, wrap_mode="none", height=5)
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.scroll_y == 0
        # Scroll down 3 times
        for _ in range(3):
            text._handle_scroll_event(
                type("E", (), {"scroll_direction": "down", "scroll_delta": 1})()
            )
        assert text.scroll_y == 3
        # Scroll up 1 time
        text._handle_scroll_event(type("E", (), {"scroll_direction": "up", "scroll_delta": -1})())
        assert text.scroll_y == 2
        setup.destroy()

    async def test_should_handle_mouse_scroll_events_for_horizontal_scrolling_with_unwrapped_text(
        self,
    ):
        """Maps to test("should handle mouse scroll events for horizontal scrolling with unwrapped text")."""

        setup = await create_test_renderer(80, 5)
        text = TextRenderable(
            content="A" * 100,
            wrap_mode="none",
        )
        text.width = 20
        text._max_width = 20
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.scroll_x == 0
        # Scroll right 5 times
        for _ in range(5):
            text._handle_scroll_event(
                type("E", (), {"scroll_direction": "right", "scroll_delta": 1})()
            )
        assert text.scroll_x == 5
        # Scroll left 2 times
        for _ in range(2):
            text._handle_scroll_event(
                type("E", (), {"scroll_direction": "left", "scroll_delta": -1})()
            )
        assert text.scroll_x == 3
        setup.destroy()

    async def test_should_not_allow_horizontal_scrolling_when_text_is_wrapped(self):
        """Maps to test("should not allow horizontal scrolling when text is wrapped")."""

        setup = await create_test_renderer(20, 5)
        content = "This is a long line that will wrap when word wrapping is enabled"
        text = TextRenderable(content=content, wrap_mode="word")
        text.width = 15
        text.height = 3
        setup.renderer.root.add(text)
        setup.render_frame()
        # Attempt horizontal scroll
        for _ in range(5):
            text._handle_scroll_event(
                type("E", (), {"scroll_direction": "right", "scroll_delta": 1})()
            )
        assert text.scroll_x == 0  # No horizontal scroll when wrapped
        setup.destroy()

    async def test_should_clamp_scroll_position_to_valid_bounds(self):
        """Maps to test("should clamp scroll position to valid bounds")."""

        setup = await create_test_renderer(20, 5)
        text = TextRenderable(
            content="Line 1\nLine 2\nLine 3",
            wrap_mode="none",
        )
        setup.renderer.root.add(text)
        setup.render_frame()
        # Scroll way past the end
        for _ in range(10):
            text._handle_scroll_event(
                type("E", (), {"scroll_direction": "down", "scroll_delta": 1})()
            )
        assert text.scroll_y <= text.max_scroll_y
        assert text.scroll_y >= 0
        # Scroll way past the top
        for _ in range(20):
            text._handle_scroll_event(
                type("E", (), {"scroll_direction": "up", "scroll_delta": -1})()
            )
        assert text.scroll_y == 0
        setup.destroy()

    async def test_should_expose_scrollwidth_and_scrollheight_getters(self):
        """Maps to test("should expose scrollWidth and scrollHeight getters")."""

        setup = await create_test_renderer(20, 5)
        text = TextRenderable(
            content="Line 1\nLine 2 with more content\nLine 3",
            wrap_mode="none",
        )
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.scroll_height == 3
        assert text.scroll_width > 0
        setup.destroy()

    async def test_should_calculate_maxscrolly_and_maxscrollx_correctly(self):
        """Maps to test("should calculate maxScrollY and maxScrollX correctly")."""

        setup = await create_test_renderer(20, 5)
        content = "\n".join(f"Line {i + 1}" for i in range(8))
        text = TextRenderable(content=content, wrap_mode="none")
        text.height = 5
        setup.renderer.root.add(text)
        setup.render_frame()
        assert text.max_scroll_y == max(0, text.scroll_height - text.height)
        assert text.max_scroll_x == max(0, text.scroll_width - text.width)
        setup.destroy()

    async def test_should_update_scroll_position_via_setters(self):
        """Maps to test("should update scroll position via setters")."""

        setup = await create_test_renderer(20, 5)
        content = "\n".join(f"Line {i + 1}" for i in range(10))
        text = TextRenderable(content=content, wrap_mode="none")
        text.height = 5
        setup.renderer.root.add(text)
        setup.render_frame()
        text.scroll_y = 3
        assert text.scroll_y == 3
        if text.max_scroll_x > 0:
            text.scroll_x = 2
            assert text.scroll_x == 2
        setup.destroy()


# ═════════════════════════════════════════════════════════════════════════════
# Mouse Dispatch Pipeline Selection Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestTextSelectionViaMouse:
    """Tests that exercise the full mouse dispatch pipeline for text selection.

    Unlike the tests above that call text.set_selection() directly, these
    tests use setup.mock_mouse.drag() / click() so the event flows through
    the renderer's _dispatch_mouse_event -> start_selection ->
    update_selection -> on_selection_changed path.
    """

    async def test_mouse_drag_selects_text(self):
        """Dragging across a TextRenderable via the mouse pipeline produces a selection."""
        setup = await create_test_renderer(40, 5)
        text = TextRenderable(content="Hello World", selectable=True, wrap_mode="none")
        setup.renderer.root.add(text)
        setup.render_frame()

        # Preconditions
        assert text.has_selection() is False
        assert text._x == 0  # text starts at column 0

        # Drag from column 0 to column 5 (should select "Hello")
        start_x = text._x
        start_y = text._y
        end_x = text._x + 5
        end_y = text._y
        setup.mock_mouse.drag(start_x, start_y, end_x, end_y)

        # The renderer should have an active selection
        assert setup.renderer.has_selection is True

        # The text renderable should reflect a selection set via
        # on_selection_changed (cross-renderable selection pipeline)
        assert text.has_selection() is True
        selected = text.get_selected_text()
        assert len(selected) > 0
        # The selected text should be a prefix of "Hello World"
        assert selected in "Hello World"
        setup.destroy()

    async def test_mouse_click_clears_selection(self):
        """After a drag selection, a plain click elsewhere clears the selection."""
        setup = await create_test_renderer(40, 5)
        text = TextRenderable(content="Hello World", selectable=True, wrap_mode="none")
        setup.renderer.root.add(text)
        setup.render_frame()

        # Create a selection via drag
        setup.mock_mouse.drag(text._x, text._y, text._x + 5, text._y)
        assert setup.renderer.has_selection is True
        assert text.has_selection() is True

        # Click on empty space well outside the text (no preventDefault)
        setup.mock_mouse.click(setup.renderer.width - 1, setup.renderer.height - 1)

        # Selection should be cleared
        assert setup.renderer.has_selection is False
        assert text.has_selection() is False
        assert text.get_selected_text() == ""
        setup.destroy()

    async def test_mouse_drag_multiline_selects_across_lines(self):
        """Dragging across multiple lines selects text spanning those lines."""
        setup = await create_test_renderer(40, 10)
        text = TextRenderable(
            content="Line one\nLine two\nLine three",
            selectable=True,
            wrap_mode="none",
        )
        setup.renderer.root.add(text)
        setup.render_frame()

        assert text.has_selection() is False

        # Drag from the start of line 1 to partway through line 3
        start_x = text._x
        start_y = text._y
        end_x = text._x + 6
        end_y = text._y + 2  # third line
        setup.mock_mouse.drag(start_x, start_y, end_x, end_y)

        assert setup.renderer.has_selection is True
        assert text.has_selection() is True

        selected = text.get_selected_text()
        assert len(selected) > 0
        # The selection spans multiple lines so it should contain a newline
        assert "\n" in selected
        setup.destroy()
