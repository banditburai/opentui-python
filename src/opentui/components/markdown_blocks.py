"""Markdown block renderables and helper functions.

Extracted from ``markdown_renderable.py``: self-contained classes and
utility functions used by ``MarkdownRenderable`` to render individual
markdown blocks (tables, code, text, external).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..structs import display_width as _display_width
from .base import Renderable
from .text_renderable import TextRenderable as NativeTextRenderable

if TYPE_CHECKING:
    from ..renderer import Buffer

# ---------------------------------------------------------------------------
# Inline-formatting regex patterns
# ---------------------------------------------------------------------------

_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_RE_CODE = re.compile(r"`(.*?)`")
_RE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_RE_INCOMPLETE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)$")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _strip_inline_formatting(text: str, conceal: bool = True) -> str:
    """Strip or keep inline markdown formatting markers.

    When conceal=True, removes markers like **, *, ` and converts links
    to 'text (url)' format.
    When conceal=False, returns text as-is.
    """
    if not conceal:
        return text

    # Process links first (before other formatting)
    result = text
    # Complete links: [text](url) -> text (url)
    result = _RE_LINK.sub(r"\1 (\2)", result)
    # Incomplete links: [text](url -> text(url
    result = _RE_INCOMPLETE_LINK.sub(r"\1(\2", result)

    # Bold: **text** -> text
    result = _RE_BOLD.sub(r"\1", result)
    # Italic: *text* -> text
    result = _RE_ITALIC.sub(r"\1", result)
    # Inline code: `text` -> text
    result = _RE_CODE.sub(r"\1", result)

    return result


def _strip_table_cell(text: str, conceal: bool = True) -> str:
    return _strip_inline_formatting(text.strip(), conceal)


def _parse_escaped_cells(row_text: str) -> list[str]:
    """Split a table row into cells, handling escaped pipes."""
    stripped = row_text.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    cells = []
    current = ""
    i = 0
    while i < len(stripped):
        if stripped[i] == "\\" and i + 1 < len(stripped) and stripped[i + 1] == "|":
            current += "|"
            i += 2
        elif stripped[i] == "|":
            cells.append(current)
            current = ""
            i += 1
        else:
            current += stripped[i]
            i += 1
    cells.append(current)
    return [c.strip() for c in cells]


def _render_table(
    header: list[dict[str, Any]],
    rows: list[list[dict[str, Any]]],
    conceal: bool = True,
) -> list[str]:
    """Render a markdown table as bordered text lines.

    Returns list of lines like:
        +---------+-----+
        |Name     |Age  |
        +---------+-----+
        |Alice    |30   |
        +---------+-----+
    """
    if not header:
        return []

    num_cols = len(header)

    header_texts = [_strip_table_cell(h.get("text", ""), conceal) for h in header]
    row_texts = []
    for row in rows:
        row_cells = []
        for i in range(num_cols):
            if i < len(row):
                row_cells.append(_strip_table_cell(row[i].get("text", ""), conceal))
            else:
                row_cells.append("")
        row_texts.append(row_cells)

    col_widths = [_display_width(h) for h in header_texts]
    for row_cells in row_texts:
        for i, cell in enumerate(row_cells):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], _display_width(cell))

    col_widths = [max(w, 1) for w in col_widths]

    lines: list[str] = []

    top = "\u250c" + "\u252c".join("\u2500" * w for w in col_widths) + "\u2510"
    lines.append(top)

    header_line = "\u2502"
    for i, text in enumerate(header_texts):
        w = col_widths[i]
        dw = _display_width(text)
        padding = w - dw
        header_line += text + " " * padding + "\u2502"
    lines.append(header_line)

    for row_cells in row_texts:
        sep = "\u251c" + "\u253c".join("\u2500" * w for w in col_widths) + "\u2524"
        lines.append(sep)

        row_line = "\u2502"
        for i in range(num_cols):
            w = col_widths[i]
            text = row_cells[i] if i < len(row_cells) else ""
            dw = _display_width(text)
            padding = w - dw
            row_line += text + " " * padding + "\u2502"
        lines.append(row_line)

    bottom = "\u2514" + "\u2534".join("\u2500" * w for w in col_widths) + "\u2518"
    lines.append(bottom)

    return lines


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BlockState:
    token: Any  # MarkedToken
    token_raw: str
    renderable: Renderable
    table_content_cache: Any = None


@dataclass
class TableContentCache:
    # content is list of rows, each row is list of cells, each cell is list of chunks
    content: list[list[list[dict[str, str]]]]
    cell_keys: list[list[int]]


# ---------------------------------------------------------------------------
# Block renderable classes
# ---------------------------------------------------------------------------


class _MarkdownBlockRenderable(Renderable):
    __slots__ = (
        "_block_type",
        "_block_content",
        "_block_lines",
        "_margin_bottom_val",
        "_table_content",
        "_column_width_mode",
        "_column_fitter",
        "_wrap_mode_str",
        "_cell_padding",
        "_show_borders",
        "_border_val",
        "_outer_border",
        "_selectable_val",
    )

    def __init__(
        self,
        *,
        block_type: str = "text",
        lines: list[str] | None = None,
        margin_bottom: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._block_type = block_type
        self._block_lines = lines or []
        self._block_content = "\n".join(self._block_lines)
        self._margin_bottom_val = margin_bottom

        # Table-specific properties (for API compatibility)
        self._table_content: list[list[list[dict[str, str]]]] | None = None
        self._column_width_mode = "full"
        self._column_fitter = "proportional"
        self._wrap_mode_str = "word"
        self._cell_padding = 0
        self._show_borders = True
        self._border_val = True
        self._outer_border = True
        self._selectable_val = True

        self._setup_measure_func()

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            import yoga

            lines = self._block_lines
            num_lines = len(lines) + self._margin_bottom_val

            if self._block_type == "table" and self._column_width_mode == "full":
                if width_mode in (yoga.MeasureMode.AtMost, yoga.MeasureMode.Exactly):
                    measured_w = int(width)
                else:
                    measured_w = max((_display_width(ln) for ln in lines), default=1)
                return (measured_w, max(num_lines, 1))

            max_w = max((_display_width(ln) for ln in lines), default=1)

            measured_w = min(int(width), max_w) if width_mode == yoga.MeasureMode.AtMost else max_w

            return (measured_w, max(num_lines, 1))

        self._yoga_node.set_measure_func(measure)

    @property
    def margin_bottom(self) -> int:
        return self._margin_bottom_val

    @margin_bottom.setter
    def margin_bottom(self, value: int) -> None:
        if self._margin_bottom_val != value:
            self._margin_bottom_val = value
            self.mark_dirty()
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()

    # Table-specific properties for API compatibility
    @property
    def content(self) -> list[list[list[dict[str, str]]]] | None:
        return self._table_content

    @content.setter
    def content(self, value: list[list[list[dict[str, str]]]] | None) -> None:
        self._table_content = value

    @property
    def column_width_mode(self) -> str:
        return self._column_width_mode

    @column_width_mode.setter
    def column_width_mode(self, value: str) -> None:
        self._column_width_mode = value

    @property
    def column_fitter(self) -> str:
        return self._column_fitter

    @column_fitter.setter
    def column_fitter(self, value: str) -> None:
        self._column_fitter = value

    @property
    def wrap_mode(self) -> str:
        return self._wrap_mode_str

    @wrap_mode.setter
    def wrap_mode(self, value: str) -> None:
        self._wrap_mode_str = value

    @property
    def cell_padding(self) -> int:
        return self._cell_padding

    @cell_padding.setter
    def cell_padding(self, value: int) -> None:
        self._cell_padding = value

    @property
    def show_borders(self) -> bool:
        return self._show_borders

    @show_borders.setter
    def show_borders(self, value: bool) -> None:
        self._show_borders = value

    @property
    def selectable(self) -> bool:
        return self._selectable_val

    @selectable.setter
    def selectable(self, value: bool) -> None:
        self._selectable_val = value

    def update_lines(self, lines: list[str], margin_bottom: int | None = None) -> None:
        self._block_lines = lines
        self._block_content = "\n".join(lines)
        if margin_bottom is not None:
            self._margin_bottom_val = margin_bottom
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.mark_dirty()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._block_lines:
            return

        x = self._x
        y = self._y
        avail_w = self._layout_width or buffer.width

        if self._block_type == "table" and self._column_width_mode == "full":
            self._render_full_width_table(buffer, x, y, avail_w)
        else:
            for i, line in enumerate(self._block_lines):
                if y + i >= buffer.height:
                    break
                buffer.draw_text(line, x, y + i)

    def _render_full_width_table(self, buffer: Buffer, x: int, y: int, avail_w: int) -> None:
        for i, line in enumerate(self._block_lines):
            if y + i >= buffer.height:
                break
            buffer.draw_text(line, x, y + i)


class _MarkdownTableBlock(_MarkdownBlockRenderable):
    """A table renderable used internally by MarkdownRenderable."""

    @property
    def border(self) -> bool:
        return self._border_val

    @border.setter
    def border(self, value: bool) -> None:
        self._border_val = value

    @property
    def outer_border(self) -> bool:
        return self._outer_border

    @outer_border.setter
    def outer_border(self, value: bool) -> None:
        self._outer_border = value

    @property
    def border_style(self) -> str:
        return "single"

    @border_style.setter
    def border_style(self, value: str) -> None:
        pass

    @property
    def border_color(self) -> str:
        return "#888888"

    @border_color.setter
    def border_color(self, value: str) -> None:
        pass


class _MarkdownCodeBlock(Renderable):
    """Markdown code block backed by a real TextRenderable."""

    __slots__ = (
        "_filetype",
        "_is_highlighting",
        "_block_type",
        "_block_lines",
        "_block_content",
        "_margin_bottom_val",
        "_text_child",
        "_spacer",
    )

    def __init__(
        self,
        *,
        filetype: str = "",
        block_type: str = "text",
        lines: list[str] | None = None,
        margin_bottom: int = 0,
        **kwargs,
    ):
        super().__init__(flex_direction="column", **kwargs)
        self._filetype = filetype
        self._is_highlighting = False
        self._block_type = block_type
        self._block_lines = lines or []
        self._block_content = "\n".join(self._block_lines)
        self._margin_bottom_val = margin_bottom
        self._text_child = NativeTextRenderable(
            content=self._block_content,
            wrap_mode="none",
            selectable=False,
            width="100%",
        )
        self._spacer = Renderable(height=margin_bottom, flex_grow=0, flex_shrink=0)
        super().add(self._text_child)
        super().add(self._spacer)

    @property
    def filetype(self) -> str:
        return self._filetype

    @filetype.setter
    def filetype(self, value: str) -> None:
        self._filetype = value

    @property
    def is_highlighting(self) -> bool:
        return self._is_highlighting

    @property
    def margin_bottom(self) -> int:
        return self._margin_bottom_val

    @margin_bottom.setter
    def margin_bottom(self, value: int) -> None:
        if self._margin_bottom_val != value:
            self._margin_bottom_val = value
            self._spacer.height = value
            self.mark_dirty()

    def update_lines(self, lines: list[str], margin_bottom: int | None = None) -> None:
        self._block_lines = lines
        self._block_content = "\n".join(lines)
        self._text_child.content = self._block_content
        if margin_bottom is not None:
            self.margin_bottom = margin_bottom
        else:
            self.mark_dirty()


class _ExternalBlockRenderable(_MarkdownBlockRenderable):
    """Wraps an external renderable returned by a custom renderNode callback."""

    def __init__(self, *, child: Renderable, **kwargs):
        super().__init__(**kwargs)
        self._external_child = child
        self.add(child)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return
        for child in self._children:
            child.render(buffer, delta_time)
