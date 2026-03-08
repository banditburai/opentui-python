"""Tests for command registry, command palette, prompt, autocomplete, and persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from opentui.components import Box
from opentui.events import KeyEvent

from opencode.tui.autocomplete import AutocompleteState, CompletionItem
from opencode.tui.commands import Command, CommandRegistry, default_commands
from opencode.tui.components.command_palette import CommandPaletteState, command_palette
from opencode.tui.components.prompt import PromptState, prompt_box
from opencode.tui.persistence import (
    append_history,
    load_history,
    load_stash,
    pop_stash,
    push_stash,
    save_history,
)
from opencode.tui.themes import init_theme


@pytest.fixture(autouse=True)
def _theme():
    init_theme("opencode", "dark")


def _key(key: str, ctrl: bool = False, shift: bool = False, alt: bool = False) -> KeyEvent:
    return KeyEvent(key=key, ctrl=ctrl, shift=shift, alt=alt, meta=False)


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------


class TestCommandRegistry:
    def test_register_and_get(self):
        reg = CommandRegistry()
        cmd = Command(id="test", name="Test", description="A test command")
        reg.register(cmd)
        assert reg.get("test") == cmd

    def test_unregister(self):
        reg = CommandRegistry()
        reg.register(Command(id="test", name="Test"))
        reg.unregister("test")
        assert reg.get("test") is None

    def test_list_sorted(self):
        reg = CommandRegistry()
        reg.register(Command(id="b", name="Beta", category="Z"))
        reg.register(Command(id="a", name="Alpha", category="A"))
        cmds = reg.list()
        assert cmds[0].name == "Alpha"

    def test_list_by_category(self):
        reg = CommandRegistry()
        reg.register(Command(id="a", name="A", category="Cat1"))
        reg.register(Command(id="b", name="B", category="Cat2"))
        assert len(reg.list("Cat1")) == 1

    def test_categories(self):
        reg = CommandRegistry()
        reg.register(Command(id="a", name="A", category="Settings"))
        reg.register(Command(id="b", name="B", category="Session"))
        cats = reg.categories()
        assert "Settings" in cats
        assert "Session" in cats

    def test_to_dialog_items(self):
        reg = CommandRegistry()
        reg.register(Command(id="a", name="Test", description="Desc", keybinding="Ctrl+T"))
        items = reg.to_dialog_items()
        assert len(items) == 1
        assert items[0]["label"] == "Test"
        assert items[0]["keybinding"] == "Ctrl+T"

    def test_default_commands(self):
        reg = default_commands()
        cmds = reg.list()
        assert len(cmds) >= 10
        assert reg.get("new_session") is not None
        assert reg.get("change_theme") is not None


# ---------------------------------------------------------------------------
# Command palette
# ---------------------------------------------------------------------------


class TestCommandPalette:
    def test_renders_box(self):
        state = CommandPaletteState()
        d = command_palette(state)
        assert isinstance(d, Box)

    def test_type_and_backspace(self):
        state = CommandPaletteState()
        state.type_char("t")
        state.type_char("h")
        assert state.query == "th"
        state.backspace()
        assert state.query == "t"

    def test_move_selection(self):
        state = CommandPaletteState()
        state.move_down(10)
        assert state.selected_index == 1
        state.move_up()
        assert state.selected_index == 0
        state.move_up()
        assert state.selected_index == 0  # can't go below 0

    def test_reset(self):
        state = CommandPaletteState()
        state.type_char("x")
        state.move_down(5)
        state.reset()
        assert state.query == ""
        assert state.selected_index == 0


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


class TestPromptState:
    def test_insert(self):
        s = PromptState()
        s.insert("hello")
        assert s.text == "hello"
        assert s.cursor == 5

    def test_cursor_movement(self):
        s = PromptState()
        s.insert("hello world")
        s.cursor = 5
        s.cursor_forward()
        assert s.cursor == 6
        s.cursor_backward()
        assert s.cursor == 5

    def test_cursor_home_end(self):
        s = PromptState()
        s.insert("hello")
        s.cursor_home()
        assert s.cursor == 0
        s.cursor_end()
        assert s.cursor == 5

    def test_word_movement(self):
        s = PromptState()
        s.insert("hello world test")
        s.cursor = 6  # at 'w'
        s.cursor_word_forward()
        assert s.cursor > 6
        s.cursor_word_backward()
        assert s.cursor <= 6

    def test_delete_and_backspace(self):
        s = PromptState()
        s.insert("hello")
        s.cursor = 3
        s.delete_char()
        assert s.text == "helo"
        s.backspace()
        assert s.text == "heo"
        assert s.cursor == 2

    def test_kill_line(self):
        s = PromptState()
        s.insert("hello world")
        s.cursor = 5
        s.kill_line()
        assert s.text == "hello"

    def test_kill_line_back(self):
        s = PromptState()
        s.insert("hello world")
        s.cursor = 5
        s.kill_line_back()
        assert s.text == " world"
        assert s.cursor == 0

    def test_kill_word_back(self):
        s = PromptState()
        s.insert("hello world")
        s.cursor = 11
        s.kill_word_back()
        assert "hello" in s.text

    def test_submit(self):
        s = PromptState()
        s.insert("test")
        result = s.submit()
        assert result == "test"
        assert s.text == ""
        assert s.cursor == 0
        assert "test" in s.history

    def test_history(self):
        s = PromptState()
        s.insert("first")
        s.submit()
        s.insert("second")
        s.submit()
        s.history_up()
        assert s.text == "second"
        s.history_up()
        assert s.text == "first"
        s.history_down()
        assert s.text == "second"

    def test_shell_mode(self):
        s = PromptState()
        s.handle_key(_key("!"))
        assert s.mode == "shell"
        assert s.text == "!"

    def test_handle_key_enter(self):
        submitted = []
        s = PromptState()
        s.on_submit = submitted.append
        s.insert("hello")
        s.handle_key(_key("return"))
        assert submitted == ["hello"]

    def test_handle_key_shift_enter(self):
        s = PromptState()
        s.insert("line1")
        s.handle_key(_key("return", shift=True))
        assert "\n" in s.text

    def test_handle_key_ctrl_c(self):
        s = PromptState()
        s.insert("hello")
        s.handle_key(_key("c", ctrl=True))
        assert s.text == ""


class TestPromptBox:
    def test_renders(self):
        s = PromptState()
        box = prompt_box(state=s, placeholder="Type...")
        assert isinstance(box, Box)

    def test_renders_with_text(self):
        s = PromptState()
        s.insert("hello")
        box = prompt_box(state=s)
        assert isinstance(box, Box)


# ---------------------------------------------------------------------------
# Autocomplete
# ---------------------------------------------------------------------------


class TestAutocomplete:
    def test_initial_state(self):
        ac = AutocompleteState()
        assert not ac.active

    def test_activate(self):
        ac = AutocompleteState()
        ac.activate("@")
        assert ac.active
        assert ac.trigger == "@"

    def test_reset(self):
        ac = AutocompleteState()
        ac.activate("@", "test")
        ac.reset()
        assert not ac.active
        assert ac.query == ""

    def test_command_completions(self):
        ac = AutocompleteState()
        ac.activate("/")
        assert len(ac.items) > 0
        assert all(i.kind == "command" for i in ac.items)

    def test_command_filter(self):
        ac = AutocompleteState()
        ac.activate("/", "hel")
        assert any("help" in i.text for i in ac.items)

    def test_move_selection(self):
        ac = AutocompleteState()
        ac.activate("/")
        ac.move_down()
        assert ac.selected_index == 1
        ac.move_up()
        assert ac.selected_index == 0

    def test_confirm(self):
        ac = AutocompleteState()
        ac.activate("/")
        item = ac.confirm()
        assert not ac.active
        assert item is not None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_history_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "opencode.tui.persistence._data_dir",
            lambda: tmp_path,
        )
        save_history(["one", "two", "three"])
        loaded = load_history()
        assert loaded == ["one", "two", "three"]

    def test_append_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "opencode.tui.persistence._data_dir",
            lambda: tmp_path,
        )
        append_history("first")
        append_history("second")
        loaded = load_history()
        assert loaded == ["first", "second"]

    def test_history_max_entries(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "opencode.tui.persistence._data_dir",
            lambda: tmp_path,
        )
        entries = [f"entry-{i}" for i in range(100)]
        save_history(entries)
        loaded = load_history()
        assert len(loaded) <= 50

    def test_stash_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "opencode.tui.persistence._data_dir",
            lambda: tmp_path,
        )
        push_stash("stashed text", label="test")
        entries = load_stash()
        assert len(entries) == 1
        assert entries[0]["text"] == "stashed text"

    def test_pop_stash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "opencode.tui.persistence._data_dir",
            lambda: tmp_path,
        )
        push_stash("item1")
        push_stash("item2")
        popped = pop_stash()
        assert popped is not None
        assert popped["text"] == "item2"
        remaining = load_stash()
        assert len(remaining) == 1

    def test_pop_empty_stash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "opencode.tui.persistence._data_dir",
            lambda: tmp_path,
        )
        assert pop_stash() is None
