"""Performance benchmarks: full-rebuild vs fine-grained reactive prop update.

Measures the three-tier reactivity migration savings:
  Tier 1: Show/Switch/For self-manage with signal subscriptions
  Tier 2: Text content + generic _bind_reactive_prop for reactive leaf props
  Tier 3: All Renderable props accept reactive sources via _set_or_bind

Usage:
  Standalone:  python benchmarks/bench_reactivity.py
  Pytest:      pytest benchmarks/bench_reactivity.py -v
"""

import asyncio
from collections.abc import Callable

from opentui import test_render as _test_render
from opentui.components.advanced import Code, Markdown
from opentui.components.base import BaseRenderable, Renderable
from opentui.components.box import Box
from opentui.components.control_flow import (
    Dynamic,
    For,
    MemoBlock,
    Mount,
    Show,
    Switch,
    component,
)
from opentui.components.scrollbox import ScrollBox, ScrollContent
from opentui.components.text import Text
from opentui.components.textarea_renderable import TextareaRenderable
from opentui.reconciler import reconcile
from opentui.signals import Signal, _SignalState, _tracking_context, computed

# ── Benchmark harness (delegates to benchmarks.harness) ──────────────

try:
    from benchmarks.harness import bench as _bench_core
    from benchmarks.harness import bench_frame_buckets as _bench_frame_buckets_core
    from benchmarks.harness import format_result as _format_result_core
    from benchmarks.harness import registry as _registry
except ImportError:
    from harness import bench as _bench_core
    from harness import bench_frame_buckets as _bench_frame_buckets_core
    from harness import format_result as _format_result_core
    from harness import registry as _registry

# Backward-compat: _results dict keyed by label, used by standalone runner
_results = _registry._results


def _bench(
    fn: Callable,
    *,
    warmup: int = 50,
    iterations: int = 1000,
    label: str = "",
) -> dict:
    return _bench_core(fn, warmup=warmup, iterations=iterations, label=label).to_dict()


def _format_result(result: dict) -> str:
    return _format_result_core(result)


# Reactivity benchmarks only need these 10 frame buckets
_REACTIVITY_FRAME_BUCKETS = (
    "signal_handling_ns",
    "layout_ns",
    "configure_yoga_ns",
    "compute_yoga_ns",
    "apply_layout_ns",
    "update_layout_hooks_ns",
    "render_tree_ns",
    "flush_ns",
    "post_render_ns",
    "total_ns",
)


def _bench_frame_buckets(
    setup,
    mutate: Callable[[], None],
    *,
    warmup: int = 20,
    iterations: int = 200,
    label_prefix: str,
) -> dict[str, dict]:
    """Benchmark frame timing buckets. Calls setup.destroy() on completion."""
    try:
        results = _bench_frame_buckets_core(
            setup,
            mutate,
            warmup=warmup,
            iterations=iterations,
            label_prefix=label_prefix,
            buckets=_REACTIVITY_FRAME_BUCKETS,
        )
        return {name: results[name].to_dict() for name in results}
    finally:
        setup.destroy()


# ── Helpers ───────────────────────────────────────────────────────────


def _rebuild(root: BaseRenderable, component_fn: Callable, count_sig: Signal | None = None):
    """Simulate a full rebuild: re-run component_fn + reconcile."""
    old_children = list(root._children)
    if count_sig is not None:
        count_sig.set(count_sig.peek() + 1)
    tracked: set[Signal] = set()
    token = _tracking_context.set(tracked)
    try:
        component = component_fn()
    finally:
        _tracking_context.reset(token)
    root._children.clear()
    root._children_tuple = None
    reconcile(root, old_children, [component])


def _init_tree(component_fn: Callable) -> BaseRenderable:
    """Build initial tree from component_fn inside a tracking context."""
    root = BaseRenderable()
    tracked: set[Signal] = set()
    token = _tracking_context.set(tracked)
    try:
        root.add(component_fn())
    finally:
        _tracking_context.reset(token)
    return root


# ── Category 1: Signal notification baseline ─────────────────────────


class TestSignalNotificationBaseline:
    """Raw signal notification cost — the irreducible floor."""

    def test_signal_set_no_subscribers(self):
        sig = Signal(0, name="x")
        sig._subscribers.clear()
        counter = [0]

        def run():
            counter[0] += 1
            sig.set(counter[0])

        r = _bench(run, label="signal.set (0 subs)")
        assert r["median_ns"] < 50_000  # sanity: under 50us

    def test_signal_set_one_subscriber(self):
        sig = Signal(0, name="x")
        sig.subscribe(lambda v: None)
        counter = [0]

        def run():
            counter[0] += 1
            sig.set(counter[0])

        r = _bench(run, label="signal.set (1 sub, noop)")
        assert r["median_ns"] < 50_000

    def test_signal_set_ten_subscribers(self):
        sig = Signal(0, name="x")
        for _ in range(10):
            sig.subscribe(lambda v: None)
        counter = [0]

        def run():
            counter[0] += 1
            sig.set(counter[0])

        r = _bench(run, label="signal.set (10 subs, noop)")
        assert r["median_ns"] < 100_000


# ── Category 2: Reactive prop update (Tier 2/3 fast path) ────────────


