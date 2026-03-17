"""Tests for key-based reconciliation.

Upstream: N/A (Python-specific)
"""

from opentui.components.base import BaseRenderable, Renderable
from opentui.reconciler import reconcile


class TestReconciler:
    def test_same_type_no_key_preserves_identity(self):
        """Nodes of same type without keys are matched positionally."""
        parent = BaseRenderable()
        old_a = BaseRenderable()
        old_b = BaseRenderable()
        parent._children = [old_a, old_b]
        old_a._parent = parent
        old_b._parent = parent

        new_a = BaseRenderable()
        new_b = BaseRenderable()

        reconcile(parent, [old_a, old_b], [new_a, new_b])

        # Old nodes should be preserved (patched)
        assert parent._children[0] is old_a
        assert parent._children[1] is old_b

    def test_keyed_nodes_matched_by_key(self):
        """Keyed nodes match by (type, key) regardless of order."""
        parent = BaseRenderable()
        old_a = BaseRenderable(key="a")
        old_b = BaseRenderable(key="b")
        parent._children = [old_a, old_b]
        old_a._parent = parent
        old_b._parent = parent

        # Reverse order in new tree
        new_b = BaseRenderable(key="b")
        new_a = BaseRenderable(key="a")

        reconcile(parent, [old_a, old_b], [new_b, new_a])

        # Old nodes preserved, but in new order
        assert parent._children[0] is old_b
        assert parent._children[1] is old_a

    def test_unmatched_old_destroyed(self):
        """Old nodes without a match in new tree are destroyed."""
        parent = BaseRenderable()
        old_a = BaseRenderable(key="a")
        old_b = BaseRenderable(key="b")
        parent._children = [old_a, old_b]
        old_a._parent = parent
        old_b._parent = parent

        destroyed = []
        old_b.on_cleanup(lambda: destroyed.append("b"))

        # New tree only has "a"
        new_a = BaseRenderable(key="a")
        reconcile(parent, [old_a, old_b], [new_a])

        assert len(parent._children) == 1
        assert parent._children[0] is old_a
        assert destroyed == ["b"]

    def test_new_nodes_inserted(self):
        """New nodes without a match in old tree are inserted."""
        parent = BaseRenderable()
        old_a = BaseRenderable(key="a")
        parent._children = [old_a]
        old_a._parent = parent

        new_a = BaseRenderable(key="a")
        new_c = BaseRenderable(key="c")

        reconcile(parent, [old_a], [new_a, new_c])

        assert len(parent._children) == 2
        assert parent._children[0] is old_a  # matched
        assert parent._children[1] is new_c  # new

    def test_type_mismatch_no_match(self):
        """Different types with same key don't match."""
        parent = BaseRenderable()
        old = BaseRenderable(key="x")
        parent._children = [old]
        old._parent = parent

        destroyed = []
        old.on_cleanup(lambda: destroyed.append("old"))

        new = Renderable(key="x")  # Different type
        reconcile(parent, [old], [new])

        assert parent._children[0] is new
        assert destroyed == ["old"]

    def test_empty_old_tree(self):
        """Reconcile with empty old tree just inserts all new."""
        parent = BaseRenderable()
        new_a = BaseRenderable(key="a")
        new_b = BaseRenderable(key="b")

        reconcile(parent, [], [new_a, new_b])

        assert len(parent._children) == 2
        assert parent._children[0] is new_a
        assert parent._children[1] is new_b

    def test_empty_new_tree(self):
        """Reconcile with empty new tree destroys all old."""
        parent = BaseRenderable()
        old_a = BaseRenderable(key="a")
        old_b = BaseRenderable(key="b")
        parent._children = [old_a, old_b]
        old_a._parent = parent
        old_b._parent = parent

        destroyed = []
        old_a.on_cleanup(lambda: destroyed.append("a"))
        old_b.on_cleanup(lambda: destroyed.append("b"))

        reconcile(parent, [old_a, old_b], [])

        assert len(parent._children) == 0
        assert "a" in destroyed
        assert "b" in destroyed

    def test_patching_updates_properties(self):
        """Matched Renderable nodes get their properties patched."""
        parent = BaseRenderable()
        old = Renderable(key="x", width=10, opacity=1.0)
        parent._children = [old]
        old._parent = parent

        new = Renderable(key="x", width=20, opacity=0.5)
        reconcile(parent, [old], [new])

        assert parent._children[0] is old
        assert old._width == 20
        assert old._opacity == 0.5

    def test_recursive_reconciliation(self):
        """Children of matched nodes are also reconciled."""
        parent = BaseRenderable()
        old_container = BaseRenderable(key="c")
        old_child = BaseRenderable(key="child")
        old_container.add(old_child)
        parent._children = [old_container]
        old_container._parent = parent

        new_container = BaseRenderable(key="c")
        new_child = BaseRenderable(key="child")
        new_container._children = [new_child]

        reconcile(parent, [old_container], [new_container])

        assert parent._children[0] is old_container
        # Grandchild should be preserved by key
        assert old_container._children[0] is old_child

    def test_parent_references_correct(self):
        """After reconciliation, all _parent references are correct."""
        parent = BaseRenderable()
        old_a = BaseRenderable(key="a")
        parent._children = [old_a]
        old_a._parent = parent

        new_a = BaseRenderable(key="a")
        new_b = BaseRenderable(key="b")

        reconcile(parent, [old_a], [new_a, new_b])

        for child in parent._children:
            assert child._parent is parent

    def test_yoga_tree_synced_after_reconciliation(self):
        """Yoga child_count matches len(_children) after reconciliation."""
        parent = BaseRenderable()
        old_a = BaseRenderable(key="a")
        old_b = BaseRenderable(key="b")
        parent.add(old_a)
        parent.add(old_b)

        new_b = BaseRenderable(key="b")
        new_a = BaseRenderable(key="a")
        new_c = BaseRenderable(key="c")

        reconcile(parent, [old_a, old_b], [new_b, new_a, new_c])

        assert parent._yoga_node.child_count == len(parent._children)
        assert parent._yoga_node.child_count == 3
        yoga_children = parent._yoga_node.get_layout_children()
        for i, child in enumerate(parent._children):
            assert yoga_children[i] is child._yoga_node

    def test_yoga_tree_synced_through_nested_reconciliation(self):
        """Yoga tree is correct at every level after recursive reconciliation."""
        parent = BaseRenderable()
        container = BaseRenderable(key="c")
        child_x = BaseRenderable(key="x")
        child_y = BaseRenderable(key="y")
        parent.add(container)
        container.add(child_x)
        container.add(child_y)

        # New tree: same container, reordered children + new child
        new_container = BaseRenderable(key="c")
        new_y = BaseRenderable(key="y")
        new_x = BaseRenderable(key="x")
        new_z = BaseRenderable(key="z")
        new_container._children = [new_y, new_x, new_z]

        reconcile(parent, [container], [new_container])

        # Parent level: 1 child (container preserved)
        assert parent._yoga_node.child_count == 1
        assert parent._yoga_node.get_layout_children()[0] is container._yoga_node

        # Container level: 3 children in new order
        assert container._yoga_node.child_count == 3
        yoga_gc = container._yoga_node.get_layout_children()
        assert yoga_gc[0] is child_y._yoga_node  # y first now
        assert yoga_gc[1] is child_x._yoga_node  # x second
        assert yoga_gc[2] is new_z._yoga_node  # z is new

    def test_reconciler_preserves_graphics_id(self):
        """_graphics_id and _last_draw_signature survive reconciliation patching.

        Uses a dict-based subclass to simulate Image's instance attributes.
        """

        class ImageLike(Renderable):
            """No __slots__ — attrs go into __dict__, like Image."""

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._graphics_id = None
                self._last_draw_signature = None

        parent = BaseRenderable()
        old = ImageLike(key="img", width=10)
        old._graphics_id = 42
        old._last_draw_signature = ("logo.png", 0, 0, 10, 10, "kitty")
        parent._children = [old]
        old._parent = parent

        new = ImageLike(key="img", width=20)
        # Fresh node has None for both
        assert new._graphics_id is None
        assert new._last_draw_signature is None

        reconcile(parent, [old], [new])

        assert parent._children[0] is old
        assert old._width == 20  # property was patched
        assert old._graphics_id == 42  # preserved, NOT overwritten to None
        assert old._last_draw_signature == ("logo.png", 0, 0, 10, 10, "kitty")

    def test_change_detection_skips_mark_dirty_when_unchanged(self):
        """_patch_node skips mark_dirty when all attributes are identical."""
        parent = BaseRenderable()
        old = Renderable(key="x", width=10, opacity=0.5)
        parent._children = [old]
        old._parent = parent
        # Clear dirty flag set by construction
        old._dirty = False

        # Same attributes
        new = Renderable(key="x", width=10, opacity=0.5)
        reconcile(parent, [old], [new])

        assert parent._children[0] is old
        assert old._dirty is False, "mark_dirty should not be called when nothing changed"

    def test_change_detection_calls_mark_dirty_when_changed(self):
        """_patch_node calls mark_dirty when an attribute changes."""
        parent = BaseRenderable()
        old = Renderable(key="x", width=10, opacity=1.0)
        parent._children = [old]
        old._parent = parent
        old._dirty = False

        # Different width
        new = Renderable(key="x", width=20, opacity=1.0)
        reconcile(parent, [old], [new])

        assert parent._children[0] is old
        assert old._width == 20
        assert old._dirty is True, "mark_dirty should be called when an attribute changed"

    def test_template_yoga_children_detached_before_recursive_reconcile(self):
        """New template children added via add() don't cause 'already has owner' errors.

        When a component function creates Box(child_a, child_b), __init__ calls
        add() which inserts yoga nodes. The reconciler must detach these from
        the template before inserting them into the matched node's yoga tree.
        """
        parent = BaseRenderable()
        old_container = BaseRenderable(key="c")
        parent.add(old_container)

        # Simulate component function creating template with add()-based children
        new_container = BaseRenderable(key="c")
        new_child_a = BaseRenderable(key="a")
        new_child_b = BaseRenderable(key="b")
        new_container.add(new_child_a)  # yoga node owned by new_container
        new_container.add(new_child_b)  # yoga node owned by new_container

        # This should NOT raise "Child already has a owner"
        reconcile(parent, [old_container], [new_container])

        assert old_container._yoga_node.child_count == 2
        yoga_children = old_container._yoga_node.get_layout_children()
        assert yoga_children[0] is new_child_a._yoga_node
        assert yoga_children[1] is new_child_b._yoga_node
