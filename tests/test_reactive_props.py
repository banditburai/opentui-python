"""Tests for generic reactive prop bindings (_bind_reactive_prop) and _set_or_bind."""

import pytest

from opentui.components.base import BaseRenderable, Renderable
from opentui.components.box import Box
from opentui.components.control_flow import Dynamic, MemoBlock, Portal, component
from opentui.components.text import Text
from opentui import test_render as _test_render
from opentui.components.control_flow import Mount
from opentui.reconciler import reconcile
from opentui._signal_types import _ComputedSignal
from opentui._signals_runtime import _tracking_context
from opentui.signals import Batch, Signal, computed
from opentui.structs import RGBA


def _sub_count(signal: Signal) -> int:
    """Get total binding count (subscribers + prop bindings) for both native and pure-Python."""
    if signal._native is not None:
        return signal._native.total_binding_count
    return len(signal._subscribers)


class TestBindReactiveProp:
    """_bind_reactive_prop unit tests.

    Uses non-layout props (_opacity, _z_index, _border) where possible to avoid
    yoga mark_dirty errors on nodes without custom measure functions.
    Uses Text for layout-prop tests (_content) since Text has a measure func.
    """

    def test_signal_binding_sets_initial_value(self):
        """Signal binding sets the initial value of the attribute."""
        sig = Signal(0.5, name="opacity")
        r = Renderable()
        r._bind_reactive_prop("_opacity", sig)
        assert r._opacity == 0.5

    def test_signal_binding_updates_on_change(self):
        """Signal change updates the bound attribute."""
        sig = Signal(0.5, name="opacity")
        r = Renderable()
        r._bind_reactive_prop("_opacity", sig)
        sig.set(0.8)
        assert r._opacity == 0.8

    def test_signal_binding_marks_dirty(self):
        """Signal change marks the renderable dirty."""
        sig = Signal(1.0, name="opacity")
        r = Renderable()
        r._bind_reactive_prop("_opacity", sig)
        r._dirty = False
        sig.set(0.5)
        assert r._dirty is True

    def test_signal_binding_layout_prop_marks_yoga_dirty(self):
        """Layout prop change on Text (which has measure func) marks yoga dirty."""
        count = Signal(42, name="count")
        text = Text(content=count)
        assert text._content == "42"
        # _content is a layout prop; Text has a measure func so mark_dirty works
        count.set(99)
        assert text._content == "99"

    def test_computed_binding(self):
        """ComputedSignal can be bound as a reactive prop."""
        a = Signal(2, name="a")
        b = Signal(3, name="b")
        total = computed(lambda: a() + b())
        r = Renderable()
        r._bind_reactive_prop("_z_index", total)
        assert r._z_index == 5
        a.set(10)
        assert r._z_index == 13

    def test_callable_binding(self):
        """Callable source is wrapped in ComputedSignal."""
        sig = Signal(5, name="x")
        r = Renderable()
        r._bind_reactive_prop("_z_index", lambda: sig() * 2)
        assert r._z_index == 10
        sig.set(7)
        assert r._z_index == 14

    def test_callable_single_dep_optimization(self):
        """Single-dep callable uses explicit dep (no re-tracking overhead)."""
        sig = Signal(1, name="x")
        r = Renderable()
        r._bind_reactive_prop("_z_index", lambda: sig() + 10)
        # Verify it works
        sig.set(5)
        assert r._z_index == 15

    def test_map_binding(self):
        """Signal.map() result can be bound as reactive prop."""
        count = Signal(5, name="count")
        doubled = count.map(lambda v: v * 2)
        r = Renderable()
        r._bind_reactive_prop("_z_index", doubled)
        assert r._z_index == 10
        count.set(8)
        assert r._z_index == 16

    def test_unbind_stops_updates(self):
        """Unbinding stops reactive updates."""
        sig = Signal(1, name="x")
        r = Renderable()
        r._bind_reactive_prop("_z_index", sig)
        r._unbind_reactive_prop("_z_index")
        sig.set(99)
        assert r._z_index == 1  # Not updated

    def test_cleanup_on_destroy(self):
        """Destroying renderable cleans up bindings."""
        sig = Signal(1, name="x")
        r = Renderable()
        r._bind_reactive_prop("_z_index", sig)
        initial_subs = _sub_count(sig)
        r.destroy()
        assert _sub_count(sig) < initial_subs

    def test_map_dispose_on_cleanup(self):
        """Inline .map() ComputedSignal is disposed when binding is cleaned up."""
        sig = Signal(1, name="x")
        mapped = sig.map(lambda v: v * 2)
        r = Renderable()
        r._bind_reactive_prop("_z_index", mapped)
        initial_subs = _sub_count(sig)
        r._unbind_reactive_prop("_z_index")
        # .map() creates a ComputedSignal that subscribes to sig;
        # dispose should remove that subscription
        assert _sub_count(sig) < initial_subs

    def test_no_tracking_context_pollution(self):
        """Signal read during binding does NOT appear in outer tracking context."""
        from opentui._signals_runtime import _tracking_context

        sig = Signal(1, name="x")
        outer_tracked: set[Signal] = set()
        token = _tracking_context.set(outer_tracked)
        try:
            r = Renderable()
            r._bind_reactive_prop("_z_index", sig)
        finally:
            _tracking_context.reset(token)
        assert sig not in outer_tracked

    def test_plain_value_returns_false(self):
        """Non-reactive value returns False."""
        r = Renderable()
        assert r._bind_reactive_prop("_z_index", 42) is False
        assert r._bind_reactive_prop("_z_index", "hello") is False
        assert r._bind_reactive_prop("_z_index", None) is False

    def test_rebind_replaces_old(self):
        """Binding to A then B -- A no longer triggers."""
        a = Signal(1, name="a")
        b = Signal(100, name="b")
        r = Renderable()
        r._bind_reactive_prop("_z_index", a)
        assert r._z_index == 1
        r._bind_reactive_prop("_z_index", b)
        assert r._z_index == 100
        a.set(999)
        assert r._z_index == 100  # A no longer triggers

    def test_batch_compatibility(self):
        """Batch defers reactive prop updates."""
        sig = Signal(1, name="x")
        r = Renderable()
        r._bind_reactive_prop("_z_index", sig)
        with Batch():
            sig.set(10)
            sig.set(20)
            assert r._z_index == 1  # Deferred
        assert r._z_index == 20  # Final value after batch

    def test_equality_check_skips_noop(self):
        """Same value doesn't mark dirty."""
        sig = Signal(42, name="x")
        r = Renderable()
        r._bind_reactive_prop("_z_index", sig)
        r._dirty = False
        # Force signal to notify even with same value by directly calling
        sig._value = 42
        sig._notify()
        # The equality check in on_change should skip mark_dirty
        assert r._dirty is False


