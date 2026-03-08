"""Stash browser dialog — browse and restore stashed prompt text."""

from __future__ import annotations

import time as _time

from opentui.components import Box, Text

from ..components.dialog import dialog_box, select_item
from ..persistence import load_stash, pop_stash
from ..themes import get_theme


class StashBrowserState:
    """State for the stash browser dialog."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.selected_index: int = 0
        self.refresh()

    def refresh(self) -> None:
        # Store newest-first so display order matches index
        self.entries = list(reversed(load_stash()))
        self.selected_index = 0

    def move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1

    def move_down(self) -> None:
        if self.selected_index < len(self.entries) - 1:
            self.selected_index += 1

    def confirm(self) -> str | None:
        """Pop the selected stash entry's text."""
        if 0 <= self.selected_index < len(self.entries):
            entry = self.entries[self.selected_index]
            text = entry.get("text")
            pop_stash()
            self.refresh()
            return text
        return None

    def confirm_selected(self) -> str | None:
        """Return the selected entry's text (without popping)."""
        if 0 <= self.selected_index < len(self.entries):
            return self.entries[self.selected_index].get("text")
        return None


def _format_timestamp(ts: float) -> str:
    """Format a Unix timestamp as a relative time string."""
    delta = _time.time() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    return f"{int(delta / 86400)}d ago"


def stash_browser(state: StashBrowserState) -> Box:
    """Render the stash browser dialog."""
    t = get_theme()

    if not state.entries:
        return dialog_box(
            Text("Stash is empty.", fg=t.text_muted),
            Box(
                Text("Use Ctrl+S to stash current input text.", fg=t.text_muted),
                padding_top=1,
            ),
            title="Stash",
        )

    children: list[Box] = []
    for i, entry in enumerate(state.entries):
        text = entry.get("text", "")
        label_text = entry.get("label", "") or text[:40]
        ts = entry.get("timestamp", 0)
        time_str = _format_timestamp(ts) if ts else ""

        children.append(
            select_item(
                label=label_text,
                description=time_str,
                selected=(i == state.selected_index),
            )
        )

    footer = Box(
        Text("\u2191\u2193 Navigate  Enter Restore  Esc Cancel", fg=t.text_muted),
        padding_left=1,
    )

    return dialog_box(
        *children,
        footer,
        title="Stash",
    )
