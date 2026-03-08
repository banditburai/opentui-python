"""Tests for keybinding system — leader keys, contexts, config parsing."""

from __future__ import annotations

import time

import pytest

from opentui.events import KeyEvent

from opencode.tui.keybindings import (
    LEADER_TIMEOUT,
    KeyContext,
    Keybinding,
    KeybindingRegistry,
    LeaderKeyState,
    default_keybindings,
    get_leader,
    parse_key_combo,
)


def _key(key: str, ctrl: bool = False, shift: bool = False, alt: bool = False, meta: bool = False) -> KeyEvent:
    return KeyEvent(key=key, ctrl=ctrl, shift=shift, alt=alt, meta=meta)


# ---------------------------------------------------------------------------
# Keybinding matching
# ---------------------------------------------------------------------------


class TestKeybinding:
    def test_simple_match(self):
        kb = Keybinding(key="k", ctrl=True, action="test")
        assert kb.matches(_key("k", ctrl=True))

    def test_no_match_wrong_key(self):
        kb = Keybinding(key="k", ctrl=True, action="test")
        assert not kb.matches(_key("j", ctrl=True))

    def test_no_match_wrong_modifier(self):
        kb = Keybinding(key="k", ctrl=True, action="test")
        assert not kb.matches(_key("k"))

    def test_case_insensitive(self):
        kb = Keybinding(key="K", ctrl=True, action="test")
        assert kb.matches(_key("k", ctrl=True))

    def test_leader_requires_active(self):
        kb = Keybinding(key="t", leader=True, action="pick_theme")
        assert not kb.matches(_key("t"), leader_active=False)
        assert kb.matches(_key("t"), leader_active=True)

    def test_display_simple(self):
        kb = Keybinding(key="k", ctrl=True, action="test")
        assert kb.display == "Ctrl+K"

    def test_display_leader(self):
        kb = Keybinding(key="t", leader=True, action="pick_theme")
        assert kb.display == "Ctrl+X+T"

    def test_display_shift(self):
        kb = Keybinding(key="k", ctrl=True, shift=True, action="test")
        assert kb.display == "Ctrl+Shift+K"


# ---------------------------------------------------------------------------
# Leader key state
# ---------------------------------------------------------------------------


class TestLeaderKeyState:
    def test_initial_state(self):
        leader = LeaderKeyState()
        assert not leader.active
        assert leader.expired

    def test_activate_deactivate(self):
        leader = LeaderKeyState()
        leader.activate()
        assert leader.active
        assert not leader.expired
        leader.deactivate()
        assert not leader.active

    def test_timeout(self):
        leader = LeaderKeyState()
        leader.activate()
        leader._activated_at = time.monotonic() - LEADER_TIMEOUT - 0.1
        assert leader.expired

    def test_check_and_consume(self):
        leader = LeaderKeyState()
        leader.activate()
        assert leader.check_and_consume()
        assert not leader.active

    def test_check_and_consume_expired(self):
        leader = LeaderKeyState()
        leader.activate()
        leader._activated_at = time.monotonic() - LEADER_TIMEOUT - 0.1
        assert not leader.check_and_consume()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestKeybindingRegistry:
    def test_register_and_resolve(self):
        reg = KeybindingRegistry()
        reg.register(Keybinding(key="k", ctrl=True, action="test"))
        assert reg.resolve(_key("k", ctrl=True)) == "test"

    def test_resolve_no_match(self):
        reg = KeybindingRegistry()
        assert reg.resolve(_key("z")) is None

    def test_unregister(self):
        reg = KeybindingRegistry()
        reg.register(Keybinding(key="k", ctrl=True, action="test"))
        reg.unregister("test")
        assert reg.resolve(_key("k", ctrl=True)) is None

    def test_list_all(self):
        reg = default_keybindings()
        all_bindings = reg.list()
        assert len(all_bindings) > 10

    def test_list_by_context(self):
        reg = default_keybindings()
        global_bindings = reg.list(KeyContext.GLOBAL)
        prompt_bindings = reg.list(KeyContext.PROMPT)
        assert len(global_bindings) > 0
        assert len(prompt_bindings) > 0

    def test_context_isolation(self):
        reg = KeybindingRegistry()
        reg.register(Keybinding(key="a", ctrl=True, action="global_a", context=KeyContext.GLOBAL))
        reg.register(Keybinding(key="a", ctrl=True, action="prompt_a", context=KeyContext.PROMPT))
        # In global context, should get global_a
        assert reg.resolve(_key("a", ctrl=True), context=KeyContext.GLOBAL) == "global_a"


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


class TestParseKeyCombo:
    def test_simple(self):
        result = parse_key_combo("ctrl+k")
        assert result["key"] == "k"
        assert result["ctrl"] is True

    def test_multi_modifier(self):
        result = parse_key_combo("ctrl+shift+k")
        assert result["key"] == "k"
        assert result["ctrl"] is True
        assert result["shift"] is True

    def test_leader(self):
        result = parse_key_combo("leader+t")
        assert result["key"] == "t"
        assert result["leader"] is True

    def test_no_modifier(self):
        result = parse_key_combo("escape")
        assert result["key"] == "escape"
        assert result["ctrl"] is False


# ---------------------------------------------------------------------------
# Default bindings
# ---------------------------------------------------------------------------


class TestDefaultKeybindings:
    def test_has_command_palette(self):
        reg = default_keybindings()
        assert reg.resolve(_key("k", ctrl=True)) == "command_palette"

    def test_has_new_session(self):
        reg = default_keybindings()
        assert reg.resolve(_key("n", ctrl=True)) == "new_session"

    def test_has_toggle_sidebar(self):
        reg = default_keybindings()
        assert reg.resolve(_key("b", ctrl=True)) == "toggle_sidebar"

    def test_has_leader_key(self):
        reg = default_keybindings()
        assert reg.resolve(_key("x", ctrl=True)) == "leader"

    def test_has_leader_sequences(self):
        reg = default_keybindings()
        leader = get_leader()
        leader.activate()
        result = reg.resolve(_key("t"), context=KeyContext.GLOBAL)
        assert result == "pick_theme"
        leader.deactivate()

    def test_has_prompt_bindings(self):
        reg = default_keybindings()
        result = reg.resolve(_key("a", ctrl=True), context=KeyContext.PROMPT)
        assert result is not None

    def test_prompt_context_overrides_global(self):
        """PROMPT Ctrl+K (kill_line) takes priority over GLOBAL Ctrl+K (command_palette)."""
        reg = default_keybindings()
        # In GLOBAL context: Ctrl+K → command_palette
        assert reg.resolve(_key("k", ctrl=True), context=KeyContext.GLOBAL) == "command_palette"
        # In PROMPT context: Ctrl+K → kill_line (overrides GLOBAL)
        assert reg.resolve(_key("k", ctrl=True), context=KeyContext.PROMPT) == "kill_line"