class TestTextReactiveProp:
    """Text integration with _bind_reactive_prop."""

    def test_text_signal_content(self):
        """Text(content=signal) binds and updates reactively."""
        count = Signal(42, name="count")
        text = Text(content=count)
        assert text._content == "42"
        count.set(99)
        assert text._content == "99"

    def test_text_map_content(self):
        """Text(content=signal.map(...)) produces derived content."""
        count = Signal(5, name="count")
        text = Text(content=count.map(lambda v: f"Count: {v}"))
        assert text._content == "Count: 5"
        count.set(10)
        assert text._content == "Count: 10"

    def test_text_callable_content(self):
        """Text(content=lambda: ...) auto-tracks signals."""
        count = Signal(0, name="count")
        text = Text(lambda: f"Count: {count()}")
        assert text._content == "Count: 0"
        count.set(5)
        assert text._content == "Count: 5"

    def test_text_multi_signal_callable(self):
        """Callable with 2+ signals both trigger updates."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        text = Text(lambda: f"{a()} + {b()}")
        assert text._content == "1 + 2"
        a.set(10)
        assert text._content == "10 + 2"
        b.set(20)
        assert text._content == "10 + 20"

    def test_text_callable_retracking(self):
        """Conditional reads re-track on each update."""
        mode = Signal("a", name="mode")
        sig_a = Signal("hello", name="a")
        sig_b = Signal("world", name="b")
        text = Text(lambda: sig_a() if mode() == "a" else sig_b())
        assert text._content == "hello"
        # sig_b not tracked yet
        sig_b.set("WORLD")
        assert text._content == "hello"
        # Switch mode -> re-tracks
        mode.set("b")
        assert text._content == "WORLD"

    def test_text_signal_none_value(self):
        """Signal with None value produces empty string."""
        sig = Signal(None, name="x")
        text = Text(content=sig)
        assert text._content == ""

    def test_text_signal_int_value(self):
        """Signal with int value is stringified."""
        sig = Signal(42, name="x")
        text = Text(content=sig)
        assert text._content == "42"

    def test_text_static_content_unchanged(self):
        """Static string content still works."""
        text = Text("Hello")
        assert text._content == "Hello"
        assert text._prop_bindings is None


class TestReactivePropReconciler:
    """Reconciler integration with reactive prop bindings."""

    def test_reconcile_same_source_preserves_binding(self):
        """Same signal source -> keep old subscription, no re-bind."""
        count = Signal(0, name="count")
        old_text = Text(content=count, key="t")
        parent = BaseRenderable()
        parent._children = [old_text]
        old_text._parent = parent
        initial_subs = _sub_count(count)

        new_text = Text(content=count, key="t")
        reconcile(parent, [old_text], [new_text])

        # Subscriber count should not increase
        assert _sub_count(count) <= initial_subs
        # Old node still reacts
        count.set(42)
        assert old_text._content == "42"

    def test_reconcile_different_source_rebinds(self):
        """Different signal source -> old unbound, new bound."""
        a = Signal(1, name="a")
        b = Signal(100, name="b")
        old_text = Text(content=a, key="t")
        parent = BaseRenderable()
        parent._children = [old_text]
        old_text._parent = parent

        new_text = Text(content=b, key="t")
        reconcile(parent, [old_text], [new_text])

        # Old text now reacts to b, not a
        b.set(200)
        assert old_text._content == "200"
        a.set(999)
        assert old_text._content == "200"  # a no longer triggers

    def test_reconcile_reactive_to_static(self):
        """Reactive -> static: binding cleaned up."""
        sig = Signal(1, name="x")
        old_text = Text(content=sig, key="t")
        parent = BaseRenderable()
        parent._children = [old_text]
        old_text._parent = parent

        new_text = Text("static", key="t")
        reconcile(parent, [old_text], [new_text])

        assert old_text._prop_bindings is None
        sig.set(999)
        assert old_text._content == "static"  # No longer reactive

    def test_reconcile_static_to_reactive(self):
        """Static -> reactive: binding created on old node."""
        sig = Signal(42, name="x")
        old_text = Text("static", key="t")
        parent = BaseRenderable()
        parent._children = [old_text]
        old_text._parent = parent

        new_text = Text(content=sig, key="t")
        reconcile(parent, [old_text], [new_text])

        assert old_text._prop_bindings is not None
        sig.set(100)
        assert old_text._content == "100"

    def test_reconcile_no_accumulating_subscribers(self):
        """Multiple reconciliations don't accumulate subscribers."""
        count = Signal(0, name="count")
        parent = BaseRenderable()
        old_text = Text(content=count, key="t")
        parent._children = [old_text]
        old_text._parent = parent
        initial_subs = _sub_count(count)

        for _ in range(10):
            new_text = Text(content=count, key="t")
            reconcile(parent, list(parent._children), [new_text])

        assert _sub_count(count) <= initial_subs + 1