class TestReactivePropUpdate:
    """Tier 2/3: reactive prop update — the new fast path."""

    def test_signal_to_renderable_attr(self):
        sig = Signal(0, name="x")
        r = Renderable()
        r._bind_reactive_prop("_z_index", sig)
        counter = [0]

        def update():
            counter[0] += 1
            sig.set(counter[0])

        result = _bench(update, label="reactive prop: Signal -> attr")
        assert result["median_ns"] < 100_000

    def test_computed_to_renderable_attr(self):
        sig = Signal(0, name="x")
        comp = computed(lambda: sig() * 2)
        r = Renderable()
        r._bind_reactive_prop("_z_index", comp)
        counter = [0]

        def update():
            counter[0] += 1
            sig.set(counter[0])

        result = _bench(update, label="reactive prop: Computed -> attr")
        assert result["median_ns"] < 100_000

    def test_text_reactive_content_update(self):
        count = Signal(0, name="count")
        Text(content=count)
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        result = _bench(update, label="reactive prop: Text content")
        assert result["median_ns"] < 100_000

    def test_text_reactive_fg_color(self):
        color_sig = Signal("red", name="color")
        Text("hello", fg=color_sig)
        colors = ["red", "blue", "green", "yellow"]
        counter = [0]

        def update():
            counter[0] += 1
            color_sig.set(colors[counter[0] % len(colors)])

        result = _bench(update, label="reactive prop: Text fg color")
        assert result["median_ns"] < 100_000

    def test_box_reactive_border_style(self):
        toggle = Signal(False, name="t")
        Box(border=True, border_style=lambda: "double" if toggle() else "single")

        result = _bench(toggle.toggle, label="reactive prop: Box border_style toggle")
        assert result["median_ns"] < 100_000

    def test_fan_out_one_signal_five_texts(self):
        count = Signal(0, name="count")
        for i in range(5):
            Text(content=count.map(lambda v, _i=i: f"Text {_i}: {v}"))
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        result = _bench(update, label="reactive prop: 1 signal -> 5 Text nodes")
        assert result["median_ns"] < 500_000


# ── Category 3: Full rebuild cost (OLD model baseline) ────────────────


class TestFullRebuildCost:
    """Full rebuild cost — the old model that reactive props replace."""

    def test_small_tree_rebuild_5_nodes(self):
        count = Signal(0, name="count")

        def component_fn():
            return Box(
                Text(f"Count: {count()}"),
                Text(f"Status: {'positive' if count() > 0 else 'zero'}"),
                border=True,
                padding=1,
            )

        root = _init_tree(component_fn)
        result = _bench(
            lambda: _rebuild(root, component_fn, count),
            label="full rebuild: 5-node tree",
        )
        assert result["median_ns"] < 10_000_000  # under 10ms

    def test_medium_tree_rebuild_30_nodes(self):
        count = Signal(0, name="count")
        active_tab = Signal(0, name="tab")

        def component_fn():
            return Box(
                Box(
                    *[Text(f" Tab {i} ", bold=(active_tab() == i)) for i in range(3)],
                    flex_direction="row",
                ),
                Text("-" * 60),
                Box(
                    Text("Counter Panel", bold=True),
                    Box(Text(f"Value: {count()}"), border=True, padding=1),
                    Text("positive" if count() > 0 else "zero"),
                    padding=1,
                    gap=1,
                ),
                Text("-" * 60),
                Text("Status bar"),
                border=True,
                padding=1,
            )

        root = _init_tree(component_fn)
        result = _bench(
            lambda: _rebuild(root, component_fn, count),
            iterations=500,
            label="full rebuild: ~30-node tree",
        )
        assert result["median_ns"] < 50_000_000  # under 50ms

    def test_large_tree_rebuild_100_items(self):
        entries = Signal(
            [{"id": i, "text": f"Item {i}"} for i in range(100)],
            name="entries",
        )

        def component_fn():
            items = entries()
            return Box(
                Text(f"Total: {len(items)}"),
                *[
                    Box(
                        Text(f"#{item['id']}"),
                        Text(item["text"]),
                        flex_direction="row",
                        key=f"entry-{item['id']}",
                    )
                    for item in items
                ],
                padding=1,
            )

        root = _init_tree(component_fn)
        counter = [0]

        def rebuild():
            counter[0] += 1
            old = entries.peek()
            new = list(old)
            new[-1] = {"id": new[-1]["id"], "text": f"Item {counter[0]}"}
            entries.set(new)
            _rebuild(root, component_fn)

        result = _bench(rebuild, iterations=200, label="full rebuild: 100-item list (~400 nodes)")
        assert result["median_ns"] < 100_000_000  # under 100ms


# ── Category 4: Reconciler patch cost ────────────────────────────────


class TestReconcilerPatchCost:
    """Matched-node reconciliation cost once a rebuild is required."""

    def test_keyed_patch_20_text_nodes(self):
        parent = BaseRenderable()
        old_children = [Text(f"Item {i}", key=f"k{i}") for i in range(20)]
        for child in old_children:
            parent.add(child)
        counter = [0]

        def patch():
            counter[0] += 1
            new_children = [Text(f"Item {i}-{counter[0]}", key=f"k{i}") for i in range(20)]
            reconcile(parent, list(parent._children), new_children)

        result = _bench(patch, iterations=300, label="reconcile patch: 20 keyed Text nodes")
        assert result["median_ns"] < 10_000_000

    def test_keyed_patch_100_text_nodes(self):
        parent = BaseRenderable()
        old_children = [Text(f"Item {i}", key=f"k{i}") for i in range(100)]
        for child in old_children:
            parent.add(child)
        counter = [0]

        def patch():
            counter[0] += 1
            new_children = [Text(f"Item {i}-{counter[0]}", key=f"k{i}") for i in range(100)]
            reconcile(parent, list(parent._children), new_children)

        result = _bench(patch, iterations=100, label="reconcile patch: 100 keyed Text nodes")
        assert result["median_ns"] < 50_000_000


