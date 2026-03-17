"""Text component - styled text display."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..text_utils import measure_text, wrap_text
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


class Text(Renderable):
    """Text component - displays styled text.

    Usage:
        text = Text("Hello, World!")
        text = Text(content="Hello!")
        text = Text("Hello ", Bold("World"))
    """

    def __init__(
        self,
        content: str | None = None,
        *children: Any,
        # Style
        fg: s.RGBA | str | None = None,
        bg: s.RGBA | str | None = None,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
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
        all_children: tuple[Any, ...]
        if isinstance(content, TextModifier):
            all_children = (content, *children)
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

        self._content = text_content or ""
        self._bold = bold
        self._italic = italic
        self._underline = underline
        self._strikethrough = strikethrough
        self._selection_start = selection_start
        self._selection_end = selection_end
        self._selection_bg = (
            self._parse_color(selection_bg) if selection_bg else s.RGBA(0.3, 0.3, 0.7, 1.0)
        )
        self._wrap_mode = wrap_mode if wrap_mode in ("none", "char", "word") else "word"

        # Closure reads self._content dynamically for yoga measure
        self._setup_measure_func()

        self._text_modifiers: list[TextModifier] = []
        for child in all_children:
            if isinstance(child, TextModifier):
                self._text_modifiers.append(child)
            elif isinstance(child, str):
                self._content += child
            else:
                self._content += str(child)

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        self._content = value
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
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            total_padding = self._padding_left + self._padding_right
            vertical_padding = self._padding_top + self._padding_bottom

            effective_width = 0 if width_mode == yoga.MeasureMode.Undefined else int(width)

            content_width = max(0, effective_width - total_padding)
            w, h = measure_text(self._content, content_width, self._wrap_mode)

            measured_w = w + total_padding
            measured_h = h + vertical_padding

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(width, measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

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

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        available_width = 0
        if self._layout_width:
            available_width = int(self._layout_width) - self._padding_left - self._padding_right
        available_width = max(0, available_width)

        lines = wrap_text(self._content, available_width, self._wrap_mode)

        if (
            self._selection_start is not None
            and self._selection_end is not None
            and self._selection_start < self._selection_end
        ):
            start_pos = max(0, self._selection_start)
            end_pos = min(len(self._content), self._selection_end)

            before_width, _ = measure_text(self._content[:start_pos], 0, "none")
            sel_width, _ = measure_text(self._content[start_pos:end_pos], 0, "none")

            if sel_width > 0:
                buffer.fill_rect(x + before_width, y, sel_width, 1, self._selection_bg)

        attrs = self._get_attributes()
        for i, line in enumerate(lines):
            buffer.draw_text(line, x, y + i, self._fg, self._background_color, attrs)


class TextModifier(Renderable):
    """Base class for text modifiers (Bold, Italic, etc.).

    Text modifiers apply styling to their child content.
    They can be nested within Text components.
    """

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
            if isinstance(child, Renderable):
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
    """Link modifier.

    Usage:
        Text(Link("click here", href="https://example.com"))
    """

    def __init__(
        self,
        *children: Any,
        href: str = "",
        **kwargs,
    ):
        super().__init__(*children, **kwargs)
        self._href = href

    @property
    def href(self) -> str:
        return self._href


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