class TestSetOrBind:
    """_set_or_bind unit tests."""

    def test_static_value_sets_directly(self):
        """Static value is set directly, no binding created."""
        r = Renderable()
        r._set_or_bind("_z_index", 42)
        assert r._z_index == 42
        assert r._prop_bindings is None

    def test_signal_creates_binding(self):
        """Signal source creates a reactive binding."""
        sig = Signal(10, name="z")
        r = Renderable()
        r._set_or_bind("_z_index", sig)
        assert r._z_index == 10
        assert r._prop_bindings is not None
        assert "_z_index" in r._prop_bindings
        sig.set(20)
        assert r._z_index == 20

    def test_callable_creates_binding(self):
        """Callable source creates a reactive binding via ComputedSignal."""
        sig = Signal(5, name="x")
        r = Renderable()
        r._set_or_bind("_z_index", lambda: sig() * 2)
        assert r._z_index == 10
        sig.set(7)
        assert r._z_index == 14

    def test_computed_creates_binding(self):
        """ComputedSignal source creates a reactive binding."""
        a = Signal(2, name="a")
        total = computed(lambda: a() + 100)
        r = Renderable()
        r._set_or_bind("_z_index", total)
        assert r._z_index == 102
        a.set(5)
        assert r._z_index == 105

    def test_transform_applied_to_static(self):
        """Transform is applied to static value."""
        r = Renderable()
        r._set_or_bind("_background_color", "red", transform=Renderable._parse_color)
        assert isinstance(r._background_color, RGBA)

    def test_transform_applied_to_signal(self):
        """Transform is applied via .map() for signal sources."""
        color_sig = Signal("red", name="color")
        r = Renderable()
        r._set_or_bind("_fg", color_sig, transform=Renderable._parse_color)
        assert isinstance(r._fg, RGBA)
        color_sig.set("blue")
        assert isinstance(r._fg, RGBA)

    def test_transform_applied_to_callable(self):
        """Transform wraps callable output."""
        color_sig = Signal("red", name="color")
        r = Renderable()
        r._set_or_bind("_fg", lambda: color_sig(), transform=Renderable._parse_color)
        assert isinstance(r._fg, RGBA)
        color_sig.set("blue")
        assert isinstance(r._fg, RGBA)

    def test_none_value_skips_transform(self):
        """None value skips transform entirely."""
        r = Renderable()
        r._set_or_bind("_fg", None, transform=Renderable._parse_color)
        assert r._fg is None

    def test_transform_not_applied_to_none_from_signal(self):
        """Signal emitting None → _parse_color(None) → None."""
        sig = Signal(None, name="color")
        r = Renderable()
        r._set_or_bind("_fg", sig, transform=Renderable._parse_color)
        # _parse_color(None) returns None
        assert r._fg is None

    def test_string_not_treated_as_callable(self):
        """String values are not treated as callables."""
        r = Renderable()
        r._set_or_bind("_title", "hello")
        assert r._title == "hello"
        assert r._prop_bindings is None

    def test_type_not_treated_as_callable(self):
        """Type objects are not treated as callables."""
        r = Renderable()
        r._set_or_bind("_z_index", int)
        assert r._z_index is int
        assert r._prop_bindings is None


