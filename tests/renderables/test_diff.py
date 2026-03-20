"""Port of upstream Diff.test.ts.

Upstream: packages/core/src/renderables/Diff.test.ts
Tests ported: 72/72
"""

import re

import pytest

from opentui import TestSetup, create_test_renderer
from opentui.components.diff_renderable import DiffRenderable
from opentui.structs import RGBA

# ── Diff fixtures ──────────────────────────────────────────────────────

SIMPLE_DIFF = """\
--- a/test.js
+++ b/test.js
@@ -1,3 +1,3 @@
 function hello() {
-  console.log("Hello");
+  console.log("Hello, World!");
 }"""

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

ADD_ONLY_DIFF = """\
--- a/new.js
+++ b/new.js
@@ -0,0 +1,3 @@
+function newFunction() {
+  return true;
+}"""

REMOVE_ONLY_DIFF = """\
--- a/old.js
+++ b/old.js
@@ -1,3 +0,0 @@
-function oldFunction() {
-  return false;
-}"""

LARGE_DIFF = """\
--- a/large.js
+++ b/large.js
@@ -42,9 +42,10 @@
 const line42 = 'context';
 const line43 = 'context';
-const line44 = 'removed';
+const line44 = 'added';
 const line45 = 'context';
+const line46 = 'added';
 const line47 = 'context';
 const line48 = 'context';
-const line49 = 'removed';
+const line49 = 'changed';
 const line50 = 'context';
 const line51 = 'context';"""


# ── Helpers ────────────────────────────────────────────────────────────


async def _make(
    diff: str = "",
    view: str = "unified",
    width: int = 80,
    height: int = 20,
    show_line_numbers: bool = True,
    wrap_mode: str | None = None,
    conceal: bool = False,
    fg: str | RGBA | None = None,
    filetype: str | None = None,
    added_bg: str | None = None,
    removed_bg: str | None = None,
    added_sign_color: str | None = None,
    removed_sign_color: str | None = None,
    added_content_bg: str | None = None,
    removed_content_bg: str | None = None,
    context_content_bg: str | None = None,
    **extra_kw,
) -> tuple[TestSetup, DiffRenderable]:
    """Create a test renderer with a DiffRenderable added to root."""
    setup = await create_test_renderer(width, height)

    kw: dict = dict(
        id="test-diff",
        diff=diff,
        view=view,
        show_line_numbers=show_line_numbers,
        width="100%",
        height="100%",
    )
    if wrap_mode is not None:
        kw["wrap_mode"] = wrap_mode
    if conceal:
        kw["conceal"] = conceal
    if fg is not None:
        kw["fg"] = fg
    if filetype is not None:
        kw["filetype"] = filetype
    if added_bg is not None:
        kw["added_bg"] = added_bg
    if removed_bg is not None:
        kw["removed_bg"] = removed_bg
    if added_sign_color is not None:
        kw["added_sign_color"] = added_sign_color
    if removed_sign_color is not None:
        kw["removed_sign_color"] = removed_sign_color
    if added_content_bg is not None:
        kw["added_content_bg"] = added_content_bg
    if removed_content_bg is not None:
        kw["removed_content_bg"] = removed_content_bg
    if context_content_bg is not None:
        kw["context_content_bg"] = context_content_bg
    kw.update(extra_kw)

    dr = DiffRenderable(**kw)
    setup.renderer.root.add(dr)
    setup.render_frame()
    return setup, dr


def _frame(setup: TestSetup) -> str:
    """Capture a frame as plain text."""
    return setup.capture_char_frame()


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDiffRenderable:
    """Maps to top-level test() calls in Diff.test.ts (no describe blocks)."""

    async def test_reuses_raster_cache_when_diff_is_clean(self):
        setup = await create_test_renderer(80, 20)
        try:
            class _CountingDiff(DiffRenderable):
                __slots__ = ("unified_calls",)

                def __init__(self, **kwargs):
                    super().__init__(**kwargs)
                    self.unified_calls = 0

                def _render_unified(self, buffer, x, y, width, height):
                    self.unified_calls += 1
                    return super()._render_unified(buffer, x, y, width, height)

            diff = _CountingDiff(
                id="counting-diff",
                diff=SIMPLE_DIFF,
                view="unified",
                width="100%",
                height="100%",
            )
            setup.renderer.root.add(diff)

            setup.render_frame()
            assert diff.unified_calls == 1

            setup.render_frame()
            assert diff.unified_calls == 1

            diff.fg = "#ffcc00"
            setup.render_frame()
            assert diff.unified_calls == 2
        finally:
            setup.destroy()

    async def test_basic_construction_with_unified_view(self):
        """Maps to test("DiffRenderable - basic construction with unified view")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")
        assert dr.diff == SIMPLE_DIFF
        assert dr.view == "unified"
        setup.destroy()

    async def test_basic_construction_with_split_view(self):
        """Maps to test("DiffRenderable - basic construction with split view")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="split")
        assert dr.diff == SIMPLE_DIFF
        assert dr.view == "split"
        setup.destroy()

    async def test_defaults_to_unified_view(self):
        """Maps to test("DiffRenderable - defaults to unified view")."""
        setup, dr = await _make(diff=SIMPLE_DIFF)
        assert dr.view == "unified"
        setup.destroy()

    async def test_unified_view_renders_correctly(self):
        """Maps to test("DiffRenderable - unified view renders correctly")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")
        frame = _frame(setup)

        # Both removed and added lines should be present
        assert 'console.log("Hello")' in frame
        assert 'console.log("Hello, World!")' in frame
        setup.destroy()

    async def test_split_view_renders_correctly(self):
        """Maps to test("DiffRenderable - split view renders correctly")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="split")
        frame = _frame(setup)

        # In split view, both sides should be visible
        assert "console.log" in frame
        assert "Hello" in frame
        assert "World" in frame
        setup.destroy()

    async def test_multi_line_diff_unified_view(self):
        """Maps to test("DiffRenderable - multi-line diff unified view")."""
        setup, dr = await _make(diff=MULTI_LINE_DIFF, view="unified")
        frame = _frame(setup)

        # Check for additions
        assert "function subtract" in frame
        # Check for modifications
        assert "a * b * 1" in frame
        setup.destroy()

    async def test_multi_line_diff_split_view(self):
        """Maps to test("DiffRenderable - multi-line diff split view")."""
        setup, dr = await _make(diff=MULTI_LINE_DIFF, view="split")
        frame = _frame(setup)

        # Left side should have old code
        assert "a * b" in frame
        # Right side should have new code
        assert "subtract" in frame
        setup.destroy()

    async def test_add_only_diff_unified_view(self):
        """Maps to test("DiffRenderable - add-only diff unified view")."""
        setup, dr = await _make(diff=ADD_ONLY_DIFF, view="unified")
        frame = _frame(setup)
        assert "newFunction" in frame
        setup.destroy()

    async def test_add_only_diff_split_view(self):
        """Maps to test("DiffRenderable - add-only diff split view")."""
        setup, dr = await _make(diff=ADD_ONLY_DIFF, view="split")
        frame = _frame(setup)
        # Right side should have the new function
        assert "newFunction" in frame
        setup.destroy()

    async def test_remove_only_diff_unified_view(self):
        """Maps to test("DiffRenderable - remove-only diff unified view")."""
        setup, dr = await _make(diff=REMOVE_ONLY_DIFF, view="unified")
        frame = _frame(setup)
        assert "oldFunction" in frame
        setup.destroy()

    async def test_remove_only_diff_split_view(self):
        """Maps to test("DiffRenderable - remove-only diff split view")."""
        setup, dr = await _make(diff=REMOVE_ONLY_DIFF, view="split")
        frame = _frame(setup)
        # Left side should have the old function
        assert "oldFunction" in frame
        setup.destroy()

    async def test_large_line_numbers_displayed_correctly(self):
        """Maps to test("DiffRenderable - large line numbers displayed correctly")."""
        setup, dr = await _make(diff=LARGE_DIFF, view="unified", show_line_numbers=True)
        frame = _frame(setup)

        # Check that line numbers in the 40s are displayed
        assert re.search(r"4[0-9]", frame)
        setup.destroy()

    async def test_can_toggle_view_mode(self):
        """Maps to test("DiffRenderable - can toggle view mode")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")
        unified_frame = _frame(setup)
        assert dr.view == "unified"

        # Switch to split view
        dr.view = "split"
        split_frame = _frame(setup)
        assert dr.view == "split"

        # Frames should be different
        assert unified_frame != split_frame
        setup.destroy()

    async def test_can_update_diff_content(self):
        """Maps to test("DiffRenderable - can update diff content")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")
        frame1 = _frame(setup)
        assert "Hello" in frame1

        # Update diff
        dr.diff = MULTI_LINE_DIFF
        frame2 = _frame(setup)
        assert "subtract" in frame2
        assert 'console.log("Hello")' not in frame2
        setup.destroy()

    async def test_can_toggle_line_numbers(self):
        """Maps to test("DiffRenderable - can toggle line numbers")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", show_line_numbers=True)
        assert dr.show_line_numbers is True

        # Hide line numbers
        dr.show_line_numbers = False
        _frame(setup)
        assert dr.show_line_numbers is False
        setup.destroy()

    async def test_can_update_filetype(self):
        """Maps to test("DiffRenderable - can update filetype")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", filetype="javascript")
        _frame(setup)
        assert dr.filetype == "javascript"

        # Update filetype
        dr.filetype = "typescript"
        assert dr.filetype == "typescript"
        setup.destroy()

    async def test_handles_empty_diff(self):
        """Maps to test("DiffRenderable - handles empty diff")."""
        setup, dr = await _make(diff="", view="unified")
        _frame(setup)  # should not crash
        assert dr.diff == ""
        setup.destroy()

    async def test_handles_diff_with_no_changes(self):
        """Maps to test("DiffRenderable - handles diff with no changes")."""
        no_change_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,3 +1,3 @@
 function hello() {
   console.log("Hello");
 }"""
        setup, dr = await _make(diff=no_change_diff, view="unified")
        frame = _frame(setup)
        assert "function hello" in frame
        setup.destroy()

    async def test_can_update_wrapmode(self):
        """Maps to test("DiffRenderable - can update wrap_mode")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", wrap_mode="word")
        _frame(setup)
        assert dr.wrap_mode == "word"

        dr.wrap_mode = "char"
        assert dr.wrap_mode == "char"
        setup.destroy()

    async def test_split_view_alignment_with_empty_lines(self):
        """Maps to test("DiffRenderable - split view alignment with empty lines")."""
        alignment_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,2 +1,5 @@
 line1
