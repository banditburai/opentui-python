"""Code viewer — read-only source display with line numbers."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from ..themes import get_theme


def line_number_gutter(*, total_lines: int, **kwargs: Any) -> Box:
    """Render a column of line numbers."""
    t = get_theme()
    width = len(str(total_lines)) if total_lines else 1
    children: list[Text] = []
    for i in range(1, total_lines + 1):
        children.append(Text(str(i).rjust(width), fg=t.diff_line_number))
    return Box(
        *children,
        flex_direction="column",
        padding_right=1,
        **kwargs,
    )


def code_viewer(
    *,
    source: str,
    filename: str = "",
    show_line_numbers: bool = True,
    **kwargs: Any,
) -> Box:
    """Render a read-only code viewer with optional line numbers and filename header."""
    t = get_theme()
    lines = source.split("\n") if source else []

    parts: list[Box | Text] = []

    # Optional filename header
    if filename:
        parts.append(
            Text(filename, bold=True, fg=t.text)
        )

    # Code body: gutter + source lines
    code_children: list[Text] = [Text(line, fg=t.markdown_code_block) for line in lines]
    code_col = Box(*code_children, flex_direction="column")

    if show_line_numbers and lines:
        gutter = line_number_gutter(total_lines=len(lines))
        body = Box(gutter, code_col, flex_direction="row")
    else:
        body = code_col

    parts.append(body)

    return Box(
        *parts,
        flex_direction="column",
        background_color=t.background_element,
        padding_left=1,
        padding_right=1,
        border=True,
        border_style="round",
        border_color=t.border,
        **kwargs,
    )