class TestReactiveRenderableProps:
    """Test reactive binding of Renderable constructor props."""

    def test_box_reactive_fg(self):
        """Box(fg=color_signal) updates fg on signal change."""
        color_sig = Signal("red", name="color")
        box = Box(fg=color_sig)
        initial_fg = box._fg
        assert isinstance(initial_fg, RGBA)
        color_sig.set("blue")
        assert box._fg != initial_fg
        assert isinstance(box._fg, RGBA)

    def test_box_reactive_border_color(self):
        """Box(border=True, border_color=sig) updates border color."""
        color_sig = Signal("red", name="bc")
        box = Box(border=True, border_color=color_sig)
        assert isinstance(box._border_color, RGBA)
        color_sig.set("green")
        assert isinstance(box._border_color, RGBA)

    def test_box_reactive_border_style(self):
        """Box(border_style=lambda: ...) toggles border style."""
        toggle = Signal(False, name="t")
        box = Box(border=True, border_style=lambda: "double" if toggle() else "single")
        assert box._border_style == "single"
        toggle.set(True)
        assert box._border_style == "double"

    def test_box_reactive_visible(self):
        """Box(visible=show_signal) toggles visibility."""
        show = Signal(True, name="show")
        box = Box(visible=show)
        assert box._visible is True
        show.set(False)
        assert box._visible is False

    def test_box_reactive_width(self):
        """Box(width=size_signal) updates width."""
        size = Signal(20, name="size")
        box = Box(width=size)
        assert box._width == 20
        size.set(40)
        assert box._width == 40

    def test_box_reactive_padding(self):
        """Box(padding_top=pad_signal) updates padding."""
        pad = Signal(1, name="pad")
        box = Box(padding_top=pad)
        assert box._padding_top == 1
        pad.set(3)
        assert box._padding_top == 3

    def test_box_reactive_opacity(self):
        """Box(opacity=op_signal) clamped to [0, 1]."""
        op = Signal(0.5, name="op")
        box = Box(opacity=op)
        assert box._opacity == 0.5
        op.set(1.5)
        assert box._opacity == 1.0  # Clamped
        op.set(-0.5)
        assert box._opacity == 0.0  # Clamped

    def test_text_reactive_bold(self):
        """Text("x", bold=bold_signal) toggles bold."""
        bold_sig = Signal(False, name="bold")
        text = Text("hello", bold=bold_sig)
        assert text._bold is False
        bold_sig.set(True)
        assert text._bold is True

    def test_text_reactive_fg(self):
        """Text("x", fg=color_signal) updates text color."""
        color_sig = Signal("red", name="color")
        text = Text("hello", fg=color_sig)
        assert isinstance(text._fg, RGBA)
        color_sig.set("blue")
        assert isinstance(text._fg, RGBA)

    def test_box_reactive_z_index(self):
        """Box(z_index=sig) updates z_index."""
        z = Signal(0, name="z")
        box = Box(z_index=z)
        assert box._z_index == 0
        z.set(10)
        assert box._z_index == 10

    def test_box_reactive_flex_grow(self):
        """Box(flex_grow=sig) updates flex_grow."""
        fg = Signal(0, name="fg")
        box = Box(flex_grow=fg)
        assert box._flex_grow == 0
        fg.set(1)
        assert box._flex_grow == 1


class TestRunOnce:
    """Test 'run once' component pattern — no body deps when all reactive."""

    def test_empty_body_deps_when_all_reactive(self):
        """Component with only reactive bindings has no tracked body deps."""
        count = Signal(0, name="count")

        def my_component():
            return Box(
                Text(count.map(lambda v: f"Count: {v}")),
                fg=count.map(lambda v: RGBA(0, v / 100, 0, 1)),
            )

        # Run the component in a tracking context to measure body deps.
        body_deps: set[Signal] = set()
        token = _tracking_context.set(body_deps)
        try:
            my_component()
        finally:
            _tracking_context.reset(token)

        # count should NOT be in body deps because all reads are inside
        # .map() lambdas which run in null tracking contexts
        assert count not in body_deps

    def test_component_fn_called_once(self):
        """Verify signal changes don't re-invoke component_fn when body deps are empty."""
        count = Signal(0, name="count")
        call_count = 0

        def my_component():
            nonlocal call_count
            call_count += 1
            return Box(Text(count.map(lambda v: f"Count: {v}")))

        # Simulate what renderer does: run in tracking context
        body_deps: set[Signal] = set()
        token = _tracking_context.set(body_deps)
        try:
            my_component()
        finally:
            _tracking_context.reset(token)

        assert call_count == 1
        assert not body_deps  # No body-read signals tracked.

        # Signal change should NOT trigger re-call (no body deps)
        count.set(5)
        count.set(10)
        assert call_count == 1  # Still 1 — no rebuild triggered

    def test_reactive_updates_without_rebuild(self):
        """Signal change updates UI without rebuild when using reactive props."""
        count = Signal(0, name="count")
        text = Text(count.map(lambda v: f"Count: {v}"))
        assert text._content == "Count: 0"

        # Update happens via reactive binding, not rebuild
        count.set(42)
        assert text._content == "Count: 42"


