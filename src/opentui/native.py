"""Native bindings wrapper - uses nanobind C++ extensions when available."""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .editor.editor_view_native import NativeEditorView
    from .editor.text_view_native import NativeTextBufferView

from .ffi import get_native, is_native_available

_nb: Any = get_native()
_NANOBIND_AVAILABLE: bool = is_native_available()


def _decode(value: Any) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _rgba_to_list(color: Any) -> list[float] | None:
    if color is None:
        return None
    if isinstance(color, list | tuple):
        return [float(color[0]), float(color[1]), float(color[2]), float(color[3])]
    return [float(color.r), float(color.g), float(color.b), float(color.a)]


class NativeRenderer:
    """Wrapper for native renderer using nanobind bindings."""

    def __init__(self, width: int, height: int, testing: bool = False, remote: bool = False):
        if not _NANOBIND_AVAILABLE:
            raise RuntimeError("Nanobind bindings not available")
        self._ptr = _nb.renderer.create_renderer(width, height, testing, remote)

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.renderer.destroy_renderer(self._ptr)
                self._ptr = None
        except Exception:
            pass

    def render(self, skip_diff: bool = False) -> None:
        _nb.renderer.render(self._ptr, skip_diff)

    def resize(self, width: int, height: int) -> None:
        _nb.renderer.resize_renderer(self._ptr, width, height)

    def setup_terminal(self, use_alternate_screen: bool) -> None:
        _nb.renderer.setup_terminal(self._ptr, use_alternate_screen)

    def suspend(self) -> None:
        _nb.renderer.suspend_renderer(self._ptr)

    def resume(self) -> None:
        _nb.renderer.resume_renderer(self._ptr)

    def clear_terminal(self) -> None:
        _nb.renderer.clear_terminal(self._ptr)

    def set_title(self, title: str) -> None:
        _nb.renderer.set_terminal_title(self._ptr, title)

    def set_cursor(self, x: int, y: int, visible: bool = True) -> None:
        _nb.renderer.set_cursor_position(self._ptr, x, y, visible)

    def enable_mouse(self, enable_movement: bool = False) -> None:
        _nb.renderer.enable_mouse(self._ptr, enable_movement)

    def disable_mouse(self) -> None:
        _nb.renderer.disable_mouse(self._ptr)

    def enable_kitty_keyboard(self, flags: int) -> None:
        _nb.renderer.enable_kitty_keyboard(self._ptr, flags)

    def disable_kitty_keyboard(self) -> None:
        _nb.renderer.disable_kitty_keyboard(self._ptr)

    def get_next_buffer(self):
        return _nb.renderer.get_next_buffer(self._ptr)

    def get_current_buffer(self):
        return _nb.renderer.get_current_buffer(self._ptr)


class NativeBuffer:
    """Wrapper for native buffer using nanobind bindings."""

    def __init__(self, ptr: Any):
        self._ptr = ptr

    @property
    def ptr(self) -> Any:
        return self._ptr

    def clear(self) -> None:
        _nb.buffer.buffer_clear(self._ptr, 0.0)

    def resize(self, width: int, height: int) -> None:
        _nb.buffer.buffer_resize(self._ptr, width, height)

    def draw_text(self, text: str, x: int, y: int) -> None:
        text_bytes = text.encode("utf-8") if isinstance(text, str) else text
        _nb.buffer.buffer_draw_text(self._ptr, text_bytes, len(text_bytes), x, y)

    def set_cell(self, x: int, y: int, ch: int) -> None:
        _nb.buffer.buffer_set_cell(self._ptr, x, y, ch)

    def fill_rect(self, x: int, y: int, width: int, height: int) -> None:
        _nb.buffer.buffer_fill_rect(self._ptr, x, y, width, height)

    def get_char_ptr(self) -> int:
        return _nb.buffer.buffer_get_char_ptr(self._ptr)

    def get_fg_ptr(self) -> int:
        return _nb.buffer.buffer_get_fg_ptr(self._ptr)

    def get_bg_ptr(self) -> int:
        return _nb.buffer.buffer_get_bg_ptr(self._ptr)

    def get_width(self) -> int:
        return _nb.buffer.get_buffer_width(self._ptr)

    def get_height(self) -> int:
        return _nb.buffer.get_buffer_height(self._ptr)


