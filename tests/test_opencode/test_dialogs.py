"""Tests for application dialogs — pickers, help, MCP status, stash, export."""

from __future__ import annotations

import pytest

from opentui.components import Box

from opencode.tui.dialogs.agent import AgentPickerState, agent_picker
from opencode.tui.dialogs.export import ExportDialogState, export_dialog
from opencode.tui.dialogs.help import help_overview
from opencode.tui.dialogs.mcp import McpStatusState, mcp_status_dialog
from opencode.tui.dialogs.model import ModelPickerState, model_picker
from opencode.tui.dialogs.provider import ProviderPickerState, provider_picker
from opencode.tui.dialogs.session import SessionPickerState, session_picker
from opencode.tui.dialogs.stash import StashBrowserState, stash_browser
from opencode.tui.dialogs.theme import ThemePickerState, theme_picker
from opencode.tui.themes import init_theme


@pytest.fixture(autouse=True)
def _theme():
    init_theme("opencode", "dark")


# ---------------------------------------------------------------------------
# Theme picker
# ---------------------------------------------------------------------------


class TestThemePicker:
    def test_renders(self):
        state = ThemePickerState()
        box = theme_picker(state)
        assert isinstance(box, Box)

    def test_type_and_filter(self):
        state = ThemePickerState()
        state.type_char("d")
        state.type_char("r")
        assert state.query == "dr"

    def test_backspace(self):
        state = ThemePickerState()
        state.type_char("a")
        state.backspace()
        assert state.query == ""

    def test_move(self):
        state = ThemePickerState()
        state.move_down(10)
        assert state.selected_index == 1
        state.move_up()
        assert state.selected_index == 0
        state.move_up()
        assert state.selected_index == 0

    def test_confirm(self):
        state = ThemePickerState()
        result = state.confirm()
        # Should return a theme name (first in list)
        assert result is not None

    def test_toggle_mode(self):
        state = ThemePickerState()
        state.toggle_mode()  # dark -> light
        state.toggle_mode()  # light -> dark

    def test_reset(self):
        state = ThemePickerState()
        state.type_char("x")
        state.move_down(5)
        state.reset()
        assert state.query == ""
        assert state.selected_index == 0


# ---------------------------------------------------------------------------
# Model picker
# ---------------------------------------------------------------------------


class TestModelPicker:
    def test_renders(self):
        state = ModelPickerState()
        box = model_picker(state)
        assert isinstance(box, Box)

    def test_with_current_model(self):
        state = ModelPickerState(current_model="gpt-4o")
        box = model_picker(state)
        assert isinstance(box, Box)

    def test_type_filter(self):
        state = ModelPickerState()
        state.type_char("c")
        state.type_char("l")
        items = state._filtered(state.models)
        assert all("cl" in m["label"].lower() for m in items)

    def test_confirm(self):
        state = ModelPickerState()
        result = state.confirm()
        assert result is not None

    def test_custom_models(self):
        custom = [{"label": "my-model", "description": "Custom"}]
        state = ModelPickerState(models=custom)
        assert state.confirm() == "my-model"

    def test_move_and_backspace(self):
        state = ModelPickerState()
        state.move_down(10)
        assert state.selected_index == 1
        state.type_char("x")
        state.backspace()
        assert state.query == ""

    def test_reset(self):
        state = ModelPickerState()
        state.type_char("a")
        state.reset()
        assert state.query == ""


# ---------------------------------------------------------------------------
# Session picker
# ---------------------------------------------------------------------------


class TestSessionPicker:
    def test_renders_empty(self):
        state = SessionPickerState()
        box = session_picker(state)
        assert isinstance(box, Box)

    def test_renders_with_sessions(self):
        sessions = [
            {"id": "s1", "title": "First session"},
            {"id": "s2", "title": "Second session"},
        ]
        state = SessionPickerState(sessions=sessions, active_id="s1")
        box = session_picker(state)
        assert isinstance(box, Box)

    def test_filter(self):
        sessions = [
            {"id": "s1", "title": "Python project"},
            {"id": "s2", "title": "Rust project"},
        ]
        state = SessionPickerState(sessions=sessions)
        state.type_char("p")
        state.type_char("y")
        filtered = state._filtered(state.sessions, key="title")
        assert len(filtered) == 1

    def test_confirm(self):
        sessions = [{"id": "s1", "title": "Test"}]
        state = SessionPickerState(sessions=sessions)
        result = state.confirm()
        assert result == "s1"

    def test_update_sessions(self):
        state = SessionPickerState()
        state.update_sessions([{"id": "s1", "title": "New"}], active_id="s1")
        assert len(state.sessions) == 1
        assert state.active_id == "s1"

    def test_move(self):
        sessions = [{"id": "s1"}, {"id": "s2"}]
        state = SessionPickerState(sessions=sessions)
        state.move_down(2)
        assert state.selected_index == 1
        state.move_up()
        assert state.selected_index == 0


# ---------------------------------------------------------------------------
# Provider picker
# ---------------------------------------------------------------------------


class TestProviderPicker:
    def test_renders(self):
        state = ProviderPickerState()
        box = provider_picker(state)
        assert isinstance(box, Box)

    def test_confirm(self):
        state = ProviderPickerState()
        result = state.confirm()
        assert result == "anthropic"  # first default

    def test_filter(self):
        state = ProviderPickerState()
        state.type_char("o")
        filtered = state._filtered(state.providers)
        assert any("open" in p["label"] for p in filtered)

    def test_custom_providers(self):
        custom = [{"label": "my-api", "description": "Custom API"}]
        state = ProviderPickerState(providers=custom)
        assert state.confirm() == "my-api"

    def test_with_current(self):
        state = ProviderPickerState(current_provider="openai")
        box = provider_picker(state)
        assert isinstance(box, Box)

    def test_reset(self):
        state = ProviderPickerState()
        state.type_char("x")
        state.reset()
        assert state.query == ""


