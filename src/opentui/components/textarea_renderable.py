from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from .. import hooks
from .. import structs as s
from ..enums import RenderStrategy
from ..events import KeyEvent, PasteEvent
from ..keymapping import (
    DEFAULT_KEY_ALIASES,
    KeyAliasMap,
    KeyBinding,
    build_key_bindings_map,
    lookup_action,
    merge_key_aliases,
    merge_key_bindings,
)
from ..native import NativeEditBuffer, NativeEditorView
from .base import Renderable

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..renderer import Buffer


_DEFAULT_TEXTAREA_BINDINGS: list[KeyBinding] = [
    KeyBinding(name="left", action="move-left"),
    KeyBinding(name="right", action="move-right"),
    KeyBinding(name="up", action="move-up"),
    KeyBinding(name="down", action="move-down"),
    KeyBinding(name="b", action="move-left", ctrl=True),
    KeyBinding(name="f", action="move-right", ctrl=True),
    KeyBinding(name="a", action="line-home", ctrl=True),
    KeyBinding(name="e", action="line-end", ctrl=True),
    KeyBinding(name="home", action="line-home"),
    KeyBinding(name="end", action="line-end"),
    KeyBinding(name="home", action="buffer-home", ctrl=True),
    KeyBinding(name="end", action="buffer-end", ctrl=True),
    KeyBinding(name="left", action="select-left", shift=True),
    KeyBinding(name="right", action="select-right", shift=True),
    KeyBinding(name="up", action="select-up", shift=True),
    KeyBinding(name="down", action="select-down", shift=True),
    KeyBinding(name="home", action="select-buffer-home", shift=True),
    KeyBinding(name="end", action="select-buffer-end", shift=True),
    KeyBinding(name="a", action="select-line-home", ctrl=True, shift=True),
    KeyBinding(name="e", action="select-line-end", ctrl=True, shift=True),
    KeyBinding(name="a", action="visual-line-home", meta=True),
    KeyBinding(name="e", action="visual-line-end", meta=True),
    KeyBinding(name="a", action="select-visual-line-home", meta=True, shift=True),
    KeyBinding(name="e", action="select-visual-line-end", meta=True, shift=True),
    KeyBinding(name="f", action="word-forward", meta=True),
    KeyBinding(name="b", action="word-backward", meta=True),
    KeyBinding(name="right", action="word-forward", meta=True),
    KeyBinding(name="left", action="word-backward", meta=True),
    KeyBinding(name="right", action="word-forward", ctrl=True),
    KeyBinding(name="left", action="word-backward", ctrl=True),
    KeyBinding(name="f", action="select-word-forward", meta=True, shift=True),
    KeyBinding(name="b", action="select-word-backward", meta=True, shift=True),
    KeyBinding(name="right", action="select-word-forward", meta=True, shift=True),
    KeyBinding(name="left", action="select-word-backward", meta=True, shift=True),
    KeyBinding(name="backspace", action="backspace"),
    KeyBinding(name="backspace", action="backspace", shift=True),
    KeyBinding(name="delete", action="delete"),
    KeyBinding(name="delete", action="delete", shift=True),
    KeyBinding(name="d", action="delete", ctrl=True),
    KeyBinding(name="w", action="delete-word-backward", ctrl=True),
    KeyBinding(name="backspace", action="delete-word-backward", meta=True),
    KeyBinding(name="d", action="delete-word-forward", meta=True),
    KeyBinding(name="delete", action="delete-word-forward", meta=True),
    KeyBinding(name="delete", action="delete-word-forward", ctrl=True),
    KeyBinding(name="backspace", action="delete-word-backward", ctrl=True),
    KeyBinding(name="k", action="delete-to-line-end", ctrl=True),
    KeyBinding(name="u", action="delete-to-line-start", ctrl=True),
    KeyBinding(name="d", action="delete-line", ctrl=True, shift=True),
    KeyBinding(name="return", action="newline"),
    KeyBinding(name="linefeed", action="newline"),
    KeyBinding(name="a", action="select-all", super_key=True),
    KeyBinding(name="z", action="undo", ctrl=True),
    KeyBinding(name="-", action="undo", ctrl=True),
    KeyBinding(name=".", action="redo", ctrl=True, shift=True),
    KeyBinding(name="z", action="undo", meta=True),
    KeyBinding(name="z", action="redo", meta=True, shift=True),
    KeyBinding(name="return", action="submit", meta=True),
]


from typing import NamedTuple as _NamedTuple


class _CursorPos(_NamedTuple):
    row: int
    col: int


