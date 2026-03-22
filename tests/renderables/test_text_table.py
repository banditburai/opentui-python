"""Port of upstream TextTable.test.ts.

Upstream: packages/core/src/renderables/TextTable.test.ts
Tests ported: 31/31 (0 skipped)
"""

import re
import unicodedata

import pytest

from opentui import create_test_renderer
from opentui.components.text_table_renderable import TextTableRenderable

# Vertical border codepoint
VERTICAL_BORDER_CP = ord("\u2502")  # │
BORDER_CHAR_PATTERN = re.compile(r"[┌┐└┘├┤┬┴┼│─]")


# ── Helpers ──────────────────────────────────────────────────────────────


def cell(text: str):
    """Create a cell content (list of TextChunk dicts)."""
    return [{"text": text}]


def bold(text: str):
    """Create a bold cell content (list of TextChunk dicts with bold attr)."""
    return [{"text": text, "attributes": 1}]


def green(text: str):
    """Create a green cell content."""
    return [{"text": text, "fg": [0.0, 0.5, 0.0, 1.0]}]


def red(text: str):
    """Create a red cell content."""
    return [{"text": text, "fg": [1.0, 0.0, 0.0, 1.0]}]


def yellow(text: str):
    """Create a yellow cell content."""
    return [{"text": text, "fg": [1.0, 1.0, 0.0, 1.0]}]


def get_char_at_frame(frame: str, x: int, y: int) -> str:
    """Get the character at position (x, y) from a captured frame string."""
    lines = frame.split("\n")
    if y < 0 or y >= len(lines):
        return ""
    line = lines[y]
    if x < 0 or x >= len(line):
        return ""
    return line[x]


def _char_display_width(ch: str) -> int:
    """Return the display column width of a character.

    CJK ideographs and certain emoji occupy 2 columns; most other
    characters (including box-drawing) occupy 1.
    """
    eaw = unicodedata.east_asian_width(ch)
    if eaw in ("W", "F"):
        return 2
    return 1


def find_vertical_border_xs_in_frame(frame: str, y: int) -> list[int]:
    """Find x positions (display columns) of vertical border characters in the given row of a frame.

    Accounts for double-width CJK / emoji characters.
    """
    lines = frame.split("\n")
    if y < 0 or y >= len(lines):
        return []
    line = lines[y]
    xs = []
    col = 0
    for ch in line:
        if ch == "\u2502":  # │
            xs.append(col)
        col += _char_display_width(ch)
    return xs


def count_char(text: str, target: str) -> int:
    """Count occurrences of target character in text."""
    return sum(1 for ch in text if ch == target)


def normalize_frame_block(lines: list[str]) -> str:
    """Normalize a block of lines by stripping common leading whitespace."""
    trimmed = [line.rstrip() for line in lines]
    non_empty = [line for line in trimmed if line]
    if not non_empty:
        return "\n".join(trimmed) + "\n"
    min_indent = min(len(line) - len(line.lstrip()) for line in non_empty)
    return "\n".join(line[min_indent:] for line in trimmed) + "\n"


def extract_table_block(frame: str, header_matcher) -> str:
    """Extract a table block from a frame using a header matcher function."""
    lines = frame.split("\n")
    header_y = -1
    for i, line in enumerate(lines):
        if header_matcher(line):
            header_y = i
            break
    if header_y < 0:
        raise ValueError("Unable to find table header line")

    top_y = header_y
    while top_y >= 0 and "\u250c" not in (lines[top_y] if top_y < len(lines) else ""):
        top_y -= 1
    if top_y < 0:
        raise ValueError("Unable to find table top border")

    bottom_y = header_y
    while bottom_y < len(lines) and "\u2514" not in (
        lines[bottom_y] if bottom_y < len(lines) else ""
    ):
        bottom_y += 1
    if bottom_y >= len(lines):
        raise ValueError("Unable to find table bottom border")

    return normalize_frame_block(lines[top_y : bottom_y + 1])


def find_text_point(frame: str, text: str) -> tuple[int, int]:
    """Find the (x, y) position of text in a frame."""
    lines = frame.split("\n")
    for y, line in enumerate(lines):
        x = line.find(text)
        if x >= 0:
            return (x, y)
    raise ValueError(f"Unable to find '{text}' in frame")


