"""Unit tests for opentui.selection module.

Tests for SelectionAnchor, Selection, LocalSelectionBounds, and
convert_global_to_local_selection. No upstream TypeScript test file exists
for lib/selection.ts — these tests are written from the Python implementation.
"""

from __future__ import annotations

from opentui.selection import (
    LocalSelectionBounds,
    Selection,
    SelectionAnchor,
    convert_global_to_local_selection,
)


# ---------------------------------------------------------------------------
# Helpers — lightweight renderable stubs
# ---------------------------------------------------------------------------


class _FakeRenderable:
    """Minimal stub exposing .x, .y for SelectionAnchor and Selection tests."""

    def __init__(self, x: int = 0, y: int = 0, *, text: str = "", destroyed: bool = False) -> None:
        self.x = x
        self.y = y
        self._text = text
        self._destroyed = destroyed
        self.is_destroyed = destroyed

    def get_selected_text(self) -> str:
        return self._text


# ===========================================================================
# SelectionAnchor
# ===========================================================================


class TestSelectionAnchor:
    """Tests for SelectionAnchor position tracking relative to a renderable."""

    def test_anchor_stores_relative_offset(self):
        """Anchor at absolute (15, 25) on a renderable at (10, 20)
        should store a relative offset of (5, 5)."""
        r = _FakeRenderable(x=10, y=20)
        anchor = SelectionAnchor(r, absolute_x=15, absolute_y=25)
        assert anchor.x == 15
        assert anchor.y == 25

    def test_anchor_follows_renderable_move(self):
        """When the renderable moves, the anchor's absolute position updates."""
        r = _FakeRenderable(x=10, y=20)
        anchor = SelectionAnchor(r, absolute_x=15, absolute_y=25)
        # Simulate a scroll / layout shift
        r.x = 30
        r.y = 40
        assert anchor.x == 35
        assert anchor.y == 45

    def test_anchor_at_renderable_origin(self):
        """Anchor at the renderable's own origin should have 0 relative offset."""
        r = _FakeRenderable(x=5, y=8)
        anchor = SelectionAnchor(r, absolute_x=5, absolute_y=8)
        assert anchor.x == 5
        assert anchor.y == 8
        # After move, still at renderable origin
        r.x = 0
        r.y = 0
        assert anchor.x == 0
        assert anchor.y == 0

    def test_anchor_with_negative_relative_offset(self):
        """Anchor can be before the renderable origin (negative relative)."""
        r = _FakeRenderable(x=10, y=10)
        anchor = SelectionAnchor(r, absolute_x=7, absolute_y=5)
        assert anchor.x == 7
        assert anchor.y == 5
        r.x = 20
        r.y = 20
        assert anchor.x == 17
        assert anchor.y == 15

    def test_anchor_with_zero_position_renderable(self):
        """Renderable at (0, 0) — relative offset equals the absolute coords."""
        r = _FakeRenderable(x=0, y=0)
        anchor = SelectionAnchor(r, absolute_x=3, absolute_y=4)
        assert anchor.x == 3
        assert anchor.y == 4


# ===========================================================================
# Selection — construction and basic properties
# ===========================================================================


class TestSelectionConstruction:
    """Tests for Selection initial state after construction."""

    def test_initial_properties(self):
        """A new Selection should be active, dragging, and not marked as start."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 5, "y": 5})
        assert sel.is_active is True
        assert sel.is_dragging is True
        assert sel.is_start is False

    def test_anchor_and_focus_values(self):
        """anchor and focus properties must reflect the constructor arguments."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 2, "y": 3}, {"x": 7, "y": 9})
        assert sel.anchor == {"x": 2, "y": 3}
        assert sel.focus == {"x": 7, "y": 9}

    def test_anchor_dict_is_copy(self):
        """Mutating the returned anchor dict must not affect internal state."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 1, "y": 2}, {"x": 3, "y": 4})
        a = sel.anchor
        a["x"] = 999
        assert sel.anchor == {"x": 1, "y": 2}

    def test_focus_dict_is_copy(self):
        """Mutating the returned focus dict must not affect internal state."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 1, "y": 2}, {"x": 3, "y": 4})
        f = sel.focus
        f["x"] = 999
        assert sel.focus == {"x": 3, "y": 4}

    def test_empty_selected_and_touched_renderables(self):
        """Renderable lists start empty."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 0, "y": 0})
        assert sel.selected_renderables == []
        assert sel.touched_renderables == []


# ===========================================================================
# Selection — setters
# ===========================================================================


class TestSelectionSetters:
    """Tests for Selection property setters."""

    def test_set_focus(self):
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 5, "y": 5})
        sel.focus = {"x": 10, "y": 12}
        assert sel.focus == {"x": 10, "y": 12}

    def test_set_focus_makes_defensive_copy(self):
        """The internal focus should not change when the input dict is mutated."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 5, "y": 5})
        d = {"x": 10, "y": 12}
        sel.focus = d
        d["x"] = 999
        assert sel.focus == {"x": 10, "y": 12}

    def test_set_is_active(self):
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 0, "y": 0})
        sel.is_active = False
        assert sel.is_active is False
        sel.is_active = True
        assert sel.is_active is True

    def test_set_is_dragging(self):
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 0, "y": 0})
        sel.is_dragging = False
        assert sel.is_dragging is False

    def test_set_is_start(self):
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 0, "y": 0})
        sel.is_start = True
        assert sel.is_start is True


