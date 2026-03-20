"""Tests for structural control flow primitives — For, Show, Switch.

Tests ported: 26/26 from upstream control-flow.test.tsx
(Index tests are not applicable — Python has no Index component.
ErrorBoundary tests are in tests/solid/test_error_boundary.py.
Three upstream tests that rely on render-level infrastructure are
mapped to unit-level equivalents below.)
"""

from opentui import reactive, template_component
from opentui.components.base import BaseRenderable, Renderable
from opentui.components.control_flow import For, Match, Show, Switch
from opentui.reconciler import reconcile

# Imports for render-output tests
from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.text import Text
from opentui.signals import Signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sub_count(signal: Signal) -> int:
    """Get total binding count (subscribers + prop bindings) for both native and pure-Python."""
    if signal._native is not None:
        return signal._native.total_binding_count
    return len(signal._subscribers)



def _make_item(id: int, label: str = ""):
    return {"id": id, "label": label or f"item-{id}"}


def _render_item(item):
    """Render function for For tests — returns a BaseRenderable with key."""
    return BaseRenderable(key=f"item-{item['id']}")


# ---------------------------------------------------------------------------
# For tests
# ---------------------------------------------------------------------------


class TestFor:
    def test_initial_build(self):
        """First _reconcile_children() builds correct children."""
        items = [_make_item(1), _make_item(2), _make_item(3)]
        f = For(each=items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list")
        f._reconcile_children()

        assert len(f._children) == 3
        assert f._children[0].key == "item-1"
        assert f._children[1].key == "item-2"
        assert f._children[2].key == "item-3"

    def test_same_keys_skips(self):
        """Same items in same order → no-op (fast path)."""
        items = [_make_item(1), _make_item(2)]
        f = For(each=items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list")
        f._reconcile_children()

        child_0 = f._children[0]
        child_1 = f._children[1]

        # Reconcile again with same items
        f._reconcile_children()

        assert f._children[0] is child_0
        assert f._children[1] is child_1

    def test_new_item_added(self):
        """Only the new item gets rendered; existing preserved."""
        items = [_make_item(1), _make_item(2)]
        f = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list"
        )
        f._reconcile_children()

        old_child_0 = f._children[0]
        old_child_1 = f._children[1]

        # Add item 3
        items.append(_make_item(3))
        f._reconcile_children()

        assert len(f._children) == 3
        assert f._children[0] is old_child_0  # preserved
        assert f._children[1] is old_child_1  # preserved
        assert f._children[2].key == "item-3"  # new

    def test_append_only_skips_rerender_for_unchanged_prefix_items(self):
        """Append-only updates should not re-render unchanged existing items."""
        items = [_make_item(1), _make_item(2)]
        render_calls: list[int] = []

        def render_item(item):
            render_calls.append(item["id"])
            return BaseRenderable(key=f"item-{item['id']}")

        f = For(
            each=lambda: items,
            render=render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()
        render_calls.clear()

        items.append(_make_item(3))
        f._reconcile_children()

        assert render_calls == [3]

    def test_item_removed(self):
        """Removed item is destroyed; others preserved."""
        items = [_make_item(1), _make_item(2), _make_item(3)]
        f = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list"
        )
        f._reconcile_children()

        child_1 = f._children[0]
        child_3 = f._children[2]

        destroyed = []
        f._children[1].on_cleanup(lambda: destroyed.append("item-2"))

        # Remove item 2
        items.pop(1)
        f._reconcile_children()

        assert len(f._children) == 2
        assert f._children[0] is child_1  # preserved
        assert f._children[1] is child_3  # preserved
        assert "item-2" in destroyed

    def test_truncate_only_skips_rerender_for_unchanged_prefix_items(self):
        """Tail removal should preserve and avoid rerendering the shared prefix."""
        items = [_make_item(1), _make_item(2), _make_item(3)]
        render_calls: list[int] = []

        def render_item(item):
            render_calls.append(item["id"])
            node = BaseRenderable(key=f"item-{item['id']}")
            return node

        f = For(
            each=lambda: items,
            render=render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()

        destroyed: list[str] = []
        f._children[2].on_cleanup(lambda: destroyed.append("item-3"))
        render_calls.clear()

        items.pop()
        prefix_0 = f._children[0]
        prefix_1 = f._children[1]
        f._reconcile_children()

        assert render_calls == []
        assert len(f._children) == 2
        assert f._children[0] is prefix_0
        assert f._children[1] is prefix_1
        assert "item-3" in destroyed

    def test_reorder(self):
        """Reorder reuses existing children in new order."""
        items = [_make_item(1), _make_item(2), _make_item(3)]
        f = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list"
        )
        f._reconcile_children()

        child_1 = f._children[0]
        child_2 = f._children[1]
        child_3 = f._children[2]

        # Reverse order
        items.reverse()
        f._reconcile_children()

        assert f._children[0] is child_3
        assert f._children[1] is child_2
        assert f._children[2] is child_1

    def test_empty_to_items(self):
        """Starts empty, items added."""
        items = []
        f = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list"
        )
        f._reconcile_children()
        assert len(f._children) == 0

        items.extend([_make_item(1), _make_item(2)])
        f._reconcile_children()
        assert len(f._children) == 2

    def test_items_to_empty(self):
        """All items removed."""
        items = [_make_item(1), _make_item(2)]
        f = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list"
        )
        f._reconcile_children()
        assert len(f._children) == 2

        destroyed = []
        for c in f._children:
            c.on_cleanup(lambda k=c.key: destroyed.append(k))

        items.clear()
        f._reconcile_children()
        assert len(f._children) == 0
        assert "item-1" in destroyed
        assert "item-2" in destroyed

    def test_in_reconciler_matched(self):
        """Reconciler delegates to For._reconcile_children() for matched For nodes."""
        parent = BaseRenderable()
        items = [_make_item(1)]
        old_for = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="for"
        )
        old_for._reconcile_children()
        parent._children = [old_for]
        old_for._parent = parent

        old_child = old_for._children[0]

        # Add item 2
        items.append(_make_item(2))

        # Template For (what component function would return)
        new_for = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="for"
        )

        reconcile(parent, [old_for], [new_for])

        # Old For preserved
        assert parent._children[0] is old_for
        # Children reconciled by For
        assert len(old_for._children) == 2
        assert old_for._children[0] is old_child  # preserved
        assert old_for._children[1].key == "item-2"  # new

    def test_in_reconciler_new(self):
        """First mount: reconciler calls For._reconcile_children() for new For nodes."""
        parent = BaseRenderable()
        items = [_make_item(1), _make_item(2)]
        new_for = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="for"
        )

        reconcile(parent, [], [new_for])

        assert parent._children[0] is new_for
        # Children should have been built
        assert len(new_for._children) == 2

    def test_nested_for_has_children_on_insert(self):
        """Reconciler initializes For nodes nested inside new subtrees.

        Regression test: when a For is deeply nested (e.g. Box -> ScrollBox
        -> For), and the entire parent subtree is inserted as new by the
        reconciler, _init_nested_fors recursively finds the For and calls
        _reconcile_children().  Without this, the For would have empty
        _children until the next signal change triggers another rebuild.
        """
        parent = BaseRenderable()
        items = [_make_item(1), _make_item(2)]

        # Simulate the dashboard pattern: For inside Box (like ScrollBox inside content_row)
        inner_for = For(
            each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="for"
        )
        wrapper = Renderable(key="wrapper")
        wrapper.add(inner_for)

        # Old tree has a different child (like empty-text placeholder)
        old_child = Renderable(key="old")
        parent._children = [old_child]
        old_child._parent = parent

        # Reconciler inserts wrapper as new (type mismatch with old_child)
        reconcile(parent, [old_child], [wrapper])

        # wrapper is inserted as-is (new node, not a For)
        assert parent._children[0] is wrapper
        # The nested For should have children — initialized by _init_nested_fors
        nested_for = wrapper._children[0]
        assert isinstance(nested_for, For)
        assert len(nested_for._children) == 2
        assert nested_for._children[0].key == "item-1"
        assert nested_for._children[1].key == "item-2"

    def test_yoga_height_auto_after_layout_feedback(self):
        """For always auto-sizes height from children, never locks to stale value.

        Regression test: _apply_yoga_layout writes computed height into
        self._height.  On non-rebuild frames, _configure_yoga_node would set
        that as an explicit node.height on the yoga node.  When the For
        later gains children, configure_node(height=None) merely *skips*
        setting height, so the stale 0 persists and all entries collapse.

        Simulates the real hierarchy: parent(height=50) -> For(flex_shrink=0).
        Uses children with explicit height=4 (like real log entries).
        """
        from opentui import layout as yoga_layout

        def _apply_layouts(root):
            """Apply yoga layout recursively."""
            root._apply_yoga_layout()
            for c in root._children:
                _apply_layouts(c)

        def _render_sized_item(item):
            """Render function that creates children with explicit height."""
            return Renderable(key=f"item-{item['id']}", height=4)

        items = []
        parent = Renderable(key="parent", height=50)
        f = For(
            each=lambda: items,
            render=_render_sized_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
            flex_shrink=0,
        )
        parent.add(f)

        # Frame 1: empty For, layout computes height=0
        parent._configure_yoga_properties()
        yoga_layout.compute_layout(parent._yoga_node, 100, 50)
        _apply_layouts(parent)
        assert f._layout_height == 0  # No children -> 0 computed height
        assert f._height is None  # Original prop unchanged

        # Frame 2 (no signal change, no rebuild): _configure_yoga_node runs
        # with self._height=None (original prop, never overwritten by layout).
        # This keeps the yoga node in auto-height mode.
        parent._configure_yoga_properties()
        yoga_layout.compute_layout(parent._yoga_node, 100, 50)
        _apply_layouts(parent)
        assert f._layout_height == 0  # Still 0 computed
        assert f._height is None  # Prop still untouched

        # Frame 3 (signal change -> rebuild):
        # _patch_node resets _height=None, _reconcile_children adds items.
        items.extend([_make_item(1), _make_item(2)])
        f._height = None  # simulates _patch_node reset
        f._reconcile_children()

        parent._configure_yoga_properties()
        yoga_layout.compute_layout(parent._yoga_node, 100, 50)
        _apply_layouts(parent)

        # With the _layout_width/_layout_height separation, the feedback loop
        # is broken: _width/_height (props) are never overwritten by layout,
        # so _configure_yoga_node always reads the original values.
        assert f._layout_height == 8, (
            f"For layout height should be 8 (2 items * 4), got {f._layout_height}"
        )

    def test_for_reorder_with_nested_show(self):
        """For correctly orders children after array reversal with nested Show.

        Upstream: "REPRODUCE BUG: For component has incorrect ordering after
        array reordering" — creates items with optional description (Show),
        sets ordered list, then reverses it, verifying the child order
        matches the reversed source order.
        """
        items: list[dict] = []

        def render_option(item):
            """Render an option box with an optional Show for description."""
            box = Renderable(key=f"option-{item['id']}")
            if item.get("description"):
                show = Show(
                    when=lambda desc=item["description"]: desc,
                    render=lambda: Renderable(key="desc"),
                    key="show-desc",
                )
                box.add(show)
            return box

        f = For(
            each=lambda: items,
            render=render_option,
            key_fn=lambda e: f"option-{e['id']}",
            key="container",
        )
        f._reconcile_children()
        assert len(f._children) == 0

        # Set initial ordered items
        ordered = [
            {"id": "order-1", "display": "First"},
            {"id": "order-2", "display": "Second"},
            {"id": "order-3", "display": "Third"},
            {"id": "order-4", "display": "Fourth"},
            {"id": "order-5", "display": "Fifth"},
        ]
        items.extend(ordered)
        f._reconcile_children()

        assert len(f._children) == 5
        assert f._children[0].key == "option-order-1"
        assert f._children[1].key == "option-order-2"
        assert f._children[2].key == "option-order-3"
        assert f._children[3].key == "option-order-4"
        assert f._children[4].key == "option-order-5"

        # Reverse the array — this exposed a bug in the upstream TS version
        items.clear()
        items.extend(reversed(ordered))
        f._reconcile_children()

        assert len(f._children) == 5
        assert f._children[0].key == "option-order-5"
        assert f._children[1].key == "option-order-4"
        assert f._children[2].key == "option-order-3"
        assert f._children[3].key == "option-order-2"
        assert f._children[4].key == "option-order-1"


