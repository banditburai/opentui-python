"""Prompt component — enhanced input with cursor, selection, and modes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from opentui.components import Box, Text
from opentui.events import KeyEvent

from ..themes import get_theme


class PromptState:
    """Enhanced prompt state with cursor position and word-level movement."""

    def __init__(self) -> None:
        self.text: str = ""
        self.cursor: int = 0
        self.history: list[str] = []
        self.history_index: int = -1
        self._draft: str = ""
        self.on_submit: Callable[[str], None] | None = None
        self.mode: str = "normal"  # "normal", "shell" (!)

    @property
    def before_cursor(self) -> str:
        return self.text[: self.cursor]

    @property
    def after_cursor(self) -> str:
        return self.text[self.cursor :]

    def insert(self, text: str) -> None:
        self.text = self.before_cursor + text + self.after_cursor
        self.cursor += len(text)

    def submit(self) -> str:
        result = self.text
        if result:
            self.history.append(result)
        self.text = ""
        self.cursor = 0
        self.history_index = -1
        self.mode = "normal"
        return result

    def cursor_home(self) -> None:
        # Move to start of current line
        line_start = self.text.rfind("\n", 0, self.cursor)
        self.cursor = line_start + 1 if line_start >= 0 else 0

    def cursor_end(self) -> None:
        # Move to end of current line
        line_end = self.text.find("\n", self.cursor)
        self.cursor = line_end if line_end >= 0 else len(self.text)

    def cursor_forward(self) -> None:
        if self.cursor < len(self.text):
            self.cursor += 1

    def cursor_backward(self) -> None:
        if self.cursor > 0:
            self.cursor -= 1

    def cursor_word_forward(self) -> None:
        i = self.cursor
        # Skip current word chars
        while i < len(self.text) and self.text[i].isalnum():
            i += 1
        # Skip non-word chars
        while i < len(self.text) and not self.text[i].isalnum():
            i += 1
        self.cursor = i

    def cursor_word_backward(self) -> None:
        i = self.cursor
        # Skip preceding non-word chars
        while i > 0 and not self.text[i - 1].isalnum():
            i -= 1
        # Skip word chars
        while i > 0 and self.text[i - 1].isalnum():
            i -= 1
        self.cursor = i

    def delete_char(self) -> None:
        if self.cursor < len(self.text):
            self.text = self.before_cursor + self.text[self.cursor + 1 :]

    def backspace(self) -> None:
        if self.cursor > 0:
            self.text = self.text[: self.cursor - 1] + self.after_cursor
            self.cursor -= 1

    def kill_line(self) -> None:
        """Delete from cursor to end of line."""
        line_end = self.text.find("\n", self.cursor)
        if line_end >= 0:
            self.text = self.before_cursor + self.text[line_end:]
        else:
            self.text = self.before_cursor

    def kill_line_back(self) -> None:
        """Delete from cursor to start of line."""
        line_start = self.text.rfind("\n", 0, self.cursor)
        start = line_start + 1 if line_start >= 0 else 0
        self.text = self.text[:start] + self.after_cursor
        self.cursor = start

    def kill_word_back(self) -> None:
        """Delete the word before the cursor."""
        old_cursor = self.cursor
        self.cursor_word_backward()
        self.text = self.text[: self.cursor] + self.text[old_cursor:]

    def history_up(self) -> None:
        if not self.history:
            return
        if self.history_index == -1:
            self._draft = self.text
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        self.text = self.history[self.history_index]
        self.cursor = len(self.text)

    def history_down(self) -> None:
        if self.history_index == -1:
            return
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.text = self.history[self.history_index]
        else:
            self.history_index = -1
            self.text = self._draft
        self.cursor = len(self.text)

    def handle_key(self, event: KeyEvent) -> bool:
        """Process a key event. Returns True if handled."""
        key = event.key.lower()

        if key == "c" and event.ctrl:
            self.text = ""
            self.cursor = 0
            return True

        if key in ("return", "enter") and event.shift:
            self.insert("\n")
            return True

        if key in ("return", "enter"):
            result = self.submit()
            if self.on_submit:
                self.on_submit(result)
            return True

        if key == "up":
            self.history_up()
            return True
        if key == "down":
            self.history_down()
            return True

        if key == "backspace":
            self.backspace()
            return True

        if key == "delete":
            self.delete_char()
            return True

        if key == "left":
            if event.ctrl or event.alt:
                self.cursor_word_backward()
            else:
                self.cursor_backward()
            return True

        if key == "right":
            if event.ctrl or event.alt:
                self.cursor_word_forward()
            else:
                self.cursor_forward()
            return True

        if key == "home":
            self.cursor_home()
            return True
        if key == "end":
            self.cursor_end()
            return True

        # Ctrl shortcuts
        if event.ctrl:
            if key == "a":
                self.cursor_home()
                return True
            if key == "e":
                self.cursor_end()
                return True
            if key == "k":
                self.kill_line()
                return True
            if key == "u":
                self.kill_line_back()
                return True
            if key == "w":
                self.kill_word_back()
                return True
            if key == "d":
                self.delete_char()
                return True
            if key == "f":
                self.cursor_forward()
                return True
            if key == "b":
                self.cursor_backward()
                return True

        # Regular character
        if len(event.key) == 1 and not event.ctrl and not event.alt:
            char = event.key
            # Detect shell mode
            if not self.text and char == "!":
                self.mode = "shell"
            self.insert(char)
            return True

        return False


def prompt_box(
    *,
    state: PromptState,
    placeholder: str = "",
    **kwargs: Any,
) -> Box:
    """Render the prompt with cursor indicator."""
    t = get_theme()
    cursor_char = "\u2588"  # block cursor

    if state.text:
        before = state.before_cursor
        after = state.after_cursor
        parts: list[Text] = []

        # Mode indicator
        if state.mode == "shell":
            parts.append(Text("! ", fg=t.warning, bold=True))

        # Handle multi-line
        display = before + cursor_char + after
        for line in display.split("\n"):
            parts.append(Text(line, fg=t.text))

        children = parts
    elif placeholder:
        children = [Text(placeholder, fg=t.text_muted, italic=True)]
    else:
        children = [Text(cursor_char, fg=t.text)]

    defaults = dict(
        flex_direction="column",
        border=True,
        border_style="round",
        border_color=t.border_active if state.text else t.border,
        padding_left=1,
        padding_right=1,
    )
    defaults.update(kwargs)

    return Box(*children, **defaults)
