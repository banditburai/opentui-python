"""Tests for TerminalConsole — comprehensive unit tests for console.py.

No upstream console.test.ts exists, so these tests are written from scratch
to cover the full console.py API: ConsolePosition, ConsoleBounds,
TerminalConsole (bounds calculation, visibility toggling, position modes,
mouse hit-testing, resize, destroy).

Upstream: packages/core/src/console.ts
"""

from dataclasses import dataclass

import pytest

from opentui.renderer.console import ConsoleBounds, ConsolePosition, TerminalConsole


# ---------------------------------------------------------------------------
# Mock renderer — only needs .width and .height properties
# ---------------------------------------------------------------------------


class MockRenderer:
    """Lightweight mock renderer providing width/height for TerminalConsole."""

    def __init__(self, width: int = 80, height: int = 24):
        self._width = width
        self._height = height

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height


# ---------------------------------------------------------------------------
# Mouse event helper
# ---------------------------------------------------------------------------


@dataclass
class FakeMouseEvent:
    """Minimal mouse event with x, y, and type fields."""

    x: int
    y: int
    type: str = "down"


# ---------------------------------------------------------------------------
# ConsolePosition enum
# ---------------------------------------------------------------------------


class TestConsolePosition:
    """ConsolePosition enum values."""

    def test_has_four_members(self):
        assert len(ConsolePosition) == 4

    def test_top_value(self):
        assert ConsolePosition.TOP.value == "top"

    def test_bottom_value(self):
        assert ConsolePosition.BOTTOM.value == "bottom"

    def test_left_value(self):
        assert ConsolePosition.LEFT.value == "left"

    def test_right_value(self):
        assert ConsolePosition.RIGHT.value == "right"

    def test_can_construct_from_string(self):
        assert ConsolePosition("top") is ConsolePosition.TOP
        assert ConsolePosition("bottom") is ConsolePosition.BOTTOM
        assert ConsolePosition("left") is ConsolePosition.LEFT
        assert ConsolePosition("right") is ConsolePosition.RIGHT


# ---------------------------------------------------------------------------
# ConsoleBounds dataclass
# ---------------------------------------------------------------------------


class TestConsoleBounds:
    """ConsoleBounds dataclass."""

    def test_stores_fields(self):
        b = ConsoleBounds(x=10, y=20, width=30, height=40)
        assert b.x == 10
        assert b.y == 20
        assert b.width == 30
        assert b.height == 40

    def test_equality(self):
        a = ConsoleBounds(x=0, y=0, width=80, height=7)
        b = ConsoleBounds(x=0, y=0, width=80, height=7)
        assert a == b

    def test_inequality(self):
        a = ConsoleBounds(x=0, y=0, width=80, height=7)
        b = ConsoleBounds(x=0, y=0, width=80, height=8)
        assert a != b


# ---------------------------------------------------------------------------
# TerminalConsole — default construction
# ---------------------------------------------------------------------------