# ---------------------------------------------------------------------------
# Show tests
# ---------------------------------------------------------------------------


class TestShow:
    def test_truthy_renders_children(self):
        """Condition truthy → render() called, children present."""
        show = Show(
            when=lambda: True,
            render=lambda: Renderable(key="content"),
            key="show",
        )
        assert len(show._children) == 1
        assert show._children[0].key == "content"
        assert show._is_active is True

    def test_falsy_renders_fallback(self):
        """Condition falsy → fallback() called."""
        show = Show(
            when=lambda: False,
            render=lambda: Renderable(key="content"),
            fallback=lambda: Renderable(key="fallback"),
            key="show",
        )
        assert len(show._children) == 1
        assert show._children[0].key == "fallback"
        assert show._is_active is True

    def test_falsy_no_fallback_empty(self):
        """Falsy, no fallback → empty children, inactive."""
        show = Show(
            when=lambda: False,
            render=lambda: Renderable(key="content"),
            key="show",
        )
        assert len(show._children) == 0
        assert show._is_active is False

    def test_render_returns_list(self):
        """render() can return a list of children."""
        show = Show(
            when=lambda: True,
            render=lambda: [Renderable(key="a"), Renderable(key="b")],
            key="show",
        )
        assert len(show._children) == 2
        assert show._children[0].key == "a"
        assert show._children[1].key == "b"

    def test_show_inside_for(self):
        """Show can be a child of a For item."""
        items = [_make_item(1)]

        def render_with_show(item):
            box = Renderable(key=f"item-{item['id']}")
            show = Show(
                when=lambda: True,
                render=lambda: Renderable(key="detail"),
                key="show",
            )
            box.add(show)
            return box

        f = For(each=items, render=render_with_show, key_fn=lambda e: f"item-{e['id']}", key="list")
        f._reconcile_children()

        assert len(f._children) == 1
        item_node = f._children[0]
        assert len(item_node._children) == 1
        show_node = item_node._children[0]
        assert isinstance(show_node, Show)
        assert len(show_node._children) == 1

    def test_for_inside_show(self):
        """For can be wrapped in a Show."""
        items = [_make_item(1), _make_item(2)]
        show = Show(
            when=lambda: True,
            render=lambda: For(
                each=items,
                render=_render_item,
                key_fn=lambda e: f"item-{e['id']}",
                key="list",
            ),
            key="show",
        )
        assert len(show._children) == 1
        assert isinstance(show._children[0], For)

    def test_show_ordering_in_parent(self):
        """Show inserts children in correct order relative to siblings.

        Upstream: "should conditionally render content with <Show> in the
        correct order" — verifies that when a Show condition becomes true,
        its rendered child appears between its preceding and following
        siblings (first, second, third ordering).
        """
        parent = Renderable(key="container")
        first = Renderable(key="first")
        show = Show(
            when=lambda: True,
            render=lambda: Renderable(key="second"),
            key="show",
        )
        third = Renderable(key="third")

        parent.add(first)
        parent.add(show)
        parent.add(third)

        # The Show node itself is a child of parent, holding "second" inside.
        assert len(parent._children) == 3
        assert parent._children[0].key == "first"
        assert parent._children[1].key == "show"
        assert parent._children[2].key == "third"

        # The Show's own child should be the rendered content.
        assert len(show._children) == 1
        assert show._children[0].key == "second"

        # When Show is false with no fallback, it has no children (inactive).
        show_false = Show(
            when=lambda: False,
            render=lambda: Renderable(key="hidden"),
            key="show-false",
        )
        parent2 = Renderable(key="container2")
        parent2.add(Renderable(key="first"))
        parent2.add(show_false)
        parent2.add(Renderable(key="third"))

        # Parent still has 3 children (the Show node is present but inactive).
        assert len(parent2._children) == 3
        assert parent2._children[0].key == "first"
        assert parent2._children[1].key == "show-false"
        assert parent2._children[2].key == "third"

        # Inactive Show has zero children.
        assert len(show_false._children) == 0
        assert show_false._is_active is False


