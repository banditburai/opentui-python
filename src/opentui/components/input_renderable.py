from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..events import KeyEvent
from ..keymapping import (
    DEFAULT_KEY_ALIASES,
    KeyAliasMap,
    KeyBinding,
    build_key_bindings_map,
    lookup_action,
    merge_key_aliases,
    merge_key_bindings,
)
from .base import Renderable

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..renderer import Buffer

# Defaults match TextareaRenderable but override Enter → submit.
_DEFAULT_INPUT_BINDINGS: list[KeyBinding] = [
    KeyBinding(name="return", action="submit"),
    KeyBinding(name="linefeed", action="submit"),
    KeyBinding(name="backspace", action="delete-backward"),
    KeyBinding(name="delete", action="delete"),
    KeyBinding(name="w", action="delete-word-backward", ctrl=True),
    KeyBinding(name="backspace", action="delete-word-backward", meta=True),
    KeyBinding(name="d", action="delete-word-forward", meta=True),
    KeyBinding(name="u", action="delete-to-line-start", ctrl=True),
    KeyBinding(name="k", action="delete-to-line-end", ctrl=True),
    KeyBinding(name="d", action="delete-line", ctrl=True, shift=True),
    KeyBinding(name="left", action="move-left"),
    KeyBinding(name="right", action="move-right"),
    KeyBinding(name="b", action="move-left", ctrl=True),
    KeyBinding(name="f", action="move-right", ctrl=True),
    KeyBinding(name="a", action="line-home", ctrl=True),
    KeyBinding(name="e", action="line-end", ctrl=True),
    KeyBinding(name="home", action="buffer-home"),
    KeyBinding(name="end", action="buffer-end"),
    KeyBinding(name="b", action="move-word-backward", meta=True),
    KeyBinding(name="f", action="move-word-forward", meta=True),
    KeyBinding(name="left", action="move-word-backward", meta=True),
    KeyBinding(name="right", action="move-word-forward", meta=True),
    KeyBinding(name="d", action="delete", ctrl=True),
    KeyBinding(name="z", action="undo", ctrl=True),
    KeyBinding(name=".", action="redo", ctrl=True, shift=True),
]


