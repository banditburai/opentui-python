"""Box component - container with borders and layout."""

from __future__ import annotations

from collections.abc import Callable
import math
import time
from typing import TYPE_CHECKING, Any

from .. import structs as s
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


# Border style characters
BORDER_CHARS = {
    "single": {
        "top_left": "┌",
        "top_right": "┐",
        "bottom_left": "└",
        "bottom_right": "┘",
        "horizontal": "─",
        "vertical": "│",
    },
    "double": {
        "top_left": "╔",
        "top_right": "╗",
        "bottom_left": "╚",
        "bottom_right": "╝",
        "horizontal": "═",
        "vertical": "║",
    },
    "round": {
        "top_left": "╭",
        "top_right": "╮",
        "bottom_left": "╰",
        "bottom_right": "╯",
        "horizontal": "─",
        "vertical": "│",
    },
    "bold": {
        "top_left": "┏",
        "top_right": "┓",
        "bottom_left": "┗",
        "bottom_right": "┛",
        "horizontal": "━",
        "vertical": "┃",
    },
    "block": {
        "top_left": "█",
        "top_right": "█",
        "bottom_left": "█",
        "bottom_right": "█",
        "horizontal": "█",
        "vertical": "█",
    },
}


class LinearScrollAccel:
    """No-op scroll acceleration."""

    def tick(self, _now_ms: float | None = None) -> float:
        return 1.0

    def reset(self) -> None:
        return None


class MacOSScrollAccel:
    """macOS-inspired scroll acceleration."""

    _HISTORY_SIZE = 3
    _STREAK_TIMEOUT = 150  # ms
    _MIN_TICK_INTERVAL = 6  # ms
    _REFERENCE_INTERVAL = 100  # ms

    def __init__(self, *, amplitude: float = 0.8, tau: float = 3.0, max_multiplier: float = 6.0):
        self._amplitude = amplitude
        self._tau = tau
        self._max_multiplier = max_multiplier
        self._last_tick_ms = 0.0
        self._history: list[float] = []

    def tick(self, now_ms: float | None = None) -> float:
        if now_ms is None:
            now_ms = time.monotonic() * 1000.0

        dt = (now_ms - self._last_tick_ms) if self._last_tick_ms else float("inf")
        if dt == float("inf") or dt > self._STREAK_TIMEOUT:
            self._last_tick_ms = now_ms
            self._history.clear()
            return 1.0

        if dt < self._MIN_TICK_INTERVAL:
            return 1.0

        self._last_tick_ms = now_ms
        self._history.append(dt)
        if len(self._history) > self._HISTORY_SIZE:
            self._history.pop(0)

        avg_interval = sum(self._history) / len(self._history)
        velocity = self._REFERENCE_INTERVAL / avg_interval
        x = velocity / self._tau
        multiplier = 1.0 + self._amplitude * (math.exp(x) - 1.0)
        return min(multiplier, self._max_multiplier)

    def reset(self) -> None:
        self._last_tick_ms = 0.0
        self._history.clear()


