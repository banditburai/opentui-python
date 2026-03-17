"""Port of upstream LineNumberRenderable.wrapping.test.ts.

Upstream: packages/core/src/renderables/__tests__/LineNumberRenderable.wrapping.test.ts
Tests ported: 2/2
"""

import re

from opentui import LineNumberRenderable, TextareaRenderable, create_test_renderer


class TestLineNumberRenderableWrappingScrolling:
    """Maps to describe("LineNumberRenderable Wrapping & Scrolling")."""

    async def test_renders_correct_line_numbers_when_scrolled(self):
        """Maps to test("renders correct line numbers when scrolled")."""
        setup = await create_test_renderer(20, 5)

        content = "1111111111 1111111\n2222222222 2222222\n333\n444\n555"

        editor = TextareaRenderable(
            initial_value=content,
            wrap_mode="char",
            width="100%",
            height="100%",
        )

        editor_with_lines = LineNumberRenderable(
            target=editor,
            min_width=3,
            padding_right=1,
            width="100%",
            height="100%",
        )

        setup.renderer.root.add(editor_with_lines)

        frame = setup.capture_char_frame()
        # Line number 1 should be visible with the start of content
        assert " 1 " in frame
        assert "1111111111" in frame

        # Move cursor to bottom to force scroll
        editor.edit_buffer.set_cursor(4, 0)

        frame = setup.capture_char_frame()

        # After scrolling, line 5 should be visible
        assert " 5 " in frame
        assert "555" in frame
        # Line 2 should still be visible (wrapping means it takes multiple visual lines)
        assert "2222222222" in frame

        setup.destroy()

    async def test_renders_correct_line_numbers_with_complex_wrapping_and_empty_lines(self):
        """Maps to test("renders correct line numbers with complex wrapping and empty lines")."""
        setup = await create_test_renderer(30, 10)

        content = "A" * 20 + "\n\n" + "B" * 40 + "\n\nC"

        editor = TextareaRenderable(
            initial_value=content,
            wrap_mode="char",
            width="100%",
            height="100%",
        )

        editor_with_lines = LineNumberRenderable(
            target=editor,
            min_width=3,
            padding_right=1,
            width="100%",
            height="100%",
        )

        setup.renderer.root.add(editor_with_lines)

        frame = setup.capture_char_frame()
        lines = frame.split("\n")

        # Line 0: logical line 1 with 20 A's
        assert re.search(r" 1 A{20}", lines[0]), f"Line 0 mismatch: {lines[0]!r}"

        # Line 1: logical line 2 (empty line)
        assert re.search(r" 2\s*$", lines[1]), f"Line 1 mismatch: {lines[1]!r}"

        # Line 2: logical line 3 with B's (first visual line of wrapped content)
        assert re.search(r" 3 B+", lines[2]), f"Line 2 mismatch: {lines[2]!r}"

        # Line 3: continuation of logical line 3 (no line number, just B's with gutter padding)
        assert re.search(r"^\s+B+", lines[3]), f"Line 3 mismatch: {lines[3]!r}"

        # Line 4: logical line 4 (empty line)
        assert re.search(r" 4\s*$", lines[4]), f"Line 4 mismatch: {lines[4]!r}"

        # Line 5: logical line 5 with "C"
        assert re.search(r" 5 C", lines[5]), f"Line 5 mismatch: {lines[5]!r}"

        setup.destroy()