class TextareaRenderable(Renderable):
    """Multi-line text editor renderable backed by native EditBuffer.

    Usage:
        ta = TextareaRenderable(initial_value="Hello\\nWorld")
        ta.focus()
        ta.handle_key(KeyEvent(key="a"))
        assert "a" in ta.plain_text
    """

    __slots__ = (
        "_edit_buffer",
        "_editor_view",
        "_initial_value",
        "_placeholder_str",
        "_placeholder_color",
        "_text_color",
        "_focused_bg_color",
        "_focused_text_color",
        "_cursor_color",
        "_selection_bg_color",
        "_selection_fg_color",
        "_key_bindings",
        "_key_alias_map",
        "_key_map",
        "_selection_start",
        "_selection_end",
        "_selecting",
        "_drag_anchor_x",
        "_drag_anchor_y",
        "_drag_focus_x",
        "_drag_focus_y",
        "_is_dragging_selection",
        "_on_submit",
        "_on_paste_handler",
        "_on_key_down_handler",
        "_on_content_change",
        "_on_cursor_change",
        "_is_destroyed",
        "_selectable",
        "_is_scroll_target",
        "_wrap_mode",
        "_scroll_margin",
        "_key_handler",
        "_syntax_style",
        "_tab_indicator",
        "_tab_indicator_color",
        "_auto_scroll_velocity",
        "_auto_scroll_accumulator",
        "_scroll_speed",
        "_drag_anchor_line",
        "_drag_anchor_col",
        "_cross_renderable_selection_active",
        "_keyboard_selection_active",
    )

    def get_render_strategy(self) -> RenderStrategy:
        return RenderStrategy.HEAVY_WIDGET

    def __init__(
        self,
        *,
        initial_value: str = "",
        placeholder: str | None = "",
        # Colors
        background_color: s.RGBA | str | None = None,
        text_color: s.RGBA | str | None = None,
        focused_background_color: s.RGBA | str | None = None,
        focused_text_color: s.RGBA | str | None = None,
        placeholder_color: s.RGBA | str | None = None,
        cursor_color: s.RGBA | str | None = None,
        selection_background_color: s.RGBA | str | None = None,
        selection_bg: s.RGBA | str | None = None,
        selection_fg: s.RGBA | str | None = None,
        selectable: bool = True,
        # Wrapping and scrolling
        wrap_mode: str = "none",
        scroll_margin: float = 0.2,
        # Key bindings
        key_bindings: list[KeyBinding] | None = None,
        key_alias_map: KeyAliasMap | None = None,
        # Events
        on_submit: Callable | None = None,
        on_paste: Callable | None = None,
        on_key_down: Callable | None = None,
        on_content_change: Callable | None = None,
        on_cursor_change: Callable | None = None,
        # Syntax highlighting
        syntax_style: Any | None = None,
        # Tab indicator
        tab_indicator: str | int | None = None,
        tab_indicator_color: s.RGBA | str | None = None,
        **kwargs,
    ):
        if background_color is not None and "background_color" not in kwargs:
            kwargs["background_color"] = background_color

        super().__init__(**kwargs)

        self._edit_buffer = NativeEditBuffer()

        self._initial_value = initial_value
        if initial_value:
            self._edit_buffer.set_text(initial_value)
            self._edit_buffer.set_cursor(0, 0)

        # Default viewport size; updated via _on_size_change callback
        init_w = (
            int(kwargs.get("width", 80)) if isinstance(kwargs.get("width"), int | float) else 80
        )
        init_h = (
            int(kwargs.get("height", 24)) if isinstance(kwargs.get("height"), int | float) else 24
        )
        self._editor_view = NativeEditorView(self._edit_buffer.ptr, init_w, init_h)
        self._wrap_mode = wrap_mode
        self._scroll_margin = scroll_margin
        if wrap_mode != "none":
            self._editor_view.set_wrap_mode(wrap_mode)
        self._editor_view.set_scroll_margin(scroll_margin)

        self._placeholder_str = placeholder
        self._placeholder_color = (
            self._parse_color(placeholder_color)
            if placeholder_color
            else s.RGBA(0.5, 0.5, 0.5, 1.0)
        )

        self._text_color = self._parse_color(text_color)
        self._focused_bg_color = self._parse_color(focused_background_color)
        self._focused_text_color = self._parse_color(focused_text_color)
        self._cursor_color = self._parse_color(cursor_color)
        self._selection_bg_color = self._parse_color(selection_background_color or selection_bg)
        self._selection_fg_color = self._parse_color(selection_fg)

        self._focusable = True
        self._selectable = selectable

        # Selection state (offsets into plain text)
        self._selection_start: int | None = None
        self._selection_end: int | None = None
        self._selecting = False
        self._cross_renderable_selection_active = False
        self._keyboard_selection_active = False

        self._drag_anchor_x: int | None = None
        self._drag_anchor_y: int | None = None
        self._drag_focus_x: int | None = None
        self._drag_focus_y: int | None = None
        self._is_dragging_selection = False
        # Buffer-space anchor (absolute line, col - fixed at mouse-down time)
        self._drag_anchor_line: int = 0
        self._drag_anchor_col: int = 0

        self._on_submit = on_submit
        self._on_paste_handler = on_paste
        self._on_key_down_handler = on_key_down
        self._on_content_change = on_content_change
        self._on_cursor_change = on_cursor_change

        self._key_bindings = list(_DEFAULT_TEXTAREA_BINDINGS)
        self._key_alias_map = dict(DEFAULT_KEY_ALIASES)
        if key_bindings:
            self._key_bindings = merge_key_bindings(self._key_bindings, key_bindings)
        if key_alias_map:
            self._key_alias_map = merge_key_aliases(self._key_alias_map, key_alias_map)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

        self._is_destroyed = False

        # Expose a key handler for the renderer's event forwarding system
        self._key_handler = self.handle_key

        self._setup_measure_func()

        self._syntax_style = None
        if syntax_style is not None:
            self.syntax_style = syntax_style

        self._tab_indicator: str | int | None = None
        self._tab_indicator_color: s.RGBA | None = None
        if tab_indicator is not None:
            self.tab_indicator = tab_indicator
        if tab_indicator_color is not None:
            self.tab_indicator_color = tab_indicator_color

        # Mark as scroll target for renderer scroll event routing
        self._is_scroll_target = True

        # Auto-scroll state
        self._auto_scroll_velocity: float = 0.0
        self._auto_scroll_accumulator: float = 0.0
        self._scroll_speed: float = 16.0  # lines per second

        # Register mouse event handlers for selection and scrolling
        self._on_mouse_down = self._handle_mouse_down
        self._on_mouse_drag = self._handle_mouse_drag
        self._on_mouse_drag_end = self._handle_mouse_drag_end
        self._on_mouse_up = self._handle_mouse_up
        self._on_mouse_scroll = self._handle_scroll_event

        # Chain _on_size_change: sync EditorView viewport when dimensions change.
        # Preserve any user-provided on_size_change callback from kwargs.
        _prev_on_size_change = self._on_size_change

        def _on_textarea_size_change(w, h):
            try:
                self._editor_view.set_viewport_size(w, h)
                self._follow_cursor()
            except Exception:
                pass
            if _prev_on_size_change is not None:
                _prev_on_size_change(w, h)

        self._on_size_change = _on_textarea_size_change

    @property
    def plain_text(self) -> str:
        return self._edit_buffer.get_text()

    @property
    def initial_value(self) -> str:
        return self._initial_value

    @property
    def cursor_position(self) -> tuple[int, int]:
        return self._edit_buffer.get_cursor_position()

    @property
    def line_count(self) -> int:
        text = self.plain_text
        if not text:
            return 1
        return text.count("\n") + 1

    @property
    def placeholder(self) -> str | None:
        return self._placeholder_str

    @placeholder.setter
    def placeholder(self, v: str | None) -> None:
        # undefined/None both clear the placeholder
        self._placeholder_str = v
        self.mark_paint_dirty()

    @property
    def placeholder_color(self) -> s.RGBA | None:
        return self._placeholder_color

    @placeholder_color.setter
    def placeholder_color(self, v: s.RGBA | str | None) -> None:
        self._placeholder_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def text_color(self) -> s.RGBA | None:
        return self._text_color

    @text_color.setter
    def text_color(self, v: s.RGBA | str | None) -> None:
        self._text_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def background_color(self) -> s.RGBA | None:
        return self._background_color

    @background_color.setter
    def background_color(self, v: s.RGBA | str | None) -> None:
        self._background_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def focused_background_color(self) -> s.RGBA | None:
        return self._focused_bg_color

    @focused_background_color.setter
    def focused_background_color(self, v: s.RGBA | str | None) -> None:
        self._focused_bg_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def focused_text_color(self) -> s.RGBA | None:
        return self._focused_text_color

    @focused_text_color.setter
    def focused_text_color(self, v: s.RGBA | str | None) -> None:
        self._focused_text_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def cursor_color(self) -> s.RGBA | None:
        return self._cursor_color

    @cursor_color.setter
    def cursor_color(self, v: s.RGBA | str | None) -> None:
        self._cursor_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def selectable(self) -> bool:
        return self._selectable

    @selectable.setter
    def selectable(self, value: bool) -> None:
        self._selectable = value

    @property
    def selection_bg(self) -> s.RGBA | None:
        return self._selection_bg_color

    @selection_bg.setter
    def selection_bg(self, value: s.RGBA | str | None) -> None:
        self._selection_bg_color = self._parse_color(value)
        self.mark_paint_dirty()

    @property
    def selection_fg(self) -> s.RGBA | None:
        return self._selection_fg_color

    @selection_fg.setter
    def selection_fg(self, value: s.RGBA | str | None) -> None:
        self._selection_fg_color = self._parse_color(value)
        self.mark_paint_dirty()

    def should_start_selection(self, x: int, y: int) -> bool:
        if not self._selectable:
            return False
        local_x = x - self._x
        local_y = y - self._y
        w = self._layout_width or 0
        h = self._layout_height or 0
        return 0 <= local_x < w and 0 <= local_y < h

    @property
    def key_bindings(self) -> list[KeyBinding]:
        return list(self._key_bindings)

    @key_bindings.setter
    def key_bindings(self, bindings: list[KeyBinding]) -> None:
        self._key_bindings = merge_key_bindings(_DEFAULT_TEXTAREA_BINDINGS, bindings)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

    @property
    def key_alias_map(self) -> KeyAliasMap:
        return dict(self._key_alias_map)

    @key_alias_map.setter
    def key_alias_map(self, aliases: KeyAliasMap) -> None:
        self._key_alias_map = merge_key_aliases(DEFAULT_KEY_ALIASES, aliases)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

    @property
    def on_submit(self) -> Callable | None:
        return self._on_submit

    @on_submit.setter
    def on_submit(self, handler: Callable | None) -> None:
        self._on_submit = handler

    @property
    def on_content_change(self) -> Callable | None:
        return self._on_content_change

    @on_content_change.setter
    def on_content_change(self, handler: Callable | None) -> None:
        self._on_content_change = handler

    @property
    def on_cursor_change(self) -> Callable | None:
        return self._on_cursor_change

    @on_cursor_change.setter
    def on_cursor_change(self, handler: Callable | None) -> None:
        self._on_cursor_change = handler

    @property
    def edit_buffer(self) -> NativeEditBuffer:
        return self._edit_buffer

    @property
    def editor_view(self) -> NativeEditorView:
        return self._editor_view

    # -- Syntax highlighting API --

    @property
    def syntax_style(self):
        return self._syntax_style

    @syntax_style.setter
    def syntax_style(self, style) -> None:
        from ..native import _nb

        self._syntax_style = style
        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        if style is not None:
            _nb.text_buffer.text_buffer_set_syntax_style(text_buf_ptr, style._native.ptr)
        else:
            _nb.text_buffer.text_buffer_clear_syntax_style(text_buf_ptr)

    def add_highlight(self, line_idx: int, spec: dict) -> None:
        """Add a highlight to a specific line.

        Args:
            line_idx: Zero-based line index.
            spec: Dict with keys: start, end, styleId, priority, hlRef (optional).
        """
        from ..native import _nb

        start = spec.get("start", spec.get("startCol", 0))
        end = spec.get("end", spec.get("endCol", 0))
        style_id = spec.get("styleId", spec.get("style_id", 0))
        priority = spec.get("priority", 0)
        hl_ref = spec.get("hlRef", spec.get("hl_ref", 0))
        if start == end:
            return
        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        _nb.text_buffer.text_buffer_add_highlight(
            text_buf_ptr, line_idx, start, end, style_id, priority, hl_ref
        )

    def add_highlight_by_char_range(self, spec: dict) -> None:
        """Add a highlight by character range spanning multiple lines.

        Args:
            spec: Dict with keys: start, end, styleId, priority, hlRef (optional).
        """
        from ..native import _nb

        start = spec.get("start", 0)
        end = spec.get("end", 0)
        style_id = spec.get("styleId", spec.get("style_id", 0))
        priority = spec.get("priority", 0)
        hl_ref = spec.get("hlRef", spec.get("hl_ref", 0))
        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        _nb.text_buffer.text_buffer_add_highlight_by_char_range(
            text_buf_ptr, start, end, style_id, priority, hl_ref
        )

    def get_line_highlights(self, line_idx: int) -> list[dict]:
        """Get highlights for a specific line.

        Returns:
            List of dicts with keys: start, end, styleId, priority, hlRef.
        """
        from ..native import _nb

        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        return _nb.text_buffer.text_buffer_get_line_highlights(text_buf_ptr, line_idx)

    def remove_highlights_by_ref(self, hl_ref: int) -> None:
        """Remove all highlights with the given reference ID."""
        from ..native import _nb

        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        _nb.text_buffer.text_buffer_remove_highlights_by_ref(text_buf_ptr, hl_ref)

    def clear_line_highlights(self, line_idx: int) -> None:
        """Clear all highlights for a specific line."""
        from ..native import _nb

        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        _nb.text_buffer.text_buffer_clear_line_highlights(text_buf_ptr, line_idx)

    def clear_all_highlights(self) -> None:
        """Clear all highlights across all lines."""
        from ..native import _nb

        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        _nb.text_buffer.text_buffer_clear_all_highlights(text_buf_ptr)

    @property
    def virtual_line_count(self) -> int:
        """Get the number of virtual (wrapped) lines.

        Used by LineNumberRenderable to size the gutter.
        """
        try:
            return self._editor_view.get_total_virtual_line_count()
        except Exception:
            return self.line_count

    @property
    def scroll_y(self) -> int:
        """Get the current vertical scroll offset.

        Used by LineNumberRenderable to determine which lines are visible.
        """
        try:
            viewport = self._editor_view.get_viewport()
            return viewport.get("offsetY", 0)
        except Exception:
            return 0

    @property
    def line_info(self):
        """Get line layout info from the native editor view.

        Returns a LineInfo-like object with line_sources, line_start_cols, etc.
        Used by LineNumberRenderable to map visual lines to logical lines.
        """
        from .line_number_renderable import LineInfo

        try:
            info = self._editor_view.get_line_info()
            return LineInfo(
                line_start_cols=info.get("start_cols", info.get("lineStartCols", [])),
                line_width_cols=info.get("width_cols", info.get("lineWidthCols", [])),
                line_width_cols_max=info.get("width_cols_max", info.get("lineWidthColsMax", 0)),
                line_sources=info.get("sources", info.get("lineSources", [])),
                line_wraps=info.get("wraps", info.get("lineWraps", [])),
            )
        except Exception:
            return None

    @property
    def wrap_mode(self) -> str:
        return self._wrap_mode

    @wrap_mode.setter
    def wrap_mode(self, mode: str) -> None:
        self._wrap_mode = mode
        self._editor_view.set_wrap_mode(mode)
        # Mark yoga dirty so measure function re-runs
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.mark_dirty()

    @property
    def scroll_margin(self) -> float:
        return self._scroll_margin

    @scroll_margin.setter
    def scroll_margin(self, margin: float) -> None:
        self._scroll_margin = margin
        self._editor_view.set_scroll_margin(margin)

    @property
    def tab_indicator(self) -> str | int | None:
        return self._tab_indicator

    @tab_indicator.setter
    def tab_indicator(self, value: str | int | None) -> None:
        """Set the tab indicator character.

        Accepts a string (first codepoint is used) or an integer codepoint.
        """
        if self._tab_indicator != value:
            self._tab_indicator = value
            if value is not None:
                codepoint = ord(value[0]) if isinstance(value, str) else value
                self._editor_view.set_tab_indicator(codepoint)
            self.mark_paint_dirty()

    @property
    def tab_indicator_color(self) -> s.RGBA | None:
        return self._tab_indicator_color

    @tab_indicator_color.setter
    def tab_indicator_color(self, value: s.RGBA | str | None) -> None:
        new_color = self._parse_color(value)
        if self._tab_indicator_color != new_color:
            self._tab_indicator_color = new_color
            if new_color is not None:
                self._editor_view.set_tab_indicator_color(
                    new_color.r, new_color.g, new_color.b, new_color.a
                )
            self.mark_paint_dirty()

    @property
    def logical_cursor(self) -> Any:
        line, col = self._edit_buffer.get_cursor_position()
        return _CursorPos(line, col)

    def clear(self) -> None:
        if self._is_destroyed:
            return
        self._edit_buffer.set_text("")
        self._edit_buffer.set_cursor(0, 0)
        self.clear_selection()
        self._notify_content_changed()
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.mark_dirty()

    @property
    def has_selection(self) -> bool:
        # Check native editor view when cross-renderable selection is active
        if getattr(self, "_cross_renderable_selection_active", False):
            try:
                if self._editor_view.has_selection():
                    return True
            except Exception:
                pass
        return (
            self._selection_start is not None
            and self._selection_end is not None
            and self._selection_start != self._selection_end
        )

    @property
    def selection(self) -> tuple[int, int] | None:
        # Check native editor view when cross-renderable selection is active
        if getattr(self, "_cross_renderable_selection_active", False):
            try:
                native_sel = self._editor_view.get_selection()
                if native_sel is not None:
                    return (native_sel["start"], native_sel["end"])
            except Exception:
                pass
        if self._selection_start is None or self._selection_end is None:
            return None
        s_start = min(self._selection_start, self._selection_end)
        s_end = max(self._selection_start, self._selection_end)
        if s_start == s_end:
            return None
        return (s_start, s_end)

    def set_selection(self, start: int, end: int) -> None:
        text = self.plain_text
        text_len = len(text)
        self._selection_start = max(0, min(start, text_len))
        self._selection_end = max(0, min(end, text_len))
        self.mark_paint_dirty()

    def clear_selection(self) -> None:
        self._selection_start = None
        self._selection_end = None
        if self._cross_renderable_selection_active:
            self._cross_renderable_selection_active = False
            with contextlib.suppress(Exception):
                self._editor_view.reset_local_selection()
        self.mark_paint_dirty()

    def get_selected_text(self) -> str:
        # Check native editor view when cross-renderable selection is active
        if getattr(self, "_cross_renderable_selection_active", False):
            try:
                native_text = self._editor_view.get_selected_text()
                if native_text:
                    return native_text
            except Exception:
                pass
        sel = self.selection
        if sel is None:
            return ""
        text = self.plain_text
        return text[sel[0] : sel[1]]

    def on_selection_changed(self, selection) -> bool:
        """Converts global selection coordinates to local and applies via the
        native editor view's local selection API.  Returns True if this
        renderable has a selection after the change.

        When the textarea is managing its own drag selection internally
        (e.g., single-renderable mouse drag within the textarea), defer
        to the internal path rather than applying cross-renderable
        selection on top.
        """
        # If the textarea is currently managing its own drag selection,
        # let the internal path handle it to avoid double-selection.
        if self._is_dragging_selection:
            return self.has_selection

        from ..selection import convert_global_to_local_selection

        local_sel = convert_global_to_local_selection(selection, self._x, self._y)

        update_cursor = True
        follow_cursor = self._keyboard_selection_active

        if local_sel is None or not local_sel.is_active:
            self._keyboard_selection_active = False
            self._cross_renderable_selection_active = False
            self._editor_view.reset_local_selection()
            self._selection_start = None
            self._selection_end = None
            self.mark_paint_dirty()
            return False

        self._cross_renderable_selection_active = True

        changed: bool
        if selection is not None and selection.is_start:
            changed = self._editor_view.set_local_selection(
                local_sel.anchor_x,
                local_sel.anchor_y,
                local_sel.focus_x,
                local_sel.focus_y,
                update_cursor=update_cursor,
                follow_cursor=follow_cursor,
                bg_color=self._selection_bg_color,
                fg_color=self._selection_fg_color,
            )
        else:
            changed = self._editor_view.update_local_selection(
                local_sel.anchor_x,
                local_sel.anchor_y,
                local_sel.focus_x,
                local_sel.focus_y,
                update_cursor=update_cursor,
                follow_cursor=follow_cursor,
                bg_color=self._selection_bg_color,
                fg_color=self._selection_fg_color,
            )

        if changed:
            self.mark_paint_dirty()

        return self.has_selection

    def select_all(self) -> None:
        text = self.plain_text
        self._selection_start = 0
        self._selection_end = len(text)
        lines = text.split("\n")
        last_line = len(lines) - 1
        last_col = len(lines[-1]) if lines else 0
        self._edit_buffer.set_cursor(last_line, last_col)
        self.mark_paint_dirty()

    def _delete_selection(self) -> bool:
        sel = self.selection
        if sel is None:
            return False
        text = self.plain_text
        start_pos = self._offset_to_line_col(text, sel[0])
        end_pos = self._offset_to_line_col(text, sel[1])
        self._edit_buffer.delete_range(start_pos[0], start_pos[1], end_pos[0], end_pos[1])
        self._edit_buffer.set_cursor(start_pos[0], start_pos[1])
        self.clear_selection()
        self._notify_content_changed()
        return True

    def insert_char(self, char: str) -> None:
        if self._is_destroyed:
            return
        if self.has_selection:
            self._delete_selection()
        self._edit_buffer.insert_text(char)
        self._notify_content_changed()
        self._notify_cursor_changed()
        self.mark_dirty()

    def insert_text(self, text: str) -> None:
        if self._is_destroyed:
            return
        if self.has_selection:
            self._delete_selection()
        self._edit_buffer.insert_text(text)
        self._notify_content_changed()
        self._notify_cursor_changed()
        self.mark_dirty()

    def delete_char(self) -> None:
        if self.has_selection:
            self._delete_selection()
            return
        self._edit_buffer.delete_char()
        self._notify_content_changed()
        self.mark_dirty()

    def delete_char_backward(self) -> None:
        if self.has_selection:
            self._delete_selection()
            return
        self._edit_buffer.delete_char_backward()
        self._notify_content_changed()
        self._notify_cursor_changed()
        self.mark_dirty()

    def newline(self) -> None:
        if self.has_selection:
            self._delete_selection()
        self._edit_buffer.newline()
        self._notify_content_changed()
        self._notify_cursor_changed()
        self.mark_dirty()

    def delete_line(self) -> None:
        line, col = self.cursor_position
        text = self.plain_text
        lines = text.split("\n")
        if line >= len(lines):
            return
        line_start = sum(len(lines[i]) + 1 for i in range(line))
        line_end = line_start + len(lines[line])
        if line < len(lines) - 1:
            line_end += 1  # include \n
        elif line > 0:
            line_start -= 1
        start_pos = self._offset_to_line_col(text, line_start)
        end_pos = self._offset_to_line_col(text, line_end)
        self._edit_buffer.delete_range(start_pos[0], start_pos[1], end_pos[0], end_pos[1])
        new_text = self._edit_buffer.get_text()
        new_lines = new_text.split("\n")
        new_line = min(line, len(new_lines) - 1)
        new_col = min(col, len(new_lines[new_line]) if new_lines else 0)
        self._edit_buffer.set_cursor(new_line, new_col)
        self._notify_content_changed()
        self.mark_dirty()

    def delete_to_line_end(self) -> None:
        line, col = self.cursor_position
        text = self.plain_text
        lines = text.split("\n")
        if line >= len(lines):
            return
        line_display_width = self._str_display_width(lines[line])
        if col >= line_display_width:
            return
        self._edit_buffer.delete_range(line, col, line, line_display_width)
        self._notify_content_changed()
        self.mark_dirty()

    def delete_to_line_start(self) -> None:
        line, col = self.cursor_position
        if col <= 0:
            return
        self._edit_buffer.delete_range(line, 0, line, col)
        self._edit_buffer.set_cursor(line, 0)
        self._notify_content_changed()
        self.mark_dirty()

    def move_word_forward(self, select: bool = False) -> None:
        text = self.plain_text
        offset = self._line_col_to_offset(text, *self.cursor_position)
        new_offset = self._next_word_boundary(text, offset)
        if select:
            self._extend_selection(offset, new_offset)
        else:
            self.clear_selection()
        new_pos = self._offset_to_line_col(text, new_offset)
        self._edit_buffer.set_cursor(new_pos[0], new_pos[1])
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def move_word_backward(self, select: bool = False) -> None:
        text = self.plain_text
        offset = self._line_col_to_offset(text, *self.cursor_position)
        new_offset = self._prev_word_boundary(text, offset)
        if select:
            self._extend_selection(offset, new_offset)
        else:
            self.clear_selection()
        new_pos = self._offset_to_line_col(text, new_offset)
        self._edit_buffer.set_cursor(new_pos[0], new_pos[1])
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def delete_word_forward(self) -> None:
        text = self.plain_text
        offset = self._line_col_to_offset(text, *self.cursor_position)
        end_offset = self._next_word_boundary(text, offset)
        if end_offset == offset:
            return
        end_pos = self._offset_to_line_col(text, end_offset)
        line, col = self.cursor_position
        self._edit_buffer.delete_range(line, col, end_pos[0], end_pos[1])
        self._notify_content_changed()
        self.mark_dirty()

    def delete_word_backward(self) -> None:
        text = self.plain_text
        offset = self._line_col_to_offset(text, *self.cursor_position)
        start_offset = self._prev_word_boundary(text, offset)
        if start_offset == offset:
            return
        start_pos = self._offset_to_line_col(text, start_offset)
        line, col = self.cursor_position
        self._edit_buffer.delete_range(start_pos[0], start_pos[1], line, col)
        self._edit_buffer.set_cursor(start_pos[0], start_pos[1])
        self._notify_content_changed()
        self.mark_dirty()

    def move_cursor_left(self, select: bool = False) -> None:
        if select:
            text = self.plain_text
            offset = self._line_col_to_offset(text, *self.cursor_position)
            new_offset = max(0, offset - 1)
            self._extend_selection(offset, new_offset)
        else:
            self.clear_selection()
        self._edit_buffer.move_cursor_left()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def move_cursor_right(self, select: bool = False) -> None:
        if select:
            text = self.plain_text
            offset = self._line_col_to_offset(text, *self.cursor_position)
            new_offset = min(len(text), offset + 1)
            self._extend_selection(offset, new_offset)
        else:
            self.clear_selection()
        self._edit_buffer.move_cursor_right()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def move_cursor_up(self, select: bool = False) -> None:
        if select:
            text = self.plain_text
            old_offset = self._line_col_to_offset(text, *self.cursor_position)
            if self._wrap_mode != "none":
                self._editor_view.move_up_visual()
            else:
                self._edit_buffer.move_cursor_up()
            new_offset = self._line_col_to_offset(text, *self.cursor_position)
            self._extend_selection(old_offset, new_offset)
        else:
            self.clear_selection()
            if self._wrap_mode != "none":
                self._editor_view.move_up_visual()
            else:
                self._edit_buffer.move_cursor_up()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def move_cursor_down(self, select: bool = False) -> None:
        if select:
            text = self.plain_text
            old_offset = self._line_col_to_offset(text, *self.cursor_position)
            if self._wrap_mode != "none":
                self._editor_view.move_down_visual()
            else:
                self._edit_buffer.move_cursor_down()
            new_offset = self._line_col_to_offset(text, *self.cursor_position)
            self._extend_selection(old_offset, new_offset)
        else:
            self.clear_selection()
            if self._wrap_mode != "none":
                self._editor_view.move_down_visual()
            else:
                self._edit_buffer.move_cursor_down()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_line_home(self, select: bool = False) -> None:
        """Move cursor to start of current line.

        If already at col 0 and not on the first line, wraps to the end of the
        previous line.
        """
        line, col = self.cursor_position
        text = self.plain_text
        lines = text.split("\n")

        if col == 0 and line > 0:
            # Wrap to end of previous line
            target_line = line - 1
            target_col = self._str_display_width(lines[target_line])
            if select:
                old_offset = self._line_col_to_offset(text, line, col)
                new_offset = self._line_col_to_offset(text, target_line, target_col)
                self._extend_selection(old_offset, new_offset)
            else:
                self.clear_selection()
            self._edit_buffer.set_cursor(target_line, target_col)
        else:
            if select:
                old_offset = self._line_col_to_offset(text, line, col)
                new_offset = self._line_col_to_offset(text, line, 0)
                self._extend_selection(old_offset, new_offset)
            else:
                self.clear_selection()
            self._edit_buffer.set_cursor(line, 0)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_line_end(self, select: bool = False) -> None:
        """Move cursor to end of current line.

        If already at end of line and not on the last line, wraps to the start
        of the next line.
        """
        line, col = self.cursor_position
        text = self.plain_text
        lines = text.split("\n")
        if line >= len(lines):
            return
        line_display_width = self._str_display_width(lines[line])

        if col >= line_display_width and line < len(lines) - 1:
            # Wrap to start of next line
            target_line = line + 1
            target_col = 0
            if select:
                old_offset = self._line_col_to_offset(text, line, col)
                new_offset = self._line_col_to_offset(text, target_line, target_col)
                self._extend_selection(old_offset, new_offset)
            else:
                self.clear_selection()
            self._edit_buffer.set_cursor(target_line, target_col)
        else:
            if select:
                old_offset = self._line_col_to_offset(text, line, col)
                new_offset = self._line_col_to_offset(text, line, line_display_width)
                self._extend_selection(old_offset, new_offset)
            else:
                self.clear_selection()
            self._edit_buffer.set_cursor(line, line_display_width)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_visual_line_home(self, select: bool = False) -> None:
        """Move cursor to start of the current visual line.

        When wrapping is enabled, this goes to the start of the visual (wrapped)
        line, not the logical line. Without wrapping, behaves same as line-home
        (without wrap-around behavior).
        """
        text = self.plain_text
        old_offset = self._line_col_to_offset(text, *self.cursor_position)

        # Use EditorView's getVisualSOL to find visual line start
        sol = self._editor_view.get_visual_sol()
        target_line = sol.logical_row
        target_col = sol.logical_col

        if select:
            new_offset = self._line_col_to_offset(text, target_line, target_col)
            self._extend_selection(old_offset, new_offset)
        else:
            self.clear_selection()

        self._edit_buffer.set_cursor(target_line, target_col)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_visual_line_end(self, select: bool = False) -> None:
        """Move cursor to end of the current visual line.

        When wrapping is enabled, this goes to the end of the visual (wrapped)
        line, not the logical line. Without wrapping, behaves same as line-end
        (without wrap-around behavior).
        """
        text = self.plain_text
        old_offset = self._line_col_to_offset(text, *self.cursor_position)

        # Use EditorView's getVisualEOL to find visual line end
        eol = self._editor_view.get_visual_eol()
        target_line = eol.logical_row
        target_col = eol.logical_col

        if select:
            new_offset = self._line_col_to_offset(text, target_line, target_col)
            self._extend_selection(old_offset, new_offset)
        else:
            self.clear_selection()

        self._edit_buffer.set_cursor(target_line, target_col)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_buffer_home(self, select: bool = False) -> None:
        if select:
            text = self.plain_text
            old_offset = self._line_col_to_offset(text, *self.cursor_position)
            self._extend_selection(old_offset, 0)
        else:
            self.clear_selection()
        self._edit_buffer.set_cursor(0, 0)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_buffer_end(self, select: bool = False) -> None:
        text = self.plain_text
        lines = text.split("\n")
        last_line = max(0, len(lines) - 1)
        last_col = self._str_display_width(lines[last_line]) if lines else 0
        if select:
            old_offset = self._line_col_to_offset(text, *self.cursor_position)
            self._extend_selection(old_offset, len(text))
        else:
            self.clear_selection()
        self._edit_buffer.set_cursor(last_line, last_col)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def goto_line(self, line_num: int) -> None:
        """Go to a specific line number (0-based).

        Uses the native gotoLine which moves to the END of the target line.
        """
        self._edit_buffer.goto_line(line_num)
        self._follow_cursor()
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def undo(self) -> bool:
        self.clear_selection()
        result = self._edit_buffer.undo()
        if result:
            self._notify_content_changed()
            self._notify_cursor_changed()
            self.mark_dirty()
        return bool(result)

    def redo(self) -> bool:
        self.clear_selection()
        result = self._edit_buffer.redo()
        if result:
            self._notify_content_changed()
            self._notify_cursor_changed()
            self.mark_dirty()
        return bool(result)

    def submit(self) -> None:
        self.emit("submit", self.plain_text)
        if self._on_submit:
            self._on_submit(self.plain_text)

    def handle_paste(self, event: PasteEvent) -> None:
        if self._is_destroyed:
            return
        if self._on_paste_handler:
            self._on_paste_handler(event)
        if event.default_prevented:
            return
        text = event.text if hasattr(event, "text") else str(event)
        if text:
            self.insert_text(text)

    def focus(self) -> None:
        """Focus this textarea and register keyboard + paste handlers."""
        if self._is_destroyed:
            return
        if self._focused:
            return
        self._focused = True
        # Register handle_key so MockInput (and any global dispatch) reaches us
        hooks.register_keyboard_handler(self._key_handler)
        hooks.register_paste_handler(self.handle_paste)
        self.mark_paint_dirty()

    def blur(self) -> None:
        """Blur this textarea and unregister keyboard + paste handlers."""
        if self._is_destroyed:
            return
        if not self._focused:
            return
        self._focused = False
        hooks.unregister_keyboard_handler(self._key_handler)
        hooks.unregister_paste_handler(self.handle_paste)
        self.mark_paint_dirty()

    def handle_key(self, event: KeyEvent) -> bool:
        if self._is_destroyed:
            return False
        if event.default_prevented:
            return False
        if not self._focused:
            return False

        # Call onKeyDown handler first (can preventDefault)
        if self._on_key_down_handler:
            self._on_key_down_handler(event)
            if event.default_prevented:
                return False

        action = self._lookup_action(event)
        if action:
            return self._dispatch_action(action)

        char = event.sequence or event.key
        if (
            len(char) == 1
            and char.isprintable()
            and not event.ctrl
            and not event.alt
            and not event.meta
            and not event.hyper
        ):
            if self.has_selection:
                self._delete_selection()
            self.insert_char(char)
            return True

        return False

    def _lookup_action(self, event: KeyEvent) -> str | None:
        return lookup_action(
            event.key,
            event.ctrl,
            event.shift,
            event.alt,
            event.meta,
            self._key_map,
            self._key_alias_map,
        )

    def _dispatch_action(self, action: str) -> bool:
        handler = self._ACTION_TABLE.get(action)
        if handler is not None:
            handler(self)
            return True
        return False

    _ACTION_TABLE: dict[str, Any] = {
        "move-left": lambda self: self.move_cursor_left(),
        "move-right": lambda self: self.move_cursor_right(),
        "move-up": lambda self: self.move_cursor_up(),
        "move-down": lambda self: self.move_cursor_down(),
        "select-left": lambda self: self.move_cursor_left(select=True),
        "select-right": lambda self: self.move_cursor_right(select=True),
        "select-up": lambda self: self.move_cursor_up(select=True),
        "select-down": lambda self: self.move_cursor_down(select=True),
        "line-home": lambda self: self.goto_line_home(),
        "line-end": lambda self: self.goto_line_end(),
        "select-line-home": lambda self: self.goto_line_home(select=True),
        "select-line-end": lambda self: self.goto_line_end(select=True),
        "visual-line-home": lambda self: self.goto_visual_line_home(),
        "visual-line-end": lambda self: self.goto_visual_line_end(),
        "select-visual-line-home": lambda self: self.goto_visual_line_home(select=True),
        "select-visual-line-end": lambda self: self.goto_visual_line_end(select=True),
        "buffer-home": lambda self: self.goto_buffer_home(),
        "buffer-end": lambda self: self.goto_buffer_end(),
        "select-buffer-home": lambda self: self.goto_buffer_home(select=True),
        "select-buffer-end": lambda self: self.goto_buffer_end(select=True),
        "word-forward": lambda self: self.move_word_forward(),
        "word-backward": lambda self: self.move_word_backward(),
        "select-word-forward": lambda self: self.move_word_forward(select=True),
        "select-word-backward": lambda self: self.move_word_backward(select=True),
        "backspace": lambda self: self.delete_char_backward(),
        "delete": lambda self: self.delete_char(),
        "delete-word-forward": lambda self: self.delete_word_forward(),
        "delete-word-backward": lambda self: self.delete_word_backward(),
        "delete-line": lambda self: self.delete_line(),
        "delete-to-line-end": lambda self: self.delete_to_line_end(),
        "delete-to-line-start": lambda self: self.delete_to_line_start(),
        "newline": lambda self: self.newline(),
        "select-all": lambda self: self.select_all(),
        "undo": lambda self: self.undo(),
        "redo": lambda self: self.redo(),
        "submit": lambda self: self.submit(),
    }

    def _screen_to_buffer_pos(self, screen_x: int, screen_y: int) -> tuple[int, int]:
        local_x = screen_x - self._x
        local_y = screen_y - self._y

        viewport = self._editor_view.get_viewport()
        offset_x = viewport.get("offsetX", 0)
        offset_y = viewport.get("offsetY", 0)

        buf_line = local_y + offset_y
        buf_col = local_x + offset_x

        text = self.plain_text
        lines = text.split("\n")
        max_line = max(0, len(lines) - 1)
        buf_line = max(0, min(buf_line, max_line))

        if buf_line < len(lines):
            line_width = self._str_display_width(lines[buf_line])
            buf_col = max(0, min(buf_col, line_width))
        else:
            buf_col = 0

        return (buf_line, buf_col)

    def _handle_mouse_down(self, event: Any) -> None:
        if self._is_destroyed:
            return
        if not self._selectable:
            return

        line, col = self._screen_to_buffer_pos(event.x, event.y)
        self._edit_buffer.set_cursor(line, col)
        self._notify_cursor_changed()

        self.clear_selection()

        self._drag_anchor_x = event.x - self._x
        self._drag_anchor_y = event.y - self._y
        self._drag_focus_x = self._drag_anchor_x
        self._drag_focus_y = self._drag_anchor_y
        self._is_dragging_selection = False
        self._drag_anchor_line = line
        self._drag_anchor_col = col

        self.mark_paint_dirty()

    def _handle_mouse_drag(self, event: Any) -> None:
        if self._is_destroyed:
            return
        if not self._selectable:
            return
        if self._drag_anchor_x is None:
            return

        self._is_dragging_selection = True

        viewport = self._editor_view.get_viewport()
        offset_x = viewport.get("offsetX", 0)
        offset_y = viewport.get("offsetY", 0)
        vp_height = viewport.get("height", self._layout_height or 1)

        local_x = event.x - self._x
        local_y = event.y - self._y
        self._drag_focus_x = local_x
        self._drag_focus_y = local_y

        text = self.plain_text
        lines = text.split("\n")
        max_line = max(0, len(lines) - 1)

        focus_line = local_y + offset_y
        focus_col = local_x + offset_x

        focus_line = max(0, min(focus_line, max_line))
        if focus_line < len(lines):
            line_width = self._str_display_width(lines[focus_line])
            focus_col = max(0, min(focus_col, line_width))
        else:
            focus_col = 0

        anchor_line = self._drag_anchor_line
        anchor_col = self._drag_anchor_col
        anchor_line = max(0, min(anchor_line, max_line))
        if anchor_line < len(lines):
            anchor_col = max(0, min(anchor_col, self._str_display_width(lines[anchor_line])))
        else:
            anchor_col = 0

        if self._drag_anchor_x is None or self._drag_anchor_y is None:
            return
        try:
            self._editor_view.set_local_selection(
                self._drag_anchor_x,
                self._drag_anchor_y,
                local_x,
                local_y,
                update_cursor=True,
                follow_cursor=False,
                bg_color=self._selection_bg_color,
                fg_color=self._selection_fg_color,
            )
            ev_sel = self._editor_view.get_selection()
            if ev_sel is not None:
                self._selection_start = ev_sel.get("start", 0)
                self._selection_end = ev_sel.get("end", 0)
            else:
                self._selection_start = None
                self._selection_end = None
        except Exception:
            anchor_offset = self._line_col_to_offset(text, anchor_line, anchor_col)
            focus_offset = self._line_col_to_offset(text, focus_line, focus_col)
            self._selection_start = min(anchor_offset, focus_offset)
            self._selection_end = max(anchor_offset, focus_offset)

        self._edit_buffer.set_cursor(focus_line, focus_col)

        scroll_margin = max(1, int(vp_height * self._scroll_margin))
        if local_y < scroll_margin:
            self._auto_scroll_velocity = -self._scroll_speed
        elif local_y >= vp_height - scroll_margin:
            self._auto_scroll_velocity = self._scroll_speed
        else:
            self._auto_scroll_velocity = 0

        self.mark_paint_dirty()

    def _handle_mouse_drag_end(self, event: Any) -> None:
        if self._is_destroyed:
            return
        self._is_dragging_selection = False
        self._auto_scroll_velocity = 0.0
        self._auto_scroll_accumulator = 0.0

    def _handle_mouse_up(self, event: Any) -> None:
        if self._is_destroyed:
            return
        self._is_dragging_selection = False
        self._auto_scroll_velocity = 0.0
        self._auto_scroll_accumulator = 0.0
        self._drag_anchor_x = None
        self._drag_anchor_y = None

    def _handle_scroll_event(self, event: Any) -> None:
        # Don't call _notify_cursor_changed — it triggers _follow_cursor
        # which would reset the viewport back to the cursor position.
        if self._is_destroyed:
            return

        direction = getattr(event, "scroll_direction", None)
        if direction is None:
            delta = getattr(event, "scroll_delta", 0)
            direction = "down" if delta > 0 else "up"

        viewport = self._editor_view.get_viewport()
        offset_x = viewport.get("offsetX", 0)
        offset_y = viewport.get("offsetY", 0)
        vp_width = viewport.get("width", self._layout_width or 80)
        vp_height = viewport.get("height", self._layout_height or 24)

        if direction in ("up", "down"):
            scroll_delta = 1 if direction == "down" else -1
            total_virtual = len(self.plain_text.split("\n"))
            with contextlib.suppress(Exception):
                total_virtual = self._editor_view.get_total_virtual_line_count()
            max_offset_y = max(0, total_virtual - vp_height)
            new_offset_y = max(0, min(offset_y + scroll_delta, max_offset_y))

            if new_offset_y != offset_y:
                # Move cursor into viewport if needed (silently, no follow-cursor).
                # set_cursor must happen BEFORE set_viewport because set_cursor
                # triggers native follow-cursor which would reset the viewport.
                cursor_line, cursor_col = self.cursor_position
                if cursor_line < new_offset_y:
                    self._edit_buffer.set_cursor(new_offset_y, cursor_col)
                elif cursor_line >= new_offset_y + vp_height:
                    self._edit_buffer.set_cursor(new_offset_y + vp_height - 1, cursor_col)

                # Set viewport AFTER cursor move so it isn't overridden by
                # the native follow-cursor that set_cursor triggers.
                self._editor_view.set_viewport(offset_x, new_offset_y, vp_width, vp_height)
                self.mark_paint_dirty()

        elif direction in ("left", "right"):
            # Horizontal scroll (only when wrapping is disabled)
            if self._wrap_mode != "none":
                return

            scroll_delta = 1 if direction == "right" else -1
            new_offset_x = max(0, offset_x + scroll_delta)

            if new_offset_x != offset_x:
                self._editor_view.set_viewport(new_offset_x, offset_y, vp_width, vp_height)
                self.mark_paint_dirty()

    def handle_scroll_event(self, event: Any) -> None:
        self._handle_scroll_event(event)

    def _tick_auto_scroll(self, delta_time: float) -> None:
        """Advance auto-scroll accumulator and scroll the viewport.

        Advances auto-scroll during drag selection.
        ``delta_time`` is in seconds (render frames pass 1/60 by default).
        Our ``_scroll_speed``
        is already in lines-per-second so we work in seconds here.
        """
        if self._auto_scroll_velocity == 0.0:
            return
        if not self.has_selection:
            return

        self._auto_scroll_accumulator += self._auto_scroll_velocity * delta_time

        lines_to_scroll = int(abs(self._auto_scroll_accumulator))
        if lines_to_scroll > 0:
            direction = 1 if self._auto_scroll_velocity > 0 else -1
            viewport = self._editor_view.get_viewport()
            offset_x = viewport.get("offsetX", 0)
            offset_y = viewport.get("offsetY", 0)
            vp_width = viewport.get("width", self._layout_width or 80)
            vp_height = viewport.get("height", self._layout_height or 24)

            total_virtual = self._editor_view.get_total_virtual_line_count()
            max_offset_y = max(0, total_virtual - vp_height)
            new_offset_y = max(0, min(offset_y + direction * lines_to_scroll, max_offset_y))

            if new_offset_y != offset_y:
                self._editor_view.set_viewport(offset_x, new_offset_y, vp_width, vp_height)

                if self._is_dragging_selection and self._drag_focus_y is not None:
                    self._update_drag_selection_after_scroll()

            self._auto_scroll_accumulator -= direction * lines_to_scroll

    def _update_drag_selection_after_scroll(self) -> None:
        """Re-apply drag selection after auto-scroll moved the viewport.

        When the viewport scrolls during a drag, the selection needs to
        extend to cover the newly visible content, even though the mouse
        hasn't moved.  The anchor is fixed in buffer-space (set at mouse-down
        time), while the focus is recomputed from the last local mouse
        position + the new viewport offset.
        """
        if self._drag_anchor_x is None or self._drag_focus_y is None:
            return

        viewport = self._editor_view.get_viewport()
        offset_x = viewport.get("offsetX", 0)
        offset_y = viewport.get("offsetY", 0)

        text = self.plain_text
        lines = text.split("\n")
        max_line = max(0, len(lines) - 1)

        focus_line = self._drag_focus_y + offset_y
        focus_col = (self._drag_focus_x or 0) + offset_x

        focus_line = max(0, min(focus_line, max_line))
        if focus_line < len(lines):
            line_width = self._str_display_width(lines[focus_line])
            focus_col = max(0, min(focus_col, line_width))
        else:
            focus_col = 0

        anchor_line = self._drag_anchor_line
        anchor_col = self._drag_anchor_col

        anchor_offset = self._line_col_to_offset(text, anchor_line, anchor_col)
        focus_offset = self._line_col_to_offset(text, focus_line, focus_col)
        self._selection_start = min(anchor_offset, focus_offset)
        self._selection_end = max(anchor_offset, focus_offset)

        self._edit_buffer.set_cursor(focus_line, focus_col)
        self.mark_paint_dirty()

    def get_selection_dict(self) -> dict[str, int] | None:
        sel = self.selection
        if sel is None:
            return None
        return {"start": sel[0], "end": sel[1]}

    def _extend_selection(self, old_offset: int, new_offset: int) -> None:
        if self._selection_start is None:
            # Start new selection from old position
            self._selection_start = old_offset
        self._selection_end = new_offset

    @staticmethod
    def _str_display_width(s: str) -> int:
        return sum(TextareaRenderable._char_display_width(ch) for ch in s)

    @staticmethod
    def _char_display_width(ch: str) -> int:
        cp = ord(ch)
        # CJK Unified Ideographs
        if 0x4E00 <= cp <= 0x9FFF:
            return 2
        # CJK Extension A
        if 0x3400 <= cp <= 0x4DBF:
            return 2
        # CJK Extension B-I (supplementary)
        if 0x20000 <= cp <= 0x3134F:
            return 2
        # CJK Compatibility Ideographs
        if 0xF900 <= cp <= 0xFAFF:
            return 2
        # Hangul Syllables
        if 0xAC00 <= cp <= 0xD7AF:
            return 2
        # CJK Punctuation (Ideographic full stop, etc.)
        if 0x3000 <= cp <= 0x303F:
            return 2
        # Fullwidth forms
        if 0xFF01 <= cp <= 0xFF60:
            return 2
        if 0xFFE0 <= cp <= 0xFFE6:
            return 2
        # Hiragana
        if 0x3040 <= cp <= 0x309F:
            return 2
        # Katakana
        if 0x30A0 <= cp <= 0x30FF:
            return 2
        return 1

    @staticmethod
    def _offset_to_line_col(text: str, offset: int) -> tuple[int, int]:
        """Convert a character offset to (line, display_col).

        Returns display-width columns (CJK chars count as 2).
        """
        offset = max(0, min(offset, len(text)))
        line = 0
        col = 0
        for i in range(offset):
            if text[i] == "\n":
                line += 1
                col = 0
            else:
                col += TextareaRenderable._char_display_width(text[i])
        return (line, col)

    @staticmethod
    def _line_col_to_offset(text: str, line: int, col: int) -> int:
        """Convert (line, display_col) to a character offset.

        Accepts display-width columns (CJK chars count as 2).
        """
        offset = 0
        current_line = 0
        for ch in text:
            if current_line == line:
                break
            if ch == "\n":
                current_line += 1
            offset += 1
        # Now offset is at the start of the target line.
        # Walk display columns to find the character offset.
        display_col = 0
        while offset < len(text) and text[offset] != "\n" and display_col < col:
            display_col += TextareaRenderable._char_display_width(text[offset])
            offset += 1
        return offset

    @staticmethod
    def _char_class(ch: str) -> int:
        """Classify a character for word boundary detection.

        Returns 0 for whitespace, 1 for CJK/ideograph, 2 for other (ASCII, etc).
        """
        if ch in (" ", "\n", "\t"):
            return 0
        cp = ord(ch)
        # CJK Unified Ideographs
        if 0x4E00 <= cp <= 0x9FFF:
            return 1
        # CJK Extension A
        if 0x3400 <= cp <= 0x4DBF:
            return 1
        # CJK Extension B-I (supplementary)
        if 0x20000 <= cp <= 0x3134F:
            return 1
        # CJK Compatibility Ideographs
        if 0xF900 <= cp <= 0xFAFF:
            return 1
        # Hangul Syllables
        if 0xAC00 <= cp <= 0xD7AF:
            return 1
        # CJK Punctuation (Ideographic full stop, etc.)
        if 0x3000 <= cp <= 0x303F:
            return 1
        # Fullwidth forms
        if 0xFF00 <= cp <= 0xFFEF:
            return 1
        # Hiragana
        if 0x3040 <= cp <= 0x309F:
            return 1
        # Katakana
        if 0x30A0 <= cp <= 0x30FF:
            return 1
        return 2

    @staticmethod
    def _next_word_boundary(text: str, offset: int) -> int:
        length = len(text)
        if offset >= length:
            return length
        pos = offset
        cls = TextareaRenderable._char_class
        start_class = cls(text[pos])
        if start_class == 0:
            # In whitespace: skip whitespace, then the following word group,
            # then trailing whitespace
            while pos < length and cls(text[pos]) == 0:
                pos += 1
            if pos < length:
                word_class = cls(text[pos])
                while pos < length and cls(text[pos]) == word_class:
                    pos += 1
                while pos < length and cls(text[pos]) == 0:
                    pos += 1
            return pos
        else:
            # Skip same-class chars (CJK group or ASCII group)
            while pos < length and cls(text[pos]) == start_class:
                pos += 1
            # Skip trailing whitespace
            while pos < length and cls(text[pos]) == 0:
                pos += 1
            return pos

    @staticmethod
    def _prev_word_boundary(text: str, offset: int) -> int:
        if offset <= 0:
            return 0
        pos = offset
        cls = TextareaRenderable._char_class
        # Skip whitespace
        while pos > 0 and cls(text[pos - 1]) == 0:
            pos -= 1
        if pos <= 0:
            return 0
        prev_class = cls(text[pos - 1])
        # Skip same-class chars (CJK group or ASCII group)
        while pos > 0 and cls(text[pos - 1]) == prev_class:
            pos -= 1
        return pos

    def _notify_content_changed(self) -> None:
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self._follow_cursor()
        self.emit("contentChanged", self.plain_text)
        if self._on_content_change:
            self._on_content_change(self.plain_text)

    def _notify_cursor_changed(self) -> None:
        self._follow_cursor()
        pos = self.cursor_position
        self.emit("cursorChanged", pos)
        if self._on_cursor_change:
            self._on_cursor_change(pos)

    def _follow_cursor(self) -> None:
        with contextlib.suppress(Exception):
            self._editor_view.get_visual_cursor()

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            text = self.plain_text
            if not text:
                return (max(1, 1), 1)

            lines = text.split("\n")
            line_count = len(lines)
            max_line_width = max((self._str_display_width(line) for line in lines), default=1)

            if self._wrap_mode == "none":
                measured_w = max(1, max_line_width)
                measured_h = max(1, line_count)

                if width_mode == yoga.MeasureMode.AtMost:
                    measured_w = min(int(width), measured_w)

                return (measured_w, measured_h)

            avail_w = (
                int(width)
                if width_mode in (yoga.MeasureMode.AtMost, yoga.MeasureMode.Exactly)
                else max_line_width
            )

            if avail_w <= 0:
                avail_w = max_line_width

            try:
                self._editor_view.set_viewport_size(avail_w, 9999)
                vline_count = self._editor_view.get_total_virtual_line_count()
                measured_h = max(1, vline_count)
            except Exception:
                measured_h = max(1, line_count)

            measured_w = avail_w

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(int(width), measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def get_text_range(self, start_offset: int, end_offset: int) -> str:
        """Get a substring of the text by character offsets.

        Returns "" if start >= end or range is completely out of bounds.
        Clamps to valid bounds otherwise.
        """
        text = self.plain_text
        text_len = len(text)
        start = max(0, min(start_offset, text_len))
        end = max(0, min(end_offset, text_len))
        if start >= end:
            return ""
        return text[start:end]

    def get_text_range_by_coords(
        self,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
    ) -> str:
        text = self.plain_text
        s_off = self._line_col_to_offset(text, start_line, start_col)
        e_off = self._line_col_to_offset(text, end_line, end_col)
        text_len = len(text)
        s_off = max(0, min(s_off, text_len))
        e_off = max(0, min(e_off, text_len))
        if s_off >= e_off:
            return ""
        return text[s_off:e_off]

    @property
    def cursor_offset(self) -> int:
        text = self.plain_text
        line, col = self.cursor_position
        return self._line_col_to_offset(text, line, col)

    @cursor_offset.setter
    def cursor_offset(self, offset: int) -> None:
        text = self.plain_text
        offset = max(0, min(offset, len(text)))
        pos = self._offset_to_line_col(text, offset)
        self._edit_buffer.set_cursor(pos[0], pos[1])
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def delete_range(
        self,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
    ) -> None:
        self._edit_buffer.delete_range(start_line, start_col, end_line, end_col)
        self._notify_content_changed()
        self.mark_dirty()

    def delete_selected_text(self) -> bool:
        return self._delete_selection()

    def set_text(self, text: str) -> None:
        if self._is_destroyed:
            return
        self._edit_buffer.set_text(text)
        self._edit_buffer.set_cursor(0, 0)
        self.clear_selection()
        self._notify_content_changed()
        self.mark_dirty()

    def set_cursor(self, line: int, col: int) -> None:
        self._edit_buffer.set_cursor(line, col)
        self._notify_cursor_changed()
        self.mark_paint_dirty()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        self._tick_auto_scroll(delta_time)

        x = self._x
        y = self._y
        w = self._layout_width or 0
        h = self._layout_height or 1

        if w <= 0:
            return

        bg = self._background_color
        fg = self._fg or self._text_color
        if self._focused:
            if self._focused_bg_color:
                bg = self._focused_bg_color
            if self._focused_text_color:
                fg = self._focused_text_color

        if bg:
            buffer.fill_rect(x, y, w, h, bg)

        text = self.plain_text
        if not text and self._placeholder_str:
            placeholder = self._placeholder_str[:w]
            buffer.draw_text(placeholder, x, y, self._placeholder_color, bg)
            return

        # Use native EditorView rendering for correct wrapping/scrolling.
        # Save and restore viewport state because draw_editor_view may
        # trigger internal follow-cursor logic that adjusts the viewport.
        try:
            # Sync selection state + colors to the native EditorView before drawing
            sel = self.selection
            if sel is not None:
                self._editor_view.set_selection(
                    sel[0],
                    sel[1],
                    bg_color=self._selection_bg_color,
                    fg_color=self._selection_fg_color,
                )
            else:
                self._editor_view.reset_selection()

            vp = self._editor_view.get_viewport()
            if vp.get("width", 0) != w or vp.get("height", 0) != h:
                self._editor_view.set_viewport(vp.get("offsetX", 0), vp.get("offsetY", 0), w, h)
                vp = self._editor_view.get_viewport()
            buffer.draw_editor_view(self._editor_view, x, y)
            # Restore viewport in case native rendering modified it
            self._editor_view.set_viewport(
                vp.get("offsetX", 0),
                vp.get("offsetY", 0),
                vp.get("width", w),
                vp.get("height", h),
            )
        except Exception:
            # Fallback: simple line-by-line rendering without wrapping
            lines = text.split("\n") if text else []
            for i, line in enumerate(lines):
                if i >= h:
                    break
                display = line[:w] if len(line) > w else line
                if display:
                    buffer.draw_text(display, x, y + i, fg, bg)

    def destroy(self) -> None:
        self._is_destroyed = True
        hooks.unregister_keyboard_handler(self._key_handler)
        self._focused = False
        if self._editor_view:
            self._editor_view.destroy()
        if self._edit_buffer:
            self._edit_buffer.destroy()
        super().destroy()


__all__ = ["TextareaRenderable"]
