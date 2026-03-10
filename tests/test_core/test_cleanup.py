"""Tests for destroy() and cleanup behavior."""

from opentui.components.base import BaseRenderable


class TestDestroyYogaCleanup:
    def test_destroy_removes_yoga_child_from_parent(self):
        """After destroy(), parent's yoga node no longer contains the child."""
        parent = BaseRenderable()
        child = BaseRenderable()
        parent.add(child)
        assert parent._yoga_node.child_count == 1

        child.destroy()
        assert parent._yoga_node.child_count == 0

    def test_destroy_nulls_yoga_node(self):
        """After destroy(), the node's _yoga_node is None."""
        r = BaseRenderable()
        assert r._yoga_node is not None
        r.destroy()
        assert r._yoga_node is None
