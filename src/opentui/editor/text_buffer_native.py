"""Native text buffer and syntax style wrappers."""

from __future__ import annotations

import ctypes
import sys
from typing import Any

from ..native import _decode, _nb, _rgba_to_list


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
    global _zig_set_styled_text_fn
    if _zig_set_styled_text_fn is None:
        try:
            if sys.platform == "win32":
                from ..ffi import _preloaded_lib_path

                if _preloaded_lib_path is None:
                    raise OSError("OpenTUI native library was not preloaded")
                lib = ctypes.CDLL(_preloaded_lib_path)
            else:
                lib = ctypes.CDLL(None)
            fn = lib.textBufferSetStyledText
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

        # Note: Zig's setStyledText copies all text and link data internally
        # (via @memcpy and pool.alloc), so ctypes buffers only need to survive
        # the synchronous call — no pinning required after it returns.
        #
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
        return _decode(result)

    def get_text_range(self, start: int, end: int, max_len: int = 0) -> str:
        if max_len <= 0:
            max_len = self.get_byte_size() + 1
        result = _nb.text_buffer.text_buffer_get_text_range(self._ptr, start, end, max_len)
        return _decode(result)

    def set_default_fg(self, color: Any = None) -> None:
        _nb.text_buffer.text_buffer_set_default_fg(self._ptr, _rgba_to_list(color))

    def set_default_bg(self, color: Any = None) -> None:
        _nb.text_buffer.text_buffer_set_default_bg(self._ptr, _rgba_to_list(color))

    def set_default_attributes(self, attrs: int) -> None:
        _nb.text_buffer.text_buffer_set_default_attributes(self._ptr, attrs)

    def reset_defaults(self) -> None:
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
        return _decode(result)

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
        return _nb.text_buffer.syntax_style_register(self._ptr, name, fg, bg, attributes)

    def resolve_by_name(self, name: str) -> int:
        return _nb.text_buffer.syntax_style_resolve_by_name(self._ptr, name)

    def get_style_count(self) -> int:
        return _nb.text_buffer.syntax_style_get_style_count(self._ptr)

    def destroy(self) -> None:
        if self._ptr:
            _nb.text_buffer.destroy_syntax_style(self._ptr)
            self._ptr = None