# ---------------------------------------------------------------------------
# Switch tests
# ---------------------------------------------------------------------------


class TestSwitch:
    def test_condition_matching(self):
        """Match objects — first truthy wins."""
        switch = Switch(
            Match(when=lambda: False, render=lambda: Renderable(key="a")),
            Match(when=lambda: True, render=lambda: Renderable(key="b")),
            Match(when=lambda: True, render=lambda: Renderable(key="c")),
            key="switch",
        )
        assert len(switch._children) == 1
        assert switch._children[0].key == "b"
        assert switch._is_active is True

    def test_value_matching(self):
        """on/cases dict selects correct branch."""
        switch = Switch(
            on=lambda: 1,
            cases={
                0: lambda: Renderable(key="zero"),
                1: lambda: Renderable(key="one"),
                2: lambda: Renderable(key="two"),
            },
            key="switch",
        )
        assert len(switch._children) == 1
        assert switch._children[0].key == "one"

    def test_fallback(self):
        """No match → fallback."""
        switch = Switch(
            on=lambda: 99,
            cases={0: lambda: Renderable(key="zero")},
            fallback=lambda: Renderable(key="default"),
            key="switch",
        )
        assert len(switch._children) == 1
        assert switch._children[0].key == "default"

    def test_no_match_no_fallback(self):
        """No match, no fallback → empty, inactive."""
        switch = Switch(
            on=lambda: 99,
            cases={0: lambda: Renderable(key="zero")},
            key="switch",
        )
        assert len(switch._children) == 0
        assert switch._is_active is False

    def test_branch_change_via_reconciler(self):
        """Reconciler handles Switch branch swap correctly."""
        parent = BaseRenderable()

        # First render: tab=0
        old_switch = Switch(
            on=lambda: 0,
            cases={
                0: lambda: Renderable(key="panel-0"),
                1: lambda: Renderable(key="panel-1"),
            },
            key="switch",
        )
        parent._children = [old_switch]
        old_switch._parent = parent

        # Second render: tab=1
        new_switch = Switch(
            on=lambda: 1,
            cases={
                0: lambda: Renderable(key="panel-0"),
                1: lambda: Renderable(key="panel-1"),
            },
            key="switch",
        )

        reconcile(parent, [old_switch], [new_switch])

        # Old switch preserved (same type + key)
        assert parent._children[0] is old_switch
        # Children should now be from tab=1
        assert len(old_switch._children) == 1
        assert old_switch._children[0].key == "panel-1"

    def test_condition_matching_no_truthy(self):
        """All Match conditions false → fallback."""
        switch = Switch(
            Match(when=lambda: False, render=lambda: Renderable(key="a")),
            Match(when=lambda: False, render=lambda: Renderable(key="b")),
            fallback=lambda: Renderable(key="fallback"),
            key="switch",
        )
        assert switch._children[0].key == "fallback"

    def test_switch_with_for_inside_matches(self):
        """Switch branches can contain For components.

        Upstream: "should handle <Switch> with <For> inside matches" —
        verifies that switching between modes changes the For-rendered
        content (e.g. "list" mode vs "grid" mode).
        """
        items = [_make_item(1, "One"), _make_item(2, "Two"), _make_item(3, "Three")]

        def render_list_item(item):
            return Renderable(key=f"list-{item['id']}")

        def render_grid_item(item):
            return Renderable(key=f"grid-{item['id']}")

        # "list" mode — For renders list-style items
        switch_list = Switch(
            Match(
                when=lambda: True,
                render=lambda: For(
                    each=items,
                    render=render_list_item,
                    key_fn=lambda e: f"list-{e['id']}",
                    key="for-list",
                ),
            ),
            Match(
                when=lambda: False,
                render=lambda: For(
                    each=items,
                    render=render_grid_item,
                    key_fn=lambda e: f"grid-{e['id']}",
                    key="for-grid",
                ),
            ),
            key="switch",
        )

        assert len(switch_list._children) == 1
        list_for = switch_list._children[0]
        assert isinstance(list_for, For)
        # For is lazy — reconcile its children
        list_for._reconcile_children()
        assert len(list_for._children) == 3
        assert list_for._children[0].key == "list-1"
        assert list_for._children[1].key == "list-2"
        assert list_for._children[2].key == "list-3"

        # "grid" mode — second Match is true
        switch_grid = Switch(
            Match(
                when=lambda: False,
                render=lambda: For(
                    each=items,
                    render=render_list_item,
                    key_fn=lambda e: f"list-{e['id']}",
                    key="for-list",
                ),
            ),
            Match(
                when=lambda: True,
                render=lambda: For(
                    each=items,
                    render=render_grid_item,
                    key_fn=lambda e: f"grid-{e['id']}",
                    key="for-grid",
                ),
            ),
            key="switch",
        )

        assert len(switch_grid._children) == 1
        grid_for = switch_grid._children[0]
        assert isinstance(grid_for, For)
        grid_for._reconcile_children()
        assert len(grid_for._children) == 3
        assert grid_for._children[0].key == "grid-1"
        assert grid_for._children[1].key == "grid-2"
        assert grid_for._children[2].key == "grid-3"