# ── Category 4: Tier 1 — Control flow reactive update ────────────────


class TestControlFlowReactiveUpdate:
    """Tier 1: Show/Switch/For self-managing reactive updates."""

    def test_show_toggle_reactive(self):
        visible = Signal(True, name="vis")
        Show(
            Box(Text("Content"), padding=1),
            when=visible,
            fallback=Text("Hidden"),
        )

        result = _bench(visible.toggle, label="Show reactive toggle")
        assert result["median_ns"] < 1_000_000  # under 1ms

    def test_switch_branch_change_reactive(self):
        tab = Signal(0, name="tab")
        Switch(
            on=tab,
            cases={
                0: lambda: Box(Text("Panel A"), padding=1),
                1: lambda: Box(Text("Panel B"), padding=1),
                2: lambda: Box(Text("Panel C"), padding=1),
            },
        )
        counter = [0]

        def cycle():
            counter[0] += 1
            tab.set(counter[0] % 3)

        result = _bench(cycle, label="Switch reactive branch change")
        assert result["median_ns"] < 1_000_000

    def test_switch_same_branch_noop(self):
        tab = Signal(0, name="tab")
        other = Signal(0, name="other")
        Switch(
            on=lambda: tab() if other() is not None else tab(),
            cases={0: lambda: Text("A"), 1: lambda: Text("B")},
        )
        counter = [0]

        def noop_update():
            counter[0] += 1
            other.set(counter[0])

        result = _bench(noop_update, label="Switch reactive noop (same branch)")
        assert result["median_ns"] < 500_000

    def test_for_reorder_reactive(self):
        items = [{"id": i, "text": f"Item {i}"} for i in range(20)]
        entries = Signal(items, name="entries")
        f = For(
            lambda item: Box(Text(item["text"]), key=f"e-{item['id']}"),
            each=entries,
            key_fn=lambda item: f"e-{item['id']}",
        )
        f._reconcile_children()

        def reorder():
            current = list(entries.peek())
            current.reverse()
            entries.set(current)

        result = _bench(reorder, iterations=200, label="For reactive: reverse 20-item list")
        assert result["median_ns"] < 10_000_000


# ── Category 5: Head-to-head comparison ───────────────────────────────


