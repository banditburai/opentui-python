"""Application dialogs — pickers for themes, models, sessions, providers, etc."""

from __future__ import annotations

from ..fuzzy import fuzzy_filter


class PickerState:
    """Base class for fuzzy-searchable picker dialog state."""

    def __init__(self) -> None:
        self.query: str = ""
        self.selected_index: int = 0

    def reset(self) -> None:
        self.query = ""
        self.selected_index = 0

    def type_char(self, char: str) -> None:
        self.query += char
        self.selected_index = 0

    def backspace(self) -> None:
        if self.query:
            self.query = self.query[:-1]
            self.selected_index = 0

    def move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1

    def move_down(self, max_items: int) -> None:
        if self.selected_index < max_items - 1:
            self.selected_index += 1

    def _filtered(self, items: list[dict[str, str]], key: str = "label") -> list[dict[str, str]]:
        """Return items filtered by fuzzy match on *key*, in score order."""
        if not self.query:
            return items
        labels = [item[key] for item in items]
        matches = fuzzy_filter(self.query, labels)
        label_to_item = {item[key]: item for item in items}
        return [label_to_item[label] for label, _ in matches if label in label_to_item]


from .agent import AgentPickerState, agent_picker
from .export import ExportDialogState, export_dialog
from .help import help_overview
from .mcp import McpStatusState, mcp_status_dialog
from .model import ModelPickerState, model_picker
from .provider import ProviderPickerState, provider_picker
from .session import SessionPickerState, session_picker
from .stash import StashBrowserState, stash_browser
from .theme import ThemePickerState, theme_picker

__all__ = [
    "AgentPickerState",
    "ExportDialogState",
    "McpStatusState",
    "ModelPickerState",
    "PickerState",
    "ProviderPickerState",
    "SessionPickerState",
    "StashBrowserState",
    "ThemePickerState",
    "agent_picker",
    "export_dialog",
    "help_overview",
    "mcp_status_dialog",
    "model_picker",
    "provider_picker",
    "session_picker",
    "stash_browser",
    "theme_picker",
]
