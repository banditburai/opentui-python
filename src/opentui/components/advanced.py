"""Advanced components - Code, Diff, Markdown, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import structs as s
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


class Code(Renderable):
    """Code block with syntax highlighting.

    Usage:
        code = Code(
            "def hello():\\n    print('world')",
            filetype="python"
        )
    """

    def __init__(
        self,
        content: str = "",
        *children: Any,
        # Code options
        filetype: str = "plaintext",
        tree_sitter_client: Any = None,
        # Display options
        show_line_numbers: bool = True,
        highlight_current_line: bool = False,
        # Style
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._content = content
        self._filetype = filetype
        self._show_line_numbers = show_line_numbers
        self._highlight_current_line = highlight_current_line
        self._syntax_style = None

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        self._content = value

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the code block."""
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._width or (buffer.width - x)
        height = self._height or (buffer.height - y)

        # Draw background
        if self._background_color:
            buffer.fill_rect(x, y, width, height, self._background_color)

        # Render code lines
        lines = self._content.split("\n")
        for i, line in enumerate(lines[:height]):
            line_y = y + i
            if line_y >= buffer.height:
                break

            # Line number
            if self._show_line_numbers:
                line_num = str(i + 1).rjust(3)
                buffer.draw_text(
                    line_num, x, line_y, s.RGBA(0.5, 0.5, 0.5, 1), self._background_color
                )

            # Code content
            code_x = x + 4 if self._show_line_numbers else x
            display_line = line[: width - 4] if self._show_line_numbers else line[:width]
            buffer.draw_text(display_line, code_x, line_y, self._fg, self._background_color)