class InputRenderable(Renderable):
    """Single-line text input renderable.

    Uses Python-level text storage with keybinding dispatch.

    Usage:
        inp = InputRenderable(value="Hello", placeholder="Type here...")
        inp.focus()
        inp.handle_key(KeyEvent(key="a"))
        assert inp.value == "Helloa"
    """

    __slots__ = (
        "_value",
        "_cursor_position",
        "_max_length",
        "_placeholder_str",
        "_text_color",
        "_placeholder_color",
        "_focused_bg_color",
        "_focused_text_color",
        "_cursor_color",
        "_last_committed_value",
        "_key_bindings",
        "_key_alias_map",
        "_key_map",
        "_on_key_down",
        "_on_paste_handler",
        "_undo_stack",
        "_redo_stack",
        "_is_destroyed",
    )

    def __init__(
        self,
        *,
        value: str = "",
        max_length: int = 1000,
        placeholder: str = "",
        # Colors
        background_color: s.RGBA | str | None = None,
        text_color: s.RGBA | str | None = None,
        focused_background_color: s.RGBA | str | None = None,
        focused_text_color: s.RGBA | str | None = None,
        placeholder_color: s.RGBA | str | None = None,
        cursor_color: s.RGBA | str | None = None,
        # Key bindings
        key_bindings: list[KeyBinding] | None = None,
        key_alias_map: KeyAliasMap | None = None,
        # Events
        on_paste: Callable | None = None,
        on_key_down: Callable | None = None,
        **kwargs,
    ):
        if background_color is not None and "background_color" not in kwargs:
            kwargs["background_color"] = background_color

        super().__init__(**kwargs)

        clean_value = value.replace("\n", "").replace("\r", "")[:max_length]

        self._value = clean_value
        self._cursor_position = len(clean_value)
        self._max_length = max_length
        self._placeholder_str = placeholder

        self._set_or_bind("_text_color", text_color, transform=self._parse_color)
        self._set_or_bind(
            "_placeholder_color",
            placeholder_color if placeholder_color is not None else s.RGBA(0.5, 0.5, 0.5, 1.0),
            transform=self._parse_color,
        )
        self._set_or_bind(
            "_focused_bg_color", focused_background_color, transform=self._parse_color
        )
        self._set_or_bind("_focused_text_color", focused_text_color, transform=self._parse_color)
        self._set_or_bind("_cursor_color", cursor_color, transform=self._parse_color)

        self._focusable = True
        self._last_committed_value = clean_value

        self._on_key_down = on_key_down
        self._on_paste_handler = on_paste

        self._undo_stack: deque[tuple[str, int]] = deque(maxlen=self._MAX_UNDO_HISTORY)
        self._redo_stack: deque[tuple[str, int]] = deque(maxlen=self._MAX_UNDO_HISTORY)

        self._key_bindings = list(_DEFAULT_INPUT_BINDINGS)
        self._key_alias_map = dict(DEFAULT_KEY_ALIASES)
        if key_bindings:
            self._key_bindings = merge_key_bindings(self._key_bindings, key_bindings)
        if key_alias_map:
            self._key_alias_map = merge_key_aliases(self._key_alias_map, key_alias_map)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

        self._is_destroyed = False

        self._setup_measure_func()

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str) -> None:
        v = v.replace("\n", "").replace("\r", "")[: self._max_length]
        self._save_undo_state()
        self._value = v
        self._cursor_position = len(v)
        self.emit("input", v)
        self.mark_dirty()

    @property
    def plain_text(self) -> str:
        return self._value

    @property
    def cursor_offset(self) -> int:
        return self._cursor_position

    @cursor_offset.setter
    def cursor_offset(self, v: int) -> None:
        new_pos = max(0, min(v, len(self._value)))
        if new_pos != self._cursor_position:
            self._cursor_position = new_pos
            self.mark_paint_dirty()

    @property
    def max_length(self) -> int:
        return self._max_length

    @max_length.setter
    def max_length(self, v: int) -> None:
        self._max_length = v
        if len(self._value) > v:
            self._value = self._value[:v]
            self._cursor_position = min(self._cursor_position, v)
            self.mark_dirty()

    @property
    def placeholder(self) -> str:
        return self._placeholder_str

    @placeholder.setter
    def placeholder(self, v: str) -> None:
        self._placeholder_str = v
        if not self._value:
            # Placeholder affects measure function when value is empty
            self.mark_dirty()
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()
        else:
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
    def placeholder_color(self) -> s.RGBA | None:
        return self._placeholder_color

    @placeholder_color.setter
    def placeholder_color(self, v: s.RGBA | str | None) -> None:
        self._placeholder_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def cursor_color(self) -> s.RGBA | None:
        return self._cursor_color

    @cursor_color.setter
    def cursor_color(self, v: s.RGBA | str | None) -> None:
        self._cursor_color = self._parse_color(v)
        self.mark_paint_dirty()

    @property
    def key_bindings(self) -> list[KeyBinding]:
        return list(self._key_bindings)

    @key_bindings.setter
    def key_bindings(self, bindings: list[KeyBinding]) -> None:
        self._key_bindings = merge_key_bindings(_DEFAULT_INPUT_BINDINGS, bindings)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

    @property
    def key_alias_map(self) -> KeyAliasMap:
        return dict(self._key_alias_map)

    @key_alias_map.setter
    def key_alias_map(self, aliases: KeyAliasMap) -> None:
        self._key_alias_map = merge_key_aliases(DEFAULT_KEY_ALIASES, aliases)
        self._key_map = build_key_bindings_map(self._key_bindings, self._key_alias_map)

    @property
    def on_key_down(self) -> Callable | None:
        return self._on_key_down

    @on_key_down.setter
    def on_key_down(self, handler: Callable | None) -> None:
        self._on_key_down = handler

    def focus(self) -> None:
        """Focus this input, storing current value for change detection."""
        if self._focused:
            return
        self._focused = True
        self._last_committed_value = self._value
        self.mark_paint_dirty()

    def blur(self) -> None:
        """Blur this input, emitting CHANGE if value changed since focus."""
        if self._is_destroyed:
            return
        if not self._focused:
            return
        self._focused = False
        self.mark_paint_dirty()
        if self._value != self._last_committed_value:
            self.emit("change", self._value)
            self._last_committed_value = self._value

    def insert_text(self, text: str) -> None:
        text = text.replace("\n", "").replace("\r", "")
        if not text:
            return
        remaining = self._max_length - len(self._value)
        if remaining <= 0:
            return
        text = text[:remaining]
        self._save_undo_state()
        self._value = (
            self._value[: self._cursor_position] + text + self._value[self._cursor_position :]
        )
        self._cursor_position += len(text)
        self.emit("input", self._value)
        self.mark_dirty()

    def delete_char(self) -> bool:
        if self._cursor_position >= len(self._value):
            return False
        self._save_undo_state()
        self._value = (
            self._value[: self._cursor_position] + self._value[self._cursor_position + 1 :]
        )
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def delete_char_backward(self) -> bool:
        if self._cursor_position <= 0:
            return False
        self._save_undo_state()
        self._value = (
            self._value[: self._cursor_position - 1] + self._value[self._cursor_position :]
        )
        self._cursor_position -= 1
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def delete_word_backward(self) -> bool:
        if self._cursor_position <= 0:
            return False
        self._save_undo_state()
        pos = self._cursor_position
        while pos > 0 and self._value[pos - 1] == " ":
            pos -= 1
        while pos > 0 and self._value[pos - 1] != " ":
            pos -= 1
        self._value = self._value[:pos] + self._value[self._cursor_position :]
        self._cursor_position = pos
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def delete_word_forward(self) -> bool:
        if self._cursor_position >= len(self._value):
            return False
        self._save_undo_state()
        pos = self._cursor_position
        while pos < len(self._value) and self._value[pos] != " ":
            pos += 1
        while pos < len(self._value) and self._value[pos] == " ":
            pos += 1
        self._value = self._value[: self._cursor_position] + self._value[pos:]
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def delete_line(self) -> bool:
        if not self._value:
            return False
        self._save_undo_state()
        self._value = ""
        self._cursor_position = 0
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def delete_to_line_start(self) -> bool:
        if self._cursor_position <= 0:
            return False
        self._save_undo_state()
        self._value = self._value[self._cursor_position :]
        self._cursor_position = 0
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def delete_to_line_end(self) -> bool:
        if self._cursor_position >= len(self._value):
            return False
        self._save_undo_state()
        self._value = self._value[: self._cursor_position]
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def move_cursor_left(self) -> bool:
        if self._cursor_position <= 0:
            return False
        self._cursor_position -= 1
        self.mark_paint_dirty()
        return True

    def move_cursor_right(self) -> bool:
        if self._cursor_position >= len(self._value):
            return False
        self._cursor_position += 1
        self.mark_paint_dirty()
        return True

    def goto_line_home(self) -> bool:
        if self._cursor_position == 0:
            return False
        self._cursor_position = 0
        self.mark_paint_dirty()
        return True

    def goto_line_end(self) -> bool:
        if self._cursor_position == len(self._value):
            return False
        self._cursor_position = len(self._value)
        self.mark_paint_dirty()
        return True

    def goto_buffer_home(self) -> bool:
        """Move cursor to start of buffer (same as line home for single line)."""
        return self.goto_line_home()

    def goto_buffer_end(self) -> bool:
        """Move cursor to end of buffer (same as line end for single line)."""
        return self.goto_line_end()

    def move_word_forward(self) -> bool:
        if self._cursor_position >= len(self._value):
            return False
        pos = self._cursor_position
        while pos < len(self._value) and self._value[pos] != " ":
            pos += 1
        while pos < len(self._value) and self._value[pos] == " ":
            pos += 1
        self._cursor_position = pos
        self.mark_paint_dirty()
        return True

    def move_word_backward(self) -> bool:
        if self._cursor_position <= 0:
            return False
        pos = self._cursor_position
        while pos > 0 and self._value[pos - 1] == " ":
            pos -= 1
        while pos > 0 and self._value[pos - 1] != " ":
            pos -= 1
        self._cursor_position = pos
        self.mark_paint_dirty()
        return True

    _MAX_UNDO_HISTORY = 100

    def _save_undo_state(self) -> None:
        self._undo_stack.append((self._value, self._cursor_position))
        self._redo_stack.clear()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append((self._value, self._cursor_position))
        self._value, self._cursor_position = self._undo_stack.pop()
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append((self._value, self._cursor_position))
        self._value, self._cursor_position = self._redo_stack.pop()
        self.emit("input", self._value)
        self.mark_dirty()
        return True

    def _submit(self) -> None:
        if self._value != self._last_committed_value:
            self.emit("change", self._value)
            self._last_committed_value = self._value
        self.emit("enter", self._value)

    def handle_paste(self, event: Any) -> None:
        if self._on_paste_handler:
            self._on_paste_handler(event)
        text = getattr(event, "text", "")
        if text:
            self.insert_text(text)

    def handle_key(self, event: KeyEvent) -> bool:
        if event.default_prevented:
            return False
        if not self._focused:
            return False

        if self._on_key_down:
            self._on_key_down(event)
            if event.default_prevented:
                return False

        action = self._lookup_action(event)
        if action:
            return self._dispatch_action(action)

        char = event.sequence or event.key
        if len(char) == 1 and char.isprintable() and not event.ctrl and not event.alt:
            self.insert_text(char)
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
        "submit": lambda self: self._submit(),
        "delete-backward": lambda self: self.delete_char_backward(),
        "delete": lambda self: self.delete_char(),
        "delete-word-backward": lambda self: self.delete_word_backward(),
        "delete-word-forward": lambda self: self.delete_word_forward(),
        "delete-line": lambda self: self.delete_line(),
        "delete-to-line-start": lambda self: self.delete_to_line_start(),
        "delete-to-line-end": lambda self: self.delete_to_line_end(),
        "move-left": lambda self: self.move_cursor_left(),
        "move-right": lambda self: self.move_cursor_right(),
        "line-home": lambda self: self.goto_line_home(),
        "line-end": lambda self: self.goto_line_end(),
        "buffer-home": lambda self: self.goto_buffer_home(),
        "buffer-end": lambda self: self.goto_buffer_end(),
        "move-word-forward": lambda self: self.move_word_forward(),
        "move-word-backward": lambda self: self.move_word_backward(),
        "undo": lambda self: self.undo(),
        "redo": lambda self: self.redo(),
    }

    def _setup_measure_func(self) -> None:
        """Set up yoga measure function — always height 1 for single-line input."""

        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            text = self._value or self._placeholder_str
            text_len = len(text) if text else 1

            measured_w = text_len
            measured_h = 1

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(int(width), measured_w)

            return (max(1, measured_w), measured_h)

        self._yoga_node.set_measure_func(measure)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

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

        display_text = self._value
        draw_color = fg
        if not display_text and self._placeholder_str:
            display_text = self._placeholder_str
            draw_color = self._placeholder_color

        if display_text and len(display_text) > w:
            display_text = display_text[:w]

        if display_text:
            buffer.draw_text(display_text, x, y, draw_color, bg)

    def destroy(self) -> None:
        self._is_destroyed = True
        super().destroy()


__all__ = ["InputRenderable"]