class TestDynamic:
    """Mounted dynamic region updates without forcing parent rebuilds."""

    def test_dynamic_keeps_body_deps_empty(self):
        count = Signal(0, name="count")

        def my_component():
            return Box(Dynamic(render=lambda: Text(f"Count: {count()}")))

        body_deps: set[Signal] = set()
        token = _tracking_context.set(body_deps)
        try:
            my_component()
        finally:
            _tracking_context.reset(token)

        assert count not in body_deps

    def test_dynamic_updates_children_in_place(self):
        count = Signal(0, name="count")
        dyn = Dynamic(render=lambda: Text(f"Count: {count()}", key="count"))
        child = dyn._children[0]

        assert isinstance(child, Text)
        assert child._content == "Count: 0"

        count.set(7)

        assert dyn._children[0] is child
        assert child._content == "Count: 7"

    def test_dynamic_cache_key_reuses_branch_children(self):
        branch = Signal(0, name="branch")
        dyn = Dynamic(
            cache_key=lambda: branch(),
            render=lambda: Box(Text(f"Branch {branch()}"), key=f"branch-{branch()}"),
        )

        branch0 = dyn._children[0]
        branch.set(1)
        branch1 = dyn._children[0]
        branch.set(0)

        assert dyn._children[0] is branch0
        assert branch1 is not branch0

    def test_dynamic_same_cache_key_skips_render_fn(self):
        branch = Signal(0, name="branch")
        value = Signal(0, name="value")
        calls = 0

        def render():
            nonlocal calls
            calls += 1
            return Text(value.map(lambda v: f"Value: {v}"), key="value")

        dyn = Dynamic(cache_key=lambda: branch(), render=render)
        child = dyn._children[0]
        assert child._content == "Value: 0"
        assert calls == 1

        value.set(5)

        assert calls == 1
        assert dyn._children[0] is child
        assert child._content == "Value: 5"

    @pytest.mark.asyncio
    async def test_dynamic_updates_without_parent_rebuild_in_renderer(self):
        count = Signal(0, name="count")
        calls = 0

        def app():
            nonlocal calls
            calls += 1
            return Box(Dynamic(render=lambda: Text(f"Count: {count()}")))

        setup = await _test_render(app)
        try:
            assert calls == 1
            assert "Count: 0" in setup.capture_char_frame()

            count.set(42)
            setup.render_frame()

            assert calls == 1
            assert "Count: 42" in setup.capture_char_frame()
        finally:
            setup.renderer.destroy()

    def test_box_callable_child_keeps_body_deps_empty(self):
        count = Signal(0, name="count")

        def my_component():
            return Box(lambda: Text(f"Count: {count()}"))

        body_deps: set[Signal] = set()
        token = _tracking_context.set(body_deps)
        try:
            my_component()
        finally:
            _tracking_context.reset(token)

        assert count not in body_deps

    def test_box_callable_child_updates_in_place(self):
        count = Signal(0, name="count")
        box = Box(lambda: Text(f"Count: {count()}", key="count"))
        region = box._children[0]
        child = region._children[0]

        assert isinstance(child, Text)
        assert child._content == "Count: 0"

        count.set(9)

        assert box._children[0] is region
        assert region._children[0] is child
        assert child._content == "Count: 9"

    def test_box_scalar_callable_child_uses_text_fast_path(self):
        count = Signal(0, name="count")
        box = Box(lambda: f"Count: {count()}")
        region = box._children[0]
        child = region._children[0]

        assert isinstance(child, Text)
        assert child._content == "Count: 0"

        count.set(11)

        assert region._children[0] is child
        assert child._content == "Count: 11"

    @pytest.mark.asyncio
    async def test_box_callable_child_updates_without_parent_rebuild_in_renderer(self):
        count = Signal(0, name="count")
        calls = 0

        def app():
            nonlocal calls
            calls += 1
            return Box(lambda: Text(f"Count: {count()}"))

        setup = await _test_render(app)
        try:
            assert calls == 1
            assert "Count: 0" in setup.capture_char_frame()

            count.set(21)
            setup.render_frame()

            assert calls == 1
            assert "Count: 21" in setup.capture_char_frame()
        finally:
            setup.renderer.destroy()

    @pytest.mark.asyncio
    async def test_box_scalar_callable_child_updates_without_parent_rebuild_in_renderer(self):
        count = Signal(0, name="count")
        calls = 0

        def app():
            nonlocal calls
            calls += 1
            return Box(lambda: f"Count: {count()}")

        setup = await _test_render(app)
        try:
            assert calls == 1
            assert "Count: 0" in setup.capture_char_frame()

            count.set(17)
            setup.render_frame()

            assert calls == 1
            assert "Count: 17" in setup.capture_char_frame()
        finally:
            setup.renderer.destroy()

    def test_box_callable_child_normalizes_list_results(self):
        count = Signal(0, name="count")
        box = Box(lambda: [Text("A", key="a"), f"B{count()}"])
        region = box._children[0]

        assert [type(child).__name__ for child in region._children] == ["Text", "Text"]
        assert region._children[0]._content == "A"
        assert region._children[1]._content == "B0"

        count.set(3)

        assert region._children[0]._content == "A"
        assert region._children[1]._content == "B3"

    def test_box_callable_child_can_switch_between_text_and_nodes(self):
        mode = Signal("text", name="mode")
        count = Signal(0, name="count")
        box = Box(
            lambda: (
                f"Count: {count()}" if mode() == "text" else Text(f"Node: {count()}", key="node")
            )
        )
        region = box._children[0]

        assert len(region._children) == 1
        assert isinstance(region._children[0], Text)
        assert region._children[0]._content == "Count: 0"

        mode.set("node")
        assert len(region._children) == 1
        assert isinstance(region._children[0], Text)
        assert region._children[0]._content == "Node: 0"

        count.set(4)
        assert region._children[0]._content == "Node: 4"

    def test_box_callable_plain_text_node_patches_content_and_style(self):
        count = Signal(0, name="count")
        box = Box(lambda: Text(f"Count: {count()}", bold=(count() % 2 == 1), key="count"))
        region = box._children[0]
        child = region._children[0]

        assert isinstance(child, Text)
        assert child._content == "Count: 0"
        assert child._bold is False

        count.set(1)

        assert region._children[0] is child
        assert child._content == "Count: 1"
        assert child._bold is True

    def test_box_callable_plain_box_node_patches_in_place(self):
        count = Signal(0, name="count")
        box = Box(
            lambda: Box(
                Text(f"Count: {count()}", key="count"),
                border=(count() % 2 == 1),
                padding=1,
                key="panel",
            )
        )
        region = box._children[0]
        panel = region._children[0]
        text = panel._children[0]

        assert isinstance(panel, Box)
        assert isinstance(text, Text)
        assert panel._border is False
        assert text._content == "Count: 0"

        count.set(1)

        assert region._children[0] is panel
        assert panel._children[0] is text
        assert panel._border is True
        assert text._content == "Count: 1"