+line2_added
+line3_added
+line4_added
 line5"""
        setup, dr = await _make(diff=alignment_diff, view="split")
        frame = _frame(setup)

        assert "line1" in frame
        assert "line5" in frame
        assert "line2_added" in frame
        setup.destroy()

    async def test_context_lines_shown_on_both_sides_in_split_view(self):
        """Maps to test("DiffRenderable - context lines shown on both sides in split view")."""
        setup, dr = await _make(diff=MULTI_LINE_DIFF, view="split")
        frame = _frame(setup)

        # Context lines should appear on both sides
        assert "function add" in frame
        assert "function multiply" in frame
        setup.destroy()

    async def test_custom_colors_applied_correctly(self):
        """Maps to test("DiffRenderable - custom colors applied correctly")."""
        setup, dr = await _make(
            diff=SIMPLE_DIFF,
            view="unified",
            added_bg="#00ff00",
            removed_bg="#ff0000",
            added_sign_color="#00ff00",
            removed_sign_color="#ff0000",
        )
        frame = _frame(setup)

        # Should not crash with custom colors
        assert 'console.log("Hello")' in frame
        setup.destroy()

    async def test_line_numbers_hidden_for_empty_alignment_lines_in_split_view(self):
        """Maps to test("DiffRenderable - line numbers hidden for empty alignment lines in split view")."""
        setup, dr = await _make(
            diff=ADD_ONLY_DIFF,
            view="split",
            show_line_numbers=True,
        )
        frame = _frame(setup)

        # Right side should have line numbers for new lines
        # Left side should have empty lines without line numbers
        # The important thing is it renders without crashing
        assert "newFunction" in frame
        setup.destroy()

    async def test_stable_rendering_across_multiple_frames(self):
        """Maps to test("DiffRenderable - stable rendering across multiple frames (no visual glitches)")."""
        setup, dr = await _make(diff=MULTI_LINE_DIFF, view="unified", show_line_numbers=True)

        first_frame = _frame(setup)
        second_frame = _frame(setup)
        third_frame = _frame(setup)

        # All frames should be identical
        assert first_frame == second_frame
        assert second_frame == third_frame

        # Verify content is present
        assert "function add" in first_frame
        assert "function subtract" in first_frame
        assert "function multiply" in first_frame

        # Verify line numbers are present and properly aligned
        frame_lines = first_frame.split("\n")
        lines_with_line_numbers = [ln for ln in frame_lines if re.match(r"^\s*\d+\s+", ln)]

        # Should have multiple lines with line numbers
        assert len(lines_with_line_numbers) > 5

        # All line numbers should have the same width (stable gutter)
        line_number_widths = []
        for line in lines_with_line_numbers:
            m = re.match(r"^(\s*\d+)\s", line)
            if m:
                line_number_widths.append(len(m.group(1)))

        line_number_widths = [w for w in line_number_widths if w > 0]
        unique_widths = set(line_number_widths)
        assert len(unique_widths) == 1  # Gutter width should be consistent
        setup.destroy()

    async def test_can_be_constructed_without_diff_and_set_via_setter(self):
        """Maps to test("DiffRenderable - can be constructed without diff and set via setter")."""
        setup, dr = await _make(diff="", view="unified")
        frame = _frame(setup)
        assert frame.strip() == ""

        # Now set diff via setter
        dr.diff = SIMPLE_DIFF
        frame = _frame(setup)
        assert "function hello" in frame
        assert 'console.log("Hello")' in frame
        assert 'console.log("Hello, World!")' in frame
        setup.destroy()

    async def test_consistent_left_padding_for_line_numbers_greater_than_9(self):
        """Maps to test("DiffRenderable - consistent left padding for line numbers > 9")."""
        diff_with_10_plus = """\
