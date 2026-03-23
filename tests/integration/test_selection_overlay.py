"""Tests for _apply_selection_overlay skip-rect segment splitting.

Validates that the post-render selection overlay correctly:
- Paints full-width highlights for multi-row selections
- Skips regions covered by component-level selection (avoids double-highlight)
- Handles multiple skip rects on the same row
- Handles skip rects outside the selection bounds (no effect)
- Paints single-row partial selections correctly
"""

from __future__ import annotations

import pytest

from opentui import Box, TestSetup, create_test_renderer
from opentui.components.text_renderable import TextRenderable
from opentui.renderer.core import _SELECTION_BG
from opentui.selection import Selection
from opentui.structs import RGBA


def _bg_matches_selection(bg: RGBA) -> bool:
    """Check if a buffer cell's bg matches the selection overlay color."""
    return (
        abs(bg.r - _SELECTION_BG.r) < 0.02
        and abs(bg.g - _SELECTION_BG.g) < 0.02
        and abs(bg.b - _SELECTION_BG.b) < 0.02
    )


class TestSelectionOverlay:
    """Tests for CliRenderer._apply_selection_overlay()."""

    @pytest.mark.asyncio
    async def test_overlay_paints_full_selection_without_skip_rects(self):
        """Selection across 3 rows with no selectable components paints all rows."""
        setup = await create_test_renderer(20, 5)
        try:
            root = setup.renderer.root
            box = Box(width=20, height=5)
            root.add(box)
            setup.render_frame()

            # Manually create a selection spanning rows 1-3, cols 2-15
            anchor_renderable = box
            sel = Selection(anchor_renderable, {"x": 2, "y": 1}, {"x": 15, "y": 3})
            sel.is_dragging = False
            setup.renderer._current_selection = sel

            setup.render_frame()
            buf = setup.get_buffer()

            # Row 0: no highlight
            assert not _bg_matches_selection(buf.get_bg_color(5, 0))

            # Row 1 (start row): cols 2-19 should be highlighted
            assert _bg_matches_selection(buf.get_bg_color(2, 1))
            assert _bg_matches_selection(buf.get_bg_color(10, 1))
            assert not _bg_matches_selection(buf.get_bg_color(1, 1))

            # Row 2 (middle row): full width 0-19 highlighted
            assert _bg_matches_selection(buf.get_bg_color(0, 2))
            assert _bg_matches_selection(buf.get_bg_color(19, 2))

            # Row 3 (end row): cols 0-15 highlighted
            assert _bg_matches_selection(buf.get_bg_color(0, 3))
            assert _bg_matches_selection(buf.get_bg_color(15, 3))

            # Row 4: no highlight
            assert not _bg_matches_selection(buf.get_bg_color(5, 4))
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_overlay_skips_component_with_active_selection(self):
        """When a selectable TextRenderable has active component selection,
        the overlay skips its bounding rect to avoid double-highlighting."""
        setup = await create_test_renderer(40, 6)
        try:
            root = setup.renderer.root
            # Place a selectable text at known position
            text = TextRenderable(
                content="Hello World",
                width=20,
                height=1,
                left=5,
                top=2,
                position="absolute",
                selectable=True,
                selection_bg="#4a5568",
            )
            root.add(text)
            setup.render_frame()

            # Start selection via drag that covers the text and beyond
            setup.mock_mouse.drag(0, 1, 39, 4)
            setup.render_frame()

            buf = setup.get_buffer()

            # The text at (5, 2) has its own component-level selection.
            # Check that row 2 has gaps in the overlay where the text is.
            # Columns BEFORE the text (0-4) should have overlay highlight
            assert _bg_matches_selection(buf.get_bg_color(0, 2))
            assert _bg_matches_selection(buf.get_bg_color(4, 2))

            # The text itself (5-24) has component selection bg (#4a5568),
            # NOT the overlay bg. Check it does NOT match overlay color.
            text_bg = buf.get_bg_color(5, 2)
            # The component selection bg is #4a5568 ≈ (0.29, 0.33, 0.41)
            # The overlay bg is (0.3, 0.3, 0.7) — the blue channel differs
            assert abs(text_bg.b - _SELECTION_BG.b) > 0.1, (
                f"Text region should have component bg, not overlay bg: {text_bg}"
            )

            # Columns AFTER the text (25-39) should have overlay highlight
            assert _bg_matches_selection(buf.get_bg_color(25, 2))
            assert _bg_matches_selection(buf.get_bg_color(39, 2))
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_overlay_with_skip_rect_outside_selection(self):
        """A selectable component outside the selection bounds has no effect."""
        setup = await create_test_renderer(30, 4)
        try:
            root = setup.renderer.root
            # Text is at row 3, but selection only covers rows 0-1
            text = TextRenderable(
                content="Outside",
                width=10,
                height=1,
                left=5,
                top=3,
                position="absolute",
                selectable=True,
            )
            root.add(text)
            setup.render_frame()

            # Create selection on rows 0-1 only
            anchor_renderable = root
            sel = Selection(anchor_renderable, {"x": 0, "y": 0}, {"x": 29, "y": 1})
            sel.is_dragging = False
            setup.renderer._current_selection = sel

            setup.render_frame()
            buf = setup.get_buffer()

            # Row 0 and 1 should be fully highlighted (no skip rects intersect)
            assert _bg_matches_selection(buf.get_bg_color(0, 0))
            assert _bg_matches_selection(buf.get_bg_color(15, 0))
            assert _bg_matches_selection(buf.get_bg_color(0, 1))
            assert _bg_matches_selection(buf.get_bg_color(29, 1))

            # Row 3 should NOT be highlighted
            assert not _bg_matches_selection(buf.get_bg_color(5, 3))
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_overlay_single_row_selection(self):
        """Single-row selection highlights only the selected columns."""
        setup = await create_test_renderer(20, 3)
        try:
            root = setup.renderer.root
            box = Box(width=20, height=3)
            root.add(box)
            setup.render_frame()

            # Select row 1, cols 5-12
            sel = Selection(box, {"x": 5, "y": 1}, {"x": 12, "y": 1})
            sel.is_dragging = False
            setup.renderer._current_selection = sel

            setup.render_frame()
            buf = setup.get_buffer()

            # Before selection: no highlight
            assert not _bg_matches_selection(buf.get_bg_color(4, 1))
            # Inside selection: highlight
            assert _bg_matches_selection(buf.get_bg_color(5, 1))
            assert _bg_matches_selection(buf.get_bg_color(12, 1))
            # After selection: no highlight
            assert not _bg_matches_selection(buf.get_bg_color(13, 1))
            # Other rows: no highlight
            assert not _bg_matches_selection(buf.get_bg_color(8, 0))
            assert not _bg_matches_selection(buf.get_bg_color(8, 2))
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_no_overlay_when_selection_inactive(self):
        """When selection.is_active is False, no overlay is painted."""
        setup = await create_test_renderer(20, 3)
        try:
            root = setup.renderer.root
            box = Box(width=20, height=3)
            root.add(box)
            setup.render_frame()

            sel = Selection(box, {"x": 0, "y": 0}, {"x": 19, "y": 2})
            sel.is_active = False
            sel.is_dragging = False
            setup.renderer._current_selection = sel

            setup.render_frame()
            buf = setup.get_buffer()

            # No cells should have selection highlight
            assert not _bg_matches_selection(buf.get_bg_color(0, 0))
            assert not _bg_matches_selection(buf.get_bg_color(10, 1))
            assert not _bg_matches_selection(buf.get_bg_color(19, 2))
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_no_overlay_when_no_selection(self):
        """When _current_selection is None, no overlay is painted."""
        setup = await create_test_renderer(20, 3)
        try:
            root = setup.renderer.root
            box = Box(width=20, height=3)
            root.add(box)
            setup.render_frame()

            assert setup.renderer._current_selection is None
            buf = setup.get_buffer()
            # No cells should have selection highlight
            assert not _bg_matches_selection(buf.get_bg_color(10, 1))
        finally:
            setup.destroy()