# ===========================================================================
# Selection — bounds computation
# ===========================================================================


class TestSelectionBounds:
    """Tests for Selection.bounds property."""

    def test_normal_direction_bounds(self):
        """Anchor before focus — standard forward selection."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 2, "y": 3}, {"x": 8, "y": 7})
        b = sel.bounds
        assert b == {"x": 2, "y": 3, "width": 7, "height": 5}

    def test_inverted_direction_bounds(self):
        """Focus before anchor — backward selection. Bounds must still be correct."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 8, "y": 7}, {"x": 2, "y": 3})
        b = sel.bounds
        assert b == {"x": 2, "y": 3, "width": 7, "height": 5}

    def test_single_cell_selection(self):
        """Anchor and focus at the same position covers 1x1."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 5, "y": 5}, {"x": 5, "y": 5})
        b = sel.bounds
        assert b == {"x": 5, "y": 5, "width": 1, "height": 1}

    def test_horizontal_line_selection(self):
        """Selection along a single row."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 3}, {"x": 9, "y": 3})
        b = sel.bounds
        assert b == {"x": 0, "y": 3, "width": 10, "height": 1}

    def test_vertical_line_selection(self):
        """Selection along a single column."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 4, "y": 0}, {"x": 4, "y": 5})
        b = sel.bounds
        assert b == {"x": 4, "y": 0, "width": 1, "height": 6}

    def test_bounds_at_origin(self):
        """Selection starting at (0,0)."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 3, "y": 2})
        b = sel.bounds
        assert b == {"x": 0, "y": 0, "width": 4, "height": 3}

    def test_bounds_follow_anchor_movement(self):
        """When the anchor renderable moves, bounds must update."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 2, "y": 3}, {"x": 5, "y": 6})
        b1 = sel.bounds
        assert b1 == {"x": 2, "y": 3, "width": 4, "height": 4}

        # Simulate renderable move (anchor follows)
        r.x = 10
        r.y = 10
        b2 = sel.bounds
        # Anchor is now (12, 13), focus is still (5, 6)
        assert b2 == {"x": 5, "y": 6, "width": 8, "height": 8}

    def test_bounds_after_focus_update(self):
        """Changing focus updates the bounds."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 5, "y": 5})
        sel.focus = {"x": 10, "y": 10}
        b = sel.bounds
        assert b == {"x": 0, "y": 0, "width": 11, "height": 11}


# ===========================================================================
# Selection — renderable tracking
# ===========================================================================


