"""ScrollBox state and sticky-scroll helpers."""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any

from ..events import MouseButton


def scroll_to_element(scrollbox: Any, renderable: Any) -> None:
    target_y = int(getattr(renderable, "_y", 0))
    target_x = int(getattr(renderable, "_x", 0))
    target_h = int(getattr(renderable, "_layout_height", 0) or 0)
    target_w = int(getattr(renderable, "_layout_width", 0) or 0)
    node = getattr(renderable, "_parent", None)
    content = scrollbox._scroll_content
    while node is not None and node is not content and node is not scrollbox:
        target_y += int(getattr(node, "_y", 0))
        target_x += int(getattr(node, "_x", 0))
        node = getattr(node, "_parent", None)

    vw, vh = viewport_inner_size(scrollbox)
    if target_y < scrollbox._scroll_offset_y:
        scrollbox.scroll_to(x=scrollbox._scroll_offset_x, y=target_y)
    elif target_y + target_h > scrollbox._scroll_offset_y + vh:
        scrollbox.scroll_to(x=scrollbox._scroll_offset_x, y=target_y + target_h - vh)
    if target_x < scrollbox._scroll_offset_x:
        scrollbox.scroll_to(x=target_x, y=scrollbox._scroll_offset_y)
    elif target_x + target_w > scrollbox._scroll_offset_x + vw:
        scrollbox.scroll_to(x=target_x + target_w - vw, y=scrollbox._scroll_offset_y)


def viewport_inner_size(scrollbox: Any) -> tuple[int, int]:
    width = int(scrollbox._layout_width or 0)
    height = int(scrollbox._layout_height or 0)
    if scrollbox._border:
        width = max(0, width - int(scrollbox._border_left) - int(scrollbox._border_right))
        height = max(0, height - int(scrollbox._border_top) - int(scrollbox._border_bottom))
    return width, height


def measure_content(scrollbox: Any) -> tuple[int, int]:
    content = scrollbox._scroll_content
    return (
        int(getattr(content, "_layout_width", 0) or 0),
        int(getattr(content, "_layout_height", 0) or 0),
    )


def max_scroll_x(scrollbox: Any) -> int:
    return max(0, scrollbox._scroll_width - scrollbox._viewport_width)


def max_scroll_y(scrollbox: Any) -> int:
    return max(0, scrollbox._scroll_height - scrollbox._viewport_height)


def is_at_sticky_position(
    scrollbox: Any,
    *,
    offset_x: int | None = None,
    offset_y: int | None = None,
) -> bool:
    if not scrollbox._sticky_scroll or not scrollbox._sticky_start:
        return False

    scroll_x = scrollbox._scroll_offset_x if offset_x is None else offset_x
    scroll_y = scrollbox._scroll_offset_y if offset_y is None else offset_y
    threshold = scrollbox._sticky_threshold

    if scrollbox._sticky_start == "top":
        return scroll_y <= threshold
    if scrollbox._sticky_start == "bottom":
        return scroll_y >= max_scroll_y(scrollbox) - threshold
    if scrollbox._sticky_start == "left":
        return scroll_x <= threshold
    if scrollbox._sticky_start == "right":
        return scroll_x >= max_scroll_x(scrollbox) - threshold
    return False


def update_sticky_state(scrollbox: Any) -> None:
    if not scrollbox._sticky_scroll:
        return

    scroll_max_y = max_scroll_y(scrollbox)
    scroll_max_x = max_scroll_x(scrollbox)
    threshold = scrollbox._sticky_threshold

    if scrollbox._scroll_offset_y <= 0:
        scrollbox._sticky_scroll_top = True
        scrollbox._sticky_scroll_bottom = False
        if not scrollbox._is_applying_sticky_scroll and (
            scrollbox._sticky_start == "top"
            or (scrollbox._sticky_start == "bottom" and scroll_max_y == 0)
        ):
            scrollbox._has_manual_scroll = False
    elif scrollbox._scroll_offset_y >= scroll_max_y - threshold:
        scrollbox._sticky_scroll_top = False
        scrollbox._sticky_scroll_bottom = True
        if not scrollbox._is_applying_sticky_scroll and scrollbox._sticky_start == "bottom":
            scrollbox._has_manual_scroll = False
    else:
        scrollbox._sticky_scroll_top = False
        scrollbox._sticky_scroll_bottom = False

    if scrollbox._scroll_offset_x <= 0:
        scrollbox._sticky_scroll_left = True
        scrollbox._sticky_scroll_right = False
        if not scrollbox._is_applying_sticky_scroll and (
            scrollbox._sticky_start == "left"
            or (scrollbox._sticky_start == "right" and scroll_max_x == 0)
        ):
            scrollbox._has_manual_scroll = False
    elif scrollbox._scroll_offset_x >= scroll_max_x - threshold:
        scrollbox._sticky_scroll_left = False
        scrollbox._sticky_scroll_right = True
        if not scrollbox._is_applying_sticky_scroll and scrollbox._sticky_start == "right":
            scrollbox._has_manual_scroll = False
    else:
        scrollbox._sticky_scroll_left = False
        scrollbox._sticky_scroll_right = False


