"""Tests for component cleanup on unmount."""

from opentui.components.base import BaseRenderable


class TestCleanup:
    def test_on_cleanup_runs_on_destroy(self):
        """Cleanup functions run when renderable is destroyed."""
        calls = []
        r = BaseRenderable()
        r.on_cleanup(lambda: calls.append("cleaned"))
        r.destroy()
        assert calls == ["cleaned"]

    def test_multiple_cleanups(self):
        """Multiple cleanup functions all run."""
        calls = []
        r = BaseRenderable()
        r.on_cleanup(lambda: calls.append("a"))
        r.on_cleanup(lambda: calls.append("b"))
        r.on_cleanup(lambda: calls.append("c"))
        r.destroy()
        assert calls == ["a", "b", "c"]

    def test_cleanup_error_does_not_block_others(self):
        """If one cleanup raises, others still run."""
        calls = []
        r = BaseRenderable()
        r.on_cleanup(lambda: calls.append("first"))
        r.on_cleanup(lambda: (_ for _ in ()).throw(ValueError("boom")))
        r.on_cleanup(lambda: calls.append("third"))
        r.destroy()
        assert "first" in calls
        assert "third" in calls

    def test_cleanup_runs_before_children_destroyed(self):
        """Cleanups on parent run before children are destroyed."""
        order = []
        parent = BaseRenderable()
        child = BaseRenderable()
        parent.add(child)
        parent.on_cleanup(lambda: order.append("parent"))
        child.on_cleanup(lambda: order.append("child"))
        parent.destroy()
        assert order[0] == "parent"
        assert "child" in order

    def test_destroy_recursively_runs_cleanups(self):
        """destroy_recursively() also runs cleanups."""
        calls = []
        r = BaseRenderable()
        r.on_cleanup(lambda: calls.append("cleaned"))
        r.destroy_recursively()
        assert calls == ["cleaned"]

    def test_cleanups_cleared_after_destroy(self):
        """After destroy, cleanups list is empty."""
        r = BaseRenderable()
        r.on_cleanup(lambda: None)
        r.destroy()
        assert len(r._cleanups) == 0

    def test_rebuild_destroys_unmatched_old_children(self, fake_renderer):
        """When renderer rebuilds tree, unmatched old children are destroyed with cleanups."""
        r = fake_renderer

        calls = []
        # Use keyed node so reconciler can't match it to different key
        old_child = BaseRenderable(key="old")
        old_child.on_cleanup(lambda: calls.append("cleaned"))
        r._root.add(old_child)

        # New child with different key — old won't match
        new_child = BaseRenderable(key="new")
        r._component_fn = lambda: new_child
        r._rebuild_component_tree()

        assert calls == ["cleaned"]
        assert r._root._children[0] is new_child
