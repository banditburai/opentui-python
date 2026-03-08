"""Provider picker dialog — Ctrl+X -> P."""

from __future__ import annotations

from opentui.components import Box

from ..components.dialog import select_dialog
from . import PickerState

_DEFAULT_PROVIDERS = [
    {"label": "anthropic", "description": "Claude models via Anthropic API"},
    {"label": "openai", "description": "GPT models via OpenAI API"},
    {"label": "google", "description": "Gemini models via Google AI"},
    {"label": "openrouter", "description": "Multi-provider routing"},
    {"label": "deepseek", "description": "DeepSeek models"},
    {"label": "ollama", "description": "Local models via Ollama"},
    {"label": "custom", "description": "Custom OpenAI-compatible endpoint"},
]


class ProviderPickerState(PickerState):
    """State for the provider picker dialog."""

    def __init__(
        self,
        providers: list[dict[str, str]] | None = None,
        current_provider: str = "",
    ) -> None:
        super().__init__()
        self.providers = providers or list(_DEFAULT_PROVIDERS)
        self.current_provider = current_provider

    def confirm(self) -> str | None:
        """Return the selected provider name."""
        items = self._filtered(self.providers)
        if 0 <= self.selected_index < len(items):
            return items[self.selected_index]["label"]
        return None


def provider_picker(state: ProviderPickerState) -> Box:
    """Render the provider picker dialog."""
    items = []
    for p in state.providers:
        marker = " \u2713" if p["label"] == state.current_provider else ""
        items.append({
            "label": f'{p["label"]}{marker}',
            "description": p.get("description", ""),
        })

    return select_dialog(
        title="Provider",
        items=items,
        query=state.query,
        selected_index=state.selected_index,
    )
