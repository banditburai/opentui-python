from __future__ import annotations

from .markdown_blocks import (
    _MarkdownCodeBlock,
    _MarkdownTableBlock,
    _render_table,
    _strip_table_cell,
)
from .markdown_parser import MarkedToken
from .markdown_renderable_planning import MarkdownTableOptions, process_text_line


def create_table_renderable(
    token: MarkedToken,
    *,
    block_id: str,
    conceal: bool,
    margin_bottom: int,
    table_options: MarkdownTableOptions,
) -> _MarkdownTableBlock:
    table_lines = _render_table(token.header, token.rows, conceal)

    num_cols = len(token.header)
    table_content: list[list[list[dict[str, str]]]] = []

    header_row: list[list[dict[str, str]]] = []
    for header_cell in token.header:
        text = _strip_table_cell(header_cell.get("text", ""), conceal)
        header_row.append([{"text": text}])
    table_content.append(header_row)

    for row in token.rows:
        data_row: list[list[dict[str, str]]] = []
        for column_index in range(num_cols):
            if column_index < len(row):
                text = _strip_table_cell(row[column_index].get("text", ""), conceal)
                data_row.append([{"text": text}])
            else:
                data_row.append([{"text": ""}])
        table_content.append(data_row)

    renderable = _MarkdownTableBlock(
        id=block_id,
        block_type="table",
        lines=table_lines,
        margin_bottom=margin_bottom,
    )
    renderable.content = table_content
    apply_table_options(renderable, table_options)
    return renderable


def create_code_renderable(
    token: MarkedToken,
    *,
    block_id: str,
    margin_bottom: int,
) -> _MarkdownCodeBlock:
    code_text = token.text
    if code_text.endswith("\n"):
        code_text = code_text[:-1]
    lines = code_text.split("\n") if code_text else []

    return _MarkdownCodeBlock(
        id=block_id,
        block_type="code",
        lines=lines,
        margin_bottom=margin_bottom,
        filetype=token.lang or "",
    )


def create_markdown_text_renderable(
    raw: str,
    *,
    block_id: str,
    conceal: bool,
    margin_bottom: int,
) -> _MarkdownCodeBlock:
    raw_stripped = raw.rstrip("\n")
    if not raw_stripped:
        return _MarkdownCodeBlock(
            id=block_id,
            block_type="text",
            lines=[],
            margin_bottom=margin_bottom,
            filetype="markdown",
        )

    lines = raw_stripped.split("\n")
    processed_lines = [process_text_line(line, conceal=conceal) for line in lines]

    return _MarkdownCodeBlock(
        id=block_id,
        block_type="text",
        lines=processed_lines,
        margin_bottom=margin_bottom,
        filetype="markdown",
    )


def update_table_renderable(
    renderable: _MarkdownTableBlock,
    token: MarkedToken,
    *,
    conceal: bool,
    margin_bottom: int,
    table_options: MarkdownTableOptions,
) -> None:
    table_lines = _render_table(token.header, token.rows, conceal)

    old_content = renderable.content if renderable.content else []
    num_cols = len(token.header)
    table_content: list[list[list[dict[str, str]]]] = []

    header_row: list[list[dict[str, str]]] = []
    for column_index, header_cell in enumerate(token.header):
        text = _strip_table_cell(header_cell.get("text", ""), conceal)
        new_chunk = [{"text": text}]
        if (
            old_content
            and column_index < len(old_content[0])
            and old_content[0][column_index] == new_chunk
        ):
            header_row.append(old_content[0][column_index])
        else:
            header_row.append(new_chunk)
    table_content.append(header_row)

    for row_index, row in enumerate(token.rows):
        data_row: list[list[dict[str, str]]] = []
        old_row_index = row_index + 1
        for column_index in range(num_cols):
            if column_index < len(row):
                text = _strip_table_cell(row[column_index].get("text", ""), conceal)
                new_chunk = [{"text": text}]
            else:
                new_chunk = [{"text": ""}]
            if (
                old_row_index < len(old_content)
                and column_index < len(old_content[old_row_index])
                and old_content[old_row_index][column_index] == new_chunk
            ):
                data_row.append(old_content[old_row_index][column_index])
            else:
                data_row.append(new_chunk)
        table_content.append(data_row)

    renderable.content = table_content
    renderable.update_lines(table_lines, margin_bottom)
    apply_table_options(renderable, table_options)


def apply_table_options(
    renderable: _MarkdownTableBlock,
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