class TestMemoBlock:
    """Structurally stable mounted region with explicit invalidation."""

    def test_memoblock_skips_rerender_for_leaf_updates(self):
        count = Signal(0, name="count")
        calls = 0

        def render():
            nonlocal calls
            calls += 1
            return Text(content=count.map(lambda v: f"Count: {v}"))

        memo = MemoBlock(render=render)
        child = memo._children[0]

        assert calls == 1
        assert child._content == "Count: 0"

        count.set(5)

        assert calls == 1
        assert memo._children[0] is child
        assert child._content == "Count: 5"

    def test_memoblock_rerenders_when_invalidation_key_changes(self):
        mode = Signal("a", name="mode")
        count = Signal(0, name="count")
        calls = 0

        def render():
            nonlocal calls
            calls += 1
            return Box(
                Text(f"Mode: {mode()}"),
                Text(content=count.map(lambda v: f"Count: {v}")),
                key=f"mode-{mode()}",
            )

        memo = MemoBlock(render=render, invalidate_when=lambda: mode())
        branch_a = memo._children[0]
        assert calls == 1

        count.set(1)
        assert calls == 1
        assert memo._children[0] is branch_a

        mode.set("b")
        branch_b = memo._children[0]
        assert calls == 2
        assert branch_b is not branch_a

        mode.set("a")
        assert calls == 2
        assert memo._children[0] is branch_a


class TestMount:
    """Stable mounted subtree with imperative reactive updates."""

    def test_mounted_template_updates_boxed_subtree_in_place(self):
        count = Signal(0, name="count")

        def build():
            return Box(
                Text("", key="count"),
                Text("", key="double"),
                padding=1,
                border=False,
                key="panel",
            )

        def update(mounted):
            assert isinstance(mounted, Box)
            mounted._children[0].content = f"Count: {count()}"
            mounted._children[1].content = f"Double: {count() * 2}"
            mounted._border = bool(count() % 2)
            mounted.mark_dirty()

        template = Mount(build, update=update)
        panel = template._children[0]
        count_text = panel._children[0]
        double_text = panel._children[1]

        assert panel._border is False
        assert count_text._content == "Count: 0"
        assert double_text._content == "Double: 0"

        count.set(1)

        assert template._children[0] is panel
        assert panel._children[0] is count_text
        assert panel._children[1] is double_text
        assert panel._border is True
        assert count_text._content == "Count: 1"
        assert double_text._content == "Double: 2"

    def test_mounted_template_rebuilds_on_invalidation_key(self):
        mode = Signal("a", name="mode")
        count = Signal(0, name="count")

        def build():
            return Box(Text("", key="count"), key=f"panel-{mode()}")

        def update(mounted):
            assert isinstance(mounted, Box)
            mounted._children[0].content = f"{mode()}:{count()}"
            mounted.mark_dirty()

        template = Mount(build, update=update, invalidate_when=lambda: mode())
        panel_a = template._children[0]

        count.set(1)
        assert template._children[0] is panel_a
        assert panel_a._children[0]._content == "a:1"

        mode.set("b")
        panel_b = template._children[0]
        assert panel_b is not panel_a
        assert panel_b._children[0]._content == "b:1"

    def test_mounted_template_update_receives_cached_refs(self):
        count = Signal(0, name="count")

        def build():
            return Box(
                Text("", id="count_text"),
                Text("", id="double_text"),
                id="panel",
            )

        def update(mounted, refs):
            panel = refs["panel"]
            count_text = refs["count_text"]
            double_text = refs["double_text"]
            assert mounted is panel
            count_text.content = f"Count: {count()}"
            double_text.content = f"Double: {count() * 2}"
            panel.mark_dirty()

        template = Mount(build, update=update)
        panel = template._children[0]
        count_text = panel.find_descendant_by_id("count_text")
        double_text = panel.find_descendant_by_id("double_text")

        assert count_text is not None
        assert double_text is not None
        assert count_text._content == "Count: 0"
        assert double_text._content == "Double: 0"

        count.set(2)

        assert panel.find_descendant_by_id("count_text") is count_text
        assert panel.find_descendant_by_id("double_text") is double_text
        assert count_text._content == "Count: 2"
        assert double_text._content == "Double: 4"

    def test_mounted_template_refs_include_portal_content(self):
        root = Renderable(key="root", width=80, height=24)
        count = Signal(0, name="count")

        def build():
            return Portal(
                Text("", id="portal-text"),
                mount=root,
                key="portal",
            )

        def update(mounted, refs):
            portal_text = refs["portal-text"]
            assert isinstance(mounted, Portal)
            portal_text.content = f"Count: {count()}"

        mounted = Mount(build, update=update)
        root.add(mounted)
        mounted._configure_yoga_properties()

        container = next(
            child
            for child in root._children
            if getattr(child, "key", None) == "portal-container-portal"
        )
        portal_text = container._children[0]
        assert portal_text._content == "Count: 0"

        count.set(3)

        assert container._children[0] is portal_text
        assert portal_text._content == "Count: 3"