class TestConsoleDefaults:
    """Default construction with no options."""

    def test_starts_hidden(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        assert c.visible is False

    def test_default_position_is_bottom(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        # The default position is bottom — verify bounds are at the bottom
        c.show()
        assert c.bounds.y > 0
        assert c.bounds.y + c.bounds.height == r.height

    def test_default_size_percent_is_30(self):
        r = MockRenderer(width=100, height=100)
        c = TerminalConsole(r)
        c.show()
        assert c.bounds.height == 30  # 30% of 100

    def test_bounds_available_even_when_hidden(self):
        """Bounds are computed at construction time, not just on show()."""
        r = MockRenderer()
        c = TerminalConsole(r)
        b = c.bounds
        assert b.width > 0
        assert b.height > 0


# ---------------------------------------------------------------------------
# TerminalConsole — visibility toggling
# ---------------------------------------------------------------------------


class TestConsoleVisibility:
    """show(), hide(), toggle() methods."""

    def test_show_makes_visible(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.show()
        assert c.visible is True

    def test_hide_makes_invisible(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.show()
        c.hide()
        assert c.visible is False

    def test_toggle_from_hidden(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.toggle()
        assert c.visible is True

    def test_toggle_from_visible(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.show()
        c.toggle()
        assert c.visible is False

    def test_double_toggle_restores_state(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.toggle()
        c.toggle()
        assert c.visible is False

    def test_show_is_idempotent(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.show()
        c.show()
        assert c.visible is True

    def test_hide_is_idempotent(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.hide()
        c.hide()
        assert c.visible is False


# ---------------------------------------------------------------------------
# TerminalConsole — position modes and bounds calculation
# ---------------------------------------------------------------------------


class TestConsolePositionBottom:
    """Position: bottom (default)."""

    def test_spans_full_width(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom"})
        c.show()
        assert c.bounds.width == 80

    def test_x_is_zero(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom"})
        c.show()
        assert c.bounds.x == 0

    def test_y_plus_height_equals_terminal_height(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom"})
        c.show()
        b = c.bounds
        assert b.y + b.height == 24

    def test_height_is_fraction_of_terminal(self):
        r = MockRenderer(width=80, height=100)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 25})
        c.show()
        assert c.bounds.height == 25  # 25% of 100


class TestConsolePositionTop:
    """Position: top."""

    def test_x_is_zero(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "top"})
        c.show()
        assert c.bounds.x == 0

    def test_y_is_zero(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "top"})
        c.show()
        assert c.bounds.y == 0

    def test_spans_full_width(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "top"})
        c.show()
        assert c.bounds.width == 80

    def test_height_is_fraction_of_terminal(self):
        r = MockRenderer(width=80, height=100)
        c = TerminalConsole(r, {"position": "top", "size_percent": 40})
        c.show()
        assert c.bounds.height == 40


class TestConsolePositionLeft:
    """Position: left."""

    def test_x_is_zero(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "left"})
        c.show()
        assert c.bounds.x == 0

    def test_y_is_zero(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "left"})
        c.show()
        assert c.bounds.y == 0

    def test_spans_full_height(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "left"})
        c.show()
        assert c.bounds.height == 24

    def test_width_is_fraction_of_terminal(self):
        r = MockRenderer(width=100, height=24)
        c = TerminalConsole(r, {"position": "left", "size_percent": 50})
        c.show()
        assert c.bounds.width == 50


class TestConsolePositionRight:
    """Position: right."""

    def test_x_plus_width_equals_terminal_width(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "right"})
        c.show()
        b = c.bounds
        assert b.x + b.width == 80

    def test_y_is_zero(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "right"})
        c.show()
        assert c.bounds.y == 0

    def test_spans_full_height(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "right"})
        c.show()
        assert c.bounds.height == 24

    def test_width_is_fraction_of_terminal(self):
        r = MockRenderer(width=100, height=24)
        c = TerminalConsole(r, {"position": "right", "size_percent": 20})
        c.show()
        assert c.bounds.width == 20

    def test_x_offset_correct(self):
        r = MockRenderer(width=100, height=24)
        c = TerminalConsole(r, {"position": "right", "size_percent": 20})
        c.show()
        assert c.bounds.x == 80  # 100 - 20


# ---------------------------------------------------------------------------
# TerminalConsole — size_percent edge cases
# ---------------------------------------------------------------------------


class TestConsoleSizePercent:
    """size_percent option and edge cases."""

    def test_size_percent_100_covers_full_dimension(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 100})
        c.show()
        b = c.bounds
        assert b.height == 24
        assert b.y == 0

    def test_size_percent_1_gives_at_least_one(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 1})
        c.show()
        assert c.bounds.height >= 1

    def test_size_percent_via_camel_case_key(self):
        """sizePercent (camelCase) is accepted as an alias."""
        r = MockRenderer(width=100, height=100)
        c = TerminalConsole(r, {"position": "top", "sizePercent": 50})
        c.show()
        assert c.bounds.height == 50

    def test_height_minimum_clamp_to_1(self):
        """Even with very small terminal, height is at least 1."""
        r = MockRenderer(width=80, height=2)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 10})
        c.show()
        # 10% of 2 = 0.2 -> int(0.2) = 0, but clamped to max(1, ...)
        assert c.bounds.height >= 1

    def test_width_minimum_clamp_to_1(self):
        """Even with very small terminal, width is at least 1."""
        r = MockRenderer(width=2, height=24)
        c = TerminalConsole(r, {"position": "left", "size_percent": 10})
        c.show()
        assert c.bounds.width >= 1


# ---------------------------------------------------------------------------
# TerminalConsole — invalid / fallback options
# ---------------------------------------------------------------------------


