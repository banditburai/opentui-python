"""MarkdownRenderable - renders parsed markdown as terminal output."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..enums import RenderStrategy
from ..markdown_parser import MarkedToken, ParseState, parse_markdown_incremental
from ..structs import display_width as _display_width
from .base import Renderable
from .text_renderable import TextRenderable as NativeTextRenderable

if TYPE_CHECKING:
    from ..renderer import Buffer


_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_RE_CODE = re.compile(r"`(.*?)`")
_RE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_RE_INCOMPLETE_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)$")


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

    # Handle escaped pipes
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
        ┌─────┬───┐
        │Name │Age│
        ├─────┼───┤
        │Alice│30 │
        └─────┴───┘
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

    top = "┌" + "┬".join("─" * w for w in col_widths) + "┐"
    lines.append(top)

    header_line = "│"
    for i, text in enumerate(header_texts):
        w = col_widths[i]
        dw = _display_width(text)
        padding = w - dw
        header_line += text + " " * padding + "│"
    lines.append(header_line)

    for row_cells in row_texts:
        sep = "├" + "┼".join("─" * w for w in col_widths) + "┤"
        lines.append(sep)

        row_line = "│"
        for i in range(num_cols):
            w = col_widths[i]
            text = row_cells[i] if i < len(row_cells) else ""
            dw = _display_width(text)
            padding = w - dw
            row_line += text + " " * padding + "│"
        lines.append(row_line)

    bottom = "└" + "┴".join("─" * w for w in col_widths) + "┘"
    lines.append(bottom)

    return lines


@dataclass
class BlockState:
    token: MarkedToken
    token_raw: str
    renderable: Renderable
    table_content_cache: Any = None


@dataclass
class TableContentCache:
    # content is list of rows, each row is list of cells, each cell is list of chunks
    content: list[list[list[dict[str, str]]]]
    cell_keys: list[list[int]]


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


class TextTableRenderable(_MarkdownBlockRenderable):
    """A table renderable - subclass for isinstance checks in tests."""

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


class CodeRenderable(Renderable):
    """Markdown block wrapper backed by a real TextRenderable."""

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


class RenderNodeContext:
    def __init__(
        self,
        syntax_style: Any,
        conceal: bool,
        conceal_code: bool,
        tree_sitter_client: Any,
        default_render: Callable,
    ):
        self.syntax_style = syntax_style
        self.conceal = conceal
        self.conceal_code = conceal_code
        self.tree_sitter_client = tree_sitter_client
        self.default_render = default_render


@dataclass
class MarkdownTableOptions:
    width_mode: str = "full"
    column_fitter: str = "proportional"
    wrap_mode: str = "word"
    cell_padding: int = 0
    borders: bool = True
    outer_border: bool | None = None
    border_style: str = "single"
    border_color: str = "#888888"
    selectable: bool = True


class MarkdownRenderable(Renderable):
    """Renders markdown content as terminal output.

    Parses markdown incrementally, creating child renderables for each
    block: tables become TextTableRenderable, code blocks become
    CodeRenderable, and text blocks become CodeRenderable with filetype="markdown".

    Supports concealment of inline formatting markers, streaming mode
    for incremental content updates, and custom render node callbacks.
    """

    def __init__(
        self,
        *,
        content: str = "",
        syntax_style: Any = None,
        conceal: bool = True,
        conceal_code: bool = False,
        tree_sitter_client: Any = None,
        streaming: bool = False,
        table_options: dict | MarkdownTableOptions | None = None,
        render_node: Callable | None = None,
        **kwargs,
    ):
        super().__init__(flex_direction="column", **kwargs)

        self._content = content
        self._syntax_style = syntax_style
        self._conceal = conceal
        self._conceal_code = conceal_code
        self._tree_sitter_client = tree_sitter_client
        self._streaming = streaming
        self._render_node = render_node
        self._style_dirty = False

        if isinstance(table_options, dict):
            self._table_options = MarkdownTableOptions(
                width_mode=table_options.get("widthMode", table_options.get("width_mode", "full")),
                column_fitter=table_options.get(
                    "columnFitter", table_options.get("column_fitter", "proportional")
                ),
                wrap_mode=table_options.get("wrapMode", table_options.get("wrap_mode", "word")),
                cell_padding=table_options.get("cellPadding", table_options.get("cell_padding", 0)),
                borders=table_options.get("borders", True),
                selectable=table_options.get("selectable", True),
            )
        elif isinstance(table_options, MarkdownTableOptions):
            self._table_options = table_options
        else:
            self._table_options = MarkdownTableOptions()

        self._parse_state: ParseState | None = None
        self._block_states: list[BlockState] = []

        self._update_blocks()

    def get_render_strategy(self) -> RenderStrategy:
        return RenderStrategy.HEAVY_WIDGET

    # -- Public properties --

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        if self.is_destroyed:
            return
        if self._content != value:
            self._content = value
            self._update_blocks()
            self.mark_dirty()

    @property
    def syntax_style(self) -> Any:
        return self._syntax_style

    @syntax_style.setter
    def syntax_style(self, value: Any) -> None:
        if self._syntax_style is not value:
            self._syntax_style = value
            self._style_dirty = True
            self.mark_paint_dirty()

    @property
    def conceal(self) -> bool:
        return self._conceal

    @conceal.setter
    def conceal(self, value: bool) -> None:
        if self._conceal != value:
            self._conceal = value
            self._style_dirty = True
            self.mark_paint_dirty()

    @property
    def conceal_code(self) -> bool:
        return self._conceal_code

    @conceal_code.setter
    def conceal_code(self, value: bool) -> None:
        if self._conceal_code != value:
            self._conceal_code = value
            self._style_dirty = True
            self.mark_paint_dirty()

    @property
    def streaming(self) -> bool:
        return self._streaming

    @streaming.setter
    def streaming(self, value: bool) -> None:
        if self.is_destroyed:
            return
        if self._streaming != value:
            self._streaming = value
            self._update_blocks(force_table_refresh=True)

    @property
    def table_options(self) -> MarkdownTableOptions:
        return self._table_options

    @table_options.setter
    def table_options(self, value: dict | MarkdownTableOptions) -> None:
        if isinstance(value, dict):
            self._table_options = MarkdownTableOptions(
                width_mode=value.get("widthMode", value.get("width_mode", "full")),
                column_fitter=value.get("columnFitter", value.get("column_fitter", "proportional")),
                wrap_mode=value.get("wrapMode", value.get("wrap_mode", "word")),
                cell_padding=value.get("cellPadding", value.get("cell_padding", 0)),
                borders=value.get("borders", True),
                selectable=value.get("selectable", True),
            )
        else:
            self._table_options = value
        self._apply_table_options_to_blocks()

    # Internal state accessors for tests
    @property
    def _blockStates(self) -> list[BlockState]:
        """Alias for tests that access _blockStates."""
        return self._block_states

    @property
    def _parseState(self) -> ParseState | None:
        """Alias for tests that access _parseState."""
        return self._parse_state

    # -- Public methods --

    def clear_cache(self) -> None:
        self._parse_state = None
        self._clear_block_states()
        self._update_blocks()
        self.mark_dirty()

    # -- Private methods --

    def _should_render_separately(self, token: MarkedToken) -> bool:
        return token.type in ("code", "table", "blockquote")

    def _get_inter_block_margin(self, token: MarkedToken, has_next: bool) -> int:
        if not has_next:
            return 0
        return 1 if self._should_render_separately(token) else 0

    def _build_renderable_tokens(self, tokens: list[MarkedToken]) -> list[MarkedToken]:
        """Group tokens into renderable blocks.

        When no custom renderNode is set, non-separately-rendered tokens
        (headings, paragraphs, lists, hr) are merged into single markdown
        text blocks. Spacing tokens between them are absorbed.
        """
        if self._render_node:
            return [t for t in tokens if t.type != "space"]

        render_tokens: list[MarkedToken] = []
        markdown_raw = ""

        def flush():
            nonlocal markdown_raw
            if not markdown_raw:
                return
            # Normalize trailing double-newlines
            normalized = re.sub(r"(?:\r?\n){2,}$", "\n", markdown_raw)
            if normalized:
                render_tokens.append(
                    MarkedToken(
                        type="paragraph",
                        raw=normalized,
                        text=normalized,
                    )
                )
            markdown_raw = ""

        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.type == "space":
                if not markdown_raw:
                    i += 1
                    continue

                # Look ahead past consecutive spaces
                next_idx = i + 1
                while next_idx < len(tokens) and tokens[next_idx].type == "space":
                    next_idx += 1

                next_token = tokens[next_idx] if next_idx < len(tokens) else None
                if next_token and not self._should_render_separately(next_token):
                    markdown_raw += token.raw
                i += 1
                continue

            if self._should_render_separately(token):
                flush()
                render_tokens.append(token)
                i += 1
                continue

            markdown_raw += token.raw
            i += 1

        flush()
        return render_tokens

    def _render_token_lines(
        self, token: MarkedToken, margin_bottom: int = 0
    ) -> tuple[str, list[str]]:
        if token.type == "table":
            if token.rows:
                table_lines = _render_table(token.header, token.rows, self._conceal)
                return "table", table_lines
            else:
                return "text", token.raw.rstrip("\n").split("\n")

        if token.type == "code":
            code_text = token.text
            if code_text.endswith("\n"):
                code_text = code_text[:-1]
            return "code", code_text.split("\n") if code_text else []

        if token.type == "blockquote":
            lines = token.raw.rstrip("\n").split("\n")
            return "text", lines

        raw = token.raw.rstrip("\n")
        if not raw:
            return "text", []

        lines = raw.split("\n")
        return "text", [self._process_text_line(line) for line in lines]

    def _process_text_line(self, line: str) -> str:
        if self._conceal:
            # Heading concealment: remove "# " prefix
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if heading_match:
                return _strip_inline_formatting(heading_match.group(2), True)

            # Strip inline formatting
            return _strip_inline_formatting(line, True)
        return line

    def _create_table_renderable(
        self,
        token: MarkedToken,
        block_id: str,
        margin_bottom: int = 0,
    ) -> TextTableRenderable:
        table_lines = _render_table(token.header, token.rows, self._conceal)

        num_cols = len(token.header)
        table_content: list[list[list[dict[str, str]]]] = []

        header_row: list[list[dict[str, str]]] = []
        for h in token.header:
            text = _strip_table_cell(h.get("text", ""), self._conceal)
            header_row.append([{"text": text}])
        table_content.append(header_row)

        for row in token.rows:
            data_row: list[list[dict[str, str]]] = []
            for i in range(num_cols):
                if i < len(row):
                    text = _strip_table_cell(row[i].get("text", ""), self._conceal)
                    data_row.append([{"text": text}])
                else:
                    data_row.append([{"text": ""}])
            table_content.append(data_row)

        renderable = TextTableRenderable(
            id=block_id,
            block_type="table",
            lines=table_lines,
            margin_bottom=margin_bottom,
        )
        renderable.content = table_content
        renderable.column_width_mode = self._table_options.width_mode
        renderable.column_fitter = self._table_options.column_fitter
        renderable.wrap_mode = self._table_options.wrap_mode
        renderable.cell_padding = self._table_options.cell_padding
        renderable.show_borders = self._table_options.borders
        renderable._border_val = self._table_options.borders
        renderable._outer_border = (
            self._table_options.outer_border
            if self._table_options.outer_border is not None
            else self._table_options.borders
        )
        renderable.selectable = self._table_options.selectable

        return renderable

    def _create_code_renderable(
        self,
        token: MarkedToken,
        block_id: str,
        margin_bottom: int = 0,
    ) -> CodeRenderable:
        code_text = token.text
        if code_text.endswith("\n"):
            code_text = code_text[:-1]
        lines = code_text.split("\n") if code_text else []

        return CodeRenderable(
            id=block_id,
            block_type="code",
            lines=lines,
            margin_bottom=margin_bottom,
            filetype=token.lang or "",
        )

    def _create_markdown_text_renderable(
        self,
        raw: str,
        block_id: str,
        margin_bottom: int = 0,
    ) -> CodeRenderable:
        raw_stripped = raw.rstrip("\n")
        if not raw_stripped:
            return CodeRenderable(
                id=block_id,
                block_type="text",
                lines=[],
                margin_bottom=margin_bottom,
                filetype="markdown",
            )

        lines = raw_stripped.split("\n")
        processed_lines = [self._process_text_line(line) for line in lines]

        return CodeRenderable(
            id=block_id,
            block_type="text",
            lines=processed_lines,
            margin_bottom=margin_bottom,
            filetype="markdown",
        )

    def _update_table_renderable(
        self,
        renderable: TextTableRenderable,
        token: MarkedToken,
        margin_bottom: int = 0,
    ) -> None:
        """Update an existing table renderable with new token data.

        Reuses cell chunk list objects when their content hasn't changed,
        so that identity-based stability checks pass (``cell is old_cell``).
        """
        table_lines = _render_table(token.header, token.rows, self._conceal)

        old_content = renderable.content if renderable.content else []

        num_cols = len(token.header)
        table_content: list[list[list[dict[str, str]]]] = []

        header_row: list[list[dict[str, str]]] = []
        for col_idx, h in enumerate(token.header):
            text = _strip_table_cell(h.get("text", ""), self._conceal)
            new_chunk = [{"text": text}]
            if (
                len(old_content) > 0
                and col_idx < len(old_content[0])
                and old_content[0][col_idx] == new_chunk
            ):
                header_row.append(old_content[0][col_idx])
            else:
                header_row.append(new_chunk)
        table_content.append(header_row)

        for row_idx, row in enumerate(token.rows):
            data_row: list[list[dict[str, str]]] = []
            old_row_idx = row_idx + 1  # +1 for header
            for i in range(num_cols):
                if i < len(row):
                    text = _strip_table_cell(row[i].get("text", ""), self._conceal)
                    new_chunk = [{"text": text}]
                else:
                    new_chunk = [{"text": ""}]
                if (
                    old_row_idx < len(old_content)
                    and i < len(old_content[old_row_idx])
                    and old_content[old_row_idx][i] == new_chunk
                ):
                    data_row.append(old_content[old_row_idx][i])
                else:
                    data_row.append(new_chunk)
            table_content.append(data_row)

        renderable.content = table_content
        renderable.update_lines(table_lines, margin_bottom)
        renderable.column_width_mode = self._table_options.width_mode
        renderable.column_fitter = self._table_options.column_fitter

    def _apply_table_options_to_blocks(self) -> None:
        for state in self._block_states:
            if isinstance(state.renderable, TextTableRenderable):
                state.renderable.column_width_mode = self._table_options.width_mode
                state.renderable.column_fitter = self._table_options.column_fitter
                state.renderable.wrap_mode = self._table_options.wrap_mode
                state.renderable.cell_padding = self._table_options.cell_padding
                state.renderable._border_val = self._table_options.borders
                state.renderable._outer_border = (
                    self._table_options.outer_border
                    if self._table_options.outer_border is not None
                    else self._table_options.borders
                )
                state.renderable.show_borders = self._table_options.borders
                state.renderable.selectable = self._table_options.selectable
        self.mark_dirty()

    def _clear_block_states(self) -> None:
        for state in self._block_states:
            state.renderable.destroy_recursively()
        self._block_states = []

    def _update_blocks(self, force_table_refresh: bool = False) -> None:
        if self.is_destroyed:
            return

        if not self._content:
            self._clear_block_states()
            self._parse_state = None
            return

        trailing_unstable = 2 if self._streaming else 0
        self._parse_state = parse_markdown_incremental(
            self._content, self._parse_state, trailing_unstable
        )

        tokens = self._parse_state.tokens
        if not tokens and self._content:
            # Parse failure - fallback
            self._clear_block_states()
            fallback = self._create_markdown_text_renderable(self._content, f"{self._id}-fallback")
            self.add(fallback)
            self._block_states = [
                BlockState(
                    token=MarkedToken(type="text", raw=self._content, text=self._content),
                    token_raw=self._content,
                    renderable=fallback,
                )
            ]
            return

        block_tokens = self._build_renderable_tokens(tokens)
        last_block_index = len(block_tokens) - 1

        block_index = 0
        for i, token in enumerate(block_tokens):
            has_next = i < last_block_index
            existing = (
                self._block_states[block_index] if block_index < len(self._block_states) else None
            )

            # Same token object reference = unchanged
            if existing and existing.token is token:
                if force_table_refresh:
                    self._update_existing_block(existing, token, block_index, has_next)
                block_index += 1
                continue

            # Same raw content and type
            if existing and existing.token_raw == token.raw and existing.token.type == token.type:
                existing.token = token
                if force_table_refresh:
                    self._update_existing_block(existing, token, block_index, has_next)
                block_index += 1
                continue

            # Same type, different content - update in place
            if existing and existing.token.type == token.type:
                self._update_existing_block(existing, token, block_index, has_next)
                existing.token = token
                existing.token_raw = token.raw
                block_index += 1
                continue

            # Different type or new block
            if existing:
                existing.renderable.destroy_recursively()

            renderable = self._create_block_renderable(token, block_index, has_next)
            if renderable:
                self.add(renderable)

                if block_index < len(self._block_states):
                    self._block_states[block_index] = BlockState(
                        token=token,
                        token_raw=token.raw,
                        renderable=renderable,
                    )
                else:
                    self._block_states.append(
                        BlockState(
                            token=token,
                            token_raw=token.raw,
                            renderable=renderable,
                        )
                    )
            block_index += 1

        # Remove excess blocks
        while len(self._block_states) > block_index:
            removed = self._block_states.pop()
            removed.renderable.destroy_recursively()

    def _create_block_renderable(
        self,
        token: MarkedToken,
        index: int,
        has_next: bool,
    ) -> Renderable | None:
        block_id = f"{self._id}-block-{index}"
        margin_bottom = self._get_inter_block_margin(token, has_next)

        # Custom renderNode
        if self._render_node:
            ctx = RenderNodeContext(
                syntax_style=self._syntax_style,
                conceal=self._conceal,
                conceal_code=self._conceal_code,
                tree_sitter_client=self._tree_sitter_client,
                default_render=lambda: self._create_default_renderable(token, index, has_next),
            )
            custom = self._render_node(token, ctx)
            if custom is not None:
                # Custom renderable - wrap if not our type
                if isinstance(custom, _MarkdownBlockRenderable | CodeRenderable):
                    return custom
                # For external renderables, wrap in a block
                return _ExternalBlockRenderable(
                    child=custom,
                    id=block_id,
                    margin_bottom=margin_bottom,
                )

        return self._create_default_renderable(token, index, has_next)

    def _create_default_renderable(
        self,
        token: MarkedToken,
        index: int,
        has_next: bool,
    ) -> Renderable | None:
        block_id = f"{self._id}-block-{index}"
        margin_bottom = self._get_inter_block_margin(token, has_next)

        if token.type == "table":
            if token.rows:
                return self._create_table_renderable(token, block_id, margin_bottom)
            else:
                # Table with no data rows - show raw
                return self._create_markdown_text_renderable(token.raw, block_id, margin_bottom)

        if token.type == "code":
            return self._create_code_renderable(token, block_id, margin_bottom)

        if token.type == "space":
            return None

        if not token.raw:
            return None

        return self._create_markdown_text_renderable(token.raw, block_id, margin_bottom)

    def _update_existing_block(
        self,
        state: BlockState,
        token: MarkedToken,
        index: int,
        has_next: bool,
    ) -> None:
        margin_bottom = self._get_inter_block_margin(token, has_next)

        if (
            token.type == "table"
            and isinstance(state.renderable, TextTableRenderable)
            and token.rows
        ):
            self._update_table_renderable(state.renderable, token, margin_bottom)
            return

        # Re-render the token lines
        block_type, lines = self._render_token_lines(token, margin_bottom)
        state.renderable.update_lines(lines, margin_bottom)

    def _rerender_blocks(self) -> None:
        for i, state in enumerate(self._block_states):
            has_next = i < len(self._block_states) - 1
            token = state.token
            margin_bottom = self._get_inter_block_margin(token, has_next)

            if (
                token.type == "table"
                and isinstance(state.renderable, TextTableRenderable)
                and token.rows
            ):
                self._update_table_renderable(state.renderable, token, margin_bottom)
                continue

            if token.type == "code":
                # Code blocks don't change with conceal (unless concealCode)
                state.renderable.margin_bottom = margin_bottom
                continue

            # Re-process text lines with new conceal settings
            block_type, lines = self._render_token_lines(token, margin_bottom)
            state.renderable.update_lines(lines, margin_bottom)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if self._style_dirty:
            self._style_dirty = False
            self._rerender_blocks()

        super().render(buffer, delta_time)


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
