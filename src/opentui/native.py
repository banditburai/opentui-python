"""Native bindings wrapper - uses nanobind C++ extensions when available."""

from __future__ import annotations

import contextlib
import ctypes
import importlib.util
import os
import sys
from typing import Any

_nb: Any = None
_NANOBIND_AVAILABLE = False

# Reuse FFI search/preload logic from ffi.py (single source of truth).
from .ffi import _iter_binding_search_dirs, _preload_opentui_library

_preload_opentui_library()
_search_dirs = _iter_binding_search_dirs()

_so_file = None
if "opentui_bindings" in sys.modules:
    _nb = sys.modules["opentui_bindings"]
    _NANOBIND_AVAILABLE = True

if _nb is None:
    for _dir in _search_dirs:
        if os.path.isdir(_dir):
            for f in os.listdir(_dir):
                if f.startswith("opentui_bindings") and (f.endswith(".so") or f.endswith(".pyd")):
                    _so_file = os.path.join(_dir, f)
                    break
        if _so_file:
            break

if _so_file and _nb is None:
    try:
        spec = importlib.util.spec_from_file_location("opentui_bindings", _so_file)
        if spec and spec.loader:
            _nb = importlib.util.module_from_spec(spec)
            sys.modules["opentui_bindings"] = _nb
            spec.loader.exec_module(_nb)
            _NANOBIND_AVAILABLE = True
    except Exception as e:
        import warnings

        warnings.warn(f"Failed to load nanobind bindings: {e}", stacklevel=1)
        _nb = None


class _ColorArray(ctypes.Structure):
    _fields_ = [("values", ctypes.c_float * 4)]


class _StyledChunk(ctypes.Structure):
    _fields_ = [
        ("text_ptr", ctypes.c_void_p),
        ("text_len", ctypes.c_size_t),
        ("fg_ptr", ctypes.c_void_p),
        ("bg_ptr", ctypes.c_void_p),
        ("attributes", ctypes.c_uint32),
        ("_pad", ctypes.c_uint32),
        ("link_ptr", ctypes.c_void_p),
        ("link_len", ctypes.c_size_t),
    ]


_zig_set_styled_text_fn: Any = None


def _get_zig_set_styled_text() -> Any:
    """Lazily resolve and cache the textBufferSetStyledText Zig symbol."""
    global _zig_set_styled_text_fn
    if _zig_set_styled_text_fn is None:
        try:
            fn = ctypes.CDLL(None).textBufferSetStyledText
        except OSError:
            import logging

            logging.getLogger(__name__).debug(
                "Could not load default CDLL for textBufferSetStyledText"
            )
            raise
        except AttributeError:
            import logging

            logging.getLogger(__name__).debug(
                "textBufferSetStyledText symbol not found in default CDLL"
            )
            raise
        fn.restype = None
        fn.argtypes = [
            ctypes.c_void_p,  # buffer pointer
            ctypes.c_void_p,  # data pointer (StyledChunk array)
            ctypes.c_size_t,  # chunk count
        ]
        _zig_set_styled_text_fn = fn
    return _zig_set_styled_text_fn


def _rgba_to_list(color: Any) -> list[float] | None:
    """Convert an RGBA color object (or list) to a [r, g, b, a] float list, or None."""
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

    def draw_frame(self) -> None:
        _nb.buffer.draw_frame_buffer(self._ptr)

    def get_rendered_text(self, add_line_breaks: bool = True) -> str:
        """Get the rendered content as plain text."""
        raw: bytes = _nb.buffer.buffer_write_resolved_chars(self._ptr, add_line_breaks)
        return raw.decode("utf-8") if raw else ""

    def get_id(self) -> str:
        raw: bytes = _nb.buffer.buffer_get_id(self._ptr)
        return raw.decode("utf-8") if raw else ""

    def draw_editor_view(self, editor_view: NativeEditorView, x: int = 0, y: int = 0) -> None:
        """Render an EditorView into this buffer."""
        _nb.editor_view.buffer_draw_editor_view(self._ptr, editor_view.ptr, x, y)

    def draw_text_buffer_view(self, view: NativeTextBufferView, x: int = 0, y: int = 0) -> None:
        """Render a TextBufferView into this buffer."""
        _nb.text_buffer.buffer_draw_text_buffer_view(self._ptr, view.ptr, x, y)

    def _check_bounds(self, x: int, y: int) -> int:
        """Validate (x, y) is within buffer dimensions. Returns width."""
        w = self.get_width()
        h = self.get_height()
        if x < 0 or x >= w or y < 0 or y >= h:
            raise IndexError(f"cell ({x}, {y}) out of bounds for {w}x{h} buffer")
        return w

    def get_fg_color(self, x: int, y: int) -> tuple[float, float, float, float]:
        """Read the foreground RGBA at cell (x, y) via the raw fg pointer."""
        w = self._check_bounds(x, y)
        ptr_int = _nb.buffer.buffer_get_fg_ptr(self._ptr)
        offset = (y * w + x) * 4  # 4 floats per cell
        arr = (ctypes.c_float * 4).from_address(ptr_int + offset * ctypes.sizeof(ctypes.c_float))
        return (arr[0], arr[1], arr[2], arr[3])

    def get_bg_color(self, x: int, y: int) -> tuple[float, float, float, float]:
        """Read the background RGBA at cell (x, y) via the raw bg pointer."""
        w = self._check_bounds(x, y)
        ptr_int = _nb.buffer.buffer_get_bg_ptr(self._ptr)
        offset = (y * w + x) * 4
        arr = (ctypes.c_float * 4).from_address(ptr_int + offset * ctypes.sizeof(ctypes.c_float))
        return (arr[0], arr[1], arr[2], arr[3])

    def get_attributes(self, x: int, y: int) -> int:
        """Read the attribute bitmask at cell (x, y)."""
        w = self._check_bounds(x, y)
        ptr_int = _nb.buffer.buffer_get_attributes_ptr(self._ptr)
        offset = y * w + x
        arr = (ctypes.c_uint32 * 1).from_address(ptr_int + offset * ctypes.sizeof(ctypes.c_uint32))
        return arr[0]

    def get_char(self, x: int, y: int) -> int:
        """Read the character code at cell (x, y)."""
        w = self._check_bounds(x, y)
        ptr_int = _nb.buffer.buffer_get_char_ptr(self._ptr)
        offset = y * w + x
        arr = (ctypes.c_uint32 * 1).from_address(ptr_int + offset * ctypes.sizeof(ctypes.c_uint32))
        return arr[0]