# ---------------------------------------------------------------------------
# Reactive subscription tests — signal changes update without full rebuild
# ---------------------------------------------------------------------------


class TestShowReactive:
    """Show reactively swaps children when tracked signals change."""

    def test_show_reactive_toggle(self):
        """Signal change swaps Show children without manual reconcile."""
        visible = Signal(True, name="visible")
        show = Show(
            when=lambda: visible(),
            render=lambda: Renderable(key="content"),
            fallback=lambda: Renderable(key="hidden"),
            key="show",
        )
        assert show._children[0].key == "content"
        assert show._current_branch == "render"

        # Signal change → reactive update
        visible.set(False)
        assert show._children[0].key == "hidden"
        assert show._current_branch == "fallback"

        # Toggle back
        visible.set(True)
        assert show._children[0].key == "content"
        assert show._current_branch == "render"

    def test_show_reactive_to_none(self):
        """Signal becomes falsy with no fallback → empty, inactive."""
        visible = Signal(True, name="visible")
        show = Show(
            when=lambda: visible(),
            render=lambda: Renderable(key="content"),
            key="show",
        )
        assert len(show._children) == 1
        assert show._is_active is True

        visible.set(False)
        assert len(show._children) == 0
        assert show._is_active is False
        assert show._current_branch == "none"

    def test_show_reactive_same_branch_noop(self):
        """Same branch after signal change → no child destruction."""
        visible = Signal(True, name="visible")
        show = Show(
            when=lambda: visible(),
            render=lambda: Renderable(key="content"),
            key="show",
        )
        child = show._children[0]

        # Set to another truthy value — same branch
        visible.set(42)
        assert show._children[0] is child  # Same identity

    def test_show_reactive_caches_old_children(self):
        """Branch swap caches old children (not destroyed until Show destroys)."""
        visible = Signal(True, name="visible")
        destroyed = []
        show = Show(
            when=lambda: visible(),
            render=lambda: Renderable(key="content"),
            fallback=lambda: Renderable(key="hidden"),
            key="show",
        )
        content_child = show._children[0]
        content_child.on_cleanup(lambda: destroyed.append("content"))

        visible.set(False)
        # Branch cached, not destroyed
        assert "content" not in destroyed
        assert show._render_cache is not None
        assert content_child in show._render_cache

        # Destroying Show cleans up cached branches
        show.destroy()
        assert "content" in destroyed

    def test_show_destroy_cleans_subscription(self):
        """Destroying Show unsubscribes from signals."""
        visible = Signal(True, name="visible")
        show = Show(
            when=lambda: visible(),
            render=lambda: Renderable(key="content"),
            key="show",
        )
        assert show._condition_cleanup is not None

        show.destroy()
        assert show._condition_cleanup is None

        # Signal change after destroy should not crash
        visible.set(False)


class TestSwitchReactive:
    """Switch reactively swaps branches when tracked signals change."""

    def test_switch_reactive_value_change(self):
        """on= signal change swaps Switch branch."""
        tab = Signal(0, name="tab")
        switch = Switch(
            on=lambda: tab(),
            cases={
                0: lambda: Renderable(key="panel-0"),
                1: lambda: Renderable(key="panel-1"),
                2: lambda: Renderable(key="panel-2"),
            },
            key="switch",
        )
        assert switch._children[0].key == "panel-0"

        tab.set(1)
        assert switch._children[0].key == "panel-1"

        tab.set(2)
        assert switch._children[0].key == "panel-2"

    def test_switch_reactive_to_fallback(self):
        """Value doesn't match any case → falls back."""
        tab = Signal(0, name="tab")
        switch = Switch(
            on=lambda: tab(),
            cases={0: lambda: Renderable(key="panel-0")},
            fallback=lambda: Renderable(key="default"),
            key="switch",
        )
        assert switch._children[0].key == "panel-0"

        tab.set(99)
        assert switch._children[0].key == "default"
        assert switch._current_branch_key == ("fallback",)

    def test_switch_reactive_to_none(self):
        """No match, no fallback → inactive."""
        tab = Signal(0, name="tab")
        switch = Switch(
            on=lambda: tab(),
            cases={0: lambda: Renderable(key="panel-0")},
            key="switch",
        )
        assert switch._is_active is True

        tab.set(99)
        assert switch._is_active is False
        assert len(switch._children) == 0

    def test_switch_reactive_same_branch_noop(self):
        """Same branch key → no child destruction."""
        tab = Signal(0, name="tab")
        switch = Switch(
            on=lambda: tab(),
            cases={0: lambda: Renderable(key="panel-0")},
            key="switch",
        )
        child = switch._children[0]

        # Set same value → same branch
        tab.set(0)
        assert switch._children[0] is child

    def test_switch_reactive_match_mode(self):
        """Match-based switch reactively updates on signal change."""
        score = Signal(95, name="score")
        switch = Switch(
            Match(when=lambda: score() >= 90, render=lambda: Renderable(key="A")),
            Match(when=lambda: score() >= 80, render=lambda: Renderable(key="B")),
            fallback=lambda: Renderable(key="F"),
            key="grade",
        )
        assert switch._children[0].key == "A"

        score.set(85)
        assert switch._children[0].key == "B"

        score.set(50)
        assert switch._children[0].key == "F"

    def test_switch_destroy_cleans_subscription(self):
        """Destroying Switch unsubscribes from signals."""
        tab = Signal(0, name="tab")
        switch = Switch(
            on=lambda: tab(),
            cases={0: lambda: Renderable(key="p0")},
            key="switch",
        )
        assert switch._condition_cleanup is not None

        switch.destroy()
        assert switch._condition_cleanup is None
        tab.set(1)  # Should not crash


