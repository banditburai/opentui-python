"""Markdown block renderables and helper functions."""

import re
from dataclasses import dataclass
from typing import Any

from ... import structs as s
from ...renderer.buffer import Buffer
from ...structs import display_width as _display_width
from ..base import Renderable
from ..text_renderable import TextRenderable

# Box-drawing characters used for table borders
_BOX_CHARS = frozenset("┌┐└┘├┤┬┴┼─│")

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


def _prepare_table_data(
    header: list[dict[str, Any]],
    rows: list[list[dict[str, Any]]],
    conceal: bool,
    cell_padding: int,
) -> tuple[list[str], list[list[str]], list[int], int]:
    """Extract text and compute column widths for table rendering."""
    num_cols = len(header)
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
    return header_texts, row_texts, col_widths, num_cols


def _render_table(
    header: list[dict[str, Any]],
    rows: list[list[dict[str, Any]]],
    conceal: bool = True,
    cell_padding: int = 0,
) -> list[str]:
    if not header:
        return []

    header_texts, row_texts, col_widths, num_cols = _prepare_table_data(
        header, rows, conceal, cell_padding
    )
    pad = " " * cell_padding

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


def _render_table_styled(
    header: list[dict[str, Any]],
    rows: list[list[dict[str, Any]]],
    conceal: bool = True,
    cell_padding: int = 0,
    *,
    border_fg: s.RGBA | None = None,
    header_fg: s.RGBA | None = None,
    header_attributes: int = 0,
) -> list[dict[str, Any]]:
    """Render a table as styled chunks for ``NativeTextBuffer.set_styled_text``.

    Returns a list of chunk dicts (``text``, ``fg``, ``bg``, ``attributes``)
    that produces the same visual layout as :func:`_render_table` but with
    per-chunk styling:

    * **Border characters** get ``border_fg`` (dimmed colour).
    * **Header cell text** gets ``header_fg`` and ``header_attributes`` (bold).
    * **Data cell text** uses default styling (``fg=None``).

    The plain-text concatenation of all chunks is identical to
    ``"\\n".join(_render_table(...))``, preserving sizing / selection offsets.
    """
    if not header:
        return []

    _dim = border_fg  # alias for readability

    header_texts, row_texts, col_widths, num_cols = _prepare_table_data(
        header, rows, conceal, cell_padding
    )
    pad = " " * cell_padding

    chunks: list[dict[str, Any]] = []

    def _border(text: str) -> None:
        chunks.append({"text": text, "fg": _dim, "attributes": 0})

    def _header_cell(text: str) -> None:
        chunks.append({"text": text, "fg": header_fg, "attributes": header_attributes})

    def _data_cell(text: str) -> None:
        chunks.append({"text": text})

    def _nl() -> None:
        chunks.append({"text": "\n"})

    # ── Top border ──
    _border("\u250c" + "\u252c".join("\u2500" * w for w in col_widths) + "\u2510")
    _nl()

    # ── Header row ──
    for i, text in enumerate(header_texts):
        _border("\u2502")
        w = col_widths[i] - 2 * cell_padding
        padding = w - _display_width(text)
        if pad:
            _header_cell(pad)
        _header_cell(text + " " * padding)
        if pad:
            _header_cell(pad)
    _border("\u2502")
    _nl()

    # ── Data rows ──
    for row_cells in row_texts:
        _border("\u251c" + "\u253c".join("\u2500" * w for w in col_widths) + "\u2524")
        _nl()
        for i in range(num_cols):
            _border("\u2502")
            w = col_widths[i] - 2 * cell_padding
            text = row_cells[i] if i < len(row_cells) else ""
            padding = w - _display_width(text)
            if pad:
                _data_cell(pad)
            _data_cell(text + " " * padding)
            if pad:
                _data_cell(pad)
        _border("\u2502")
        _nl()

    # ── Bottom border ──
    _border("\u2514" + "\u2534".join("\u2500" * w for w in col_widths) + "\u2518")

    return chunks


@dataclass
class BlockState:
    token: Any
    token_raw: str
    renderable: Renderable


class _MarkdownBlockWrapper(Renderable):
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


