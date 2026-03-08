"""Tests for keybinding frozen dataclass."""

import pytest
from dataclasses import FrozenInstanceError

from opencode.tui.keybindings import Keybinding


class TestKeybindingFrozen:
    def test_is_frozen(self):
        kb = Keybinding(key="k", action="test")
        with pytest.raises(FrozenInstanceError):
            kb.key = "j"

    def test_cannot_mutate_action(self):
        kb = Keybinding(key="k", action="test")
        with pytest.raises(FrozenInstanceError):
            kb.action = "other"

    def test_cannot_mutate_ctrl(self):
        kb = Keybinding(key="k", action="test", ctrl=True)
        with pytest.raises(FrozenInstanceError):
            kb.ctrl = False