class Box(Renderable):
    """Box component - container with optional border and layout.

    Usage:
        box = Box(
            padding=2,
            border=True,
            border_style="rounded",
            children=[
                Text("Hello!"),
            ]
        )
    """

    def __init__(
        self,
        *children: Any,
        # Identity
        key: str | int | None = None,
        # Layout
        width: int | None = None,
        height: int | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        flex_grow: float = 0,
        flex_shrink: float = 1,
        flex_basis: float | str | None = None,
        flex_direction: str = "column",
        flex_wrap: str = "nowrap",
        justify_content: str = "flex-start",
        align_items: str = "stretch",
        align_self: str | None = None,
        gap: int = 0,
        # Spacing
        padding: int = 0,
        padding_top: int | None = None,
        padding_right: int | None = None,
        padding_bottom: int | None = None,
        padding_left: int | None = None,
        margin: int = 0,
        margin_top: int | None = None,
        margin_right: int | None = None,
        margin_bottom: int | None = None,
        margin_left: int | None = None,
        # Style
        background_color: s.RGBA | str | None = None,
        fg: s.RGBA | str | None = None,
        border: bool = False,
        border_style: str = "single",
        border_color: s.RGBA | str | None = None,
        title: str | None = None,
        title_alignment: str = "left",
        # Focus
        focused: bool = False,
        # Border sides
        border_top: bool = True,
        border_right: bool = True,
        border_bottom: bool = True,
        border_left: bool = True,
        border_chars: dict | None = None,
        # Overflow
        overflow: str = "visible",
        # Visibility
        visible: bool = True,
        opacity: float = 1.0,
    ):
        super().__init__(
            key=key,
            overflow=overflow,
            width=width,
            height=height,
            min_width=min_width,
            min_height=min_height,
            max_width=max_width,
            max_height=max_height,
            flex_grow=flex_grow,
            flex_shrink=flex_shrink,
            flex_basis=flex_basis,
            flex_direction=flex_direction,
            flex_wrap=flex_wrap,
            justify_content=justify_content,
            align_items=align_items,
            align_self=align_self,
            gap=gap,
            padding=padding,
            padding_top=padding_top,
            padding_right=padding_right,
            padding_bottom=padding_bottom,
            padding_left=padding_left,
            margin=margin,
            margin_top=margin_top,
            margin_right=margin_right,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            background_color=background_color,
            fg=fg,
            border=border,
            border_style=border_style,
            border_color=border_color,
            title=title,
            title_alignment=title_alignment,
            focused=focused,
            border_top=border_top,
            border_right=border_right,
            border_bottom=border_bottom,
            border_left=border_left,
            border_chars=border_chars,
            visible=visible,
            opacity=opacity,
        )

        # Add children (both positional and keyword)
        all_children = list(children) if children else []
        for child in all_children:
            if isinstance(child, Renderable):
                self.add(child)
            elif isinstance(child, str):
                from .text import Text

                self.add(Text(child))
            else:
                # Try to render as text
                from .text import Text

                self.add(Text(str(child)))

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the box with border."""
        if not self._visible:
            return

        # Get dimensions (yoga-computed layout, not the original prop)
        width = self._layout_width or buffer.width
        height = self._layout_height or buffer.height

        # Draw border if enabled
        if self._border and width > 0 and height > 0:
            self._draw_border(buffer, width, height)

        # Draw focus ring if focused
        if self._focused and width > 0 and height > 0:
            self._draw_focus_ring(buffer, width, height)

        # Draw background for the box
        if self._background_color:
            bg_x = self._x if not self._border else self._x + 1
            bg_y = self._y if not self._border else self._y + 1
            bg_w = width - (2 if self._border else 0)
            bg_h = height - (2 if self._border else 0)
            if bg_w > 0 and bg_h > 0:
                buffer.fill_rect(bg_x, bg_y, bg_w, bg_h, self._background_color)

        # Clip children to box bounds when overflow is hidden
        clip = self._overflow == "hidden"
        if clip:
            buffer.push_scissor_rect(self._x, self._y, width, height)

        # Render children at their yoga-computed absolute positions
        for child in self._children:
            if isinstance(child, Renderable):
                child.render(buffer, delta_time)

        if clip:
            buffer.pop_scissor_rect()

    def _get_border_chars(self) -> dict:
        """Get border characters with validation."""
        if self._border_chars:
            required_keys = {
                "top_left",
                "top_right",
                "bottom_left",
                "bottom_right",
                "horizontal",
                "vertical",
            }
            if required_keys.issubset(self._border_chars.keys()):
                return self._border_chars
        return BORDER_CHARS.get(self._border_style, BORDER_CHARS["single"])

    def _draw_border(self, buffer: Buffer, width: int, height: int) -> None:
        """Draw the box border."""
        chars = self._get_border_chars()

        border_color = self._border_color or self._fg
        bg = self._background_color

        # Top border
        if self._border_top and width > 2:
            # Left corner
            if self._border_left:
                buffer.draw_text(chars["top_left"], self._x, self._y, border_color, bg)
            # Horizontal line
            start_x = self._x + (1 if self._border_left else 0)
            end_x = self._x + width - (1 if self._border_right else 0)
            if end_x > start_x:
                buffer.draw_text(
                    chars["horizontal"] * (end_x - start_x), start_x, self._y, border_color, bg
                )
            # Right corner
            if self._border_right:
                buffer.draw_text(chars["top_right"], self._x + width - 1, self._y, border_color, bg)

        # Bottom border
        if self._border_bottom and height > 2:
            # Left corner
            if self._border_left:
                buffer.draw_text(
                    chars["bottom_left"], self._x, self._y + height - 1, border_color, bg
                )
            # Horizontal line
            start_x = self._x + (1 if self._border_left else 0)
            end_x = self._x + width - (1 if self._border_right else 0)
            if end_x > start_x:
                buffer.draw_text(
                    chars["horizontal"] * (end_x - start_x),
                    start_x,
                    self._y + height - 1,
                    border_color,
                    bg,
                )
            # Right corner
            if self._border_right:
                buffer.draw_text(
                    chars["bottom_right"],
                    self._x + width - 1,
                    self._y + height - 1,
                    border_color,
                    bg,
                )

        # Left and right borders
        if self._border_left or self._border_right:
            top_y = self._y + (1 if self._border_top else 0)
            bottom_y = self._y + height - (1 if self._border_bottom else 0)
            for y in range(top_y, bottom_y):
                if self._border_left:
                    buffer.draw_text(chars["vertical"], self._x, y, border_color, bg)
                if self._border_right:
                    buffer.draw_text(chars["vertical"], self._x + width - 1, y, border_color, bg)

        # Title (only if top border is drawn)
        if self._title and self._border_top:
            title_x = self._x + 1
            if self._title_alignment == "center":
                title_x = self._x + (width - len(self._title)) // 2
            elif self._title_alignment == "right":
                title_x = self._x + width - len(self._title) - 2

            buffer.draw_text(self._title, title_x, self._y, border_color, bg)

    def _draw_focus_ring(self, buffer: Buffer, width: int, height: int) -> None:
        """Draw a focus ring around the box."""
        focus_color = s.RGBA(0.3, 0.5, 1.0, 1.0)

        # Top edge
        for x in range(self._x, self._x + width):
            buffer.draw_text("─", x, self._y - 1 if self._y > 0 else self._y, focus_color, None)

        # Bottom edge
        for x in range(self._x, self._x + width):
            buffer.draw_text("─", x, self._y + height, focus_color, None)

        # Left edge
        for y in range(self._y, self._y + height):
            buffer.draw_text("│", self._x - 1 if self._x > 0 else self._x, y, focus_color, None)

        # Right edge
        for y in range(self._y, self._y + height):
            buffer.draw_text("│", self._x + width, y, focus_color, None)

        # Corners
        if self._x > 0:
            buffer.draw_text(
                "┌", self._x - 1, self._y - 1 if self._y > 0 else self._y, focus_color, None
            )
            buffer.draw_text("└", self._x - 1, self._y + height, focus_color, None)
        if self._x + width < buffer.width:
            buffer.draw_text(
                "┐", self._x + width, self._y - 1 if self._y > 0 else self._y, focus_color, None
            )
            buffer.draw_text("┘", self._x + width, self._y + height, focus_color, None)


class ScrollBox(Box):
    """Scrollable container with offset-based scrolling.

    Uses buffer-level translation (like OpenCode's translateY) for smooth
    scrolling that never triggers yoga layout recomputation.  All children
    stay in the tree — content is shifted via a drawing offset and clipped
    to the viewport via scissor rect.

    Usage:
        scroll = ScrollBox(
            *children,
            scroll_offset_y=current_scroll,
            scroll_y=True,
            flex_grow=1,
        )
    """

    def __init__(
        self,
        *children: Any,
        # Scroll options
        scroll_x: bool = False,
        scroll_y: bool = True,
        sticky_scroll: bool = False,
        sticky_start: str | None = None,
        scroll_acceleration: Any | None = None,
        scroll_offset_x: int = 0,
        scroll_offset_y: int = 0,
        scroll_offset_y_fn: Callable[[], int] | None = None,
        # Box options
        **kwargs,
    ):
        kwargs.setdefault("overflow", "hidden")
        super().__init__(*children, **kwargs)

        self._scroll_x = scroll_x
        self._scroll_y = scroll_y
        self._sticky_scroll = sticky_scroll
        self._sticky_start = sticky_start
        self._scroll_acceleration = scroll_acceleration or LinearScrollAccel()
        self._scroll_offset_x = scroll_offset_x
        self._scroll_offset_y = scroll_offset_y
        self._scroll_offset_y_fn = scroll_offset_y_fn
        self._scroll_accumulator_x = 0.0
        self._scroll_accumulator_y = 0.0
        self._scroll_width = 0
        self._scroll_height = 0
        self._viewport_width = 0
        self._viewport_height = 0
        self._has_manual_scroll = False
        self._is_applying_sticky_scroll = False
        self._sticky_scroll_top = False
        self._sticky_scroll_bottom = False
        self._sticky_scroll_left = False
        self._sticky_scroll_right = False
        self._is_scroll_target = True

    @property
    def scroll_x(self) -> bool:
        return self._scroll_x

    @property
    def scroll_y(self) -> bool:
        return self._scroll_y

    @property
    def scroll_offset_x(self) -> int:
        return self._scroll_offset_x

    @property
    def scroll_offset_y(self) -> int:
        return self._scroll_offset_y

    @property
    def scroll_height(self) -> int:
        return self._scroll_height

    @property
    def viewport_height(self) -> int:
        return self._viewport_height

    @property
    def has_manual_scroll(self) -> bool:
        return self._has_manual_scroll

    def is_at_bottom(self) -> bool:
        return self._scroll_offset_y >= self._max_scroll_y()

    def scroll_to(self, x: int = 0, y: int = 0) -> None:
        """Scroll to position. Has no visible effect when scroll_offset_y_fn is set."""
        self._set_scroll_offsets(x=x, y=y, mark_manual=True)

    def scroll_by(self, delta_x: int = 0, delta_y: int = 0) -> None:
        """Scroll by delta amount. Has no visible effect when scroll_offset_y_fn is set."""
        self._set_scroll_offsets(
            x=self._scroll_offset_x + delta_x,
            y=self._scroll_offset_y + delta_y,
            mark_manual=True,
        )

    def reset_sticky_scroll(self) -> None:
        """Re-enable sticky auto-follow at the configured sticky edge."""
        self._has_manual_scroll = False
        if self._sticky_scroll and self._sticky_start:
            self._apply_sticky_start(self._sticky_start)

    def _viewport_inner_size(self) -> tuple[int, int]:
        width = int(self._layout_width or 0)
        height = int(self._layout_height or 0)
        if self._border:
            width = max(0, width - int(self._border_left) - int(self._border_right))
            height = max(0, height - int(self._border_top) - int(self._border_bottom))
        return width, height

    def _measure_content(self) -> tuple[int, int]:
        width = 0
        height = 0
        origin_x = self._x
        origin_y = self._y

        def visit(node: Renderable) -> None:
            nonlocal width, height
            node_w = int(node._layout_width or 0)
            node_h = int(node._layout_height or 0)
            width = max(width, node._x + node_w - origin_x)
            height = max(height, node._y + node_h - origin_y)
            for child in node.get_children():
                if isinstance(child, Renderable):
                    visit(child)

        for child in self._children:
            if isinstance(child, Renderable):
                visit(child)
        return width, height

    def _max_scroll_x(self) -> int:
        return max(0, self._scroll_width - self._viewport_width)

    def _max_scroll_y(self) -> int:
        return max(0, self._scroll_height - self._viewport_height)

    def _is_at_sticky_position(self, *, offset_x: int | None = None, offset_y: int | None = None) -> bool:
        if not self._sticky_scroll or not self._sticky_start:
            return False

        scroll_x = self._scroll_offset_x if offset_x is None else offset_x
        scroll_y = self._scroll_offset_y if offset_y is None else offset_y

        if self._sticky_start == "top":
            return scroll_y <= 0
        if self._sticky_start == "bottom":
            return scroll_y >= self._max_scroll_y()
        if self._sticky_start == "left":
            return scroll_x <= 0
        if self._sticky_start == "right":
            return scroll_x >= self._max_scroll_x()
        return False

    def _update_sticky_state(self) -> None:
        if not self._sticky_scroll:
            return

        max_scroll_y = self._max_scroll_y()
        max_scroll_x = self._max_scroll_x()

        if self._scroll_offset_y <= 0:
            self._sticky_scroll_top = True
            self._sticky_scroll_bottom = False
            if not self._is_applying_sticky_scroll and (
                self._sticky_start == "top" or (self._sticky_start == "bottom" and max_scroll_y == 0)
            ):
                self._has_manual_scroll = False
        elif self._scroll_offset_y >= max_scroll_y:
            self._sticky_scroll_top = False
            self._sticky_scroll_bottom = True
            if not self._is_applying_sticky_scroll and self._sticky_start == "bottom":
                self._has_manual_scroll = False
        else:
            self._sticky_scroll_top = False
            self._sticky_scroll_bottom = False

        if self._scroll_offset_x <= 0:
            self._sticky_scroll_left = True
            self._sticky_scroll_right = False
            if not self._is_applying_sticky_scroll and (
                self._sticky_start == "left" or (self._sticky_start == "right" and max_scroll_x == 0)
            ):
                self._has_manual_scroll = False
        elif self._scroll_offset_x >= max_scroll_x:
            self._sticky_scroll_left = False
            self._sticky_scroll_right = True
            if not self._is_applying_sticky_scroll and self._sticky_start == "right":
                self._has_manual_scroll = False
        else:
            self._sticky_scroll_left = False
            self._sticky_scroll_right = False

    def _apply_sticky_start(self, sticky_start: str) -> None:
        was_applying = self._is_applying_sticky_scroll
        self._is_applying_sticky_scroll = True
        try:
            if sticky_start == "top":
                self._scroll_offset_y = 0
                self._sticky_scroll_top = True
                self._sticky_scroll_bottom = False
            elif sticky_start == "bottom":
                self._scroll_offset_y = self._max_scroll_y()
                self._sticky_scroll_top = False
                self._sticky_scroll_bottom = True
            elif sticky_start == "left":
                self._scroll_offset_x = 0
                self._sticky_scroll_left = True
                self._sticky_scroll_right = False
            elif sticky_start == "right":
                self._scroll_offset_x = self._max_scroll_x()
                self._sticky_scroll_left = False
                self._sticky_scroll_right = True
        finally:
            self._is_applying_sticky_scroll = was_applying

    def _sync_scroll_metrics(self) -> None:
        viewport_width, viewport_height = self._viewport_inner_size()
        content_width, content_height = self._measure_content()

        self._viewport_width = viewport_width
        self._viewport_height = viewport_height
        self._scroll_width = max(viewport_width, content_width)
        self._scroll_height = max(viewport_height, content_height)

        self._scroll_offset_x = min(self._scroll_offset_x, self._max_scroll_x())
        self._scroll_offset_y = min(self._scroll_offset_y, self._max_scroll_y())

        if self._sticky_scroll:
            if self._sticky_start and not self._has_manual_scroll:
                self._apply_sticky_start(self._sticky_start)
            else:
                if self._sticky_scroll_top:
                    self._scroll_offset_y = 0
                elif self._sticky_scroll_bottom:
                    self._scroll_offset_y = self._max_scroll_y()
                if self._sticky_scroll_left:
                    self._scroll_offset_x = 0
                elif self._sticky_scroll_right:
                    self._scroll_offset_x = self._max_scroll_x()

        self._update_sticky_state()

    def _set_scroll_offsets(
        self,
        *,
        x: int | None = None,
        y: int | None = None,
        mark_manual: bool,
    ) -> bool:
        self._sync_scroll_metrics()
        changed = False

        if x is not None and self._scroll_x:
            new_x = min(self._max_scroll_x(), max(0, int(x)))
            if new_x != self._scroll_offset_x:
                self._scroll_offset_x = new_x
                changed = True
        if y is not None and self._scroll_y:
            new_y = min(self._max_scroll_y(), max(0, int(y)))
            if new_y != self._scroll_offset_y:
                self._scroll_offset_y = new_y
                changed = True

        if changed and mark_manual and not self._is_applying_sticky_scroll:
            if (self._max_scroll_y() > 1 or self._max_scroll_x() > 1) and not self._is_at_sticky_position():
                self._has_manual_scroll = True

        self._update_sticky_state()
        return changed

    def _handle_mouse_scroll(self, event: Any) -> None:
        if self._scroll_offset_y_fn is not None:
            return
        if not self.contains_point(event.x, event.y):
            return

        direction = getattr(event, "scroll_direction", None)
        if direction is None:
            direction = "down" if getattr(event, "scroll_delta", 0) > 0 else "up"

        scroll_amount = abs(getattr(event, "scroll_delta", 0) or 1)
        multiplier = self._scroll_acceleration.tick(time.monotonic() * 1000.0)
        total_amount = scroll_amount * multiplier

        # Snap cleanly to the sticky edge near the boundary to avoid the
        # small residual-accumulator bobble when the user returns to bottom.
        if direction == "up" and self._scroll_y and self._scroll_offset_y <= 1:
            self._set_scroll_offsets(y=0, mark_manual=True)
            self._scroll_accumulator_y = 0.0
            event.stop_propagation()
            return
        if direction == "down" and self._scroll_y and self._max_scroll_y() - self._scroll_offset_y <= 1:
            self._set_scroll_offsets(y=self._max_scroll_y(), mark_manual=True)
            self._scroll_accumulator_y = 0.0
            event.stop_propagation()
            return

        if direction == "up" and self._scroll_y:
            self._scroll_accumulator_y -= total_amount
            integer_scroll = math.trunc(self._scroll_accumulator_y)
            if integer_scroll != 0:
                moved = self._set_scroll_offsets(
                    y=self._scroll_offset_y + integer_scroll,
                    mark_manual=True,
                )
                self._scroll_accumulator_y -= integer_scroll
                if not moved:
                    self._scroll_accumulator_y = 0.0
        elif direction == "down" and self._scroll_y:
            self._scroll_accumulator_y += total_amount
            integer_scroll = math.trunc(self._scroll_accumulator_y)
            if integer_scroll != 0:
                moved = self._set_scroll_offsets(
                    y=self._scroll_offset_y + integer_scroll,
                    mark_manual=True,
                )
                self._scroll_accumulator_y -= integer_scroll
                if not moved:
                    self._scroll_accumulator_y = 0.0

        if direction == "up" and self._scroll_offset_y <= 0:
            self._scroll_accumulator_y = 0.0
        if direction == "down" and self._scroll_offset_y >= self._max_scroll_y():
            self._scroll_accumulator_y = 0.0

        event.stop_propagation()

    def handle_scroll_event(self, event: Any) -> None:
        """Handle a wheel/trackpad scroll event as an owned scroll target."""
        self._handle_mouse_scroll(event)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render with buffer-offset scrolling (like OpenCode's translateY).

        Flow:
        1. Draw border & background (unaffected by scroll)
        2. Push scissor rect for viewport clipping
        3. Push drawing offset = -scroll_offset (the translateY equivalent)
        4. Render children at their yoga positions (offset shifts them)
        5. Pop offset, pop scissor
        """
        if not self._visible:
            return

        width = self._layout_width or buffer.width
        height = self._layout_height or buffer.height
        self._sync_scroll_metrics()

        # Draw border (unaffected by scroll)
        if self._border and width > 0 and height > 0:
            self._draw_border(buffer, width, height)

        if self._focused and width > 0 and height > 0:
            self._draw_focus_ring(buffer, width, height)

        # Draw background (unaffected by scroll)
        if self._background_color:
            bg_x = self._x if not self._border else self._x + 1
            bg_y = self._y if not self._border else self._y + 1
            bg_w = width - (2 if self._border else 0)
            bg_h = height - (2 if self._border else 0)
            if bg_w > 0 and bg_h > 0:
                buffer.fill_rect(bg_x, bg_y, bg_w, bg_h, self._background_color)

        # Push scissor for viewport clipping (BEFORE offset so it's in
        # absolute screen coordinates — matching OpenCode's viewport
        # overflow:hidden)
        buffer.push_scissor_rect(self._x, self._y, width, height)

        # Push scroll offset as a drawing translation.
        # This is the Python equivalent of OpenCode's:
        #   this.content.translateY = -position
        # If scroll_offset_fn is provided, call it at render time to get
        # the current offset — this bypasses the signal system entirely.
        offset_y = int(self._scroll_offset_y_fn()) if self._scroll_offset_y_fn else self._scroll_offset_y
        offset_dx = -self._scroll_offset_x if self._scroll_x else 0
        offset_dy = -offset_y if self._scroll_y else 0
        buffer.push_offset(offset_dx, offset_dy)

        # Render children at their yoga-computed positions.
        # The buffer offset transparently shifts all drawing (including
        # grandchildren) without changing any yoga layout properties.
        for child in self._children:
            if isinstance(child, Renderable):
                child.render(buffer, delta_time)

        buffer.pop_offset()
        buffer.pop_scissor_rect()


__all__ = [
    "Box",
    "LinearScrollAccel",
    "MacOSScrollAccel",
    "ScrollBox",
]
