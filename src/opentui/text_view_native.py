"""Native text buffer view wrapper."""

from __future__ import annotations

from typing import Any

from .text_buffer_native import NativeTextBuffer

# Wrap mode constants matching zig enum values
_WRAP_MODE_NONE = 0
_WRAP_MODE_CHAR = 1
_WRAP_MODE_WORD = 2


def _get_nb():
    from .native import _nb

    return _nb


def _rgba_to_list(color: Any) -> list[float] | None:
    from .native import _rgba_to_list as _native_rgba_to_list

    return _native_rgba_to_list(color)


class NativeTextBufferView:
    """Wrapper for native text buffer view using nanobind bindings."""

    # Wrap mode constants
    WRAP_MODE_NONE = 0
    WRAP_MODE_CHAR = 1
    WRAP_MODE_WORD = 2

    def __init__(self, buffer_ptr: Any, text_buffer: NativeTextBuffer | None = None):
        _nb = _get_nb()
        self._ptr: Any = _nb.text_buffer.create_text_buffer_view(buffer_ptr)
        self._text_buffer = text_buffer

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb = _get_nb()
                _nb.text_buffer.destroy_text_buffer_view(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> Any:
        return self._ptr

    def set_viewport(self, x: int, y: int, width: int, height: int) -> None:
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_set_viewport(self._ptr, x, y, width, height)

    def set_wrap_width(self, width: int) -> None:
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_set_wrap_width(self._ptr, width)

    def set_wrap_mode(self, mode: int | str) -> None:
        _nb = _get_nb()
        if isinstance(mode, str):
            mode_map = {"none": 0, "char": 1, "word": 2}
            mode = mode_map.get(mode, 0)
        _nb.text_buffer.text_buffer_view_set_wrap_mode(self._ptr, mode)

    def set_viewport_size(self, width: int, height: int) -> None:
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_set_viewport_size(self._ptr, width, height)

    def get_virtual_line_count(self) -> int:
        _nb = _get_nb()
        return _nb.text_buffer.text_buffer_view_get_virtual_line_count(self._ptr)

    def set_selection(self, start: int, end: int) -> None:
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_set_selection(self._ptr, start, end)

    def reset_selection(self) -> None:
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_reset_selection(self._ptr)

    def get_selection_info(self) -> int:
        _nb = _get_nb()
        return _nb.text_buffer.text_buffer_view_get_selection_info(self._ptr)

    def get_selection(self) -> dict[str, int] | None:
        packed = self.get_selection_info()
        if packed == 0xFFFF_FFFF_FFFF_FFFF:
            return None
        start = (packed >> 32) & 0xFFFF_FFFF
        end = packed & 0xFFFF_FFFF
        return {"start": start, "end": end}

    def has_selection(self) -> bool:
        return self.get_selection() is not None

    def update_selection(self, end: int) -> None:
        _nb = _get_nb()
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
        _nb = _get_nb()
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
        _nb = _get_nb()
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
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_reset_local_selection(self._ptr)

    def get_line_info(self) -> dict:
        _nb = _get_nb()
        return _nb.text_buffer.text_buffer_view_get_line_info(self._ptr)

    def get_logical_line_info(self) -> dict:
        _nb = _get_nb()
        return _nb.text_buffer.text_buffer_view_get_logical_line_info(self._ptr)

    def get_selected_text(self) -> str:
        _nb = _get_nb()
        raw: bytes = _nb.text_buffer.text_buffer_view_get_selected_text(self._ptr)
        return raw.decode("utf-8") if raw else ""

    def set_tab_indicator(self, indicator: int) -> None:
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_set_tab_indicator(self._ptr, indicator)

    def set_tab_indicator_color(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_set_tab_indicator_color(self._ptr, r, g, b, a)

    def set_truncate(self, truncate: bool) -> None:
        _nb = _get_nb()
        _nb.text_buffer.text_buffer_view_set_truncate(self._ptr, truncate)

    def measure(self, width: int, height: int) -> tuple[int, int]:
        _nb = _get_nb()
        return _nb.text_buffer.text_buffer_view_measure_for_dimensions(self._ptr, width, height)

    def measure_for_dimensions(self, width: int, height: int) -> dict[str, int] | None:
        _nb = _get_nb()
        result = _nb.text_buffer.text_buffer_view_measure_for_dimensions(self._ptr, width, height)
        if result is None:
            return None
        line_count, width_cols_max = result
        return {"lineCount": line_count, "widthColsMax": width_cols_max}

    def get_plain_text(self) -> str:
        _nb = _get_nb()
        raw: bytes = _nb.text_buffer.text_buffer_view_get_plain_text(self._ptr)
        if raw:
            return raw.decode("utf-8")
        if self._text_buffer is not None:
            return self._text_buffer.get_plain_text()
        return ""