def encode_unicode(text: str, width_method: int = 0) -> list[tuple[int, int]]:
    """Encode text into list of (width, char_code) tuples using the native encoder."""
    text_bytes = text.encode("utf-8")
    return _nb.buffer.encode_unicode(text_bytes, width_method)


class NativeTextBuffer:
    """Wrapper for native text buffer using nanobind bindings.

    The Zig text buffer stores borrowed pointers to appended text data
    (via mem_registry with owned=false). To prevent dangling pointers,
    we keep Python bytes objects alive in _pinned_buffers for the
    lifetime of the text buffer.
    """

    def __init__(self, encoding: int = 0):
        self._ptr: Any = _nb.text_buffer.create_text_buffer(encoding)
        self._pinned_buffers: list[bytes] = []

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.text_buffer.destroy_text_buffer(self._ptr)
                self._ptr = None
            self._pinned_buffers.clear()
        except Exception:
            pass

    @property
    def ptr(self) -> Any:
        return self._ptr

    def set_text(self, text: str) -> None:
        """Set text content, replacing any existing content.

        Implemented as clear() + append() to avoid raw pointer FFI complexities
        while achieving the same result as set_text.
        """
        _nb.text_buffer.text_buffer_clear(self._ptr)
        self._pinned_buffers.clear()
        if text:
            text_bytes = text.encode("utf-8")
            self._pinned_buffers.append(text_bytes)
            _nb.text_buffer.text_buffer_append(self._ptr, text_bytes, len(text_bytes))

    def set_styled_text(self, chunks: list[dict]) -> None:
        """Set styled text from a list of chunk dicts, replacing existing content.

        Each chunk dict should have:
          - text (str): the text content
          - fg (RGBA | None): optional foreground color with r, g, b, a floats (0-1)
          - bg (RGBA | None): optional background color with r, g, b, a floats (0-1)
          - attributes (int): optional text attribute bitmask (default 0)
          - link (str | None): optional link URL

        Serializes styled text chunks into the native StyledChunk layout.
        """
        if not chunks:
            _nb.text_buffer.text_buffer_clear(self._ptr)
            self._pinned_buffers.clear()
            return

        self._pinned_buffers.clear()

        # Bypass nanobind binding (const char* cannot transport embedded null bytes).
        # Zig StyledChunk layout (extern struct, 64-bit):
        #   text_ptr:   [*]const u8   (8 bytes, pointer)
        #   text_len:   usize         (8 bytes)
        #   fg_ptr:     ?[*]const f32 (8 bytes, nullable pointer)
        #   bg_ptr:     ?[*]const f32 (8 bytes, nullable pointer)
        #   attributes: u32           (4 bytes + 4 bytes padding)
        #   link_ptr:   ?[*]const u8  (8 bytes, nullable pointer)
        #   link_len:   usize         (8 bytes)
        # Total: 56 bytes per chunk

        chunk_count = len(chunks)
        chunk_array = (_StyledChunk * chunk_count)()

        pinned: list[Any] = []

        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            text_bytes = text.encode("utf-8")
            c_text = ctypes.create_string_buffer(text_bytes, len(text_bytes))
            pinned.append(c_text)
            chunk_array[i].text_ptr = ctypes.cast(c_text, ctypes.c_void_p).value
            chunk_array[i].text_len = len(text_bytes)

            fg = chunk.get("fg")
            if fg is not None:
                fg_arr = _ColorArray()
                fg_arr.values[0] = float(fg.r if hasattr(fg, "r") else fg[0])
                fg_arr.values[1] = float(fg.g if hasattr(fg, "g") else fg[1])
                fg_arr.values[2] = float(fg.b if hasattr(fg, "b") else fg[2])
                fg_arr.values[3] = float(fg.a if hasattr(fg, "a") else fg[3])
                pinned.append(fg_arr)
                chunk_array[i].fg_ptr = ctypes.cast(ctypes.pointer(fg_arr), ctypes.c_void_p).value
            else:
                chunk_array[i].fg_ptr = 0

            bg = chunk.get("bg")
            if bg is not None:
                bg_arr = _ColorArray()
                bg_arr.values[0] = float(bg.r if hasattr(bg, "r") else bg[0])
                bg_arr.values[1] = float(bg.g if hasattr(bg, "g") else bg[1])
                bg_arr.values[2] = float(bg.b if hasattr(bg, "b") else bg[2])
                bg_arr.values[3] = float(bg.a if hasattr(bg, "a") else bg[3])
                pinned.append(bg_arr)
                chunk_array[i].bg_ptr = ctypes.cast(ctypes.pointer(bg_arr), ctypes.c_void_p).value
            else:
                chunk_array[i].bg_ptr = 0

            chunk_array[i].attributes = chunk.get("attributes", 0)
            chunk_array[i]._pad = 0

            link = chunk.get("link")
            if link:
                link_url = link if isinstance(link, str) else link.get("url", "")
                link_bytes = link_url.encode("utf-8")
                c_link = ctypes.create_string_buffer(link_bytes, len(link_bytes))
                pinned.append(c_link)
                chunk_array[i].link_ptr = ctypes.cast(c_link, ctypes.c_void_p).value
                chunk_array[i].link_len = len(link_bytes)
            else:
                chunk_array[i].link_ptr = 0
                chunk_array[i].link_len = 0

        _zig_set_styled = _get_zig_set_styled_text()

        buf_ptr = self._ptr
        if not isinstance(buf_ptr, int):
            ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
            ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [
                ctypes.py_object,
                ctypes.c_char_p,
            ]
            buf_ptr = ctypes.pythonapi.PyCapsule_GetPointer(
                buf_ptr,
                b"nb_handle",
            )

        _zig_set_styled(
            ctypes.c_void_p(buf_ptr),
            ctypes.cast(chunk_array, ctypes.c_void_p),
            chunk_count,
        )

    def append(self, text: str) -> None:
        text_bytes = text.encode("utf-8")
        self._pinned_buffers.append(text_bytes)
        _nb.text_buffer.text_buffer_append(self._ptr, text_bytes, len(text_bytes))

    def clear(self) -> None:
        _nb.text_buffer.text_buffer_clear(self._ptr)
        self._pinned_buffers.clear()

    def reset(self) -> None:
        _nb.text_buffer.text_buffer_reset(self._ptr)
        self._pinned_buffers.clear()

    def get_length(self) -> int:
        return _nb.text_buffer.text_buffer_get_length(self._ptr)

    def get_byte_size(self) -> int:
        return _nb.text_buffer.text_buffer_get_byte_size(self._ptr)

    def get_line_count(self) -> int:
        return _nb.text_buffer.text_buffer_get_line_count(self._ptr)

    def get_plain_text(self, max_len: int = 0) -> str:
        if max_len <= 0:
            max_len = self.get_byte_size() + 1
        result = _nb.text_buffer.text_buffer_get_plain_text(self._ptr, max_len)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return result

    def get_text_range(self, start: int, end: int, max_len: int = 0) -> str:
        if max_len <= 0:
            max_len = self.get_byte_size() + 1
        result = _nb.text_buffer.text_buffer_get_text_range(self._ptr, start, end, max_len)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return result

    def set_default_fg(self) -> None:
        """Set default foreground color (currently resets to None)."""
        _nb.text_buffer.text_buffer_set_default_fg(self._ptr)

    def set_default_bg(self) -> None:
        """Set default background color (currently resets to None)."""
        _nb.text_buffer.text_buffer_set_default_bg(self._ptr)

    def set_default_attributes(self, attrs: int) -> None:
        """Set default text attributes."""
        _nb.text_buffer.text_buffer_set_default_attributes(self._ptr, attrs)

    def reset_defaults(self) -> None:
        """Reset all default styles."""
        _nb.text_buffer.text_buffer_reset_defaults(self._ptr)

    def set_tab_width(self, width: int) -> None:
        _nb.text_buffer.text_buffer_set_tab_width(self._ptr, width)

    def get_tab_width(self) -> int:
        return _nb.text_buffer.text_buffer_get_tab_width(self._ptr)

    def append_from_mem_id(self, mem_id: int) -> None:
        _nb.text_buffer.text_buffer_append_from_mem_id(self._ptr, mem_id)

    def get_text_range_by_coords(
        self, start_row: int, start_col: int, end_row: int, end_col: int, max_len: int = 0
    ) -> str:
        if max_len <= 0:
            max_len = self.get_byte_size() + 1
        result = _nb.text_buffer.text_buffer_get_text_range_by_coords(
            self._ptr, start_row, start_col, end_row, end_col, max_len
        )
        return result.decode("utf-8") if isinstance(result, bytes) else result

    # -- Highlight API --

    def add_highlight(
        self,
        line_idx: int,
        start: int,
        end: int,
        style_id: int = 0,
        priority: int = 0,
        hl_ref: int = 0,
    ) -> None:
        _nb.text_buffer.text_buffer_add_highlight(
            self._ptr, line_idx, start, end, style_id, priority, hl_ref
        )

    def add_highlight_by_char_range(
        self, start: int, end: int, style_id: int = 0, priority: int = 0, hl_ref: int = 0
    ) -> None:
        _nb.text_buffer.text_buffer_add_highlight_by_char_range(
            self._ptr, start, end, style_id, priority, hl_ref
        )

    def remove_highlights_by_ref(self, hl_ref: int) -> None:
        _nb.text_buffer.text_buffer_remove_highlights_by_ref(self._ptr, hl_ref)

    def clear_line_highlights(self, line_idx: int) -> None:
        _nb.text_buffer.text_buffer_clear_line_highlights(self._ptr, line_idx)

    def clear_all_highlights(self) -> None:
        _nb.text_buffer.text_buffer_clear_all_highlights(self._ptr)

    def set_syntax_style(self, style: NativeSyntaxStyle | None) -> None:
        ptr = style.ptr if style is not None else None
        _nb.text_buffer.text_buffer_set_syntax_style(self._ptr, ptr)

    def get_line_highlights(self, line_idx: int) -> list[dict]:
        return _nb.text_buffer.text_buffer_get_line_highlights(self._ptr, line_idx)

    def get_highlight_count(self) -> int:
        return _nb.text_buffer.text_buffer_get_highlight_count(self._ptr)