--- a/test.js
+++ b/test.js
@@ -8,7 +8,9 @@
 line8
 line9
-line10_old
+line10_new
 line11
+line12_added
+line13_added
 line14
 line15
-line16_old
+line16_new"""
        setup, dr = await _make(diff=diff_with_10_plus, view="unified", show_line_numbers=True)
        frame = _frame(setup)

        frame_lines = frame.split("\n")

        # Line 8 should be present
        line8 = next((ln for ln in frame_lines if "line8" in ln), None)
        assert line8 is not None
        assert re.search(r"\d+\s", line8)

        # Line 10 should be present
        line10 = next((ln for ln in frame_lines if "line10" in ln), None)
        assert line10 is not None

        # Line 16 should be present
        line16 = next((ln for ln in frame_lines if "line16" in ln), None)
        assert line16 is not None
        setup.destroy()

    async def test_line_numbers_are_correct_in_unified_view(self):
        """Maps to test("DiffRenderable - line numbers are correct in unified view")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", show_line_numbers=True)
        frame = _frame(setup)
        frame_lines = frame.split("\n")

        # Line 2 is removed (old file line 2)
        removed_line = next((ln for ln in frame_lines if 'console.log("Hello");' in ln), None)
        assert removed_line is not None
        assert re.search(r"^\s*2\s+-", removed_line)

        # Line 2 is added (new file line 2)
        added_line = next((ln for ln in frame_lines if 'console.log("Hello, World!")' in ln), None)
        assert added_line is not None
        assert re.search(r"^\s*2\s+\+", added_line)
        setup.destroy()

    async def test_line_numbers_are_correct_in_split_view(self):
        """Maps to test("DiffRenderable - line numbers are correct in split view")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="split", show_line_numbers=True)
        frame = _frame(setup)
        frame_lines = frame.split("\n")

        # In split view, both sides are on the same terminal line
        split_line = next((ln for ln in frame_lines if 'console.log("Hello, World!")' in ln), None)
        assert split_line is not None
        # Should contain line 2 with - on left side
        assert re.search(r"^\s*2\s+-", split_line)
        # Should contain line 2 with + on right side
        assert re.search(r"2\s+\+.*console\.log\(\"Hello, World!\"\)", split_line)
        setup.destroy()

    async def test_split_view_should_not_wrap_lines_prematurely(self):
        """Maps to test("DiffRenderable - split view should not wrap lines prematurely")."""
        long_line_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,4 +1,4 @@
 class Calculator {
-  subtract(a: number, b: number): number {
+  subtract(a: number, b: number, c: number = 0): number {
   return a - b;
 }"""
        setup, dr = await _make(
            diff=long_line_diff,
            view="split",
            show_line_numbers=True,
            wrap_mode="word",
        )
        frame = _frame(setup)
        frame_lines = frame.split("\n")

        # Find the line with "subtract" on the left side
        left_subtract = next(
            (ln for ln in frame_lines if "subtract" in ln and "b: number):" in ln),
            None,
        )
        assert left_subtract is not None

        # The line should contain the full method signature
        assert re.search(r"subtract\(a: number, b: number\):", left_subtract)

        # Right side should have subtract lines
        right_subtract_lines = [ln for ln in frame_lines if "subtract" in ln or "c: number" in ln]
        assert len(right_subtract_lines) > 0
        setup.destroy()

    async def test_split_view_alignment_with_calculator_diff(self):
        """Maps to test("DiffRenderable - split view alignment with calculator diff")."""
        calculator_diff = """\
--- a/calculator.ts
+++ b/calculator.ts
@@ -1,13 +1,20 @@
 class Calculator {
   add(a: number, b: number): number {
     return a + b;
   }

-  subtract(a: number, b: number): number {
-    return a - b;
+  subtract(a: number, b: number, c: number = 0): number {
+    return a - b - c;
   }

   multiply(a: number, b: number): number {
     return a * b;
   }
+
+  divide(a: number, b: number): number {
+    if (b === 0) {
+      throw new Error("Division by zero");
+    }
+    return a / b;
+  }
 }"""
        setup, dr = await _make(
            diff=calculator_diff,
            view="split",
            show_line_numbers=True,
            wrap_mode="none",
        )
        frame = _frame(setup)
        frame_lines = frame.split("\n")

        # Find the closing brace on the left (old line 13)
        left_closing = next((ln for ln in frame_lines if re.match(r"^\s*13\s+\}", ln)), None)
        assert left_closing is not None

        # Find the closing brace on the right (new line 20)
        right_closing = next((ln for ln in frame_lines if re.search(r"\s*20\s+\}", ln)), None)
        assert right_closing is not None

        # They should be on the SAME line in the output
        assert left_closing == right_closing
        setup.destroy()

    async def test_switching_between_unified_and_split_views_multiple_times(self):
        """Maps to test("DiffRenderable - switching between unified and split views multiple times")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", show_line_numbers=True)

        # Step 1: Verify unified view
        frame = _frame(setup)
        assert "function hello" in frame
        assert 'console.log("Hello")' in frame
        assert 'console.log("Hello, World!")' in frame

        # Step 2: Switch to split
        dr.view = "split"
        frame = _frame(setup)
        assert "function hello" in frame
        assert 'console.log("Hello")' in frame
        assert 'console.log("Hello, World!")' in frame

        # Step 3: Back to unified
        dr.view = "unified"
        frame = _frame(setup)
        assert "function hello" in frame
        assert 'console.log("Hello")' in frame
        assert 'console.log("Hello, World!")' in frame

        # Step 4: Split again
        dr.view = "split"
        frame = _frame(setup)
        assert "function hello" in frame
        assert 'console.log("Hello")' in frame
        assert 'console.log("Hello, World!")' in frame
        setup.destroy()

    async def test_wrapmode_works_in_unified_view(self):
        """Maps to test("DiffRenderable - wrap_mode works in unified view")."""
        long_line_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,3 +1,3 @@
 function hello() {
-  console.log("This is a very long line that should wrap when wrapMode is set to word but not when it is set to none");
+  console.log("This is a very long line that has been modified and should wrap when wrapMode is set to word but not when it is set to none");
 }"""
        setup, dr = await _make(
            diff=long_line_diff,
            view="unified",
            show_line_numbers=True,
            wrap_mode="none",
            width=80,
        )
        frame_none = _frame(setup)

        # Change to wrap_mode: word
        dr.wrap_mode = "word"
        frame_word = _frame(setup)

        # Frames should be different (word wrapping changes rendering)
        assert frame_none != frame_word

        # Change back to none
        dr.wrap_mode = "none"
        frame_none_again = _frame(setup)
        assert frame_none_again == frame_none
        setup.destroy()

    async def test_split_view_with_wrapmode_honors_wrapping_alignment(self):
        """Maps to test("DiffRenderable - split view with wrap_mode honors wrapping alignment")."""
        calculator_diff = """\
--- a/calculator.ts
+++ b/calculator.ts
@@ -1,13 +1,20 @@
 class Calculator {
   add(a: number, b: number): number {
     return a + b;
   }

-  subtract(a: number, b: number): number {
-    return a - b;
+  subtract(a: number, b: number, c: number = 0): number {
+    return a - b - c;
   }

   multiply(a: number, b: number): number {
     return a * b;
   }
+
+  divide(a: number, b: number): number {
+    if (b === 0) {
+      throw new Error("Division by zero");
+    }
+    return a / b;
+  }
 }"""
        setup, dr = await _make(
            diff=calculator_diff,
            view="split",
            show_line_numbers=True,
            wrap_mode="word",
            width=80,
            height=40,
        )
        frame = _frame(setup)
        frame_lines = frame.split("\n")

        # Find closing brace on left (old line 13)
        left_closing = next((ln for ln in frame_lines if re.match(r"^\s*13\s+\}", ln)), None)
        assert left_closing is not None

        # Find closing brace on right (new line 20)
        right_closing = next((ln for ln in frame_lines if re.search(r"\s*20\s+\}", ln)), None)
        assert right_closing is not None

        # They should be on the same line
        assert left_closing == right_closing
        setup.destroy()

    async def test_context_lines_show_new_line_numbers_in_unified_view(self):
        """Maps to test("DiffRenderable - context lines show new line numbers in unified view")."""
        calculator_diff = """\
--- a/calculator.ts
+++ b/calculator.ts
@@ -1,13 +1,20 @@
 class Calculator {
   add(a: number, b: number): number {
     return a + b;
   }

-  subtract(a: number, b: number): number {
-    return a - b;
+  subtract(a: number, b: number, c: number = 0): number {
+    return a - b - c;
   }

   multiply(a: number, b: number): number {
     return a * b;
   }
+
+  divide(a: number, b: number): number {
+    if (b === 0) {
+      throw new Error("Division by zero");
+    }
+    return a / b;
+  }
 }"""
        setup, dr = await _make(
            diff=calculator_diff,
            view="unified",
            show_line_numbers=True,
            width=80,
            height=30,
        )
        frame = _frame(setup)
        frame_lines = frame.split("\n")

        # The closing brace "}" for Calculator class
        # In new file it's at line 20. Find LAST closing brace matching pattern
        closing_brace_lines = [
            ln for ln in frame_lines if re.match(r"^\s*\d+\s+[+-]?\s*\}\s*$", ln)
        ]

        # The last one should be the class closing brace
        assert len(closing_brace_lines) > 0
        class_closing = closing_brace_lines[-1]

        # Extract line number
        m = re.match(r"^\s*(\d+)", class_closing)
        assert m is not None
        line_number = int(m.group(1))

        # Should show line 20 (new file), not 13 (old file)
        assert line_number == 20
        setup.destroy()

    async def test_multiple_hunks_in_unified_view(self):
        """Maps to test("DiffRenderable - multiple hunks in unified view")."""
        multi_hunk_diff = """\
--- a/file.js
+++ b/file.js
@@ -1,3 +1,3 @@
 function first() {
-  return 1;
+  return "one";
 }
@@ -15,4 +15,5 @@
 function second() {
   var x = 10;
+  var y = 20;
   return x;
 }
@@ -30,3 +31,3 @@
 function third() {
-  console.log("old");
+  console.log("new");
 }"""
        setup, dr = await _make(diff=multi_hunk_diff, view="unified", show_line_numbers=True)
        frame = _frame(setup)

        # All three hunks should be present
        assert 'return "one"' in frame
        assert "var y = 20" in frame
        assert 'console.log("new")' in frame

        frame_lines = frame.split("\n")

        # First hunk around line 2
        first_hunk = next((ln for ln in frame_lines if 'return "one"' in ln), None)
        assert first_hunk is not None
        assert re.search(r"2\s+\+", first_hunk)

        # Second hunk - added line
        second_hunk = next((ln for ln in frame_lines if "var y = 20" in ln), None)
        assert second_hunk is not None
        assert re.search(r"17\s+\+", second_hunk)

        # Third hunk around line 32
        third_hunk = next((ln for ln in frame_lines if 'console.log("new")' in ln), None)
        assert third_hunk is not None
        assert re.search(r"32\s+\+", third_hunk)
        setup.destroy()

    async def test_multiple_hunks_in_split_view(self):
        """Maps to test("DiffRenderable - multiple hunks in split view")."""
        multi_hunk_diff = """\
--- a/file.js
+++ b/file.js
@@ -1,3 +1,3 @@
 function first() {
-  return 1;
+  return "one";
 }
@@ -15,4 +15,5 @@
 function second() {
   var x = 10;
+  var y = 20;
   return x;
 }
@@ -30,3 +31,3 @@
 function third() {
-  console.log("old");
+  console.log("new");
 }"""
        setup, dr = await _make(diff=multi_hunk_diff, view="split", show_line_numbers=True)
        frame = _frame(setup)

        # All three hunks should be present
        assert 'return "one"' in frame
        assert "var y = 20" in frame
        assert 'console.log("new")' in frame

        # Both old and new content should be visible
        assert "return 1" in frame
        assert 'console.log("old")' in frame
        setup.destroy()

    async def test_no_newline_at_end_of_file_in_unified_view(self):
        """Maps to test("DiffRenderable - no newline at end of file in unified view")."""
        no_newline_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,3 +1,3 @@
 line1
 line2
