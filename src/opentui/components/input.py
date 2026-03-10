"""Input components - text input, textarea, select."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..events import KeyEvent
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


class Input(Renderable):
    """Single-line text input.

    Usage:
        input = Input(
            value=value_signal,
            placeholder="Enter text...",
            on_input=handler,
            on_submit=handler,
        )
    """

    def __init__(
        self,
        value: str | None = None,
        *children: Any,
        # Input options
        placeholder: str = "",
        max_length: int | None = None,
        # Focus
        focused: bool = False,
        # Events
        on_input: Callable[[str], None] | None = None,
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        on_key: Callable[[KeyEvent], bool] | None = None,
        # Style
        **kwargs,
    ):
        super().__init__(
            focused=focused,
            **kwargs,
        )

        self._value = value or ""
        self._placeholder = placeholder
        self._max_length = max_length
        self._cursor_position = len(self._value)

        # Register event handlers
        if on_input:
            self.on("input", on_input)
        if on_change:
            self.on("change", on_change)
        if on_submit:
            self.on("submit", on_submit)
        if on_key:
            self.on("key", on_key)

        self._focusable = True
        self._on_key = on_key

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str) -> None:
        self._value = v
        if self._cursor_position > len(v):
            self._cursor_position = len(v)

    @property
    def placeholder(self) -> str:
        return self._placeholder

    def insert_text(self, text: str) -> None:
        """Insert text at cursor position."""
        if self._max_length and len(self._value) + len(text) > self._max_length:
            text = text[: self._max_length - len(self._value)]

        new_value = (
            self._value[: self._cursor_position] + text + self._value[self._cursor_position :]
        )
        self._cursor_position += len(text)
        self.value = new_value
        self.emit("input", new_value)

    def delete_char(self, forward: bool = False) -> None:
        """Delete character at cursor position."""
        if forward:
            if self._cursor_position < len(self._value):
                self.value = (
                    self._value[: self._cursor_position] + self._value[self._cursor_position + 1 :]
                )
        else:
            if self._cursor_position > 0:
                self.value = (
                    self._value[: self._cursor_position - 1] + self._value[self._cursor_position :]
                )
                self._cursor_position -= 1

    def move_cursor(self, offset: int) -> None:
        """Move cursor by offset."""
        new_pos = self._cursor_position + offset
        self._cursor_position = max(0, min(len(self._value), new_pos))

    def handle_key(self, event: KeyEvent) -> bool:
        """Handle keyboard input.

        Returns True if the event was handled.
        """
        key = event.key.lower()

        if key == "backspace":
            self.delete_char(forward=False)
            return True
        elif key == "delete":
            self.delete_char(forward=True)
            return True
        elif key == "left":
            self.move_cursor(-1)
            return True
        elif key == "right":
            self.move_cursor(1)
            return True
        elif key == "home":
            self._cursor_position = 0
            return True
        elif key == "end":
            self._cursor_position = len(self._value)
            return True
        elif key == "return" or key == "enter":
            self.emit("submit", self._value)
            return True
        elif key == "escape":
            return True
        elif len(key) == 1:
            self.insert_text(key)
            return True

        if self._on_key:
            return self._on_key(event)

        return False

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the input."""
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._layout_width or (buffer.width - x)

        # Draw background
        if self._background_color:
            buffer.fill_rect(x, y, width, 1, self._background_color)

        # Draw value or placeholder
        display_text = self._value
        text_color = self._fg
        bg_color = self._background_color

        if not display_text and self._placeholder:
            display_text = self._placeholder
            text_color = s.RGBA(0.5, 0.5, 0.5, 1)  # Gray for placeholder

        # Truncate to fit
        if len(display_text) > width:
            display_text = display_text[:width]

        buffer.draw_text(display_text, x, y, text_color, bg_color)

        # Draw cursor if focused
        if self._focused and self._cursor_position <= width:
            cursor_char = "█"
            cursor_x = x + self._cursor_position
            cursor_bg = s.RGBA(1, 1, 1, 1)
            buffer.draw_text(cursor_char, cursor_x, y, s.RGBA(0, 0, 0, 1), cursor_bg)