class TestForReactive:
    """For reactively reconciles children when tracked signals change."""

    def test_for_reactive_signal_change(self):
        """Signal change triggers reactive reconciliation."""
        items_sig = Signal([_make_item(1), _make_item(2)], name="items")
        f = For(
            each=lambda: items_sig(),
            render=_render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()
        assert len(f._children) == 2

        # Add item via signal
        items_sig.set([_make_item(1), _make_item(2), _make_item(3)])
        assert len(f._children) == 3
        assert f._children[2].key == "item-3"

    def test_for_reactive_preserves_existing(self):
        """Reactive update preserves existing children by key."""
        items_sig = Signal([_make_item(1), _make_item(2)], name="items")
        f = For(
            each=lambda: items_sig(),
            render=_render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()
        child_1 = f._children[0]
        child_2 = f._children[1]

        items_sig.set([_make_item(1), _make_item(2), _make_item(3)])
        assert f._children[0] is child_1
        assert f._children[1] is child_2

    def test_for_reactive_remove(self):
        """Reactive update removes and destroys deleted items."""
        items_sig = Signal([_make_item(1), _make_item(2), _make_item(3)], name="items")
        f = For(
            each=lambda: items_sig(),
            render=_render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()

        destroyed = []
        f._children[1].on_cleanup(lambda: destroyed.append("item-2"))

        items_sig.set([_make_item(1), _make_item(3)])
        assert len(f._children) == 2
        assert "item-2" in destroyed

    def test_for_destroy_cleans_subscription(self):
        """Destroying For unsubscribes from signals."""
        items_sig = Signal([_make_item(1)], name="items")
        f = For(
            each=lambda: items_sig(),
            render=_render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()
        assert f._data_cleanup is not None

        f.destroy()
        assert f._data_cleanup is None
        items_sig.set([_make_item(1), _make_item(2)])  # Should not crash


# ---------------------------------------------------------------------------
# Subscription leak prevention tests
# ---------------------------------------------------------------------------


class TestSubscriptionLeakPrevention:
    """Verify that reconciler cleans up subscriptions on discarded new nodes."""

    def test_show_reconcile_no_leak(self):
        """Reconciling Show cleans up new node's subscription."""
        visible = Signal(True, name="visible")

        old_show = Show(
            when=lambda: visible(),
            render=lambda: Renderable(key="content"),
            key="show",
        )
        parent = BaseRenderable()
        parent._children = [old_show]
        old_show._parent = parent

        initial_sub_count = _sub_count(visible)

        # Simulate full rebuild: create new Show (subscribes in __init__)
        new_show = Show(
            when=lambda: visible(),
            render=lambda: Renderable(key="content"),
            key="show",
        )
        assert _sub_count(visible) == initial_sub_count + 1  # Leaked if not cleaned

        # Reconcile — should clean up new_show's subscription
        reconcile(parent, [old_show], [new_show])

        assert _sub_count(visible) == initial_sub_count  # No leak
        assert parent._children[0] is old_show  # Old preserved

    def test_switch_reconcile_no_leak(self):
        """Reconciling Switch cleans up new node's subscription."""
        tab = Signal(0, name="tab")

        old_switch = Switch(
            on=lambda: tab(),
            cases={0: lambda: Renderable(key="p0")},
            key="sw",
        )
        parent = BaseRenderable()
        parent._children = [old_switch]
        old_switch._parent = parent

        initial_sub_count = _sub_count(tab)

        new_switch = Switch(
            on=lambda: tab(),
            cases={0: lambda: Renderable(key="p0")},
            key="sw",
        )
        assert _sub_count(tab) == initial_sub_count + 1

        reconcile(parent, [old_switch], [new_switch])
        assert _sub_count(tab) == initial_sub_count

    def test_for_reconcile_no_leak(self):
        """Reconciling For cleans up new node's subscription."""
        items_sig = Signal([_make_item(1)], name="items")

        old_for = For(
            each=lambda: items_sig(),
            render=_render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="for",
        )
        old_for._reconcile_children()
        parent = BaseRenderable()
        parent._children = [old_for]
        old_for._parent = parent

        initial_sub_count = _sub_count(items_sig)

        new_for = For(
            each=lambda: items_sig(),
            render=_render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="for",
        )

        reconcile(parent, [old_for], [new_for])
        assert _sub_count(items_sig) == initial_sub_count

    def test_show_no_accumulating_subscribers(self):
        """Multiple reconciliations don't accumulate subscribers."""
        visible = Signal(True, name="visible")

        parent = BaseRenderable()
        old_show = Show(
            when=lambda: visible(),
            render=lambda: Renderable(key="c"),
            key="show",
        )
        parent._children = [old_show]
        old_show._parent = parent

        initial_sub_count = _sub_count(visible)

        # Simulate 10 rebuilds
        for _ in range(10):
            new_show = Show(
                when=lambda: visible(),
                render=lambda: Renderable(key="c"),
                key="show",
            )
            reconcile(parent, list(parent._children), [new_show])

        # Should still have same subscriber count — no leaks
        assert _sub_count(visible) == initial_sub_count


# ---------------------------------------------------------------------------
# Re-tracking tests — conditional deps correctly handled
# ---------------------------------------------------------------------------


class TestShowRetracking:
    """Show re-tracks deps when condition reads different signals."""

    def test_show_retracks_conditional_deps(self):
        """Show discovers new signal deps on reactive update."""
        mode = Signal("a", name="mode")
        sig_a = Signal(True, name="a")
        sig_b = Signal(True, name="b")

        show = Show(
            when=lambda: sig_a() if mode() == "a" else sig_b(),
            render=lambda: Renderable(key="content"),
            key="show",
        )
        assert show._current_branch == "render"

        # Initially tracks mode + sig_a. Change sig_b — should NOT trigger.
        sig_b.set(False)
        assert show._current_branch == "render"  # No change (sig_b not tracked)

        # Switch mode to "b" — re-tracks, now tracks mode + sig_b
        mode.set("b")
        # sig_b is False, so now condition is False
        assert show._current_branch == "none"

        # Now sig_b changes should trigger updates
        sig_b.set(True)
        assert show._current_branch == "render"

    def test_switch_retracks_conditional_deps(self):
        """Switch discovers new signal deps on reactive update."""
        mode = Signal("direct", name="mode")
        tab = Signal(0, name="tab")
        alt = Signal(0, name="alt")

        switch = Switch(
            on=lambda: tab() if mode() == "direct" else alt(),
            cases={
                0: lambda: Renderable(key="p0"),
                1: lambda: Renderable(key="p1"),
            },
            key="sw",
        )
        assert switch._children[0].key == "p0"

        # tab change triggers update
        tab.set(1)
        assert switch._children[0].key == "p1"

        # Switch to alt mode — now tracks mode + alt instead of mode + tab
        mode.set("alt")
        # alt is 0, so branch changes to p0
        assert switch._children[0].key == "p0"

        # alt change should now trigger
        alt.set(1)
        assert switch._children[0].key == "p1"

        # tab change should NOT trigger anymore
        tab.set(0)
        assert switch._children[0].key == "p1"  # Unchanged


# ---------------------------------------------------------------------------
# Rebuild-skip optimization tests
# ---------------------------------------------------------------------------


class TestRebuildSkip:
    """Verify signal changes are handled reactively by Show/For/Switch
    without triggering rebuilds."""

    async def test_show_signal_updates_reactively(self):
        """Signal read only in Show.when updates content reactively."""
        visible = Signal(True, name="visible")

        def component():
            return Box(
                Show(
                    when=lambda: visible(),
                    render=lambda: Text("Shown"),
                    fallback=lambda: Text("Hidden"),
                    key="show",
                ),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})

        visible.set(False)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Hidden" in frame

        visible.set(True)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Shown" in frame

        setup.destroy()

    async def test_template_component_updates_stable_text(self):
        """Template-lowered stable text updates reactively."""
        count = Signal(0, name="count")

        @template_component
        def component():
            return Box(Text(reactive(lambda: f"Count: {count()}"), id="count_text"))

        setup = await _test_render(component, {"width": 40, "height": 10})

        count.set(1)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Count: 1" in frame

        setup.destroy()

    async def test_body_signal_reads_rejected(self):
        """Signal reads in ordinary component bodies are rejected."""
        count = Signal(0, name="count")

        def component():
            return Box(Text(f"Count: {count()}"))

        import pytest

        with pytest.raises(RuntimeError, match="reads signals in its body"):
            await _test_render(component, {"width": 40, "height": 10})

    async def test_template_components_skip_signal_tracking(self):
        """Template components skip signal tracking and work correctly."""
        count = Signal(0, name="count")

        @template_component
        def component():
            return Box(Text(reactive(lambda: f"Count: {count()}"), id="count_text"))

        setup = await _test_render(component, {"width": 40, "height": 10})

        count.set(2)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Count: 2" in frame

        setup.destroy()

    async def test_switch_signal_updates_reactively(self):
        """Signal read only in Switch.on updates content reactively."""
        tab = Signal(0, name="tab")

        def component():
            return Box(
                Switch(
                    on=lambda: tab(),
                    cases={
                        0: lambda: Text("Tab 0"),
                        1: lambda: Text("Tab 1"),
                    },
                    key="tabs",
                ),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})

        tab.set(1)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Tab 1" in frame

        setup.destroy()

    async def test_successful_frame_clears_dirty_flags(self):
        """Renderer clears _dirty after a successful frame so future pruning can rely on it."""

        class CountingRenderable(Renderable):
            __slots__ = ("render_count",)

            def __init__(self):
                super().__init__()
                self.render_count = 0

            def render(self, buffer, delta_time: float = 0) -> None:
                self.render_count += 1

        child = CountingRenderable()

        def component():
            return Box(child)

        setup = await _test_render(component, {"width": 40, "height": 10})

        setup.render_frame()
        assert child.render_count == 1
        assert child._dirty is False

        child.mark_dirty()
        setup.render_frame()
        assert child.render_count == 2
        assert child._dirty is False

        setup.destroy()

    async def test_custom_update_layout_still_runs_on_clean_frames(self):
        """Layout-hook renderables must still receive per-frame update_layout calls."""

        class CountingLayoutRenderable(Renderable):
            __slots__ = ("layout_calls",)

            def __init__(self):
                super().__init__()
                self.layout_calls = 0

            def update_layout(self, delta_time: float = 0) -> None:
                self.layout_calls += 1

        child = CountingLayoutRenderable()

        def component():
            return Box(child)

        setup = await _test_render(component, {"width": 40, "height": 10})

        setup.render_frame()
        setup.render_frame()

        assert child.layout_calls == 2

        setup.destroy()


# ---------------------------------------------------------------------------
# For data-change propagation tests
# ---------------------------------------------------------------------------


class TestForDataPropagation:
    """Verify that For propagates data changes to reused children."""

    def test_for_updates_reused_child_props(self):
        """Reused child gets updated props when data changes (same keys)."""
        items = [{"id": 1, "label": "old"}]

        def render_item(item):
            return Text(item["label"], key=f"item-{item['id']}")

        f = For(
            each=lambda: items,
            render=render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()
        assert f._children[0]._content == "old"

        child_identity = f._children[0]

        # Update data (same key, different label)
        items[0] = {"id": 1, "label": "new"}
        f._reconcile_children()

        # Same identity (reused), but props updated
        assert f._children[0] is child_identity
        assert f._children[0]._content == "new"

    def test_for_fast_path_still_patches(self):
        """Fast path (same keys, same order) still patches data changes."""
        items = [{"id": 1, "label": "A"}, {"id": 2, "label": "B"}]

        def render_item(item):
            return Text(item["label"], key=f"item-{item['id']}")

        f = For(
            each=lambda: items,
            render=render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()
        child_1 = f._children[0]
        child_2 = f._children[1]

        # Same keys, same order, different labels
        items[0] = {"id": 1, "label": "A-updated"}
        items[1] = {"id": 2, "label": "B-updated"}
        f._reconcile_children()

        # Same identities, updated props
        assert f._children[0] is child_1
        assert f._children[1] is child_2
        assert f._children[0]._content == "A-updated"
        assert f._children[1]._content == "B-updated"

    def test_for_reactive_data_change_propagates(self):
        """Signal-driven data change propagates to reused children."""
        items_sig = Signal([{"id": 1, "label": "v1"}], name="items")

        def render_item(item):
            return Text(item["label"], key=f"item-{item['id']}")

        f = For(
            each=lambda: items_sig(),
            render=render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()
        assert f._children[0]._content == "v1"
        child = f._children[0]

        # Signal update with same key, new data
        items_sig.set([{"id": 1, "label": "v2"}])

        assert f._children[0] is child  # Same identity
        assert f._children[0]._content == "v2"  # Updated data

    async def test_for_data_change_renders_correctly(self):
        """For data change propagates to visible text output."""
        items_sig = Signal(
            [
                {"id": 1, "label": "Alpha"},
                {"id": 2, "label": "Bravo"},
            ],
            name="items",
        )

        def component():
            return Box(
                For(
                    each=lambda: items_sig(),
                    render=lambda item: Text(item["label"], key=f"item-{item['id']}"),
                    key_fn=lambda e: f"item-{e['id']}",
                    key="list",
                ),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})
        frame = setup.capture_char_frame()
        assert "Alpha" in frame
        assert "Bravo" in frame

        # Update labels (same keys)
        items_sig.set(
            [
                {"id": 1, "label": "Alpha-v2"},
                {"id": 2, "label": "Bravo-v2"},
            ]
        )
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Alpha-v2" in frame
        assert "Bravo-v2" in frame
        setup.destroy()

    def test_for_prepend_fast_path_preserves_suffix_and_skips_rerender(self):
        """Pure prepend preserves existing suffix identities and only renders new heads."""
        item_one = {"id": 1}
        item_two = {"id": 2}
        items = [item_one, item_two]
        render_calls: list[int] = []
        destroyed: list[int] = []

        class Row(Text):
            __slots__ = ("item_id",)

            def __init__(self, item_id: int):
                super().__init__(f"item-{item_id}", key=f"item-{item_id}")
                self.item_id = item_id

            def destroy(self) -> None:
                destroyed.append(self.item_id)
                super().destroy()

        def render_item(item):
            render_calls.append(item["id"])
            return Row(item["id"])

        f = For(
            each=lambda: items,
            render=render_item,
            key_fn=lambda e: f"item-{e['id']}",
            key="list",
        )
        f._reconcile_children()
        old_first = f._children[0]
        old_second = f._children[1]

        render_calls.clear()
        items = [{"id": 0}, item_one, item_two]
        f._reconcile_children()

        assert [child.key for child in f._children] == ["item-0", "item-1", "item-2"]
        assert f._children[0] is not old_first
        assert f._children[1] is old_first
        assert f._children[2] is old_second
        assert render_calls == [0]
        assert destroyed == []


# ---------------------------------------------------------------------------
# Render-output verification tests
# ---------------------------------------------------------------------------


def _rebuild(setup, component_fn):
    """Rebuild the component tree from a factory function.

    Clears the root's children and yoga nodes, then adds the new component.
    This is the Python equivalent of SolidJS reactive re-rendering.
    """
    root = setup.renderer.root
    root._children.clear()
    root._yoga_node.remove_all_children()
    component = component_fn()
    root.add(component)


class TestControlFlowRenderOutput:
    """End-to-end render verification for For, Show, and Switch.

    These tests use test_render / capture_char_frame to verify that
    control-flow primitives produce the expected visible output, not
    just the correct tree structure.
    """

    async def test_for_renders_visible_items(self):
        """For component renders each item's text content into the frame."""
        items = [
            {"id": 1, "label": "Alpha"},
            {"id": 2, "label": "Bravo"},
            {"id": 3, "label": "Charlie"},
        ]

        def component():
            return Box(
                For(
                    each=items,
                    render=lambda item: Text(item["label"], key=f"item-{item['id']}"),
                    key_fn=lambda e: f"item-{e['id']}",
                    key="list",
                ),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})
        frame = setup.capture_char_frame()

        assert "Alpha" in frame
        assert "Bravo" in frame
        assert "Charlie" in frame
        setup.destroy()

    async def test_show_renders_content_when_true(self):
        """Show with truthy condition renders its content visibly."""

        def component():
            return Box(
                Show(
                    when=lambda: True,
                    render=lambda: Text("Visible content"),
                    key="show",
                ),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})
        frame = setup.capture_char_frame()

        assert "Visible content" in frame
        setup.destroy()

    async def test_show_renders_fallback_when_false(self):
        """Show with falsy condition renders the fallback content."""

        def component():
            return Box(
                Show(
                    when=lambda: False,
                    render=lambda: Text("Primary content"),
                    fallback=lambda: Text("Fallback content"),
                    key="show",
                ),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})
        frame = setup.capture_char_frame()

        assert "Primary content" not in frame
        assert "Fallback content" in frame
        setup.destroy()

    async def test_show_toggles_content(self):
        """Toggling Show's condition signal swaps visible content."""
        visible = Signal(True, name="visible")

        def component():
            return Box(
                Show(
                    when=lambda: visible(),
                    render=lambda: Text("Now you see me"),
                    fallback=lambda: Text("Now you don't"),
                    key="show",
                ),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})
        frame = setup.capture_char_frame()
        assert "Now you see me" in frame
        assert "Now you don't" not in frame

        # Toggle condition to False and rebuild
        visible.set(False)
        _rebuild(setup, component)

        frame = setup.capture_char_frame()
        assert "Now you see me" not in frame
        assert "Now you don't" in frame
        setup.destroy()