-line3
\\ No newline at end of file
+line3_modified
\\ No newline at end of file"""
        setup, dr = await _make(diff=no_newline_diff, view="unified", show_line_numbers=True)
        frame = _frame(setup)

        # Should show both old and new versions
        assert "line3" in frame
        assert "line3_modified" in frame

        # Should NOT show the "No newline" marker as content
        frame_lines = frame.split("\n")
        marker_lines = [ln for ln in frame_lines if "No newline at end of file" in ln]
        assert len(marker_lines) == 0
        setup.destroy()

    async def test_no_newline_at_end_of_file_in_split_view(self):
        """Maps to test("DiffRenderable - no newline at end of file in split view")."""
        no_newline_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,3 +1,3 @@
 line1
 line2
-line3
\\ No newline at end of file
+line3_modified
\\ No newline at end of file"""
        setup, dr = await _make(diff=no_newline_diff, view="split", show_line_numbers=True)
        frame = _frame(setup)

        # Both sides should show their respective versions
        assert "line3" in frame
        assert "line3_modified" in frame

        # Should NOT show the "No newline" marker
        frame_lines = frame.split("\n")
        marker_lines = [ln for ln in frame_lines if "No newline at end of file" in ln]
        assert len(marker_lines) == 0
        setup.destroy()

    async def test_asymmetric_block_with_more_removes_than_adds_in_split_view(self):
        """Maps to test("DiffRenderable - asymmetric block with more removes than adds in split view")."""
        asym_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,7 +1,4 @@
 context_before
