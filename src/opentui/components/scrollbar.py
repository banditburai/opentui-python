"""ScrollBar component for OpenTUI Python."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

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
        on_scroll: Callable[[int], None] | None = None,
        auto_hide: bool = True,
        # Arrow characters
        arrow_up: str = "▲",
        arrow_down: str = "▼",
        arrow_left: str = "◀",
        arrow_right: str = "▶",
        # Track characters
        track_char: str = "░",
        slider_char: str = "█",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._orientation = orientation
        self._total_items = total_items
        self._visible_items = visible_items
        self._position = position
        self._on_scroll = on_scroll
        self._auto_hide = auto_hide
        self._arrow_up = arrow_up
        self._arrow_down = arrow_down
        self._arrow_left = arrow_left
        self._arrow_right = arrow_right
        self._track_char = track_char
        self._slider_char = slider_char
        self._focusable = True

    @property
    def orientation(self) -> str:
        return self._orientation

    @property
    def total_items(self) -> int:
        return self._total_items

    @total_items.setter
    def total_items(self, value: int) -> None:
        self._total_items = value
        self.mark_dirty()

    @property
    def visible_items(self) -> int:
        return self._visible_items

    @visible_items.setter
    def visible_items(self, value: int) -> None:
        self._visible_items = value
        self.mark_dirty()

    @property
    def position(self) -> int:
        return self._position

    @position.setter
    def position(self, value: int) -> None:
        max_pos = max(0, self._total_items - self._visible_items)
        self._position = max(0, min(value, max_pos))
        self.mark_dirty()

    @property
    def should_show(self) -> bool:
        """Whether the scrollbar should be visible (content exceeds viewport)."""
        return self._total_items > self._visible_items

    def scroll_to(self, position: int) -> None:
        """Scroll to a specific position."""
        old_pos = self._position
        self.position = position
        if self._position != old_pos and self._on_scroll:
            self._on_scroll(self._position)

    def scroll_by(self, delta: int) -> None:
        """Scroll by a relative amount."""
        self.scroll_to(self._position + delta)

    def scroll_page_up(self) -> None:
        """Scroll up by one page."""
        self.scroll_by(-self._visible_items)

    def scroll_page_down(self) -> None:
        """Scroll down by one page."""
        self.scroll_by(self._visible_items)

    def scroll_to_start(self) -> None:
        """Scroll to the beginning."""
        self.scroll_to(0)

    def scroll_to_end(self) -> None:
        """Scroll to the end."""
        self.scroll_to(self._total_items - self._visible_items)

    def _get_slider_info(self, track_length: int) -> tuple[int, int]:
        """Calculate slider position and size within the track.

        Returns:
            (slider_start, slider_size) in track units
        """
        if self._total_items <= 0 or self._total_items <= self._visible_items:
            return 0, track_length

        ratio = self._visible_items / self._total_items
        slider_size = max(1, int(track_length * ratio))

        max_pos = self._total_items - self._visible_items
        if max_pos > 0:
            slider_start = int((track_length - slider_size) * self._position / max_pos)
        else:
            slider_start = 0

        return slider_start, slider_size

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the scrollbar to the buffer."""
        if not self._visible:
            return
        if self._auto_hide and not self.should_show:
            return

        w = self._layout_width or 1
        h = self._layout_height or 1

        if self._orientation == "vertical":
            self._render_vertical(buffer, w, h)
        else:
            self._render_horizontal(buffer, w, h)

    def _render_vertical(self, buffer: Buffer, w: int, h: int) -> None:
        """Render a vertical scrollbar."""
        x = self._x
        y = self._y

        if h < 3:
            return

        # Up arrow
        buffer.draw_text(self._arrow_up, x, y, fg=self._fg)
        # Down arrow
        buffer.draw_text(self._arrow_down, x, y + h - 1, fg=self._fg)

        # Track
        track_length = h - 2
        slider_start, slider_size = self._get_slider_info(track_length)

        for i in range(track_length):
            ty = y + 1 + i
            if slider_start <= i < slider_start + slider_size:
                buffer.draw_text(self._slider_char, x, ty, fg=self._fg)
            else:
                buffer.draw_text(self._track_char, x, ty, fg=self._fg)

    def _render_horizontal(self, buffer: Buffer, w: int, h: int) -> None:
        """Render a horizontal scrollbar."""
        x = self._x
        y = self._y

        if w < 3:
            return

        # Left arrow
        buffer.draw_text(self._arrow_left, x, y, fg=self._fg)
        # Right arrow
        buffer.draw_text(self._arrow_right, x + w - 1, y, fg=self._fg)

        # Track
        track_length = w - 2
        slider_start, slider_size = self._get_slider_info(track_length)

        for i in range(track_length):
            tx = x + 1 + i
            if slider_start <= i < slider_start + slider_size:
                buffer.draw_text(self._slider_char, tx, y, fg=self._fg)
            else:
                buffer.draw_text(self._track_char, tx, y, fg=self._fg)

    def handle_key(self, key: str) -> bool:
        """Handle keyboard navigation. Returns True if key was consumed."""
        if self._orientation == "vertical":
            if key in ("up", "k"):
                self.scroll_by(-1)
                return True
            elif key in ("down", "j"):
                self.scroll_by(1)
                return True
        else:
            if key in ("left", "h"):
                self.scroll_by(-1)
                return True
            elif key in ("right", "l"):
                self.scroll_by(1)
                return True

        if key == "pageup":
            self.scroll_page_up()
            return True
        elif key == "pagedown":
            self.scroll_page_down()
            return True
        elif key == "home":
            self.scroll_to_start()
            return True
        elif key == "end":
            self.scroll_to_end()
            return True

        return False


__all__ = ["ScrollBar"]
