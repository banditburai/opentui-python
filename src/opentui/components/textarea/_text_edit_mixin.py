"""Shared text-editing logic for Input and Textarea."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

from ...events import KeyEvent


class _TextEditHost(Protocol):
    """Protocol for the host class that _TextEditMixin is mixed into."""

    _value: str
    _cursor_position: int
    _on_key: Callable[[Any], bool] | None
    value: str

    def emit(self, event: str, *args: Any) -> None: ...
    def mark_paint_dirty(self) -> None: ...


class _TextEditMixin:
    """Common text editing: insert, delete, cursor movement, key dispatch.

    Mixed into Input and Textarea alongside Renderable, which provides
    emit() and mark_paint_dirty().
    """

    # Declare slots used by this mixin (actual storage on the concrete class)
    _value: str
    _cursor_position: int
    _on_key: Callable[[Any], bool] | None

    if TYPE_CHECKING:
        # These come from Renderable — declared here for type-checker only
        value: str

        def emit(self, event: str, *args: Any) -> None: ...
        def mark_paint_dirty(self) -> None: ...

    def insert_text(self, text: str) -> None:
        max_len = getattr(self, "_max_length", None)
        if max_len is not None and max_len > 0 and len(self._value) + len(text) > max_len:
            text = text[: max_len - len(self._value)]
        new_value = (
            self._value[: self._cursor_position] + text + self._value[self._cursor_position :]
        )
        self._cursor_position += len(text)
        self.value = new_value
        self.emit("input", new_value)

    def delete_char(self, forward: bool = False) -> None:
        if forward:
            if self._cursor_position < len(self._value):
                self.value = (
                    self._value[: self._cursor_position] + self._value[self._cursor_position + 1 :]
                )
        elif self._cursor_position > 0:
            self.value = (
                self._value[: self._cursor_position - 1] + self._value[self._cursor_position :]
            )
            self._cursor_position -= 1

    def move_cursor(self, offset: int) -> None:
        new_pos = self._cursor_position + offset
        self._cursor_position = max(0, min(len(self._value), new_pos))
        self.mark_paint_dirty()

    def _handle_enter(self) -> bool:
        """Override in subclass for enter key behavior."""
        return True

    def handle_key(self, event: KeyEvent) -> bool:
        key = event.key.lower()
        if key == "backspace":
            self.delete_char(forward=False)
            return True
        if key == "delete":
            self.delete_char(forward=True)
            return True
        if key == "left":
            self.move_cursor(-1)
            return True
        if key == "right":
            self.move_cursor(1)
            return True
        if key == "home":
            self._cursor_position = 0
            self.mark_paint_dirty()
            return True
        if key == "end":
            self._cursor_position = len(self._value)
            self.mark_paint_dirty()
            return True
        if key in {"return", "enter"}:
            return self._handle_enter()
        if key == "escape":
            return True
        if len(key) == 1:
            self.insert_text(key)
            return True
        if self._on_key:
            return self._on_key(event)
        return False