class TestHeadToHead:
    """Direct comparison: old-style body read vs new-style reactive binding."""

    @staticmethod
    def _counter_old_style():
        count = Signal(0, name="count")

        def component_fn():
            return Box(
                Text(f"Count: {count()}"),
                Text(f"Double: {count() * 2}"),
                padding=1,
                border=True,
            )

        root = _init_tree(component_fn)
        return _bench(
            lambda: _rebuild(root, component_fn, count),
            label="H2H old: counter (full rebuild)",
        )

    @staticmethod
    def _counter_dynamic_region():
        count = Signal(0, name="count")
        root = BaseRenderable()
        root.add(
            Box(
                Dynamic(render=lambda: Text(f"Count: {count()}")),
                Dynamic(render=lambda: Text(f"Double: {count() * 2}")),
                padding=1,
                border=True,
            )
        )
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update, label="H2H mid: counter (dynamic region)")

    @staticmethod
    def _counter_dynamic_cached():
        count = Signal(0, name="count")
        root = BaseRenderable()
        root.add(
            Box(
                Dynamic(
                    cache_key=lambda: "count",
                    render=lambda: Text(content=count.map(lambda v: f"Count: {v}")),
                ),
                Dynamic(
                    cache_key=lambda: "double",
                    render=lambda: Text(content=count.map(lambda v: f"Double: {v * 2}")),
                ),
                padding=1,
                border=True,
            )
        )
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update, label="H2H mid: counter (dynamic cached)")

    @staticmethod
    def _counter_auto_dynamic_children():
        count = Signal(0, name="count")
        root = BaseRenderable()
        root.add(
            Box(
                lambda: Text(f"Count: {count()}"),
                lambda: Text(f"Double: {count() * 2}"),
                padding=1,
                border=True,
            )
        )
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update, label="H2H mid: counter (auto child dynamic)")

    @staticmethod
    def _counter_auto_text_children():
        count = Signal(0, name="count")
        root = BaseRenderable()
        root.add(
            Box(
                lambda: f"Count: {count()}",
                lambda: f"Double: {count() * 2}",
                padding=1,
                border=True,
            )
        )
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update, label="H2H mid: counter (auto child text expr)")

    @staticmethod
    def _counter_auto_boxed_dynamic():
        count = Signal(0, name="count")
        root = BaseRenderable()
        root.add(
            Box(
                lambda: Box(
                    Text(f"Count: {count()}", key="count"),
                    Text(f"Double: {count() * 2}", key="double"),
                    padding=1,
                    border=(count() % 2 == 1),
                    key="panel",
                )
            )
        )
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update, label="H2H mid: counter (auto boxed dynamic)")

    @staticmethod
    def _counter_mounted_template():
        count = Signal(0, name="count")
        root = BaseRenderable()

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

        root.add(Box(Mount(build, update=update), padding=1, border=True))
        counter = [0]

        def update_count():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update_count, label="H2H mid: counter (mounted template)")

    @staticmethod
    def _counter_template_bindings():
        count = Signal(0, name="count")
        root = BaseRenderable()
        root.add(
            Box(
                Mount(
                    lambda: Box(
                        Text(lambda: f"Count: {count()}", id="count_text"),
                        Text(lambda: f"Double: {count() * 2}", id="double_text"),
                        id="panel",
                        padding=1,
                        border=lambda: bool(count() % 2),
                    )
                ),
                padding=1,
                border=True,
            )
        )
        counter = [0]

        def update_count():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update_count, label="H2H mid: counter (mount reactive)")

    @staticmethod
    def _counter_mount_lowering():
        count = Signal(0, name="count")
        root = BaseRenderable()
        root.add(
            Box(
                Mount(
                    lambda: Box(
                        Text(lambda: f"Count: {count()}", id="count_text"),
                        Text(lambda: f"Double: {count() * 2}", id="double_text"),
                        id="panel",
                        padding=1,
                        border=lambda: bool(count() % 2),
                    )
                ),
                padding=1,
                border=True,
            )
        )
        counter = [0]

        def update_count():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update_count, label="H2H mid: counter (mount lowering)")

    @staticmethod
    def _counter_component():
        count = Signal(0, name="count")

        @component
        def CounterPanel():
            return Box(
                Text(lambda: f"Count: {count()}", id="count_text"),
                Text(lambda: f"Double: {count() * 2}", id="double_text"),
                id="panel",
                padding=1,
                border=lambda: bool(count() % 2),
            )

        root = BaseRenderable()
        root.add(Box(CounterPanel(), padding=1, border=True))
        counter = [0]

        def update_count():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update_count, label="H2H mid: counter (template component)")

    @staticmethod
    def _counter_memoblock():
        count = Signal(0, name="count")
        root = BaseRenderable()
        root.add(
            Box(
                MemoBlock(render=lambda: Text(content=count.map(lambda v: f"Count: {v}"))),
                MemoBlock(render=lambda: Text(content=count.map(lambda v: f"Double: {v * 2}"))),
                padding=1,
                border=True,
            )
        )
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update, label="H2H mid: counter (memo block)")

    @staticmethod
    def _counter_new_style():
        count = Signal(0, name="count")
        text1 = Text(content=count.map(lambda v: f"Count: {v}"))
        text2 = Text(content=count.map(lambda v: f"Double: {v * 2}"))
        root = BaseRenderable()
        root.add(Box(text1, text2, padding=1, border=True))
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update, label="H2H new: counter (reactive binding)")

    @staticmethod
    def _tab_switch_old_style():
        active_tab = Signal(0, name="tab")

        def component_fn():
            tab = active_tab()
            panels = [Box(Text(f"Panel {i}"), padding=1) for i in range(3)]
            return Box(
                *[Text(f"Tab {i}", bold=(tab == i)) for i in range(3)],
                panels[tab],
                padding=1,
            )

        root = _init_tree(component_fn)
        counter = [0]

        def update():
            counter[0] += 1
            active_tab.set(counter[0] % 3)
            _rebuild(root, component_fn)

        return _bench(update, iterations=500, label="H2H old: tab switch (full rebuild)")

    @staticmethod
    def _tab_switch_new_style():
        active_tab = Signal(0, name="tab")
        switch = Switch(
            on=active_tab,
            cases={
                0: lambda: Box(Text("Panel 0"), padding=1),
                1: lambda: Box(Text("Panel 1"), padding=1),
                2: lambda: Box(Text("Panel 2"), padding=1),
            },
        )
        tab_bar = Box(
            *[Text(f"Tab {i}", bold=active_tab.map(lambda v, _i=i: v == _i)) for i in range(3)],
            flex_direction="row",
        )
        root = BaseRenderable()
        root.add(Box(tab_bar, switch, padding=1))
        counter = [0]

        def update():
            counter[0] += 1
            active_tab.set(counter[0] % 3)

        return _bench(update, iterations=500, label="H2H new: tab switch (reactive)")

    def test_counter_update_old_style(self):
        r = self._counter_old_style()
        assert r["median_ns"] > 0

    def test_counter_update_dynamic_region(self):
        r = self._counter_dynamic_region()
        assert r["median_ns"] > 0

    def test_counter_update_dynamic_cached(self):
        r = self._counter_dynamic_cached()
        assert r["median_ns"] > 0

    def test_counter_update_auto_dynamic_children(self):
        r = self._counter_auto_dynamic_children()
        assert r["median_ns"] > 0

    def test_counter_update_auto_text_children(self):
        r = self._counter_auto_text_children()
        assert r["median_ns"] > 0

    def test_counter_update_auto_boxed_dynamic(self):
        r = self._counter_auto_boxed_dynamic()
        assert r["median_ns"] > 0

    def test_counter_update_mounted_template(self):
        r = self._counter_mounted_template()
        assert r["median_ns"] > 0

    def test_counter_update_template_bindings(self):
        r = self._counter_template_bindings()
        assert r["median_ns"] > 0

    def test_counter_update_mount_lowering(self):
        r = self._counter_mount_lowering()
        assert r["median_ns"] > 0

    def test_counter_update_component(self):
        r = self._counter_component()
        assert r["median_ns"] > 0

    def test_counter_update_memoblock(self):
        r = self._counter_memoblock()
        assert r["median_ns"] > 0

    def test_counter_update_new_style(self):
        r = self._counter_new_style()
        assert r["median_ns"] > 0

    def test_tab_switch_old_style(self):
        r = self._tab_switch_old_style()
        assert r["median_ns"] > 0

    def test_tab_switch_new_style(self):
        r = self._tab_switch_new_style()
        assert r["median_ns"] > 0