# ---------------------------------------------------------------------------
# Reactive Text — callable content with signal auto-tracking
# ---------------------------------------------------------------------------


class TestReactiveText:
    """Text with callable content reactively updates when signals change."""

    def test_callable_content_initial_value(self):
        """Callable content is evaluated to produce initial _content."""
        count = Signal(42, name="count")
        text = Text(lambda: f"Count: {count()}")
        assert text._content == "Count: 42"

    def test_callable_content_signal_update(self):
        """Signal change updates Text._content reactively."""
        count = Signal(0, name="count")
        text = Text(lambda: f"Count: {count()}")
        assert text._content == "Count: 0"

        count.set(5)
        assert text._content == "Count: 5"

        count.set(10)
        assert text._content == "Count: 10"

    def test_callable_content_multiple_signals(self):
        """Callable that reads multiple signals tracks all of them."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        text = Text(lambda: f"{a()} + {b()} = {a() + b()}")
        assert text._content == "1 + 2 = 3"

        a.set(10)
        assert text._content == "10 + 2 = 12"

        b.set(20)
        assert text._content == "10 + 20 = 30"

    def test_callable_content_same_value_noop(self):
        """Same computed content doesn't mark dirty."""
        count = Signal(5, name="count")
        text = Text(lambda: f"Count: {count()}")
        text._dirty = False  # Reset dirty

        # Set signal to same value — no notification at all
        count.set(5)
        assert text._dirty is False

    def test_callable_content_retracks_deps(self):
        """Conditional reads re-track on each update."""
        mode = Signal("a", name="mode")
        sig_a = Signal("hello", name="a")
        sig_b = Signal("world", name="b")

        text = Text(lambda: sig_a() if mode() == "a" else sig_b())
        assert text._content == "hello"

        # sig_b not tracked yet — changing it should NOT update
        sig_b.set("WORLD")
        assert text._content == "hello"

        # Switch mode → re-tracks, now reads sig_b
        mode.set("b")
        assert text._content == "WORLD"

        # sig_a no longer tracked
        sig_a.set("HELLO")
        assert text._content == "WORLD"

        # sig_b now triggers
        sig_b.set("updated")
        assert text._content == "updated"

    def test_callable_content_destroy_cleans_subscription(self):
        """Destroying reactive Text unsubscribes from signals."""
        count = Signal(0, name="count")
        text = Text(lambda: f"Count: {count()}")
        assert text._prop_bindings is not None

        initial_sub_count = _sub_count(count)
        text.destroy()
        assert _sub_count(count) < initial_sub_count

        # Signal change after destroy should not crash
        count.set(99)

    def test_static_content_unchanged(self):
        """Static string content still works normally."""
        text = Text("Hello")
        assert text._content == "Hello"
        assert text._prop_bindings is None

    def test_callable_content_none_return(self):
        """Callable returning None produces empty string."""
        text = Text(lambda: None)
        assert text._content == ""

    def test_callable_content_int_return(self):
        """Callable returning non-string value is stringified."""
        count = Signal(42, name="count")
        text = Text(lambda: count())
        assert text._content == "42"

        count.set(99)
        assert text._content == "99"

    def test_callable_content_zero_deps(self):
        """Callable reading no signals produces static content via _bind_reactive_prop."""
        text = Text(lambda: "constant")
        assert text._content == "constant"
        # Zero-dep callable still creates a binding (ComputedSignal wrapper)
        assert text._prop_bindings is not None

    def test_callable_content_batch_single_update(self):
        """Batch defers reactive Text updates — content is consistent after batch."""
        from opentui.signals import Batch

        a = Signal(1, name="a")
        b = Signal(2, name="b")
        eval_count = 0

        def content_fn():
            nonlocal eval_count
            eval_count += 1
            return f"{a()} + {b()}"

        text = Text(content_fn)
        assert text._content == "1 + 2"
        eval_count = 0  # Reset after init

        with Batch():
            a.set(10)
            b.set(20)
            # During batch, subscribers are deferred
            assert text._content == "1 + 2"

        # After batch exit, content reflects final values
        assert text._content == "10 + 20"

    def test_callable_content_exception_in_update(self):
        """Exception in callable during reactive update resets reentrancy guard.

        With _bind_reactive_prop, the callable is wrapped in a ComputedSignal.
        When the callable raises, the exception propagates through the signal
        subscriber chain. The ComputedSignal's _computing guard is reset in
        its finally block, and the old value is preserved (set() never called).
        """
        count = Signal(0, name="count")
        should_fail = Signal(False, name="fail")

        def content_fn():
            if should_fail():
                raise ValueError("boom")
            return f"Count: {count()}"

        text = Text(content_fn)
        assert text._content == "Count: 0"

        # Trigger exception — propagates through signal subscriber
        try:
            should_fail.set(True)
        except ValueError:
            pass  # Exception propagates out of signal.set()

        # After fixing the callable, updates should resume
        try:
            should_fail.set(False)
        except Exception:
            pass
        # The content should be restored since the callable no longer raises
        # A new signal change triggers the ComputedSignal to re-evaluate
        count.set(1)
        assert text._content == "Count: 1"

    def test_callable_content_diff_tracking_efficiency(self):
        """Reactive text with multiple deps updates correctly."""
        a = Signal(1, name="a")
        b = Signal(2, name="b")
        text = Text(lambda: f"{a()} + {b()}")
        assert text._prop_bindings is not None

        # Trigger update — same deps, content updates correctly
        a.set(5)
        assert text._content == "5 + 2"

        b.set(10)
        assert text._content == "5 + 10"


