"""Select dropdown component."""

from collections.abc import Callable
from typing import Any

from ..renderer.buffer import Buffer
from ..structs import MUTED_GRAY
from .base import Renderable

_DROPDOWN_EDGE_MARGIN = 4
_DROPDOWN_INNER_MARGIN = 2
_MAX_DROPDOWN_ITEMS = 10


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
        selected: Any = None,
        focused: bool = False,
        on_change: Callable[[int, SelectOption | None], None] | None = None,
        on_select: Callable[[int, SelectOption | None], None] | None = None,
        **kwargs,
    ):
        super().__init__(focused=focused, **kwargs)

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
            if len(display_text) > width - _DROPDOWN_EDGE_MARGIN:
                display_text = display_text[: width - _DROPDOWN_EDGE_MARGIN]
            buffer.draw_text(f"▼ {display_text}", x, y, self._fg, self._background_color)
        else:
            buffer.draw_text("▼ Select...", x, y, MUTED_GRAY, self._background_color)

        if self._expanded:
            for i, opt in enumerate(self._options[:_MAX_DROPDOWN_ITEMS]):
                line_y = y + i + 1
                if line_y >= buffer.height:
                    break

                prefix = "▶" if i == self._selected_index else " "
                display_text = opt.name
                if len(display_text) > width - _DROPDOWN_INNER_MARGIN:
                    display_text = display_text[: width - _DROPDOWN_INNER_MARGIN]

                buffer.draw_text(
                    f"{prefix} {display_text}", x, line_y, self._fg, self._background_color
                )


__all__ = ["Select", "SelectOption"]
