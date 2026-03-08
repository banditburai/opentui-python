"""Tests for key-based reconciliation."""

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
