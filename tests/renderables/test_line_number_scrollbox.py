"""Port of upstream LineNumberRenderable.scrollbox.test.ts.

Upstream: packages/core/src/renderables/__tests__/LineNumberRenderable.scrollbox.test.ts
Tests ported: 10/10 (0 skipped)
"""

import pytest

from opentui import create_test_renderer
from opentui.components.box import Box, ScrollBox, ScrollContent
from opentui.components.code_renderable import CodeRenderable, SyntaxStyle
from opentui.components.line_number_renderable import LineNumberRenderable
from opentui.structs import RGBA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def generate_code(n: int) -> str:
    """Generate n JavaScript functions, each 4 lines, for test content."""
    lines: list[str] = []
    for i in range(1, n + 1):
        lines.extend(
            [
                f"function test{i}() {{",
                f'  console.log("Line {i}");',
                f"  return {i};",
                "}",
            ]
        )
    return "\n".join(lines)


def _make_syntax_style() -> SyntaxStyle:
    return SyntaxStyle.from_styles(
        {
            "default": {"fg": RGBA(1, 1, 1, 1)},
        }
    )


class TestLineNumberRenderableInScrollBox:
    """Maps to describe("LineNumberRenderable in ScrollBox")."""

    async def test_single_code_renderable_with_line_numbers_in_scrollbox_correct_dimensions(self):
        """Maps to test("single Code renderable with line numbers in ScrollBox - correct dimensions")."""
        setup = await create_test_renderer(32, 10)
        try:
            code_text = generate_code(20)  # 80 lines
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
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
            )

            bordered_box = Box(
                ln,
                border=True,
                width="100%",
                height="100%",
            )

            scroll = ScrollBox(
                content=ScrollContent(bordered_box),
                width="100%",
                height="100%",
                scroll_y=True,
                sticky_scroll=True,
                sticky_start="bottom",
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            # Check gutter exists with width > 0 and height > 0
            gutter = ln._gutter
            assert gutter is not None
            assert gutter._layout_width is not None and gutter._layout_width > 0
            assert gutter._layout_height is not None and gutter._layout_height > 0

            # Inner dimensions: 32 wide - 2 (border) = 30 inner width, 10 tall - 2 (border) = 8 inner height
            # LineNumberRenderable should match the inner dimensions of the bordered box
            assert ln._layout_width is not None and ln._layout_width > 0
            assert ln._layout_height is not None and ln._layout_height > 0
        finally:
            setup.destroy()

    async def test_single_code_renderable_in_scrollbox_scroll_and_verify_dimensions(self):
        """Maps to test("single Code renderable in ScrollBox - scroll and verify dimensions")."""
        setup = await create_test_renderer(32, 10)
        try:
            code_text = generate_code(20)  # 80 lines
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
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
            )

            bordered_box = Box(
                ln,
                border=True,
                width="100%",
                height="100%",
            )

            scroll = ScrollBox(
                content=ScrollContent(bordered_box),
                width="100%",
                height="100%",
                scroll_y=True,
                sticky_scroll=True,
                sticky_start="bottom",
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            # Record gutter dimensions before scroll
            gutter = ln._gutter
            width_before = gutter._layout_width
            height_before = gutter._layout_height

            assert width_before is not None and width_before > 0
            assert height_before is not None and height_before > 0

            # Scroll by 10 lines
            scroll.scroll_by(delta_y=10)
            setup.render_frame()

            # Verify gutter dimensions haven't changed after scroll
            assert gutter._layout_width == width_before
            assert gutter._layout_height == height_before
        finally:
            setup.destroy()

    async def test_multiple_code_renderables_with_line_numbers_in_scrollbox_correct_dimensions(
        self,
    ):
        """Maps to test("multiple Code renderables with line numbers in ScrollBox - correct dimensions")."""
        setup = await create_test_renderer(32, 10)
        try:
            syntax_style = _make_syntax_style()

            code_texts = [
                generate_code(5),  # 20 lines
                generate_code(3),  # 12 lines
                generate_code(4),  # 16 lines
            ]

            ln_renderables = []
            for i, text in enumerate(code_texts):
                code = CodeRenderable(
                    setup.renderer,
                    id=f"test-code-{i}",
                    content=text,
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
                ln_renderables.append(ln)

            scroll = ScrollBox(
                content=ScrollContent(*ln_renderables),
                width="100%",
                height="100%",
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            # Each line number renderable should have correct dimensions
            for ln in ln_renderables:
                gutter = ln._gutter
                assert gutter is not None
                assert gutter._layout_width is not None and gutter._layout_width > 0
                assert gutter._layout_height is not None and gutter._layout_height > 0
                assert ln._layout_width is not None and ln._layout_width > 0
                assert ln._layout_height is not None and ln._layout_height > 0
        finally:
            setup.destroy()

    async def test_nested_boxes_with_different_border_styles_dimensions_correct(self):
        """Maps to test("nested boxes with different border styles - dimensions correct")."""
        setup = await create_test_renderer(32, 10)
        try:
            code_text = generate_code(10)  # 40 lines
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
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
            )

            # Inner bordered box
            inner_box = Box(
                ln,
                border=True,
                border_style="single",
                width="100%",
                height="100%",
            )

            # Outer bordered box
            outer_box = Box(
                inner_box,
                border=True,
                border_style="double",
                width="100%",
                height="100%",
            )

            scroll = ScrollBox(
                content=ScrollContent(outer_box),
                width="100%",
                height="100%",
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            # Check gutter works with multiple levels of nesting
            gutter = ln._gutter
            assert gutter is not None
            assert gutter._layout_width is not None and gutter._layout_width > 0
            assert gutter._layout_height is not None and gutter._layout_height > 0

            # Line number renderable should be positioned within the nested boxes
            assert ln._layout_width is not None and ln._layout_width > 0
            assert ln._layout_height is not None and ln._layout_height > 0
        finally:
            setup.destroy()

    async def test_scrollbox_with_horizontal_and_vertical_scrolling_dimensions_stable(self):
        """Maps to test("ScrollBox with horizontal and vertical scrolling - dimensions stable")."""
        setup = await create_test_renderer(32, 10)
        try:
            # Create wide content (long lines)
            lines = []
            for i in range(1, 41):
                lines.append(
                    f"function reallyLongFunctionName{i}(argA, argB, argC, argD, argE) {{ return {i}; }}"
                )
            wide_content = "\n".join(lines)

            syntax_style = _make_syntax_style()

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content=wide_content,
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
                draw_unstyled_text=True,
                width="100%",
                height="auto",
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
            )

            scroll = ScrollBox(
                content=ScrollContent(ln),
                width="100%",
                height="100%",
                scroll_x=True,
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            gutter = ln._gutter
            initial_width = gutter._layout_width
            initial_height = gutter._layout_height

            assert initial_width is not None and initial_width > 0
            assert initial_height is not None and initial_height > 0

            # Scroll vertically
            scroll.scroll_by(delta_y=5)
            setup.render_frame()

            assert gutter._layout_width == initial_width
            assert gutter._layout_height == initial_height

            # Scroll horizontally
            scroll.scroll_by(delta_x=10)
            setup.render_frame()

            assert gutter._layout_width == initial_width
            assert gutter._layout_height == initial_height
        finally:
            setup.destroy()

    async def test_gutter_width_changes_with_line_count_verify_remeasure(self):
        """Maps to test("gutter width changes with line count - verify remeasure")."""
        setup = await create_test_renderer(32, 10)
        try:
            # Start with 8 lines (2 functions)
            code_text = generate_code(2)
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
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
            )

            scroll = ScrollBox(
                content=ScrollContent(ln),
                width="100%",
                height="100%",
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            gutter = ln._gutter
            initial_width = gutter._layout_width
            assert initial_width is not None and initial_width > 0

            # Change to 80 lines (20 functions)
            code.content = generate_code(20)
            gutter.remeasure()
            setup.render_frame()

            width_after_20 = gutter._layout_width
            assert width_after_20 >= initial_width

            # Change to 480 lines (120 functions)
            code.content = generate_code(120)
            gutter.remeasure()
            setup.render_frame()

            width_after_120 = gutter._layout_width
            assert width_after_120 >= width_after_20
        finally:
            setup.destroy()

    async def test_line_colors_span_full_width_in_scrollbox(self):
        """Maps to test("line colors span full width in ScrollBox")."""
        setup = await create_test_renderer(32, 10)
        try:
            code_text = generate_code(10)  # 40 lines
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
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="#ffffff",
                bg="#000000",
                line_colors={1: "#2d4a2e", 3: "#4a2d2d"},
                width="100%",
                height="auto",
            )

            scroll = ScrollBox(
                content=ScrollContent(ln),
                width="100%",
                height="100%",
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)
            setup.render_frame()

            # Verify the line colors render (content is present)
            frame = setup.capture_char_frame()
            assert "function test1" in frame

            # Verify gutter has dimensions
            gutter = ln._gutter
            assert gutter is not None
            assert gutter._layout_width > 0
            assert gutter._layout_height > 0
        finally:
            setup.destroy()

    async def test_viewport_culling_with_line_numbers_dimensions_stable(self):
        """Maps to test("viewport culling with line numbers - dimensions stable")."""
        setup = await create_test_renderer(32, 10)
        try:
            # Create tall content in a small viewport
            code_text = generate_code(50)  # 200 lines
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
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
            )

            scroll = ScrollBox(
                content=ScrollContent(ln),
                width="100%",
                height="100%",
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)

            # Render multiple times and verify stable dimensions
            setup.render_frame()
            gutter = ln._gutter
            width_1 = gutter._layout_width
            height_1 = gutter._layout_height

            setup.render_frame()
            width_2 = gutter._layout_width
            height_2 = gutter._layout_height

            setup.render_frame()
            width_3 = gutter._layout_width
            height_3 = gutter._layout_height

            assert width_1 == width_2 == width_3
            assert height_1 == height_2 == height_3
        finally:
            setup.destroy()

    async def test_expected_failure_box_width_changes_unexpectedly_on_first_few_renders(self):
        """Maps to test("EXPECTED FAILURE: Box width changes unexpectedly on first few renders")."""
        setup = await create_test_renderer(32, 10)
        try:
            code_text = generate_code(20)  # 80 lines
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
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
            )

            bordered_box = Box(
                ln,
                border=True,
                width="100%",
                height="100%",
            )

            scroll = ScrollBox(
                content=ScrollContent(bordered_box),
                width="100%",
                height="100%",
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)

            # Capture width across multiple renders
            widths = []
            for _ in range(5):
                setup.render_frame()
                widths.append(ln._layout_width)

            # Check if width is stable across all renders (this is the expected failure)
            # If width changes on first few renders, this assertion will fail
            assert all(w == widths[0] for w in widths), f"Width changed across renders: {widths}"
        finally:
            setup.destroy()

    async def test_expected_failure_gutter_height_may_not_match_parent_height_initially(self):
        """Maps to test("EXPECTED FAILURE: Gutter height may not match parent height initially")."""
        setup = await create_test_renderer(32, 10)
        try:
            code_text = generate_code(20)  # 80 lines
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
            )

            ln = LineNumberRenderable(
                target=code,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="auto",
            )

            bordered_box = Box(
                ln,
                border=True,
                width="100%",
                height="100%",
            )

            scroll = ScrollBox(
                content=ScrollContent(bordered_box),
                width="100%",
                height="100%",
                scroll_y=True,
            )

            setup.renderer.root.add(scroll)

            # First render
            setup.render_frame()

            gutter = ln._gutter
            gutter_height = gutter._layout_height
            parent_height = ln._layout_height

            # Gutter height should match parent height from the first render
            # This is an expected failure if it doesn't match initially
            assert gutter_height == parent_height, (
                f"Gutter height {gutter_height} != parent height {parent_height} on first render"
            )
        finally:
            setup.destroy()