class TestReactiveTextReconciler:
    """Reconciler correctly handles reactive Text."""

    def test_text_reconcile_no_leak(self):
        """Reconciling reactive Text cleans up new node's subscription."""
        count = Signal(0, name="count")

        old_text = Text(lambda: f"Count: {count()}", key="counter")
        parent = BaseRenderable()
        parent._children = [old_text]
        old_text._parent = parent

        initial_sub_count = _sub_count(count)

        # Simulate rebuild: new Text subscribes in __init__
        new_text = Text(lambda: f"Count: {count()}", key="counter")
        assert _sub_count(count) == initial_sub_count + 1  # Leaked if not cleaned

        # Reconcile — should clean up new_text's subscription
        reconcile(parent, [old_text], [new_text])

        assert _sub_count(count) == initial_sub_count  # No leak
        assert parent._children[0] is old_text  # Old preserved

    def test_text_no_accumulating_subscribers(self):
        """Multiple reconciliations don't accumulate subscribers."""
        count = Signal(0, name="count")

        parent = BaseRenderable()
        old_text = Text(lambda: f"Count: {count()}", key="counter")
        parent._children = [old_text]
        old_text._parent = parent

        initial_sub_count = _sub_count(count)

        # Simulate 10 rebuilds
        for _ in range(10):
            new_text = Text(lambda: f"Count: {count()}", key="counter")
            reconcile(parent, list(parent._children), [new_text])

        assert _sub_count(count) == initial_sub_count

    def test_text_reactive_after_reconcile(self):
        """Old reactive Text still updates after reconciliation."""
        count = Signal(0, name="count")

        old_text = Text(lambda: f"Count: {count()}", key="counter")
        parent = BaseRenderable()
        parent._children = [old_text]
        old_text._parent = parent

        new_text = Text(lambda: f"Count: {count()}", key="counter")
        reconcile(parent, [old_text], [new_text])

        # Old text still reactive
        count.set(42)
        assert old_text._content == "Count: 42"

    def test_text_callable_patched_on_reconcile(self):
        """Reconciler patches _content_source from new to old."""
        count = Signal(0, name="count")

        old_text = Text(lambda: f"v1: {count()}", key="counter")
        parent = BaseRenderable()
        parent._children = [old_text]
        old_text._parent = parent

        # New Text has a different callable
        new_text = Text(lambda: f"v2: {count()}", key="counter")
        reconcile(parent, [old_text], [new_text])

        # After reconcile, old_text has new callable
        count.set(5)
        assert old_text._content == "v2: 5"