# ── Category 6: Scaling behavior ──────────────────────────────────────


class TestScaling:
    """Verify O(1) reactive updates vs O(n) full rebuilds."""

    @staticmethod
    def _reactive_tree(n: int):
        count = Signal(0, name="count")
        for i in range(n):
            Text(content=count.map(lambda v, _i=i: f"Text {_i}: {v}"))
        return count

    @staticmethod
    def _rebuild_tree(n: int):
        count = Signal(0, name="count")

        def component_fn():
            return Box(*[Text(f"Text {i}: {count()}") for i in range(n)])

        root = _init_tree(component_fn)
        return count, root, component_fn

    @staticmethod
    def _bench_reactive(n: int, iterations: int = 1000):
        count = TestScaling._reactive_tree(n)
        counter = [0]

        def update():
            counter[0] += 1
            count.set(counter[0])

        return _bench(update, iterations=iterations, label=f"scaling reactive: {n} nodes")

    @staticmethod
    def _bench_rebuild(n: int, iterations: int = 500):
        count, root, fn = TestScaling._rebuild_tree(n)
        return _bench(
            lambda: _rebuild(root, fn, count),
            iterations=iterations,
            label=f"scaling rebuild: {n} nodes",
        )

    def test_reactive_update_10_nodes(self):
        r = self._bench_reactive(10)
        assert r["median_ns"] > 0

    def test_reactive_update_100_nodes(self):
        r = self._bench_reactive(100)
        assert r["median_ns"] > 0

    def test_reactive_update_500_nodes(self):
        r = self._bench_reactive(500, iterations=500)
        assert r["median_ns"] > 0

    def test_rebuild_10_nodes(self):
        r = self._bench_rebuild(10)
        assert r["median_ns"] > 0

    def test_rebuild_100_nodes(self):
        r = self._bench_rebuild(100, iterations=200)
        assert r["median_ns"] > 0

    def test_rebuild_500_nodes(self):
        r = self._bench_rebuild(500, iterations=100)
        assert r["median_ns"] > 0

    def test_reactive_scales_sublinearly(self):
        """Reactive updates should scale roughly with subscriber count, not tree size."""
        r10 = self._bench_reactive(10)
        r100 = self._bench_reactive(100)
        ratio = r100["median_ns"] / max(r10["median_ns"], 1)
        assert ratio < 15, f"Reactive scaling ratio {ratio:.1f}x for 10x more nodes — expected <15x"

    def test_rebuild_scales_linearly(self):
        """Full rebuilds should scale roughly linearly with tree size."""
        r10 = self._bench_rebuild(10)
        r100 = self._bench_rebuild(100, iterations=200)
        ratio = r100["median_ns"] / max(r10["median_ns"], 1)
        assert ratio < 30, f"Rebuild scaling ratio {ratio:.1f}x for 10x more nodes — expected <30x"


# ── Category 7: Frame pipeline costs ─────────────────────────────────


class TestFramePipeline:
    """Measure full-frame costs using renderer timing buckets."""

    @staticmethod
    def _component_frame():
        count = Signal(0, name="count")

        @component
        def app():
            return Box(Text(lambda: f"Count: {count()}", id="count_text"))

        setup = asyncio.run(_test_render(app, {"width": 40, "height": 10}))
        counter = [0]

        def mutate():
            counter[0] += 1
            count.set(counter[0])

        return _bench_frame_buckets(
            setup,
            mutate,
            label_prefix="frame template: stable text",
        )

    @staticmethod
    def _control_flow_frame():
        visible = Signal(True, name="visible")

        def app():
            return Box(
                Show(
                    Text("Shown"),
                    when=visible,
                    fallback=Text("Hidden"),
                )
            )

        setup = asyncio.run(_test_render(app, {"width": 40, "height": 10}))

        def mutate():
            visible.toggle()

        return _bench_frame_buckets(
            setup,
            mutate,
            label_prefix="frame reactive: show toggle",
        )

    def test_component_frame_buckets(self):
        results = self._component_frame()
        assert results["total_ns"]["median_ns"] > 0

    def test_control_flow_frame_buckets(self):
        results = self._control_flow_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["signal_handling_ns"]["median_ns"] > 0


# ── Category 8: Workload frame costs ─────────────────────────────────