class MarkdownTextBlock(TextRenderable):
    __slots__ = ("_block_type", "_block_lines", "_block_content")

    def __init__(
        self,
        *,
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
        self._block_type = block_type
        self._block_lines = block_lines
        self._block_content = "\n".join(block_lines)
        TextRenderable.content.fset(self, self._block_content)

    def update_lines(self, lines: list[str], margin_bottom: int | None = None) -> None:
        self._block_lines = lines
        self._block_content = "\n".join(lines)
        TextRenderable.content.fset(self, self._block_content)
        if margin_bottom is not None:
            self.margin_bottom = margin_bottom
        else:
            self.mark_dirty()


class MarkdownTableBlock(MarkdownTextBlock):
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

    # ── Styled rendering ──

    def update_styled_lines(
        self,
        styled_chunks: list[dict[str, Any]],
        lines: list[str],
        margin_bottom: int | None = None,
    ) -> None:
        """Set table content using styled chunks for native rendering.

        *styled_chunks* is a list of dicts for
        ``NativeTextBuffer.set_styled_text`` (text/fg/bg/attributes).
        *lines* is the plain-text fallback (same layout, no styling).
        The plain text is kept in ``_block_lines`` / ``_block_content``
        for the Python fallback renderer and for measurement.
        """
        self._block_lines = lines
        self._block_content = "\n".join(lines)
        # Use native styled text if available, fall back to plain text
        try:
            self._text_buffer.set_styled_text(styled_chunks)
        except Exception:
            # Fallback: set plain text (e.g. if Zig FFI unavailable)
            TextRenderable.content.fset(self, self._block_content)
        self._has_manual_styled_text = True
        if margin_bottom is not None:
            self.margin_bottom = margin_bottom
        self._update_text_info()
        self.mark_dirty()

    # ── Clean selection (no border glyphs) ──

    def get_selected_text(self) -> str:
        """Return selected text with border glyphs stripped.

        Uses the stored ``_table_content`` cell data to reconstruct
        clean tab-separated text.  Falls back to stripping box-drawing
        characters from the raw selection if cell data is unavailable.
        """
        from ..text_renderable import _get_selected_text as _base_get_selected_text

        raw = _base_get_selected_text(self)
        if not raw:
            return raw

        # Fast path: use structured cell data if available
        if self._table_content:
            return _extract_clean_table_text(raw, self._table_content)

        # Fallback: strip box-drawing characters from the raw selection
        return _strip_border_chars(raw)


def _strip_border_chars(text: str) -> str:
    """Strip box-drawing border characters and collapse whitespace.

    Processes selected text line-by-line: removes border glyphs,
    replaces each removed glyph with a tab marker, collapses adjacent
    tab markers, and trims leading/trailing whitespace on each line.
    """
    result_lines: list[str] = []
    for line in text.split("\n"):
        # Skip pure-border lines (separator rows like ├───┼───┤)
        stripped = line.strip()
        if stripped and all(ch in _BOX_CHARS or ch == " " for ch in stripped):
            continue
        # Replace vertical border characters with tab markers, remove others
        parts: list[str] = []
        for ch in line:
            if ch == "\u2502":  # │ — column separator
                parts.append("\t")
            elif ch in _BOX_CHARS:
                continue
            else:
                parts.append(ch)
        clean = "".join(parts)
        # Collapse whitespace around tabs, strip leading/trailing tabs + spaces
        clean = re.sub(r"\s*\t\s*", "\t", clean).strip("\t \n")
        if clean:
            result_lines.append(clean)
    return "\n".join(result_lines)


def _extract_clean_table_text(
    raw_selected: str,
    table_content: list[list[list[dict[str, str]]]],
) -> str:
    """Extract clean cell text from structured table content.

    Matches selected raw text against the known cell data to produce
    a clean tab-separated, newline-separated representation.

    The selection may span a subset of rows/columns; we determine which
    cells were selected by checking if their text appears in the raw
    selection.  Falls back to :func:`_strip_border_chars` if matching
    fails.
    """
    if not table_content:
        return _strip_border_chars(raw_selected)

    # Flatten cell text per row for matching
    all_rows: list[list[str]] = []
    for row in table_content:
        cells: list[str] = []
        for cell_chunks in row:
            cell_text = "".join(chunk.get("text", "") for chunk in cell_chunks).strip()
            cells.append(cell_text)
        all_rows.append(cells)

    # Build clean output: include rows whose cell text appears in the raw selection
    selected_rows: list[str] = []
    for row_cells in all_rows:
        # Check if any cell from this row appears in the selected text
        row_selected_cells: list[str] = []
        for cell_text in row_cells:
            if cell_text and cell_text in raw_selected:
                row_selected_cells.append(cell_text)
            elif not cell_text:
                # Empty cells are included if the row has other selected content
                row_selected_cells.append("")
        if any(c for c in row_selected_cells):
            selected_rows.append("\t".join(row_selected_cells))

    if selected_rows:
        return "\n".join(selected_rows)

    # Fallback if structured matching fails
    return _strip_border_chars(raw_selected)


class _ExternalBlockWrapper(_MarkdownBlockWrapper):
    __slots__ = ("_external_child",)

    def __init__(self, *, child: Renderable, **kwargs):
        super().__init__(**kwargs)
        self._external_child = child
        self.add(child)
        if getattr(child, "selectable", False):
            self.selectable = True

    def should_start_selection(self, x: int, y: int) -> bool:
        fn = getattr(self._external_child, "should_start_selection", None)
        return fn(x, y) if fn is not None else getattr(self._external_child, "selectable", False)

    def on_selection_changed(self, selection: object) -> bool:
        fn = getattr(self._external_child, "on_selection_changed", None)
        return fn(selection) if fn is not None else False

    def has_selection(self) -> bool:
        fn = getattr(self._external_child, "has_selection", None)
        return fn() if fn is not None else False

    def get_selected_text(self) -> str:
        fn = getattr(self._external_child, "get_selected_text", None)
        return fn() if fn is not None else ""