class NativeSyntaxStyle:
    """Wrapper for native syntax style definition."""

    def __init__(self):
        self._ptr: Any = _nb.text_buffer.create_syntax_style()

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.text_buffer.destroy_syntax_style(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> Any:
        return self._ptr

    def register(
        self,
        name: str,
        fg: list[float] | None = None,
        bg: list[float] | None = None,
        attributes: int = 0,
    ) -> int:
        """Register a named style. Returns the style ID."""
        return _nb.text_buffer.syntax_style_register(self._ptr, name, fg, bg, attributes)

    def resolve_by_name(self, name: str) -> int:
        """Resolve a style name to its ID. Returns 0 if not found."""
        return _nb.text_buffer.syntax_style_resolve_by_name(self._ptr, name)

    def get_style_count(self) -> int:
        return _nb.text_buffer.syntax_style_get_style_count(self._ptr)

    def destroy(self) -> None:
        if self._ptr:
            _nb.text_buffer.destroy_syntax_style(self._ptr)
            self._ptr = None


class NativeTextBufferView:
    """Wrapper for native text buffer view using nanobind bindings."""

    # Wrap mode constants
    WRAP_MODE_NONE = 0
    WRAP_MODE_CHAR = 1
    WRAP_MODE_WORD = 2

    def __init__(self, buffer_ptr: Any, text_buffer: NativeTextBuffer | None = None):
        self._ptr: Any = _nb.text_buffer.create_text_buffer_view(buffer_ptr)
        self._text_buffer = text_buffer

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.text_buffer.destroy_text_buffer_view(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> Any:
        return self._ptr

    def set_viewport(self, x: int, y: int, width: int, height: int) -> None:
        _nb.text_buffer.text_buffer_view_set_viewport(self._ptr, x, y, width, height)

    def set_wrap_width(self, width: int) -> None:
        _nb.text_buffer.text_buffer_view_set_wrap_width(self._ptr, width)

    def set_wrap_mode(self, mode: int | str) -> None:
        """Set wrap mode. Accepts int (0=none, 1=char, 2=word) or string ('none', 'char', 'word')."""
        if isinstance(mode, str):
            mode_map = {"none": 0, "char": 1, "word": 2}
            mode = mode_map.get(mode, 0)
        _nb.text_buffer.text_buffer_view_set_wrap_mode(self._ptr, mode)

    def set_viewport_size(self, width: int, height: int) -> None:
        _nb.text_buffer.text_buffer_view_set_viewport_size(self._ptr, width, height)

    def get_virtual_line_count(self) -> int:
        return _nb.text_buffer.text_buffer_view_get_virtual_line_count(self._ptr)

    def set_selection(self, start: int, end: int) -> None:
        """Set selection range by character offsets."""
        _nb.text_buffer.text_buffer_view_set_selection(self._ptr, start, end)

    def reset_selection(self) -> None:
        """Clear/reset the current selection."""
        _nb.text_buffer.text_buffer_view_reset_selection(self._ptr)

    def get_selection_info(self) -> int:
        """Get packed selection info as u64. Use unpack helpers to extract start/end."""
        return _nb.text_buffer.text_buffer_view_get_selection_info(self._ptr)

    def get_selection(self) -> dict[str, int] | None:
        """Get selection as {start, end} dict, or None if no selection."""
        packed = self.get_selection_info()
        if packed == 0xFFFF_FFFF_FFFF_FFFF:
            return None
        start = (packed >> 32) & 0xFFFF_FFFF
        end = packed & 0xFFFF_FFFF
        return {"start": start, "end": end}

    def has_selection(self) -> bool:
        """Check if there is an active selection."""
        return self.get_selection() is not None

    def update_selection(self, end: int) -> None:
        """Update selection end point (extends existing selection)."""
        _nb.text_buffer.text_buffer_view_update_selection(self._ptr, end)

    def set_local_selection(
        self,
        anchor_x: int,
        anchor_y: int,
        focus_x: int,
        focus_y: int,
        bg_color: Any = None,
        fg_color: Any = None,
    ) -> bool:
        """Set local (coordinate-based) selection with optional colors.

        Returns True if selection changed.
        """
        bg = _rgba_to_list(bg_color)
        fg = _rgba_to_list(fg_color)
        try:
            return _nb.text_buffer.text_buffer_view_set_local_selection(
                self._ptr, anchor_x, anchor_y, focus_x, focus_y, bg, fg
            )
        except TypeError:
            # Fallback for native bindings without color parameter support
            return _nb.text_buffer.text_buffer_view_set_local_selection(
                self._ptr, anchor_x, anchor_y, focus_x, focus_y
            )

    def update_local_selection(
        self,
        anchor_x: int,
        anchor_y: int,
        focus_x: int,
        focus_y: int,
        bg_color: Any = None,
        fg_color: Any = None,
    ) -> bool:
        """Update local (coordinate-based) selection with optional colors.

        Returns True if selection changed.
        """
        bg = _rgba_to_list(bg_color)
        fg = _rgba_to_list(fg_color)
        try:
            return _nb.text_buffer.text_buffer_view_update_local_selection(
                self._ptr, anchor_x, anchor_y, focus_x, focus_y, bg, fg
            )
        except TypeError:
            # Fallback for native bindings without color parameter support
            return _nb.text_buffer.text_buffer_view_update_local_selection(
                self._ptr, anchor_x, anchor_y, focus_x, focus_y
            )

    def reset_local_selection(self) -> None:
        """Reset local selection."""
        _nb.text_buffer.text_buffer_view_reset_local_selection(self._ptr)

    def get_line_info(self) -> dict:
        """Get cached line info. Returns dict with start_cols, width_cols, sources, wraps, width_cols_max."""
        return _nb.text_buffer.text_buffer_view_get_line_info(self._ptr)

    def get_logical_line_info(self) -> dict:
        """Get logical line info. Returns dict with start_cols, width_cols, sources, wraps, width_cols_max."""
        return _nb.text_buffer.text_buffer_view_get_logical_line_info(self._ptr)

    def get_selected_text(self) -> str:
        """Get the currently selected text."""
        raw: bytes = _nb.text_buffer.text_buffer_view_get_selected_text(self._ptr)
        return raw.decode("utf-8") if raw else ""

    def set_tab_indicator(self, indicator: int) -> None:
        """Set tab indicator character (Unicode codepoint)."""
        _nb.text_buffer.text_buffer_view_set_tab_indicator(self._ptr, indicator)

    def set_tab_indicator_color(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        """Set tab indicator color (RGBA, 0.0-1.0 range)."""
        _nb.text_buffer.text_buffer_view_set_tab_indicator_color(self._ptr, r, g, b, a)

    def set_truncate(self, truncate: bool) -> None:
        """Set whether to truncate lines that exceed viewport width."""
        _nb.text_buffer.text_buffer_view_set_truncate(self._ptr, truncate)

    def measure(self, width: int, height: int) -> tuple[int, int]:
        """Measure for given dimensions. Returns (width_cols_max, line_count)."""
        return _nb.text_buffer.text_buffer_view_measure_for_dimensions(self._ptr, width, height)

    def measure_for_dimensions(self, width: int, height: int) -> dict[str, int] | None:
        """Measure for given dimensions. Returns dict with lineCount and widthColsMax, or None."""
        result = _nb.text_buffer.text_buffer_view_measure_for_dimensions(self._ptr, width, height)
        if result is None:
            return None
        line_count, width_cols_max = result
        return {"lineCount": line_count, "widthColsMax": width_cols_max}

    def get_plain_text(self) -> str:
        """Get plain text via the view's native binding."""
        raw: bytes = _nb.text_buffer.text_buffer_view_get_plain_text(self._ptr)
        if raw:
            return raw.decode("utf-8")
        if self._text_buffer is not None:
            return self._text_buffer.get_plain_text()
        return ""


class NativeEditBuffer:
    """Wrapper for native edit buffer using nanobind bindings."""

    def __init__(self, encoding: int = 0):
        self._ptr: Any = _nb.edit_buffer.create_edit_buffer(encoding)
        self._text_buffer_ptr: Any = _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)
        self._single_text_mem_id: int | None = None
        self._single_text_bytes: bytes | None = None  # prevent GC while Zig holds pointer
        self._event_listeners: dict[str, list] = {"cursor_changed": [], "content_changed": []}
        self._destroyed = False

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.edit_buffer.destroy_edit_buffer(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> Any:
        return self._ptr

    def insert_text(self, text: str) -> None:
        _nb.edit_buffer.edit_buffer_insert_text(self._ptr, text)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def delete_char(self) -> None:
        _nb.edit_buffer.edit_buffer_delete_char(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def delete_char_backward(self) -> None:
        _nb.edit_buffer.edit_buffer_delete_char_backward(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def set_text(self, text: str) -> None:
        if self._ptr is None:
            raise RuntimeError("EditBuffer is destroyed")
        text_bytes = text.encode("utf-8")
        tb = self._text_buffer_ptr
        if self._single_text_mem_id is not None:
            _nb.text_buffer.text_buffer_replace_mem_buffer(
                tb,
                self._single_text_mem_id,
                text_bytes,
                len(text_bytes),
                False,
            )
        else:
            self._single_text_mem_id = _nb.text_buffer.text_buffer_register_mem_buffer(
                tb,
                text_bytes,
                len(text_bytes),
                False,
            )
        self._single_text_bytes = text_bytes  # prevent GC while Zig holds pointer
        _nb.edit_buffer.edit_buffer_set_text_from_mem(self._ptr, self._single_text_mem_id)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def move_cursor_left(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_left(self._ptr)
        self._emit("cursor_changed")

    def move_cursor_right(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_right(self._ptr)
        self._emit("cursor_changed")

    def move_cursor_up(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_up(self._ptr)
        self._emit("cursor_changed")

    def move_cursor_down(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_down(self._ptr)
        self._emit("cursor_changed")

    def goto_line(self, line: int) -> None:
        _nb.edit_buffer.edit_buffer_goto_line(self._ptr, line)
        self._emit("cursor_changed")

    def can_undo(self) -> bool:
        return _nb.edit_buffer.edit_buffer_can_undo(self._ptr)

    def can_redo(self) -> bool:
        return _nb.edit_buffer.edit_buffer_can_redo(self._ptr)

    def undo(self, max_len: int = 0) -> str:
        if max_len <= 0:
            tb_ptr = _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)
            max_len = _nb.text_buffer.text_buffer_get_byte_size(tb_ptr) + 1
        result = _nb.edit_buffer.edit_buffer_undo(self._ptr, max_len)
        if isinstance(result, bytes):
            result = result.decode("utf-8")
        self._emit("content_changed")
        self._emit("cursor_changed")
        return result

    def redo(self, max_len: int = 0) -> str:
        if max_len <= 0:
            tb_ptr = _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)
            max_len = _nb.text_buffer.text_buffer_get_byte_size(tb_ptr) + 1
        result = _nb.edit_buffer.edit_buffer_redo(self._ptr, max_len)
        if isinstance(result, bytes):
            result = result.decode("utf-8")
        self._emit("content_changed")
        self._emit("cursor_changed")
        return result

    def get_text(self, max_len: int = 0) -> str:
        if max_len <= 0:
            tb_ptr = _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)
            max_len = _nb.text_buffer.text_buffer_get_byte_size(tb_ptr) + 1
        result = _nb.edit_buffer.edit_buffer_get_text(self._ptr, max_len)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return result

    def set_cursor(self, line: int, col: int) -> None:
        _nb.edit_buffer.edit_buffer_set_cursor(self._ptr, line, col)
        self._emit("cursor_changed")

    def get_cursor_position(self) -> tuple[int, int]:
        # The native API writes (line, col) as two consecutive int32 values
        # into the first capsule pointer (8 bytes total).
        ctypes.pythonapi.PyCapsule_New.restype = ctypes.py_object
        ctypes.pythonapi.PyCapsule_New.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_void_p,
        ]
        buf = (ctypes.c_int32 * 2)(0, 0)
        dummy = ctypes.c_int64(0)
        buf_cap = ctypes.pythonapi.PyCapsule_New(ctypes.addressof(buf), b"nb_handle", None)
        dummy_cap = ctypes.pythonapi.PyCapsule_New(ctypes.addressof(dummy), b"nb_handle", None)
        _nb.edit_buffer.edit_buffer_get_cursor_position(self._ptr, buf_cap, dummy_cap)
        return (buf[0], buf[1])

    def delete_range(self, start_line: int, start_col: int, end_line: int, end_col: int) -> None:
        _nb.edit_buffer.edit_buffer_delete_range(
            self._ptr, start_line, start_col, end_line, end_col
        )
        self._emit("content_changed")
        self._emit("cursor_changed")

    def newline(self) -> None:
        _nb.edit_buffer.edit_buffer_new_line(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def destroy(self) -> None:
        self._destroyed = True
        self._event_listeners = {"cursor_changed": [], "content_changed": []}
        if self._ptr:
            _nb.edit_buffer.destroy_edit_buffer(self._ptr)
            self._ptr = None

    # -- Event system --

    def on(self, event: str, callback) -> None:
        """Register an event listener."""
        if event in self._event_listeners:
            self._event_listeners[event].append(callback)

    def off(self, event: str, callback) -> None:
        """Remove an event listener."""
        if event in self._event_listeners:
            with contextlib.suppress(ValueError):
                self._event_listeners[event].remove(callback)

    def _emit(self, event: str, *args) -> None:
        """Emit an event to all registered listeners."""
        if self._destroyed:
            return
        for listener in self._event_listeners.get(event, []):
            listener(*args)

    # -- Python-level wrapper methods --

    def clear(self) -> None:
        """Clear all text and reset cursor to (0, 0)."""
        self.set_text("")
        self.set_cursor(0, 0)

    def move_to_line_start(self) -> None:
        """Move cursor to the beginning of the current line."""
        line, _ = self.get_cursor_position()
        self.set_cursor(line, 0)

    def move_to_line_end(self) -> None:
        """Move cursor to the end of the current line."""
        line, _ = self.get_cursor_position()
        text = self.get_text()
        lines = text.split("\n")
        if line < len(lines):
            self.set_cursor(line, len(lines[line]))
        else:
            self.set_cursor(line, 0)

    def delete_line(self, line: int | None = None) -> None:
        """Delete an entire line. If line is None, deletes the current line."""
        if line is None:
            line, _ = self.get_cursor_position()
        text = self.get_text()
        lines = text.split("\n")
        if line < 0 or line >= len(lines):
            return
        if len(lines) == 1:
            self.set_text("")
            self.set_cursor(0, 0)
        elif line == len(lines) - 1:
            self.delete_range(line - 1, len(lines[line - 1]), line, len(lines[line]))
            self.set_cursor(line - 1 if line > 0 else 0, 0)
        else:
            self.delete_range(line, 0, line + 1, 0)
            self.set_cursor(min(line, len(lines) - 2), 0)

    def delete_to_line_end(self) -> None:
        """Delete from cursor to end of current line."""
        line, col = self.get_cursor_position()
        text = self.get_text()
        lines = text.split("\n")
        if line < len(lines):
            line_len = len(lines[line])
            if col < line_len:
                self.delete_range(line, col, line, line_len)

    def get_line_count(self) -> int:
        """Get the number of lines in the buffer."""
        text = self.get_text()
        if not text:
            return 1
        return text.count("\n") + 1

    def get_line(self, line: int) -> str:
        """Get the text of a specific line."""
        text = self.get_text()
        lines = text.split("\n")
        if 0 <= line < len(lines):
            return lines[line]
        return ""

    def get_line_length(self, line: int) -> int:
        """Get the length of a specific line."""
        return len(self.get_line(line))

    def get_next_word_boundary(self, line: int, col: int) -> tuple[int, int]:
        """Find the next word boundary from position (line, col)."""
        text = self.get_text()
        lines = text.split("\n")
        if line >= len(lines):
            return (line, col)

        current_line = lines[line]
        pos = col

        while (
            pos < len(current_line)
            and not current_line[pos].isspace()
            and current_line[pos].isalnum()
        ):
            pos += 1
        while pos < len(current_line) and (
            current_line[pos].isspace() or not current_line[pos].isalnum()
        ):
            pos += 1

        if pos < len(current_line):
            return (line, pos)
        if line + 1 < len(lines):
            return (line + 1, 0)
        return (line, len(current_line))

    def get_previous_word_boundary(self, line: int, col: int) -> tuple[int, int]:
        """Find the previous word boundary from position (line, col)."""
        text = self.get_text()
        lines = text.split("\n")
        if line >= len(lines):
            return (line, col)

        current_line = lines[line]
        pos = col

        if pos <= 0:
            if line > 0:
                prev_line = lines[line - 1]
                return (line - 1, len(prev_line))
            return (0, 0)

        pos -= 1
        while pos > 0 and (current_line[pos].isspace() or not current_line[pos].isalnum()):
            pos -= 1
        while pos > 0 and current_line[pos - 1].isalnum():
            pos -= 1

        return (line, pos)

    def offset_to_position(self, offset: int) -> tuple[int, int] | None:
        """Convert a byte offset to (line, col) position."""
        text = self.get_text()
        if offset < 0 or offset > len(text):
            return None
        prefix = text[:offset]
        line = prefix.count("\n")
        last_nl = prefix.rfind("\n")
        col = offset - (last_nl + 1)
        return (line, col)

    def position_to_offset(self, line: int, col: int) -> int:
        """Convert (line, col) position to character offset."""
        text = self.get_text()
        lines = text.split("\n")
        if line < 0 or line >= len(lines):
            return -1
        offset = sum(len(lines[i]) + 1 for i in range(line)) + col
        return offset

    def get_line_start_offset(self, line: int) -> int:
        """Get the character offset of the start of a line."""
        text = self.get_text()
        lines = text.split("\n")
        if line < 0 or line >= len(lines):
            return -1
        return sum(len(lines[i]) + 1 for i in range(line))

    def get_eol(self, line: int) -> int:
        """Get the column position of the end of a given line."""
        text = self.get_text()
        lines = text.split("\n")
        if 0 <= line < len(lines):
            return len(lines[line])
        return 0

    def replace_text(
        self, start_line: int, start_col: int, end_line: int, end_col: int, text: str
    ) -> None:
        """Replace text in a range with new text, creating undo history."""
        self.delete_range(start_line, start_col, end_line, end_col)
        self.set_cursor(start_line, start_col)
        self.insert_text(text)

    # -- Native-backed methods (use Zig implementation instead of Python) --

    def get_text_buffer_ptr(self) -> Any:
        """Get the underlying TextBuffer pointer. Useful for highlight operations."""
        return _nb.edit_buffer.edit_buffer_get_text_buffer(self._ptr)

    def set_cursor_by_offset(self, offset: int) -> None:
        """Set cursor position by byte offset."""
        _nb.edit_buffer.edit_buffer_set_cursor_by_offset(self._ptr, offset)
        self._emit("cursor_changed")

    def get_cursor_native(self) -> tuple[int, int]:
        """Get cursor position using native binding (simpler than PyCapsule approach)."""
        return _nb.edit_buffer.edit_buffer_get_cursor(self._ptr)

    def get_next_word_boundary_native(self) -> tuple[int, int, int]:
        """Get next word boundary. Returns (row, col, offset)."""
        return _nb.edit_buffer.edit_buffer_get_next_word_boundary(self._ptr)

    def get_prev_word_boundary_native(self) -> tuple[int, int, int]:
        """Get previous word boundary. Returns (row, col, offset)."""
        return _nb.edit_buffer.edit_buffer_get_prev_word_boundary(self._ptr)

    def get_eol_native(self) -> tuple[int, int, int]:
        """Get end-of-line position. Returns (row, col, offset)."""
        return _nb.edit_buffer.edit_buffer_get_eol(self._ptr)

    def offset_to_position_native(self, offset: int) -> tuple[int, int, int] | None:
        """Convert byte offset to (row, col, offset). Returns None if invalid."""
        result = _nb.edit_buffer.edit_buffer_offset_to_position(self._ptr, offset)
        return result  # None if invalid, tuple otherwise

    def position_to_offset_native(self, row: int, col: int) -> int:
        """Convert (row, col) to byte offset using native implementation."""
        return _nb.edit_buffer.edit_buffer_position_to_offset(self._ptr, row, col)

    def get_line_start_offset_native(self, row: int) -> int:
        """Get byte offset of start of a line using native implementation."""
        return _nb.edit_buffer.edit_buffer_get_line_start_offset(self._ptr, row)

    def get_text_range_native(self, start_offset: int, end_offset: int, max_len: int = 0) -> str:
        """Get text in a byte offset range using native implementation."""
        if max_len <= 0:
            max_len = (end_offset - start_offset) + 1
        result = _nb.edit_buffer.edit_buffer_get_text_range(
            self._ptr, start_offset, end_offset, max_len
        )
        return result.decode("utf-8") if isinstance(result, bytes) else result

    def get_text_range_by_coords_native(
        self, start_row: int, start_col: int, end_row: int, end_col: int, max_len: int = 65_536
    ) -> str:
        """Get text in a coordinate range using native implementation."""
        result = _nb.edit_buffer.edit_buffer_get_text_range_by_coords(
            self._ptr, start_row, start_col, end_row, end_col, max_len
        )
        return result.decode("utf-8") if isinstance(result, bytes) else result

    def replace_text_native(self, text: str) -> None:
        """Replace all text non-destructively (preserves cursor where possible)."""
        _nb.edit_buffer.edit_buffer_replace_text(self._ptr, text)
        self._emit("content_changed")

    def clear_native(self) -> None:
        """Clear all text using native implementation."""
        _nb.edit_buffer.edit_buffer_clear(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def clear_history(self) -> None:
        """Clear undo/redo history."""
        _nb.edit_buffer.edit_buffer_clear_history(self._ptr)

    def delete_line_native(self) -> None:
        """Delete the current line using native implementation."""
        _nb.edit_buffer.edit_buffer_delete_line(self._ptr)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def insert_char(self, ch: str) -> None:
        """Insert a single character (alias for insertChar in Zig)."""
        _nb.edit_buffer.edit_buffer_insert_char(self._ptr, ch)
        self._emit("content_changed")
        self._emit("cursor_changed")

    def get_id(self) -> int:
        """Get the unique buffer ID."""
        return _nb.edit_buffer.edit_buffer_get_id(self._ptr)


class VisualCursor:
    """Represents a cursor position with both visual and logical coordinates."""

    __slots__ = ("visual_row", "visual_col", "logical_row", "logical_col", "offset")

    def __init__(
        self,
        visual_row: int = 0,
        visual_col: int = 0,
        logical_row: int = 0,
        logical_col: int = 0,
        offset: int = 0,
    ):
        self.visual_row = visual_row
        self.visual_col = visual_col
        self.logical_row = logical_row
        self.logical_col = logical_col
        self.offset = offset

    def __repr__(self) -> str:
        return (
            f"VisualCursor(visual_row={self.visual_row}, visual_col={self.visual_col}, "
            f"logical_row={self.logical_row}, logical_col={self.logical_col}, offset={self.offset})"
        )


# Wrap mode constants matching zig enum values
_WRAP_MODE_NONE = 0
_WRAP_MODE_CHAR = 1
_WRAP_MODE_WORD = 2

_WRAP_MODE_MAP: dict[str, int] = {
    "none": _WRAP_MODE_NONE,
    "char": _WRAP_MODE_CHAR,
    "word": _WRAP_MODE_WORD,
}


def _tuple_to_visual_cursor(t: tuple) -> VisualCursor:
    """Convert a (visual_row, visual_col, logical_row, logical_col, offset) tuple to VisualCursor."""
    return VisualCursor(
        visual_row=t[0],
        visual_col=t[1],
        logical_row=t[2],
        logical_col=t[3],
        offset=t[4],
    )


class NativeEditorView:
    """Wrapper for native editor view using nanobind bindings."""

    def __init__(self, buffer_ptr: Any, width: int, height: int):
        self._ptr: Any = _nb.editor_view.create_editor_view(buffer_ptr, width, height)
        self._destroyed = False
        self._width = width
        self._height = height

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr and not self._destroyed:
                _nb.editor_view.destroy_editor_view(self._ptr)
                self._ptr = None
        except Exception:
            pass

    def _guard(self) -> None:
        """Raise an error if the view has been destroyed."""
        if self._destroyed:
            raise RuntimeError("EditorView is destroyed")

    @property
    def ptr(self) -> Any:
        self._guard()
        return self._ptr

    def destroy(self) -> None:
        """Destroy the editor view and free resources."""
        if self._destroyed:
            return
        self._destroyed = True
        if self._ptr:
            _nb.editor_view.destroy_editor_view(self._ptr)
            self._ptr = None

    def set_viewport(self, x: int, y: int, width: int, height: int) -> None:
        self._guard()
        _nb.editor_view.editor_view_set_viewport(self._ptr, x, y, width, height)

    def set_viewport_size(self, width: int, height: int) -> None:
        self._guard()
        self._width = width
        self._height = height
        _nb.editor_view.editor_view_set_viewport_size(self._ptr, width, height)

    def get_viewport(self) -> dict:
        """Get viewport as dict with offsetX, offsetY, width, height."""
        self._guard()
        ctypes.pythonapi.PyCapsule_New.restype = ctypes.py_object
        ctypes.pythonapi.PyCapsule_New.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_void_p,
        ]
        buf = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        caps = []
        for i in range(4):
            cap = ctypes.pythonapi.PyCapsule_New(ctypes.addressof(buf) + i * 4, b"nb_handle", None)
            caps.append(cap)
        _nb.editor_view.editor_view_get_viewport(self._ptr, caps[0], caps[1], caps[2], caps[3])
        return {
            "offsetX": buf[0],
            "offsetY": buf[1],
            "width": buf[2],
            "height": buf[3],
        }

    def set_scroll_margin(self, margin: float) -> None:
        self._guard()
        _nb.editor_view.editor_view_set_scroll_margin(self._ptr, margin)

    def set_wrap_mode(self, mode: str) -> None:
        self._guard()
        mode_val = _WRAP_MODE_MAP.get(mode, _WRAP_MODE_NONE)
        _nb.editor_view.editor_view_set_wrap_mode(self._ptr, mode_val)

    def get_virtual_line_count(self) -> int:
        self._guard()
        return _nb.editor_view.editor_view_get_virtual_line_count(self._ptr)

    def get_total_virtual_line_count(self) -> int:
        self._guard()
        return _nb.editor_view.editor_view_get_total_virtual_line_count(self._ptr)

    def set_selection(
        self, start: int, end: int, bg_color: Any = None, fg_color: Any = None
    ) -> None:
        self._guard()
        bg = _rgba_to_list(bg_color)
        fg = _rgba_to_list(fg_color)
        _nb.editor_view.editor_view_set_selection(self._ptr, start, end, bg, fg)

    def update_selection(self, end: int, bg_color: Any = None, fg_color: Any = None) -> None:
        self._guard()
        bg = _rgba_to_list(bg_color)
        fg = _rgba_to_list(fg_color)
        _nb.editor_view.editor_view_update_selection(self._ptr, end, bg, fg)

    def reset_selection(self) -> None:
        self._guard()
        _nb.editor_view.editor_view_reset_selection(self._ptr)

    def get_selection(self) -> dict | None:
        """Get the current selection as {start, end} or None."""
        self._guard()
        raw = _nb.editor_view.editor_view_get_selection(self._ptr)
        # The zig returns a u64 where high 32 bits = start, low 32 bits = end
        # If no selection, it returns a sentinel value (all 1s)
        if raw == 0xFFFFFFFFFFFFFFFF:
            return None
        start = (raw >> 32) & 0xFFFFFFFF
        end = raw & 0xFFFFFFFF
        return {"start": start, "end": end}

    def has_selection(self) -> bool:
        return self.get_selection() is not None

    def set_local_selection(
        self,
        anchor_x: int,
        anchor_y: int,
        focus_x: int,
        focus_y: int,
        update_cursor: bool = False,
        follow_cursor: bool = False,
        bg_color: Any = None,
        fg_color: Any = None,
    ) -> bool:
        self._guard()
        bg = _rgba_to_list(bg_color)
        fg = _rgba_to_list(fg_color)
        return _nb.editor_view.editor_view_set_local_selection(
            self._ptr, anchor_x, anchor_y, focus_x, focus_y, bg, fg, update_cursor, follow_cursor
        )

    def update_local_selection(
        self,
        anchor_x: int,
        anchor_y: int,
        focus_x: int,
        focus_y: int,
        update_cursor: bool = False,
        follow_cursor: bool = False,
        bg_color: Any = None,
        fg_color: Any = None,
    ) -> bool:
        self._guard()
        bg = _rgba_to_list(bg_color)
        fg = _rgba_to_list(fg_color)
        return _nb.editor_view.editor_view_update_local_selection(
            self._ptr, anchor_x, anchor_y, focus_x, focus_y, bg, fg, update_cursor, follow_cursor
        )

    def reset_local_selection(self) -> None:
        self._guard()
        _nb.editor_view.editor_view_reset_local_selection(self._ptr)

    def get_selected_text(self, max_len: int = 65536) -> str:
        self._guard()
        result = _nb.editor_view.editor_view_get_selected_text(self._ptr, max_len)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return result

    def get_visual_cursor(self) -> VisualCursor:
        self._guard()
        t = _nb.editor_view.editor_view_get_visual_cursor(self._ptr)
        return _tuple_to_visual_cursor(t)

    def move_up_visual(self) -> None:
        self._guard()
        _nb.editor_view.editor_view_move_up_visual(self._ptr)

    def move_down_visual(self) -> None:
        self._guard()
        _nb.editor_view.editor_view_move_down_visual(self._ptr)

    def delete_selected_text(self) -> None:
        self._guard()
        _nb.editor_view.editor_view_delete_selected_text(self._ptr)

    def set_cursor_by_offset(self, offset: int) -> None:
        self._guard()
        _nb.editor_view.editor_view_set_cursor_by_offset(self._ptr, offset)

    def get_next_word_boundary(self) -> VisualCursor:
        self._guard()
        t = _nb.editor_view.editor_view_get_next_word_boundary(self._ptr)
        return _tuple_to_visual_cursor(t)

    def get_prev_word_boundary(self) -> VisualCursor:
        self._guard()
        t = _nb.editor_view.editor_view_get_prev_word_boundary(self._ptr)
        return _tuple_to_visual_cursor(t)

    def get_eol(self) -> VisualCursor:
        self._guard()
        t = _nb.editor_view.editor_view_get_eol(self._ptr)
        return _tuple_to_visual_cursor(t)

    def get_visual_sol(self) -> VisualCursor:
        self._guard()
        t = _nb.editor_view.editor_view_get_visual_sol(self._ptr)
        return _tuple_to_visual_cursor(t)

    def get_visual_eol(self) -> VisualCursor:
        self._guard()
        t = _nb.editor_view.editor_view_get_visual_eol(self._ptr)
        return _tuple_to_visual_cursor(t)

    # ===== New bindings =====

    def clear_viewport(self) -> None:
        """Clear/unset the viewport."""
        self._guard()
        _nb.editor_view.editor_view_clear_viewport(self._ptr)

    def get_line_info(self) -> dict:
        """Get cached line info for the viewport region."""
        self._guard()
        return _nb.editor_view.editor_view_get_line_info(self._ptr)

    def get_logical_line_info(self) -> dict:
        """Get logical (unwrapped) line info."""
        self._guard()
        return _nb.editor_view.editor_view_get_logical_line_info(self._ptr)

    def get_text_buffer_view_ptr(self) -> Any:
        """Get the underlying TextBufferView pointer."""
        self._guard()
        return _nb.editor_view.editor_view_get_text_buffer_view(self._ptr)

    def set_tab_indicator(self, indicator: int) -> None:
        """Set tab indicator character (Unicode codepoint)."""
        self._guard()
        _nb.editor_view.editor_view_set_tab_indicator(self._ptr, indicator)

    def set_tab_indicator_color(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        """Set tab indicator color (RGBA, 0.0-1.0 range)."""
        self._guard()
        _nb.editor_view.editor_view_set_tab_indicator_color(self._ptr, r, g, b, a)

    def get_text(self, max_len: int = 65536) -> str:
        """Get the text from the editor view."""
        self._guard()
        result = _nb.editor_view.editor_view_get_text(self._ptr, max_len)
        return result.decode("utf-8") if isinstance(result, bytes) else result

    def get_cursor(self) -> tuple[int, int]:
        """Get the cursor position as (row, col) using PyCapsule."""
        self._guard()
        ctypes.pythonapi.PyCapsule_New.restype = ctypes.py_object
        ctypes.pythonapi.PyCapsule_New.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_void_p,
        ]
        buf = (ctypes.c_uint32 * 2)(0, 0)
        row_cap = ctypes.pythonapi.PyCapsule_New(ctypes.addressof(buf), b"nb_handle", None)
        col_cap = ctypes.pythonapi.PyCapsule_New(ctypes.addressof(buf) + 4, b"nb_handle", None)
        _nb.editor_view.editor_view_get_cursor(self._ptr, row_cap, col_cap)
        return (buf[0], buf[1])


def is_available() -> bool:
    """Check if nanobind bindings are available."""
    return _NANOBIND_AVAILABLE


__all__ = [
    "NativeRenderer",
    "NativeBuffer",
    "NativeOptimizedBuffer",
    "NativeTextBuffer",
    "NativeTextBufferView",
    "NativeEditBuffer",
    "NativeEditorView",
    "NativeSyntaxStyle",
    "VisualCursor",
    "is_available",
]
