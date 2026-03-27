"""Pixel buffer wrapping the native nanobind renderer surface."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any

from .. import structs as s
from ..structs import char_width as _char_width
from ..structs import display_width as _display_width


@dataclass(slots=True)
class FrameTimingBuckets:
    """Per-frame renderer timings in nanoseconds."""

    signal_handling_ns: int = 0
    layout_ns: int = 0
    configure_yoga_ns: int = 0
    compute_yoga_ns: int = 0
    apply_layout_ns: int = 0
    update_layout_hooks_ns: int = 0
    mount_callbacks_ns: int = 0
    buffer_prepare_ns: int = 0
    buffer_lookup_ns: int = 0
    repaint_plan_ns: int = 0
    buffer_replay_ns: int = 0
    render_tree_ns: int = 0
    flush_ns: int = 0
    post_render_ns: int = 0
    frame_finish_ns: int = 0
    total_ns: int = 0


class Buffer:
    """Wrapper around native buffer using nanobind."""

    def __init__(self, ptr: Any, native: Any, graphics: Any = None):
        self._ptr = ptr
        self._native = native
        self._graphics = graphics
        self._width: int | None = None
        self._height: int | None = None
        self._scissor_stack: list[tuple[int, int, int, int]] = []
        self._opacity_stack: list[float] = []
        self._cached_opacity: float = 1.0
        self._offset_stack: list[tuple[int, int]] = []

    def _retarget(self, ptr: Any) -> Buffer:
        self._ptr = ptr
        self._width = None
        self._height = None
        self._scissor_stack.clear()
        self._opacity_stack.clear()
        self._cached_opacity = 1.0
        self._offset_stack.clear()
        return self

    @property
    def width(self) -> int:
        if self._width is None:
            self._width = self._native.get_buffer_width(self._ptr)
        return self._width  # type: ignore[return-value]

    @property
    def height(self) -> int:
        if self._height is None:
            self._height = self._native.get_buffer_height(self._ptr)
        return self._height  # type: ignore[return-value]

    def clear(self, bg: s.RGBA | None = None) -> None:
        alpha = bg.a if bg else 0.0
        self._native.buffer_clear(self._ptr, alpha)

    def resize(self, width: int, height: int) -> None:
        self._native.buffer_resize(self._ptr, width, height)
        self._width = width
        self._height = height

    def _apply_opacity_to_color(self, color: s.RGBA | None) -> s.RGBA | None:
        if color is None or not self._opacity_stack:
            return color
        opacity = self.get_current_opacity()
        if opacity >= 1.0:
            return color
        return s.RGBA(color.r, color.g, color.b, color.a * opacity)

    def push_offset(self, dx: int, dy: int) -> None:
        # Cumulative: pushing (0, -5) then (0, -3) yields (0, -8).
        # Mirrors OpenCode's translateY — pure render-time, no layout.
        if self._offset_stack:
            cur_dx, cur_dy = self._offset_stack[-1]
            self._offset_stack.append((cur_dx + dx, cur_dy + dy))
        else:
            self._offset_stack.append((dx, dy))

    def pop_offset(self) -> None:
        if self._offset_stack:
            self._offset_stack.pop()

    def get_offset(self) -> tuple[int, int]:
        """Return the current cumulative drawing offset (dx, dy)."""
        return self._offset_stack[-1] if self._offset_stack else (0, 0)

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        fg: s.RGBA | None = None,
        bg: s.RGBA | None = None,
        attributes: int = 0,
        link: str | None = None,
    ) -> None:
        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return

        if self._scissor_stack:
            sx, sy, sw, sh = self._scissor_stack[-1]
            if sw <= 0 or sh <= 0:
                return
            if y < sy or y >= sy + sh:
                return
            text_dw = _display_width(text)
            if x + text_dw <= sx or x >= sx + sw:
                return
            if x < sx:
                trim_cols = sx - x
                trimmed = 0
                i = 0
                while i < len(text) and trimmed < trim_cols:
                    trimmed += _char_width(text[i])
                    i += 1
                text = text[i:]
                x = sx
            end = sx + sw
            remaining_dw = _display_width(text)
            if x + remaining_dw > end:
                max_cols = end - x
                kept = 0
                i = 0
                while i < len(text) and kept + _char_width(text[i]) <= max_cols:
                    kept += _char_width(text[i])
                    i += 1
                text = text[:i]
            if not text:
                return

        if x < 0:
            return

        fg = self._apply_opacity_to_color(fg)
        bg = self._apply_opacity_to_color(bg)

        if link:
            link_id = self._native.link_alloc(link.encode("utf-8"))
            attributes = self._native.attributes_with_link(attributes, link_id)

        text_bytes = text.encode("utf-8")

        fg_tuple = (fg.r, fg.g, fg.b, fg.a) if fg else None
        bg_tuple = (bg.r, bg.g, bg.b, bg.a) if bg else None

        self._native.buffer_draw_text(
            self._ptr, text_bytes, len(text_bytes), x, y, fg_tuple, bg_tuple, attributes
        )

    def fill_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        bg: s.RGBA | None = None,
    ) -> None:
        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

        if x < 0:
            width += x
            x = 0
        if y < 0:
            height += y
            y = 0
        if width <= 0 or height <= 0:
            return

        if self._scissor_stack:
            sx, sy, sw, sh = self._scissor_stack[-1]
            if sw <= 0 or sh <= 0:
                return
            nx = max(x, sx)
            ny = max(y, sy)
            nw = min(x + width, sx + sw) - nx
            nh = min(y + height, sy + sh) - ny
            if nw <= 0 or nh <= 0:
                return
            x, y, width, height = nx, ny, nw, nh

        bg = self._apply_opacity_to_color(bg)

        bg_tuple = (bg.r, bg.g, bg.b, bg.a) if bg else None
        self._native.buffer_fill_rect(self._ptr, x, y, width, height, bg_tuple)

    def _check_bounds(self, x: int, y: int) -> None:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise IndexError(f"cell ({x}, {y}) out of bounds for {self.width}x{self.height} buffer")

    def _get_color_at(self, x: int, y: int, ptr_attr: str) -> s.RGBA:
        self._check_bounds(x, y)
        base_ptr = getattr(self._native, ptr_attr)(self._ptr)
        offset = (y * self.width + x) * 4
        arr = (ctypes.c_float * 4).from_address(base_ptr + offset * ctypes.sizeof(ctypes.c_float))
        return s.RGBA(arr[0], arr[1], arr[2], arr[3])

    def get_bg_color(self, x: int, y: int) -> s.RGBA:
        return self._get_color_at(x, y, "buffer_get_bg_ptr")

    def get_fg_color(self, x: int, y: int) -> s.RGBA:
        return self._get_color_at(x, y, "buffer_get_fg_ptr")

    def draw_editor_view(self, editor_view: Any, x: int = 0, y: int = 0) -> None:
        from ..native import _nb

        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy
        _nb.editor_view.buffer_draw_editor_view(self._ptr, editor_view.ptr, x, y)

    def draw_text_buffer_view(self, text_buffer_view: Any, x: int = 0, y: int = 0) -> None:
        from ..native import _nb

        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy
        _nb.text_buffer.buffer_draw_text_buffer_view(self._ptr, text_buffer_view.ptr, x, y)

    def get_plain_text(self) -> str:
        try:
            raw: bytes = self._native.buffer_write_resolved_chars(self._ptr, True)
            if not raw:
                return ""
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

        lines = [line.rstrip() for line in text.split("\n")]

        while lines and not lines[-1]:
            lines.pop()

        return "\n".join(lines)

    def get_attributes(self, x: int, y: int) -> int:
        self._check_bounds(x, y)
        attr_ptr = self._native.buffer_get_attributes_ptr(self._ptr)
        w = self.width
        offset = y * w + x
        arr = (ctypes.c_uint32 * 1).from_address(attr_ptr + offset * ctypes.sizeof(ctypes.c_uint32))
        return arr[0]

    def get_char_code(self, x: int, y: int) -> int:
        self._check_bounds(x, y)
        char_ptr = self._native.buffer_get_char_ptr(self._ptr)
        w = self.width
        offset = y * w + x
        arr = (ctypes.c_uint32 * 1).from_address(char_ptr + offset * ctypes.sizeof(ctypes.c_uint32))
        return arr[0]

    def get_span_lines(self) -> list[dict]:
        w = self.width
        h = self.height

        if w <= 0 or h <= 0:
            return []

        try:
            raw: bytes = self._native.buffer_write_resolved_chars(self._ptr, True)
            real_text = raw.decode("utf-8", errors="replace") if raw else ""
        except Exception:
            return []

        lines = real_text.split("\n")
        return [
            {"text": lines[y], "width": len(lines[y])}
            if y < len(lines)
            else {"text": "", "width": 0}
            for y in range(h)
        ]

    def push_scissor_rect(self, x: int, y: int, width: int, height: int) -> None:
        # Apply drawing offset so nested scissor rects within a scrolled
        # container use the same coordinate space as draw operations.
        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

        if self._scissor_stack:
            cx, cy, cw, ch = self._scissor_stack[-1]
            nx = max(x, cx)
            ny = max(y, cy)
            nw = min(x + width, cx + cw) - nx
            nh = min(y + height, cy + ch) - ny
            self._scissor_stack.append((nx, ny, max(0, nw), max(0, nh)))
        else:
            self._scissor_stack.append((x, y, width, height))

        # Sync with the native Zig buffer's scissor stack so that native
        # draw calls (e.g. bufferDrawTextBufferView) are clipped too.
        if self._graphics is not None:
            final = self._scissor_stack[-1]
            self._graphics.buffer_push_scissor_rect(
                self._ptr,
                final[0],
                final[1],
                max(0, final[2]),
                max(0, final[3]),
            )

    def pop_scissor_rect(self) -> None:
        if self._scissor_stack:
            self._scissor_stack.pop()
            if self._graphics is not None:
                self._graphics.buffer_pop_scissor_rect(self._ptr)

    def get_scissor_rect(self) -> tuple[int, int, int, int] | None:
        return self._scissor_stack[-1] if self._scissor_stack else None

    # Cached product avoids O(n) recomputation per draw call.
    def push_opacity(self, opacity: float) -> None:
        self._opacity_stack.append(opacity)
        self._cached_opacity = max(0.0, min(1.0, self._cached_opacity * opacity))

    def pop_opacity(self) -> None:
        if self._opacity_stack:
            removed = self._opacity_stack.pop()
            if not self._opacity_stack:
                self._cached_opacity = 1.0
            elif removed != 0.0:
                self._cached_opacity = max(0.0, min(1.0, self._cached_opacity / removed))
            else:
                # Recompute from scratch if we divided by zero
                self._cached_opacity = 1.0
                for o in self._opacity_stack:
                    self._cached_opacity *= o
                self._cached_opacity = max(0.0, min(1.0, self._cached_opacity))

    def get_current_opacity(self) -> float:
        return self._cached_opacity

    def draw_box(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        border_style: str = "single",
        border_color: s.RGBA | None = None,
        bg: s.RGBA | None = None,
        title: str | None = None,
        title_alignment: str = "left",
        *,
        border_top: bool = True,
        border_right: bool = True,
        border_bottom: bool = True,
        border_left: bool = True,
        should_fill: bool = True,
    ) -> None:
        if width < 1 or height < 1:
            return

        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

        border_color = self._apply_opacity_to_color(border_color)
        bg = self._apply_opacity_to_color(bg)

        border_tuple = (
            (border_color.r, border_color.g, border_color.b, border_color.a)
            if border_color
            else None
        )
        bg_tuple = (bg.r, bg.g, bg.b, bg.a) if bg else None
        self._native.buffer_draw_box(
            self._ptr,
            x,
            y,
            width,
            height,
            border_style,
            border_top,
            border_right,
            border_bottom,
            border_left,
            should_fill,
            border_tuple,
            bg_tuple,
            title or "",
            title_alignment,
        )
