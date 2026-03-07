"""Tests for the keybindings system."""

from opentui.events import KeyEvent

from opencode.tui.keybindings import (
    Keybinding,
    KeybindingRegistry,
    default_keybindings,
)


# --- Keybinding ---


class TestKeybinding:
    def test_fields(self):
        kb = Keybinding(key="k", ctrl=True, action="command_palette", description="Open command palette")
        assert kb.key == "k"
        assert kb.ctrl is True
        assert kb.action == "command_palette"

    def test_matches_event(self):
        kb = Keybinding(key="k", ctrl=True, action="command_palette")
        event = KeyEvent(key="k", ctrl=True)
        assert kb.matches(event)

    def test_no_match_wrong_key(self):
        kb = Keybinding(key="k", ctrl=True, action="command_palette")
        event = KeyEvent(key="j", ctrl=True)
        assert not kb.matches(event)

    def test_no_match_missing_modifier(self):
        kb = Keybinding(key="k", ctrl=True, action="command_palette")
        event = KeyEvent(key="k", ctrl=False)
        assert not kb.matches(event)

    def test_match_with_shift(self):
        kb = Keybinding(key="n", ctrl=True, shift=True, action="new")
        event = KeyEvent(key="n", ctrl=True, shift=True)
        assert kb.matches(event)

    def test_no_match_extra_modifier(self):
        kb = Keybinding(key="n", ctrl=True, action="new")
        event = KeyEvent(key="n", ctrl=True, alt=True)
        assert not kb.matches(event)

    def test_plain_key_match(self):
        kb = Keybinding(key="escape", action="close_overlay")
        event = KeyEvent(key="escape")
        assert kb.matches(event)


# --- KeybindingRegistry ---


class TestKeybindingRegistry:
    def test_register_and_list(self):
        reg = KeybindingRegistry()
        kb = Keybinding(key="k", ctrl=True, action="cmd_palette")
        reg.register(kb)
        assert kb in reg.list()

    def test_resolve_returns_action(self):
        reg = KeybindingRegistry()
        reg.register(Keybinding(key="k", ctrl=True, action="cmd_palette"))
        event = KeyEvent(key="k", ctrl=True)
        assert reg.resolve(event) == "cmd_palette"

    def test_resolve_returns_none_for_unknown(self):
        reg = KeybindingRegistry()
        reg.register(Keybinding(key="k", ctrl=True, action="cmd_palette"))
        event = KeyEvent(key="j", ctrl=True)
        assert reg.resolve(event) is None

    def test_first_match_wins(self):
        reg = KeybindingRegistry()
        reg.register(Keybinding(key="k", ctrl=True, action="first"))
        reg.register(Keybinding(key="k", ctrl=True, action="second"))
        event = KeyEvent(key="k", ctrl=True)
        assert reg.resolve(event) == "first"

    def test_unregister(self):
        reg = KeybindingRegistry()
        kb = Keybinding(key="k", ctrl=True, action="cmd")
        reg.register(kb)
        reg.unregister("cmd")
        assert reg.resolve(KeyEvent(key="k", ctrl=True)) is None

    def test_unregister_nonexistent_is_safe(self):
        reg = KeybindingRegistry()
        reg.unregister("nonexistent")  # should not raise


# --- Default keybindings ---


class TestDefaultKeybindings:
    def test_returns_registry(self):
        reg = default_keybindings()
        assert isinstance(reg, KeybindingRegistry)

    def test_has_command_palette(self):
        reg = default_keybindings()
        event = KeyEvent(key="k", ctrl=True)
        assert reg.resolve(event) == "command_palette"

    def test_has_new_session(self):
        reg = default_keybindings()
        event = KeyEvent(key="n", ctrl=True)
        assert reg.resolve(event) == "new_session"

    def test_has_clear(self):
        reg = default_keybindings()
        event = KeyEvent(key="l", ctrl=True)
        assert reg.resolve(event) == "clear"

    def test_has_escape(self):
        reg = default_keybindings()
        event = KeyEvent(key="escape")
        assert reg.resolve(event) == "close_overlay"
