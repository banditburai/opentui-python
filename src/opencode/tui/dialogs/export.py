"""Export dialog — options for exporting session data."""

from __future__ import annotations

from opentui.components import Box

from ..components.dialog import select_dialog
from . import PickerState

_EXPORT_FORMATS = [
    {"label": "Markdown", "description": "Export as .md file"},
    {"label": "JSON", "description": "Export as structured .json"},
    {"label": "Text", "description": "Export as plain .txt"},
    {"label": "Clipboard", "description": "Copy to clipboard"},
]


class ExportDialogState(PickerState):
    """State for the export dialog."""

    def confirm(self) -> str | None:
        """Return the selected export format label."""
        items = self._filtered(_EXPORT_FORMATS)
        if 0 <= self.selected_index < len(items):
            return items[self.selected_index]["label"]
        return None


def export_dialog(state: ExportDialogState) -> Box:
    """Render the export options dialog."""
    return select_dialog(
        title="Export Session",
        items=_EXPORT_FORMATS,
        query=state.query,
        selected_index=state.selected_index,
    )