# ---------------------------------------------------------------------------
# Agent picker
# ---------------------------------------------------------------------------


class TestAgentPicker:
    def test_renders(self):
        state = AgentPickerState()
        box = agent_picker(state)
        assert isinstance(box, Box)

    def test_confirm(self):
        state = AgentPickerState()
        result = state.confirm()
        assert result == "coder"

    def test_filter(self):
        state = AgentPickerState()
        state.type_char("r")
        filtered = state._filtered(state.agents)
        assert any("r" in a["label"] for a in filtered)

    def test_custom_agents(self):
        custom = [{"label": "custom-agent", "description": "Test"}]
        state = AgentPickerState(agents=custom)
        assert state.confirm() == "custom-agent"

    def test_reset(self):
        state = AgentPickerState()
        state.type_char("p")
        state.move_down(4)
        state.reset()
        assert state.query == ""
        assert state.selected_index == 0


# ---------------------------------------------------------------------------
# Help dialog
# ---------------------------------------------------------------------------


class TestHelpDialog:
    def test_renders(self):
        box = help_overview()
        assert isinstance(box, Box)

    def test_custom_bindings(self):
        box = help_overview(bindings=[("Ctrl+A", "Select all")])
        assert isinstance(box, Box)


# ---------------------------------------------------------------------------
# MCP status
# ---------------------------------------------------------------------------


class TestMcpStatus:
    def test_empty(self):
        state = McpStatusState()
        box = mcp_status_dialog(state)
        assert isinstance(box, Box)

    def test_with_servers(self):
        servers = [
            {"name": "fs-server", "status": "connected", "tools": ["read", "write"]},
            {"name": "db-server", "status": "disconnected", "tools": []},
        ]
        state = McpStatusState(servers=servers)
        box = mcp_status_dialog(state)
        assert isinstance(box, Box)

    def test_update(self):
        state = McpStatusState()
        state.update([{"name": "test", "status": "connected", "tools": []}])
        assert len(state.servers) == 1


# ---------------------------------------------------------------------------
# Stash browser
# ---------------------------------------------------------------------------


class TestStashBrowser:
    def test_renders_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("opencode.tui.persistence._data_dir", lambda: tmp_path)
        state = StashBrowserState()
        box = stash_browser(state)
        assert isinstance(box, Box)

    def test_renders_with_entries(self, tmp_path, monkeypatch):
        import time

        monkeypatch.setattr("opencode.tui.persistence._data_dir", lambda: tmp_path)
        from opencode.tui.persistence import push_stash

        push_stash("entry 1", label="first")
        push_stash("entry 2")

        state = StashBrowserState()
        assert len(state.entries) == 2
        box = stash_browser(state)
        assert isinstance(box, Box)

    def test_move(self, tmp_path, monkeypatch):
        monkeypatch.setattr("opencode.tui.persistence._data_dir", lambda: tmp_path)
        from opencode.tui.persistence import push_stash

        push_stash("a")
        push_stash("b")

        state = StashBrowserState()
        state.move_down()
        assert state.selected_index == 1
        state.move_up()
        assert state.selected_index == 0

    def test_confirm(self, tmp_path, monkeypatch):
        monkeypatch.setattr("opencode.tui.persistence._data_dir", lambda: tmp_path)
        from opencode.tui.persistence import push_stash

        push_stash("stashed text")

        state = StashBrowserState()
        result = state.confirm()
        assert result == "stashed text"

    def test_confirm_selected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("opencode.tui.persistence._data_dir", lambda: tmp_path)
        from opencode.tui.persistence import push_stash

        push_stash("first")
        push_stash("second")

        state = StashBrowserState()
        result = state.confirm_selected()
        assert result in ("first", "second")


# ---------------------------------------------------------------------------
# Export dialog
# ---------------------------------------------------------------------------


class TestExportDialog:
    def test_renders(self):
        state = ExportDialogState()
        box = export_dialog(state)
        assert isinstance(box, Box)

    def test_move(self):
        state = ExportDialogState()
        state.move_down(4)
        assert state.selected_index == 1
        state.move_up()
        assert state.selected_index == 0

    def test_confirm(self):
        state = ExportDialogState()
        result = state.confirm()
        assert result == "Markdown"

    def test_confirm_json(self):
        state = ExportDialogState()
        state.move_down(4)
        result = state.confirm()
        assert result == "JSON"

    def test_reset(self):
        state = ExportDialogState()
        state.move_down(4)
        state.reset()
        assert state.selected_index == 0


# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------


class TestDialogsPackage:
    def test_imports(self):
        from opencode.tui.dialogs import (
            AgentPickerState,
            ExportDialogState,
            McpStatusState,
            ModelPickerState,
            ProviderPickerState,
            SessionPickerState,
            StashBrowserState,
            ThemePickerState,
            agent_picker,
            export_dialog,
            help_overview,
            mcp_status_dialog,
            model_picker,
            provider_picker,
            session_picker,
            stash_browser,
            theme_picker,
        )
        # All imports succeed
        assert ThemePickerState is not None
