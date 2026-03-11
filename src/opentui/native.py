"""Native bindings wrapper - uses nanobind C++ extensions when available."""

import ctypes
import importlib.util
import os
import site
import sys
from typing import Any

# Try to load the .so file directly
_nb = None
_NANOBIND_AVAILABLE = False

# Get the directory where this file is located
_current_dir = os.path.dirname(os.path.abspath(__file__))
_package_dir = os.path.dirname(_current_dir)


def _iter_binding_search_dirs() -> list[str]:
    dirs: list[str] = [_current_dir]
    seen = set(dirs)

    for base in site.getsitepackages():
        candidate = os.path.join(base, "opentui")
        if candidate not in seen:
            dirs.append(candidate)
            seen.add(candidate)

    for base in sys.path:
        if not base:
            continue
        candidate = os.path.join(base, "opentui")
        if candidate not in seen:
            dirs.append(candidate)
            seen.add(candidate)

    sibling = os.path.join(_package_dir, "opentui_bindings")
    if sibling not in seen:
        dirs.append(sibling)

    return dirs


def _preload_opentui_library() -> None:
    candidates = [
        os.path.join(_current_dir, "opentui-libs", "libopentui.dylib"),
        os.path.join(_package_dir, "opentui", "opentui-libs", "libopentui.dylib"),
    ]

    for so_dir in _iter_binding_search_dirs():
        candidates.append(os.path.join(so_dir, "opentui-libs", "libopentui.dylib"))

    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        try:
            ctypes.CDLL(candidate, mode=ctypes.RTLD_GLOBAL)
            return
        except OSError:
            continue


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
        self._ptr = ptr  # Can be int or capsule

    @property
    def ptr(self) -> Any:
        return self._ptr

    def clear(self, color: tuple[float, float, float, float] | None = None) -> None:
        # For now, call without color (uses default)
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


class NativeTextBuffer:
    """Wrapper for native text buffer using nanobind bindings."""

    def __init__(self, encoding: int = 0):
        self._ptr = _nb.text_buffer.create_text_buffer(encoding)

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.text_buffer.destroy_text_buffer(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> int:
        return self._ptr

    def append(self, text: str) -> None:
        _nb.text_buffer.text_buffer_append(self._ptr, text)

    def clear(self) -> None:
        _nb.text_buffer.text_buffer_clear(self._ptr)

    def reset(self) -> None:
        _nb.text_buffer.text_buffer_reset(self._ptr)

    def get_length(self) -> int:
        return _nb.text_buffer.text_buffer_get_length(self._ptr)

    def get_line_count(self) -> int:
        return _nb.text_buffer.text_buffer_get_line_count(self._ptr)

    def get_plain_text(self, max_len: int = 4096) -> str:
        result = _nb.text_buffer.text_buffer_get_plain_text(self._ptr, max_len)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return result

    def set_tab_width(self, width: int) -> None:
        _nb.text_buffer.text_buffer_set_tab_width(self._ptr, width)

    def get_tab_width(self) -> int:
        return _nb.text_buffer.text_buffer_get_tab_width(self._ptr)


class NativeTextBufferView:
    """Wrapper for native text buffer view using nanobind bindings."""

    def __init__(self, buffer_ptr: int):
        self._ptr = _nb.text_buffer.create_text_buffer_view(buffer_ptr)

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.text_buffer.destroy_text_buffer_view(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> int:
        return self._ptr

    def set_viewport(self, x: int, y: int, width: int, height: int) -> None:
        _nb.text_buffer.text_buffer_view_set_viewport(self._ptr, x, y, width, height)

    def set_wrap_width(self, width: int) -> None:
        _nb.text_buffer.text_buffer_view_set_wrap_width(self._ptr, width)

    def set_wrap_mode(self, mode: int) -> None:
        _nb.text_buffer.text_buffer_view_set_wrap_mode(self._ptr, mode)

    def set_viewport_size(self, width: int, height: int) -> None:
        _nb.text_buffer.text_buffer_view_set_viewport_size(self._ptr, width, height)

    def get_virtual_line_count(self) -> int:
        return _nb.text_buffer.text_buffer_view_get_virtual_line_count(self._ptr)

    def measure(self, width: int, height: int) -> tuple[int, int]:
        return _nb.text_buffer.text_buffer_view_measure_for_dimensions(self._ptr, width, height)


class NativeEditBuffer:
    """Wrapper for native edit buffer using nanobind bindings."""

    def __init__(self, encoding: int = 0):
        self._ptr = _nb.edit_buffer.create_edit_buffer(encoding)

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.edit_buffer.destroy_edit_buffer(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> int:
        return self._ptr

    def insert_text(self, text: str) -> None:
        _nb.edit_buffer.edit_buffer_insert_text(self._ptr, text)

    def delete_char(self) -> None:
        _nb.edit_buffer.edit_buffer_delete_char(self._ptr)

    def delete_char_backward(self) -> None:
        _nb.edit_buffer.edit_buffer_delete_char_backward(self._ptr)

    def set_text(self, text: str) -> None:
        _nb.edit_buffer.edit_buffer_set_text(self._ptr, text)

    def move_cursor_left(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_left(self._ptr)

    def move_cursor_right(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_right(self._ptr)

    def move_cursor_up(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_up(self._ptr)

    def move_cursor_down(self) -> None:
        _nb.edit_buffer.edit_buffer_move_cursor_down(self._ptr)

    def goto_line(self, line: int) -> None:
        _nb.edit_buffer.edit_buffer_goto_line(self._ptr, line)

    def can_undo(self) -> bool:
        return _nb.edit_buffer.edit_buffer_can_undo(self._ptr)

    def can_redo(self) -> bool:
        return _nb.edit_buffer.edit_buffer_can_redo(self._ptr)

    def undo(self, max_len: int = 4096) -> str:
        result = _nb.edit_buffer.edit_buffer_undo(self._ptr, max_len)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return result

    def redo(self, max_len: int = 4096) -> str:
        result = _nb.edit_buffer.edit_buffer_redo(self._ptr, max_len)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return result


class NativeEditorView:
    """Wrapper for native editor view using nanobind bindings."""

    def __init__(self, buffer_ptr: int, width: int, height: int):
        self._ptr = _nb.editor_view.create_editor_view(buffer_ptr, width, height)

    def __del__(self):
        try:
            if hasattr(self, "_ptr") and self._ptr:
                _nb.editor_view.destroy_editor_view(self._ptr)
                self._ptr = None
        except Exception:
            pass

    @property
    def ptr(self) -> int:
        return self._ptr

    def set_viewport(self, x: int, y: int, width: int, height: int) -> None:
        _nb.editor_view.editor_view_set_viewport(self._ptr, x, y, width, height)

    def set_viewport_size(self, width: int, height: int) -> None:
        _nb.editor_view.editor_view_set_viewport_size(self._ptr, width, height)

    def reset_selection(self) -> None:
        _nb.editor_view.editor_view_reset_selection(self._ptr)


def is_available() -> bool:
    """Check if nanobind bindings are available."""
    return _NANOBIND_AVAILABLE


__all__ = [
    "NativeRenderer",
    "NativeBuffer",
    "NativeTextBuffer",
    "NativeTextBufferView",
    "NativeEditBuffer",
    "NativeEditorView",
    "is_available",
]