class TestTemplate:
    """Mount with inline reactive props (replaces old Template declarative bindings)."""

    def test_mount_updates_boxed_subtree_in_place(self):
        count = Signal(0, name="count")
        mt = Mount(
            lambda: Box(
                Text(lambda: f"Count: {count()}", id="count_text"),
                Text(lambda: f"Double: {count() * 2}", id="double_text"),
                id="panel",
                padding=1,
                border=lambda: bool(count() % 2),
            )
        )

        panel = mt._children[0]
        count_text = panel.find_descendant_by_id("count_text")
        double_text = panel.find_descendant_by_id("double_text")

        assert count_text is not None
        assert double_text is not None
        assert panel._border is False
        assert count_text._content == "Count: 0"
        assert double_text._content == "Double: 0"

        count.set(1)

        assert mt._children[0] is panel
        assert panel.find_descendant_by_id("count_text") is count_text
        assert panel.find_descendant_by_id("double_text") is double_text
        assert panel._border is True
        assert count_text._content == "Count: 1"
        assert double_text._content == "Double: 2"

    def test_mount_invalidates_structure_when_requested(self):
        mode = Signal("a", name="mode")
        count = Signal(0, name="count")
        mt = Mount(
            lambda: Box(
                Text(lambda: f"{mode()}:{count()}", id="value"),
                id=f"panel-{mode()}",
            ),
            invalidate_when=lambda: mode(),
        )

        panel_a = mt._children[0]
        value_a = panel_a.find_descendant_by_id("value")
        assert value_a is not None
        assert value_a._content == "a:0"

        count.set(1)
        assert mt._children[0] is panel_a
        assert value_a._content == "a:1"

        mode.set("b")
        panel_b = mt._children[0]
        value_b = panel_b.find_descendant_by_id("value")
        assert value_b is not None
        assert panel_b is not panel_a
        assert value_b._content == "b:1"


class TestMountReactiveProps:
    """Mount-based reactive prop binding tests."""

    def test_mount_lowers_bound_tree(self):
        count = Signal(0, name="count")
        lowered = Mount(
            lambda: Box(
                Text(lambda: f"Count: {count()}", id="count_text"),
                Text(lambda: f"Double: {count() * 2}", id="double_text"),
                id="panel",
                border=lambda: bool(count() % 2),
            )
        )

        panel = lowered._children[0]
        count_text = panel.find_descendant_by_id("count_text")
        double_text = panel.find_descendant_by_id("double_text")

        assert count_text is not None
        assert double_text is not None
        assert panel._border is False
        assert count_text._content == "Count: 0"
        assert double_text._content == "Double: 0"

        count.set(1)

        assert lowered._children[0] is panel
        assert count_text._content == "Count: 1"
        assert double_text._content == "Double: 2"
        assert panel._border is True

    def test_mount_updates_bindings_inside_portal(self):
        root = Renderable(key="root", width=80, height=24)
        count = Signal(0, name="count")

        lowered = Mount(
            lambda: Portal(
                Text(lambda: f"Count: {count()}", id="portal-text"),
                mount=root,
                key="portal",
            )
        )
        root.add(lowered)
        lowered._configure_yoga_properties()

        container = next(
            child
            for child in root._children
            if getattr(child, "key", None) == "portal-container-portal"
        )
        portal_text = container._children[0]
        assert portal_text._content == "Count: 0"

        count.set(5)

        assert container._children[0] is portal_text
        assert portal_text._content == "Count: 5"

    def test_mount_respects_invalidation(self):
        mode = Signal("a", name="mode")
        count = Signal(0, name="count")
        lowered = Mount(
            lambda: Box(
                Text(lambda: f"{mode()}:{count()}", id="value"),
                id=f"panel-{mode()}",
            ),
            invalidate_when=lambda: mode(),
        )

        panel_a = lowered._children[0]
        value_a = panel_a.find_descendant_by_id("value")
        assert value_a is not None
        assert value_a._content == "a:0"

        count.set(1)
        assert lowered._children[0] is panel_a
        assert value_a._content == "a:1"

        mode.set("b")
        panel_b = lowered._children[0]
        value_b = panel_b.find_descendant_by_id("value")
        assert value_b is not None
        assert panel_b is not panel_a
        assert value_b._content == "b:1"

    def test_mount_supports_named_binding_functions(self):
        count = Signal(0, name="count")

        def count_text() -> str:
            return f"Count: {count()}"

        def double_text() -> str:
            return f"Double: {count() * 2}"

        def panel_border() -> bool:
            return bool(count() % 2)

        def build_panel():
            return Box(
                Text(count_text, id="count_text"),
                Text(double_text, id="double_text"),
                id="panel",
                border=panel_border,
            )

        lowered = Mount(build_panel)
        panel = lowered._children[0]
        count_node = panel.find_descendant_by_id("count_text")
        double_node = panel.find_descendant_by_id("double_text")

        assert count_node is not None
        assert double_node is not None
        assert count_node._content == "Count: 0"
        assert double_node._content == "Double: 0"
        assert panel._border is False

        count.set(3)

        assert count_node._content == "Count: 3"
        assert double_node._content == "Double: 6"
        assert panel._border is True

    @pytest.mark.asyncio
    async def test_mount_renders_with_bindings(self):
        count = Signal(0, name="count")
        calls = 0

        def app():
            nonlocal calls
            calls += 1
            return Mount(
                lambda: Box(
                    Text(lambda: f"Count: {count()}", id="count_text"),
                    id="panel",
                )
            )

        setup = await _test_render(app)
        try:
            assert calls == 1
            assert "Count: 0" in setup.capture_char_frame()

            count.set(7)
            setup.render_frame()

            assert calls == 1
            assert "Count: 7" in setup.capture_char_frame()
        finally:
            setup.renderer.destroy()


