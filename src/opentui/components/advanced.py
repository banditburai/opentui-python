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

        self._setup_measure_func()

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        self._content = value
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()

    def _setup_measure_func(self) -> None:
        """Set up yoga measure function for code layout."""

        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            total_padding = self._padding_left + self._padding_right
            vertical_padding = self._padding_top + self._padding_bottom

            lines = self._content.split("\n") if self._content else []
            num_lines = len(lines)

            # Gutter width: 4 chars (3 for number + 1 space) when showing line numbers
            gutter = 4 if self._show_line_numbers else 0
            max_line_width = max((len(line) for line in lines), default=0)
            content_w = max_line_width + gutter

            measured_w = content_w + total_padding
            measured_h = num_lines + vertical_padding

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(width, measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the code block."""
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._layout_width or (buffer.width - x)
        height = self._layout_height or (buffer.height - y)

        # Draw background
        if self._background_color:
            buffer.fill_rect(x, y, width, height, self._background_color)

        # Render code lines
        lines = self._content.split("\n")
        for i, line in enumerate(lines[:height]):
            line_y = y + i
            if line_y >= buffer.height:
                break

            if self._show_line_numbers:
                line_num = str(i + 1).rjust(3)
                buffer.draw_text(
                    line_num, x, line_y, s.RGBA(0.5, 0.5, 0.5, 1), self._background_color
                )

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

        self._setup_measure_func()

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            total_padding = self._padding_left + self._padding_right
            vertical_padding = self._padding_top + self._padding_bottom

            old_lines = self._old_text.split("\n") if self._old_text else []
            new_lines = self._new_text.split("\n") if self._new_text else []
            # Diff output can have at most old + new lines
            num_lines = len(old_lines) + len(new_lines)
            max_line_width = max(
                max((len(line) for line in old_lines), default=0),
                max((len(line) for line in new_lines), default=0),
            )
            # "+2" for the status prefix ("+ " or "- ")
            content_w = max_line_width + 2

            measured_w = content_w + total_padding
            measured_h = num_lines + vertical_padding

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(width, measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def _compute_diff(self) -> list[tuple[str, str, int]]:
        """Compute diff using difflib.SequenceMatcher.

        Returns list of (status, line, line_num) tuples:
        - status: '-', '+', or ' '
        - line: the text content
        - line_num: line number in original/new
        """
        import difflib

        old_lines = self._old_text.split("\n")
        new_lines = self._new_text.split("\n")

        diff_lines: list[tuple[str, str, int]] = []
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i in range(i1, i2):
                    diff_lines.append((" ", old_lines[i], i))
            elif tag == "replace":
                for i in range(i1, i2):
                    diff_lines.append(("-", old_lines[i], i))
                for j in range(j1, j2):
                    diff_lines.append(("+", new_lines[j], j))
            elif tag == "delete":
                for i in range(i1, i2):
                    diff_lines.append(("-", old_lines[i], i))
            elif tag == "insert":
                for j in range(j1, j2):
                    diff_lines.append(("+", new_lines[j], j))

        return diff_lines

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the diff."""
        if not self._visible:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        diff_lines = self._compute_diff()

        for i, (status, line, _) in enumerate(diff_lines):
            if y + i >= buffer.height:
                break

            if status == "-":
                buffer.draw_text(
                    f"- {line}", x, y + i, s.RGBA(1, 0.3, 0.3, 1), self._background_color
                )
            elif status == "+":
                buffer.draw_text(
                    f"+ {line}", x, y + i, s.RGBA(0.3, 1, 0.3, 1), self._background_color
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

        self._setup_measure_func()

    def _setup_measure_func(self) -> None:
        """Set up yoga measure function for markdown layout."""

        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            total_padding = self._padding_left + self._padding_right
            vertical_padding = self._padding_top + self._padding_bottom

            lines = self._content.split("\n") if self._content else []
            num_lines = len(lines)
            max_line_width = max((len(line) for line in lines), default=0)

            measured_w = max_line_width + total_padding
            measured_h = num_lines + vertical_padding

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(width, measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render markdown (simplified - full implementation would parse markdown)."""
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top

        lines = self._content.split("\n")
        for i, line in enumerate(lines):
            if y + i >= buffer.height:
                break

            if line.startswith("# "):
                buffer.draw_text(line[2:], x, y + i, self._fg, self._background_color)
            elif line.startswith("## "):
                buffer.draw_text(line[3:], x, y + i, self._fg, self._background_color)
            elif line.startswith("### "):
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
        self._gutter_width = width

        self._setup_measure_func()

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            total_padding = self._padding_left + self._padding_right
            vertical_padding = self._padding_top + self._padding_bottom

            lines = self._content.split("\n") if self._content else []
            num_lines = len(lines)
            max_line_width = max((len(line) for line in lines), default=0)
            content_w = max_line_width + self._gutter_width + 1

            measured_w = content_w + total_padding
            measured_h = num_lines + vertical_padding

            if width_mode == yoga.MeasureMode.AtMost:
                measured_w = min(width, measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._content:
            return

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        width = self._layout_width or (buffer.width - x)

        lines = self._content.split("\n")
        for i, line in enumerate(lines):
            line_y = y + i
            if line_y >= buffer.height:
                break

            num = str(self._start + i).rjust(self._gutter_width)
            buffer.draw_text(num, x, line_y, s.RGBA(0.5, 0.5, 0.5, 1), self._background_color)

            content_x = x + self._gutter_width + 1
            display_line = line[: width - self._gutter_width - 1]
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

        current_x = x
        for i, tab in enumerate(self._tabs):
            is_selected = i == self._selected

            bg = s.RGBA(0.2, 0.2, 0.4, 1) if is_selected else self._background_color

            text = f" {tab} "
            fg = s.RGBA(1, 1, 1, 1) if is_selected else self._fg

            buffer.draw_text(text, current_x, y, fg, bg)

            current_x += len(text) + 1


class Slider(Renderable):
    """Slider component for numeric input.

    Usage:
        slider = Slider(
            value=50,
            min_val=0,
            max_val=100
        )
    """

    def __init__(
        self,
        *children: Any,
        # Value
        value: float = 0,
        min_val: float = 0,
        max_val: float = 100,
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
        self._min = min_val
        self._max = max_val
        self._step = step

        if on_change:
            self.on("change", on_change)

        self._focusable = True

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        clamped = v
        clamped = max(clamped, self._min)
        clamped = min(clamped, self._max)
        self._value = clamped

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
        width = self._layout_width or 20

        range_size = self._max - self._min
        if range_size > 0:
            position = int((self._value - self._min) / range_size * (width - 2))
        else:
            position = 0

        buffer.draw_text("[", x, y, self._fg, self._background_color)
        buffer.draw_text("-" * (width - 2), x + 1, y, self._fg, self._background_color)
        buffer.draw_text("]", x + width - 1, y, self._fg, self._background_color)

        thumb_x = x + 1 + position
        buffer.draw_text("●", thumb_x, y, s.RGBA(0.3, 0.7, 1, 1), self._background_color)

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

        col_widths = [len(c) for c in self._columns]
        for row in self._rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(cell))

        current_x = x
        for i, col in enumerate(self._columns):
            w = col_widths[i] if i < len(col_widths) else 10
            buffer.draw_text(col.ljust(w), current_x, y, self._fg, self._background_color)
            current_x += w + 1

        y += 1
        current_x = x
        for _i, w in enumerate(col_widths):
            buffer.draw_text(
                "-" * (w + 1), current_x, y, s.RGBA(0.5, 0.5, 0.5, 1), self._background_color
            )
            current_x += w + 1

        for _row_idx, row in enumerate(self._rows):
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