class Textarea(Input):
    """Multi-line text input.

    Usage:
        textarea = Textarea(
            value=value_signal,
            placeholder="Enter text...",
            rows=5,
        )
    """

    def __init__(
        self,
        *children: Any,
        rows: int = 3,
        wrap: bool = True,
        **kwargs,
    ):
        super().__init__(*children, **kwargs)

        self._rows = rows
        self._wrap = wrap

    @property
    def rows(self) -> int:
        return self._rows

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the textarea."""
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._layout_width or (buffer.width - x)
        height = self._layout_height or self._rows

        # Draw background
        if self._background_color:
            buffer.fill_rect(x, y, width, height, self._background_color)

        # Split text into lines
        lines = self._value.split("\n")

        # Render each line
        for i, line in enumerate(lines[:height]):
            if i >= height:
                break

            display_line = line
            if self._wrap and len(display_line) > width:
                display_line = display_line[:width]

            buffer.draw_text(display_line, x, y + i, self._fg, self._background_color)


class SelectOption:
    """Option for Select component."""

    def __init__(
        self,
        name: str,
        value: Any = None,
        description: str | None = None,
    ):
        self.name = name
        self.value = value if value is not None else name
        self.description = description


class Select(Renderable):
    """Dropdown selection component.

    Usage:
        select = Select(
            options=[
                SelectOption("Option 1", value=1),
                SelectOption("Option 2", value=2),
            ],
            selected=selected_signal,
            on_change=handler,
        )
    """

    def __init__(
        self,
        options: list[SelectOption] | None = None,
        *children: Any,
        # Selection
        selected: Any = None,
        # Focus
        focused: bool = False,
        # Events
        on_change: Callable[[int, SelectOption | None], None] | None = None,
        on_select: Callable[[int, SelectOption | None], None] | None = None,
        # Style
        **kwargs,
    ):
        super().__init__(
            focused=focused,
            **kwargs,
        )

        self._options = options or []
        self._selected_index = -1

        # Find selected index
        if selected is not None:
            for i, opt in enumerate(self._options):
                if opt.value == selected:
                    self._selected_index = i
                    break

        # Register event handlers
        if on_change:
            self.on("change", on_change)
        if on_select:
            self.on("select", on_select)

        self._focusable = True
        self._expanded = False

    @property
    def options(self) -> list[SelectOption]:
        return self._options

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @property
    def selected(self) -> SelectOption | None:
        if 0 <= self._selected_index < len(self._options):
            return self._options[self._selected_index]
        return None

    def select(self, index: int) -> None:
        """Select an option by index."""
        if 0 <= index < len(self._options):
            self._selected_index = index
            self.emit("change", index, self.selected)
            self.emit("select", index, self.selected)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the select."""
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._layout_width or (buffer.width - x)

        # Draw background
        if self._background_color:
            buffer.fill_rect(x, y, width, 1, self._background_color)

        # Draw current selection
        if self.selected:
            display_text = self.selected.name
            if len(display_text) > width - 4:
                display_text = display_text[: width - 4]
            buffer.draw_text(f"▼ {display_text}", x, y, self._fg, self._background_color)
        else:
            buffer.draw_text("▼ Select...", x, y, s.RGBA(0.5, 0.5, 0.5, 1), self._background_color)

        # Draw dropdown if expanded
        if self._expanded:
            for i, opt in enumerate(self._options[:10]):  # Limit to 10 visible
                line_y = y + i + 1
                if line_y >= buffer.height:
                    break

                prefix = "▶" if i == self._selected_index else " "
                display_text = opt.name
                if len(display_text) > width - 2:
                    display_text = display_text[: width - 2]

                buffer.draw_text(
                    f"{prefix} {display_text}", x, line_y, self._fg, self._background_color
                )


__all__ = [
    "Input",
    "Textarea",
    "Select",
    "SelectOption",
]
