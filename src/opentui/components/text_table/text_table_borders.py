"""Table border drawing utilities extracted from TextTableRenderable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ... import structs as s

if TYPE_CHECKING:
    from ...renderer import Buffer

_BORDER_CHARS = {
    "single": {
        "h": "\u2500",  # ─
        "v": "\u2502",  # │
        "tl": "\u250c",  # ┌
        "tr": "\u2510",  # ┐
        "bl": "\u2514",  # └
        "br": "\u2518",  # ┘
        "t_down": "\u252c",  # ┬
        "t_up": "\u2534",  # ┴
        "t_right": "\u251c",  # ├
        "t_left": "\u2524",  # ┤
        "cross": "\u253c",  # ┼
    },
    "double": {
        "h": "\u2550",  # ═
        "v": "\u2551",  # ║
        "tl": "\u2554",  # ╔
        "tr": "\u2557",  # ╗
        "bl": "\u255a",  # ╚
        "br": "\u255d",  # ╝
        "t_down": "\u2566",  # ╦
        "t_up": "\u2569",  # ╩
        "t_right": "\u2560",  # ╠
        "t_left": "\u2563",  # ╣
        "cross": "\u256c",  # ╬
    },
    "round": {
        "h": "\u2500",  # ─
        "v": "\u2502",  # │
        "tl": "\u256d",  # ╭
        "tr": "\u256e",  # ╮
        "bl": "\u2570",  # ╰
        "br": "\u256f",  # ╯
        "t_down": "\u252c",  # ┬
        "t_up": "\u2534",  # ┴
        "t_right": "\u251c",  # ├
        "t_left": "\u2524",  # ┤
        "cross": "\u253c",  # ┼
    },
}


class _BorderLayout:
    __slots__ = ("left", "right", "top", "bottom", "inner_vertical", "inner_horizontal")

    def __init__(
        self,
        left: bool,
        right: bool,
        top: bool,
        bottom: bool,
        inner_vertical: bool,
        inner_horizontal: bool,
    ):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom
        self.inner_vertical = inner_vertical
        self.inner_horizontal = inner_horizontal


def resolve_border_layout(
    outer: bool, table_border: bool, n_cols: int, n_rows: int
) -> _BorderLayout:
    return _BorderLayout(
        left=outer,
        right=outer,
        top=outer,
        bottom=outer,
        inner_vertical=table_border and n_cols > 1,
        inner_horizontal=table_border and n_rows > 1,
    )


def get_vertical_border_count(layout: _BorderLayout, n_cols: int) -> int:
    count = 0
    if layout.left:
        count += 1
    if layout.right:
        count += 1
    if layout.inner_vertical:
        count += max(0, n_cols - 1)
    return count


def get_horizontal_border_count(layout: _BorderLayout, n_rows: int) -> int:
    count = 0
    if layout.top:
        count += 1
    if layout.bottom:
        count += 1
    if layout.inner_horizontal:
        count += max(0, n_rows - 1)
    return count


def get_intersection_char(
    chars: dict, is_top: bool, is_bottom: bool, is_left: bool, is_right: bool
) -> str:
    if is_top and is_left:
        return chars["tl"]
    if is_top and is_right:
        return chars["tr"]
    if is_bottom and is_left:
        return chars["bl"]
    if is_bottom and is_right:
        return chars["br"]
    if is_top:
        return chars["t_down"]
    if is_bottom:
        return chars["t_up"]
    if is_left:
        return chars["t_right"]
    if is_right:
        return chars["t_left"]
    return chars["cross"]


def draw_borders(
    buffer: Buffer,
    base_x: int,
    base_y: int,
    style: str,
    fg: s.RGBA,
    bg: s.RGBA | None,
    border_layout: _BorderLayout,
    table_layout: object,
    n_cols: int,
    n_rows: int,
) -> None:
    """Draw grid borders using Python fallback (when native grid primitive unavailable)."""
    chars = _BORDER_CHARS.get(style, _BORDER_CHARS["single"])

    col_offsets = table_layout.column_offsets
    row_offsets = table_layout.row_offsets
    col_widths = table_layout.column_widths
    row_heights = table_layout.row_heights

    for border_idx in range(n_rows + 1):
        if border_idx == 0:
            if not border_layout.top:
                continue
        elif border_idx == n_rows:
            if not border_layout.bottom:
                continue
        elif not border_layout.inner_horizontal:
            continue

        if border_idx < len(row_offsets):
            by = row_offsets[border_idx]
        elif (
            border_idx > 0
            and border_idx - 1 < len(row_offsets)
            and border_idx - 1 < len(row_heights)
        ):
            by = row_offsets[border_idx - 1] + 1 + row_heights[border_idx - 1]
        else:
            continue

        if by < 0:
            continue

        abs_by = base_y + by

        for col_border_idx in range(n_cols + 1):
            if col_border_idx == 0:
                draw_vertical = border_layout.left
            elif col_border_idx == n_cols:
                draw_vertical = border_layout.right
            else:
                draw_vertical = border_layout.inner_vertical

            if draw_vertical:
                if col_border_idx < len(col_offsets):
                    bx = col_offsets[col_border_idx]
                elif (
                    col_border_idx > 0
                    and col_border_idx - 1 < len(col_offsets)
                    and col_border_idx - 1 < len(col_widths)
                ):
                    bx = col_offsets[col_border_idx - 1] + 1 + col_widths[col_border_idx - 1]
                else:
                    continue

                if bx < 0:
                    continue

                abs_bx = base_x + bx

                is_top = border_idx == 0
                is_bottom = border_idx == n_rows
                is_left = col_border_idx == 0
                is_right = col_border_idx == n_cols

                ch = get_intersection_char(chars, is_top, is_bottom, is_left, is_right)
                buffer.draw_text(ch, abs_bx, abs_by, fg, bg)

            if col_border_idx < n_cols:
                if col_border_idx < len(col_offsets):
                    seg_start = col_offsets[col_border_idx] + 1
                else:
                    continue
                seg_width = col_widths[col_border_idx] if col_border_idx < len(col_widths) else 1
                for sx in range(seg_width):
                    buffer.draw_text(chars["h"], base_x + seg_start + sx, abs_by, fg, bg)

    for row_idx in range(n_rows):
        if row_idx >= len(row_offsets) or row_idx >= len(row_heights):
            continue
        cell_y_start = row_offsets[row_idx] + 1
        cell_height = row_heights[row_idx]

        for vy in range(cell_height):
            abs_vy = base_y + cell_y_start + vy

            for col_border_idx in range(n_cols + 1):
                if col_border_idx == 0:
                    if not border_layout.left:
                        continue
                elif col_border_idx == n_cols:
                    if not border_layout.right:
                        continue
                elif not border_layout.inner_vertical:
                    continue

                if col_border_idx < len(col_offsets):
                    vx = col_offsets[col_border_idx]
                elif (
                    col_border_idx > 0
                    and col_border_idx - 1 < len(col_offsets)
                    and col_border_idx - 1 < len(col_widths)
                ):
                    vx = col_offsets[col_border_idx - 1] + 1 + col_widths[col_border_idx - 1]
                else:
                    continue

                if vx < 0:
                    continue

                buffer.draw_text(chars["v"], base_x + vx, abs_vy, fg, bg)
