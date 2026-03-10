"""Tests for structural control flow primitives — For, Show, Switch."""

from opentui.components.base import BaseRenderable, Renderable
from opentui.components.control_flow import For, Match, Show, Switch
from opentui.reconciler import reconcile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
        f = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list")
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

    def test_item_removed(self):
        """Removed item is destroyed; others preserved."""
        items = [_make_item(1), _make_item(2), _make_item(3)]
        f = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list")
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

    def test_reorder(self):
        """Reorder reuses existing children in new order."""
        items = [_make_item(1), _make_item(2), _make_item(3)]
        f = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list")
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
        f = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list")
        f._reconcile_children()
        assert len(f._children) == 0

        items.extend([_make_item(1), _make_item(2)])
        f._reconcile_children()
        assert len(f._children) == 2

    def test_items_to_empty(self):
        """All items removed."""
        items = [_make_item(1), _make_item(2)]
        f = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="list")
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
        old_for = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="for")
        old_for._reconcile_children()
        parent._children = [old_for]
        old_for._parent = parent

        old_child = old_for._children[0]

        # Add item 2
        items.append(_make_item(2))

        # Template For (what component function would return)
        new_for = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="for")

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
        new_for = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="for")

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
        inner_for = For(each=lambda: items, render=_render_item, key_fn=lambda e: f"item-{e['id']}", key="for")
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
        f = For(each=lambda: items, render=_render_sized_item, key_fn=lambda e: f"item-{e['id']}", key="list", flex_shrink=0)
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
        assert f._layout_height == 8, f"For layout height should be 8 (2 items * 4), got {f._layout_height}"


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
