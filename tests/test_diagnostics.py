"""Tests for the diagnostics module."""

from __future__ import annotations

import logging

import pytest

from opentui import diagnostics
from opentui.diagnostics import (
    ALL,
    DIRTY,
    LAYOUT,
    RESIZE,
    VISIBILITY,
    disable_diagnostics,
    enable_diagnostics,
)


@pytest.fixture(autouse=True)
def _reset_diagnostics():
    """Ensure diagnostics are off and handlers cleaned up."""
    diagnostics._enabled = 0
    yield
    diagnostics._enabled = 0
    diagnostics._log_file_path = None
    for h in diagnostics._log.handlers[:]:
        h.close()
        diagnostics._log.removeHandler(h)


# ---------------------------------------------------------------------------
# Fake node helpers
# ---------------------------------------------------------------------------


def _make_node(name="Box", node_id="", parent=None):
    class _FakeNode:
        pass

    _FakeNode.__name__ = name
    n = _FakeNode()
    n._id = node_id
    n._parent = parent
    n._min_width = None
    n._min_height = None
    return n


# ---------------------------------------------------------------------------
# Enable / Disable
# ---------------------------------------------------------------------------


class TestEnableDisable:
    def test_enable_single_category(self):
        enable_diagnostics("resize")
        assert diagnostics._enabled == RESIZE

    def test_enable_multiple_categories(self):
        enable_diagnostics("resize", "layout", "visibility")
        assert diagnostics._enabled == (RESIZE | LAYOUT | VISIBILITY)

    def test_enable_all(self):
        enable_diagnostics("all")
        assert diagnostics._enabled == ALL

    def test_disable(self):
        enable_diagnostics("all")
        disable_diagnostics()
        assert diagnostics._enabled == 0

    def test_case_insensitive(self):
        enable_diagnostics("RESIZE", "Layout")
        assert diagnostics._enabled == (RESIZE | LAYOUT)

    def test_unknown_category_raises(self):
        with pytest.raises(ValueError, match="Unknown diagnostics category"):
            enable_diagnostics("bogus")

    def test_additive_by_default(self):
        """Successive calls OR with existing categories."""
        enable_diagnostics("resize")
        enable_diagnostics("layout")
        assert diagnostics._enabled == (RESIZE | LAYOUT)

    def test_replace_mode(self):
        """replace=True starts fresh."""
        enable_diagnostics("resize", "layout")
        enable_diagnostics("dirty", replace=True)
        assert diagnostics._enabled == DIRTY


# ---------------------------------------------------------------------------
# Env init
# ---------------------------------------------------------------------------


class TestInitFromEnv:
    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("OPENTUI_DEBUG", "layout,resize")
        diagnostics._init_from_env()
        assert diagnostics._enabled == (LAYOUT | RESIZE)

    def test_empty_env_var(self, monkeypatch):
        monkeypatch.setenv("OPENTUI_DEBUG", "")
        diagnostics._init_from_env()
        assert diagnostics._enabled == 0

    def test_unset_env_var(self, monkeypatch):
        monkeypatch.delenv("OPENTUI_DEBUG", raising=False)
        diagnostics._init_from_env()
        assert diagnostics._enabled == 0


# ---------------------------------------------------------------------------
# Auto-handler
# ---------------------------------------------------------------------------


