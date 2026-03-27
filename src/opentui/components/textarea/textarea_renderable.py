from collections.abc import Callable
from typing import Any
from typing import NamedTuple as _NamedTuple

from ... import hooks
from ... import structs as s
from ...editor.edit_buffer_native import NativeEditBuffer
from ...editor.editor_view_native import NativeEditorView
from ...enums import RenderStrategy
from ...events import KeyEvent, PasteEvent
from ...input.keymapping import (
    DEFAULT_KEY_ALIASES,
    KeyAliasMap,
    KeyBinding,
    lookup_action_for_event,
)
from ...renderer.buffer import Buffer
from ..base import Renderable, _parse_color_static, _Prop
from ._textarea_init import (
    create_textarea_editor,
    init_textarea_runtime_state,
    wire_textarea_runtime_handlers,
)
from .textarea_keymap import (
    init_textarea_key_bindings,
    resolve_textarea_colors,
    update_textarea_key_aliases,
    update_textarea_key_bindings,
)
from .textarea_text_utils import (
    line_col_to_offset,
    offset_to_line_col,
    str_display_width,
)


class _CursorPos(_NamedTuple):
    row: int
    col: int


from ._textarea_mouse import _MouseMixin
from ._textarea_navigation import _NavigationMixin
from ._textarea_selection import _SelectionMixin