class NativeOptimizedBuffer:
    """Wrapper for native optimized buffer (frame buffer for rendering)."""

    def __init__(
        self,
        width: int,
        height: int,
        *,
        respect_alpha: bool = True,
        encoding: int = 0,
        buffer_id: str = "",
    ):
        self._ptr: Any = _nb.buffer.create_optimized_buffer(
            width, height, respect_alpha, encoding, buffer_id
        )

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.buffer.destroy_optimized_buffer(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> Any:
        return self._ptr

    def clear(self, alpha: float = 0.0) -> None:
        _nb.buffer.buffer_clear(self._ptr, alpha)

    def resize(self, width: int, height: int) -> None:
        _nb.buffer.buffer_resize(self._ptr, width, height)

    def get_width(self) -> int:
        return _nb.buffer.get_buffer_width(self._ptr)

    def get_height(self) -> int:
        return _nb.buffer.get_buffer_height(self._ptr)

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        fg: list[float] | None = None,
        bg: list[float] | None = None,
        attrs: int = 0,
    ) -> None:
        text_bytes = text.encode("utf-8")
        _nb.buffer.buffer_draw_text(self._ptr, text_bytes, len(text_bytes), x, y, fg, bg, attrs)

    def set_cell(
        self,
        x: int,
        y: int,
        ch: int,
        fg: list[float] | None = None,
        bg: list[float] | None = None,
        attrs: int = 0,
    ) -> None:
        _nb.buffer.buffer_set_cell(self._ptr, x, y, ch, fg, bg, attrs)

    def set_cell_with_alpha(
        self,
        x: int,
        y: int,
        ch: int,
        fg: list[float] | None = None,
        bg: list[float] | None = None,
        attrs: int = 0,
    ) -> None:
        _nb.buffer.buffer_set_cell_with_alpha_blending(self._ptr, x, y, ch, fg, bg, attrs)

    def draw_char(
        self,
        ch: int,
        x: int,
        y: int,
        fg: list[float] | None = None,
        bg: list[float] | None = None,
        attrs: int = 0,
    ) -> None:
        _nb.buffer.buffer_draw_char(self._ptr, ch, x, y, fg, bg, attrs)

    def fill_rect(
        self, x: int, y: int, width: int, height: int, bg: list[float] | None = None
    ) -> None:
        _nb.buffer.buffer_fill_rect(self._ptr, x, y, width, height, bg)

    def get_respect_alpha(self) -> bool:
        return _nb.buffer.buffer_get_respect_alpha(self._ptr)

    def set_respect_alpha(self, respect: bool) -> None:
        _nb.buffer.buffer_set_respect_alpha(self._ptr, respect)

    def draw_frame(
        self,
        target: NativeOptimizedBuffer,
        x: int = 0,
        y: int = 0,
        source_x: int = 0,
        source_y: int = 0,
        source_width: int = 0,
        source_height: int = 0,
    ) -> None:
        _nb.buffer.draw_frame_buffer(
            target.ptr, x, y, self._ptr, source_x, source_y, source_width, source_height
        )

    def get_rendered_text(self, add_line_breaks: bool = True) -> str:
        raw: bytes = _nb.buffer.buffer_write_resolved_chars(self._ptr, add_line_breaks)
        return raw.decode("utf-8") if raw else ""

    def get_id(self) -> str:
        raw: bytes = _nb.buffer.buffer_get_id(self._ptr)
        return raw.decode("utf-8") if raw else ""

    def draw_editor_view(self, editor_view: NativeEditorView, x: int = 0, y: int = 0) -> None:
        _nb.editor_view.buffer_draw_editor_view(self._ptr, editor_view.ptr, x, y)

    def draw_text_buffer_view(self, view: NativeTextBufferView, x: int = 0, y: int = 0) -> None:
        _nb.text_buffer.buffer_draw_text_buffer_view(self._ptr, view.ptr, x, y)

    def _check_bounds(self, x: int, y: int) -> int:
        w = self.get_width()
        h = self.get_height()
        if x < 0 or x >= w or y < 0 or y >= h:
            raise IndexError(f"cell ({x}, {y}) out of bounds for {w}x{h} buffer")
        return w

    def get_fg_color(self, x: int, y: int) -> tuple[float, float, float, float]:
        w = self._check_bounds(x, y)
        ptr_int = _nb.buffer.buffer_get_fg_ptr(self._ptr)
        offset = (y * w + x) * 4  # 4 floats per cell
        arr = (ctypes.c_float * 4).from_address(ptr_int + offset * ctypes.sizeof(ctypes.c_float))
        return (arr[0], arr[1], arr[2], arr[3])

    def get_bg_color(self, x: int, y: int) -> tuple[float, float, float, float]:
        w = self._check_bounds(x, y)
        ptr_int = _nb.buffer.buffer_get_bg_ptr(self._ptr)
        offset = (y * w + x) * 4
        arr = (ctypes.c_float * 4).from_address(ptr_int + offset * ctypes.sizeof(ctypes.c_float))
        return (arr[0], arr[1], arr[2], arr[3])

    def get_attributes(self, x: int, y: int) -> int:
        w = self._check_bounds(x, y)
        ptr_int = _nb.buffer.buffer_get_attributes_ptr(self._ptr)
        offset = y * w + x
        arr = (ctypes.c_uint32 * 1).from_address(ptr_int + offset * ctypes.sizeof(ctypes.c_uint32))
        return arr[0]

    def get_char(self, x: int, y: int) -> int:
        w = self._check_bounds(x, y)
        ptr_int = _nb.buffer.buffer_get_char_ptr(self._ptr)
        offset = y * w + x
        arr = (ctypes.c_uint32 * 1).from_address(ptr_int + offset * ctypes.sizeof(ctypes.c_uint32))
        return arr[0]


def encode_unicode(text: str, width_method: int = 0) -> list[tuple[int, int]]:
    text_bytes = text.encode("utf-8")
    return _nb.buffer.encode_unicode(text_bytes, width_method)


def is_available() -> bool:
    return _NANOBIND_AVAILABLE


__all__ = [
    "NativeRenderer",
    "NativeBuffer",
    "NativeOptimizedBuffer",
    "is_available",
    "encode_unicode",
]