class TestTemplateComponent:
    """Component-level migration path onto mounted-template execution."""

    def test_component_updates_in_place(self):
        count = Signal(0, name="count")

        @component
        def CounterPanel():
            return Box(
                Text(lambda: f"Count: {count()}", id="count_text"),
                Text(lambda: f"Double: {count() * 2}", id="double_text"),
                id="panel",
                border=lambda: bool(count() % 2),
            )

        panel_component = CounterPanel()
        panel = panel_component._children[0]
        count_text = panel.find_descendant_by_id("count_text")
        double_text = panel.find_descendant_by_id("double_text")

        assert count_text is not None
        assert double_text is not None
        assert panel._border is False
        assert count_text._content == "Count: 0"
        assert double_text._content == "Double: 0"

        count.set(1)

        assert panel_component._children[0] is panel
        assert count_text._content == "Count: 1"
        assert double_text._content == "Double: 2"
        assert panel._border is True

    def test_component_invalidates_when_requested(self):
        mode = Signal("a", name="mode")
        count = Signal(0, name="count")

        @component(invalidate_when=lambda current_mode: current_mode())
        def ModePanel(current_mode):
            return Box(
                Text(lambda: f"{current_mode()}:{count()}", id="value"),
                id=f"panel-{current_mode()}",
            )

        panel_component = ModePanel(mode)
        panel_a = panel_component._children[0]
        value_a = panel_a.find_descendant_by_id("value")
        assert value_a is not None
        assert value_a._content == "a:0"

        count.set(1)
        assert panel_component._children[0] is panel_a
        assert value_a._content == "a:1"

        mode.set("b")
        panel_b = panel_component._children[0]
        value_b = panel_b.find_descendant_by_id("value")
        assert value_b is not None
        assert panel_b is not panel_a
        assert value_b._content == "b:1"

    @pytest.mark.asyncio
    async def test_component_skips_parent_rebuild_in_renderer(self):
        count = Signal(0, name="count")
        calls = 0

        @component
        def CounterPanel():
            nonlocal calls
            calls += 1
            return Box(
                Text(lambda: f"Count: {count()}", id="count_text"),
                id="panel",
            )

        setup = await _test_render(CounterPanel)
        try:
            assert calls == 1
            assert "Count: 0" in setup.capture_char_frame()

            count.set(9)
            setup.render_frame()

            assert calls == 1
            assert "Count: 9" in setup.capture_char_frame()
        finally:
            setup.renderer.destroy()


# ---------------------------------------------------------------------------
# visible + _live_count interaction tests
# ---------------------------------------------------------------------------


class TestVisibleLiveCount:
    """Test that toggling visible propagates _live_count correctly."""

    def test_reactive_visible_propagates_live_count(self):
        """Reactive visible signal propagates _live_count to parent."""
        vis = Signal(True, name="v")
        parent = Box()
        child = Box(visible=vis)
        parent.add(child)
        # Set live after parenting so _propagate_live_count reaches parent
        child.live = True

        # Initial state: live=True, visible=True → _live_count=1, propagated to parent
        assert child._live_count == 1
        assert parent._live_count == 1

        # Toggle off: visible=False → _live_count should drop
        vis.set(False)
        assert child._visible is False
        assert child._live_count == 0
        assert parent._live_count == 0

        # Toggle back on
        vis.set(True)
        assert child._visible is True
        assert child._live_count == 1
        assert parent._live_count == 1

    def test_imperative_visible_propagates_live_count(self):
        """Setting visible via property setter propagates _live_count."""
        parent = Box()
        child = Box()
        parent.add(child)
        child.live = True

        assert parent._live_count == 1

        child.visible = False
        assert parent._live_count == 0

        child.visible = True
        assert parent._live_count == 1

    def test_visible_toggle_no_live_no_propagation(self):
        """When live=False, toggling visible does NOT change _live_count."""
        vis = Signal(True, name="v")
        parent = Box()
        child = Box(visible=vis)
        parent.add(child)

        assert child._live_count == 0
        assert parent._live_count == 0

        vis.set(False)
        assert child._live_count == 0
        assert parent._live_count == 0

    def test_visible_setter_idempotent(self):
        """Setting visible to its current value is a no-op."""
        parent = Box()
        child = Box()
        parent.add(child)
        child.live = True

        assert parent._live_count == 1

        # No-op: already True
        child.visible = True
        assert parent._live_count == 1