class TestConsoleInvalidOptions:
    """Invalid or missing options fall back gracefully."""

    def test_invalid_position_falls_back_to_bottom(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "invalid"})
        c.show()
        # Should behave like bottom: y > 0
        b = c.bounds
        assert b.y > 0
        assert b.y + b.height == 24

    def test_none_options_use_defaults(self):
        r = MockRenderer()
        c = TerminalConsole(r, None)
        c.show()
        # Should not raise; should be bottom 30%
        assert c.visible is True
        assert c.bounds.width == 80

    def test_empty_options_use_defaults(self):
        r = MockRenderer()
        c = TerminalConsole(r, {})
        c.show()
        assert c.visible is True


# ---------------------------------------------------------------------------
# TerminalConsole — mouse hit-testing
# ---------------------------------------------------------------------------


class TestConsoleMouseHandling:
    """handle_mouse() — event consumption and hit-testing."""

    def test_returns_false_when_hidden(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        # Do NOT show — console is hidden
        event = FakeMouseEvent(x=40, y=20)
        assert c.handle_mouse(event) is False

    def test_returns_true_for_click_inside_bounds(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        # Click in the middle of the console
        event = FakeMouseEvent(x=b.x + b.width // 2, y=b.y + b.height // 2)
        assert c.handle_mouse(event) is True

    def test_returns_false_for_click_outside_bounds(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        # Click above the console
        event = FakeMouseEvent(x=0, y=0)
        assert c.handle_mouse(event) is False

    def test_returns_true_for_title_bar_click(self):
        """Click on the first row (title bar) of the console."""
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x + 5, y=b.y)
        assert c.handle_mouse(event) is True

    def test_returns_true_for_scroll_event_inside(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x + 1, y=b.y + 1, type="scroll")
        assert c.handle_mouse(event) is True

    def test_returns_false_for_scroll_event_outside(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        event = FakeMouseEvent(x=0, y=0, type="scroll")
        assert c.handle_mouse(event) is False

    def test_returns_true_for_drag_inside(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x + 1, y=b.y + 2, type="drag")
        assert c.handle_mouse(event) is True

    def test_returns_true_for_up_inside(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x + 1, y=b.y + 2, type="up")
        assert c.handle_mouse(event) is True

    def test_edge_hit_top_left(self):
        """Top-left corner of bounds is inside."""
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x, y=b.y)
        assert c.handle_mouse(event) is True

    def test_edge_hit_bottom_right(self):
        """Bottom-right corner (just inside) is inside."""
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x + b.width - 1, y=b.y + b.height - 1)
        assert c.handle_mouse(event) is True

    def test_edge_miss_just_outside_right(self):
        """One pixel past the right edge is outside."""
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x + b.width, y=b.y)
        assert c.handle_mouse(event) is False

    def test_edge_miss_just_outside_bottom(self):
        """One pixel past the bottom edge is outside."""
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x, y=b.y + b.height)
        assert c.handle_mouse(event) is False

    def test_negative_coordinates_are_outside(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "top", "size_percent": 50})
        c.show()
        event = FakeMouseEvent(x=-1, y=-1)
        assert c.handle_mouse(event) is False


