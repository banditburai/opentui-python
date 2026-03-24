"""Multi-line text input component."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ... import structs as s
from ...events import KeyEvent
from ...hooks import use_cursor, use_cursor_style
from ...structs import MUTED_GRAY
from ...text_utils import measure_text, wrap_text
from ._text_edit_mixin import _TextEditMixin
from ..base import Renderable

if TYPE_CHECKING:
    from ...renderer import Buffer


class Textarea(_TextEditMixin, Renderable):
    """Multi-line text input with word/char wrapping and yoga layout.

    Usage:
        textarea = Textarea(
            initial_value="Hello World",
            placeholder="Enter text...",
            wrap_mode="word",
        )
    """

    def __init__(
        self,
        value: str | None = None,
        initial_value: str | None = None,
        placeholder: str = "",
        wrap_mode: str = "none",
        rows: int | None = None,
        text_color: s.RGBA | str | None = None,
        placeholder_color: s.RGBA | str | None = None,
        focused_background_color: s.RGBA | str | None = None,
        focused_text_color: s.RGBA | str | None = None,
        cursor_color: s.RGBA | str | None = None,
        focused: bool = False,
        on_input: Callable[[str], None] | None = None,
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        on_key: Callable[[KeyEvent], bool] | None = None,
        cursor_style: str = "bar",
        **kwargs,
    ):
        if text_color is not None and "fg" not in kwargs:
            kwargs["fg"] = text_color

        super().__init__(focused=focused, **kwargs)

        self._value = initial_value if initial_value is not None else (value or "")
        self._placeholder = placeholder
        self._wrap_mode = wrap_mode if wrap_mode in ("none", "char", "word") else "none"
        self._rows = rows

        self._text_color = self._parse_color(text_color)
        self._placeholder_color = (
            self._parse_color(placeholder_color) if placeholder_color else MUTED_GRAY
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

    def _handle_enter(self) -> bool:
        self.insert_text("\n")
        return True

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


__all__ = ["Textarea"]
