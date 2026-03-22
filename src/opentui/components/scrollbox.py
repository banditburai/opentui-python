"""ScrollBox component - scrollable container with offset-based scrolling."""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..events import MouseButton
from .base import BaseRenderable
from .box import Box, _normalize_box_child

if TYPE_CHECKING:
    from ..renderer import Buffer

# Lazy-cached import of For (avoids circular import at module level)
_For_cls: type | None = None


class LinearScrollAccel:
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


class ScrollContent(Box):
    """Explicit layout/content container for ScrollBox.

    ScrollBox owns viewport, scrolling state, clipping, and shell semantics.
    ScrollContent owns the scrollable child layout.
    """

    def __init__(self, *children: Any, **kwargs):
        kwargs.setdefault("flex_shrink", 0)
        kwargs.setdefault("align_self", "flex-start")
        super().__init__(*children, **kwargs)


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
        content: ScrollContent | Box | None = None,
        # Scroll options
        scroll_x: bool = False,
        scroll_y: bool = True,
        sticky_scroll: bool = False,
        sticky_start: str | None = None,
        sticky_threshold: int = 0,
        scroll_acceleration: Any | None = None,
        scroll_offset_x: int = 0,
        scroll_offset_y: int = 0,
        scroll_offset_y_fn: Callable[[], int] | None = None,
        desired_scroll_y: int | None = None,
        # Box options
        **kwargs,
    ):
        content_kwargs: dict[str, Any] = {}
        for key in (
            "flex_direction",
            "flex_wrap",
            "justify_content",
            "align_items",
            "gap",
            "padding",
            "padding_top",
            "padding_right",
            "padding_bottom",
            "padding_left",
            "padding_x",
            "padding_y",
        ):
            if key in kwargs:
                content_kwargs[key] = kwargs.pop(key)

        kwargs.setdefault("overflow", "hidden")
        kwargs.setdefault("flex_direction", "column")
        kwargs.setdefault("justify_content", "flex-start")
        kwargs.setdefault("align_items", "stretch")
        kwargs.setdefault("gap", 0)
        kwargs.setdefault("padding", 0)
        super().__init__(**kwargs)

        self._scroll_x = scroll_x
        self._scroll_y = scroll_y
        self._sticky_scroll = sticky_scroll
        self._sticky_start = sticky_start
        self._sticky_threshold = sticky_threshold
        self._scroll_acceleration = scroll_acceleration or LinearScrollAccel()
        self._scroll_offset_x = scroll_offset_x
        self._scroll_offset_y = scroll_offset_y
        self._scroll_offset_y_fn = scroll_offset_y_fn
        self._desired_scroll_y = desired_scroll_y
        self._last_applied_desired_y = None
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
        # Register _on_mouse_scroll so the tree-dispatch path can find us
        # (matches OpenTUI core processMouseEvent propagation for scroll events).
        self._on_mouse_scroll = self._handle_mouse_scroll
        explicit_content = content
        normalized_children: list[BaseRenderable] = []
        if children:
            for child in children:
                normalized_children.extend(_normalize_box_child(child))

        if (
            explicit_content is None
            and len(normalized_children) == 1
            and isinstance(normalized_children[0], ScrollContent)
        ):
            explicit_content = normalized_children[0]
            normalized_children = []

        if explicit_content is None:
            explicit_content = ScrollContent(
                *normalized_children,
                min_width="100%",
                max_width=None if scroll_x else "100%",
                max_height=None if scroll_y else "100%",
                **content_kwargs,
            )
        else:
            if content_kwargs:
                keys = ", ".join(sorted(content_kwargs))
                raise TypeError(
                    "ScrollBox content layout props must be defined on ScrollContent "
                    f"when using explicit content. Move these props to ScrollContent: {keys}"
                )
            if normalized_children:
                explicit_content.add_children(normalized_children)
            explicit_content.min_width = "100%"
            explicit_content.max_width = None if scroll_x else "100%"
            explicit_content.max_height = None if scroll_y else "100%"

        self._scroll_content = explicit_content
        self._scroll_content._host = self
        super().add(self._scroll_content)

    def add(self, child: BaseRenderable | None, index: int | None = None) -> int:
        return self._scroll_content.add(child, index=index)

    def add_children(self, children: list[BaseRenderable]) -> None:
        self._scroll_content.add_children(children)

    def remove(self, child: BaseRenderable) -> None:
        self._scroll_content.remove(child)

    def insert_before(self, child: BaseRenderable | None, anchor: BaseRenderable | None) -> int:
        return self._scroll_content.insert_before(child, anchor)

    def get_children(self) -> tuple[BaseRenderable, ...]:
        return self._scroll_content.get_children()

    def get_children_count(self) -> int:
        return self._scroll_content.get_children_count()

    def get_renderable(self, id: str) -> BaseRenderable | None:
        return self._scroll_content.get_renderable(id)

    @property
    def content(self) -> ScrollContent | Box:
        return self._scroll_content

    def _copy_content_layout_from(self, other: ScrollBox) -> None:
        content = self._scroll_content
        other_content = other._scroll_content
        for attr in (
            "flex_direction",
            "flex_wrap",
            "justify_content",
            "align_items",
            "gap",
            "padding",
            "padding_top",
            "padding_right",
            "padding_bottom",
            "padding_left",
        ):
            setattr(content, attr, getattr(other_content, attr))

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

    @property
    def scroll_top(self) -> int:
        """Alias for scroll_offset_y (scrollBox.scrollTop equivalent)."""
        return self._scroll_offset_y

    @scroll_top.setter
    def scroll_top(self, value: int) -> None:
        self.scroll_to(x=self._scroll_offset_x, y=value)

    @property
    def scroll_left(self) -> int:
        """Alias for scroll_offset_x (scrollBox.scrollLeft equivalent)."""
        return self._scroll_offset_x

    @scroll_left.setter
    def scroll_left(self, value: int) -> None:
        self.scroll_to(x=value, y=self._scroll_offset_y)

    @property
    def scroll_width(self) -> int:
        return self._scroll_width

    @property
    def viewport_width(self) -> int:
        return self._viewport_width

    @property
    def viewport(self) -> dict[str, int]:
        width = int(self._layout_width or 0)
        height = int(self._layout_height or 0)
        return {"x": self._x, "y": self._y, "width": width, "height": height}

    def is_at_bottom(self) -> bool:
        return self._scroll_offset_y >= self._max_scroll_y()

    def scroll_to(self, x: int = 0, y: int = 0) -> None:
        self._set_scroll_offsets(x=x, y=y, mark_manual=True)

    def scroll_by(self, delta_x: int = 0, delta_y: int = 0) -> None:
        self._set_scroll_offsets(
            x=self._scroll_offset_x + delta_x,
            y=self._scroll_offset_y + delta_y,
            mark_manual=True,
        )

    def scroll_to_element(self, renderable: Any) -> None:
        """Scroll to make *renderable* visible within this ScrollBox.

        Calculates the element's position relative to the scroll content
        and adjusts scroll offsets so it falls within the viewport.
        """
        # Walk up the parent chain to accumulate the offset relative to our content
        target_y = int(getattr(renderable, "_y", 0))
        target_x = int(getattr(renderable, "_x", 0))
        target_h = int(getattr(renderable, "_layout_height", 0) or 0)
        target_w = int(getattr(renderable, "_layout_width", 0) or 0)
        node = getattr(renderable, "_parent", None)
        content = self._scroll_content
        while node is not None and node is not content and node is not self:
            target_y += int(getattr(node, "_y", 0))
            target_x += int(getattr(node, "_x", 0))
            node = getattr(node, "_parent", None)

        vw, vh = self._viewport_inner_size()
        # Vertical: ensure element is within viewport
        if target_y < self._scroll_offset_y:
            self.scroll_to(x=self._scroll_offset_x, y=target_y)
        elif target_y + target_h > self._scroll_offset_y + vh:
            self.scroll_to(x=self._scroll_offset_x, y=target_y + target_h - vh)
        # Horizontal: ensure element is within viewport
        if target_x < self._scroll_offset_x:
            self.scroll_to(x=target_x, y=self._scroll_offset_y)
        elif target_x + target_w > self._scroll_offset_x + vw:
            self.scroll_to(x=target_x + target_w - vw, y=self._scroll_offset_y)

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
        content = self._scroll_content
        return (
            int(getattr(content, "_layout_width", 0) or 0),
            int(getattr(content, "_layout_height", 0) or 0),
        )

    def _max_scroll_x(self) -> int:
        return max(0, self._scroll_width - self._viewport_width)

    def _max_scroll_y(self) -> int:
        return max(0, self._scroll_height - self._viewport_height)

    def _is_at_sticky_position(
        self, *, offset_x: int | None = None, offset_y: int | None = None
    ) -> bool:
        if not self._sticky_scroll or not self._sticky_start:
            return False

        scroll_x = self._scroll_offset_x if offset_x is None else offset_x
        scroll_y = self._scroll_offset_y if offset_y is None else offset_y
        th = self._sticky_threshold

        if self._sticky_start == "top":
            return scroll_y <= th
        if self._sticky_start == "bottom":
            return scroll_y >= self._max_scroll_y() - th
        if self._sticky_start == "left":
            return scroll_x <= th
        if self._sticky_start == "right":
            return scroll_x >= self._max_scroll_x() - th
        return False

    def _update_sticky_state(self) -> None:
        if not self._sticky_scroll:
            return

        max_scroll_y = self._max_scroll_y()
        max_scroll_x = self._max_scroll_x()
        th = self._sticky_threshold

        if self._scroll_offset_y <= 0:
            self._sticky_scroll_top = True
            self._sticky_scroll_bottom = False
            if not self._is_applying_sticky_scroll and (
                self._sticky_start == "top"
                or (self._sticky_start == "bottom" and max_scroll_y == 0)
            ):
                self._has_manual_scroll = False
        elif self._scroll_offset_y >= max_scroll_y - th:
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
                self._sticky_start == "left"
                or (self._sticky_start == "right" and max_scroll_x == 0)
            ):
                self._has_manual_scroll = False
        elif self._scroll_offset_x >= max_scroll_x - th:
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
            new_max_y = self._max_scroll_y()
            new_max_x = self._max_scroll_x()
            if self._sticky_start and not self._has_manual_scroll:
                self._apply_sticky_start(self._sticky_start)
            else:
                if self._sticky_scroll_top:
                    self._scroll_offset_y = 0
                elif self._sticky_scroll_bottom and new_max_y > 0:
                    self._scroll_offset_y = new_max_y
                if self._sticky_scroll_left:
                    self._scroll_offset_x = 0
                elif self._sticky_scroll_right and new_max_x > 0:
                    self._scroll_offset_x = new_max_x

        # Note: do NOT call _update_sticky_state() here — it is called only
        # by _set_scroll_offsets() (user-initiated scrolls).  Calling it during
        # content-size recalculation would incorrectly reset _has_manual_scroll
        # when content shrinks and the scroll offset is clamped (issue #709).

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

        if (
            changed
            and mark_manual
            and not self._is_applying_sticky_scroll
            and (self._max_scroll_y() > 1 or self._max_scroll_x() > 1)
            and not self._is_at_sticky_position()
        ):
            self._has_manual_scroll = True

        if changed:
            # Scrolling changes visible content and hit-testing without
            # requiring Yoga reconfiguration.
            self.mark_hit_paint_dirty()

        self._update_sticky_state()
        return changed

    def _apply_scroll_axis(self, signed_amount: float, axis: str) -> None:
        if axis == "y":
            self._scroll_accumulator_y += signed_amount
            integer_scroll = math.trunc(self._scroll_accumulator_y)
            if integer_scroll != 0:
                moved = self._set_scroll_offsets(
                    y=self._scroll_offset_y + integer_scroll,
                    mark_manual=True,
                )
                self._scroll_accumulator_y -= integer_scroll
                if not moved:
                    self._scroll_accumulator_y = 0.0
        else:
            self._scroll_accumulator_x += signed_amount
            integer_scroll = math.trunc(self._scroll_accumulator_x)
            if integer_scroll != 0:
                moved = self._set_scroll_offsets(
                    x=self._scroll_offset_x + integer_scroll,
                    mark_manual=True,
                )
                self._scroll_accumulator_x -= integer_scroll
                if not moved:
                    self._scroll_accumulator_x = 0.0

    def _handle_mouse_scroll(self, event: Any) -> None:
        if self._scroll_offset_y_fn is not None:
            return
        if not self.contains_point(event.x, event.y):
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
        multiplier = self._scroll_acceleration.tick(time.monotonic() * 1000.0)
        total_amount = scroll_amount * multiplier
        if direction in ("up", "down") and self._scroll_y:
            sign = -1 if direction == "up" else 1
            self._apply_scroll_axis(total_amount * sign, "y")
        elif direction in ("left", "right") and self._scroll_x:
            sign = -1 if direction == "left" else 1
            self._apply_scroll_axis(total_amount * sign, "x")

        if direction == "up" and self._scroll_offset_y <= 0:
            self._scroll_accumulator_y = 0.0
            self._scroll_acceleration.reset()
        if direction == "down" and self._scroll_offset_y >= self._max_scroll_y():
            self._scroll_accumulator_y = 0.0
            self._scroll_acceleration.reset()
        if direction == "left" and self._scroll_offset_x <= 0:
            self._scroll_accumulator_x = 0.0
            self._scroll_acceleration.reset()
        if direction == "right" and self._scroll_offset_x >= self._max_scroll_x():
            self._scroll_accumulator_x = 0.0
            self._scroll_acceleration.reset()

        event.stop_propagation()

    def handle_scroll_event(self, event: Any) -> None:
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

        has_opacity = self._opacity < 1.0
        if has_opacity:
            buffer.push_opacity(self._opacity)

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        # Apply scroll target only when the desired position has changed.
        # This prevents overwriting manual (trackpad/mouse) scrolling when
        # the component re-renders with the same desired position.
        if self._desired_scroll_y is not None:
            if self._desired_scroll_y != self._last_applied_desired_y:
                self._scroll_offset_y = self._desired_scroll_y
                self._last_applied_desired_y = self._desired_scroll_y
            self._desired_scroll_y = None

        width = self._layout_width or buffer.width
        height = self._layout_height or buffer.height
        self._sync_scroll_metrics()

        self._render_chrome(buffer, width, height)

        # Push scissor for viewport clipping (BEFORE offset so it's in
        # absolute screen coordinates — matching OpenCode's viewport
        # overflow:hidden)
        buffer.push_scissor_rect(self._x, self._y, width, height)

        # Push scroll offset as a drawing translation.
        # This is the Python equivalent of OpenCode's:
        #   this.content.translateY = -position
        # If scroll_offset_fn is provided, call it at render time to get
        # the current offset — this bypasses the signal system entirely.
        offset_y = (
            int(self._scroll_offset_y_fn()) if self._scroll_offset_y_fn else self._scroll_offset_y
        )
        offset_dx = -self._scroll_offset_x if self._scroll_x else 0
        offset_dy = -offset_y if self._scroll_y else 0
        buffer.push_offset(offset_dx, offset_dy)

        # The buffer offset transparently shifts all drawing (including
        # grandchildren) without changing any yoga layout properties.
        # Viewport culling: skip children entirely outside the visible
        # scroll viewport to avoid unnecessary render work.
        global _For_cls
        if _For_cls is None:
            from .control_flow import For

            _For_cls = For
        For = _For_cls

        for child in self._scroll_content._children:
            # isinstance(child, For) is intentional — this is viewport culling
            # that flattens For's children for per-item scroll clipping, not a
            # type guard. All _children are always Renderable instances.
            if (
                isinstance(child, For)
                and child._visible
                and child._render_before is None
                and child._render_after is None
            ):
                for grandchild in child._children:
                    if self._scroll_y:
                        cy_rel = grandchild._y - self._y
                        child_h = grandchild._layout_height or 0
                        if cy_rel + child_h <= offset_y or cy_rel >= offset_y + height:
                            continue
                    grandchild.render(buffer, delta_time)
                continue
            if self._scroll_y:
                cy_rel = child._y - self._y
                child_h = child._layout_height or 0
                if cy_rel + child_h <= offset_y or cy_rel >= offset_y + height:
                    continue
            child.render(buffer, delta_time)

        buffer.pop_offset()
        buffer.pop_scissor_rect()

        if self._render_after:
            self._render_after(buffer, delta_time, self)

        if has_opacity:
            buffer.pop_opacity()


def _content_property(name: str) -> property:
    def getter(self: ScrollBox):
        return getattr(self._scroll_content, name)

    def setter(self: ScrollBox, value: object):
        setattr(self._scroll_content, name, value)

    return property(getter, setter)


for _name in (
    "flex_direction",
    "flex_wrap",
    "justify_content",
    "align_items",
    "gap",
    "padding",
    "padding_top",
    "padding_right",
    "padding_bottom",
    "padding_left",
):
    setattr(ScrollBox, _name, _content_property(_name))


__all__ = [
    "LinearScrollAccel",
    "MacOSScrollAccel",
    "ScrollBox",
    "ScrollContent",
]
