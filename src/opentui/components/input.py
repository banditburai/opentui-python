"""Single-line text input component."""

from collections.abc import Callable

from ..events import KeyEvent
from ..hooks import use_cursor, use_cursor_style
from ..renderer.buffer import Buffer
from ..structs import MUTED_GRAY
from .base import Renderable
from .textarea._text_edit_mixin import _TextEditMixin


class Input(_TextEditMixin, Renderable):
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
        placeholder: str = "",
        max_length: int | None = None,
        focused: bool = False,
        show_cursor: bool = True,
        on_input: Callable[[str], None] | None = None,
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
        on_key: Callable[[KeyEvent], bool] | None = None,
        cursor_style: str = "bar",
        cursor_color: str | None = None,
        **kwargs,
    ):
        super().__init__(focused=focused, **kwargs)

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

    def _handle_enter(self) -> bool:
        self.emit("submit", self._value)
        return True

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
            text_color = MUTED_GRAY

        if len(display_text) > width:
            display_text = display_text[:width]

        buffer.draw_text(display_text, x, y, text_color, bg_color)

        if self._focused and self._show_cursor and self._cursor_position <= width:
            use_cursor(x + self._cursor_position, y)
            use_cursor_style(self._cursor_style, self._cursor_color)


__all__ = ["Input"]