-remove1
-remove2
-remove3
-remove4
-remove5
+add1
+add2
 context_after"""
        setup, dr = await _make(diff=asym_diff, view="split", show_line_numbers=True)
        frame = _frame(setup)

        # Left side should have all 5 removes
        assert "remove1" in frame
        assert "remove2" in frame
        assert "remove3" in frame
        assert "remove4" in frame
        assert "remove5" in frame

        # Right side should have 2 adds
        assert "add1" in frame
        assert "add2" in frame

        # Context lines
        frame_lines = frame.split("\n")
        context_before = [ln for ln in frame_lines if "context_before" in ln]
        context_after = [ln for ln in frame_lines if "context_after" in ln]
        assert len(context_before) >= 1
        assert len(context_after) >= 1
        setup.destroy()

    async def test_asymmetric_block_with_more_adds_than_removes_in_split_view(self):
        """Maps to test("DiffRenderable - asymmetric block with more adds than removes in split view")."""
        asym_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,4 +1,7 @@
 context_before
-remove1
-remove2
+add1
+add2
+add3
+add4
+add5
 context_after"""
        setup, dr = await _make(diff=asym_diff, view="split", show_line_numbers=True)
        frame = _frame(setup)

        # Left side should have 2 removes
        assert "remove1" in frame
        assert "remove2" in frame

        # Right side should have all 5 adds
        assert "add1" in frame
        assert "add2" in frame
        assert "add3" in frame
        assert "add4" in frame
        assert "add5" in frame

        # Context lines should be aligned
        frame_lines = frame.split("\n")
        context_before = [ln for ln in frame_lines if "context_before" in ln]
        context_after = [ln for ln in frame_lines if "context_after" in ln]
        assert len(context_before) >= 1
        assert len(context_after) >= 1
        setup.destroy()

    async def test_back_to_back_change_blocks_without_context_lines_in_split_view(self):
        """Maps to test("DiffRenderable - back-to-back change blocks without context lines in split view")."""
        b2b_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,4 +1,4 @@
-remove1
-remove2
-remove3
-remove4
+add1
+add2
+add3
+add4"""
        setup, dr = await _make(diff=b2b_diff, view="split", show_line_numbers=True)
        frame = _frame(setup)

        # All removes should be on left
        assert "remove1" in frame
        assert "remove2" in frame
        assert "remove3" in frame
        assert "remove4" in frame

        # All adds should be on right
        assert "add1" in frame
        assert "add2" in frame
        assert "add3" in frame
        assert "add4" in frame

        frame_lines = [ln for ln in frame.split("\n") if ln.strip()]
        assert len(frame_lines) > 0
        setup.destroy()

    async def test_very_long_lines_wrapping_multiple_times_in_split_view(self):
        """Maps to test("DiffRenderable - very long lines wrapping multiple times in split view")."""
        long_line_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,3 +1,3 @@
 short line
-This is an extremely long line that will definitely wrap multiple times when rendered in a split view with word wrapping enabled because it contains so many words and characters
+This is an extremely long line that has been modified and will definitely wrap multiple times when rendered in a split view with word wrapping enabled because it contains so many words and characters and even more content
 another short line"""
        setup, dr = await _make(
            diff=long_line_diff,
            view="split",
            show_line_numbers=True,
            wrap_mode="word",
        )
        frame = _frame(setup)

        # Both versions should be present (possibly truncated)
        assert "extremely long line" in frame
        assert "has been modified" in frame

        # Short lines should still be aligned
        assert "short line" in frame
        assert "another short line" in frame
        setup.destroy()

    async def test_rapid_diff_updates_trigger_microtask_coalescing(self):
        """Maps to test("DiffRenderable - rapid diff updates trigger microtask coalescing")."""
        setup, dr = await _make(
            diff=SIMPLE_DIFF,
            view="split",
            show_line_numbers=True,
            wrap_mode="word",
        )
        _frame(setup)

        # Rapidly update the diff multiple times
        dr.diff = MULTI_LINE_DIFF
        dr.diff = ADD_ONLY_DIFF
        dr.diff = REMOVE_ONLY_DIFF
        dr.diff = SIMPLE_DIFF

        frame = _frame(setup)

        # Should show the final diff (SIMPLE_DIFF)
        assert "function hello" in frame
        assert 'console.log("Hello")' in frame
        assert 'console.log("Hello, World!")' in frame

        # Should NOT show content from intermediate diffs
        assert "subtract" not in frame
        assert "newFunction" not in frame
        assert "oldFunction" not in frame
        setup.destroy()

    async def test_explicit_content_background_colors_differ_from_gutter(self):
        """Maps to test("DiffRenderable - explicit content background colors differ from gutter")."""
        setup, dr = await _make(
            diff=SIMPLE_DIFF,
            view="unified",
            show_line_numbers=True,
            added_bg="#1a4d1a",
            removed_bg="#4d1a1a",
            added_content_bg="#2a5d2a",
            removed_content_bg="#5d2a2a",
        )
        frame = _frame(setup)

        # Verify content is rendered
        assert "function hello" in frame
        assert 'console.log("Hello")' in frame
        assert 'console.log("Hello, World!")' in frame

        # Verify properties are set correctly
        assert dr.added_bg == RGBA.from_hex("#1a4d1a")
        assert dr.removed_bg == RGBA.from_hex("#4d1a1a")
        assert dr.added_content_bg == RGBA.from_hex("#2a5d2a")
        assert dr.removed_content_bg == RGBA.from_hex("#5d2a2a")

        # Test that we can update them
        dr.added_content_bg = "#3a6d3a"
        assert dr.added_content_bg == RGBA.from_hex("#3a6d3a")

        frame2 = _frame(setup)
        assert "function hello" in frame2
        setup.destroy()

    async def test_malformed_diff_string_handled_gracefully(self):
        """Maps to test("DiffRenderable - malformed diff string handled gracefully")."""
        malformed = "This is not a valid diff format\nJust some random text\nWithout proper headers"
        setup, dr = await _make(diff=malformed, view="unified")
        _frame(setup)  # should not crash
        assert dr.diff == malformed
        setup.destroy()

    async def test_invalid_diff_format_shows_error_with_raw_diff(self):
        """Maps to test("DiffRenderable - invalid diff format shows error with raw diff")."""
        invalid_diff = """\
--- a/test.js
+++ b/test.js
@@ -a,b +c,d @@
 function hello() {
-  console.log("Hello");
+  console.log("Hello, World!");
 }"""
        setup, dr = await _make(diff=invalid_diff, view="unified")
        frame = _frame(setup)

        # Should contain error message
        assert "Unknown line" in frame

        # Should show the raw diff content
        assert "@@ -a,b +c,d @@" in frame
        assert "function hello" in frame
        setup.destroy()

    async def test_diff_with_only_context_lines_no_changes(self):
        """Maps to test("DiffRenderable - diff with only context lines (no changes)")."""
        context_only_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,5 +1,5 @@
 line1
 line2
 line3
 line4
 line5"""
        setup, dr = await _make(diff=context_only_diff, view="unified", show_line_numbers=True)
        frame = _frame(setup)

        # All lines should be present
        assert "line1" in frame
        assert "line2" in frame
        assert "line3" in frame
        assert "line4" in frame
        assert "line5" in frame

        # No +/- signs should be present (only context)
        frame_lines = frame.split("\n")
        changed_lines = [ln for ln in frame_lines if re.search(r"[+-]\s*line", ln)]
        assert len(changed_lines) == 0
        setup.destroy()

    async def test_should_not_leak_listeners_on_unified_view_updates(self):
        """Maps to test("DiffRenderable - should not leak listeners on unified view updates")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")
        _frame(setup)

        # Get the underlying CodeRenderable
        code_renderable = dr.left_code_renderable
        assert code_renderable is not None

        # Check initial listener count
        initial_count = code_renderable.listener_count("line-info-change")

        # Update the diff multiple times
        for i in range(10):
            dr.diff = SIMPLE_DIFF.replace('"Hello"', f'"Hello{i}"')
            _frame(setup)

        # Check that listener count hasn't grown
        final_count = code_renderable.listener_count("line-info-change")
        assert final_count == initial_count
        setup.destroy()

    async def test_should_not_leak_listeners_on_split_view_updates(self):
        """Maps to test("DiffRenderable - should not leak listeners on split view updates")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="split")
        _frame(setup)

        # Get the underlying CodeRenderables
        left_cr = dr.left_code_renderable
        right_cr = dr.right_code_renderable
        assert left_cr is not None
        assert right_cr is not None

        # Check initial listener counts
        left_initial = left_cr.listener_count("line-info-change")
        right_initial = right_cr.listener_count("line-info-change")

        # Update the diff multiple times
        for i in range(10):
            dr.diff = SIMPLE_DIFF.replace('"Hello"', f'"Hello{i}"')
            _frame(setup)

        # Check that listener counts haven't grown
        assert left_cr.listener_count("line-info-change") == left_initial
        assert right_cr.listener_count("line-info-change") == right_initial
        setup.destroy()

    async def test_should_not_leak_listeners_when_switching_views(self):
        """Maps to test("DiffRenderable - should not leak listeners when switching views")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")
        _frame(setup)

        left_cr = dr.left_code_renderable
        assert left_cr is not None
        initial_left_count = left_cr.listener_count("line-info-change")

        # Switch views multiple times
        for _ in range(5):
            dr.view = "split"
            _frame(setup)
            dr.view = "unified"
            _frame(setup)

        final_left_count = left_cr.listener_count("line-info-change")
        assert final_left_count <= initial_left_count + 2
        setup.destroy()

    async def test_should_not_leak_listeners_on_rapid_property_changes(self):
        """Maps to test("DiffRenderable - should not leak listeners on rapid property changes")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="split")
        _frame(setup)

        left_cr = dr.left_code_renderable
        right_cr = dr.right_code_renderable
        left_initial = left_cr.listener_count("line-info-change")
        right_initial = right_cr.listener_count("line-info-change")

        # Make rapid changes that trigger rebuilds
        for i in range(10):
            dr.wrap_mode = "word" if i % 2 == 0 else "char"
            dr.added_bg = "#ff0000" if i % 2 == 0 else "#00ff00"
            dr.removed_bg = "#0000ff" if i % 2 == 0 else "#ffff00"
            _frame(setup)

        assert left_cr.listener_count("line-info-change") == left_initial
        assert right_cr.listener_count("line-info-change") == right_initial
        setup.destroy()

    async def test_can_toggle_conceal_with_markdown_diff(self):
        """Maps to test("DiffRenderable - can toggle conceal with markdown diff")."""
        markdown_diff = """\