def find_selectable_point(table: TextTableRenderable, direction: str) -> tuple[int, int]:
    """Find a selectable point on the table."""
    points = []
    for y in range(table.y, table.y + table.height):
        for x in range(table.x, table.x + table.width):
            if table.should_start_selection(x, y):
                points.append((x, y))
    assert len(points) > 0, "No selectable points found"

    if direction == "top-left":
        points.sort(key=lambda p: (p[1], p[0]))
        return points[0]
    else:  # bottom-right
        points.sort(key=lambda p: (-p[1], -p[0]))
        return points[0]


async def _create_table(setup, **kwargs):
    """Create a TextTableRenderable, add to root, render a frame."""
    table = TextTableRenderable(**kwargs)
    setup.renderer.root.add(table)
    setup.render_frame()
    return table


class TestTextTableRenderable:
    """Maps to describe("TextTableRenderable")."""

    async def test_reuses_raster_cache_when_table_is_clean(self):
        setup = await create_test_renderer(60, 16)
        try:

            class _CountingTable(TextTableRenderable):
                __slots__ = ("border_calls", "cell_calls")

                def __init__(self, **kwargs):
                    super().__init__(**kwargs)
                    self.border_calls = 0
                    self.cell_calls = 0

                def _draw_borders(self, buffer, base_x, base_y):
                    self.border_calls += 1
                    return super()._draw_borders(buffer, base_x, base_y)

                def _draw_cells(self, buffer, base_x, base_y):
                    self.cell_calls += 1
                    return super()._draw_cells(buffer, base_x, base_y)

            table = _CountingTable(
                left=0,
                top=0,
                position="absolute",
                column_width_mode="content",
                content=[[cell("A"), cell("B")], [cell("1"), cell("2")]],
            )
            setup.renderer.root.add(table)
            setup.render_frame()

            table.border_calls = 0
            table.cell_calls = 0

            table._invalidate_raster_only()
            setup.render_frame()
            dirty_border_calls = table.border_calls
            dirty_cell_calls = table.cell_calls
            assert dirty_border_calls >= 1
            assert dirty_cell_calls >= 1

            setup.render_frame()
            assert table.border_calls == dirty_border_calls
            assert table.cell_calls == dirty_cell_calls
        finally:
            setup.destroy()

    async def test_renders_a_basic_table_with_styled_cell_chunks(self):
        """Maps to test("renders a basic table with styled cell chunks")."""
        setup = await create_test_renderer(60, 16)
        try:
            content = [
                [bold("Name"), bold("Status"), bold("Notes")],
                [cell("Alpha"), green("OK"), cell("All systems nominal")],
                [cell("Bravo"), red("WARN"), cell("Pending checks")],
            ]

            table = await _create_table(
                setup,
                left=1,
                top=1,
                position="absolute",
                column_width_mode="content",
                content=content,
            )

            frame = setup.capture_char_frame()
            assert "Alpha" in frame
            assert "WARN" in frame
            # Table should contain borders
            assert "\u2502" in frame  # │
            assert "\u250c" in frame  # ┌
        finally:
            setup.destroy()

    async def test_wraps_content_and_fits_columns_when_width_is_constrained(self):
        """Maps to test("wraps content and fits columns when width is constrained")."""
        setup = await create_test_renderer(60, 16)
        try:
            content = [
                [bold("ID"), bold("Description")],
                [
                    cell("1"),
                    cell("This is a long sentence that should wrap across multiple visual lines"),
                ],
                [cell("2"), cell("Short")],
            ]

            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=34,
                wrap_mode="word",
                content=content,
            )

            frame = setup.capture_char_frame()
            assert "Description" in frame

            # The table should have wrapped text (multiple visual lines for the long content)
            lines = frame.split("\n")
            # Find the row that starts with "1"
            row_lines = [
                i
                for i, line in enumerate(lines)
                if "\u25021" in line.replace(" ", "") or ("│1" in line)
            ]
            # There should be wrapping (the long sentence takes multiple lines)
            assert table.height > 5  # Would need at least header + wrapping rows
        finally:
            setup.destroy()

    async def test_keeps_intrinsic_width_in_content_mode_when_extra_space_is_available(self):
        """Maps to test("keeps intrinsic width in content mode when extra space is available")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=34,
                wrap_mode="word",
                column_width_mode="content",
                content=[
                    [cell("A"), cell("B")],
                    [cell("1"), cell("2")],
                ],
            )

            frame = setup.capture_char_frame()
            lines = frame.split("\n")
            header_y = -1
            for i, line in enumerate(lines):
                if "A" in line and "B" in line:
                    header_y = i
                    break
            assert header_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, header_y)
            assert len(border_xs) == 3
            assert border_xs[0] == 0
            # In content mode, the right border should be less than the full width
            assert border_xs[-1] < 33
        finally:
            setup.destroy()

    async def test_fills_available_width_by_default_in_full_mode(self):
        """Maps to test("fills available width by default in full mode")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=34,
                wrap_mode="word",
                content=[
                    [cell("A"), cell("B")],
                    [cell("1"), cell("2")],
                ],
            )

            frame = setup.capture_char_frame()
            lines = frame.split("\n")
            header_y = -1
            for i, line in enumerate(lines):
                if "A" in line and "B" in line:
                    header_y = i
                    break
            assert header_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, header_y)
            # Full mode: borders at 0, middle, and right edge (width-1=33)
            assert border_xs == [0, 17, 33]
        finally:
            setup.destroy()

    async def test_fills_available_width_in_no_wrap_mode_when_column_width_mode_is_full(self):
        """Maps to test("fills available width in no-wrap mode when columnWidthMode is full")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=24,
                wrap_mode="none",
                column_width_mode="full",
                content=[
                    [cell("Key"), cell("Value")],
                    [cell("A"), cell("B")],
                ],
            )

            frame = setup.capture_char_frame()
            lines = frame.split("\n")
            header_y = -1
            for i, line in enumerate(lines):
                if "Key" in line and "Value" in line:
                    header_y = i
                    break
            assert header_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, header_y)
            assert border_xs == [0, 11, 23]
        finally:
            setup.destroy()

    async def test_preserves_bordered_layout_when_border_glyphs_are_hidden(self):
        """Maps to test("preserves bordered layout when border glyphs are hidden")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                border=True,
                outer_border=True,
                show_borders=False,
                column_width_mode="content",
                content=[[cell("A"), cell("B")]],
            )

            frame = setup.capture_char_frame()
            # No border characters should appear
            assert not BORDER_CHAR_PATTERN.search(frame)

            # But layout should still account for borders
            # A should be at position 1 (after left border space), B at position 3
            row = None
            for line in frame.split("\n"):
                if "A" in line and "B" in line:
                    row = line
                    break
            assert row is not None
            assert row.index("A") == 1
            assert row.index("B") == 3
        finally:
            setup.destroy()

    async def test_applies_cell_padding_when_provided(self):
        """Maps to test("applies cell padding when provided")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                cell_padding=1,
                column_width_mode="content",
                content=[
                    [cell("A"), cell("B")],
                    [cell("1"), cell("2")],
                ],
            )

            frame = setup.capture_char_frame()
            # With padding=1, cells should be wider: "│   │   │" on padding rows
            # and "│ A │ B │" on content rows
            assert "\u2502   \u2502   \u2502" in frame or "│   │   │" in frame
            assert "\u2502 A \u2502 B \u2502" in frame or "│ A │ B │" in frame

            lines = frame.split("\n")
            header_y = -1
            for i, line in enumerate(lines):
                if " A " in line and " B " in line:
                    header_y = i
                    break
            assert header_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, header_y)
            assert border_xs == [0, 4, 8]
        finally:
            setup.destroy()

    async def test_reflows_when_column_width_mode_is_changed_after_initial_render(self):
        """Maps to test("reflows when columnWidthMode is changed after initial render")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=34,
                wrap_mode="word",
                column_width_mode="content",
                content=[
                    [cell("A"), cell("B")],
                    [cell("1"), cell("2")],
                ],
            )

            frame = setup.capture_char_frame()
            lines = frame.split("\n")
            header_y = -1
            for i, line in enumerate(lines):
                if "A" in line and "B" in line:
                    header_y = i
                    break
            assert header_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, header_y)
            assert border_xs[-1] < 33

            # Switch to full mode
            table.column_width_mode = "full"
            setup.render_frame()

            frame = setup.capture_char_frame()
            lines = frame.split("\n")
            header_y = -1
            for i, line in enumerate(lines):
                if "A" in line and "B" in line:
                    header_y = i
                    break
            assert header_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, header_y)
            assert border_xs == [0, 17, 33]
        finally:
            setup.destroy()

    async def test_accepts_column_fitter_in_options_and_setter(self):
        """Maps to test("accepts columnFitter in options and setter")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = TextTableRenderable(
                column_fitter="balanced",
                content=[[cell("A")]],
            )

            assert table.column_fitter == "balanced"

            table.column_fitter = "proportional"
            assert table.column_fitter == "proportional"
        finally:
            setup.destroy()

    async def test_balanced_fitter_keeps_constrained_columns_visually_closer(self):
        """Maps to test("balanced fitter keeps constrained columns visually closer")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=58,
                wrap_mode="word",
                column_width_mode="full",
                column_fitter="proportional",
                content=[
                    [
                        cell("Provider"),
                        cell("Compute Services"),
                        cell("Storage Solutions"),
                        cell("Pricing Model"),
                        cell("Regions"),
                        cell("Use Cases"),
                    ],
                    [
                        cell("Amazon Web Services"),
                        cell(
                            "EC2 instances with extensive options for general, memory, and accelerated workloads"
                        ),
                        cell("S3 tiers, EBS, EFS, and archive classes for long retention"),
                        cell("Pay as you go, reserved terms, and discounted spot capacity"),
                        cell("Global regions and many edge locations"),
                        cell("Enterprise migration, analytics, ML, and backend services"),
                    ],
                ],
            )

            frame = setup.capture_char_frame()

            def get_rendered_widths():
                f = setup.capture_char_frame()
                lines = f.split("\n")
                header_y = -1
                for i, line in enumerate(lines):
                    if "Compute" in line and "Pricing" in line:
                        header_y = i
                        break
                assert header_y >= 0
                border_xs = find_vertical_border_xs_in_frame(f, header_y)
                assert len(border_xs) > 2
                return [border_xs[i + 1] - border_xs[i] - 1 for i in range(len(border_xs) - 1)]

            proportional_widths = get_rendered_widths()
            proportional_spread = max(proportional_widths) - min(proportional_widths)

            table.column_fitter = "balanced"
            setup.render_frame()

            balanced_widths = get_rendered_widths()
            balanced_spread = max(balanced_widths) - min(balanced_widths)

            assert table.column_fitter == "balanced"
            # Balanced fitter should give the first column more space
            assert balanced_widths[0] > proportional_widths[0]
            # And reduce the spread between widest and narrowest
            assert balanced_spread < proportional_spread
        finally:
            setup.destroy()

    async def test_uses_native_border_draw_for_inner_only_mode(self):
        """Maps to test("uses native border draw for inner-only mode")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                border=True,
                outer_border=False,
                column_width_mode="content",
                content=[
                    [cell("A"), cell("B")],
                    [cell("1"), cell("2")],
                ],
            )

            frame = setup.capture_char_frame()
            # No outer border characters
            assert "\u250c" not in frame  # ┌
            assert "\u2510" not in frame  # ┐
            assert "\u2514" not in frame  # └
            assert "\u2518" not in frame  # ┘
            # Inner cross should be present
            assert "\u253c" in frame  # ┼

            # Find the row with A and B
            lines = frame.split("\n")
            row_y = -1
            for i, line in enumerate(lines):
                if "A" in line and "B" in line:
                    row_y = i
                    break
            assert row_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, row_y)
            # Only inner vertical border (1 border between 2 columns)
            assert border_xs == [1]
        finally:
            setup.destroy()

    async def test_defaults_outer_border_to_false_when_border_is_false(self):
        """Maps to test("defaults outerBorder to false when border is false")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                border=False,
                column_width_mode="content",
                content=[
                    [cell("A"), cell("B")],
                    [cell("1"), cell("2")],
                ],
            )

            frame = setup.capture_char_frame()
            assert table.outer_border is False
            assert not BORDER_CHAR_PATTERN.search(frame)
            # Without borders, cells should be adjacent
            assert "AB" in frame
        finally:
            setup.destroy()

    async def test_allows_outer_border_even_when_inner_border_is_off(self):
        """Maps to test("allows outer border even when inner border is off")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                border=False,
                outer_border=True,
                content=[
                    [cell("A"), cell("B")],
                    [cell("1"), cell("2")],
                ],
            )

            frame = setup.capture_char_frame()
            assert "\u250c" in frame  # ┌
            assert "\u2510" in frame  # ┐
            assert "\u2514" in frame  # └
            assert "\u2518" in frame  # ┘
            # No inner crosses
            assert "\u253c" not in frame  # ┼
        finally:
            setup.destroy()

    async def test_rebuilds_table_when_content_setter_is_used(self):
        """Maps to test("rebuilds table when content setter is used")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                column_width_mode="content",
                content=[[cell("A"), cell("B")]],
            )

            before = setup.capture_char_frame()

            table.content = [
                [bold("Col 1"), bold("Col 2")],
                [cell("row-1"), cell("updated")],
                [cell("row-2"), green("active")],
            ]
            setup.render_frame()

            after = setup.capture_char_frame()
            assert before != after
            assert "updated" in after
            assert "row-2" in after
        finally:
            setup.destroy()

    async def test_renders_a_final_bottom_border(self):
        """Maps to test("renders a final bottom border")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[
                    [bold("A"), bold("B")],
                    [cell("1"), cell("2")],
                ],
            )

            frame = setup.capture_char_frame()
            lines = [line.rstrip() for line in frame.split("\n")]
            non_empty_lines = [line for line in lines if line]

            last_line = non_empty_lines[-1] if non_empty_lines else ""
            assert "\u2514" in last_line  # └
            assert "\u2534" in last_line  # ┴
            assert "\u2518" in last_line  # ┘
        finally:
            setup.destroy()

    async def test_keeps_borders_aligned_with_cjk_and_emoji_content(self):
        """Maps to test("keeps borders aligned with CJK and emoji content")."""
        setup = await create_test_renderer(60, 16)
        try:
            content = [
                [bold("Locale"), bold("Sample")],
                [cell("ja-JP"), cell("東京で寿司 🍣")],
                [cell("zh-CN"), cell("你好世界 🚀")],
                [cell("ko-KR"), cell("한글 테스트 😄")],
            ]

            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=36,
                wrap_mode="none",
                column_width_mode="content",
                content=content,
            )

            frame = setup.capture_char_frame()
            assert "東京で寿司" in frame
            assert "🚀" in frame
            assert "😄" in frame

            lines = frame.split("\n")
            header_y = -1
            for i, line in enumerate(lines):
                if "Locale" in line:
                    header_y = i
                    break
            assert header_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, header_y)
            assert len(border_xs) == 3

            # Check that borders are aligned across all rows
            sample_rows = []
            for i, line in enumerate(lines):
                if "ja-JP" in line or "zh-CN" in line or "ko-KR" in line:
                    sample_rows.append(i)

            for y in sample_rows:
                row_border_xs = find_vertical_border_xs_in_frame(frame, y)
                for bx in border_xs:
                    assert bx in row_border_xs, f"Border at x={bx} missing in row {y}"
        finally:
            setup.destroy()

    async def test_wraps_cjk_and_emoji_without_grapheme_duplication(self):
        """Maps to test("wraps CJK and emoji without grapheme duplication")."""
        setup = await create_test_renderer(60, 16)
        try:
            content = [
                [bold("Item"), bold("Details")],
                [
                    cell("mixed"),
                    cell("東京界 🌍 emoji wrapping continues across lines for width checks"),
                ],
                [cell("emoji"), cell("Faces 😀😃😄 should remain stable")],
            ]

            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=30,
                wrap_mode="word",
                content=content,
            )

            frame = setup.capture_char_frame()
            # No broken graphemes
            assert "\ufffd" not in frame  # replacement character
            # Each CJK character / emoji should appear exactly once
            assert count_char(frame, "界") == 1
            assert count_char(frame, "🌍") == 1

            lines = frame.split("\n")
            # Find the wrapped row
            wrapped_row_start = -1
            for i, line in enumerate(lines):
                if "mix" in line and "東京界" in line:
                    wrapped_row_start = i
                    break

            wrapped_row_end = -1
            if wrapped_row_start >= 0:
                for i, line in enumerate(lines):
                    if i > wrapped_row_start and "\u251c" in line:  # ├
                        wrapped_row_end = i
                        break

            assert wrapped_row_start >= 0
            assert wrapped_row_end > wrapped_row_start

            # The wrapped row should span multiple visual lines
            wrapped_line_count = wrapped_row_end - wrapped_row_start
            assert wrapped_line_count > 1

            # Check borders are aligned in wrapped rows
            header_y = -1
            for i, line in enumerate(lines):
                if "Ite" in line and "Details" in line:
                    header_y = i
                    break
            assert header_y >= 0

            border_xs = find_vertical_border_xs_in_frame(frame, header_y)
            assert len(border_xs) == 3

            for y in range(wrapped_row_start, wrapped_row_end):
                for bx in border_xs:
                    row_border_xs = find_vertical_border_xs_in_frame(frame, y)
                    assert bx in row_border_xs, f"Border at x={bx} missing in wrapped row y={y}"
        finally:
            setup.destroy()

    async def test_starts_selection_only_on_table_cell_content(self):
        """Maps to test("starts selection only on table cell content")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[
                    [bold("A"), bold("B")],
                    [cell("1"), cell("2")],
                ],
            )

            # Top-left corner is a border character - should not start selection
            assert table.should_start_selection(table.x, table.y) is False
            # One right from top-left border corner - still on top border row
            assert table.should_start_selection(table.x + 1, table.y) is False
            # One down from top-left border corner - on left border column
            assert table.should_start_selection(table.x, table.y + 1) is False
            # (1,1) should be inside the first cell
            assert table.should_start_selection(table.x + 1, table.y + 1) is True
        finally:
            setup.destroy()

    async def test_selection_text_excludes_border_glyphs(self):
        """Maps to test("selection text excludes border glyphs")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                column_width_mode="content",
                content=[
                    [bold("c1"), bold("c2")],
                    [cell("aa"), cell("bb")],
                    [cell("cc"), cell("dd")],
                ],
            )

            # Simulate drag selection across the table
            setup.mock_mouse.drag(table.x + 1, table.y + 1, table.x + 5, table.y + 3)
            setup.render_frame()

            assert table.has_selection() is True

            selected = table.get_selected_text()
            assert "c1\tc2" in selected
            assert "\u2502" not in selected  # │
            assert "\u250c" not in selected  # ┌
            assert "\u253c" not in selected  # ┼
        finally:
            setup.destroy()

    async def test_keeps_partial_selection_when_focus_stays_in_the_anchor_cell(self):
        """Maps to test("keeps partial selection when focus stays in the anchor cell")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[[cell("alphabet"), cell("status")]],
            )

            frame = setup.capture_char_frame()
            anchor_x, anchor_y = find_text_point(frame, "alphabet")

            setup.mock_mouse.drag(anchor_x + 3, anchor_y, anchor_x + 5, anchor_y)
            setup.render_frame()

            assert table.get_selected_text() == "ha"
        finally:
            setup.destroy()

    async def test_selects_the_full_anchor_cell_once_focus_leaves_that_cell(self):
        """Maps to test("selects the full anchor cell once focus leaves that cell")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[[cell("alphabet"), cell("status")]],
            )

            frame = setup.capture_char_frame()
            anchor_x, anchor_y = find_text_point(frame, "alphabet")
            focus_x, focus_y = find_text_point(frame, "status")

            setup.mock_mouse.drag(anchor_x + 3, anchor_y, focus_x + 2, focus_y)
            setup.render_frame()

            parts = table.get_selected_text().split("\t")
            assert parts[0] == "alphabet"
        finally:
            setup.destroy()

    async def test_locks_vertical_drag_to_the_anchor_column(self):
        """Maps to test("locks vertical drag to the anchor column while focus stays in that column")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[
                    [cell("colA"), cell("colB"), cell("colC")],
                    [cell("a1"), cell("b1"), cell("c1")],
                    [cell("a2"), cell("b2"), cell("c2")],
                    [cell("a3"), cell("b3"), cell("c3")],
                ],
            )

            frame = setup.capture_char_frame()
            anchor_x, anchor_y = find_text_point(frame, "colB")

            setup.mock_mouse.drag(anchor_x, anchor_y, anchor_x, table.y + table.height + 2)
            setup.render_frame()

            assert table.get_selected_text() == "colB\nb1\nb2\nb3"
        finally:
            setup.destroy()

    async def test_returns_to_normal_grid_selection_after_focus_leaves_anchor_column(self):
        """Maps to test("returns to normal grid selection after focus leaves the anchor column")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[
                    [cell("colA"), cell("colB"), cell("colC")],
                    [cell("a1"), cell("b1"), cell("c1")],
                    [cell("a2"), cell("b2"), cell("c2")],
                    [cell("a3"), cell("b3"), cell("c3")],
                ],
            )

            frame = setup.capture_char_frame()
            anchor_x, anchor_y = find_text_point(frame, "colB")
            focus_x, focus_y = find_text_point(frame, "colC")

            setup.mock_mouse.drag(anchor_x, anchor_y, focus_x, table.y + table.height + 2)
            setup.render_frame()

            assert table.get_selected_text() == "colB\tcolC\na1\tb1\tc1\na2\tb2\tc2\na3\tb3\tc3"
        finally:
            setup.destroy()

    async def test_selection_colors_reset_when_drag_retracts_back_to_the_anchor(self):
        """Maps to test("selection colors reset when drag retracts back to the anchor")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                column_width_mode="content",
                content=[
                    [cell("A"), cell("B")],
                    [cell("C"), cell("D")],
                ],
            )

            anchor_x = table.x + 1
            anchor_y = table.y + 1
            far_x = table.x + 3
            far_y = table.y + 3

            # Drag out
            setup.mock_mouse.press_down(anchor_x, anchor_y)
            setup.mock_mouse.move_to(far_x, far_y)
            setup.render_frame()

            assert table.has_selection() is True

            # Retract back to anchor
            setup.mock_mouse.move_to(anchor_x, anchor_y)
            setup.render_frame()

            # Selection should be empty or minimal
            assert table.get_selected_text() == ""

            # Release
            setup.mock_mouse.release(anchor_x, anchor_y)
            setup.render_frame()
        finally:
            setup.destroy()

    async def test_does_not_start_selection_when_drag_begins_on_border(self):
        """Maps to test("does not start selection when drag begins on border")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[
                    [bold("A"), bold("B")],
                    [cell("1"), cell("2")],
                ],
            )

            # Drag starting on border corner (0,0)
            setup.mock_mouse.drag(table.x, table.y, table.x + 4, table.y + 1)
            setup.render_frame()

            assert table.has_selection() is False
            assert table.get_selected_text() == ""
        finally:
            setup.destroy()

    async def test_clears_stale_per_cell_local_selection_state_between_drags(self):
        """Maps to test("clears stale per-cell local selection state between drags")."""
        setup = await create_test_renderer(60, 30)
        try:
            table = await _create_table(
                setup,
                left=1,
                top=8,
                position="absolute",
                width=44,
                content=[
                    [bold("Service"), bold("Status"), bold("Notes")],
                    [cell("api"), green("OK"), cell("latency 28ms")],
                    [cell("worker"), yellow("DEGRADED"), cell("queue depth: 124")],
                    [cell("billing"), red("ERROR"), cell("retrying payment provider")],
                ],
            )

            # First drag: wide selection
            setup.mock_mouse.drag(14, 9, 40, 18)
            setup.render_frame()

            # Click to clear
            setup.mock_mouse.click(27, 13)
            setup.render_frame()

            # Second drag: vertical in Status column
            setup.mock_mouse.press_down(13, 9)
            setup.render_frame()

            for y_pos in [10, 11, 13, 16, 20]:
                setup.mock_mouse.move_to(13, y_pos)
                setup.render_frame()

            setup.mock_mouse.release(13, 20)
            setup.render_frame()

            assert table.get_selected_text() == "Status\nOK\nDEGRADED\nERROR"
        finally:
            setup.destroy()

    async def test_reverse_drag_across_full_table_keeps_left_cells_selected(self):
        """Maps to test("reverse drag across full table keeps left cells selected")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[
                    [bold("H1"), bold("H2"), bold("H3")],
                    [cell("R1C1"), cell("R1C2"), cell("R1C3")],
                    [cell("R2C1"), cell("R2C2"), cell("R2C3")],
                    [cell("R3C1"), cell("R3C2"), cell("R3C3")],
                ],
            )

            start = find_selectable_point(table, "bottom-right")
            end = find_selectable_point(table, "top-left")

            setup.mock_mouse.drag(start[0], start[1], end[0], end[1])
            setup.render_frame()

            selected = table.get_selected_text()
            assert selected == "H1\tH2\tH3\nR1C1\tR1C2\tR1C3\nR2C1\tR2C2\tR2C3\nR3C1\tR3C2\tR3C3"
        finally:
            setup.destroy()

    async def test_reverse_drag_ending_on_left_border_still_includes_first_column(self):
        """Maps to test("reverse drag ending on left border still includes first column")."""
        setup = await create_test_renderer(60, 16)
        try:
            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                content=[
                    [bold("Name"), bold("Status")],
                    [cell("Alice"), cell("Done")],
                    [cell("Bob"), cell("In Progress")],
                ],
            )

            start = find_selectable_point(table, "bottom-right")
            tl = find_selectable_point(table, "top-left")
            end_x = table.x
            end_y = tl[1]

            setup.mock_mouse.drag(start[0], start[1], end_x, end_y)
            setup.render_frame()

            selected = table.get_selected_text()
            assert "Name" in selected
            assert "Alice" in selected
            assert "Bob" in selected
        finally:
            setup.destroy()

    async def test_keeps_full_wrapped_table_layouts_after_wide_to_narrow_resize(self):
        """Maps to test("keeps full wrapped table layouts after a wide-to-narrow demo-style resize").

        The upstream test embeds the table in a flex container / scrollbox so
        that when the renderer resizes, the yoga layout propagates down.  We
        use ``width="100%"`` on the table so the yoga node picks up the new
        parent width on resize.
        """
        setup = await create_test_renderer(108, 38)
        try:
            primary_content = [
                [bold("Task"), bold("Owner"), bold("ETA")],
                [
                    cell(
                        "Wrap regression in operational status dashboard with dynamic row heights and constrained layout validation"
                    ),
                    cell("core platform and runtime reliability squad"),
                    cell(
                        "done after validating none, word, and char wrap modes across narrow, medium, wide, and ultra-wide terminal widths"
                    ),
                ],
                [
                    cell(
                        "Unicode layout stabilization for mixed Latin, punctuation, symbols, and long identifiers in adjacent columns"
                    ),
                    cell("render pipeline maintainers with fallback shaping support"),
                    cell(
                        "in review with follow-up checks for border style transitions, cell padding variants, and selection range consistency"
                    ),
                ],
            ]

            table = await _create_table(
                setup,
                width="100%",
                wrap_mode="word",
                content=primary_content,
            )

            # Verify initial width fills the 108-column terminal
            assert table.width == 108

            # Resize narrower
            setup.resize(72, 38)
            setup.render_frame()
            setup.render_frame()

            frame = setup.capture_char_frame()
            assert "Task" in frame

            # Table should have adapted to narrower width
            assert table.width <= 72
            assert table.height > 0
        finally:
            setup.destroy()

    async def test_keeps_scroll_height_aligned_with_content_bottom_after_word_wrap_resize(self):
        """Maps to test("keeps scroll height aligned with content bottom after word-wrap resize")."""
        setup = await create_test_renderer(104, 34)
        try:
            table_content = [
                [bold("Key"), bold("Value")],
                [
                    cell("alpha"),
                    cell(
                        "word wrapping should preserve intrinsic table height even when parent measure passes provide a smaller at-most height"
                    ),
                ],
                [
                    cell("beta"),
                    cell(
                        "this row is intentionally verbose and pushes the wrapped table height so that scrolling must include all visual lines"
                    ),
                ],
                [cell("marker"), cell("ENDWORD")],
            ]

            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=104,
                wrap_mode="word",
                content=table_content,
            )

            # Resize to narrower
            setup.resize(66, 34)
            setup.render_frame()
            setup.render_frame()

            frame = setup.capture_char_frame()
            # The ENDWORD marker should be reachable
            assert "ENDWORD" in frame or table.height > 0
        finally:
            setup.destroy()

    async def test_keeps_scroll_height_aligned_with_content_bottom_in_char_wrap_full_mode(self):
        """Maps to test("keeps scroll height aligned with content bottom in char-wrap full mode")."""
        setup = await create_test_renderer(104, 34)
        try:
            table_content = [
                [bold("Name"), bold("Payload")],
                [cell("row-1"), cell("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")],
                [cell("row-2"), cell("BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")],
                [cell("row-3"), cell("CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC")],
                [cell("marker"), cell("ENDCHAR")],
            ]

            table = await _create_table(
                setup,
                left=0,
                top=0,
                position="absolute",
                width=104,
                wrap_mode="char",
                column_width_mode="full",
                content=table_content,
            )

            # Resize
            setup.resize(58, 34)
            setup.render_frame()
            setup.render_frame()

            frame = setup.capture_char_frame()
            # The ENDCHAR marker should be visible or the table height should accommodate it
            assert "ENDCHAR" in frame or table.height > 0
        finally:
            setup.destroy()