class TestWorkloadFrames:
    """Frame-level workload benchmarks closer to migrated app shapes."""

    @staticmethod
    def _stable_shell_for_update_frame():
        entries = Signal(
            [{"id": i, "text": f"Message {i}"} for i in range(40)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Text(lambda: f"Total: {len(entries())}", id="count_text"),
                Box(
                    For(
                        lambda item: Text(item["text"], key=f"msg-{item['id']}"),
                        each=entries,
                        key_fn=lambda item: f"msg-{item['id']}",
                    ),
                    border=True,
                    padding=1,
                ),
                gap=1,
                padding=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 60, "height": 20}))
        counter = [0]

        def mutate():
            counter[0] += 1
            current = list(entries.peek())
            current[-1] = {"id": current[-1]["id"], "text": f"Message {counter[0]}"}
            entries.set(current)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=120,
            label_prefix="frame workload: stable shell + For update",
        )

    def test_stable_shell_for_update_frame_buckets(self):
        results = self._stable_shell_for_update_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    @staticmethod
    def _stable_scrollbox_for_append_frame():
        entries = Signal(
            [{"id": i, "text": f"Message {i}"} for i in range(80)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        For(
                            lambda item: Box(
                                Text(item["text"]),
                                margin_top=1,
                                margin_bottom=1,
                                key=f"msg-{item['id']}",
                            ),
                            each=entries,
                            key_fn=lambda item: f"msg-{item['id']}",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 60, "height": 20}))
        counter = [len(entries.peek())]

        def mutate():
            current = list(entries.peek())
            current.append({"id": counter[0], "text": f"Message {counter[0]}"})
            counter[0] += 1
            entries.set(current)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=100,
            label_prefix="frame workload: stable ScrollBox + For append",
        )

    @staticmethod
    def _stable_scrollbox_for_truncate_frame():
        entries = Signal(
            [{"id": i, "text": f"Message {i}"} for i in range(80)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        For(
                            lambda item: Box(
                                Text(item["text"]),
                                margin_top=1,
                                margin_bottom=1,
                                key=f"msg-{item['id']}",
                            ),
                            each=entries,
                            key_fn=lambda item: f"msg-{item['id']}",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 60, "height": 20}))

        def mutate():
            current = list(entries.peek())
            current.pop()
            entries.set(current)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=60,
            label_prefix="frame workload: stable ScrollBox + For truncate",
        )

    @staticmethod
    def _stable_scrollbox_for_prepend_frame():
        entries = Signal(
            [{"id": i, "text": f"Message {i}"} for i in range(80)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        For(
                            lambda item: Box(
                                Text(item["text"]),
                                margin_top=1,
                                margin_bottom=1,
                                key=f"msg-{item['id']}",
                            ),
                            each=entries,
                            key_fn=lambda item: f"msg-{item['id']}",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 60, "height": 20}))
        counter = [len(entries.peek())]

        def mutate():
            current = list(entries.peek())
            current.insert(0, {"id": counter[0], "text": f"Message {counter[0]}"})
            counter[0] += 1
            entries.set(current)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=40,
            label_prefix="frame workload: stable ScrollBox + For prepend",
        )

    @staticmethod
    def _stable_scrollbox_code_append_frame():
        code_block = (
            "def greet(name):\n"
            "    print(f'hello {name}')\n"
            "\n"
            "for idx in range(3):\n"
            "    greet(idx)\n"
            "\n"
            "print('done')\n"
        )
        entries = Signal(
            [{"id": i, "content": code_block} for i in range(24)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        For(
                            lambda item: Box(
                                Code(
                                    item["content"],
                                    filetype="python",
                                    show_line_numbers=True,
                                ),
                                margin_top=1,
                                margin_bottom=1,
                                key=f"code-{item['id']}",
                            ),
                            each=entries,
                            key_fn=lambda item: f"code-{item['id']}",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 80, "height": 30}))
        counter = [len(entries.peek())]

        def mutate():
            current = list(entries.peek())
            current.append({"id": counter[0], "content": code_block})
            counter[0] += 1
            entries.set(current)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=40,
            label_prefix="frame workload: stable ScrollBox + Code append",
        )

    @staticmethod
    def _stable_scrollbox_code_resize_frame():
        code_block = (
            "def greet(name):\n"
            "    print(f'hello {name}')\n"
            "\n"
            "for idx in range(3):\n"
            "    greet(idx)\n"
            "\n"
            "print('done')\n"
        )
        entries = Signal(
            [{"id": i, "content": code_block} for i in range(24)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        For(
                            lambda item: Box(
                                Code(
                                    item["content"],
                                    filetype="python",
                                    show_line_numbers=True,
                                ),
                                margin_top=1,
                                margin_bottom=1,
                                key=f"code-{item['id']}",
                            ),
                            each=entries,
                            key_fn=lambda item: f"code-{item['id']}",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 100, "height": 24}))
        widths = [100, 84, 96, 80, 92, 88]
        index = [0]

        def mutate():
            index[0] = (index[0] + 1) % len(widths)
            setup.resize(widths[index[0]], 24)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=60,
            label_prefix="frame workload: stable ScrollBox + Code resize",
        )

    @staticmethod
    def _stable_scrollbox_markdown_append_frame():
        markdown_block = (
            "# Release Notes\n\n"
            "## Highlights\n"
            "- Faster template updates\n"
            "- Lower fallback rebuild cost\n"
            "- Better scrollbox behavior\n\n"
            "### Details\n"
            "The mounted template path keeps stable structure live while dynamic "
            "regions update through bindings and keyed control-flow nodes.\n"
        )
        entries = Signal(
            [{"id": i, "content": markdown_block} for i in range(40)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        For(
                            lambda item: Box(
                                Markdown(item["content"]),
                                margin_top=1,
                                margin_bottom=1,
                                key=f"md-{item['id']}",
                            ),
                            each=entries,
                            key_fn=lambda item: f"md-{item['id']}",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 90, "height": 24}))
        counter = [len(entries.peek())]

        def mutate():
            current = list(entries.peek())
            current.append({"id": counter[0], "content": markdown_block})
            counter[0] += 1
            entries.set(current)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=40,
            label_prefix="frame workload: stable ScrollBox + Markdown append",
        )

    @staticmethod
    def _stable_scrollbox_markdown_resize_frame():
        markdown_block = (
            "# Resize Notes\n\n"
            "## Context\n"
            "Mounted markdown content should preserve visibility and avoid unnecessary "
            "rebuild work while the viewport width changes.\n\n"
            "### Body\n"
            "This paragraph is intentionally long enough to wrap at narrower widths so "
            "the resize benchmark exercises layout recomputation and redraw cost.\n"
        )
        entries = Signal(
            [{"id": i, "content": markdown_block} for i in range(24)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        For(
                            lambda item: Box(
                                Markdown(item["content"]),
                                margin_top=1,
                                margin_bottom=1,
                                key=f"md-{item['id']}",
                            ),
                            each=entries,
                            key_fn=lambda item: f"md-{item['id']}",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 96, "height": 24}))
        widths = [96, 80, 92, 76, 88, 84]
        index = [0]

        def mutate():
            index[0] = (index[0] + 1) % len(widths)
            setup.resize(widths[index[0]], 24)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=60,
            label_prefix="frame workload: stable ScrollBox + Markdown resize",
        )

    @staticmethod
    def _stable_scrollbox_textarea_resize_frame():
        text_block = (
            "This is a wrapped textarea workload used to measure viewport resize cost.\n"
            "Each textarea contains multiple lines and enough content to reflow when "
            "the width changes.\n"
            "The goal is to isolate layout, native editor rendering, and flush cost.\n"
        )
        entries = Signal(
            [{"id": i, "content": text_block} for i in range(10)],
            name="entries",
        )

        @component
        def app():
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        For(
                            lambda item: Box(
                                TextareaRenderable(
                                    initial_value=item["content"],
                                    wrap_mode="word",
                                    height=4,
                                ),
                                margin_top=1,
                                margin_bottom=1,
                                key=f"ta-{item['id']}",
                            ),
                            each=entries,
                            key_fn=lambda item: f"ta-{item['id']}",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 100, "height": 24}))
        widths = [100, 84, 96, 80, 92, 88]
        index = [0]

        def mutate():
            index[0] = (index[0] + 1) % len(widths)
            setup.resize(widths[index[0]], 24)

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=40,
            label_prefix="frame workload: stable ScrollBox + Textarea resize",
        )

    @staticmethod
    def _stable_scrollbox_textarea_cursor_frame():
        text_block = (
            "Cursor benchmark content for textarea.\n"
            "This line gives the cursor room to move back and forth.\n"
            "The viewport should repaint without needing layout changes.\n"
        )

        textarea_ref: list[TextareaRenderable | None] = [None]

        @component
        def app():
            textarea = TextareaRenderable(
                initial_value=text_block,
                wrap_mode="word",
                height=4,
            )
            textarea_ref[0] = textarea
            return Box(
                Box(Text(lambda: "Header", id="header"), flex_shrink=0),
                ScrollBox(
                    content=ScrollContent(
                        Box(
                            textarea,
                            margin_top=1,
                            margin_bottom=1,
                            key="ta-cursor",
                        )
                    ),
                    sticky_scroll=True,
                    sticky_start="bottom",
                    flex_grow=1,
                ),
                Box(Text(lambda: "Footer", id="footer"), flex_shrink=0),
                flex_direction="column",
                gap=1,
            )

        setup = asyncio.run(_test_render(app, {"width": 100, "height": 24}))
        textarea = textarea_ref[0]
        assert textarea is not None
        textarea.focus()
        direction = [1]

        def mutate():
            if direction[0] > 0:
                moved = textarea.move_cursor_right()
                if not moved:
                    direction[0] = -1
                    textarea.move_cursor_left()
            else:
                moved = textarea.move_cursor_left()
                if not moved:
                    direction[0] = 1
                    textarea.move_cursor_right()

        return _bench_frame_buckets(
            setup,
            mutate,
            iterations=80,
            label_prefix="frame workload: stable ScrollBox + Textarea cursor",
        )

    def test_stable_scrollbox_for_append_frame_buckets(self):
        results = self._stable_scrollbox_for_append_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    def test_stable_scrollbox_for_truncate_frame_buckets(self):
        results = self._stable_scrollbox_for_truncate_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    def test_stable_scrollbox_for_prepend_frame_buckets(self):
        results = self._stable_scrollbox_for_prepend_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    def test_stable_scrollbox_code_append_frame_buckets(self):
        results = self._stable_scrollbox_code_append_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    def test_stable_scrollbox_code_resize_frame_buckets(self):
        results = self._stable_scrollbox_code_resize_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    def test_stable_scrollbox_markdown_append_frame_buckets(self):
        results = self._stable_scrollbox_markdown_append_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    def test_stable_scrollbox_markdown_resize_frame_buckets(self):
        results = self._stable_scrollbox_markdown_resize_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    def test_stable_scrollbox_textarea_resize_frame_buckets(self):
        results = self._stable_scrollbox_textarea_resize_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0

    def test_stable_scrollbox_textarea_cursor_frame_buckets(self):
        results = self._stable_scrollbox_textarea_cursor_frame()
        assert results["total_ns"]["median_ns"] > 0
        assert results["layout_ns"]["median_ns"] > 0
        assert results["render_tree_ns"]["median_ns"] > 0


