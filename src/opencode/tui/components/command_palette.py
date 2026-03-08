"""Command palette — Ctrl+K fuzzy-filtered command picker dialog."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from ..commands import CommandRegistry, default_commands
from ..components.dialog import select_dialog
from ..themes import get_theme


class CommandPaletteState:
    """Mutable state for the command palette overlay."""

    def __init__(self, registry: CommandRegistry | None = None) -> None:
        self.registry = registry or default_commands()
        self.query: str = ""
        self.selected_index: int = 0

    def reset(self) -> None:
        self.query = ""
        self.selected_index = 0

    def move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1

    def move_down(self, max_items: int) -> None:
        if self.selected_index < max_items - 1:
            self.selected_index += 1

    def type_char(self, char: str) -> None:
        self.query += char
        self.selected_index = 0

    def backspace(self) -> None:
        if self.query:
            self.query = self.query[:-1]
            self.selected_index = 0

    @property
    def selected_command_id(self) -> str | None:
        """Return the ID of the currently selected command."""
        items = self.registry.to_dialog_items()
        if not items:
            return None
        # Simple: use filtered items if query present
        if self.query:
            q = self.query.lower()
            items = [i for i in items if q in i["label"].lower()]
        if 0 <= self.selected_index < len(items):
            cmd = self.registry.get(
                next(
                    (c.id for c in self.registry.list() if c.name == items[self.selected_index]["label"]),
                    "",
                )
            )
            return cmd.id if cmd else None
        return None


def command_palette(state: CommandPaletteState) -> Box:
    """Render the command palette as a select dialog."""
    items = state.registry.to_dialog_items()

    return select_dialog(
        title="Command Palette",
        items=items,
        query=state.query,
        selected_index=state.selected_index,
        size="medium",
    )
