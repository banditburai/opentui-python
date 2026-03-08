"""Help dialog — Ctrl+X -> H."""

from __future__ import annotations

from opentui.components import Box

from ..components.dialog import help_dialog

# Default keybinding reference
_BINDINGS = [
    # --- Global ---
    ("Ctrl+K", "Command palette (global)"),
    ("Ctrl+N", "New session"),
    ("Ctrl+L", "Clear screen"),
    ("Ctrl+B", "Toggle sidebar"),
    ("Ctrl+X -> T", "Change theme"),
    ("Ctrl+X -> M", "Change model"),
    ("Ctrl+X -> S", "Switch session"),
    ("Ctrl+X -> P", "Change provider"),
    ("Ctrl+X -> A", "Change agent"),
    ("Ctrl+X -> H", "Show help"),
    ("Ctrl+C", "Clear input / Cancel"),
    ("Shift+Enter", "New line in input"),
    ("Tab", "Autocomplete"),
    ("Escape", "Close dialog"),
    ("Up/Down", "History navigation"),
    # --- Prompt ---
    ("Ctrl+A", "Move to line start"),
    ("Ctrl+E", "Move to line end"),
    ("Ctrl+K", "Delete to end of line (in prompt)"),
    ("Ctrl+U", "Delete to start of line"),
    ("Ctrl+W", "Delete word backward"),
]


def help_overview(bindings: list[tuple[str, str]] | None = None) -> Box:
    """Render the help overview dialog with keybinding reference."""
    return help_dialog(bindings=bindings or _BINDINGS)