def apply_sticky_start(scrollbox: Any, sticky_start: str) -> None:
    was_applying = scrollbox._is_applying_sticky_scroll
    scrollbox._is_applying_sticky_scroll = True
    try:
        if sticky_start == "top":
            scrollbox._scroll_offset_y = 0
            scrollbox._sticky_scroll_top = True
            scrollbox._sticky_scroll_bottom = False
        elif sticky_start == "bottom":
            scrollbox._scroll_offset_y = max_scroll_y(scrollbox)
            scrollbox._sticky_scroll_top = False
            scrollbox._sticky_scroll_bottom = True
        elif sticky_start == "left":
            scrollbox._scroll_offset_x = 0
            scrollbox._sticky_scroll_left = True
            scrollbox._sticky_scroll_right = False
        elif sticky_start == "right":
            scrollbox._scroll_offset_x = max_scroll_x(scrollbox)
            scrollbox._sticky_scroll_left = False
            scrollbox._sticky_scroll_right = True
    finally:
        scrollbox._is_applying_sticky_scroll = was_applying


def sync_scroll_metrics(scrollbox: Any) -> None:
    viewport_width, viewport_height = viewport_inner_size(scrollbox)
    content_width, content_height = measure_content(scrollbox)

    scrollbox._viewport_width = viewport_width
    scrollbox._viewport_height = viewport_height
    scrollbox._scroll_width = max(viewport_width, content_width)
    scrollbox._scroll_height = max(viewport_height, content_height)

    scrollbox._scroll_offset_x = min(scrollbox._scroll_offset_x, max_scroll_x(scrollbox))
    scrollbox._scroll_offset_y = min(scrollbox._scroll_offset_y, max_scroll_y(scrollbox))

    if scrollbox._sticky_scroll:
        new_max_y = max_scroll_y(scrollbox)
        new_max_x = max_scroll_x(scrollbox)
        if scrollbox._sticky_start and not scrollbox._has_manual_scroll:
            apply_sticky_start(scrollbox, scrollbox._sticky_start)
        else:
            if scrollbox._sticky_scroll_top:
                scrollbox._scroll_offset_y = 0
            elif scrollbox._sticky_scroll_bottom and new_max_y > 0:
                scrollbox._scroll_offset_y = new_max_y
            if scrollbox._sticky_scroll_left:
                scrollbox._scroll_offset_x = 0
            elif scrollbox._sticky_scroll_right and new_max_x > 0:
                scrollbox._scroll_offset_x = new_max_x


def set_scroll_offsets(
    scrollbox: Any,
    *,
    x: int | None = None,
    y: int | None = None,
    mark_manual: bool,
) -> bool:
    sync_scroll_metrics(scrollbox)
    changed = False

    if x is not None and scrollbox._scroll_x:
        new_x = min(max_scroll_x(scrollbox), max(0, int(x)))
        if new_x != scrollbox._scroll_offset_x:
            scrollbox._scroll_offset_x = new_x
            changed = True
    if y is not None and scrollbox._scroll_y:
        new_y = min(max_scroll_y(scrollbox), max(0, int(y)))
        if new_y != scrollbox._scroll_offset_y:
            scrollbox._scroll_offset_y = new_y
            changed = True

    if (
        changed
        and mark_manual
        and not scrollbox._is_applying_sticky_scroll
        and (max_scroll_y(scrollbox) > 1 or max_scroll_x(scrollbox) > 1)
        and not is_at_sticky_position(scrollbox)
    ):
        scrollbox._has_manual_scroll = True

    if changed:
        scrollbox.mark_hit_paint_dirty()

    update_sticky_state(scrollbox)
    return changed


