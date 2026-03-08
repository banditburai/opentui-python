"""Agent picker dialog — Ctrl+X -> A."""

from __future__ import annotations

from opentui.components import Box

from ..components.dialog import select_dialog
from . import PickerState

_DEFAULT_AGENTS = [
    {"label": "coder", "description": "General coding assistant"},
    {"label": "planner", "description": "Task planning and architecture"},
    {"label": "researcher", "description": "Code exploration and analysis"},
    {"label": "reviewer", "description": "Code review and quality checks"},
]


class AgentPickerState(PickerState):
    """State for the agent picker dialog."""

    def __init__(
        self,
        agents: list[dict[str, str]] | None = None,
        current_agent: str = "",
    ) -> None:
        super().__init__()
        self.agents = agents or list(_DEFAULT_AGENTS)
        self.current_agent = current_agent

    def confirm(self) -> str | None:
        """Return the selected agent name."""
        items = self._filtered(self.agents)
        if 0 <= self.selected_index < len(items):
            return items[self.selected_index]["label"]
        return None


def agent_picker(state: AgentPickerState) -> Box:
    """Render the agent picker dialog."""
    items = []
    for a in state.agents:
        marker = " \u2713" if a["label"] == state.current_agent else ""
        items.append({
            "label": f'{a["label"]}{marker}',
            "description": a.get("description", ""),
        })

    return select_dialog(
        title="Agent",
        items=items,
        query=state.query,
        selected_index=state.selected_index,
    )
