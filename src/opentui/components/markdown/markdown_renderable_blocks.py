from typing import Any

from ... import structs as s
from .markdown_blocks import (
    MarkdownTableBlock,
    MarkdownTextBlock,
    _render_table,
    _render_table_styled,
    _strip_table_cell,
)
from .markdown_parser import MarkedToken
from .markdown_renderable_planning import MarkdownTableOptions, process_text_line

# Default styling for table borders (dim gray) and headers (bold)
_DEFAULT_BORDER_FG = s.RGBA(0.5, 0.5, 0.5, 1.0)
_DEFAULT_HEADER_ATTRIBUTES = s.TEXT_ATTRIBUTE_BOLD


def _build_table_content(
    token: MarkedToken,
    conceal: bool,
    old_content: list[list[list[dict[str, str]]]] | None = None,
) -> list[list[list[dict[str, str]]]]:
    """Build the structured table content (cell data) from a parsed token.

    If *old_content* is provided, unchanged cells reuse the old list objects
    (identity-preserving for downstream diffing).
    """
    num_cols = len(token.header)
    prev = old_content or []
    table_content: list[list[list[dict[str, str]]]] = []

    header_row: list[list[dict[str, str]]] = []
    for col_idx, header_cell in enumerate(token.header):
        text = _strip_table_cell(header_cell.get("text", ""), conceal)
        new_chunk = [{"text": text}]
        if prev and col_idx < len(prev[0]) and prev[0][col_idx] == new_chunk:
            header_row.append(prev[0][col_idx])
        else:
            header_row.append(new_chunk)
    table_content.append(header_row)

    for row_idx, row in enumerate(token.rows):
        data_row: list[list[dict[str, str]]] = []
        old_row_idx = row_idx + 1
        for col_idx in range(num_cols):
            if col_idx < len(row):
                text = _strip_table_cell(row[col_idx].get("text", ""), conceal)
                new_chunk = [{"text": text}]
            else:
                new_chunk = [{"text": ""}]
            if (
                old_row_idx < len(prev)
                and col_idx < len(prev[old_row_idx])
                and prev[old_row_idx][col_idx] == new_chunk
            ):
                data_row.append(prev[old_row_idx][col_idx])
            else:
                data_row.append(new_chunk)
        table_content.append(data_row)

    return table_content


def _build_styled_and_plain(
    token: MarkedToken,
    conceal: bool,
    table_options: MarkdownTableOptions,
    *,
    border_fg: s.RGBA | None = None,
    header_fg: s.RGBA | None = None,
    header_attributes: int = 0,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (styled_chunks, plain_lines) for a table token."""
    cell_padding = table_options.cell_padding
    styled_chunks = _render_table_styled(
        token.header,
        token.rows,
        conceal,
        cell_padding,
        border_fg=border_fg or _DEFAULT_BORDER_FG,
        header_fg=header_fg,
        header_attributes=header_attributes or _DEFAULT_HEADER_ATTRIBUTES,
    )
    plain_lines = _render_table(
        token.header,
        token.rows,
        conceal,
        cell_padding=cell_padding,
    )
    return styled_chunks, plain_lines


def create_table_renderable(
    token: MarkedToken,
    *,
    block_id: str,
    conceal: bool,
    margin_bottom: int,
    table_options: MarkdownTableOptions,
    border_fg: s.RGBA | None = None,
    header_fg: s.RGBA | None = None,
    header_attributes: int = 0,
) -> MarkdownTableBlock:
    table_content = _build_table_content(token, conceal)
    styled_chunks, plain_lines = _build_styled_and_plain(
        token,
        conceal,
        table_options,
        border_fg=border_fg,
        header_fg=header_fg,
        header_attributes=header_attributes,
    )

    # Create with plain lines for initial sizing, then apply styled content
    renderable = MarkdownTableBlock(
        id=block_id,
        block_type="table",
        lines=plain_lines,
        margin_bottom=margin_bottom,
    )
    renderable.content = table_content
    apply_table_options(renderable, table_options)

    # Apply styled text (bold headers, dim borders) via native buffer
    renderable.update_styled_lines(styled_chunks, plain_lines, margin_bottom)
    return renderable


def create_code_renderable(
    token: MarkedToken,
    *,
    block_id: str,
    margin_bottom: int,
) -> MarkdownTextBlock:
    code_text = token.text
    if code_text.endswith("\n"):
        code_text = code_text[:-1]
    lines = code_text.split("\n") if code_text else []

    return MarkdownTextBlock(
        id=block_id,
        block_type="code",
        lines=lines,
        margin_bottom=margin_bottom,
    )


def create_markdown_text_renderable(
    raw: str,
    *,
    block_id: str,
    conceal: bool,
    margin_bottom: int,
) -> MarkdownTextBlock:
    raw_stripped = raw.rstrip("\n")
    if not raw_stripped:
        return MarkdownTextBlock(
            id=block_id,
            block_type="text",
            lines=[],
            margin_bottom=margin_bottom,
        )

    lines = raw_stripped.split("\n")
    processed_lines = [process_text_line(line, conceal=conceal) for line in lines]

    return MarkdownTextBlock(
        id=block_id,
        block_type="text",
        lines=processed_lines,
        margin_bottom=margin_bottom,
    )


def update_table_renderable(
    renderable: MarkdownTableBlock,
    token: MarkedToken,
    *,
    conceal: bool,
    margin_bottom: int,
    table_options: MarkdownTableOptions,
    border_fg: s.RGBA | None = None,
    header_fg: s.RGBA | None = None,
    header_attributes: int = 0,
) -> None:
    old_content = renderable.content if renderable.content else None
    table_content = _build_table_content(token, conceal, old_content)
    renderable.content = table_content

    styled_chunks, plain_lines = _build_styled_and_plain(
        token,
        conceal,
        table_options,
        border_fg=border_fg,
        header_fg=header_fg,
        header_attributes=header_attributes,
    )
    renderable.update_styled_lines(styled_chunks, plain_lines, margin_bottom)
    apply_table_options(renderable, table_options)


def apply_table_options(
    renderable: MarkdownTableBlock,
    table_options: MarkdownTableOptions,
) -> None:
    renderable.column_width_mode = table_options.width_mode
    renderable.column_fitter = table_options.column_fitter
    renderable.wrap_mode = table_options.wrap_mode
    renderable.cell_padding = table_options.cell_padding
    renderable.show_borders = table_options.borders
    renderable.border = table_options.borders
    renderable.outer_border = (
        table_options.outer_border
        if table_options.outer_border is not None
        else table_options.borders
    )
    renderable.selectable = table_options.selectable
