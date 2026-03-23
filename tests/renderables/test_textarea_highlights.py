"""Tests for Textarea highlights — ported from Textarea.highlights.test.ts (25 tests).

Upstream: reference/opentui/packages/core/src/renderables/__tests__/Textarea.highlights.test.ts
"""

import pytest

from opentui import TestSetup, create_test_renderer
from opentui.components.textarea_renderable import TextareaRenderable
from opentui.native import NativeOptimizedBuffer
from opentui.structs import RGBA
from opentui.editor.syntax_style import SyntaxStyle, StyleDefinition


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _make_textarea(
    setup: TestSetup,
    *,
    initial_value: str = "",
    syntax_style=None,
    width=None,
    height=None,
    **extra_kw,
) -> TextareaRenderable:
    """Create a TextareaRenderable, add to renderer root, and render once."""
    kw: dict = dict(
        initial_value=initial_value,
        position="relative",
    )
    if syntax_style is not None:
        kw["syntax_style"] = syntax_style
    if width is not None:
        kw["width"] = width
    if height is not None:
        kw["height"] = height
    kw.update(extra_kw)
    ta = TextareaRenderable(**kw)
    setup.renderer.root.add(ta)
    setup.render_frame()
    return ta


# ═══════════════════════════════════════════════════════════════════════════
# SyntaxStyle Management
# ═══════════════════════════════════════════════════════════════════════════


class TestSyntaxStyleManagement:
    """Maps to describe('Textarea - Highlights') > describe('SyntaxStyle Management')."""

    async def test_should_set_syntax_style_via_constructor_option(self):
        """should set syntax style via constructor option"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        editor = await _make_textarea(setup, initial_value="hello", syntax_style=style)

        assert editor.syntax_style is style
        setup.destroy()

    async def test_should_set_syntax_style_via_setter(self):
        """should set syntax style via setter"""
        setup = await create_test_renderer(80, 24)
        editor = await _make_textarea(setup, initial_value="hello")

        assert editor.syntax_style is None

        style = SyntaxStyle.create()
        editor.syntax_style = style
        assert editor.syntax_style is style
        setup.destroy()

    async def test_should_clear_syntax_style_when_set_to_none(self):
        """should clear syntax style when set to null"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        editor = await _make_textarea(setup, initial_value="hello", syntax_style=style)

        assert editor.syntax_style is style

        editor.syntax_style = None
        assert editor.syntax_style is None
        setup.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Highlight Management
# ═══════════════════════════════════════════════════════════════════════════


