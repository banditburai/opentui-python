from __future__ import annotations

import contextlib
import math
from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..native import NativeTextBuffer, NativeTextBufferView
from .base import Renderable
from .textnode import StyledText, TextNode

if TYPE_CHECKING:
    from ..renderer import Buffer


class TextRenderable(Renderable):
    """Text renderable backed by native TextBuffer and TextBufferView.

    Supports two content modes:
    1. Direct: Set content via ``content`` property (string or StyledText)
    2. Node-based: Add TextNode children via ``add()``; text is gathered each render

    Usage:
        text = TextRenderable(content="Hello, World!")
        text = TextRenderable(wrap_mode="word", selectable=True)
        text.content = "New content"

        # Node-based:
        node = TextNode("styled text", fg=RGBA(1,0,0,1))
        text.add(node)
    """

    __slots__ = (
        "_text_buffer",
        "_text_buffer_view",
        "_root_text_node",
        "_scroll_x",
        "_scroll_y",
        "_wrap_mode_str",
        "_selectable",
        "_selection_bg_color",
        "_selection_fg_color",
        "_truncate",
        "_tab_indicator",
        "_tab_indicator_color",
        "_text_attributes",
        "_has_manual_styled_text",
        "_is_scroll_target",
        "_current_selection",
        # True when selection was set via cross-renderable on_selection_changed
        "_cross_renderable_selection_active",
    )

    def __init__(
        self,
        *,
        content: StyledText | str | None = None,
        selectable: bool = True,
        wrap_mode: str = "word",
        truncate: bool = False,
        selection_bg: s.RGBA | str | None = None,
        selection_fg: s.RGBA | str | None = None,
        tab_indicator: str | int | None = None,
        tab_indicator_color: s.RGBA | str | None = None,
        attributes: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._text_buffer = NativeTextBuffer()
        self._text_buffer_view = NativeTextBufferView(self._text_buffer.ptr, self._text_buffer)

        self._root_text_node = TextNode("")

        self._scroll_x: int = 0
        self._scroll_y: int = 0

        self._wrap_mode_str = wrap_mode if wrap_mode in ("none", "char", "word") else "word"
        self._text_buffer_view.set_wrap_mode(self._wrap_mode_str)

        self._selectable = selectable
        self._set_or_bind("_selection_bg_color", selection_bg, transform=self._parse_color)
        self._set_or_bind("_selection_fg_color", selection_fg, transform=self._parse_color)

        self._set_or_bind("_truncate", truncate)

        self._tab_indicator = tab_indicator
        self._set_or_bind("_tab_indicator_color", tab_indicator_color, transform=self._parse_color)
        if isinstance(tab_indicator, int) and tab_indicator > 0:
            self._text_buffer.set_tab_width(tab_indicator)

        self._text_attributes = attributes
        if attributes:
            self._text_buffer.set_default_attributes(attributes)

        # Manual styled text flag — prevents auto-gather from nodes
        self._has_manual_styled_text = False

        self._is_scroll_target = True

        self._current_selection: dict[str, int] | None = None
        self._cross_renderable_selection_active = False

        # Set up yoga measure function BEFORE setting content
        # (content setter calls mark_dirty which requires measure func on leaf)
        self._setup_text_measure_func()

        if content is not None:
            self.content = content

        self._on_mouse_scroll = self._handle_scroll_event

        # Chain _on_size_change: update viewport offset when dimensions change.
        # Preserve any user-provided on_size_change callback from kwargs.
        _prev_on_size_change = self._on_size_change

        def _text_size_change(w, h):
            self._update_viewport_offset()
            if _prev_on_size_change is not None:
                _prev_on_size_change(w, h)

        self._on_size_change = _text_size_change

    @property
    def content(self) -> str:
        return self._text_buffer.get_plain_text()

    @content.setter
    def content(self, value: StyledText | str) -> None:
        self._has_manual_styled_text = True
        if isinstance(value, StyledText):
            chunks = value.to_text_nodes()
            text = "".join(node.to_plain_text() for node in chunks)
            self._text_buffer.set_text(text)
        elif isinstance(value, str):
            self._text_buffer.set_text(value)
        else:
            self._text_buffer.set_text(str(value))
        self._update_text_info()

    @property
    def plain_text(self) -> str:
        return self._text_buffer.get_plain_text()

    @property
    def text_length(self) -> int:
        return self._text_buffer.get_length()

    @property
    def line_count(self) -> int:
        return self._text_buffer.get_line_count()

    @property
    def virtual_line_count(self) -> int:
        return self._text_buffer_view.get_virtual_line_count()

    @property
    def line_info(self):
        from .line_number_renderable import LineInfo

        try:
            info = self._text_buffer_view.get_line_info()
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
    def text_node(self) -> TextNode:
        return self._root_text_node

    @property
    def width(self) -> int:
        return self._layout_width

    @width.setter
    def width(self, value: int | str | None) -> None:
        self._width = value
        if isinstance(value, int | float) and self._flex_shrink == 1:
            self._flex_shrink = 0
        self.mark_dirty()

    @property
    def height(self) -> int:
        return self._layout_height

    @height.setter
    def height(self, value: int | str | None) -> None:
        self._height = value
        if isinstance(value, int | float) and self._flex_shrink == 1:
            self._flex_shrink = 0
        self.mark_dirty()

    @property
    def wrap_mode(self) -> str:
        return self._wrap_mode_str

    @wrap_mode.setter
    def wrap_mode(self, value: str) -> None:
        if value not in ("none", "char", "word"):
            value = "word"
        if self._wrap_mode_str != value:
            self._wrap_mode_str = value
            self._text_buffer_view.set_wrap_mode(value)
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()
            self._update_text_info()

    @property
    def truncate(self) -> bool:
        return self._truncate

    @truncate.setter
    def truncate(self, value: bool) -> None:
        self._truncate = value
        self.mark_paint_dirty()

    @property
    def scroll_x(self) -> int:
        return self._scroll_x

    @scroll_x.setter
    def scroll_x(self, value: int) -> None:
        clamped = max(0, min(value, self.max_scroll_x))
        if self._scroll_x != clamped:
            self._scroll_x = clamped
            self._update_viewport_offset()
            self.mark_paint_dirty()

    @property
    def scroll_y(self) -> int:
        return self._scroll_y

    @scroll_y.setter
    def scroll_y(self, value: int) -> None:
        clamped = max(0, min(value, self.max_scroll_y))
        if self._scroll_y != clamped:
            self._scroll_y = clamped
            self._update_viewport_offset()
            self.mark_paint_dirty()

    @property
    def scroll_width(self) -> int:
        result = self._text_buffer_view.measure_for_dimensions(0, 0)
        if result:
            return result.get("widthColsMax", 0)
        return 0

    @property
    def scroll_height(self) -> int:
        return self.line_count

    @property
    def max_scroll_x(self) -> int:
        w = self._layout_width or 0
        return max(0, self.scroll_width - w)

    @property
    def max_scroll_y(self) -> int:
        h = self._layout_height or 0
        return max(0, self.scroll_height - h)

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

    def has_selection(self) -> bool:

        if self._cross_renderable_selection_active:
            try:
                if self._text_buffer_view.has_selection():
                    return True
            except Exception:
                pass
        return self._current_selection is not None

    def get_selection(self) -> dict[str, int] | None:

        if self._cross_renderable_selection_active:
            try:
                native_sel = self._text_buffer_view.get_selection()
                if native_sel is not None:
                    return native_sel
            except Exception:
                pass
        return self._current_selection

    def get_selected_text(self) -> str:

        if self._cross_renderable_selection_active:
            try:
                native_text = self._text_buffer_view.get_selected_text()
                if native_text:
                    return native_text
            except Exception:
                pass
        sel = self._current_selection
        if sel is None:
            return ""
        start = sel["start"]
        end = sel["end"]
        if start >= end:
            return ""
        text = self._text_buffer.get_plain_text()
        return text[start:end]

    def on_selection_changed(self, selection) -> bool:
        """Converts global selection coordinates to local and applies via the
        native text buffer view's local selection API.  Returns True if this
        renderable has a selection after the change.
        """
        from ..selection import convert_global_to_local_selection

        local_sel = convert_global_to_local_selection(selection, self._x, self._y)

        if local_sel is None or not local_sel.is_active:
            self._cross_renderable_selection_active = False
            self._text_buffer_view.reset_local_selection()
            self._current_selection = None
            self.mark_paint_dirty()
            return False

        self._cross_renderable_selection_active = True

        changed: bool
        if selection is not None and selection.is_start:
            changed = self._text_buffer_view.set_local_selection(
                local_sel.anchor_x,
                local_sel.anchor_y,
                local_sel.focus_x,
                local_sel.focus_y,
                bg_color=self._selection_bg_color,
                fg_color=self._selection_fg_color,
            )
        else:
            changed = self._text_buffer_view.update_local_selection(
                local_sel.anchor_x,
                local_sel.anchor_y,
                local_sel.focus_x,
                local_sel.focus_y,
                bg_color=self._selection_bg_color,
                fg_color=self._selection_fg_color,
            )

        if changed:
            self.mark_paint_dirty()

        return self.has_selection()

    def set_selection(self, start: int, end: int) -> None:
        if start > end:
            start, end = end, start
        text = self._text_buffer.get_plain_text()
        text_len = len(text)
        start = max(0, min(start, text_len))
        end = max(0, min(end, text_len))
        if start == end:
            self._current_selection = None
        else:
            self._current_selection = {"start": start, "end": end}
        with contextlib.suppress(Exception):
            self._text_buffer_view.set_selection(start, end)
        self.mark_paint_dirty()

    def clear_selection(self) -> None:
        self._current_selection = None
        self._cross_renderable_selection_active = False
        with contextlib.suppress(Exception):
            self._text_buffer_view.reset_selection()
        with contextlib.suppress(Exception):
            self._text_buffer_view.reset_local_selection()
        self.mark_paint_dirty()

    @property
    def tab_indicator(self) -> str | int | None:
        return self._tab_indicator

    @tab_indicator.setter
    def tab_indicator(self, value: str | int | None) -> None:
        self._tab_indicator = value
        if isinstance(value, int) and value > 0:
            self._text_buffer.set_tab_width(value)
        self.mark_dirty()

    @property
    def tab_indicator_color(self) -> s.RGBA | None:
        return self._tab_indicator_color

    @tab_indicator_color.setter
    def tab_indicator_color(self, value: s.RGBA | str | None) -> None:
        self._tab_indicator_color = self._parse_color(value)
        self.mark_paint_dirty()

    @property
    def attributes(self) -> int:
        return self._text_attributes

    @attributes.setter
    def attributes(self, value: int) -> None:
        self._text_attributes = value
        self._text_buffer.set_default_attributes(value)
        self.mark_paint_dirty()

    def add(self, child: Any, index: int | None = None) -> int:
        if isinstance(child, TextNode | StyledText | str):
            self._has_manual_styled_text = False  # Switch to node-based mode
            result = self._root_text_node.add(child, index)
            self._sync_text_from_nodes()
            return result
        return super().add(child, index)

    def remove(self, child: Any) -> None:
        if isinstance(child, str):
            children = self._root_text_node.get_children()
            for c in children:
                if isinstance(c, TextNode) and c._id == child:
                    self._root_text_node.remove(c)
                    self._has_manual_styled_text = False
                    self._sync_text_from_nodes()
                    return
            # Also try removing a string child
            try:
                self._root_text_node.remove(child)
                self._has_manual_styled_text = False
                self._sync_text_from_nodes()
            except ValueError:
                pass
            return
        if isinstance(child, TextNode):
            try:
                self._root_text_node.remove(child)
                self._has_manual_styled_text = False
                self._sync_text_from_nodes()
            except ValueError:
                pass
            return
        super().remove(child)

    def insert_before(self, child: Any, anchor: Any = None) -> int:
        if isinstance(child, TextNode | StyledText | str):
            self._has_manual_styled_text = False  # Switch to node-based mode
            if anchor is not None:
                self._root_text_node.insert_before(child, anchor)
            else:
                self._root_text_node.add(child)
            self._sync_text_from_nodes()
            return self._root_text_node.get_children_count() - 1
        return super().insert_before(child, anchor)

    def clear(self) -> None:
        self._root_text_node.clear()
        self._root_text_node._text = ""
        self._text_buffer.clear()
        self._has_manual_styled_text = False
        self._current_selection = None
        self._update_text_info()

    def get_text_children(self) -> list[TextNode]:
        return [c for c in self._root_text_node.get_children() if isinstance(c, TextNode)]

    def coord_to_offset(self, local_x: int, local_y: int) -> int:
        text = self.plain_text
        if not text:
            return 0

        orig_lines = text.split("\n")

        if self._wrap_mode_str == "none" or (self._layout_width or 0) <= 0:
            # No wrapping — simple line/col mapping
            y = max(0, local_y + self._scroll_y)
            if y >= len(orig_lines):
                return len(text)
            offset = sum(len(orig_lines[i]) + 1 for i in range(y))
            offset += max(0, min(local_x, len(orig_lines[y])))
            return min(offset, len(text))

        # With wrapping — build visual→original offset map
        w = self._layout_width
        visual_line_offsets: list[int] = []  # offset in text for each visual line start
        base_offset = 0
        for orig_line in orig_lines:
            if not orig_line or len(orig_line) <= w:
                visual_line_offsets.append(base_offset)
            elif self._wrap_mode_str == "word":
                wrapped = _word_wrap(orig_line, w)
                pos = 0
                for wl in wrapped:
                    visual_line_offsets.append(base_offset + pos)
                    pos += len(wl)
                    if pos < len(orig_line) and orig_line[pos] == " ":
                        pos += 1
            else:  # char
                for i in range(0, len(orig_line), w):
                    visual_line_offsets.append(base_offset + i)
            base_offset += len(orig_line) + 1  # +1 for newline

        y = max(0, local_y + self._scroll_y)
        if y >= len(visual_line_offsets):
            return len(text)

        line_start = visual_line_offsets[y]
        # Determine visual line length
        if y + 1 < len(visual_line_offsets):
            line_end = visual_line_offsets[y + 1]
            # Don't count newline as part of this visual line
            if line_end > 0 and line_end - 1 < len(text) and text[line_end - 1] == "\n":
                line_end -= 1
        else:
            line_end = len(text)

        line_len = line_end - line_start
        col = max(0, min(local_x, line_len))
        return min(line_start + col, len(text))

    def _sync_text_from_nodes(self) -> None:
        if self._has_manual_styled_text:
            return
        plain_text = self._root_text_node.to_plain_text()
        self._text_buffer.set_text(plain_text)
        self._update_text_info()

    def _update_text_info(self) -> None:
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self._update_viewport_offset()
        self.mark_dirty()

    def _update_viewport_offset(self) -> None:
        w = self._layout_width or 0
        h = self._layout_height or 0
        if w > 0 and h > 0:
            self._text_buffer_view.set_viewport(self._scroll_x, self._scroll_y, w, h)

    def _setup_text_measure_func(self) -> None:
        def measure(
            yoga_node: Any, width: float, width_mode: Any, height: float, height_mode: Any
        ) -> tuple[float, float]:
            import yoga

            # Undefined = max-content (no wrapping constraint)
            if width_mode == yoga.MeasureMode.Undefined:
                effective_width = 0
            else:
                effective_width = 0 if math.isnan(width) else int(width)

            effective_height = 1 if math.isnan(height) else int(height)
            if effective_height <= 0:
                effective_height = 1

            if effective_width > 0:
                self._text_buffer_view.set_wrap_width(effective_width)

            result = self._text_buffer_view.measure_for_dimensions(
                effective_width, max(1, effective_height)
            )

            if result:
                measured_w = max(1, result["widthColsMax"])
                measured_h = max(1, result["lineCount"])
            else:
                measured_w = 1
                measured_h = 1

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(int(width), measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def _handle_scroll_event(self, event: Any) -> None:
        direction = getattr(event, "scroll_direction", None)
        if direction is None:
            delta = getattr(event, "scroll_delta", 0)
            direction = "down" if delta > 0 else "up"

        if direction in ("up", "down"):
            delta = 1 if direction == "down" else -1
            self.scroll_y = self._scroll_y + delta
        elif direction in ("left", "right"):
            # Only allow horizontal scrolling when not wrapping
            if self._wrap_mode_str == "none":
                delta = 1 if direction == "right" else -1
                self.scroll_x = self._scroll_x + delta

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        if not self._has_manual_styled_text:
            self._sync_text_from_nodes()

        x = self._x
        y = self._y
        w = self._layout_width or 0
        h = self._layout_height or 0

        if w <= 0 or h <= 0:
            return

        if self._background_color:
            buffer.fill_rect(x, y, w, h, self._background_color)

        try:
            from ..native import _nb

            if _nb is not None:
                # Apply buffer offset for native draw (the native function
                # bypasses Python-level offset/scissor stacks).
                render_x, render_y = x, y
                if buffer._offset_stack:
                    dx, dy = buffer._offset_stack[-1]
                    render_x += dx
                    render_y += dy

                # Update viewport before drawing.  The native buffer's
                # scissor stack (synced via Buffer.push_scissor_rect) clips
                # per-character.
                self._text_buffer_view.set_viewport(self._scroll_x, self._scroll_y, w, h)
                _nb.text_buffer.buffer_draw_text_buffer_view(
                    buffer._ptr, self._text_buffer_view._ptr, render_x, render_y
                )
                if self._border:
                    self._render_border(buffer, x, y, w, h)
                return
        except Exception:
            pass

        self._render_python(buffer, x, y, w, h)

    def _render_python(self, buffer: Buffer, x: int, y: int, w: int, h: int) -> None:
        text = self._text_buffer.get_plain_text()
        if not text:
            return

        lines = text.split("\n")

        if self._wrap_mode_str != "none" and w > 0:
            wrapped_lines: list[str] = []
            for line in lines:
                if not line:
                    wrapped_lines.append("")
                elif len(line) <= w:
                    wrapped_lines.append(line)
                elif self._wrap_mode_str == "word":
                    wrapped_lines.extend(_word_wrap(line, w))
                else:  # char
                    for i in range(0, len(line), w):
                        wrapped_lines.append(line[i : i + w])
            lines = wrapped_lines

        start_line = self._scroll_y
        visible_lines = lines[start_line : start_line + h]

        fg = self._fg
        attrs = self._text_attributes

        for i, line in enumerate(visible_lines):
            if not line:
                continue
            display_line = line
            if self._scroll_x > 0 and self._wrap_mode_str == "none":
                display_line = line[self._scroll_x :]
            if self._truncate and len(display_line) > w:
                display_line = display_line[: w - 1] + "…"
            elif len(display_line) > w:
                display_line = display_line[:w]

            buffer.draw_text(display_line, x, y + i, fg, None, attrs)

        if self._border:
            self._render_border(buffer, x, y, w, h)

    def _render_border(self, buffer: Buffer, x: int, y: int, w: int, h: int) -> None:
        border_color = self._border_color
        if self._focused and self._focused_border_color:
            border_color = self._focused_border_color
        buffer.draw_box(
            x,
            y,
            w,
            h,
            self._border_style,
            border_color,
            title=self._title,
            title_alignment=self._title_alignment,
        )

    def destroy(self) -> None:
        self._root_text_node.clear()
        self._current_selection = None
        super().destroy()


def _word_wrap(text: str, width: int) -> list[str]:
    if not text or width <= 0:
        return [text]

    lines: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= width:
            lines.append(remaining)
            break

        # Find last space within width
        break_pos = remaining.rfind(" ", 0, width + 1)
        if break_pos <= 0:
            # No space found — break at width (long word)
            break_pos = width
            lines.append(remaining[:break_pos])
            remaining = remaining[break_pos:]
        else:
            lines.append(remaining[:break_pos])
            remaining = remaining[break_pos + 1 :]  # Skip the space

    return lines if lines else [""]


__all__ = ["TextRenderable"]