class TestSelectionRenderableTracking:
    """Tests for selected and touched renderable lists."""

    def test_update_selected_renderables(self):
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 0, "y": 0})
        items = [_FakeRenderable(), _FakeRenderable()]
        sel.update_selected_renderables(items)
        assert sel.selected_renderables is items

    def test_update_touched_renderables(self):
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 0, "y": 0})
        items = [_FakeRenderable()]
        sel.update_touched_renderables(items)
        assert sel.touched_renderables is items

    def test_replace_selected_renderables(self):
        """Updating selected renderables replaces the previous list entirely."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 0, "y": 0})
        first = [_FakeRenderable()]
        sel.update_selected_renderables(first)
        second = [_FakeRenderable(), _FakeRenderable()]
        sel.update_selected_renderables(second)
        assert sel.selected_renderables is second


# ===========================================================================
# Selection — get_selected_text
# ===========================================================================


class TestSelectionGetSelectedText:
    """Tests for Selection.get_selected_text()."""

    def test_single_renderable_text(self):
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 10, "y": 0})
        sel.update_selected_renderables(
            [
                _FakeRenderable(x=0, y=0, text="hello"),
            ]
        )
        assert sel.get_selected_text() == "hello"

    def test_multiple_renderables_sorted_by_reading_order(self):
        """Renderables are sorted top-to-bottom, then left-to-right."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 20, "y": 3})
        sel.update_selected_renderables(
            [
                _FakeRenderable(x=10, y=2, text="second line right"),
                _FakeRenderable(x=0, y=0, text="first line"),
                _FakeRenderable(x=0, y=2, text="second line left"),
            ]
        )
        result = sel.get_selected_text()
        assert result == "first line\nsecond line left\nsecond line right"

    def test_skips_destroyed_renderable_via_private_flag(self):
        """Renderables with _destroyed=True are excluded."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 10, "y": 1})
        sel.update_selected_renderables(
            [
                _FakeRenderable(x=0, y=0, text="kept"),
                _FakeRenderable(x=0, y=1, text="gone", destroyed=True),
            ]
        )
        assert sel.get_selected_text() == "kept"

    def test_skips_destroyed_renderable_via_public_flag(self):
        """Renderables with is_destroyed=True are excluded."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 10, "y": 1})
        gone = _FakeRenderable(x=0, y=1, text="gone")
        gone._destroyed = False
        gone.is_destroyed = True
        sel.update_selected_renderables(
            [
                _FakeRenderable(x=0, y=0, text="kept"),
                gone,
            ]
        )
        assert sel.get_selected_text() == "kept"

    def test_skips_empty_text(self):
        """Renderables returning empty string from get_selected_text are excluded."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 10, "y": 2})
        sel.update_selected_renderables(
            [
                _FakeRenderable(x=0, y=0, text="line one"),
                _FakeRenderable(x=0, y=1, text=""),
                _FakeRenderable(x=0, y=2, text="line three"),
            ]
        )
        assert sel.get_selected_text() == "line one\nline three"

    def test_no_selected_renderables(self):
        """get_selected_text with empty list returns empty string."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 0, "y": 0})
        assert sel.get_selected_text() == ""

    def test_all_destroyed_returns_empty(self):
        """If every selected renderable is destroyed, result is empty."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 10, "y": 1})
        sel.update_selected_renderables(
            [
                _FakeRenderable(x=0, y=0, text="a", destroyed=True),
                _FakeRenderable(x=0, y=1, text="b", destroyed=True),
            ]
        )
        assert sel.get_selected_text() == ""


# ===========================================================================
# LocalSelectionBounds dataclass
# ===========================================================================


class TestLocalSelectionBounds:
    """Tests for the LocalSelectionBounds dataclass."""

    def test_fields(self):
        b = LocalSelectionBounds(
            anchor_x=1,
            anchor_y=2,
            focus_x=3,
            focus_y=4,
            is_active=True,
        )
        assert b.anchor_x == 1
        assert b.anchor_y == 2
        assert b.focus_x == 3
        assert b.focus_y == 4
        assert b.is_active is True

    def test_equality(self):
        """Dataclass equality check."""
        a = LocalSelectionBounds(0, 0, 5, 5, True)
        b = LocalSelectionBounds(0, 0, 5, 5, True)
        assert a == b

    def test_inequality(self):
        a = LocalSelectionBounds(0, 0, 5, 5, True)
        b = LocalSelectionBounds(0, 0, 5, 5, False)
        assert a != b


# ===========================================================================
# convert_global_to_local_selection
# ===========================================================================


class TestConvertGlobalToLocalSelection:
    """Tests for the convert_global_to_local_selection helper."""

    def test_returns_none_when_selection_is_none(self):
        assert convert_global_to_local_selection(None, 0, 0) is None

    def test_returns_none_when_selection_is_inactive(self):
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 5, "y": 5}, {"x": 10, "y": 10})
        sel.is_active = False
        assert convert_global_to_local_selection(sel, 0, 0) is None

    def test_converts_to_local_coordinates(self):
        """Global anchor (10, 20), focus (15, 25) with local origin (3, 7)."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 10, "y": 20}, {"x": 15, "y": 25})
        result = convert_global_to_local_selection(sel, local_x=3, local_y=7)
        assert result is not None
        assert result.anchor_x == 7
        assert result.anchor_y == 13
        assert result.focus_x == 12
        assert result.focus_y == 18
        assert result.is_active is True

    def test_local_at_origin_gives_global_coords(self):
        """When local origin is (0, 0), local coords equal global coords."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 4, "y": 8}, {"x": 12, "y": 16})
        result = convert_global_to_local_selection(sel, local_x=0, local_y=0)
        assert result is not None
        assert result.anchor_x == 4
        assert result.anchor_y == 8
        assert result.focus_x == 12
        assert result.focus_y == 16

    def test_negative_local_coords(self):
        """When global coords are smaller than local origin, result is negative."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 2, "y": 3}, {"x": 4, "y": 5})
        result = convert_global_to_local_selection(sel, local_x=10, local_y=10)
        assert result is not None
        assert result.anchor_x == -8
        assert result.anchor_y == -7
        assert result.focus_x == -6
        assert result.focus_y == -5

    def test_always_reports_is_active_true(self):
        """When the function returns a result, is_active is always True."""
        r = _FakeRenderable(x=0, y=0)
        sel = Selection(r, {"x": 0, "y": 0}, {"x": 1, "y": 1})
        result = convert_global_to_local_selection(sel, 0, 0)
        assert result is not None
        assert result.is_active is True

    def test_respects_anchor_renderable_move(self):
        """If the anchor renderable has moved, global anchor position changes."""
        r = _FakeRenderable(x=5, y=5)
        sel = Selection(r, {"x": 10, "y": 10}, {"x": 20, "y": 20})
        # Anchor relative offset is (5, 5). Now move renderable.
        r.x = 15
        r.y = 15
        # Anchor is now (20, 20), focus is still (20, 20)
        result = convert_global_to_local_selection(sel, local_x=0, local_y=0)
        assert result is not None
        assert result.anchor_x == 20
        assert result.anchor_y == 20
        assert result.focus_x == 20
        assert result.focus_y == 20
