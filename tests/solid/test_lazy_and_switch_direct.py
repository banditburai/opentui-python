"""Tests for Lazy component and Switch with direct BaseRenderable in cases=.

These test the new DX overhaul features:
- Lazy: deferred child construction (replaces old Show(build=lambda: ...))
- Switch cases= accepting direct BaseRenderable values (auto-wrapped)
"""

from opentui import test_render as _test_render
from opentui.components.base import BaseRenderable, Renderable
from opentui.components.box import Box
from opentui.components.control_flow import For, Lazy, Match, Show, Switch
from opentui.components.text import Text
from opentui.signals import Signal


async def _strict_render(component_fn, options):
    return await _test_render(component_fn, dict(options))


# ---------------------------------------------------------------------------
# Lazy
# ---------------------------------------------------------------------------


class TestLazy:
    def test_build_fn_not_called_on_construction(self):
        """Lazy does NOT call build_fn during __init__."""
        called = []

        def build():
            called.append(True)
            return BaseRenderable(key="child")

        lazy = Lazy(build, key="test-lazy")
        assert called == [], "build_fn should not be called during __init__"
        assert lazy._built is False

    def test_build_fn_called_on_pre_configure_yoga(self):
        """Lazy calls build_fn on first _pre_configure_yoga."""
        called = []

        def build():
            called.append(True)
            return BaseRenderable(key="child")

        lazy = Lazy(build, key="test-lazy")
        lazy._pre_configure_yoga()
        assert called == [True]
        assert lazy._built is True
        assert len(lazy._children) == 1
        assert lazy._children[0].key == "child"

    def test_build_fn_only_called_once(self):
        """Second _pre_configure_yoga does NOT call build_fn again."""
        call_count = []

        def build():
            call_count.append(True)
            return BaseRenderable(key="child")

        lazy = Lazy(build, key="test-lazy")
        lazy._pre_configure_yoga()
        lazy._pre_configure_yoga()
        assert len(call_count) == 1

    def test_build_fn_returns_multiple_children(self):
        """build_fn can return a list of children."""

        def build():
            return [BaseRenderable(key="a"), BaseRenderable(key="b")]

        lazy = Lazy(build, key="test-lazy")
        lazy._pre_configure_yoga()
        assert len(lazy._children) == 2
        assert lazy._children[0].key == "a"
        assert lazy._children[1].key == "b"

    async def test_lazy_inside_show(self):
        """Lazy inside Show only builds when condition is truthy."""
        build_calls = []
        visible = Signal(False, name="visible")

        def expensive_build():
            build_calls.append(True)
            return Text("Expensive content", width="100%")

        setup = await _strict_render(
            lambda: Box(
                Show(
                    Lazy(expensive_build, key="lazy-content"),
                    when=visible,
                    fallback=Text("Hidden"),
                    key="lazy-show",
                ),
                width="100%",
                height="100%",
            ),
            {"width": 40, "height": 5},
        )

        frame = setup.capture_char_frame()
        assert "Hidden" in frame
        # Lazy build should NOT have been called yet (Show condition is False)
        assert build_calls == []

        # Toggle to visible
        visible.set(True)
        frame = setup.capture_char_frame()
        assert "Expensive content" in frame
        assert build_calls == [True]

        setup.destroy()

    async def test_lazy_inside_switch(self):
        """Lazy inside Switch cases only builds when branch is active."""
        build_calls = {"a": [], "b": []}
        tab = Signal("a", name="tab")

        def build_a():
            build_calls["a"].append(True)
            return Text("Panel A", width="100%")

        def build_b():
            build_calls["b"].append(True)
            return Text("Panel B", width="100%")

        setup = await _strict_render(
            lambda: Box(
                Switch(
                    Match(Lazy(build_a, key="lazy-a"), when=lambda: tab() == "a"),
                    Match(Lazy(build_b, key="lazy-b"), when=lambda: tab() == "b"),
                    key="lazy-switch",
                ),
                width="100%",
                height="100%",
            ),
            {"width": 40, "height": 5},
        )

        frame = setup.capture_char_frame()
        assert "Panel A" in frame
        assert build_calls["a"] == [True]
        assert build_calls["b"] == []  # Not built yet

        tab.set("b")
        frame = setup.capture_char_frame()
        assert "Panel B" in frame
        assert build_calls["b"] == [True]

        setup.destroy()


# ---------------------------------------------------------------------------
# Switch with direct BaseRenderable in cases=
# ---------------------------------------------------------------------------


