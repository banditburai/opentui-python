"""Text component - styled text display."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..text_utils import measure_text
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
        # Handle both positional and keyword content
        text_content = content
        if text_content is None and children:
            # Get text from first child if it's a string
            if isinstance(children[0], str):
                text_content = children[0]
                children = children[1:]

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

        # Process children as text modifiers
        self._text_modifiers: list[TextModifier] = []
        for child in children:
            if isinstance(child, TextModifier):
                self._text_modifiers.append(child)
            elif isinstance(child, str):
                self._content += child
            else:
                # Try to convert to string
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

    def _build_yoga_tree(self) -> Any:
        """Build yoga tree with measure function for text."""
        from ..text_utils import measure_text

        node = self._ensure_yoga_node()

        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            total_padding = self._padding_left + self._padding_right
            vertical_padding = self._padding_top + self._padding_bottom

            # Undefined = max-content (no wrapping)
            if width_mode == yoga.MeasureMode.Undefined:
                effective_width = 0
            else:
                effective_width = int(width)

            content_width = max(0, effective_width - total_padding)
            w, h = measure_text(self._content, content_width, self._wrap_mode)

            measured_w = w + total_padding
            measured_h = h + vertical_padding

            # AtMost mode: return min of available and measured
            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(width, measured_w)

            # Exactly mode: should return measured, but yoga sometimes ignores it
            # Return measured size regardless

            return (measured_w, measured_h)

        node.set_measure_func(measure)

        return node

    def _get_attributes(self) -> int:
        """Get text attribute flags."""
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
        """Render the text."""
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        # Draw selection highlight if there's a valid selection
        if (
            self._selection_start is not None
            and self._selection_end is not None
            and self._selection_start < self._selection_end
        ):
            content = self._content
            start_pos = max(0, self._selection_start)
            end_pos = min(len(content), self._selection_end)

            # Measure text before selection
            before_sel = content[:start_pos]
            sel_text = content[start_pos:end_pos]

            _, text_height = measure_text(content, 0, "none")
            text_height = max(1, text_height)

            # Calculate x positions
            before_width, _ = measure_text(before_sel, 0, "none")
            sel_width, _ = measure_text(sel_text, 0, "none")

            # Draw selection background
            if sel_width > 0:
                buffer.fill_rect(x + before_width, y, sel_width, text_height, self._selection_bg)

        buffer.draw_text(
            self._content, x, y, self._fg, self._background_color, self._get_attributes()
        )


class TextModifier(Renderable):
    """Base class for text modifiers (Bold, Italic, etc.)."""

    def __init__(self, *children: Any, **kwargs):
        super().__init__(**kwargs)

        # Process children
        for child in children:
            if isinstance(child, str):
                # Strings are added as Text nodes
                self.add(Text(child))
            elif isinstance(child, Renderable):
                self.add(child)
            else:
                self.add(Text(str(child)))


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