--- a/test.md
+++ b/test.md
@@ -1,3 +1,3 @@
 First line
-Some text **old**
+Some text **boldtext** and *italic*
 End line"""

        setup, dr = await _make(
            diff=markdown_diff,
            view="unified",
            filetype="markdown",
            conceal=True,
        )
        frame_with_conceal = _frame(setup)
        assert dr.conceal is True

        # Toggle conceal off
        dr.conceal = False
        frame_without_conceal = _frame(setup)
        assert dr.conceal is False

        # Both frames should contain the text content
        assert "First line" in frame_with_conceal
        assert "First line" in frame_without_conceal
        setup.destroy()

    async def test_conceal_works_in_split_view(self):
        """Maps to test("DiffRenderable - conceal works in split view")."""
        markdown_diff = """\
--- a/test.md
+++ b/test.md
@@ -1,3 +1,3 @@
 First line
-Some text **old**
+Some text **boldtext** and *italic*
 End line"""

        setup, dr = await _make(
            diff=markdown_diff,
            view="split",
            filetype="markdown",
            conceal=True,
        )
        frame_with_conceal = _frame(setup)
        assert dr.conceal is True

        # Toggle conceal off
        dr.conceal = False
        frame_without_conceal = _frame(setup)
        assert dr.conceal is False

        # Both frames should contain the text content
        assert "First line" in frame_with_conceal
        assert "First line" in frame_without_conceal
        setup.destroy()

    async def test_conceal_defaults_to_false_when_not_specified(self):
        """Maps to test("DiffRenderable - conceal defaults to false when not specified")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", filetype="javascript")
        _frame(setup)
        assert dr.conceal is False
        setup.destroy()

    async def test_should_handle_resize_with_wrapping_without_leaking_listeners(self):
        """Maps to test("DiffRenderable - should handle resize with wrapping without leaking listeners")."""
        setup, dr = await _make(
            diff=SIMPLE_DIFF,
            view="split",
            wrap_mode="word",
            width=100,
        )
        _frame(setup)

        left_cr = dr.left_code_renderable
        right_cr = dr.right_code_renderable
        left_initial = left_cr.listener_count("line-info-change")
        right_initial = right_cr.listener_count("line-info-change")

        # Simulate multiple resizes
        for i in range(10):
            dr.width = 50 + i * 5
            _frame(setup)

        assert left_cr.listener_count("line-info-change") == left_initial
        assert right_cr.listener_count("line-info-change") == right_initial
        setup.destroy()

    async def test_gutter_configuration_updates_work_correctly(self):
        """Maps to test("DiffRenderable - gutter configuration updates work correctly")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", show_line_numbers=True)
        _frame(setup)

        left_cr = dr.left_code_renderable
        left_side = dr.left_side
        assert left_side is not None
        assert left_cr is not None

        initial_count = left_cr.listener_count("line-info-change")

        # Get initial frame to verify line numbers are showing
        frame = _frame(setup)
        assert "function hello" in frame

        # Update multiple gutter configurations
        for i in range(5):
            dr.diff = SIMPLE_DIFF.replace('"Hello"', f'"Hello{i}"')
            _frame(setup)

        # Verify listener count is stable
        assert left_cr.listener_count("line-info-change") == initial_count

        # Verify rendering still works
        frame = _frame(setup)
        assert "function hello" in frame
        assert "Hello4" in frame
        setup.destroy()

    async def test_target_remains_functional_after_multiple_updates(self):
        """Maps to test("DiffRenderable - target remains functional after multiple updates")."""
        setup, dr = await _make(diff=MULTI_LINE_DIFF, view="split", show_line_numbers=True)
        _frame(setup)

        left_cr = dr.left_code_renderable
        right_cr = dr.right_code_renderable

        # Register listeners and verify events fire
        left_event_fired = False
        right_event_fired = False

        def left_listener():
            nonlocal left_event_fired
            left_event_fired = True

        def right_listener():
            nonlocal right_event_fired
            right_event_fired = True

        left_cr.on("line-info-change", left_listener)
        right_cr.on("line-info-change", right_listener)

        # Update diff multiple times
        for i in range(5):
            left_event_fired = False
            right_event_fired = False

            dr.diff = MULTI_LINE_DIFF.replace("add(a, b)", f"add(a, b, {i})")
            _frame(setup)

            # Events should have fired during the update
            assert left_event_fired is True
            assert right_event_fired is True

        left_cr.off("line-info-change", left_listener)
        right_cr.off("line-info-change", right_listener)
        setup.destroy()

    async def test_gutter_remains_in_correct_position_after_updates(self):
        """Maps to test("DiffRenderable - gutter remains in correct position after updates")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", show_line_numbers=True)
        frame = _frame(setup)
        lines = frame.split("\n")

        # Find a line with content
        content_line = next((ln for ln in lines if "function hello" in ln), None)
        assert content_line is not None
        # Line number should be at the start
        assert re.match(r"^\s*\d+", content_line)

        # Update diff multiple times
        for i in range(5):
            dr.diff = SIMPLE_DIFF.replace('"Hello"', f'"Hello{i}"')
            frame = _frame(setup)
            updated_lines = frame.split("\n")
            updated_content = next((ln for ln in updated_lines if "function hello" in ln), None)
            assert updated_content is not None
            assert re.match(r"^\s*\d+", updated_content)
        setup.destroy()

    async def test_properly_cleans_up_listeners_on_destroy(self):
        """Maps to test("DiffRenderable - properly cleans up listeners on destroy")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="split")
        _frame(setup)

        left_cr = dr.left_code_renderable
        right_cr = dr.right_code_renderable

        # Update multiple times to potentially create leaks
        for i in range(5):
            dr.diff = SIMPLE_DIFF.replace('"Hello"', f'"Hello{i}"')
            _frame(setup)

        left_count = left_cr.listener_count("line-info-change")
        right_count = right_cr.listener_count("line-info-change")

        # Verify listeners exist (>=0 is fine, the important thing is no crash)
        assert left_count >= 0
        assert right_count >= 0

        # Destroy the diff
        dr.destroy_recursively()

        # The DiffRenderable should be destroyed
        assert dr.is_destroyed is True
        setup.destroy()

    async def test_line_numbers_update_correctly_after_resize_causes_wrapping_changes(self):
        """Maps to test("DiffRenderable - line numbers update correctly after resize causes wrapping changes")."""
        long_line_diff = """\