class TestReactiveTextRebuildSkip:
    """Reactive Text updates without full tree rebuilds."""

    async def test_reactive_text_updates(self):
        """Signal read only in Text callable updates reactively."""
        count = Signal(0, name="count")

        def component():
            return Box(
                Text(lambda: f"Count: {count()}", key="counter"),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})

        count.set(1)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Count: 1" in frame

        count.set(42)
        setup.render_frame()

        frame = setup.capture_char_frame()
        assert "Count: 42" in frame

        setup.destroy()

    async def test_reactive_text_renders_initial_value(self):
        """Reactive Text renders correct initial content."""
        count = Signal(7, name="count")

        def component():
            return Box(
                Text(lambda: f"Value: {count()}", key="display"),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})
        frame = setup.capture_char_frame()
        assert "Value: 7" in frame
        setup.destroy()

    async def test_mixed_reactive_text_and_show(self):
        """Reactive Text and Show both update reactively."""
        count = Signal(0, name="count")
        visible = Signal(True, name="visible")

        def component():
            return Box(
                Text(lambda: f"Count: {count()}", key="counter"),
                Show(
                    when=lambda: visible(),
                    render=lambda: Text("Shown"),
                    fallback=lambda: Text("Hidden"),
                    key="show",
                ),
            )

        setup = await _test_render(component, {"width": 40, "height": 10})

        count.set(5)
        setup.render_frame()
        frame = setup.capture_char_frame()
        assert "Count: 5" in frame

        visible.set(False)
        setup.render_frame()
        frame = setup.capture_char_frame()
        assert "Hidden" in frame

        setup.destroy()
