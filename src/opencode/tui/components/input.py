"""Input area — multi-line text input with history and key handling."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from opentui.components import Box, Text
from opentui.events import KeyEvent

from ..themes import get_theme


class InputState:
    """Mutable state for the input area.

    Handles text editing, history navigation, and key dispatch.
    """

    def __init__(self) -> None:
        self.text: str = ""
        self.history: list[str] = []
        self.history_index: int = -1
        self._draft: str = ""
        self.on_submit: Callable[[str], None] | None = None

    def submit(self) -> str:
        """Submit current text: return it, add to history, and clear."""
        result = self.text
        if result:
            self.history.append(result)
        self.text = ""
        self.history_index = -1
        return result

    def history_up(self) -> None:
        """Navigate to older history entry."""
        if not self.history:
            return
        if self.history_index == -1:
            self._draft = self.text
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        self.text = self.history[self.history_index]

    def history_down(self) -> None:
        """Navigate to newer history entry."""
        if self.history_index == -1:
            return
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.text = self.history[self.history_index]
        else:
            self.history_index = -1
            self.text = self._draft

    def handle_key(self, event: KeyEvent) -> bool:
        """Process a key event. Returns True if handled."""
        key = event.key.lower()

        # Ctrl+C clears input
        if key == "c" and event.ctrl:
            self.text = ""
            return True

        # Shift+Enter inserts newline
        if key in ("return", "enter") and event.shift:
            self.text += "\n"
            return True

        # Enter submits
        if key in ("return", "enter"):
            result = self.submit()
            if self.on_submit:
                self.on_submit(result)
            return True

        # Up/Down for history
        if key == "up":
            self.history_up()
            return True
        if key == "down":
            self.history_down()
            return True

        # Backspace
        if key == "backspace":
            if self.text:
                self.text = self.text[:-1]
            return True

        # Regular character — use original case from event.key
        if len(event.key) == 1 and not event.ctrl and not event.alt:
            self.text += event.key
            return True

        return False


def input_area(
    *,
    state: InputState,
    placeholder: str = "",
    **kwargs: Any,
) -> Box:
    """Render the input area as a Box with the current text or placeholder."""
    t = get_theme()

    if state.text:
        lines = state.text.split("\n")
        children: list[Text] = [Text(line, fg=t.text) for line in lines]
    elif placeholder:
        children = [Text(placeholder, fg=t.text_muted, italic=True)]
    else:
        children = [Text("", fg=t.text)]

    defaults = dict(
        flex_direction="column",
        border=True,
        border_style="round",
        border_color=t.border,
        padding_left=1,
        padding_right=1,
    )
    defaults.update(kwargs)

    return Box(*children, **defaults)
