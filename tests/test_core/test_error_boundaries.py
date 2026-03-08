"""Tests for error boundaries in the render loop."""

import logging

from opentui.components.base import BaseRenderable
from opentui.renderer import CliRenderer, CliRendererConfig, RootRenderable

from .conftest import FakeNative


def _make_renderer() -> CliRenderer:
    config = CliRendererConfig(width=80, height=24, testing=True)
    r = CliRenderer(1, config, FakeNative())
    r._root = RootRenderable(r)
    return r


class TestErrorBoundaries:
    def test_rebuild_restores_on_error(self):
        """When component_fn raises, old children are restored."""
        r = _make_renderer()
        child = BaseRenderable()
        r._root.add(child)

        def bad_component():
            raise ValueError("boom")

        r._component_fn = bad_component
        r._rebuild_component_tree()

        # Old children should be restored
        assert len(r._root._children) == 1
        assert r._root._children[0] is child
        assert child._parent is r._root

    def test_rebuild_succeeds_normally(self):
        """Normal rebuild updates tree via reconciliation."""
        r = _make_renderer()
        old_child = BaseRenderable()
        r._root.add(old_child)

        new_child = BaseRenderable()

        def good_component():
            return new_child

        r._component_fn = good_component
        r._rebuild_component_tree()

        # Reconciler matches old to new (same type, no key) — old identity preserved
        assert len(r._root._children) == 1

    def test_rebuild_error_logged(self, caplog):
        """Errors during rebuild are logged."""
        r = _make_renderer()

        def bad_component():
            raise RuntimeError("component error")

        r._component_fn = bad_component

        with caplog.at_level(logging.ERROR):
            r._rebuild_component_tree()

        assert any("Error rebuilding component tree" in msg for msg in caplog.messages)