class TestSwitchDirectNodes:
    def test_cases_with_direct_renderables(self):
        """Switch cases= accepts direct BaseRenderable values."""
        tab = Signal(0, name="tab")
        switch = Switch(
            on=tab,
            cases={
                0: BaseRenderable(key="zero"),
                1: BaseRenderable(key="one"),
            },
            key="test-switch",
        )
        # The internal _cases should be callables (auto-wrapped)
        for k, v in switch._cases.items():
            assert callable(v), f"cases[{k}] should be a callable, got {type(v)}"

    def test_cases_with_direct_renderables_returns_correct_node(self):
        """Auto-wrapped cases return the original node."""
        node_zero = BaseRenderable(key="zero")
        node_one = BaseRenderable(key="one")
        tab = Signal(0, name="tab")
        switch = Switch(
            on=tab,
            cases={
                0: node_zero,
                1: node_one,
            },
            key="test-switch",
        )
        result = switch._cases[0]()
        assert result is node_zero
        result = switch._cases[1]()
        assert result is node_one

    def test_cases_with_list_of_renderables(self):
        """Switch cases= accepts list of BaseRenderable values."""
        node_a = BaseRenderable(key="a")
        node_b = BaseRenderable(key="b")
        tab = Signal(0, name="tab")
        switch = Switch(
            on=tab,
            cases={
                0: [node_a, node_b],
            },
            key="test-switch",
        )
        result = switch._cases[0]()
        assert result == [node_a, node_b]

    def test_cases_mixed_callables_and_nodes(self):
        """Switch cases= accepts mix of callables and direct nodes."""
        node = BaseRenderable(key="direct")
        tab = Signal(0, name="tab")
        switch = Switch(
            on=tab,
            cases={
                0: node,
                1: lambda: BaseRenderable(key="factory"),
            },
            key="test-switch",
        )
        assert switch._cases[0]() is node
        assert switch._cases[1]().key == "factory"

    def test_fallback_with_direct_renderable(self):
        """Switch fallback= accepts a direct BaseRenderable."""
        fb_node = BaseRenderable(key="fallback")
        tab = Signal(99, name="tab")
        switch = Switch(
            on=tab,
            cases={0: BaseRenderable(key="zero")},
            fallback=fb_node,
            key="test-switch",
        )
        assert callable(switch._fallback_fn)
        assert switch._fallback_fn() is fb_node

    async def test_switch_renders_direct_node_cases(self):
        """Integration: Switch with direct nodes renders correctly."""
        tab = Signal(0, name="tab")

        setup = await _strict_render(
            lambda: Box(
                Switch(
                    on=tab,
                    cases={
                        0: Text("Home", width="100%"),
                        1: Text("Settings", width="100%"),
                    },
                    fallback=Text("Unknown", width="100%"),
                    key="direct-switch",
                ),
                width="100%",
                height="100%",
            ),
            {"width": 40, "height": 5},
        )

        frame = setup.capture_char_frame()
        assert "Home" in frame

        tab.set(1)
        frame = setup.capture_char_frame()
        assert "Settings" in frame

        tab.set(99)
        frame = setup.capture_char_frame()
        assert "Unknown" in frame

        setup.destroy()


# ---------------------------------------------------------------------------
# Show with Expr as when=
# ---------------------------------------------------------------------------


class TestShowWithExpr:
    async def test_show_with_signal_comparison(self):
        """Show when= accepts Expr from signal comparison."""
        count = Signal(0, name="count")

        setup = await _strict_render(
            lambda: Box(
                Show(
                    Text("Positive!", width="100%"),
                    when=count > 0,
                    fallback=Text("Zero", width="100%"),
                    key="expr-show",
                ),
                width="100%",
                height="100%",
            ),
            {"width": 40, "height": 5},
        )

        frame = setup.capture_char_frame()
        assert "Zero" in frame

        count.set(5)
        frame = setup.capture_char_frame()
        assert "Positive!" in frame

        count.set(-1)
        frame = setup.capture_char_frame()
        assert "Zero" in frame

        setup.destroy()

    async def test_show_with_chained_expr(self):
        """Show when= works with chained Expr: (a + b) > threshold."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")

        setup = await _strict_render(
            lambda: Box(
                Show(
                    Text("Above 10", width="100%"),
                    when=(a + b) > 10,
                    fallback=Text("Below", width="100%"),
                    key="chain-show",
                ),
                width="100%",
                height="100%",
            ),
            {"width": 40, "height": 5},
        )

        frame = setup.capture_char_frame()
        assert "Below" in frame

        a.set(5)
        b.set(7)
        frame = setup.capture_char_frame()
        assert "Above 10" in frame

        setup.destroy()