class TestAutoHandler:
    def test_file_handler_attached_on_enable(self, tmp_path, monkeypatch):
        """enable_diagnostics creates a log file."""
        diagnostics._log.handlers.clear()
        diagnostics._log_file_path = None
        log_path = str(tmp_path / "test-debug.log")
        monkeypatch.setenv("OPENTUI_DEBUG_LOG", log_path)
        enable_diagnostics("resize")
        assert len(diagnostics._log.handlers) >= 1
        assert isinstance(diagnostics._log.handlers[0], logging.FileHandler)
        assert diagnostics._log_file_path == log_path
        # Clean up handler so it doesn't hold file open
        for h in diagnostics._log.handlers[:]:
            h.close()
            diagnostics._log.removeHandler(h)

    def test_no_duplicate_handlers(self, tmp_path, monkeypatch):
        """Calling enable_diagnostics twice doesn't double handlers."""
        diagnostics._log.handlers.clear()
        diagnostics._log_file_path = None
        monkeypatch.setenv("OPENTUI_DEBUG_LOG", str(tmp_path / "test-debug.log"))
        enable_diagnostics("resize")
        count = len(diagnostics._log.handlers)
        enable_diagnostics("layout")
        assert len(diagnostics._log.handlers) == count
        for h in diagnostics._log.handlers[:]:
            h.close()
            diagnostics._log.removeHandler(h)

    def test_log_content_written_to_file(self, tmp_path, monkeypatch):
        """Diagnostics actually write to the log file."""
        diagnostics._log.handlers.clear()
        diagnostics._log_file_path = None
        log_path = tmp_path / "test-debug.log"
        monkeypatch.setenv("OPENTUI_DEBUG_LOG", str(log_path))
        enable_diagnostics("resize")
        diagnostics.log_resize(80, 24, 120, 40)
        # Flush handlers
        for h in diagnostics._log.handlers:
            h.flush()
        content = log_path.read_text()
        assert "resize: 80x24 -> 120x40" in content
        for h in diagnostics._log.handlers[:]:
            h.close()
            diagnostics._log.removeHandler(h)

    def test_get_log_file_path(self, tmp_path, monkeypatch):
        diagnostics._log.handlers.clear()
        diagnostics._log_file_path = None
        log_path = str(tmp_path / "test-debug.log")
        monkeypatch.setenv("OPENTUI_DEBUG_LOG", log_path)
        assert diagnostics.get_log_file_path() is None
        enable_diagnostics("layout")
        assert diagnostics.get_log_file_path() == log_path
        for h in diagnostics._log.handlers[:]:
            h.close()
            diagnostics._log.removeHandler(h)


# ---------------------------------------------------------------------------
# Resize
# ---------------------------------------------------------------------------


class TestLogResize:
    def test_emits_debug_log(self, caplog):
        enable_diagnostics("resize")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_resize(120, 40, 100, 30)
        assert "resize: 120x40 -> 100x30" in caplog.text


# ---------------------------------------------------------------------------
# Layout facts
# ---------------------------------------------------------------------------


class TestLogLayoutFacts:
    def test_size_change_logged(self, caplog):
        enable_diagnostics("layout")
        node = _make_node("Sidebar", "sb")
        # fact layout: (node, parent_id, has_children, _, old_x, old_y, old_w, old_h, new_x, new_y, new_w, new_h)
        fact = (node, 0, False, False, 0, 0, 24, 30, 0, 0, 30, 40)
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_layout_facts([fact])
        assert "Sidebar#sb" in caplog.text
        assert "30x40" in caplog.text
        assert "24x30" in caplog.text

    def test_collapse_to_zero_warns(self, caplog):
        enable_diagnostics("layout")
        node = _make_node("HelpPanel")
        # fact layout: (node, parent_id, has_children, _, old_x, old_y, old_w, old_h, new_x, new_y, new_w, new_h)
        fact = (node, 0, False, False, 100, 5, 20, 10, 0, 0, 0, 0)
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_layout_facts([fact])
        assert "collapsed to zero" in caplog.text

    def test_no_change_no_log(self, caplog):
        enable_diagnostics("layout")
        node = _make_node("Static")
        fact = (node, 0, False, False, 5, 5, 10, 10, 5, 5, 10, 10)
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_layout_facts([fact])
        assert "Static" not in caplog.text

    def test_min_constraint_violation_warns(self, caplog):
        enable_diagnostics("layout")
        node = _make_node("StatusLine")
        node._min_height = 3
        # old_h=3, new_h=1 → new_h > 0 but < min_height=3 → constraint warning
        # fact layout: (node, parent_id, has_children, _, old_x, old_y, old_w, old_h, new_x, new_y, new_w, new_h)
        fact = (node, 0, False, False, 0, 0, 80, 3, 0, 0, 80, 1)
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_layout_facts([fact])
        assert "min_height=3" in caplog.text
        assert "constraint overridden" in caplog.text

    def test_percentage_min_width_no_crash(self, caplog):
        """Percentage string min_width/min_height must not crash."""
        enable_diagnostics("layout")
        node = _make_node("FlexBox")
        node._min_width = "50%"
        fact = (node, 0, False, False, 0, 0, 10, 10, 0, 0, 20, 20)
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_layout_facts([fact])  # must not raise TypeError
        # Should still log the size change
        assert "FlexBox" in caplog.text

    def test_none_facts_no_crash(self):
        enable_diagnostics("layout")
        diagnostics.log_layout_facts(None)  # should not raise


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


