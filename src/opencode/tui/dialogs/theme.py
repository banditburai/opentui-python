"""Theme picker dialog — Ctrl+X -> T."""

from __future__ import annotations

from opentui.components import Box

from ..components.dialog import select_dialog
from ..themes import get_active_name, get_mode, list_themes, set_mode, set_theme
from . import PickerState


class ThemePickerState(PickerState):
    """State for the theme picker dialog."""

    def confirm(self) -> str | None:
        """Apply the selected theme. Returns theme name or None."""
        themes = [{"label": t} for t in list_themes()]
        filtered = self._filtered(themes)
        if 0 <= self.selected_index < len(filtered):
            name = filtered[self.selected_index]["label"]
            set_theme(name)
            return name
        return None

    def toggle_mode(self) -> None:
        """Toggle between dark and light mode."""
        mode = "light" if get_mode() == "dark" else "dark"
        set_mode(mode)


def theme_picker(state: ThemePickerState) -> Box:
    """Render the theme picker dialog."""
    themes = list_themes()
    active = get_active_name()
    mode = get_mode()

    items = []
    for name in themes:
        marker = " \u2713" if name == active else ""
        items.append({
            "label": name,
            "description": f"({mode}){marker}",
        })

    return select_dialog(
        title=f"Theme ({mode})",
        items=items,
        query=state.query,
        selected_index=state.selected_index,
    )