class TestHighlightManagement:
    """Maps to describe('Textarea - Highlights') > describe('Highlight Management')."""

    async def test_should_add_highlight_by_line_and_column_range(self):
        """should add highlight by line and column range"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        editor.add_highlight(0, {"start": 0, "end": 5, "styleId": style_id, "priority": 0})

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0]["start"] == 0
        assert highlights[0]["end"] == 5
        assert highlights[0]["style_id"] == style_id
        setup.destroy()

    async def test_should_add_multiple_highlights_to_same_line(self):
        """should add multiple highlights to same line"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id_1 = style.register_style(
            "keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True)
        )
        style_id_2 = style.register_style("string", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        editor.add_highlight(0, {"start": 0, "end": 5, "styleId": style_id_1, "priority": 0})
        editor.add_highlight(0, {"start": 6, "end": 11, "styleId": style_id_2, "priority": 0})

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 2
        setup.destroy()

    async def test_should_add_highlight_by_character_range(self):
        """should add highlight by character range"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        editor.add_highlight_by_char_range(
            {"start": 0, "end": 5, "styleId": style_id, "priority": 0}
        )

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0]["start"] == 0
        assert highlights[0]["end"] == 5
        setup.destroy()

    async def test_should_add_highlight_with_custom_priority(self):
        """should add highlight with custom priority"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        editor.add_highlight(0, {"start": 0, "end": 5, "styleId": style_id, "priority": 10})

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0]["priority"] == 10
        setup.destroy()

    async def test_should_add_highlight_with_reference_id(self):
        """should add highlight with reference ID"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        ref_id = 42
        editor.add_highlight(
            0,
            {
                "start": 0,
                "end": 5,
                "styleId": style_id,
                "priority": 0,
                "hlRef": ref_id,
            },
        )

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0]["hl_ref"] == ref_id
        setup.destroy()

    async def test_should_remove_highlights_by_reference_id(self):
        """should remove highlights by reference ID"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        ref_id = 42
        editor.add_highlight(
            0,
            {
                "start": 0,
                "end": 5,
                "styleId": style_id,
                "priority": 0,
                "hlRef": ref_id,
            },
        )

        highlights_before = editor.get_line_highlights(0)
        assert len(highlights_before) == 1

        editor.remove_highlights_by_ref(ref_id)

        highlights_after = editor.get_line_highlights(0)
        assert len(highlights_after) == 0
        setup.destroy()

    async def test_should_clear_highlights_for_specific_line(self):
        """should clear highlights for specific line"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(
            setup,
            initial_value="line one\nline two\nline three",
            syntax_style=style,
        )

        editor.add_highlight(0, {"start": 0, "end": 4, "styleId": style_id, "priority": 0})
        editor.add_highlight(1, {"start": 0, "end": 4, "styleId": style_id, "priority": 0})
        editor.add_highlight(2, {"start": 0, "end": 4, "styleId": style_id, "priority": 0})

        assert len(editor.get_line_highlights(0)) == 1
        assert len(editor.get_line_highlights(1)) == 1
        assert len(editor.get_line_highlights(2)) == 1

        editor.clear_line_highlights(1)

        assert len(editor.get_line_highlights(0)) == 1
        assert len(editor.get_line_highlights(1)) == 0
        assert len(editor.get_line_highlights(2)) == 1
        setup.destroy()

    async def test_should_clear_all_highlights(self):
        """should clear all highlights"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(
            setup,
            initial_value="line one\nline two\nline three",
            syntax_style=style,
        )

        editor.add_highlight(0, {"start": 0, "end": 4, "styleId": style_id, "priority": 0})
        editor.add_highlight(1, {"start": 0, "end": 4, "styleId": style_id, "priority": 0})
        editor.add_highlight(2, {"start": 0, "end": 4, "styleId": style_id, "priority": 0})

        editor.clear_all_highlights()

        assert len(editor.get_line_highlights(0)) == 0
        assert len(editor.get_line_highlights(1)) == 0
        assert len(editor.get_line_highlights(2)) == 0
        setup.destroy()

    async def test_should_return_empty_array_for_line_with_no_highlights(self):
        """should return empty array for line with no highlights"""
        setup = await create_test_renderer(80, 24)
        editor = await _make_textarea(setup, initial_value="hello world")

        highlights = editor.get_line_highlights(0)
        assert highlights == [] or len(highlights) == 0
        setup.destroy()

    async def test_should_return_empty_array_for_line_index_out_of_bounds(self):
        """should return empty array for line index out of bounds"""
        setup = await create_test_renderer(80, 24)
        editor = await _make_textarea(setup, initial_value="hello world")

        highlights = editor.get_line_highlights(999)
        assert len(highlights) == 0
        setup.destroy()

    async def test_should_handle_highlights_spanning_multiple_lines_via_character_range(self):
        """should handle highlights spanning multiple lines via character range"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(
            setup,
            initial_value="hello\nworld\nfoo",
            syntax_style=style,
        )

        # Char range spanning from "hello\n" through "world\n" into "foo"
        # "hello\nworld\nfoo" = 15 chars; range 0..15 spans all lines
        editor.add_highlight_by_char_range(
            {
                "start": 0,
                "end": 15,
                "styleId": style_id,
                "priority": 0,
            }
        )

        # Each line should have a highlight
        hl0 = editor.get_line_highlights(0)
        hl1 = editor.get_line_highlights(1)
        hl2 = editor.get_line_highlights(2)
        assert len(hl0) >= 1
        assert len(hl1) >= 1
        assert len(hl2) >= 1
        setup.destroy()

    async def test_should_preserve_highlights_after_text_editing_when_using_hl_ref(self):
        """should preserve highlights after text editing when using hlRef"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(
            setup,
            initial_value="hello world",
            syntax_style=style,
        )

        ref_id = 99
        editor.add_highlight(
            0,
            {
                "start": 0,
                "end": 5,
                "styleId": style_id,
                "priority": 0,
                "hlRef": ref_id,
            },
        )

        # Type a character at the end of the line
        editor.focus()
        editor.edit_buffer.goto_line(9999)
        setup.mock_input.press_key("!")
        setup.render_frame()

        # The highlight should still be retrievable via its ref
        highlights = editor.get_line_highlights(0)
        # The highlight with hlRef should still exist (may have shifted)
        hl_with_ref = [h for h in highlights if h["hl_ref"] == ref_id]
        assert len(hl_with_ref) >= 1
        setup.destroy()

    async def test_should_handle_multiple_highlights_with_different_priorities(self):
        """should handle multiple highlights with different priorities"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id_1 = style.register_style(
            "keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True)
        )
        style_id_2 = style.register_style("string", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        editor.add_highlight(0, {"start": 0, "end": 5, "styleId": style_id_1, "priority": 1})
        editor.add_highlight(0, {"start": 0, "end": 5, "styleId": style_id_2, "priority": 10})

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 2

        priorities = sorted([h["priority"] for h in highlights])
        assert priorities == [1, 10]
        setup.destroy()

    async def test_should_clear_highlights_when_removing_by_ref_across_multiple_lines(self):
        """should clear highlights when removing by ref across multiple lines"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(
            setup,
            initial_value="line one\nline two\nline three",
            syntax_style=style,
        )

        ref_id = 77
        editor.add_highlight(
            0,
            {
                "start": 0,
                "end": 4,
                "styleId": style_id,
                "priority": 0,
                "hlRef": ref_id,
            },
        )
        editor.add_highlight(
            1,
            {
                "start": 0,
                "end": 4,
                "styleId": style_id,
                "priority": 0,
                "hlRef": ref_id,
            },
        )
        editor.add_highlight(
            2,
            {
                "start": 0,
                "end": 4,
                "styleId": style_id,
                "priority": 0,
                "hlRef": ref_id,
            },
        )

        assert len(editor.get_line_highlights(0)) == 1
        assert len(editor.get_line_highlights(1)) == 1
        assert len(editor.get_line_highlights(2)) == 1

        editor.remove_highlights_by_ref(ref_id)

        assert len(editor.get_line_highlights(0)) == 0
        assert len(editor.get_line_highlights(1)) == 0
        assert len(editor.get_line_highlights(2)) == 0
        setup.destroy()

    async def test_should_handle_empty_highlights_without_hl_ref(self):
        """should handle empty highlights without hlRef"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        # Add highlight without hlRef (defaults to 0)
        editor.add_highlight(0, {"start": 0, "end": 5, "styleId": style_id, "priority": 0})

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0]["hl_ref"] == 0
        setup.destroy()

    async def test_should_work_without_syntax_style_set(self):
        """should work without syntax style set"""
        setup = await create_test_renderer(80, 24)
        editor = await _make_textarea(setup, initial_value="hello world")

        # Should not crash even without syntax style
        editor.add_highlight(0, {"start": 0, "end": 5, "styleId": 1, "priority": 0})

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 1
        setup.destroy()

    async def test_should_handle_char_range_spanning_entire_buffer(self):
        """should handle char range spanning entire buffer"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        text = "line one\nline two\nline three"
        editor = await _make_textarea(setup, initial_value=text, syntax_style=style)

        editor.add_highlight_by_char_range(
            {
                "start": 0,
                "end": len(text),
                "styleId": style_id,
                "priority": 0,
            }
        )

        # All three lines should have highlights
        assert len(editor.get_line_highlights(0)) >= 1
        assert len(editor.get_line_highlights(1)) >= 1
        assert len(editor.get_line_highlights(2)) >= 1
        setup.destroy()

    async def test_should_handle_updating_highlights_after_clearing_specific_line(self):
        """should handle updating highlights after clearing specific line"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(
            setup,
            initial_value="line one\nline two\nline three",
            syntax_style=style,
        )

        editor.add_highlight(0, {"start": 0, "end": 4, "styleId": style_id, "priority": 0})
        editor.add_highlight(1, {"start": 0, "end": 4, "styleId": style_id, "priority": 0})

        # Clear line 1 highlights
        editor.clear_line_highlights(1)
        assert len(editor.get_line_highlights(1)) == 0

        # Add new highlight to line 1
        style_id_2 = style.register_style("string", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        editor.add_highlight(1, {"start": 0, "end": 8, "styleId": style_id_2, "priority": 5})

        highlights = editor.get_line_highlights(1)
        assert len(highlights) == 1
        assert highlights[0]["style_id"] == style_id_2
        assert highlights[0]["priority"] == 5

        # Line 0 should be unaffected
        assert len(editor.get_line_highlights(0)) == 1
        setup.destroy()

    async def test_should_handle_zero_width_highlights_should_be_ignored(self):
        """should handle zero-width highlights (should be ignored)"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(setup, initial_value="hello world", syntax_style=style)

        # Zero-width highlight: start == end
        editor.add_highlight(0, {"start": 3, "end": 3, "styleId": style_id, "priority": 0})

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 0
        setup.destroy()

    async def test_should_handle_multiple_reference_ids_independently(self):
        """should handle multiple reference IDs independently"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(setup, initial_value="hello world foo", syntax_style=style)

        ref_a = 10
        ref_b = 20
        editor.add_highlight(
            0,
            {
                "start": 0,
                "end": 5,
                "styleId": style_id,
                "priority": 0,
                "hlRef": ref_a,
            },
        )
        editor.add_highlight(
            0,
            {
                "start": 6,
                "end": 11,
                "styleId": style_id,
                "priority": 0,
                "hlRef": ref_b,
            },
        )

        assert len(editor.get_line_highlights(0)) == 2

        # Remove only ref_a
        editor.remove_highlights_by_ref(ref_a)

        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 1
        assert highlights[0]["hl_ref"] == ref_b
        assert highlights[0]["start"] == 6
        assert highlights[0]["end"] == 11

        # Remove ref_b
        editor.remove_highlights_by_ref(ref_b)
        assert len(editor.get_line_highlights(0)) == 0
        setup.destroy()


# ═══════════════════════════════════════════════════════════════════════════
# Highlight Rendering Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestHighlightRenderingIntegration:
    """Maps to describe('Textarea - Highlights') > describe('Highlight Rendering Integration')."""

    async def test_should_render_highlighted_text_without_crashing(self):
        """should render highlighted text without crashing"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id = style.register_style("keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True))
        editor = await _make_textarea(
            setup,
            initial_value="hello world",
            syntax_style=style,
            width=80,
            height=24,
        )

        editor.add_highlight(0, {"start": 0, "end": 5, "styleId": style_id, "priority": 0})
        setup.render_frame()

        # Draw into a NativeOptimizedBuffer — should not crash
        buf = NativeOptimizedBuffer(80, 24)
        buf.draw_editor_view(editor.editor_view, 0, 0)

        # If we got here without an exception, the test passes
        setup.destroy()

    async def test_should_handle_highlights_with_overlapping_ranges(self):
        """should handle highlights with overlapping ranges"""
        setup = await create_test_renderer(80, 24)
        style = SyntaxStyle.create()
        style_id_1 = style.register_style(
            "keyword", StyleDefinition(fg=RGBA(0, 1, 0, 1), bold=True)
        )
        style_id_2 = style.register_style("string", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        editor = await _make_textarea(
            setup,
            initial_value="hello world",
            syntax_style=style,
            width=80,
            height=24,
        )

        # Two overlapping highlights on the same range
        editor.add_highlight(0, {"start": 0, "end": 8, "styleId": style_id_1, "priority": 0})
        editor.add_highlight(0, {"start": 3, "end": 11, "styleId": style_id_2, "priority": 1})
        setup.render_frame()

        # Draw into a NativeOptimizedBuffer — should not crash
        buf = NativeOptimizedBuffer(80, 24)
        buf.draw_editor_view(editor.editor_view, 0, 0)

        # Both highlights should be retrievable
        highlights = editor.get_line_highlights(0)
        assert len(highlights) == 2
        setup.destroy()
