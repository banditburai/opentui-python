"""Configurable keybinding system for the TUI."""

from __future__ import annotations

from dataclasses import dataclass

from opentui.events import KeyEvent


@dataclass(frozen=True)
class Keybinding:
    """A single keybinding mapping a key combo to an action name."""

    key: str
    action: str
    description: str = ""
    ctrl: bool = False
    shift: bool = False
    alt: bool = False
    meta: bool = False

    def matches(self, event: KeyEvent) -> bool:
        """Check if a KeyEvent matches this keybinding."""
        return (
            event.key.lower() == self.key.lower()
            and event.ctrl == self.ctrl
            and event.shift == self.shift
            and event.alt == self.alt
            and event.meta == self.meta
        )


class KeybindingRegistry:
    """Registry of keybindings, resolving KeyEvents to action names."""

    def __init__(self) -> None:
        self._bindings: list[Keybinding] = []

    def register(self, binding: Keybinding) -> None:
        """Add a keybinding."""
        self._bindings.append(binding)

    def unregister(self, action: str) -> None:
        """Remove all keybindings for a given action."""
        self._bindings = [b for b in self._bindings if b.action != action]

    def list(self) -> list[Keybinding]:
        """Return all registered keybindings."""
        return list(self._bindings)

    def resolve(self, event: KeyEvent) -> str | None:
        """Return the action name for a KeyEvent, or None if no match."""
        for binding in self._bindings:
            if binding.matches(event):
                return binding.action
        return None


def default_keybindings() -> KeybindingRegistry:
    """Create a registry with the default OpenCode keybindings."""
    reg = KeybindingRegistry()
    for kb in [
        Keybinding(key="k", ctrl=True, action="command_palette", description="Open command palette"),
        Keybinding(key="n", ctrl=True, action="new_session", description="New session"),
        Keybinding(key="l", ctrl=True, action="clear", description="Clear screen"),
        Keybinding(key="b", ctrl=True, action="toggle_sidebar", description="Toggle sidebar"),
        Keybinding(key="escape", action="close_overlay", description="Close overlay"),
        Keybinding(key="tab", action="switch_pane", description="Switch pane"),
    ]:
        reg.register(kb)
    return reg
