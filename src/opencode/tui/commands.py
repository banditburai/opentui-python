"""Command registry — registrable commands with keybinding display."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Command:
    """A registrable command with a unique ID, display name, and optional keybinding."""

    id: str
    name: str
    description: str = ""
    keybinding: str = ""  # display string like "Ctrl+K"
    category: str = "General"


class CommandRegistry:
    """Registry of commands, used by the command palette."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        self._commands[command.id] = command

    def unregister(self, command_id: str) -> None:
        self._commands.pop(command_id, None)

    def get(self, command_id: str) -> Command | None:
        return self._commands.get(command_id)

    def list(self, category: str | None = None) -> list[Command]:
        """Return commands sorted by category then name."""
        cmds = list(self._commands.values())
        if category:
            cmds = [c for c in cmds if c.category == category]
        return sorted(cmds, key=lambda c: (c.category, c.name))

    def categories(self) -> list[str]:
        """Return sorted unique category names."""
        return sorted({c.category for c in self._commands.values()})

    def to_dialog_items(self) -> list[dict[str, str]]:
        """Convert to the format expected by ``select_dialog``."""
        return [
            {
                "label": c.name,
                "description": c.description,
                "category": c.category,
                "keybinding": c.keybinding,
            }
            for c in self.list()
        ]


def default_commands() -> CommandRegistry:
    """Create a registry with the built-in OpenCode commands."""
    reg = CommandRegistry()
    commands = [
        Command(id="new_session", name="New Session", description="Start a new chat session", keybinding="Ctrl+N", category="Session"),
        Command(id="switch_session", name="Switch Session", description="Browse and switch sessions", keybinding="Ctrl+X → S", category="Session"),
        Command(id="change_model", name="Change Model", description="Switch the AI model", keybinding="Ctrl+X → M", category="Settings"),
        Command(id="change_theme", name="Change Theme", description="Switch the color theme", keybinding="Ctrl+X → T", category="Settings"),
        Command(id="change_provider", name="Change Provider", description="Switch the AI provider", keybinding="Ctrl+X → P", category="Settings"),
        Command(id="change_agent", name="Change Agent", description="Switch the agent configuration", keybinding="Ctrl+X → A", category="Settings"),
        Command(id="toggle_sidebar", name="Toggle Sidebar", description="Show or hide the sidebar", keybinding="Ctrl+B", category="View"),
        Command(id="clear_screen", name="Clear Screen", description="Clear the chat output", keybinding="Ctrl+L", category="View"),
        Command(id="show_help", name="Show Help", description="Show keyboard shortcuts", keybinding="Ctrl+X → H", category="Help"),
        Command(id="show_mcp", name="MCP Status", description="Show MCP server status", category="System"),
        Command(id="export_session", name="Export Session", description="Export the current session", category="Session"),
        Command(id="abort", name="Abort", description="Abort the current operation", keybinding="Ctrl+C", category="Session"),
    ]
    for cmd in commands:
        reg.register(cmd)
    return reg
