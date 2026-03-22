"""Port of upstream LineNumberRenderable.scrollbox-simple.test.ts.

Upstream: packages/core/src/renderables/__tests__/LineNumberRenderable.scrollbox-simple.test.ts
Tests ported: 2/2 (0 skipped)
"""

from opentui import create_test_renderer
from opentui.components.scrollbox import ScrollBox, ScrollContent
from opentui.components.code_renderable import CodeRenderable, SyntaxStyle
from opentui.components.line_number_renderable import LineNumberRenderable
from opentui.structs import RGBA


def _make_syntax_style() -> SyntaxStyle:
    return SyntaxStyle.from_styles(
        {
            "default": {"fg": RGBA(1, 1, 1, 1)},
        }
    )


class TestLineNumberInScrollBoxSimpleCoreTest:
    """Maps to describe("LineNumber in ScrollBox - Simple Core Test")."""

    async def test_line_number_with_code_in_scroll_box_should_wrap_content_height(self):
        """Maps to test("LineNumber with Code in ScrollBox should wrap content height")."""
        setup = await create_test_renderer(40, 40)
        try:
            code_text = "function test() {\n  return true;\n}"
            syntax_style = _make_syntax_style()

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content=code_text,
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
                draw_unstyled_text=True,
                width="100%",
                height="auto",
                flex_shrink=0,
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
                flex_shrink=0,
            )

            scroll = ScrollBox(
                content=ScrollContent(ln),
                width=40,
                height=40,
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            # LineNumberRenderable should wrap to content height (3 lines),
            # NOT fill the entire viewport (40 lines).
            ln_height = ln._layout_height
            assert ln_height is not None
            assert ln_height <= 10, (
                f"LineNumberRenderable height {ln_height} should wrap to content "
                f"height (~3), not viewport height (40)"
            )
            # Should be at least the number of content lines
            assert ln_height >= 3, (
                f"LineNumberRenderable height {ln_height} should be at least content line count (3)"
            )
        finally:
            setup.destroy()

    async def test_multiple_line_number_blocks_in_scroll_box_should_each_wrap_content(self):
        """Maps to test("Multiple LineNumber blocks in ScrollBox should each wrap content")."""
        setup = await create_test_renderer(40, 40)
        try:
            syntax_style = _make_syntax_style()

            # Block 1: single line
            code1 = CodeRenderable(
                setup.renderer,
                id="test-code-1",
                content="const x = 1;",
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
                draw_unstyled_text=True,
                width="100%",
                height="auto",
                flex_shrink=0,
            )

            ln1 = LineNumberRenderable(
                target=code1,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
                flex_shrink=0,
            )

            # Block 2: single line
            code2 = CodeRenderable(
                setup.renderer,
                id="test-code-2",
                content="const y = 2;",
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
                draw_unstyled_text=True,
                width="100%",
                height="auto",
                flex_shrink=0,
            )

            ln2 = LineNumberRenderable(
                target=code2,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
                flex_shrink=0,
            )

            scroll = ScrollBox(
                content=ScrollContent(ln1, ln2),
                width=40,
                height=40,
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            # Each LineNumberRenderable should independently wrap to its content height (1),
            # not the viewport height (40).
            ln1_height = ln1._layout_height
            ln2_height = ln2._layout_height

            assert ln1_height is not None
            assert ln2_height is not None

            assert ln1_height <= 5, (
                f"LineNumberRenderable 1 height {ln1_height} should wrap to "
                f"content height (~1), not viewport height (40)"
            )
            assert ln1_height >= 1

            assert ln2_height <= 5, (
                f"LineNumberRenderable 2 height {ln2_height} should wrap to "
                f"content height (~1), not viewport height (40)"
            )
            assert ln2_height >= 1
        finally:
            setup.destroy()