class TestLogVisibility:
    def test_visibility_change_logged(self, caplog):
        enable_diagnostics("visibility")
        node = _make_node("Tooltip", "tip")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_visibility_change(node, True, False)
        assert "Tooltip#tip" in caplog.text
        assert "True -> False" in caplog.text


# ---------------------------------------------------------------------------
# Show
# ---------------------------------------------------------------------------


class TestLogShowBranch:
    def test_show_branch_logged(self, caplog):
        enable_diagnostics("visibility")
        node = _make_node("Show")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_show_branch(node, False, "render", "fallback", True)
        assert 'branch="render"->"fallback"' in caplog.text
        assert "(cached)" in caplog.text

    def test_show_branch_not_cached(self, caplog):
        enable_diagnostics("visibility")
        node = _make_node("Show")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_show_branch(node, True, "none", "render", False)
        assert "(cached)" not in caplog.text


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------


class TestLogSwitchBranch:
    def test_switch_branch_logged(self, caplog):
        enable_diagnostics("visibility")
        node = _make_node("Switch", "tabs")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_switch_branch(node, ("tab2",), ("tab1",), False)
        assert "Switch#tabs" in caplog.text
        assert "('tab1',)" in caplog.text
        assert "('tab2',)" in caplog.text


# ---------------------------------------------------------------------------
# For
# ---------------------------------------------------------------------------


class TestLogForReconcile:
    def test_for_reconcile_logged(self, caplog):
        enable_diagnostics("visibility")
        node = _make_node("For", "items")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_for_reconcile(node, 5, 3)
        assert "For#items" in caplog.text
        assert "items 5 -> 3" in caplog.text

    def test_for_empty_list(self, caplog):
        enable_diagnostics("visibility")
        node = _make_node("For")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_for_reconcile(node, 0, 0)
        assert "items 0 -> 0" in caplog.text


# ---------------------------------------------------------------------------
# Dirty
# ---------------------------------------------------------------------------


class TestLogDirty:
    def test_dirty_layout_logged(self, caplog):
        enable_diagnostics("dirty")
        node = _make_node("Box", "main")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_dirty(node, "layout")
        assert "Box#main" in caplog.text
        assert "layout" in caplog.text

    def test_dirty_paint_logged(self, caplog):
        enable_diagnostics("dirty")
        node = _make_node("Text")
        with caplog.at_level(logging.DEBUG, logger="opentui.diagnostics"):
            diagnostics.log_dirty(node, "paint")
        assert "Text" in caplog.text
        assert "paint" in caplog.text


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


class TestGating:
    def test_bitmask_independent(self):
        enable_diagnostics("resize")
        assert diagnostics._enabled & RESIZE
        assert not (diagnostics._enabled & LAYOUT)
        assert not (diagnostics._enabled & VISIBILITY)
        assert not (diagnostics._enabled & DIRTY)


# ---------------------------------------------------------------------------
# Node label
# ---------------------------------------------------------------------------


class TestNodeLabel:
    def test_with_id(self):
        assert diagnostics._node_label(_make_node("Box", "main")) == "Box#main"

    def test_without_id(self):
        assert diagnostics._node_label(_make_node("Box")) == "Box"

    def test_no_id_attr(self):
        class _Bare:
            pass

        _Bare.__name__ = "Bare"
        assert diagnostics._node_label(_Bare()) == "Bare"

    def test_parent_path(self):
        """Labels include ancestor path up to depth=2."""
        root = _make_node("App", "app")
        mid = _make_node("Row", "header", parent=root)
        leaf = _make_node("Text", "title", parent=mid)
        label = diagnostics._node_label(leaf)
        assert "App#app" in label
        assert "Row#header" in label
        assert "Text#title" in label
        # Should read left-to-right as ancestor > ... > node
        assert label.index("App#app") < label.index("Row#header") < label.index("Text#title")

    def test_shallow_tree(self):
        """Nodes with no parent just show themselves."""
        node = _make_node("Box", "solo")
        assert diagnostics._node_label(node) == "Box#solo"
