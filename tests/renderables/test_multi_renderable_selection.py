"""Port of upstream MultiRenderable.selection.test.ts.

Upstream: packages/core/src/renderables/__tests__/MultiRenderable.selection.test.ts
Tests ported: 1/1
"""

import pytest

from opentui import TestSetup, create_test_renderer
from opentui.components.text_renderable import TextRenderable
from opentui.components.textarea_renderable import TextareaRenderable


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _create_textarea(
    setup: TestSetup,
    *,
    initial_value: str = "",
    width: int = 40,
    height: int = 5,
    left: int = 0,
    top: int = 0,
    selectable: bool = True,
) -> TextareaRenderable:
    """Create a TextareaRenderable, add to root, and render once."""
    ta = TextareaRenderable(
        initial_value=initial_value,
        width=width,
        height=height,
        left=left,
        top=top,
        selectable=selectable,
        position="absolute",
    )
    setup.renderer.root.add(ta)
    setup.render_frame()
    return ta


class TestMultiRenderableSelection:
    """Maps to describe("Multi-Renderable Selection Tests")."""

    @pytest.mark.asyncio
    async def test_should_handle_selection_across_textarea_and_text_renderable(self):
        """Maps to it("should handle selection across Textarea and Text renderable").

        Creates a Textarea with scrollable content, scrolls it down,
        then drags from inside the Textarea to a TextRenderable below it.
        Verifies that both renderables have active selections with the
        expected content.
        """
        setup = await create_test_renderer(80, 24)
        try:
            # Create a Textarea with scrolling content (20 lines)
            lines_text = "\n".join(f"Line {i}" for i in range(20))
            editor = await _create_textarea(
                setup,
                initial_value=lines_text,
                width=40,
                height=5,
                left=0,
                top=0,
                selectable=True,
            )

            # Create a Text renderable below the Textarea
            text_renderable = TextRenderable(
                content="Text Below Textarea",
                width=40,
                height=1,
                left=0,
                top=6,
                selectable=True,
                position="absolute",
            )
            setup.renderer.root.add(text_renderable)
            setup.render_frame()

            # Scroll the Textarea down to line 10
            editor.goto_line(10)
            setup.render_frame()

            viewport = editor.editor_view.get_viewport()
            assert viewport["offsetY"] > 0

            # Mouse drag from inside the Textarea to the Text renderable
            start_x = editor.x + 2
            start_y = editor.y + 2
            end_x = text_renderable.x + 5
            end_y = text_renderable.y

            setup.mock_mouse.drag(start_x, start_y, end_x, end_y)
            setup.render_frame()

            assert editor.has_selection is True
            assert text_renderable.has_selection() is True

            selected_textarea_text = editor.get_selected_text()
            selected_text_text = text_renderable.get_selected_text()

            # Verify selection in Textarea (should be from the scrolled viewport)
            # The selection starts at the line visible at relative row 2 and
            # extends to the end of the visible buffer since we dragged out of it.
            assert "ne 9" in selected_textarea_text or "Line 9" in selected_textarea_text
            assert "Line 10" in selected_textarea_text

            # Verify selection in Text renderable -- "Text " (5 chars from start)
            assert selected_text_text == "Text "
        finally:
            setup.destroy()
