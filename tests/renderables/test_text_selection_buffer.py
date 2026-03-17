"""Port of upstream Text.selection-buffer.test.ts.

Upstream: packages/core/src/renderables/Text.selection-buffer.test.ts
Tests ported: 1/1
"""

import pytest

from opentui import Box, TestSetup, create_test_renderer
from opentui.components.text_renderable import TextRenderable
from opentui.structs import RGBA


class TestTextRenderableSelectionBufferValidation:
    """Maps to describe("TextRenderable Selection - Buffer Validation")."""

    @pytest.mark.asyncio
    async def test_applies_selection_background_colors_to_selected_text_renderables(self):
        """Maps to it("applies selection background colors to selected text renderables").

        Creates three TextRenderable instances inside a Box. Drags from
        text1 to the middle of text2. Verifies that:
        - text1 and text2 have selections, text3 does not
        - The correct text substrings are selected
        - The buffer's background pixels for selected cells match the
          selection background color (#4a5568)
        """
        setup = await create_test_renderer(50, 10)
        try:
            box1 = Box(
                id="box1",
                left=2,
                top=2,
                width=45,
                height=7,
                background_color="#1e2936",
                border_color="#58a6ff",
                title="Document Section 1",
                flex_direction="column",
                padding=1,
                border=True,
                position="absolute",
            )
            setup.renderer.root.add(box1)

            selection_bg = "#4a5568"
            selection_fg = "#ffffff"

            text1 = TextRenderable(
                id="text1",
                content="This is a paragraph in the first box.",
                fg="#f0f6fc",
                selection_bg=selection_bg,
                selection_fg=selection_fg,
                selectable=True,
            )
            box1.add(text1)

            text2 = TextRenderable(
                id="text2",
                content="It contains multiple lines of text",
                fg="#f0f6fc",
                selection_bg=selection_bg,
                selection_fg=selection_fg,
                selectable=True,
            )
            box1.add(text2)

            text3 = TextRenderable(
                id="text3",
                content="that can be selected independently.",
                fg="#f0f6fc",
                selection_bg=selection_bg,
                selection_fg=selection_fg,
                selectable=True,
            )
            box1.add(text3)

            setup.render_frame()

            # Drag from text1 start to text2 col 10
            setup.mock_mouse.drag(text1.x, text1.y, text2.x + 10, text2.y)
            setup.render_frame()

            assert text1.has_selection() is True
            assert text2.has_selection() is True
            assert text3.has_selection() is False

            assert text1.get_selected_text() == "This is a paragraph in the first box."
            assert text2.get_selected_text() == "It contain"

            # Validate buffer background colors for selected cells
            buffer = setup.get_buffer()
            expected_bg = RGBA.from_hex(selection_bg)

            def get_bg_at(x: int, y: int) -> RGBA:
                return buffer.get_bg_color(x, y)

            # All of text1's characters should have the selection bg
            text1_len = len(text1.plain_text)
            for col in range(text1.x, text1.x + text1_len):
                bg = get_bg_at(col, text1.y)
                bg_matches = (
                    abs(bg.r - expected_bg.r) < 0.01
                    and abs(bg.g - expected_bg.g) < 0.01
                    and abs(bg.b - expected_bg.b) < 0.01
                )
                assert bg_matches, f"text1 col {col}: expected bg ~{expected_bg}, got {bg}"

            # First 10 characters of text2 should have selection bg
            for col in range(text2.x, text2.x + 10):
                bg = get_bg_at(col, text2.y)
                bg_matches = (
                    abs(bg.r - expected_bg.r) < 0.01
                    and abs(bg.g - expected_bg.g) < 0.01
                    and abs(bg.b - expected_bg.b) < 0.01
                )
                assert bg_matches, f"text2 selected col {col}: expected bg ~{expected_bg}, got {bg}"

            # Remaining characters of text2 should NOT have selection bg
            text2_len = len(text2.plain_text)
            for col in range(text2.x + 10, text2.x + text2_len):
                bg = get_bg_at(col, text2.y)
                bg_matches = (
                    abs(bg.r - expected_bg.r) < 0.01
                    and abs(bg.g - expected_bg.g) < 0.01
                    and abs(bg.b - expected_bg.b) < 0.01
                )
                assert not bg_matches, (
                    f"text2 unselected col {col}: expected bg NOT ~{expected_bg}, got {bg}"
                )
        finally:
            setup.destroy()