def apply_scroll_axis(scrollbox: Any, signed_amount: float, axis: str) -> None:
    if axis == "y":
        scrollbox._scroll_accumulator_y += signed_amount
        integer_scroll = math.trunc(scrollbox._scroll_accumulator_y)
        if integer_scroll != 0:
            moved = set_scroll_offsets(
                scrollbox,
                y=scrollbox._scroll_offset_y + integer_scroll,
                mark_manual=True,
            )
            scrollbox._scroll_accumulator_y -= integer_scroll
            if not moved:
                scrollbox._scroll_accumulator_y = 0.0
    else:
        scrollbox._scroll_accumulator_x += signed_amount
        integer_scroll = math.trunc(scrollbox._scroll_accumulator_x)
        if integer_scroll != 0:
            moved = set_scroll_offsets(
                scrollbox,
                x=scrollbox._scroll_offset_x + integer_scroll,
                mark_manual=True,
            )
            scrollbox._scroll_accumulator_x -= integer_scroll
            if not moved:
                scrollbox._scroll_accumulator_x = 0.0


def handle_mouse_scroll(scrollbox: Any, event: Any) -> None:
    if scrollbox._scroll_offset_y_fn is not None:
        return
    if not scrollbox.contains_point(event.x, event.y):
        return

    direction = getattr(event, "scroll_direction", None)
    if direction is None:
        button = getattr(event, "button", None)
        if button == MouseButton.WHEEL_LEFT:
            direction = "left"
        elif button == MouseButton.WHEEL_RIGHT:
            direction = "right"
        else:
            direction = "down" if getattr(event, "scroll_delta", 0) > 0 else "up"
    if getattr(event, "shift", False):
        if direction == "up":
            direction = "left"
        elif direction == "down":
            direction = "right"
        elif direction == "left":
            direction = "up"
        elif direction == "right":
            direction = "down"

    scroll_amount = abs(getattr(event, "scroll_delta", 0) or 1)
    multiplier = scrollbox._scroll_acceleration.tick(time.monotonic() * 1000.0)
    total_amount = scroll_amount * multiplier
    if direction in ("up", "down") and scrollbox._scroll_y:
        sign = -1 if direction == "up" else 1
        apply_scroll_axis(scrollbox, total_amount * sign, "y")
    elif direction in ("left", "right") and scrollbox._scroll_x:
        sign = -1 if direction == "left" else 1
        apply_scroll_axis(scrollbox, total_amount * sign, "x")

    if direction == "up" and scrollbox._scroll_offset_y <= 0:
        scrollbox._scroll_accumulator_y = 0.0
        scrollbox._scroll_acceleration.reset()
    if direction == "down" and scrollbox._scroll_offset_y >= max_scroll_y(scrollbox):
        scrollbox._scroll_accumulator_y = 0.0
        scrollbox._scroll_acceleration.reset()
    if direction == "left" and scrollbox._scroll_offset_x <= 0:
        scrollbox._scroll_accumulator_x = 0.0
        scrollbox._scroll_acceleration.reset()
    if direction == "right" and scrollbox._scroll_offset_x >= max_scroll_x(scrollbox):
        scrollbox._scroll_accumulator_x = 0.0
        scrollbox._scroll_acceleration.reset()

    event.stop_propagation()


class LinearScrollAccel:
    def tick(self, _now_ms: float | None = None) -> float:
        return 1.0

    def reset(self) -> None:
        return None


class MacOSScrollAccel:
    """macOS-inspired scroll acceleration."""

    _HISTORY_SIZE = 3
    _STREAK_TIMEOUT = 150
    _MIN_TICK_INTERVAL = 6
    _REFERENCE_INTERVAL = 100

    def __init__(self, *, amplitude: float = 0.8, tau: float = 3.0, max_multiplier: float = 6.0):
        self._amplitude = amplitude
        self._tau = tau
        self._max_multiplier = max_multiplier
        self._last_tick_ms = 0.0
        self._history: deque[float] = deque(maxlen=self._HISTORY_SIZE)

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

        avg_interval = sum(self._history) / len(self._history)
        velocity = self._REFERENCE_INTERVAL / avg_interval
        x = velocity / self._tau
        multiplier = 1.0 + self._amplitude * (math.exp(x) - 1.0)
        return min(multiplier, self._max_multiplier)

    def reset(self) -> None:
        self._last_tick_ms = 0.0
        self._history.clear()


__all__ = [
    "LinearScrollAccel",
    "MacOSScrollAccel",
    "apply_scroll_axis",
    "apply_sticky_start",
    "handle_mouse_scroll",
    "is_at_sticky_position",
    "max_scroll_x",
    "max_scroll_y",
    "measure_content",
    "scroll_to_element",
    "set_scroll_offsets",
    "sync_scroll_metrics",
    "update_sticky_state",
    "viewport_inner_size",
]