--- a/test.js
+++ b/test.js
@@ -1,4 +1,4 @@
 function calculateSomethingVeryComplexWithALongFunctionNameThatWillWrap() {
-  const oldResultWithAVeryLongVariableNameThatWillDefinitelyWrapWhenRenderedInASmallerTerminal = 42;
+  const newResultWithAVeryLongVariableNameThatWillDefinitelyWrapWhenRenderedInASmallerTerminal = 100;
   return result;
 }"""
        setup, dr = await _make(
            diff=long_line_diff,
            view="unified",
            show_line_numbers=True,
            wrap_mode="word",
            width=120,
            height=40,
        )
        frame_before = _frame(setup)

        # Should contain line numbers
        lines_before = [ln for ln in frame_before.split("\n") if ln.strip()]
        line_number_matches = []
        for line in lines_before:
            m = re.match(r"^\s*(\d+)\s+([+-]?)", line)
            if m:
                line_number_matches.append(
                    {
                        "num": int(m.group(1)),
                        "sign": m.group(2),
                    }
                )

        # Should have line numbers
        assert len(line_number_matches) >= 4

        # First line should be 1
        assert line_number_matches[0]["num"] == 1
        # Second line should be 2 (removed)
        assert line_number_matches[1]["num"] == 2
        assert line_number_matches[1]["sign"] == "-"
        # Third line should be 2 (added)
        assert line_number_matches[2]["num"] == 2
        assert line_number_matches[2]["sign"] == "+"
        setup.destroy()

    async def test_fg_prop_is_passed_to_coderenderable_on_construction(self):
        """Maps to test("DiffRenderable - fg prop is passed to CodeRenderable on construction")."""
        custom_fg = "#000000"
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", fg=custom_fg)
        _frame(setup)

        assert dr.fg == RGBA.from_hex(custom_fg)

        left_cr = dr.left_code_renderable
        assert left_cr is not None
        assert left_cr.fg == RGBA.from_hex(custom_fg)
        setup.destroy()

    async def test_fg_prop_can_be_updated_via_setter(self):
        """Maps to test("DiffRenderable - fg prop can be updated via setter")."""
        initial_fg = "#000000"
        updated_fg = "#333333"

        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", fg=initial_fg)
        _frame(setup)

        dr.fg = updated_fg
        _frame(setup)

        assert dr.fg == RGBA.from_hex(updated_fg)

        left_cr = dr.left_code_renderable
        assert left_cr.fg == RGBA.from_hex(updated_fg)
        setup.destroy()

    async def test_fg_prop_is_passed_to_both_coderenderables_in_split_view(self):
        """Maps to test("DiffRenderable - fg prop is passed to both CodeRenderables in split view")."""
        custom_fg = "#222222"
        setup, dr = await _make(diff=SIMPLE_DIFF, view="split", fg=custom_fg)
        _frame(setup)

        assert dr.fg == RGBA.from_hex(custom_fg)

        left_cr = dr.left_code_renderable
        right_cr = dr.right_code_renderable
        assert left_cr is not None
        assert right_cr is not None
        assert left_cr.fg == RGBA.from_hex(custom_fg)
        assert right_cr.fg == RGBA.from_hex(custom_fg)
        setup.destroy()

    async def test_fg_prop_updates_both_coderenderables_in_split_view(self):
        """Maps to test("DiffRenderable - fg prop updates both CodeRenderables in split view")."""
        initial_fg = "#111111"
        updated_fg = "#444444"

        setup, dr = await _make(diff=SIMPLE_DIFF, view="split", fg=initial_fg)
        _frame(setup)

        left_cr = dr.left_code_renderable
        right_cr = dr.right_code_renderable

        dr.fg = updated_fg
        _frame(setup)

        assert dr.fg == RGBA.from_hex(updated_fg)
        assert left_cr.fg == RGBA.from_hex(updated_fg)
        assert right_cr.fg == RGBA.from_hex(updated_fg)
        setup.destroy()

    async def test_fg_prop_defaults_to_undefined_when_not_specified(self):
        """Maps to test("DiffRenderable - fg prop defaults to undefined when not specified")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")
        _frame(setup)
        assert dr.fg is None
        setup.destroy()

    async def test_fg_prop_can_be_set_to_undefined_to_clear_it(self):
        """Maps to test("DiffRenderable - fg prop can be set to undefined to clear it")."""
        initial_fg = "#000000"
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", fg=initial_fg)
        _frame(setup)

        assert dr.fg == RGBA.from_hex(initial_fg)

        dr.fg = None
        _frame(setup)
        assert dr.fg is None
        setup.destroy()

    async def test_fg_prop_accepts_rgba_directly(self):
        """Maps to test("DiffRenderable - fg prop accepts RGBA directly")."""
        custom_fg = RGBA(0.2, 0.2, 0.2, 1.0)
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified", fg=custom_fg)
        _frame(setup)

        assert dr.fg == custom_fg

        left_cr = dr.left_code_renderable
        assert left_cr.fg == custom_fg
        setup.destroy()

    async def test_split_view_with_word_wrapping_changing_diff_content_should_not_misalign_sides(
        self,
    ):
        """Maps to test("DiffRenderable - split view with word wrapping: changing diff content should not misalign sides")."""
        import asyncio
        from opentui.components.box import Box

        # contentExamples[0] — TypeScript Calculator diff
        calculator_diff = """\
--- a/calculator.ts
+++ b/calculator.ts
@@ -1,13 +1,20 @@
 class Calculator {
   add(a: number, b: number): number {
     return a + b;
   }

-  subtract(a: number, b: number): number {
-    return a - b;
+  subtract(a: number, b: number, c: number = 0): number {
+    return a - b - c;
   }

   multiply(a: number, b: number): number {
     return a * b;
   }
+
+  divide(a: number, b: number): number {
+    if (b === 0) {
+      throw new Error("Division by zero");
+    }
+    return a / b;
+  }
 }"""

        # contentExamples[1] — Real Session: Text Demo
        text_demo_diff = """\
Index: packages/core/src/examples/index.ts
===================================================================
--- packages/core/src/examples/index.ts\tbefore
+++ packages/core/src/examples/index.ts\tafter
@@ -56,6 +56,7 @@
 import * as terminalDemo from "./terminal"
 import * as diffDemo from "./diff-demo"
 import * as keypressDebugDemo from "./keypress-debug-demo"
+import * as textTruncationDemo from "./text-truncation-demo"
 import { setupCommonDemoKeys } from "./lib/standalone-keys"

 interface Example {
@@ -85,6 +86,12 @@
     destroy: textSelectionExample.destroy,
   },
   {
+    name: "Text Truncation Demo",
+    description: "Middle truncation with ellipsis - toggle with 'T' key and resize to test responsive behavior",
+    run: textTruncationDemo.run,
+    destroy: textTruncationDemo.destroy,
+  },
+  {
     name: "ASCII Font Selection Demo",
     description: "Text selection with ASCII fonts - precise character-level selection across different font types",
     run: asciiFontSelectionExample.run,"""

        # Use terminal width that matches the demo (~116 chars)
        setup = await create_test_renderer(116, 30)

        try:
            # Diff styling theme
            diff_colors = dict(
                added_bg="#1a4d1a",
                removed_bg="#4d1a1a",
                context_bg="transparent",
                added_sign_color="#22c55e",
                removed_sign_color="#ef4444",
                line_number_fg="#6b7280",
                line_number_bg="#161b22",
                added_line_number_bg="#0d3a0d",
                removed_line_number_bg="#3a0d0d",
            )

            # ── PART 1: CORRECT PATH ──
            # Start with textDemoDiff, view="unified", wrap_mode="none"
            # Then toggle to split, then toggle to word wrap
            parent1 = Box(id="parent-container-1", padding=1)
            setup.renderer.root.add(parent1)

            correct_diff = DiffRenderable(
                id="correct-diff",
                diff=text_demo_diff,
                view="unified",
                filetype="typescript",
                show_line_numbers=True,
                wrap_mode="none",
                conceal=True,
                flex_grow=1,
                flex_shrink=1,
                **diff_colors,
            )
            parent1.add(correct_diff)
            await asyncio.sleep(0.2)

            # Toggle to split view
            correct_diff.view = "split"
            await asyncio.sleep(0.2)

            # Toggle to word wrap
            correct_diff.wrap_mode = "word"
            await asyncio.sleep(0.5)

            correct_frame = setup.capture_char_frame()

            # Clean up
            parent1.destroy_recursively()
            setup.renderer.root.remove(parent1)
            await asyncio.sleep(0.1)

            # ── PART 2: BUGGY PATH ──
            # Start with calculatorDiff, view="unified", wrap_mode="none"
            # Then split → word wrap → change content to textDemoDiff
            parent2 = Box(id="parent-container-2", padding=1)
            setup.renderer.root.add(parent2)

            buggy_diff = DiffRenderable(
                id="buggy-diff",
                diff=calculator_diff,
                view="unified",
                filetype="typescript",
                show_line_numbers=True,
                wrap_mode="none",
                conceal=True,
                flex_grow=1,
                flex_shrink=1,
                **diff_colors,
            )
            parent2.add(buggy_diff)
            await asyncio.sleep(0.2)

            # Toggle to split view
            buggy_diff.view = "split"
            await asyncio.sleep(0.2)

            # Toggle to word wrap
            buggy_diff.wrap_mode = "word"
            await asyncio.sleep(0.2)

            # Change diff content to textDemoDiff — THIS IS WHERE THE BUG MANIFESTS
            buggy_diff.diff = text_demo_diff
            buggy_diff.filetype = "typescript"
            await asyncio.sleep(0.5)

            buggy_frame = setup.capture_char_frame()

            # ASSERTION: Both frames should be identical since they show the same
            # diff content with the same view settings (split + word wrap).
            # But due to the bug, the buggy frame has misaligned left/right sides
            # because the line_info from CodeRenderable is STALE after changing diff content.
            assert buggy_frame == correct_frame
        finally:
            setup.destroy()

    async def test_setlinecolor_applies_color_to_line(self):
        """Maps to test("DiffRenderable - set_line_color applies color to line")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")

        dr.set_line_color(0, "#ff0000")
        dr.set_line_color(1, {"gutter": "#00ff00", "content": "#0000ff"})
        dr.clear_line_color(0)
        dr.clear_line_color(1)
        # Should not crash
        setup.destroy()

    async def test_highlightlines_applies_color_to_range(self):
        """Maps to test("DiffRenderable - highlight_lines applies color to range")."""
        setup, dr = await _make(diff=MULTI_LINE_DIFF, view="unified")

        dr.highlight_lines(0, 3, "#ff0000")
        dr.clear_highlight_lines(0, 3)
        # Should not crash
        setup.destroy()

    async def test_setlinecolors_and_clearalllinecolors(self):
        """Maps to test("DiffRenderable - set_line_colors and clear_all_line_colors")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="unified")

        line_colors = {0: "#ff0000", 1: "#00ff00", 2: "#0000ff"}
        dr.set_line_colors(line_colors)
        dr.clear_all_line_colors()
        # Should not crash
        setup.destroy()

    async def test_line_highlighting_works_in_split_view(self):
        """Maps to test("DiffRenderable - line highlighting works in split view")."""
        setup, dr = await _make(diff=SIMPLE_DIFF, view="split")

        dr.set_line_color(0, "#ff0000")
        dr.highlight_lines(0, 2, "#00ff00")
        dr.clear_highlight_lines(0, 2)
        dr.clear_all_line_colors()
        # Should not crash
        setup.destroy()
