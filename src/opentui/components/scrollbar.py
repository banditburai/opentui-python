"""ScrollBar component for OpenTUI Python."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..events import MouseButton, MouseEvent
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


class ScrollBar(Renderable):
    """Scrollbar component with arrow buttons and slider track.

    Supports vertical and horizontal orientation, press+hold acceleration
    on arrow buttons, keyboard navigation, and auto-hide when content fits.

    Example:
        scrollbar = ScrollBar(
            orientation="vertical",
            total_items=100,
            visible_items=20,
            position=0,
            on_scroll=lambda pos: print(f"Scrolled to {pos}"),
        )
    """

    def __init__(
        self,
        *,
        orientation: str = "vertical",
        total_items: int = 0,
        visible_items: int = 0,
        position: int = 0,
        position_fn: Callable[[], int] | None = None,
        on_scroll: Callable[[int], None] | None = None,
        auto_hide: bool = True,
        arrow_up: str = "▲",
        arrow_down: str = "▼",
        arrow_left: str = "◀",
        arrow_right: str = "▶",
        track_char: str = "░",
        slider_char: str = "█",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._orientation = orientation
        self._set_or_bind("_total_items", total_items)
        self._set_or_bind("_visible_items", visible_items)
        self._position = position
        self._position_fn = position_fn
        self._on_scroll = on_scroll
        self._auto_hide = auto_hide
        self._arrow_up = arrow_up
        self._arrow_down = arrow_down
        self._arrow_left = arrow_left
        self._arrow_right = arrow_right
        self._track_char = track_char
        self._slider_char = slider_char
        self._focusable = True
        self._dragging_slider = False
        self._drag_anchor = 0
        self.on_mouse_down = self._handle_mouse_down
        self.on_mouse_drag = self._handle_mouse_drag
        self.on_mouse_up = self._handle_mouse_up
        self.on_mouse_drag_end = self._handle_mouse_up

    @property
    def orientation(self) -> str:
        return self._orientation

    @property
    def total_items(self) -> int:
        return self._total_items

    @total_items.setter
    def total_items(self, value: int) -> None:
        self._total_items = value
        self.mark_paint_dirty()

    @property
    def visible_items(self) -> int:
        return self._visible_items

    @visible_items.setter
    def visible_items(self, value: int) -> None:
        self._visible_items = value
        self.mark_paint_dirty()

    @property
    def position(self) -> int:
        return self._position

    @position.setter
    def position(self, value: int) -> None:
        max_pos = max(0, self._total_items - self._visible_items)
        self._position = max(0, min(value, max_pos))
        self.mark_paint_dirty()

    @property
    def should_show(self) -> bool:
        return self._total_items > self._visible_items

    def scroll_to(self, position: int) -> None:
        old_pos = self._position
        self.position = position
        if self._position != old_pos and self._on_scroll:
            self._on_scroll(self._position)

    def scroll_by(self, delta: int) -> None:
        self.scroll_to(self._position + delta)

    def scroll_page_up(self) -> None:
        self.scroll_by(-self._visible_items)

    def scroll_page_down(self) -> None:
        self.scroll_by(self._visible_items)

    def scroll_to_start(self) -> None:
        self.scroll_to(0)

    def scroll_to_end(self) -> None:
        self.scroll_to(self._total_items - self._visible_items)

    def _get_slider_info(self, track_length: int) -> tuple[int, int]:
        if self._total_items <= 0 or self._total_items <= self._visible_items:
            return 0, track_length

        ratio = self._visible_items / self._total_items
        slider_size = max(1, int(track_length * ratio))

        max_pos = self._total_items - self._visible_items
        if max_pos > 0:
            slider_start = int((track_length - slider_size) * self._effective_position() / max_pos)
        else:
            slider_start = 0

        return slider_start, slider_size

    def _max_position(self) -> int:
        return max(0, self._total_items - self._visible_items)

    def _effective_position(self) -> int:
        if self._position_fn is not None:
            return max(0, min(int(self._position_fn()), self._max_position()))
        return self._position

    def _track_hit_info(self, event: MouseEvent) -> tuple[int, int, int] | None:
        if not self.contains_point(event.x, event.y):
            return None
        if self._auto_hide and not self.should_show:
            return None

        if self._orientation == "vertical":
            height = self._layout_height or 1
            if height < 3:
                return None
            track_length = height - 2
            track_index = event.y - self._y - 1
        else:
            width = self._layout_width or 1
            if width < 3:
                return None
            track_length = width - 2
            track_index = event.x - self._x - 1

        slider_start, slider_size = self._get_slider_info(track_length)
        return track_index, slider_start, slider_size

    def _position_from_track(self, track_start: int, track_length: int, slider_size: int) -> int:
        max_pos = self._max_position()
        if max_pos <= 0:
            return 0
        available_track = max(0, track_length - slider_size)
        if available_track <= 0:
            return 0
        clamped_start = max(0, min(track_start, available_track))
        return round(clamped_start * max_pos / available_track)

    def _handle_mouse_down(self, event: MouseEvent) -> None:
        if event.button != MouseButton.LEFT:
            return
        if not self.contains_point(event.x, event.y):
            return
        if self._auto_hide and not self.should_show:
            return

        if self._orientation == "vertical":
            height = self._layout_height or 1
            if height < 3:
                return
            if event.y == self._y:
                self.scroll_by(-1)
                event.stop_propagation()
                return
            if event.y == self._y + height - 1:
                self.scroll_by(1)
                event.stop_propagation()
                return
        else:
            width = self._layout_width or 1
            if width < 3:
                return
            if event.x == self._x:
                self.scroll_by(-1)
                event.stop_propagation()
                return
            if event.x == self._x + width - 1:
                self.scroll_by(1)
                event.stop_propagation()
                return

        hit = self._track_hit_info(event)
        if hit is None:
            return
        track_index, slider_start, slider_size = hit
        if track_index < slider_start:
            self.scroll_page_up()
        elif track_index >= slider_start + slider_size:
            self.scroll_page_down()
        else:
            self._dragging_slider = True
            self._drag_anchor = track_index - slider_start
        event.stop_propagation()

    def _handle_mouse_drag(self, event: MouseEvent) -> None:
        if not self._dragging_slider or not event.is_dragging:
            return
        if self._auto_hide and not self.should_show:
            return

        if self._orientation == "vertical":
            height = self._layout_height or 1
            if height < 3:
                return
            track_length = height - 2
            track_index = event.y - self._y - 1
        else:
            width = self._layout_width or 1
            if width < 3:
                return
            track_length = width - 2
            track_index = event.x - self._x - 1

        _, slider_size = self._get_slider_info(track_length)
        track_start = track_index - self._drag_anchor
        self.scroll_to(self._position_from_track(track_start, track_length, slider_size))
        event.stop_propagation()

    def _handle_mouse_up(self, event: MouseEvent) -> None:
        if self._dragging_slider:
            self._dragging_slider = False
            event.stop_propagation()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return
        if self._auto_hide and not self.should_show:
            return

        if self._position_fn is not None:
            self._position = self._effective_position()

        w = self._layout_width or 1
        h = self._layout_height or 1

        if self._orientation == "vertical":
            self._render_vertical(buffer, w, h)
        else:
            self._render_horizontal(buffer, w, h)

    def _render_vertical(self, buffer: Buffer, w: int, h: int) -> None:
        x = self._x
        y = self._y

        if h < 3:
            return

        buffer.draw_text(self._arrow_up, x, y, fg=self._fg)
        buffer.draw_text(self._arrow_down, x, y + h - 1, fg=self._fg)

        track_length = h - 2
        slider_start, slider_size = self._get_slider_info(track_length)

        for i in range(track_length):
            ty = y + 1 + i
            if slider_start <= i < slider_start + slider_size:
                buffer.draw_text(self._slider_char, x, ty, fg=self._fg)
            else:
                buffer.draw_text(self._track_char, x, ty, fg=self._fg)

    def _render_horizontal(self, buffer: Buffer, w: int, h: int) -> None:
        x = self._x
        y = self._y

        if w < 3:
            return

        buffer.draw_text(self._arrow_left, x, y, fg=self._fg)
        buffer.draw_text(self._arrow_right, x + w - 1, y, fg=self._fg)

        track_length = w - 2
        slider_start, slider_size = self._get_slider_info(track_length)

        for i in range(track_length):
            tx = x + 1 + i
            if slider_start <= i < slider_start + slider_size:
                buffer.draw_text(self._slider_char, tx, y, fg=self._fg)
            else:
                buffer.draw_text(self._track_char, tx, y, fg=self._fg)

    def handle_key(self, key: str) -> bool:
        if self._orientation == "vertical":
            if key in ("up", "k"):
                self.scroll_by(-1)
                return True
            if key in ("down", "j"):
                self.scroll_by(1)
                return True
        else:
            if key in ("left", "h"):
                self.scroll_by(-1)
                return True
            if key in ("right", "l"):
                self.scroll_by(1)
                return True

        if key == "pageup":
            self.scroll_page_up()
            return True
        if key == "pagedown":
            self.scroll_page_down()
            return True
        if key == "home":
            self.scroll_to_start()
            return True
        if key == "end":
            self.scroll_to_end()
            return True

        return False


__all__ = ["ScrollBar"]