# ── Category 9: Allocation overhead ──────────────────────────────────


class TestAllocationOverhead:
    """Measure the raw cost of creating renderables (what reactive avoids)."""

    def test_create_box(self):
        r = _bench(lambda: Box(padding=1, border=True), label="alloc: Box()")
        assert r["median_ns"] < 1_000_000

    def test_create_text(self):
        r = _bench(lambda: Text("Hello"), label="alloc: Text('Hello')")
        assert r["median_ns"] < 1_000_000

    def test_create_text_with_reactive(self):
        sig = Signal("Hello", name="x")
        r = _bench(lambda: Text(content=sig), label="alloc: Text(content=signal)")
        assert r["median_ns"] < 1_000_000

    def test_create_5_node_tree(self):
        r = _bench(
            lambda: Box(Text("A"), Text("B"), Text("C"), padding=1),
            label="alloc: Box(3 Texts)",
        )
        assert r["median_ns"] < 5_000_000

    def test_create_for_node(self):
        items = Signal([{"id": i} for i in range(10)], name="items")
        r = _bench(
            lambda: For(
                lambda item: Text(f"Item {item['id']}"),
                each=items,
                key_fn=lambda item: str(item["id"]),
            ),
            iterations=200,
            label="alloc: For(10 items)",
        )
        assert r["median_ns"] < 10_000_000


