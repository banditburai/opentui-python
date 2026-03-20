"""Input components - text input, textarea, select."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..events import KeyEvent
from ..hooks import use_cursor, use_cursor_style
from ..text_utils import measure_text, wrap_text
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
        # Input options
        placeholder: str = "",
        max_length: int | None = None,
        # Focus
        focused: bool = False,
        # Cursor
        show_cursor: bool = True,
        # Events
        on_input: Callable[[str], None] | None = None,
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        on_key: Callable[[KeyEvent], bool] | None = None,
        # Cursor style
        cursor_style: str = "bar",
        cursor_color: str | None = None,
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
        self._cursor_style = cursor_style
        self._cursor_color = cursor_color
        self._show_cursor = show_cursor

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
        self._cursor_position = min(self._cursor_position, len(v))
        self.mark_dirty()

    @property
    def placeholder(self) -> str:
        return self._placeholder

    def insert_text(self, text: str) -> None:
        if (
            self._max_length is not None
            and self._max_length > 0
            and len(self._value) + len(text) > self._max_length
        ):
            text = text[: self._max_length - len(self._value)]

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
            self.emit("submit", self._value)
            return True
        if key == "escape":
            return True
        if len(key) == 1:
            self.insert_text(key)
            return True

        if self._on_key:
            return self._on_key(event)

        return False

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._layout_width or (buffer.width - x)

        if self._background_color:
            buffer.fill_rect(x, y, width, 1, self._background_color)

        display_text = self._value
        text_color = self._fg
        bg_color = self._background_color

        if not display_text and self._placeholder:
            display_text = self._placeholder
            text_color = s.RGBA(0.5, 0.5, 0.5, 1)

        if len(display_text) > width:
            display_text = display_text[:width]

        buffer.draw_text(display_text, x, y, text_color, bg_color)

        if self._focused and self._show_cursor and self._cursor_position <= width:
            use_cursor(x + self._cursor_position, y)
            use_cursor_style(self._cursor_style, self._cursor_color)


class Textarea(Renderable):
    """Multi-line text input with word/char wrapping and yoga layout.

    Textarea component. Supports ``initialValue``,
    ``wrapMode``, ``textColor``, ``placeholderColor``, ``focusedBackgroundColor``,
    ``focusedTextColor``, and ``cursorColor`` props.

    Usage:
        textarea = Textarea(
            initial_value="Hello World",
            placeholder="Enter text...",
            wrap_mode="word",
            text_color="#ffffff",
            background_color="#1e1e1e",
        )
    """

    def __init__(
        self,
        # Content
        value: str | None = None,
        initial_value: str | None = None,
        placeholder: str = "",
        # Wrapping
        wrap_mode: str = "none",
        rows: int | None = None,
        # Colors
        text_color: s.RGBA | str | None = None,
        placeholder_color: s.RGBA | str | None = None,
        focused_background_color: s.RGBA | str | None = None,
        focused_text_color: s.RGBA | str | None = None,
        cursor_color: s.RGBA | str | None = None,
        # Focus
        focused: bool = False,
        # Events
        on_input: Callable[[str], None] | None = None,
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        on_key: Callable[[KeyEvent], bool] | None = None,
        # Cursor style
        cursor_style: str = "bar",
        **kwargs,
    ):
        if text_color is not None and "fg" not in kwargs:
            kwargs["fg"] = text_color

        super().__init__(
            focused=focused,
            **kwargs,
        )

        self._value = initial_value if initial_value is not None else (value or "")
        self._placeholder = placeholder
        self._wrap_mode = wrap_mode if wrap_mode in ("none", "char", "word") else "none"
        self._rows = rows

        self._text_color = self._parse_color(text_color)
        self._placeholder_color = (
            self._parse_color(placeholder_color)
            if placeholder_color
            else s.RGBA(0.4, 0.4, 0.4, 1.0)
        )
        self._focused_background_color = self._parse_color(focused_background_color)
        self._focused_text_color = self._parse_color(focused_text_color)
        self._cursor_color = self._parse_color(cursor_color) if cursor_color else None
        self._cursor_style = cursor_style
        self._cursor_position = len(self._value)

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

        self._setup_measure_func()

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str) -> None:
        self._value = v
        self._cursor_position = min(self._cursor_position, len(v))
        self.mark_dirty()
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()

    @property
    def placeholder(self) -> str:
        return self._placeholder

    @property
    def wrap_mode(self) -> str:
        return self._wrap_mode

    @wrap_mode.setter
    def wrap_mode(self, v: str) -> None:
        if v not in ("none", "char", "word"):
            v = "none"
        if self._wrap_mode != v:
            self._wrap_mode = v
            self.mark_dirty()
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()

    @property
    def rows(self) -> int | None:
        return self._rows

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            total_padding = self._padding_left + self._padding_right
            vertical_padding = self._padding_top + self._padding_bottom

            effective_width = 0 if width_mode == yoga.MeasureMode.Undefined else int(width)

            content_width = max(0, effective_width - total_padding)
            text = self._value or self._placeholder
            w, h = measure_text(text, content_width, self._wrap_mode)

            measured_w = w + total_padding
            measured_h = h + vertical_padding

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(width, measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def insert_text(self, text: str) -> None:
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
            self.insert_text("\n")
            return True
        if key == "escape":
            return True
        if len(key) == 1:
            self.insert_text(key)
            return True

        if self._on_key:
            return self._on_key(event)

        return False

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        available_width = 0
        if self._layout_width:
            available_width = int(self._layout_width) - self._padding_left - self._padding_right
        available_width = max(0, available_width)

        height = self._layout_height or self._rows or 0
        content_height = height - self._padding_top - self._padding_bottom if height > 0 else 0

        bg_color = self._background_color
        text_color = self._fg or self._text_color
        if self._focused:
            if self._focused_background_color:
                bg_color = self._focused_background_color
            if self._focused_text_color:
                text_color = self._focused_text_color

        if bg_color and self._layout_width and self._layout_height:
            buffer.fill_rect(self._x, self._y, self._layout_width, self._layout_height, bg_color)

        display_text = self._value
        draw_color = text_color
        if not display_text and self._placeholder:
            display_text = self._placeholder
            draw_color = self._placeholder_color

        lines = wrap_text(display_text, available_width, self._wrap_mode)

        for i, line in enumerate(lines):
            if content_height > 0 and i >= content_height:
                break
            buffer.draw_text(line, x, y + i, draw_color, bg_color)

        if self._focused:
            text_before_cursor = self._value[: self._cursor_position]
            lines_before = text_before_cursor.split("\n")
            cursor_line = len(lines_before) - 1
            cursor_col = len(lines_before[-1])

            if self._wrap_mode != "none" and available_width > 0:
                wrapped_line_count = 0
                for i, raw_line in enumerate(self._value.split("\n")):
                    wrapped = wrap_text(raw_line, available_width, self._wrap_mode)
                    num_wrapped = max(1, len(wrapped))
                    if i < cursor_line:
                        wrapped_line_count += num_wrapped
                    else:
                        col = cursor_col
                        line_offset = 0
                        for wl in wrapped[:-1]:
                            if col <= len(wl):
                                break
                            col -= len(wl)
                            line_offset += 1
                        wrapped_line_count += line_offset
                        cursor_col = col
                        break
                cursor_line = wrapped_line_count

            cursor_x = x + cursor_col
            cursor_y = y + cursor_line
            use_cursor(cursor_x, cursor_y)
            use_cursor_style(self._cursor_style, self._cursor_color)


class SelectOption:
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

        if selected is not None:
            for i, opt in enumerate(self._options):
                if opt.value == selected:
                    self._selected_index = i
                    break

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
        if 0 <= index < len(self._options):
            self._selected_index = index
            self.mark_paint_dirty()
            self.emit("change", index, self.selected)
            self.emit("select", index, self.selected)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._layout_width or (buffer.width - x)

        if self._background_color:
            buffer.fill_rect(x, y, width, 1, self._background_color)

        if self.selected:
            display_text = self.selected.name
            if len(display_text) > width - 4:
                display_text = display_text[: width - 4]
            buffer.draw_text(f"▼ {display_text}", x, y, self._fg, self._background_color)
        else:
            buffer.draw_text("▼ Select...", x, y, s.RGBA(0.5, 0.5, 0.5, 1), self._background_color)

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