class Diff(Renderable):
    """Diff viewer component.

    Usage:
        diff = Diff(
            old_text="line 1\\nline 2",
            new_text="line 1\\nline 3",
            mode="unified"
        )
    """

    def __init__(
        self,
        old_text: str = "",
        new_text: str = "",
        *children: Any,
        # Diff options
        mode: str = "unified",  # "unified" or "split"
        context_lines: int = 3,
        # Style
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._old_text = old_text
        self._new_text = new_text
        self._mode = mode
        self._context_lines = context_lines

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the diff."""
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        # Simple diff rendering (would use actual diff algorithm in full impl)
        old_lines = self._old_text.split("\n")
        new_lines = self._new_text.split("\n")

        # Render with simple prefix indicators
        for i, line in enumerate(old_lines):
            if i < len(new_lines) and line != new_lines[i]:
                # Modified line - show both
                buffer.draw_text(
                    f"- {line}", x, y + i * 2, s.RGBA(1, 0.3, 0.3, 1), self._background_color
                )
                buffer.draw_text(
                    f"+ {new_lines[i]}",
                    x,
                    y + i * 2 + 1,
                    s.RGBA(0.3, 1, 0.3, 1),
                    self._background_color,
                )
            else:
                buffer.draw_text(f"  {line}", x, y + i, self._fg, self._background_color)


class Markdown(Renderable):
    """Markdown renderer.

    Usage:
        md = Markdown("# Hello\\n\\nThis is **bold**")
    """

    def __init__(
        self,
        content: str = "",
        *children: Any,
        # Options
        enable_syntax_highlight: bool = True,
        enable_math: bool = True,
        # Style
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._content = content
        self._enable_syntax_highlight = enable_syntax_highlight
        self._enable_math = enable_math

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render markdown (simplified - full implementation would parse markdown)."""
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        # Simple rendering - just show the raw content
        # A full implementation would parse markdown and render properly
        lines = self._content.split("\n")
        for i, line in enumerate(lines):
            if y + i >= buffer.height:
                break

            # Check for headings
            if line.startswith("# "):
                # H1
                buffer.draw_text(line[2:], x, y + i, self._fg, self._background_color)
            elif line.startswith("## "):
                # H2
                buffer.draw_text(line[3:], x, y + i, self._fg, self._background_color)
            elif line.startswith("### "):
                # H3
                buffer.draw_text(line[4:], x, y + i, self._fg, self._background_color)
            else:
                buffer.draw_text(line, x, y + i, self._fg, self._background_color)


class LineNumber(Renderable):
    """Code display with line numbers.

    Usage:
        code = LineNumber("code content here")
    """

    def __init__(
        self,
        content: str = "",
        *children: Any,
        # Options
        start: int = 1,
        width: int = 4,
        # Style
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._content = content
        self._start = start
        self._width = width

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render with line numbers."""
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._width or (buffer.width - x)

        lines = self._content.split("\n")
        for i, line in enumerate(lines):
            line_y = y + i
            if line_y >= buffer.height:
                break

            # Line number
            num = str(self._start + i).rjust(self._width)
            buffer.draw_text(num, x, line_y, s.RGBA(0.5, 0.5, 0.5, 1), self._background_color)

            # Content
            content_x = x + self._width + 1
            display_line = line[: width - self._width - 1]
            buffer.draw_text(display_line, content_x, line_y, self._fg, self._background_color)


class AsciiFont(Renderable):
    """ASCII art text renderer.

    Usage:
        ascii = AsciiFont("Hello", font="doom")
    """

    def __init__(
        self,
        content: str = "",
        *children: Any,
        # Options
        font: str = "standard",
        # Style
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._content = content
        self._font = font

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render ASCII art (simplified - would use figlet in full impl)."""
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        # Just render as regular text for now
        # Full implementation would use figlet or similar
        buffer.draw_text(self._content, x, y, self._fg, self._background_color)


class TabSelect(Renderable):
    """Tab-based selection component.

    Usage:
        tabs = TabSelect(
            tabs=["Tab 1", "Tab 2", "Tab 3"],
            selected=selected_tab
        )
    """

    def __init__(
        self,
        tabs: list[str] | None = None,
        *children: Any,
        # Selection
        selected: int = 0,
        # Focus
        focused: bool = False,
        # Events
        on_change: Any = None,
        # Style
        **kwargs,
    ):
        super().__init__(focused=focused, **kwargs)

        self._tabs = tabs or []
        self._selected = selected

        if on_change:
            self.on("change", on_change)

        self._focusable = True

    @property
    def tabs(self) -> list[str]:
        return self._tabs

    @property
    def selected(self) -> int:
        return self._selected

    def select(self, index: int) -> None:
        """Select a tab by index."""
        if 0 <= index < len(self._tabs):
            self._selected = index
            self.emit("change", index, self._tabs[index])

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the tabs."""
        if not self._visible or not self._tabs:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        # Draw each tab
        current_x = x
        for i, tab in enumerate(self._tabs):
            is_selected = i == self._selected

            # Tab background
            if is_selected:
                bg = s.RGBA(0.2, 0.2, 0.4, 1)
            else:
                bg = self._background_color

            # Tab content
            text = f" {tab} "
            fg = s.RGBA(1, 1, 1, 1) if is_selected else self._fg

            buffer.draw_text(text, current_x, y, fg, bg)

            # Move to next tab position
            current_x += len(text) + 1


class Slider(Renderable):
    """Slider component for numeric input.

    Usage:
        slider = Slider(
            value=50,
            min=0,
            max=100
        )
    """

    def __init__(
        self,
        *children: Any,
        # Value
        value: float = 0,
        min: float = 0,
        max: float = 100,
        step: float = 1,
        # Focus
        focused: bool = False,
        # Events
        on_change: Any = None,
        # Style
        **kwargs,
    ):
        super().__init__(focused=focused, **kwargs)

        self._value = value
        self._min = min
        self._max = max
        self._step = step

        if on_change:
            self.on("change", on_change)

        self._focusable = True

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = max(self._min, min(self._max, v))

    def increment(self, amount: float = 1) -> None:
        """Increment the value."""
        new_value = self._value + (amount * self._step)
        self.value = new_value
        self.emit("change", self._value)

    def decrement(self, amount: float = 1) -> None:
        """Decrement the value."""
        self.increment(-amount)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the slider."""
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._width or 20

        # Calculate position
        range_size = self._max - self._min
        if range_size > 0:
            position = int((self._value - self._min) / range_size * (width - 2))
        else:
            position = 0

        # Draw track
        buffer.draw_text("[", x, y, self._fg, self._background_color)
        buffer.draw_text("-" * (width - 2), x + 1, y, self._fg, self._background_color)
        buffer.draw_text("]", x + width - 1, y, self._fg, self._background_color)

        # Draw thumb
        thumb_x = x + 1 + position
        buffer.draw_text("●", thumb_x, y, s.RGBA(0.3, 0.7, 1, 1), self._background_color)

        # Draw value
        value_text = f" {self._value:.1f} "
        buffer.draw_text(value_text, x, y + 1, self._fg, self._background_color)


class TextTable(Renderable):
    """Table component for displaying tabular data.

    Usage:
        table = TextTable(
            columns=["Name", "Age"],
            rows=[["Alice", "30"], ["Bob", "25"]]
        )
    """

    def __init__(
        self,
        *children: Any,
        # Data
        columns: list[str] | None = None,
        rows: list[list[str]] | None = None,
        # Options
        auto_width: bool = True,
        # Style
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._columns = columns or []
        self._rows = rows or []
        self._auto_width = auto_width

    @property
    def columns(self) -> list[str]:
        return self._columns

    @property
    def rows(self) -> list[list[str]]:
        return self._rows

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the table."""
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        # Calculate column widths
        col_widths = [len(c) for c in self._columns]
        for row in self._rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(cell))

        # Render header
        current_x = x
        for i, col in enumerate(self._columns):
            w = col_widths[i] if i < len(col_widths) else 10
            buffer.draw_text(col.ljust(w), current_x, y, self._fg, self._background_color)
            current_x += w + 1

        # Render separator
        y += 1
        current_x = x
        for i, w in enumerate(col_widths):
            buffer.draw_text(
                "-" * (w + 1), current_x, y, s.RGBA(0.5, 0.5, 0.5, 1), self._background_color
            )
            current_x += w + 1

        # Render rows
        for row_idx, row in enumerate(self._rows):
            y += 1
            current_x = x
            for i, cell in enumerate(row):
                w = col_widths[i] if i < len(col_widths) else 10
                buffer.draw_text(cell.ljust(w), current_x, y, self._fg, self._background_color)
                current_x += w + 1


__all__ = [
    "Code",
    "Diff",
    "Markdown",
    "LineNumber",
    "AsciiFont",
    "TabSelect",
    "Slider",
    "TextTable",
]
