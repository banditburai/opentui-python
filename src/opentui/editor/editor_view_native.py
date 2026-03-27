"""Native editor view wrapper."""

import ctypes
from typing import Any

from ..native import _decode, _nb, _rgba_to_list
from .text_view_native import _WRAP_MODE_CHAR, _WRAP_MODE_NONE, _WRAP_MODE_WORD

_WRAP_MODE_MAP: dict[str, int] = {
    "none": _WRAP_MODE_NONE,
    "char": _WRAP_MODE_CHAR,
    "word": _WRAP_MODE_WORD,
}


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


def _tuple_to_visual_cursor(t: tuple) -> VisualCursor:
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
        if self._destroyed:
            raise RuntimeError("EditorView is destroyed")

    @property
    def ptr(self) -> Any:
        self._guard()
        return self._ptr

    def destroy(self) -> None:
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
        return _decode(result)

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
        self._guard()
        _nb.editor_view.editor_view_clear_viewport(self._ptr)

    def get_line_info(self) -> dict:
        self._guard()
        return _nb.editor_view.editor_view_get_line_info(self._ptr)

    def get_logical_line_info(self) -> dict:
        self._guard()
        return _nb.editor_view.editor_view_get_logical_line_info(self._ptr)

    def get_text_buffer_view_ptr(self) -> Any:
        self._guard()
        return _nb.editor_view.editor_view_get_text_buffer_view(self._ptr)

    def set_tab_indicator(self, indicator: int) -> None:
        self._guard()
        _nb.editor_view.editor_view_set_tab_indicator(self._ptr, indicator)

    def set_tab_indicator_color(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        self._guard()
        _nb.editor_view.editor_view_set_tab_indicator_color(self._ptr, r, g, b, a)

    def get_text(self, max_len: int = 65536) -> str:
        self._guard()
        result = _nb.editor_view.editor_view_get_text(self._ptr, max_len)
        return _decode(result)

    def get_cursor(self) -> tuple[int, int]:
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
