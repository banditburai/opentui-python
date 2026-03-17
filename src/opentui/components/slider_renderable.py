"""SliderRenderable - a scrollbar-like slider with sub-cell precision.

Slider component for numeric value selection.
Provides a draggable thumb on a track with virtual (half-cell) coordinate
system for smooth rendering.
"""

from __future__ import annotations

import builtins as _builtins
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .. import structs as s
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer

# Avoid shadowing by parameter names ``min`` / ``max``
_min = _builtins.min
_max = _builtins.max


def _js_round(x: float) -> int:
    """Round half-up semantics."""
    return math.floor(x + 0.5)


_DEFAULT_THUMB_BG = s.RGBA(0x9A / 255, 0x9E / 255, 0xA3 / 255, 0xFF / 255)
_DEFAULT_TRACK_BG = s.RGBA(0x25 / 255, 0x25 / 255, 0x27 / 255, 0xFF / 255)


class SliderRenderable(Renderable):
    """Slider renderable with sub-cell precision thumb rendering.

    The slider operates in a *virtual* coordinate system at 2x resolution
    (each real cell maps to 2 virtual units) so the thumb can be positioned
    with half-cell accuracy using Unicode half-block characters.

    Usage:
        slider = SliderRenderable(
            orientation="horizontal",
            min=0,
            max=100,
            value=50,
            width=20,
            height=1,
            on_change=lambda v: print(v),
        )
    """

    __slots__ = (
        "_orientation",
        "_slider_value",
        "_slider_min",
        "_slider_max",
        "_viewport_size",
        "_track_bg",
        "_thumb_fg",
        "_on_change_cb",
        # Drag state (closure-like)
        "_is_dragging",
        "_drag_offset_virtual",
    )

    def __init__(
        self,
        *,
        orientation: str = "horizontal",
        value: float = 0,
        min: float = 0,  # noqa: A002
        max: float = 100,  # noqa: A002
        viewport_size: float | None = None,
        background_color: s.RGBA | str | None = None,
        foreground_color: s.RGBA | str | None = None,
        on_change: Callable[[float], None] | None = None,
        # Pass through to Renderable
        **kwargs: Any,
    ):
        # flex_shrink defaults to 0 for sliders
        kwargs.setdefault("flex_shrink", 0)
        super().__init__(**kwargs)

        self._orientation = orientation
        self._slider_min = min
        self._slider_max = max
        self._slider_value = _max(min, _min(max, value))
        self._viewport_size = (
            viewport_size if viewport_size is not None else _max(1, (max - min) * 0.1)
        )
        self._on_change_cb = on_change

        self._track_bg = self._parse_color(background_color) or _DEFAULT_TRACK_BG
        self._thumb_fg = self._parse_color(foreground_color) or _DEFAULT_THUMB_BG

        self._is_dragging = False
        self._drag_offset_virtual = 0.0

        self.on_mouse_down = self._handle_mouse_down
        self.on_mouse_drag = self._handle_mouse_drag
        self.on_mouse_up = self._handle_mouse_up

    # -- Public properties ---------------------------------------------------

    @property
    def orientation(self) -> str:
        return self._orientation

    @property
    def value(self) -> float:
        return self._slider_value

    @value.setter
    def value(self, new_value: float) -> None:
        clamped = _max(self._slider_min, _min(self._slider_max, new_value))
        if clamped != self._slider_value:
            self._slider_value = clamped
            if self._on_change_cb is not None:
                self._on_change_cb(clamped)
            self.emit("change", value=clamped)
            self.request_render()

    @property
    def min(self) -> float:
        return self._slider_min

    @min.setter
    def min(self, new_min: float) -> None:
        if new_min != self._slider_min:
            self._slider_min = new_min
            if self._slider_value < new_min:
                self.value = new_min
            self.request_render()

    @property
    def max(self) -> float:
        return self._slider_max

    @max.setter
    def max(self, new_max: float) -> None:
        if new_max != self._slider_max:
            self._slider_max = new_max
            if self._slider_value > new_max:
                self.value = new_max
            self.request_render()

    @property
    def viewport_size(self) -> float:
        return self._viewport_size

    @viewport_size.setter
    def viewport_size(self, size: float) -> None:
        clamped = _max(0.01, _min(size, self._slider_max - self._slider_min))
        if clamped != self._viewport_size:
            self._viewport_size = clamped
            self.request_render()

    # -- Internal: effective dimensions ------------------------------------

    def _effective_width(self) -> int:
        if self._layout_width and self._layout_width > 0:
            return self._layout_width
        if isinstance(self._width, int) and self._width > 0:
            return self._width
        return 0

    def _effective_height(self) -> int:
        if self._layout_height and self._layout_height > 0:
            return self._layout_height
        if isinstance(self._height, int) and self._height > 0:
            return self._height
        return 0

    # -- Virtual coordinate helpers ----------------------------------------

    def get_virtual_thumb_size(self) -> int:
        w = self._effective_width()
        h = self._effective_height()
        virtual_track = (h * 2) if self._orientation == "vertical" else (w * 2)
        rng = self._slider_max - self._slider_min

        if rng == 0:
            return virtual_track

        vps = _max(1, self._viewport_size)
        content_size = rng + vps

        if content_size <= vps:
            return virtual_track

        thumb_ratio = vps / content_size
        calculated = math.floor(virtual_track * thumb_ratio)

        return _max(1, _min(calculated, virtual_track))

    def get_virtual_thumb_start(self) -> int:
        w = self._effective_width()
        h = self._effective_height()
        virtual_track = (h * 2) if self._orientation == "vertical" else (w * 2)
        rng = self._slider_max - self._slider_min

        if rng == 0:
            return 0

        value_ratio = (self._slider_value - self._slider_min) / rng
        vts = self.get_virtual_thumb_size()

        return _js_round(value_ratio * (virtual_track - vts))

    def _get_thumb_rect(self) -> dict:
        """Calculate real-cell bounding box of the thumb."""
        vts = self.get_virtual_thumb_size()
        vt_start = self.get_virtual_thumb_start()

        real_start = math.floor(vt_start / 2)
        real_size = math.ceil((vt_start + vts) / 2) - real_start

        if self._orientation == "vertical":
            return {
                "x": self._x,
                "y": self._y + real_start,
                "width": self._effective_width(),
                "height": _max(1, real_size),
            }
        else:
            return {
                "x": self._x + real_start,
                "y": self._y,
                "width": _max(1, real_size),
                "height": self._effective_height(),
            }

    # -- Mouse handling ----------------------------------------------------

    def _calculate_drag_offset_virtual(self, event: Any) -> float:
        """Compute offset of mouse within the thumb in virtual coords."""
        w = self._effective_width()
        h = self._effective_height()
        track_start = self._y if self._orientation == "vertical" else self._x
        track_size = h if self._orientation == "vertical" else w
        mouse_pos = (event.y if self._orientation == "vertical" else event.x) - track_start
        virtual_mouse = _max(0, _min(track_size * 2, mouse_pos * 2))
        vt_start = self.get_virtual_thumb_start()
        vts = self.get_virtual_thumb_size()
        return _max(0, _min(vts, virtual_mouse - vt_start))

    def _handle_mouse_down(self, event: Any) -> None:
        event.stop_propagation()
        event.prevent_default()

        thumb = self._get_thumb_rect()
        in_thumb = (
            event.x >= thumb["x"]
            and event.x < thumb["x"] + thumb["width"]
            and event.y >= thumb["y"]
            and event.y < thumb["y"] + thumb["height"]
        )

        if in_thumb:
            self._is_dragging = True
            self._drag_offset_virtual = self._calculate_drag_offset_virtual(event)
        else:
            self._update_value_from_mouse_direct(event)
            self._is_dragging = True
            self._drag_offset_virtual = self._calculate_drag_offset_virtual(event)

    def _handle_mouse_drag(self, event: Any) -> None:
        if not self._is_dragging:
            return
        event.stop_propagation()
        self._update_value_from_mouse_with_offset(event, self._drag_offset_virtual)

    def _handle_mouse_up(self, event: Any) -> None:
        if self._is_dragging:
            self._update_value_from_mouse_with_offset(event, self._drag_offset_virtual)
        self._is_dragging = False

    def _update_value_from_mouse_direct(self, event: Any) -> None:
        """Set value based on direct click position (no offset)."""
        w = self._effective_width()
        h = self._effective_height()
        track_start = self._y if self._orientation == "vertical" else self._x
        track_size = h if self._orientation == "vertical" else w
        mouse_pos = event.y if self._orientation == "vertical" else event.x

        relative = mouse_pos - track_start
        clamped = _max(0, _min(track_size, relative))
        ratio = 0.0 if track_size == 0 else clamped / track_size
        rng = self._slider_max - self._slider_min
        self.value = self._slider_min + ratio * rng

    def _update_value_from_mouse_with_offset(self, event: Any, offset_virtual: float) -> None:
        w = self._effective_width()
        h = self._effective_height()
        track_start = self._y if self._orientation == "vertical" else self._x
        track_size = h if self._orientation == "vertical" else w
        mouse_pos = event.y if self._orientation == "vertical" else event.x

        virtual_track_size = track_size * 2
        relative = mouse_pos - track_start
        clamped = _max(0, _min(track_size, relative))
        virtual_mouse = clamped * 2

        vts = self.get_virtual_thumb_size()
        max_thumb_start = _max(0, virtual_track_size - vts)

        desired = virtual_mouse - offset_virtual
        desired = _max(0, _min(max_thumb_start, desired))

        ratio = 0.0 if max_thumb_start == 0 else desired / max_thumb_start
        rng = self._slider_max - self._slider_min
        self.value = self._slider_min + ratio * rng

    # -- Rendering ---------------------------------------------------------

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return
        if self._orientation == "horizontal":
            self._render_horizontal(buffer)
        else:
            self._render_vertical(buffer)

    def _render_horizontal(self, buffer: Buffer) -> None:
        w = self._effective_width()
        h = self._effective_height()
        vts = self.get_virtual_thumb_size()
        vt_start = self.get_virtual_thumb_start()
        vt_end = vt_start + vts

        buffer.fill_rect(self._x, self._y, w, h, self._track_bg)

        real_start_cell = math.floor(vt_start / 2)
        real_end_cell = math.ceil(vt_end / 2) - 1
        start_x = _max(0, real_start_cell)
        end_x = _min(w - 1, real_end_cell)

        for rx in range(start_x, end_x + 1):
            vc_start = rx * 2
            vc_end = vc_start + 2
            ts_in_cell = _max(vt_start, vc_start)
            te_in_cell = _min(vt_end, vc_end)
            coverage = te_in_cell - ts_in_cell

            if coverage >= 2:
                ch = "\u2588"  # Full block
            else:
                is_left = ts_in_cell == vc_start
                ch = "\u258c" if is_left else "\u2590"  # Left/right half block

            for y in range(h):
                buffer.draw_text(
                    ch, self._x + rx, self._y + y, fg=self._thumb_fg, bg=self._track_bg
                )

    def _render_vertical(self, buffer: Buffer) -> None:
        w = self._effective_width()
        h = self._effective_height()
        vts = self.get_virtual_thumb_size()
        vt_start = self.get_virtual_thumb_start()
        vt_end = vt_start + vts

        buffer.fill_rect(self._x, self._y, w, h, self._track_bg)

        real_start_cell = math.floor(vt_start / 2)
        real_end_cell = math.ceil(vt_end / 2) - 1
        start_y = _max(0, real_start_cell)
        end_y = _min(h - 1, real_end_cell)

        for ry in range(start_y, end_y + 1):
            vc_start = ry * 2
            vc_end = vc_start + 2
            ts_in_cell = _max(vt_start, vc_start)
            te_in_cell = _min(vt_end, vc_end)
            coverage = te_in_cell - ts_in_cell

            if coverage >= 2:
                ch = "\u2588"  # Full block
            elif coverage > 0:
                vp_in_cell = ts_in_cell - vc_start
                ch = "\u2580" if vp_in_cell == 0 else "\u2584"  # Upper/lower half
            else:
                continue

            for x in range(w):
                buffer.draw_text(
                    ch, self._x + x, self._y + ry, fg=self._thumb_fg, bg=self._track_bg
                )


__all__ = ["SliderRenderable"]
