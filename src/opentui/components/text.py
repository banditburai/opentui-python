"""Text component - styled text display."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import yoga

from .. import structs as s
from ..colors import SELECTION_BG
from ..editor.text_buffer_native import NativeTextBuffer
from ..editor.text_view_native import NativeTextBufferView
from ..enums import RenderStrategy
from ..signals import Signal, _ComputedSignal, is_reactive
from ..structs import display_width as _display_width
from ..text_utils import measure_text, wrap_text
from .base import Renderable


def _truncate_with_ellipsis(text: str, max_width: int) -> str:
    """Truncate text to *max_width* display columns, appending ellipsis."""
    if max_width <= 0:
        return ""
    if max_width == 1:
        return "\u2026"
    target = max_width - 1  # reserve 1 col for ellipsis
    w = 0
    for i, ch in enumerate(text):
        cw = _display_width(ch)
        if w + cw > target:
            return text[:i] + "\u2026"
        w += cw
    return text  # fits — shouldn't reach here if caller checked


_MEASURE_UNDEFINED = yoga.MeasureMode.Undefined
_MEASURE_AT_MOST = yoga.MeasureMode.AtMost

if TYPE_CHECKING:
    from ..renderer import Buffer


class Text(Renderable):
    """Text component - displays styled text.

    Usage:
        text = Text("Hello, World!")
        text = Text(content="Hello!")
        text = Text("Hello ", Bold("World"))

        # Reactive callable content — auto-tracks signals and updates reactively:
        count = Signal(0, name="count")
        text = Text(lambda: f"Count: {count()}")
    """

    __slots__ = (
        "_content",
        "_bold",
        "_italic",
        "_underline",
        "_strikethrough",
        "_link",
        "_ellipsis",
        "_selection_start",
        "_selection_end",
        "_selection_bg",
        "_wrap_mode",
        "_text_modifiers",
        "_render_cache_key",
        "_render_cache_lines",
        "_render_cache_selection",
        "_native_text_buffer",
        "_native_text_view",
        "_native_render_key",
    )

    def __init__(
        self,
        content: str | Callable[[], str] | Any | None = None,
        *children: Any,
        # Style
        fg: s.RGBA | str | None = None,
        bg: s.RGBA | str | None = None,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        ellipsis: bool = False,
        # Selection
        selection_start: int | None = None,
        selection_end: int | None = None,
        selection_bg: s.RGBA | str | None = None,
        # Text wrap mode
        wrap_mode: str = "word",
        # Content (can be positional or keyword)
        **kwargs,
    ):
        text_content: str | None = None
        reactive_content: object | None = None
        all_children: tuple[Any, ...]
        if isinstance(content, TextModifier):
            all_children = (content, *children)
        elif is_reactive(content):
            reactive_content = content
            all_children = children
        elif isinstance(content, str):
            text_content = content
            all_children = children
        elif content is None and children and isinstance(children[0], str):
            text_content = children[0]
            all_children = children[1:]
        else:
            text_content = str(content) if content is not None else None
            all_children = children

        super().__init__(
            fg=fg,
            background_color=bg,
            **kwargs,
        )

        if reactive_content is not None:
            if isinstance(reactive_content, Signal | _ComputedSignal):
                str_source = reactive_content.map(lambda v: str(v) if v is not None else "")
            else:
                raw_fn = reactive_content
                str_source = lambda: str(v) if (v := raw_fn()) is not None else ""  # noqa: E731
            self._content = ""
            self._bind_reactive_prop("_content", str_source)
        else:
            self._content = text_content or ""

        self._set_or_bind("_bold", bold)
        self._set_or_bind("_italic", italic)
        self._set_or_bind("_underline", underline)
        self._set_or_bind("_strikethrough", strikethrough)
        self._link: str | None = None
        self._ellipsis: bool = ellipsis
        self._selection_start = selection_start
        self._selection_end = selection_end
        self._selection_bg = self._parse_color(selection_bg) if selection_bg else SELECTION_BG
        self._set_or_bind(
            "_wrap_mode",
            wrap_mode,
            transform=lambda v: v if v in ("none", "char", "word") else "word",
        )

        self._setup_measure_func()

        self._text_modifiers: list[TextModifier] = []
        for child in all_children:
            if isinstance(child, TextModifier):
                self._text_modifiers.append(child)
            elif isinstance(child, str):
                self._content += child
            else:
                self._content += str(child)

        self._render_cache_key: tuple | None = None
        self._render_cache_lines: tuple[str, ...] = ()
        self._render_cache_selection: tuple[int, int] | None = None
        self._native_text_buffer: NativeTextBuffer | None = None
        self._native_text_view: NativeTextBufferView | None = None
        self._native_render_key: tuple | None = None

    @property
    def _has_selection(self) -> bool:
        return (
            self._selection_start is not None
            and self._selection_end is not None
            and self._selection_start < self._selection_end
        )

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        self._content = value
        self.mark_dirty()
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()

    @property
    def wrap_mode(self) -> str:
        return self._wrap_mode

    @wrap_mode.setter
    def wrap_mode(self, value: str) -> None:
        if value not in ("none", "char", "word"):
            value = "word"
        if self._wrap_mode != value:
            self._wrap_mode = value
            self.mark_dirty()
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            total_padding = self._padding_left + self._padding_right
            vertical_padding = self._padding_top + self._padding_bottom

            effective_width = 0 if width_mode == _MEASURE_UNDEFINED else int(width)

            content_width = max(0, effective_width - total_padding)
            w, h = measure_text(self._content, content_width, self._wrap_mode)

            measured_w = w + total_padding
            measured_h = h + vertical_padding

            if width_mode == _MEASURE_AT_MOST:
                measured_w = min(width, measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def get_render_strategy(self) -> RenderStrategy:
        has_selection = self._has_selection
        if has_selection or self._render_before is not None or self._render_after is not None:
            return RenderStrategy.PYTHON_FALLBACK
        if self._link or self._ellipsis:
            return RenderStrategy.PYTHON_FALLBACK
        if self._wrap_mode != "none":
            return RenderStrategy.NATIVE_TEXT
        return RenderStrategy.COMMON_TREE

    def _get_attributes(self) -> int:
        attrs = 0
        if self._bold:
            attrs |= s.TEXT_ATTRIBUTE_BOLD
        if self._italic:
            attrs |= s.TEXT_ATTRIBUTE_ITALIC
        if self._underline:
            attrs |= s.TEXT_ATTRIBUTE_UNDERLINE
        if self._strikethrough:
            attrs |= s.TEXT_ATTRIBUTE_STRIKETHROUGH
        return attrs

    def _get_render_cache(
        self, available_width: int, attrs: int
    ) -> tuple[tuple[str, ...], tuple[int, int] | None]:
        has_selection = self._has_selection
        key = (
            self._content,
            available_width,
            self._wrap_mode,
            attrs,
            self._selection_start,
            self._selection_end,
        )
        if key == self._render_cache_key:
            return self._render_cache_lines, self._render_cache_selection

        lines = tuple(wrap_text(self._content, available_width, self._wrap_mode))
        selection = None
        if has_selection:
            start_pos = max(0, self._selection_start)
            end_pos = min(len(self._content), self._selection_end)
            before_width, _ = measure_text(self._content[:start_pos], 0, "none")
            sel_width, _ = measure_text(self._content[start_pos:end_pos], 0, "none")
            selection = (before_width, sel_width)

        self._render_cache_key = key
        self._render_cache_lines = lines
        self._render_cache_selection = selection
        return lines, selection

    def _get_native_text_view(
        self, available_width: int, viewport_height: int, attrs: int
    ) -> NativeTextBufferView:
        key = (
            self._content,
            available_width,
            viewport_height,
            self._wrap_mode,
            self._fg,
            self._background_color,
            attrs,
        )
        if self._native_text_buffer is None or self._native_text_view is None:
            self._native_text_buffer = NativeTextBuffer()
            self._native_text_view = NativeTextBufferView(
                self._native_text_buffer.ptr, self._native_text_buffer
            )
            self._native_render_key = None
        if self._native_render_key != key:
            self._native_text_buffer.set_text(self._content)
            self._native_text_buffer.set_default_fg(self._fg)
            self._native_text_buffer.set_default_bg(self._background_color)
            self._native_text_buffer.set_default_attributes(attrs)
            self._native_text_view.set_wrap_mode(self._wrap_mode)
            self._native_text_view.set_wrap_width(available_width)
            self._native_text_view.set_viewport(0, 0, available_width, viewport_height)
            self._native_render_key = key
        return self._native_text_view

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        available_width = 0
        if self._layout_width:
            available_width = int(self._layout_width) - self._padding_left - self._padding_right
        available_width = max(0, available_width)
        available_height = 0
        if self._layout_height:
            available_height = int(self._layout_height) - self._padding_top - self._padding_bottom
        available_height = max(1, available_height)
        attrs = self._get_attributes()
        has_selection = self._has_selection

        if (
            not has_selection
            and "\n" not in self._content
            and (
                self._wrap_mode == "none"
                or available_width <= 0
                or len(self._content) <= available_width
            )
        ):
            draw_content = self._content
            if (
                self._ellipsis
                and available_width > 0
                and _display_width(draw_content) > available_width
            ):
                draw_content = _truncate_with_ellipsis(draw_content, available_width)
            buffer.draw_text(
                draw_content, x, y, self._fg, self._background_color, attrs, link=self._link
            )
            return

        if not has_selection and not self._link and available_width > 0:
            buffer.draw_text_buffer_view(
                self._get_native_text_view(available_width, available_height, attrs), x, y
            )
            return

        lines, selection = self._get_render_cache(available_width, attrs)
        if selection is not None:
            before_width, sel_width = selection
            if sel_width > 0:
                buffer.fill_rect(x + before_width, y, sel_width, 1, self._selection_bg)

        for i, line in enumerate(lines):
            buffer.draw_text(
                line, x, y + i, self._fg, self._background_color, attrs, link=self._link
            )


class TextModifier(Renderable):
    """Base class for text modifiers (Bold, Italic, etc.).

    Text modifiers apply styling to their child content.
    They can be nested within Text components.
    """

    __slots__ = (
        "_bold",
        "_italic",
        "_underline",
        "_fg",
        "_bg",
    )

    def __init__(
        self,
        *children: Any,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        fg: s.RGBA | str | None = None,
        bg: s.RGBA | str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._bold = bold
        self._italic = italic
        self._underline = underline
        self._fg = self._parse_color(fg) if isinstance(fg, str) else fg
        self._bg = self._parse_color(bg) if isinstance(bg, str) else bg

        for child in children:
            if isinstance(child, str):
                self.add(Text(child, bold=bold, italic=italic, underline=underline, fg=fg, bg=bg))
            elif isinstance(child, Renderable):
                if hasattr(child, "_bold") or hasattr(child, "_italic"):
                    self._apply_style_to_child(child)
                self.add(child)
            else:
                self.add(
                    Text(str(child), bold=bold, italic=italic, underline=underline, fg=fg, bg=bg)
                )

    def _apply_style_to_child(self, child: Renderable) -> None:
        if hasattr(child, "_bold") and self._bold:
            child._bold = True  # type: ignore[attr-defined]
        if hasattr(child, "_italic") and self._italic:
            child._italic = True  # type: ignore[attr-defined]
        if hasattr(child, "_underline") and self._underline:
            child._underline = True  # type: ignore[attr-defined]

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        for child in self._children:
            if isinstance(child, Text):
                original_bold = child._bold
                original_italic = child._italic
                original_underline = child._underline
                original_fg = child._fg
                original_bg = child._background_color

                try:
                    if self._bold:
                        child._bold = True
                    if self._italic:
                        child._italic = True
                    if self._underline:
                        child._underline = True
                    if self._fg is not None:
                        child._fg = self._fg  # type: ignore[assignment]
                    if self._bg is not None:
                        child._background_color = self._bg  # type: ignore[assignment]

                    child.render(buffer, delta_time)
                finally:
                    child._bold = original_bold
                    child._italic = original_italic
                    child._underline = original_underline
                    child._fg = original_fg
                    child._background_color = original_bg
            else:
                child.render(buffer, delta_time)


class Span(TextModifier):
    """Inline styled text span.

    Usage:
        Text(
            Span("styled", fg="red"),
            " normal"
        )
    """

    def __init__(
        self,
        *children: Any,
        fg: s.RGBA | str | None = None,
        bg: s.RGBA | str | None = None,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        **kwargs,
    ):
        super().__init__(
            *children, fg=fg, bg=bg, bold=bold, italic=italic, underline=underline, **kwargs
        )


class Bold(TextModifier):
    """Bold text modifier.

    Usage:
        Text(Bold("This is bold"))
    """

    def __init__(self, *children: Any, **kwargs):
        super().__init__(*children, bold=True, **kwargs)


class Italic(TextModifier):
    """Italic text modifier.

    Usage:
        Text(Italic("This is italic"))
    """

    def __init__(self, *children: Any, **kwargs):
        super().__init__(*children, italic=True, **kwargs)


class Underline(TextModifier):
    """Underline text modifier.

    Usage:
        Text(Underline("This is underlined"))
    """

    def __init__(self, *children: Any, **kwargs):
        super().__init__(*children, underline=True, **kwargs)


class LineBreak(TextModifier):
    """Line break (br) modifier.

    Usage:
        Text("Line 1", LineBreak(), "Line 2")
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Link(TextModifier):
    """Link modifier — wraps children with an OSC 8 hyperlink.

    Usage:
        Text(Link("click here", href="https://example.com"))
    """

    def __init__(
        self,
        *children: Any,
        href: str = "",
        **kwargs,
    ):
        super().__init__(*children, underline=True, **kwargs)
        self._href = href

    @property
    def href(self) -> str:
        return self._href

    def _collect_text_descendants(
        self, node: Renderable, originals: list[tuple[Text, str | None]]
    ) -> None:
        for child in node._children:
            if isinstance(child, Text):
                originals.append((child, child._link))
                child._link = self._href
            elif isinstance(child, TextModifier):
                self._collect_text_descendants(child, originals)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._href:
            return super().render(buffer, delta_time)

        originals: list[tuple[Text, str | None]] = []
        self._collect_text_descendants(self, originals)
        try:
            super().render(buffer, delta_time)
        finally:
            for text_node, original_link in originals:
                text_node._link = original_link


__all__ = [
    "Text",
    "TextModifier",
    "Span",
    "Bold",
    "Italic",
    "Underline",
    "LineBreak",
    "Link",
]
