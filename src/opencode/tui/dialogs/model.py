"""Model picker dialog — Ctrl+X -> M."""

from __future__ import annotations

from opentui.components import Box

from ..components.dialog import select_dialog
from . import PickerState

# Common models — can be extended via config
_DEFAULT_MODELS = [
    {"label": "claude-sonnet-4-6", "description": "Anthropic", "category": "Anthropic"},
    {"label": "claude-opus-4-6", "description": "Anthropic", "category": "Anthropic"},
    {"label": "claude-haiku-4-5-20251001", "description": "Anthropic", "category": "Anthropic"},
    {"label": "gpt-4o", "description": "OpenAI", "category": "OpenAI"},
    {"label": "gpt-4o-mini", "description": "OpenAI", "category": "OpenAI"},
    {"label": "o3-mini", "description": "OpenAI", "category": "OpenAI"},
    {"label": "gemini-2.0-flash", "description": "Google", "category": "Google"},
    {"label": "deepseek-chat", "description": "DeepSeek", "category": "DeepSeek"},
    {"label": "deepseek-reasoner", "description": "DeepSeek", "category": "DeepSeek"},
]


class ModelPickerState(PickerState):
    """State for the model picker dialog."""

    def __init__(
        self,
        models: list[dict[str, str]] | None = None,
        current_model: str = "",
    ) -> None:
        super().__init__()
        self.models = models or list(_DEFAULT_MODELS)
        self.current_model = current_model

    def confirm(self) -> str | None:
        """Return the selected model name."""
        items = self._filtered(self.models)
        if 0 <= self.selected_index < len(items):
            return items[self.selected_index]["label"]
        return None


def model_picker(state: ModelPickerState) -> Box:
    """Render the model picker dialog."""
    items = []
    for m in state.models:
        marker = " \u2713" if m["label"] == state.current_model else ""
        items.append({
            "label": m["label"],
            "description": f'{m.get("description", "")}{marker}',
            "category": m.get("category", ""),
        })

    return select_dialog(
        title="Model",
        items=items,
        query=state.query,
        selected_index=state.selected_index,
    )
