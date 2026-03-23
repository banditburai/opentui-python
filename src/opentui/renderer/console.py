"""Terminal console overlay.

Provides console overlay bounds, visibility, and mouse handling that the
renderer uses to intercept mouse events before dispatching to the render tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opentui.renderer import CliRenderer


class ConsolePosition(Enum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


@dataclass
class ConsoleBounds:
    x: int
    y: int
    width: int
    height: int


class TerminalConsole:
    """Overlay console for the renderer.

    Handles mouse events inside its bounds and can consume them so they
    don't propagate to the underlying render tree.
    """

    def __init__(self, renderer: CliRenderer, options: dict[str, Any] | None = None):
        self._renderer = renderer
        self._visible = False
        opts = options or {}
        pos_str = opts.get("position", "bottom")
        try:
            self._position = ConsolePosition(pos_str)
        except ValueError:
            self._position = ConsolePosition.BOTTOM
        self._size_percent: int = opts.get("size_percent", opts.get("sizePercent", 30))
        self._console_x = 0
        self._console_y = 0
        self._console_width = 0
        self._console_height = 0
        self._destroyed = False
        self._update_dimensions()

    def _update_dimensions(self) -> None:
        width = self._renderer.width
        height = self._renderer.height
        frac = self._size_percent / 100.0

        if self._position == ConsolePosition.TOP:
            self._console_x = 0
            self._console_y = 0
            self._console_width = width
            self._console_height = max(1, int(height * frac))
        elif self._position == ConsolePosition.BOTTOM:
            h = max(1, int(height * frac))
            self._console_x = 0
            self._console_y = height - h
            self._console_width = width
            self._console_height = h
        elif self._position == ConsolePosition.LEFT:
            w = max(1, int(width * frac))
            self._console_x = 0
            self._console_y = 0
            self._console_width = w
            self._console_height = height
        elif self._position == ConsolePosition.RIGHT:
            w = max(1, int(width * frac))
            self._console_x = width - w
            self._console_y = 0
            self._console_width = w
            self._console_height = height

    def show(self) -> None:
        if not self._visible:
            self._visible = True
            self._update_dimensions()

    def hide(self) -> None:
        self._visible = False

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    @property
    def visible(self) -> bool:
        return self._visible

    @property
    def bounds(self) -> ConsoleBounds:
        return ConsoleBounds(
            x=self._console_x,
            y=self._console_y,
            width=self._console_width,
            height=self._console_height,
        )

    def handle_mouse(self, event: Any) -> bool:
        """Handle a mouse event inside the console bounds.

        Returns True if the event was consumed, False to let it fall
        through to the render tree.
        """
        if not self._visible:
            return False

        local_x = event.x - self._console_x
        local_y = event.y - self._console_y

        if (
            local_x < 0
            or local_x >= self._console_width
            or local_y < 0
            or local_y >= self._console_height
        ):
            return False

        return True

    def resize(self) -> None:
        self._update_dimensions()

    def destroy(self) -> None:
        self._destroyed = True
        self._visible = False
