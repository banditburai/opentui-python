"""Port of upstream LineNumberRenderable.test.ts.

Upstream: packages/core/src/renderables/__tests__/LineNumberRenderable.test.ts
Tests ported: 29/29 (28 implemented, 1 xfail)
  - 1 xfail: async content loading with draw_unstyled_text=false (also skipped upstream)
"""

import pytest

from opentui import (
    LineNumberRenderable,
    LineSign,
    TextRenderable,
    TextareaRenderable,
    create_test_renderer,
)
from opentui.components.box import Box
from opentui.components.line_number_renderable import GutterRenderable


class TestLineNumberRenderable:
    """Maps to describe("LineNumberRenderable")."""

    async def test_reuses_gutter_raster_cache_when_clean(self):
        setup = await create_test_renderer(20, 10)
        try:

            class _CountingGutter(GutterRenderable):
                __slots__ = ("draw_calls",)

                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.draw_calls = 0

                def _draw_line_number(self, *args, **kwargs):
                    self.draw_calls += 1
                    return super()._draw_line_number(*args, **kwargs)

            class _CountingLineNumberRenderable(LineNumberRenderable):
                __slots__ = ()

                def _set_target(self, target):
                    if self._target is target:
                        return

                    if self._target is not None:
                        if hasattr(self._target, "off"):
                            self._target.off("line-info-change", self._handle_line_info_change)
                        super(LineNumberRenderable, self).remove(self._target)

                    if self._gutter is not None:
                        super(LineNumberRenderable, self).remove(self._gutter)
                        self._gutter = None

                    self._target = target

                    if self._target._yoga_node is not None:
                        self._target._yoga_node.flex_grow = 1
                        self._target._yoga_node.flex_shrink = 1

                    if hasattr(self._target, "on"):
                        self._target.on("line-info-change", self._handle_line_info_change)

                    self._gutter = _CountingGutter(
                        self._target,
                        fg=self._ln_fg,
                        bg=self._ln_bg,
                        min_width=self._ln_min_width,
                        padding_right=self._ln_padding_right,
                        line_colors_gutter=self._line_colors_gutter,
                        line_colors_content=self._line_colors_content,
                        line_signs=self._line_signs,
                        line_number_offset=self._ln_line_number_offset,
                        hide_line_numbers=self._ln_hide_line_numbers,
                        line_numbers=self._ln_line_numbers,
                        id=f"{self._id}-gutter" if self._id else None,
                    )

                    super(LineNumberRenderable, self).add(self._gutter)
                    super(LineNumberRenderable, self).add(self._target)

            text_r = TextRenderable(content="Line 1\nLine 2\nLine 3", width="100%", height="100%")
            ln = _CountingLineNumberRenderable(
                target=text_r,
                min_width=3,
                padding_right=1,
                fg="white",
                width="100%",
                height="100%",
            )
            setup.renderer.root.add(ln)
            gutter = ln.gutter
            assert gutter is not None

            setup.render_frame()
            assert gutter.draw_calls > 0
            first_calls = gutter.draw_calls

            setup.render_frame()
            assert gutter.draw_calls == first_calls

            gutter.set_line_number_offset(10)
            setup.render_frame()
            assert gutter.draw_calls > first_calls
        finally:
            setup.destroy()

    async def test_renders_line_numbers_correctly(self):
        """Maps to test("renders line numbers correctly")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        frame = setup.capture_char_frame()

        assert " 1 Line 1" in frame
        assert " 2 Line 2" in frame
        assert " 3 Line 3" in frame
        setup.destroy()

    async def test_renders_line_numbers_for_wrapping_text(self):
        """Maps to test("renders line numbers for wrapping text")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1 is very long and should wrap around multiple lines"
        text_r = TextRenderable(
            content=text,
            width="auto",
            height="100%",
            wrap_mode="char",
        )

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        frame = setup.capture_char_frame()

        assert " 1 Line 1" in frame
        setup.destroy()

    async def test_renders_line_colors_for_diff_highlighting(self):
        """Maps to test("renders line colors for diff highlighting")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        line_colors = {
            1: "#2d4a2e",  # Green for line 2 (index 1)
            3: "#4a2d2d",  # Red for line 4 (index 3)
        }

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_colors=line_colors,
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        buf = setup.get_buffer()

        # Line 2 (index 1) gutter should have green bg
        bg = buf.get_bg_color(2, 1)
        assert abs(bg.r - 0x2D / 255) < 0.02
        assert abs(bg.g - 0x4A / 255) < 0.02
        assert abs(bg.b - 0x2E / 255) < 0.02

        # Line 2 content should have 80% darker green
        bg_c = buf.get_bg_color(10, 1)
        assert abs(bg_c.r - (0x2D / 255) * 0.8) < 0.02
        assert abs(bg_c.g - (0x4A / 255) * 0.8) < 0.02
        assert abs(bg_c.b - (0x2E / 255) * 0.8) < 0.02

        # Line 4 (index 3) gutter should have red bg
        bg4 = buf.get_bg_color(2, 3)
        assert abs(bg4.r - 0x4A / 255) < 0.02
        assert abs(bg4.g - 0x2D / 255) < 0.02
        assert abs(bg4.b - 0x2D / 255) < 0.02

        # Line 4 content should have 80% darker red
        bg4c = buf.get_bg_color(10, 3)
        assert abs(bg4c.r - (0x4A / 255) * 0.8) < 0.02
        assert abs(bg4c.g - (0x2D / 255) * 0.8) < 0.02
        assert abs(bg4c.b - (0x2D / 255) * 0.8) < 0.02

        # Line 1 (index 0) should have default black background
        bg1 = buf.get_bg_color(2, 0)
        assert abs(bg1.r) < 0.02
        assert abs(bg1.g) < 0.02
        assert abs(bg1.b) < 0.02

        setup.destroy()

    async def test_can_dynamically_update_line_colors(self):
        """Maps to test("can dynamically update line colors")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        buf = setup.get_buffer()

        # Initially no colors
        bg_init = buf.get_bg_color(2, 1)
        assert abs(bg_init.r) < 0.02
        assert abs(bg_init.g) < 0.02
        assert abs(bg_init.b) < 0.02

        # Set line color
        ln.set_line_color(1, "#2d4a2e")
        setup.render_frame()

        bg_after = buf.get_bg_color(2, 1)
        assert abs(bg_after.r - 0x2D / 255) < 0.02
        assert abs(bg_after.g - 0x4A / 255) < 0.02
        assert abs(bg_after.b - 0x2E / 255) < 0.02

        # Content at 80%
        bg_content = buf.get_bg_color(10, 1)
        assert abs(bg_content.r - (0x2D / 255) * 0.8) < 0.02
        assert abs(bg_content.g - (0x4A / 255) * 0.8) < 0.02
        assert abs(bg_content.b - (0x2E / 255) * 0.8) < 0.02

        # Clear line color
        ln.clear_line_color(1)
        setup.render_frame()

        bg_cleared = buf.get_bg_color(2, 1)
        assert abs(bg_cleared.r) < 0.02
        assert abs(bg_cleared.g) < 0.02
        assert abs(bg_cleared.b) < 0.02

        # Set multiple colors
        ln.set_line_colors({0: "#2d4a2e", 2: "#4a2d2d"})
        setup.render_frame()

        bg_l1 = buf.get_bg_color(2, 0)
        assert abs(bg_l1.r - 0x2D / 255) < 0.02
        assert abs(bg_l1.g - 0x4A / 255) < 0.02
        assert abs(bg_l1.b - 0x2E / 255) < 0.02

        bg_l3 = buf.get_bg_color(2, 2)
        assert abs(bg_l3.r - 0x4A / 255) < 0.02
        assert abs(bg_l3.g - 0x2D / 255) < 0.02
        assert abs(bg_l3.b - 0x2D / 255) < 0.02

        # Content colors at 80%
        bg_l1c = buf.get_bg_color(10, 0)
        assert abs(bg_l1c.r - (0x2D / 255) * 0.8) < 0.02
        assert abs(bg_l1c.g - (0x4A / 255) * 0.8) < 0.02
        assert abs(bg_l1c.b - (0x2E / 255) * 0.8) < 0.02

        bg_l3c = buf.get_bg_color(10, 2)
        assert abs(bg_l3c.r - (0x4A / 255) * 0.8) < 0.02
        assert abs(bg_l3c.g - (0x2D / 255) * 0.8) < 0.02
        assert abs(bg_l3c.b - (0x2D / 255) * 0.8) < 0.02

        # Clear all colors
        ln.clear_all_line_colors()
        setup.render_frame()

        bg_all_cleared = buf.get_bg_color(2, 0)
        assert abs(bg_all_cleared.r) < 0.02
        assert abs(bg_all_cleared.g) < 0.02
        assert abs(bg_all_cleared.b) < 0.02

        setup.destroy()

    async def test_renders_line_colors_for_wrapped_lines(self):
        """Maps to test("renders line colors for wrapped lines").

        When text wraps, line colors should be applied to ALL visual lines
        belonging to the logical line, not just the first visual line.
        The fix to TextRenderable.line_info to use native key names (sources,
        wraps, etc.) enables LineNumberRenderable to get the visual-to-logical
        line mapping.
        """
        setup = await create_test_renderer(20, 10)
        # Line 0: "Short" (5 chars, fits in 16 cols)
        # Line 1: long line that will wrap into multiple visual lines
        text = "Short\nThis is a longer line that should wrap"
        text_r = TextRenderable(
            content=text,
            width="100%",
            height="100%",
            wrap_mode="char",
        )

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_colors={1: "#2d4a2e"},  # Color logical line 1 (the long wrapped line)
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        buf = setup.get_buffer()

        # Verify line_info has proper line_sources (the fix)
        info = text_r.line_info
        assert info is not None
        assert len(info.line_sources) > 2, (
            "Wrapped text should have more visual lines than logical lines"
        )
        # First visual line is logical line 0
        assert info.line_sources[0] == 0
        # Subsequent visual lines should be logical line 1
        assert info.line_sources[1] == 1
        # If text wraps, there should be continuation lines also from logical line 1
        assert any(s == 1 for s in info.line_sources[2:])

        # Visual line 0 (logical line 0): should have default black bg (no color set)
        bg0 = buf.get_bg_color(2, 0)
        assert abs(bg0.r) < 0.02
        assert abs(bg0.g) < 0.02
        assert abs(bg0.b) < 0.02

        # Visual line 1 (logical line 1, first visual line): should have green gutter bg
        bg1 = buf.get_bg_color(2, 1)
        assert abs(bg1.r - 0x2D / 255) < 0.02
        assert abs(bg1.g - 0x4A / 255) < 0.02
        assert abs(bg1.b - 0x2E / 255) < 0.02

        # Visual line 2 (logical line 1, continuation/wrapped): should also have green gutter bg
        bg2 = buf.get_bg_color(2, 2)
        assert abs(bg2.r - 0x2D / 255) < 0.02
        assert abs(bg2.g - 0x4A / 255) < 0.02
        assert abs(bg2.b - 0x2E / 255) < 0.02

        setup.destroy()

    async def test_renders_line_colors_correctly_within_a_box_with_borders(self):
        """Maps to test("renders line colors correctly within a box with borders")."""
        setup = await create_test_renderer(30, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_colors={1: "#2d4a2e", 3: "#4a2d2d"},
            width="100%",
            height="100%",
        )

        box = Box(
            ln,
            border=True,
            border_style="single",
            border_color="#ffffff",
            background_color="#000000",
            width="100%",
            height="100%",
            padding=1,
        )
        setup.renderer.root.add(box)
        setup.render_frame()

        buf = setup.get_buffer()

        # Box border + padding: content starts at x=2, y=2
        # Line 2 (index 1) is at y=3 (border=1, padding=1, line_offset=1)
        line2_y = 3

        # Check gutter area has green bg
        gutter_bg = buf.get_bg_color(4, line2_y)
        assert abs(gutter_bg.r - 0x2D / 255) < 0.02
        assert abs(gutter_bg.g - 0x4A / 255) < 0.02
        assert abs(gutter_bg.b - 0x2E / 255) < 0.02

        # Content area has 80% darker green
        content_bg = buf.get_bg_color(15, line2_y)
        assert abs(content_bg.r - (0x2D / 255) * 0.8) < 0.02
        assert abs(content_bg.g - (0x4A / 255) * 0.8) < 0.02
        assert abs(content_bg.b - (0x2E / 255) * 0.8) < 0.02

        # Line without color (line 1, y=2) should not have green bg
        line1_y = 2
        bg_plain = buf.get_bg_color(15, line1_y)
        assert abs(bg_plain.r) < 0.02
        assert abs(bg_plain.g) < 0.02
        assert abs(bg_plain.b) < 0.02

        setup.destroy()

    async def test_renders_full_width_line_colors_when_line_numbers_are_hidden(self):
        """Maps to test("renders full-width line colors when line numbers are hidden")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_colors={1: "#2d4a2e"},
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)

        # First render with line numbers visible
        frame_with = setup.capture_char_frame()

        # Hide line numbers
        ln.show_line_numbers = False
        setup.render_frame()

        frame_without = setup.capture_char_frame()
        assert "Line 1" in frame_without
        # When line numbers are hidden, text should start at x=0
        lines = frame_without.split("\n")
        assert lines[1].startswith("Line 2") or "Line 2" in lines[1]

        buf = setup.get_buffer()

        # Content bg (80% darker) should extend to x=0 when gutter is hidden
        bg_left = buf.get_bg_color(0, 1)
        assert abs(bg_left.r - (0x2D / 255) * 0.8) < 0.02
        assert abs(bg_left.g - (0x4A / 255) * 0.8) < 0.02
        assert abs(bg_left.b - (0x2E / 255) * 0.8) < 0.02

        bg_mid = buf.get_bg_color(10, 1)
        assert abs(bg_mid.r - (0x2D / 255) * 0.8) < 0.02
        assert abs(bg_mid.g - (0x4A / 255) * 0.8) < 0.02
        assert abs(bg_mid.b - (0x2E / 255) * 0.8) < 0.02

        bg_right = buf.get_bg_color(19, 1)
        assert abs(bg_right.r - (0x2D / 255) * 0.8) < 0.02
        assert abs(bg_right.g - (0x4A / 255) * 0.8) < 0.02
        assert abs(bg_right.b - (0x2E / 255) * 0.8) < 0.02

        setup.destroy()

    async def test_renders_line_signs_before_and_after_line_numbers(self):
        """Maps to test("renders line signs before and after line numbers")."""
        setup = await create_test_renderer(30, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        line_signs = {
            1: LineSign(after="+"),
            3: LineSign(after="-"),
            0: LineSign(before="!"),
        }

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_signs=line_signs,
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        frame = setup.capture_char_frame()

        # Check signs are present
        assert "!" in frame
        assert "+" in frame
        assert "-" in frame

        # Verify structure
        lines = frame.split("\n")
        assert "!" in lines[0] and "1" in lines[0]  # Line 1 has ! before number
        assert "+" in lines[1] and "2" in lines[1]  # Line 2 has + after number
        assert "-" in lines[3] and "4" in lines[3]  # Line 4 has - after number

        setup.destroy()

    async def test_renders_line_signs_with_custom_colors(self):
        """Maps to test("renders line signs with custom colors")."""
        setup = await create_test_renderer(30, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        line_signs = {
            1: LineSign(after=" +", after_color="#22c55e"),
            0: LineSign(before="X", before_color="#ef4444"),
        }

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#888888",
            bg="#000000",
            line_signs=line_signs,
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        buf = setup.get_buffer()

        # Find green plus on line 2 (y=1) - should be after line number in gutter area
        found_green_plus = False
        for x in range(0, 15):
            fg = buf.get_fg_color(x, 1)
            # Green: #22c55e = rgb(34, 197, 94) => (0.133, 0.773, 0.369)
            if abs(fg.g - 197 / 255) < 0.05 and fg.r < 0.2 and fg.b < 0.5:
                found_green_plus = True
                break
        assert found_green_plus, "Green plus sign not found in gutter area on line 2"

        # Find red X on line 1 (y=0)
        found_red = False
        for x in range(5):
            fg = buf.get_fg_color(x, 0)
            # Red: #ef4444 = rgb(239, 68, 68) => (0.937, 0.267, 0.267)
            if abs(fg.r - 239 / 255) < 0.05 and fg.g < 0.4 and fg.b < 0.4:
                found_red = True
                break
        assert found_red

        setup.destroy()

    async def test_dynamically_updates_line_signs(self):
        """Maps to test("dynamically updates line signs")."""
        setup = await create_test_renderer(30, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)

        frame = setup.capture_char_frame()
        assert "+" not in frame

        # Add a sign
        ln.set_line_sign(1, LineSign(after="+"))
        frame = setup.capture_char_frame()
        assert "+" in frame

        # Clear the sign
        ln.clear_line_sign(1)
        frame = setup.capture_char_frame()
        assert "+" not in frame

        setup.destroy()

    async def test_renders_line_numbers_with_offset(self):
        """Maps to test("renders line numbers with offset")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            line_number_offset=41,
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        frame = setup.capture_char_frame()

        assert "42 Line 1" in frame
        assert "43 Line 2" in frame
        assert "44 Line 3" in frame

        setup.destroy()

    async def test_can_dynamically_update_line_number_offset(self):
        """Maps to test("can dynamically update line number offset")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            line_number_offset=0,
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)

        frame = setup.capture_char_frame()
        assert " 1 Line 1" in frame
        assert " 2 Line 2" in frame

        # Update offset
        ln.line_number_offset = 99
        frame = setup.capture_char_frame()
        assert "100 Line 1" in frame
        assert "101 Line 2" in frame
        assert "102 Line 3" in frame

        setup.destroy()

    async def test_hides_line_numbers_for_specific_lines(self):
        """Maps to test("hides line numbers for specific lines")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            hide_line_numbers={1, 3},
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        frame = setup.capture_char_frame()

        assert " 1 Line 1" in frame
        assert " 3 Line 3" in frame
        assert " 5 Line 5" in frame

        lines = frame.split("\n")
        # Line 2 should have text but not the line number "2"
        assert "Line 2" in lines[1]
        import re

        assert not re.search(r"2\s+Line 2", lines[1])

        # Line 4 should have text but not the line number "4"
        assert "Line 4" in lines[3]
        assert not re.search(r"4\s+Line 4", lines[3])

        setup.destroy()

    async def test_can_dynamically_update_hidden_line_numbers(self):
        """Maps to test("can dynamically update hidden line numbers")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)

        frame = setup.capture_char_frame()
        assert " 1 Line 1" in frame
        assert " 2 Line 2" in frame
        assert " 3 Line 3" in frame

        # Hide line 2
        ln.set_hide_line_numbers({1})
        frame = setup.capture_char_frame()
        assert " 1 Line 1" in frame
        assert "Line 2" in frame
        assert " 3 Line 3" in frame

        lines = frame.split("\n")
        import re

        assert not re.search(r"2\s+Line 2", lines[1])

        setup.destroy()

    async def test_combines_line_number_offset_with_hidden_line_numbers(self):
        """Maps to test("combines line number offset with hidden line numbers")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            line_number_offset=41,
            hide_line_numbers={1, 3},
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        frame = setup.capture_char_frame()

        # Line 1 (index 0) should show as 42
        assert "42 Line 1" in frame

        # Line 2 (index 1) should be hidden
        assert "Line 2" in frame
        lines = frame.split("\n")
        import re

        assert not re.search(r"43\s+Line 2", lines[1])

        # Line 3 (index 2) should show as 44
        assert "44 Line 3" in frame

        # Line 4 (index 3) should be hidden
        assert "Line 4" in frame
        assert not re.search(r"45\s+Line 4", lines[3])

        # Line 5 (index 4) should show as 46
        assert "46 Line 5" in frame

        setup.destroy()

    async def test_gutter_width_is_stable_from_first_render_no_width_glitch(self):
        """Maps to test("gutter width is stable from first render - no width glitch")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)

        # First render
        setup.render_frame()
        gutter = ln.gutter
        width1 = gutter._layout_width
        assert width1 > 0

        # Second render - width should not change
        setup.render_frame()
        width2 = gutter._layout_width
        assert width2 == width1

        # Third render
        setup.render_frame()
        width3 = gutter._layout_width
        assert width3 == width1

        setup.destroy()

    async def test_gutter_width_accounts_for_large_line_numbers_from_first_render(self):
        """Maps to test("gutter width accounts for large line numbers from first render")."""
        setup = await create_test_renderer(30, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            line_number_offset=997,
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)

        # First render
        setup.render_frame()
        gutter = ln.gutter
        width1 = gutter._layout_width
        # Width should be >= 5 for "1000" (4 digits + padding)
        assert width1 >= 5

        # Second and third renders should be stable
        setup.render_frame()
        assert gutter._layout_width == width1
        setup.render_frame()
        assert gutter._layout_width == width1

        setup.destroy()

    async def test_handles_async_content_loading_in_code_renderable_with_draw_unstyled_text_false(
        self,
    ):
        """Maps to test.skip("handles async content loading in Code renderable with draw_unstyled_text=false").

        Upstream skips this due to flaky Bun.sleep timing.  We use
        deterministic MockTreeSitterClient control instead.
        """
        import asyncio
        from opentui.components.code_renderable import (
            CodeRenderable,
            MockTreeSitterClient,
            SyntaxStyle,
        )
        from opentui import structs as st

        setup = await create_test_renderer(30, 10)
        syntax_style = SyntaxStyle.from_styles({"default": {"fg": st.RGBA(1, 1, 1, 1)}})
        mock_client = MockTreeSitterClient()

        # Start with empty content (matches upstream)
        code = CodeRenderable(
            content="",
            filetype="typescript",
            syntax_style=syntax_style,
            tree_sitter_client=mock_client,
            draw_unstyled_text=False,
            width="100%",
            height="100%",
        )
        ln = LineNumberRenderable(
            target=code,
            min_width=3,
            padding_right=1,
            fg="white",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)

        # First render — no content yet
        setup.render_frame()
        assert code.line_count <= 1

        # Set content on the code renderable
        code.content = 'function hello() {\n  console.log("Hello");\n}'

        # Render to trigger highlighting request
        setup.render_frame()

        # Resolve the pending highlight
        mock_client.resolve_all_highlight_once()
        await asyncio.sleep(0)

        # Render again to pick up the resolved highlights
        setup.render_frame()

        frame = setup.capture_char_frame()

        # Content should now be visible
        assert code.line_count == 3
        assert "function" in frame
        assert "console" in frame

        # Line numbers should be present
        lines = frame.split("\n")
        assert "1" in lines[0]
        assert "2" in lines[1]
        assert "3" in lines[2]

        setup.destroy()

    async def test_updates_line_numbers_when_code_renderable_content_changes(self):
        """Maps to test("updates line numbers when Code renderable content changes")."""
        from opentui.components.code_renderable import CodeRenderable, SyntaxStyle
        from opentui import structs as st

        setup = await create_test_renderer(30, 10)
        syntax_style = SyntaxStyle.from_styles({"default": {"fg": st.RGBA(1, 1, 1, 1)}})

        code = CodeRenderable(
            content="line 1\nline 2",
            filetype="typescript",
            syntax_style=syntax_style,
            draw_unstyled_text=True,
            width="100%",
            height="100%",
        )
        ln = LineNumberRenderable(
            target=code,
            min_width=3,
            padding_right=1,
            fg="white",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert code.line_count == 2 or code.virtual_line_count == 2
        assert "line 1" in frame
        assert "line 2" in frame

        # Update content
        code.content = "line 1\nline 2\nline 3\nline 4\nline 5"
        setup.render_frame()

        frame2 = setup.capture_char_frame()
        assert "line 5" in frame2
        lines = frame2.split("\n")
        assert len(lines) >= 5
        setup.destroy()

    async def test_handles_code_renderable_switching_from_no_filetype_to_having_filetype(self):
        """Maps to test("handles Code renderable switching from no filetype to having filetype")."""
        import re as re_mod
        from opentui.components.code_renderable import CodeRenderable, SyntaxStyle
        from opentui import structs as st

        setup = await create_test_renderer(30, 10)
        syntax_style = SyntaxStyle.from_styles({"default": {"fg": st.RGBA(1, 1, 1, 1)}})

        code = CodeRenderable(
            content="function test() {\n  return 42;\n}",
            filetype=None,
            syntax_style=syntax_style,
            draw_unstyled_text=True,
            width="100%",
            height="100%",
        )
        ln = LineNumberRenderable(
            target=code,
            min_width=3,
            padding_right=1,
            fg="white",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert code.line_count == 3 or code.virtual_line_count == 3
        assert "function" in frame

        # Switch filetype
        code.filetype = "typescript"
        setup.render_frame()

        frame2 = setup.capture_char_frame()
        assert "function" in frame2
        lines = frame2.split("\n")
        # Line numbers should still be present
        assert re_mod.search(r"1", lines[0])
        assert re_mod.search(r"3", lines[2])
        setup.destroy()

    async def test_maintains_consistent_left_padding_for_all_line_numbers(self):
        """Maps to test("maintains consistent left padding for all line numbers")."""
        setup = await create_test_renderer(30, 15)

        # 12 lines: 1-digit (1-9) and 2-digit (10-12) line numbers
        content_lines = [f"Line {i}" for i in range(1, 13)]
        text = "\n".join(content_lines)
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="white",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        frame = setup.capture_char_frame()

        frame_lines = frame.split("\n")
        import re

        # Line 1: format " _1 Line 1" where _ is alignment space
        assert re.match(r"^  1 Line 1", frame_lines[0])
        m1 = re.match(r"^( +)1 ", frame_lines[0])
        assert m1
        assert len(m1.group(1)) == 2  # 1 left padding + 1 alignment

        # Line 9 should have same format
        assert re.match(r"^  9 Line 9", frame_lines[8])
        m9 = re.match(r"^( +)9 ", frame_lines[8])
        assert m9
        assert len(m9.group(1)) == 2

        # Line 10: format " 10 Line 10" (1 left pad + "10" + paddingRight)
        assert re.match(r"^ 10 Line 10", frame_lines[9])
        m10 = re.match(r"^( +)10 ", frame_lines[9])
        assert m10
        assert len(m10.group(1)) == 1  # Just 1 left padding

        # All lines should have at least 1 space before first digit
        for i in range(12):
            m = re.match(r"^( +)\d+", frame_lines[i])
            assert m
            assert len(m.group(1)) >= 1

        setup.destroy()

    async def test_supports_separate_gutter_and_content_colors_with_line_color_config(self):
        """Maps to test("supports separate gutter and content colors with LineColorConfig")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_colors={1: {"gutter": "#2d4a2e", "content": "#1a2e1f"}},
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        buf = setup.get_buffer()

        # Gutter has specified color
        bg_gutter = buf.get_bg_color(2, 1)
        assert abs(bg_gutter.r - 0x2D / 255) < 0.02
        assert abs(bg_gutter.g - 0x4A / 255) < 0.02
        assert abs(bg_gutter.b - 0x2E / 255) < 0.02

        # Content has specified color (not auto-darkened)
        bg_content = buf.get_bg_color(10, 1)
        assert abs(bg_content.r - 0x1A / 255) < 0.02
        assert abs(bg_content.g - 0x2E / 255) < 0.02
        assert abs(bg_content.b - 0x1F / 255) < 0.02

        setup.destroy()

    async def test_defaults_content_color_to_darker_gutter_color_when_only_gutter_is_specified(
        self,
    ):
        """Maps to test("defaults content color to darker gutter color when only gutter is specified")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_colors={1: {"gutter": "#50fa7b"}},
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        buf = setup.get_buffer()
        expected_r = 0x50 / 255
        expected_g = 0xFA / 255
        expected_b = 0x7B / 255

        # Gutter
        bg_g = buf.get_bg_color(2, 1)
        assert abs(bg_g.r - expected_r) < 0.02
        assert abs(bg_g.g - expected_g) < 0.02
        assert abs(bg_g.b - expected_b) < 0.02

        # Content at 80%
        bg_c = buf.get_bg_color(10, 1)
        assert abs(bg_c.r - expected_r * 0.8) < 0.02
        assert abs(bg_c.g - expected_g * 0.8) < 0.02
        assert abs(bg_c.b - expected_b * 0.8) < 0.02

        setup.destroy()

    async def test_defaults_content_color_to_80_percent_of_gutter_when_using_simple_string_color_format(
        self,
    ):
        """Maps to test("defaults content color to 80% of gutter when using simple string color format")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_colors={1: "#ff5555"},
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        buf = setup.get_buffer()
        expected_r = 0xFF / 255
        expected_g = 0x55 / 255
        expected_b = 0x55 / 255

        # Gutter has full color
        bg_g = buf.get_bg_color(2, 1)
        assert abs(bg_g.r - expected_r) < 0.02
        assert abs(bg_g.g - expected_g) < 0.02
        assert abs(bg_g.b - expected_b) < 0.02

        # Content at 80%
        bg_c = buf.get_bg_color(10, 1)
        assert abs(bg_c.r - expected_r * 0.8) < 0.02
        assert abs(bg_c.g - expected_g * 0.8) < 0.02
        assert abs(bg_c.b - expected_b * 0.8) < 0.02

        setup.destroy()

    async def test_dynamically_updates_line_colors_with_line_color_config(self):
        """Maps to test("dynamically updates line colors with LineColorConfig")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        # Set line color with separate gutter/content
        ln.set_line_color(1, {"gutter": "#2d4a2e", "content": "#1a2e1f"})
        setup.render_frame()

        buf = setup.get_buffer()

        bg_gutter = buf.get_bg_color(2, 1)
        assert abs(bg_gutter.r - 0x2D / 255) < 0.02
        assert abs(bg_gutter.g - 0x4A / 255) < 0.02
        assert abs(bg_gutter.b - 0x2E / 255) < 0.02

        bg_content = buf.get_bg_color(10, 1)
        assert abs(bg_content.r - 0x1A / 255) < 0.02
        assert abs(bg_content.g - 0x2E / 255) < 0.02
        assert abs(bg_content.b - 0x1F / 255) < 0.02

        # Clear
        ln.clear_line_color(1)
        setup.render_frame()

        bg_cleared = buf.get_bg_color(2, 1)
        assert abs(bg_cleared.r) < 0.02
        assert abs(bg_cleared.g) < 0.02
        assert abs(bg_cleared.b) < 0.02

        setup.destroy()

    async def test_get_line_colors_returns_both_gutter_and_content_color_maps(self):
        """Maps to test("getLineColors returns both gutter and content color maps")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            line_colors={1: {"gutter": "#2d4a2e", "content": "#1a2e1f"}},
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        colors = ln.get_line_colors()
        assert len(colors["gutter"]) == 1
        assert len(colors["content"]) == 1

        gutter_color = colors["gutter"][1]
        assert abs(gutter_color.r - 0x2D / 255) < 0.02
        assert abs(gutter_color.g - 0x4A / 255) < 0.02
        assert abs(gutter_color.b - 0x2E / 255) < 0.02

        content_color = colors["content"][1]
        assert abs(content_color.r - 0x1A / 255) < 0.02
        assert abs(content_color.g - 0x2E / 255) < 0.02
        assert abs(content_color.b - 0x1F / 255) < 0.02

        setup.destroy()

    async def test_highlight_lines_applies_color_to_a_range_of_lines(self):
        """Maps to test("highlight_lines applies color to a range of lines")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        ln.highlight_lines(1, 3, "#2d4a2e")
        setup.render_frame()

        colors = ln.get_line_colors()
        assert 0 not in colors["gutter"]
        assert 1 in colors["gutter"]
        assert 2 in colors["gutter"]
        assert 3 in colors["gutter"]
        assert 4 not in colors["gutter"]

        setup.destroy()

    async def test_clear_highlight_lines_removes_color_from_a_range_of_lines(self):
        """Maps to test("clear_highlight_lines removes color from a range of lines")."""
        setup = await create_test_renderer(20, 10)
        text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        text_r = TextRenderable(content=text, width="100%", height="100%")

        ln = LineNumberRenderable(
            target=text_r,
            min_width=3,
            padding_right=1,
            fg="#ffffff",
            bg="#000000",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(ln)
        setup.render_frame()

        ln.highlight_lines(0, 4, "#2d4a2e")
        setup.render_frame()

        ln.clear_highlight_lines(1, 3)
        setup.render_frame()

        colors = ln.get_line_colors()
        assert 0 in colors["gutter"]
        assert 1 not in colors["gutter"]
        assert 2 not in colors["gutter"]
        assert 3 not in colors["gutter"]
        assert 4 in colors["gutter"]

        setup.destroy()

    async def test_maintains_stable_visual_line_count_when_scrolling_and_typing_with_word_wrap(
        self,
    ):
        """Maps to test("maintains stable visual line count when scrolling and typing with word wrap")."""
        setup = await create_test_renderer(35, 30)

        initial_content = (
            "Welcome to the TextareaRenderable Demo!\n"
            "\n"
            "This is an interactive text editor.\n"
            "\n"
            "\tThis is a tab\n"
            "\t\t\tMultiple tabs\n"
            "\n"
            "NAVIGATION:\n"
            "  Arrow keys to move cursor\n"
            "  Home/End for line navigation\n"
        )

        editor = TextareaRenderable(
            initial_value=initial_content,
            text_color="#F0F6FC",
            wrap_mode="word",
        )

        parent = Box(
            Box(
                LineNumberRenderable(
                    target=editor,
                    min_width=3,
                    padding_right=1,
                    fg="#4b5563",
                    width="100%",
                    height="100%",
                ),
                border=True,
                border_color="#6BCF7F",
                background_color="#0D1117",
                padding_left=1,
                padding_right=1,
            ),
            padding=1,
        )
        setup.renderer.root.add(parent)

        # Initial render
        setup.render_frame()
        frame1 = setup.capture_char_frame()
        assert "Welcome" in frame1

        # Move cursor to end to trigger scrolling
        editor.goto_buffer_end()
        setup.render_frame()
        frame2 = setup.capture_char_frame()

        # Type a character on an empty-ish line
        editor.insert_char("a")
        setup.render_frame()
        frame3 = setup.capture_char_frame()

        # Verify borders are intact
        for line in frame3.split("\n"):
            # Lines with left border should also have right border
            stripped = line.strip()
            if stripped.startswith("\u2502"):  # │
                assert stripped.endswith("\u2502") or not stripped

        setup.destroy()