class TextareaRenderable(_SelectionMixin, _NavigationMixin, _MouseMixin, Renderable):
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
        wrap_mode: str = "none",
        scroll_margin: float = 0.2,
        key_bindings: list[KeyBinding] | None = None,
        key_alias_map: KeyAliasMap | None = None,
        on_submit: Callable | None = None,
        on_paste: Callable | None = None,
        on_key_down: Callable | None = None,
        on_content_change: Callable | None = None,
        on_cursor_change: Callable | None = None,
        syntax_style: Any | None = None,
        tab_indicator: str | int | None = None,
        tab_indicator_color: s.RGBA | str | None = None,
        **kwargs,
    ):
        if background_color is not None and "background_color" not in kwargs:
            kwargs["background_color"] = background_color

        super().__init__(**kwargs)

        self._edit_buffer, self._editor_view = create_textarea_editor(
            initial_value=initial_value,
            width=kwargs.get("width"),
            height=kwargs.get("height"),
            wrap_mode=wrap_mode,
            scroll_margin=scroll_margin,
        )
        colors = resolve_textarea_colors(
            self._parse_color,
            placeholder_color=placeholder_color,
            text_color=text_color,
            focused_background_color=focused_background_color,
            focused_text_color=focused_text_color,
            cursor_color=cursor_color,
            selection_background_color=selection_background_color,
            selection_bg=selection_bg,
            selection_fg=selection_fg,
        )
        init_textarea_runtime_state(
            self,
            initial_value=initial_value,
            placeholder=placeholder,
            colors=colors,
            selectable=selectable,
            wrap_mode=wrap_mode,
            scroll_margin=scroll_margin,
            on_submit=on_submit,
            on_paste=on_paste,
            on_key_down=on_key_down,
            on_content_change=on_content_change,
            on_cursor_change=on_cursor_change,
        )

        self._key_bindings, self._key_alias_map, self._key_map = init_textarea_key_bindings(
            key_bindings, key_alias_map
        )

        self._setup_measure_func()

        if syntax_style is not None:
            self.syntax_style = syntax_style

        if tab_indicator is not None:
            self.tab_indicator = tab_indicator
        if tab_indicator_color is not None:
            self.tab_indicator_color = tab_indicator_color

        wire_textarea_runtime_handlers(self)

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
        self._placeholder_str = v
        self.mark_paint_dirty()

    placeholder_color = _Prop("_placeholder_color", _parse_color_static, paint_only=True)
    text_color = _Prop("_text_color", _parse_color_static, paint_only=True)
    background_color = _Prop("_background_color", _parse_color_static, paint_only=True)
    focused_background_color = _Prop("_focused_bg_color", _parse_color_static, paint_only=True)
    focused_text_color = _Prop("_focused_text_color", _parse_color_static, paint_only=True)
    cursor_color = _Prop("_cursor_color", _parse_color_static, paint_only=True)

    @property
    def selectable(self) -> bool:
        return self._selectable

    @selectable.setter
    def selectable(self, value: bool) -> None:
        self._selectable = value

    selection_bg = _Prop("_selection_bg_color", _parse_color_static, paint_only=True)
    selection_fg = _Prop("_selection_fg_color", _parse_color_static, paint_only=True)

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
        self._key_bindings, self._key_map = update_textarea_key_bindings(
            bindings, self._key_alias_map
        )

    @property
    def key_alias_map(self) -> KeyAliasMap:
        return dict(self._key_alias_map)

    @key_alias_map.setter
    def key_alias_map(self, aliases: KeyAliasMap) -> None:
        self._key_alias_map, self._key_map = update_textarea_key_aliases(
            DEFAULT_KEY_ALIASES, aliases, self._key_bindings
        )

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
        from ...native import _nb

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
        from ...native import _nb

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
        from ...native import _nb

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
        from ...native import _nb

        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        return _nb.text_buffer.text_buffer_get_line_highlights(text_buf_ptr, line_idx)

    def remove_highlights_by_ref(self, hl_ref: int) -> None:
        from ...native import _nb

        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        _nb.text_buffer.text_buffer_remove_highlights_by_ref(text_buf_ptr, hl_ref)

    def clear_line_highlights(self, line_idx: int) -> None:
        from ...native import _nb

        text_buf_ptr = self._edit_buffer.get_text_buffer_ptr()
        _nb.text_buffer.text_buffer_clear_line_highlights(text_buf_ptr, line_idx)

    def clear_all_highlights(self) -> None:
        from ...native import _nb

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
        from ..line_number_gutter import LineInfo

        try:
            return LineInfo.from_native_dict(self._editor_view.get_line_info())
        except Exception:
            return None

    @property
    def wrap_mode(self) -> str:
        return self._wrap_mode

    @wrap_mode.setter
    def wrap_mode(self, mode: str) -> None:
        self._wrap_mode = mode
        self._editor_view.set_wrap_mode(mode)
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
        if self._destroyed:
            return
        self._edit_buffer.set_text("")
        self._edit_buffer.set_cursor(0, 0)
        self.clear_selection()
        self._notify_content_changed()
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.mark_dirty()

    def insert_char(self, char: str) -> None:
        if self._destroyed:
            return
        if self.has_selection:
            self._delete_selection()
        self._edit_buffer.insert_text(char)
        self._notify_content_changed()
        self._notify_cursor_changed()
        self.mark_dirty()

    def insert_text(self, text: str) -> None:
        if self._destroyed:
            return
        if self.has_selection:
            self._delete_selection()
        self._edit_buffer.insert_text(text)
        self._notify_content_changed()
        self._notify_cursor_changed()
        self.mark_dirty()

    def submit(self) -> None:
        self.emit("submit", self.plain_text)
        if self._on_submit:
            self._on_submit(self.plain_text)

    def handle_paste(self, event: PasteEvent) -> None:
        if self._destroyed:
            return
        if self._on_paste_handler:
            self._on_paste_handler(event)
        if event.default_prevented:
            return
        text = getattr(event, "text", None)
        if text is None:
            text = str(event)
        if text:
            self.insert_text(text)

    def focus(self) -> None:
        """Focus this textarea and register keyboard + paste handlers."""
        if self._destroyed:
            return
        if self._focused:
            return
        self._focused = True
        hooks.register_keyboard_handler(self._key_handler)
        hooks.register_paste_handler(self.handle_paste)
        self.mark_paint_dirty()

    def blur(self) -> None:
        """Blur this textarea and unregister keyboard + paste handlers."""
        if self._destroyed:
            return
        if not self._focused:
            return
        self._focused = False
        hooks.unregister_keyboard_handler(self._key_handler)
        hooks.unregister_paste_handler(self.handle_paste)
        self.mark_paint_dirty()

    def handle_key(self, event: KeyEvent) -> bool:
        if self._destroyed:
            return False
        if event.default_prevented:
            return False
        if not self._focused:
            return False

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
        return lookup_action_for_event(event, self._key_map, self._key_alias_map)

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

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            text = self.plain_text
            if not text:
                return (1, 1)

            lines = text.split("\n")
            line_count = len(lines)
            max_line_width = max((str_display_width(line) for line in lines), default=1)

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
        s_off = line_col_to_offset(text, start_line, start_col)
        e_off = line_col_to_offset(text, end_line, end_col)
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
        return line_col_to_offset(text, line, col)

    @cursor_offset.setter
    def cursor_offset(self, offset: int) -> None:
        text = self.plain_text
        offset = max(0, min(offset, len(text)))
        pos = offset_to_line_col(text, offset)
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
        if self._destroyed:
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

        # Native drawing can mutate viewport state via internal follow-cursor behavior.
        try:
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
            self._editor_view.set_viewport(
                vp.get("offsetX", 0),
                vp.get("offsetY", 0),
                vp.get("width", w),
                vp.get("height", h),
            )
        except Exception:
            lines = text.split("\n") if text else []
            for i, line in enumerate(lines):
                if i >= h:
                    break
                display = line[:w] if len(line) > w else line
                if display:
                    buffer.draw_text(display, x, y + i, fg, bg)

    def destroy(self) -> None:
        hooks.unregister_keyboard_handler(self._key_handler)
        self._focused = False
        if self._editor_view:
            self._editor_view.destroy()
        if self._edit_buffer:
            self._edit_buffer.destroy()
        super().destroy()


__all__ = ["TextareaRenderable"]
