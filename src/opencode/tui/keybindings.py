"""Configurable keybinding system — leader keys, contexts, and full binding set."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from opentui.events import KeyEvent


# ---------------------------------------------------------------------------
# Keybinding context — determines which bindings are active
# ---------------------------------------------------------------------------


class KeyContext(Enum):
    """Context determines which keybindings are active."""

    GLOBAL = "global"
    PROMPT = "prompt"
    DIALOG = "dialog"
    SESSION_VIEW = "session_view"


# ---------------------------------------------------------------------------
# Leader key state
# ---------------------------------------------------------------------------

LEADER_TIMEOUT = 2.0  # seconds


class LeaderKeyState:
    """Tracks whether the leader key (Ctrl+X) prefix is active."""

    def __init__(self) -> None:
        self.active = False
        self._activated_at: float = 0.0

    def activate(self) -> None:
        self.active = True
        self._activated_at = time.monotonic()

    def deactivate(self) -> None:
        self.active = False
        self._activated_at = 0.0

    @property
    def expired(self) -> bool:
        if not self.active:
            return True
        return (time.monotonic() - self._activated_at) > LEADER_TIMEOUT

    def check_and_consume(self) -> bool:
        """Return True if leader is active and not expired, then deactivate."""
        if self.active and not self.expired:
            self.deactivate()
            return True
        self.deactivate()
        return False


# Module-level singleton
_leader = LeaderKeyState()


def get_leader() -> LeaderKeyState:
    return _leader


def reset_leader() -> None:
    """Reset leader key state (useful for testing)."""
    _leader.deactivate()


# ---------------------------------------------------------------------------
# Keybinding dataclass
# ---------------------------------------------------------------------------


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
    leader: bool = False  # requires Ctrl+X prefix
    context: KeyContext = KeyContext.GLOBAL

    def matches(self, event: KeyEvent, *, leader_active: bool = False) -> bool:
        """Check if a KeyEvent matches this keybinding."""
        if self.leader and not leader_active:
            return False
        if self.leader:
            # After leader, only check key (no modifier required)
            return event.key.lower() == self.key.lower()
        return (
            event.key.lower() == self.key.lower()
            and event.ctrl == self.ctrl
            and event.shift == self.shift
            and event.alt == self.alt
            and event.meta == self.meta
        )

    @property
    def display(self) -> str:
        """Human-readable key combo string."""
        parts: list[str] = []
        if self.leader:
            parts.append("Ctrl+X")
        if self.ctrl:
            parts.append("Ctrl")
        if self.shift:
            parts.append("Shift")
        if self.alt:
            parts.append("Alt")
        if self.meta:
            parts.append("Meta")
        parts.append(self.key.upper() if len(self.key) == 1 else self.key.capitalize())
        return "+".join(parts)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


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

    def list(self, context: KeyContext | None = None) -> list[Keybinding]:
        """Return keybindings, optionally filtered by context."""
        if context is None:
            return list(self._bindings)
        return [b for b in self._bindings if b.context == context]

    def resolve(self, event: KeyEvent, *, context: KeyContext = KeyContext.GLOBAL) -> str | None:
        """Return the action name for a KeyEvent, or None if no match.

        Uses two-pass resolution: context-specific bindings take priority
        over GLOBAL bindings.  This ensures e.g. PROMPT Ctrl+K (kill_line)
        wins over GLOBAL Ctrl+K (command_palette) when context is PROMPT.
        """
        leader = get_leader()
        leader_active = leader.active and not leader.expired

        # Pass 1: exact context match (skip GLOBAL)
        if context != KeyContext.GLOBAL:
            for binding in self._bindings:
                if binding.context != context:
                    continue
                if binding.matches(event, leader_active=leader_active):
                    if binding.leader:
                        leader.deactivate()
                    return binding.action

        # Pass 2: GLOBAL bindings
        for binding in self._bindings:
            if binding.context != KeyContext.GLOBAL:
                continue
            if binding.matches(event, leader_active=leader_active):
                if binding.leader:
                    leader.deactivate()
                return binding.action

        return None


# ---------------------------------------------------------------------------
# Config parser
# ---------------------------------------------------------------------------


def parse_key_combo(combo: str) -> dict:
    """Parse a key combo string like ``"ctrl+shift+k"`` into binding kwargs.

    Returns dict with keys: ``key``, ``ctrl``, ``shift``, ``alt``, ``meta``, ``leader``.
    """
    parts = [p.strip().lower() for p in combo.split("+")]
    result: dict = {"ctrl": False, "shift": False, "alt": False, "meta": False, "leader": False}

    for part in parts[:-1]:  # modifiers
        if part == "ctrl":
            result["ctrl"] = True
        elif part == "shift":
            result["shift"] = True
        elif part == "alt":
            result["alt"] = True
        elif part == "meta":
            result["meta"] = True
        elif part == "leader":
            result["leader"] = True

    result["key"] = parts[-1] if parts else ""
    return result


# ---------------------------------------------------------------------------
# Default bindings
# ---------------------------------------------------------------------------


def default_keybindings() -> KeybindingRegistry:
    """Create a registry with the full OpenCode keybinding set."""
    reg = KeybindingRegistry()

    # --- Global ---
    globals_ = [
        Keybinding(key="k", ctrl=True, action="command_palette", description="Open command palette"),
        Keybinding(key="n", ctrl=True, action="new_session", description="New session"),
        Keybinding(key="l", ctrl=True, action="clear", description="Clear screen"),
        Keybinding(key="b", ctrl=True, action="toggle_sidebar", description="Toggle sidebar"),
        Keybinding(key="escape", action="close_overlay", description="Close overlay / cancel"),
        Keybinding(key="tab", action="switch_pane", description="Switch pane"),
        # Leader key activator
        Keybinding(key="x", ctrl=True, action="leader", description="Leader key prefix"),
    ]

    # --- Leader sequences (Ctrl+X -> key) ---
    leaders = [
        Keybinding(key="t", leader=True, action="pick_theme", description="Pick theme"),
        Keybinding(key="m", leader=True, action="pick_model", description="Pick model"),
        Keybinding(key="s", leader=True, action="pick_session", description="Pick session"),
        Keybinding(key="h", leader=True, action="show_help", description="Show help"),
        Keybinding(key="p", leader=True, action="pick_provider", description="Pick provider"),
        Keybinding(key="a", leader=True, action="pick_agent", description="Pick agent"),
    ]

    # --- Prompt-context bindings ---
    prompt = [
        Keybinding(key="a", ctrl=True, action="cursor_home", description="Move to line start", context=KeyContext.PROMPT),
        Keybinding(key="e", ctrl=True, action="cursor_end", description="Move to line end", context=KeyContext.PROMPT),
        Keybinding(key="k", ctrl=True, action="kill_line", description="Delete to end of line", context=KeyContext.PROMPT),
        Keybinding(key="u", ctrl=True, action="kill_line_back", description="Delete to start of line", context=KeyContext.PROMPT),
        Keybinding(key="w", ctrl=True, action="kill_word_back", description="Delete word backward", context=KeyContext.PROMPT),
        Keybinding(key="d", ctrl=True, action="delete_char", description="Delete character forward", context=KeyContext.PROMPT),
        Keybinding(key="f", ctrl=True, action="cursor_forward", description="Move cursor forward", context=KeyContext.PROMPT),
        Keybinding(key="b", ctrl=True, action="cursor_backward", description="Move cursor backward", context=KeyContext.PROMPT),
        Keybinding(key="p", ctrl=True, action="history_prev", description="Previous history", context=KeyContext.PROMPT),
        Keybinding(key="n", ctrl=True, action="history_next", description="Next history", context=KeyContext.PROMPT),
    ]

    for kb in globals_ + leaders + prompt:
        reg.register(kb)

    return reg


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def dispatch_key(
    event: KeyEvent,
    state: object,
    registry: KeybindingRegistry,
    *,
    context: KeyContext = KeyContext.GLOBAL,
) -> bool:
    """Resolve a KeyEvent via the registry and dispatch to AppState.

    Returns True if the event was handled.
    """
    leader = get_leader()

    # Check for leader key activation (Ctrl+X)
    if event.key.lower() == "x" and event.ctrl and not leader.active:
        leader.activate()
        return True

    # If leader is active but expired, deactivate
    if leader.active and leader.expired:
        leader.deactivate()

    action = registry.resolve(event, context=context)
    if action is None:
        # If leader was active but no match, deactivate
        if leader.active:
            leader.deactivate()
        return False

    bridge = getattr(state, "bridge", None)

    if action == "close_overlay":
        from .overlay import get_overlay_manager

        mgr = get_overlay_manager()
        if mgr.is_active:
            mgr.pop()
            return True
        return False

    if action == "new_session" and bridge:
        bridge.submit(state.create_session())
        return True
    if action == "clear":
        state.messages.set([])
        return True
    if action == "toggle_sidebar":
        state.sidebar_visible.toggle()
        return True

    # Leader sequence actions are dispatched by the app layer
    # (pick_theme, pick_model, etc.)
    return action in (
        "leader", "command_palette", "pick_theme", "pick_model",
        "pick_session", "show_help", "pick_provider", "pick_agent",
        "switch_pane",
    )
