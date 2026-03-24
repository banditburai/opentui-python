"""Markdown block renderables and helper functions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ...structs import display_width as _display_width
from ..base import Renderable
from ..text_renderable import TextRenderable

if TYPE_CHECKING:
    from ...renderer import Buffer

_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_RE_CODE = re.compile(r"`(.*?)`")
_RE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_RE_INCOMPLETE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)$")


def _strip_inline_formatting(text: str, conceal: bool = True) -> str:
    if not conceal:
        return text

    result = text
    result = _RE_LINK.sub(r"\1 (\2)", result)
    result = _RE_INCOMPLETE_LINK.sub(r"\1(\2", result)
    result = _RE_BOLD.sub(r"\1", result)
    result = _RE_ITALIC.sub(r"\1", result)
    result = _RE_CODE.sub(r"\1", result)
    return result


def _strip_table_cell(text: str, conceal: bool = True) -> str:
    return _strip_inline_formatting(text.strip(), conceal)


def _parse_escaped_cells(row_text: str) -> list[str]:
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
    cell_padding: int = 0,
) -> list[str]:
    if not header:
        return []

    num_cols = len(header)
    pad = " " * cell_padding
    header_texts = [_strip_table_cell(h.get("text", ""), conceal) for h in header]
    row_texts = [
        [
            _strip_table_cell(row[i].get("text", ""), conceal) if i < len(row) else ""
            for i in range(num_cols)
        ]
        for row in rows
    ]

    col_widths = [_display_width(h) for h in header_texts]
    for row_cells in row_texts:
        for i, cell in enumerate(row_cells):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], _display_width(cell))

    col_widths = [max(w, 1) + 2 * cell_padding for w in col_widths]

    lines: list[str] = []
    lines.append("\u250c" + "\u252c".join("\u2500" * w for w in col_widths) + "\u2510")

    header_line = "\u2502"
    for i, text in enumerate(header_texts):
        w = col_widths[i] - 2 * cell_padding
        padding = w - _display_width(text)
        header_line += pad + text + " " * padding + pad + "\u2502"
    lines.append(header_line)

    for row_cells in row_texts:
        lines.append("\u251c" + "\u253c".join("\u2500" * w for w in col_widths) + "\u2524")
        row_line = "\u2502"
        for i in range(num_cols):
            w = col_widths[i] - 2 * cell_padding
            text = row_cells[i] if i < len(row_cells) else ""
            padding = w - _display_width(text)
            row_line += pad + text + " " * padding + pad + "\u2502"
        lines.append(row_line)

    lines.append("\u2514" + "\u2534".join("\u2500" * w for w in col_widths) + "\u2518")
    return lines


@dataclass
class BlockState:
    token: Any
    token_raw: str
    renderable: Renderable


class _MarkdownBlockRenderable(Renderable):
    __slots__ = ("_block_type", "_block_lines", "_block_content")

    def __init__(
        self,
        *,
        block_type: str = "text",
        lines: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._block_type = block_type
        self._block_lines = lines or []
        self._block_content = "\n".join(self._block_lines)

    def update_lines(self, lines: list[str], margin_bottom: int | None = None) -> None:
        self._block_lines = lines
        self._block_content = "\n".join(lines)
        if margin_bottom is not None:
            self.margin_bottom = margin_bottom
        self.mark_dirty()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return
        for child in self._children:
            child.render(buffer, delta_time)


class _MarkdownCodeBlock(TextRenderable):
    __slots__ = ("_filetype", "_is_highlighting", "_block_type", "_block_lines", "_block_content")

    def __init__(
        self,
        *,
        filetype: str = "",
        block_type: str = "text",
        lines: list[str] | None = None,
        margin_bottom: int = 0,
        **kwargs,
    ):
        block_lines = lines or []
        super().__init__(
            wrap_mode="none",
            selectable=True,
            margin_bottom=margin_bottom,
            **kwargs,
        )
        self._filetype = filetype
        self._is_highlighting = False
        self._block_type = block_type
        self._block_lines = block_lines
        self._block_content = "\n".join(block_lines)
        TextRenderable.content.fset(self, self._block_content)

    @property
    def filetype(self) -> str:
        return self._filetype

    @filetype.setter
    def filetype(self, value: str) -> None:
        self._filetype = value

    @property
    def is_highlighting(self) -> bool:
        return self._is_highlighting

    def update_lines(self, lines: list[str], margin_bottom: int | None = None) -> None:
        self._block_lines = lines
        self._block_content = "\n".join(lines)
        TextRenderable.content.fset(self, self._block_content)
        if margin_bottom is not None:
            self.margin_bottom = margin_bottom
        else:
            self.mark_dirty()


class _MarkdownTableBlock(_MarkdownCodeBlock):
    __slots__ = (
        "_table_content",
        "_column_width_mode",
        "_column_fitter",
        "_wrap_mode_str",
        "_cell_padding",
        "_show_borders",
        "_border_val",
        "_outer_border",
    )

    def __init__(
        self,
        *,
        block_type: str = "table",
        lines: list[str] | None = None,
        margin_bottom: int = 0,
        **kwargs,
    ):
        super().__init__(
            block_type=block_type,
            lines=lines,
            margin_bottom=margin_bottom,
            filetype="",
            **kwargs,
        )
        self._table_content: list[list[list[dict[str, str]]]] | None = None
        self._column_width_mode = "full"
        self._column_fitter = "proportional"
        self._wrap_mode_str = "word"
        self._cell_padding = 0
        self._show_borders = True
        self._border_val = True
        self._outer_border = True

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
        # Propagate to the native text buffer view (TextRenderable.wrap_mode
        # setter handles set_wrap_mode + yoga mark_dirty + _update_text_info).
        TextRenderable.wrap_mode.fset(self, value)

    @property
    def cell_padding(self) -> int:
        return self._cell_padding

    @cell_padding.setter
    def cell_padding(self, value: int) -> None:
        self._cell_padding = max(0, int(value))

    @property
    def show_borders(self) -> bool:
        return self._show_borders

    @show_borders.setter
    def show_borders(self, value: bool) -> None:
        self._show_borders = value

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


class _ExternalBlockRenderable(_MarkdownBlockRenderable):
    __slots__ = ("_external_child",)

    def __init__(self, *, child: Renderable, **kwargs):
        super().__init__(**kwargs)
        self._external_child = child
        self.add(child)
