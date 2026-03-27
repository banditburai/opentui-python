import logging
from collections.abc import Callable
from typing import Any

from ...editor.edit_buffer_native import NativeEditBuffer

_log = logging.getLogger(__name__)
from ...editor.editor_view_native import NativeEditorView
from .textarea_keymap import TextareaColorConfig


def _viewport_dimension(value: Any, fallback: int) -> int:
    return int(value) if isinstance(value, int | float) else fallback


def create_textarea_editor(
    *,
    initial_value: str,
    width: Any,
    height: Any,
    wrap_mode: str,
    scroll_margin: float,
) -> tuple[NativeEditBuffer, NativeEditorView]:
    edit_buffer = NativeEditBuffer()
    if initial_value:
        edit_buffer.set_text(initial_value)
        edit_buffer.set_cursor(0, 0)

    editor_view = NativeEditorView(
        edit_buffer.ptr,
        _viewport_dimension(width, 80),
        _viewport_dimension(height, 24),
    )
    if wrap_mode != "none":
        editor_view.set_wrap_mode(wrap_mode)
    editor_view.set_scroll_margin(scroll_margin)
    return edit_buffer, editor_view


def init_textarea_runtime_state(
    textarea,
    *,
    initial_value: str,
    placeholder: str | None,
    colors: TextareaColorConfig,
    selectable: bool,
    wrap_mode: str,
    scroll_margin: float,
    on_submit: Callable | None,
    on_paste: Callable | None,
    on_key_down: Callable | None,
    on_content_change: Callable | None,
    on_cursor_change: Callable | None,
) -> None:
    textarea._initial_value = initial_value
    textarea._placeholder_str = placeholder
    textarea._placeholder_color = colors.placeholder_color
    textarea._text_color = colors.text_color
    textarea._focused_bg_color = colors.focused_background_color
    textarea._focused_text_color = colors.focused_text_color
    textarea._cursor_color = colors.cursor_color
    textarea._selection_bg_color = colors.selection_background_color
    textarea._selection_fg_color = colors.selection_foreground_color

    textarea._focusable = True
    textarea._selectable = selectable

    textarea._selection_start = None
    textarea._selection_end = None
    textarea._selecting = False
    textarea._cross_renderable_selection_active = False
    textarea._keyboard_selection_active = False

    textarea._drag_anchor_x = None
    textarea._drag_anchor_y = None
    textarea._drag_focus_x = None
    textarea._drag_focus_y = None
    textarea._is_dragging_selection = False
    textarea._drag_anchor_line = 0
    textarea._drag_anchor_col = 0

    textarea._on_submit = on_submit
    textarea._on_paste_handler = on_paste
    textarea._on_key_down_handler = on_key_down
    textarea._on_content_change = on_content_change
    textarea._on_cursor_change = on_cursor_change

    textarea._wrap_mode = wrap_mode
    textarea._scroll_margin = scroll_margin
    textarea._key_handler = textarea.handle_key
    textarea._syntax_style = None
    textarea._tab_indicator = None
    textarea._tab_indicator_color = None
    textarea._is_scroll_target = True
    textarea._auto_scroll_velocity = 0.0
    textarea._auto_scroll_accumulator = 0.0
    textarea._scroll_speed = 16.0


def wire_textarea_runtime_handlers(textarea) -> None:
    textarea._on_mouse_down = textarea._handle_mouse_down
    textarea._on_mouse_drag = textarea._handle_mouse_drag
    textarea._on_mouse_drag_end = textarea._handle_mouse_drag_end
    textarea._on_mouse_up = textarea._handle_mouse_up
    textarea._on_mouse_scroll = textarea._handle_scroll_event

    previous_on_size_change = textarea._on_size_change

    def _on_textarea_size_change(width: int, height: int) -> None:
        try:
            textarea._editor_view.set_viewport_size(width, height)
            textarea._follow_cursor()
        except Exception:
            _log.debug("textarea size change handler failed", exc_info=True)
        if previous_on_size_change is not None:
            previous_on_size_change(width, height)

    textarea._on_size_change = _on_textarea_size_change