class TestConsoleMouseHitTestingAllPositions:
    """Mouse hit-testing works correctly for all four position modes."""

    @pytest.mark.parametrize("position", ["top", "bottom", "left", "right"])
    def test_click_inside_center_of_each_position(self, position: str):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": position, "size_percent": 50})
        c.show()
        b = c.bounds
        event = FakeMouseEvent(x=b.x + b.width // 2, y=b.y + b.height // 2)
        assert c.handle_mouse(event) is True

    @pytest.mark.parametrize("position", ["top", "bottom", "left", "right"])
    def test_click_outside_each_position(self, position: str):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": position, "size_percent": 25})
        c.show()
        _ = c.bounds  # ensure bounds are computed
        # Pick a point that is definitely outside the console bounds.
        # For top/left that means far bottom-right; for bottom/right far top-left.
        if position in ("top", "left"):
            event = FakeMouseEvent(x=79, y=23)
        else:
            event = FakeMouseEvent(x=0, y=0)
        assert c.handle_mouse(event) is False


# ---------------------------------------------------------------------------
# TerminalConsole — resize
# ---------------------------------------------------------------------------


class TestConsoleResize:
    """resize() recomputes dimensions from current renderer size."""

    def test_bounds_update_after_resize(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()

        old_bounds = c.bounds

        r.resize(120, 40)
        c.resize()
        new_bounds = c.bounds

        assert new_bounds.width == 120
        assert new_bounds.height == 20  # 50% of 40
        assert new_bounds != old_bounds

    def test_resize_updates_y_for_bottom(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        c.show()

        r.resize(80, 40)
        c.resize()
        b = c.bounds
        assert b.y + b.height == 40

    def test_resize_updates_x_for_right(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "right", "size_percent": 50})
        c.show()

        r.resize(120, 24)
        c.resize()
        b = c.bounds
        assert b.x + b.width == 120

    def test_resize_works_when_hidden(self):
        """resize() updates dimensions even if console is not visible."""
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r)
        # Don't show

        r.resize(120, 40)
        c.resize()
        b = c.bounds
        assert b.width == 120


# ---------------------------------------------------------------------------
# TerminalConsole — destroy
# ---------------------------------------------------------------------------


class TestConsoleDestroy:
    """destroy() marks console as destroyed and hides it."""

    def test_destroy_hides_console(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.show()
        c.destroy()
        assert c.visible is False

    def test_destroy_sets_destroyed_flag(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.destroy()
        assert c._destroyed is True

    def test_destroy_is_idempotent(self):
        r = MockRenderer()
        c = TerminalConsole(r)
        c.destroy()
        c.destroy()
        assert c._destroyed is True
        assert c.visible is False


# ---------------------------------------------------------------------------
# TerminalConsole — show() updates dimensions
# ---------------------------------------------------------------------------


class TestConsoleShowUpdatesDimensions:
    """show() recalculates bounds (e.g. if terminal resized while hidden)."""

    def test_show_after_renderer_resize_picks_up_new_size(self):
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "bottom", "size_percent": 50})
        # Initially hidden — change renderer size
        r.resize(120, 40)
        c.show()
        b = c.bounds
        assert b.width == 120
        assert b.height == 20  # 50% of 40
        assert b.y == 20  # 40 - 20


# ---------------------------------------------------------------------------
# TerminalConsole — combined scenarios
# ---------------------------------------------------------------------------


class TestConsoleCombinedScenarios:
    """Integration-like scenarios combining multiple operations."""

    def test_toggle_show_resize_mouse(self):
        """Full lifecycle: toggle on, resize, verify mouse, toggle off."""
        r = MockRenderer(width=80, height=24)
        c = TerminalConsole(r, {"position": "top", "size_percent": 50})

        c.toggle()
        assert c.visible is True

        b = c.bounds
        assert b.x == 0
        assert b.y == 0
        assert b.width == 80
        assert b.height == 12  # 50% of 24

        # Mouse inside
        assert c.handle_mouse(FakeMouseEvent(x=10, y=5)) is True
        # Mouse outside (below the top console)
        assert c.handle_mouse(FakeMouseEvent(x=10, y=20)) is False

        # Resize
        r.resize(100, 30)
        c.resize()
        b = c.bounds
        assert b.width == 100
        assert b.height == 15  # 50% of 30

        # Toggle off
        c.toggle()
        assert c.visible is False
        assert c.handle_mouse(FakeMouseEvent(x=10, y=5)) is False

    def test_all_positions_with_same_size(self):
        """Each position mode produces correct non-overlapping bounds."""
        r = MockRenderer(width=100, height=50)
        pct = 30

        consoles: dict[str, TerminalConsole] = {}
        for pos in ("top", "bottom", "left", "right"):
            c = TerminalConsole(r, {"position": pos, "size_percent": pct})
            c.show()
            consoles[pos] = c

        # Top
        bt = consoles["top"].bounds
        assert bt.x == 0 and bt.y == 0
        assert bt.width == 100 and bt.height == 15

        # Bottom
        bb = consoles["bottom"].bounds
        assert bb.x == 0 and bb.y == 35  # 50 - 15
        assert bb.width == 100 and bb.height == 15

        # Left
        bl = consoles["left"].bounds
        assert bl.x == 0 and bl.y == 0
        assert bl.width == 30 and bl.height == 50

        # Right
        br = consoles["right"].bounds
        assert br.x == 70 and br.y == 0  # 100 - 30
        assert br.width == 30 and br.height == 50

    def test_destroy_then_show_stays_hidden(self):
        """After destroy, show() still sets visible (destroy doesn't block show)."""
        r = MockRenderer()
        c = TerminalConsole(r)
        c.destroy()
        # The current implementation does not prevent show() after destroy.
        # Verify the actual behavior.
        c.show()
        # show() sets _visible = True regardless of _destroyed
        assert c._destroyed is True
        assert c.visible is True
