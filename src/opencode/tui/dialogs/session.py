"""Session picker dialog — Ctrl+X -> S."""

from __future__ import annotations

from opentui.components import Box

from ..components.dialog import select_dialog
from . import PickerState


class SessionPickerState(PickerState):
    """State for the session picker dialog."""

    def __init__(
        self,
        sessions: list[dict[str, str]] | None = None,
        active_id: str = "",
    ) -> None:
        super().__init__()
        self.sessions = sessions or []
        self.active_id = active_id

    def confirm(self) -> str | None:
        """Return the selected session ID."""
        items = self._filtered(self.sessions, key="title")
        if 0 <= self.selected_index < len(items):
            return items[self.selected_index].get("id")
        return None

    def update_sessions(self, sessions: list[dict[str, str]], active_id: str = "") -> None:
        self.sessions = sessions
        self.active_id = active_id


def session_picker(state: SessionPickerState) -> Box:
    """Render the session picker dialog."""
    items = []
    for s in state.sessions:
        title = s.get("title", "Untitled")
        marker = " \u2713" if s.get("id") == state.active_id else ""
        items.append({
            "label": f"{title}{marker}",
            "description": s.get("id", "")[:8],
            "title": title,
            "id": s.get("id", ""),
        })

    return select_dialog(
        title="Sessions",
        items=items,
        query=state.query,
        selected_index=state.selected_index,
    )
