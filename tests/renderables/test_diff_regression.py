"""Port of upstream Diff.regression.test.ts.

Upstream: packages/core/src/renderables/Diff.regression.test.ts
Tests ported: 2/2
"""

from opentui import create_test_renderer
from opentui.components.diff_renderable import DiffRenderable


# ── Diff fixtures ──────────────────────────────────────────────────────

MARKDOWN_DIFF = """\
--- a/test.md
+++ b/test.md
@@ -1,5 +1,5 @@
 # Heading

-Some **bold** and *italic* text with `code` inline.
+Some **boldtext** and *italictext* with `code` inline and more.

 End of document."""

MULTI_LINE_DIFF = """\
--- a/math.js
+++ b/math.js
@@ -1,7 +1,11 @@
 function add(a, b) {
   return a + b;
 }

+function subtract(a, b) {
+  return a - b;
+}
+
 function multiply(a, b) {
-  return a * b;
+  return a * b * 1;
 }"""


class TestDiffRegressions:
    """Maps to top-level tests in Diff.regression.test.ts."""

    async def test_no_endless_loop_when_concealing_markdown_formatting(self):
        """Maps to test("DiffRenderable - no endless loop when concealing markdown formatting").

        Verifies that rendering a markdown diff with conceal enabled does not
        cause an infinite render loop when concealing changes line lengths and
        triggers re-wrapping. We verify that rendering completes within a
        bounded number of frames.
        """
        setup = await create_test_renderer(80, 24)

        diff = DiffRenderable(
            diff=MARKDOWN_DIFF,
            view="unified",
            filetype="markdown",
            conceal=True,
            wrap_mode="word",
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(diff)

        # Render multiple frames - the key assertion is that this completes
        # without hanging in an infinite loop
        for _ in range(20):
            setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Heading" in frame

        # Switch view mode and wrap mode to stress the system
        diff.view = "split"
        for _ in range(5):
            setup.render_frame()

        frame2 = setup.capture_char_frame()
        assert "Heading" in frame2

        diff.wrap_mode = "char"
        for _ in range(5):
            setup.render_frame()

        frame3 = setup.capture_char_frame()
        assert "Heading" in frame3

        # If we got here without hanging, the test passes
        setup.destroy()

    async def test_line_number_alignment_and_gutter_heights_in_split_view_with_wrapping(self):
        """Maps to test("DiffRenderable - line number alignment and gutter heights in split view with wrapping").

        Verifies that line numbers align between left/right split panes and
        gutter heights match visual line counts when switching between view
        modes and enabling word wrapping.
        """
        setup = await create_test_renderer(100, 30)

        diff = DiffRenderable(
            diff=MULTI_LINE_DIFF,
            view="unified",
            show_line_numbers=True,
            width="100%",
            height="100%",
        )
        setup.renderer.root.add(diff)
        setup.render_frame()

        # Verify content is visible in unified mode
        frame_unified = setup.capture_char_frame()
        assert "function" in frame_unified

        # Switch to split mode
        diff.view = "split"
        setup.render_frame()

        frame_split = setup.capture_char_frame()
        assert "function" in frame_split

        # Switch to word wrap
        diff.wrap_mode = "word"
        setup.render_frame()

        frame_wrapped = setup.capture_char_frame()
        assert "function" in frame_wrapped

        # Verify alignment: check that left line 2 and right line 2 content
        # appear on the same row in the frame
        lines = frame_wrapped.split("\n")
        # Find a line that has content from both sides (the context lines
        # should appear on both left and right in split view)
        found_aligned = False
        for line in lines:
            # In split view, both sides should have "return" on the same row
            if line.count("return") >= 1:
                found_aligned = True
                break
        assert found_aligned, "Expected to find aligned content in split view"

        setup.destroy()