# ── Standalone runner ─────────────────────────────────────────────────


_CATEGORIES = [
    ("Signal Notification Baseline", TestSignalNotificationBaseline),
    ("Reactive Prop Update (Tier 2/3)", TestReactivePropUpdate),
    ("Full Rebuild Cost (OLD model)", TestFullRebuildCost),
    ("Reconciler Patch Cost", TestReconcilerPatchCost),
    ("Control Flow Reactive (Tier 1)", TestControlFlowReactiveUpdate),
    ("Head-to-Head Comparison", TestHeadToHead),
    ("Scaling Behavior", TestScaling),
    ("Frame Pipeline Costs", TestFramePipeline),
    ("Workload Frame Costs", TestWorkloadFrames),
    ("Allocation Overhead", TestAllocationOverhead),
]


def main():
    """Run all benchmarks and print results."""
    print("=" * 95)
    print("  OpenTUI Python: Fine-Grained Reactivity Performance Benchmarks")
    print("=" * 95)

    all_results: dict[str, dict] = {}

    for cat_name, cls in _CATEGORIES:
        print(f"\n{'─' * 95}")
        print(f"  {cat_name}")
        print(f"{'─' * 95}")

        instance = cls()
        for name in sorted(dir(instance)):
            if not name.startswith("test_"):
                continue
            # Skip meta-tests (scaling assertions) in standalone mode
            if name in ("test_reactive_scales_sublinearly", "test_rebuild_scales_linearly"):
                continue
            _SignalState.get_instance().reset()
            before = set(_results)
            getattr(instance, name)()
            # Collect any new results auto-captured by _bench()
            for label in set(_results) - before:
                print(_format_result(_results[label]))
                all_results[label] = _results[label]

    # Summary: head-to-head ratios
    print(f"\n{'=' * 95}")
    print("  HEAD-TO-HEAD SPEEDUP RATIOS")
    print(f"{'=' * 95}")

    pairs = [
        ("H2H old: counter (full rebuild)", "H2H new: counter (reactive binding)"),
        ("H2H old: tab switch (full rebuild)", "H2H new: tab switch (reactive)"),
    ]
    for old_label, new_label in pairs:
        old = all_results.get(old_label)
        new = all_results.get(new_label)
        if old and new:
            old_med = old.median_ns if hasattr(old, "median_ns") else old["median_ns"]
            new_med = new.median_ns if hasattr(new, "median_ns") else new["median_ns"]
            ratio = old_med / max(new_med, 1)
            print(
                f"  {old_label.split(':')[1].strip():<40s}  "
                f"old={old_med:>10,}ns  "
                f"new={new_med:>10,}ns  "
                f"speedup={ratio:>8.1f}x"
            )

    # Scaling summary
    print(f"\n{'=' * 95}")
    print("  SCALING COMPARISON (reactive vs rebuild)")
    print(f"{'=' * 95}")
    for n in (10, 100, 500):
        r_label = f"scaling reactive: {n} nodes"
        b_label = f"scaling rebuild: {n} nodes"
        r = all_results.get(r_label)
        b = all_results.get(b_label)
        if r and b:
            r_med = r.median_ns if hasattr(r, "median_ns") else r["median_ns"]
            b_med = b.median_ns if hasattr(b, "median_ns") else b["median_ns"]
            ratio = b_med / max(r_med, 1)
            print(
                f"  {n:>4d} nodes:  "
                f"reactive={r_med:>10,}ns  "
                f"rebuild={b_med:>10,}ns  "
                f"speedup={ratio:>8.1f}x"
            )

    print()


if __name__ == "__main__":
    main()
