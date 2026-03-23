from __future__ import annotations

from dataclasses import dataclass, field

from .. import structs as s
from ..editor.text_buffer_native import NativeTextBuffer
from ..editor.text_view_native import NativeTextBufferView


@dataclass(frozen=True, slots=True)
class TextTableConfig:
    content: list[list[list[dict] | None]]
    wrap_mode: str
    column_width_mode: str
    column_fitter: str
    cell_padding: int
    show_borders: bool
    table_border: bool
    outer_border: bool
    has_explicit_outer_border: bool
    selectable: bool
    selection_bg_color: s.RGBA | None
    selection_fg_color: s.RGBA | None
    border_style: str
    border_color: s.RGBA
    border_background_color: s.RGBA
    table_background_color: s.RGBA
    default_fg: s.RGBA
    default_bg: s.RGBA
    default_attributes: int


def resolve_text_table_config(
    parse_color,
    resolve_column_fitter,
    resolve_cell_padding,
    *,
    content,
    wrap_mode: str,
    column_width_mode: str,
    column_fitter: str,
    cell_padding: int,
    show_borders: bool,
    border: bool,
    outer_border: bool | None,
    selectable: bool,
    selection_bg,
    selection_fg,
    border_style: str,
    border_color,
    border_background_color,
    background_color,
    fg,
    bg,
    attributes: int,
) -> TextTableConfig:
    return TextTableConfig(
        content=content if content is not None else [],
        wrap_mode=wrap_mode if wrap_mode in ("none", "char", "word") else "word",
        column_width_mode=column_width_mode if column_width_mode in ("content", "full") else "full",
        column_fitter=resolve_column_fitter(column_fitter),
        cell_padding=resolve_cell_padding(cell_padding),
        show_borders=show_borders,
        table_border=border,
        has_explicit_outer_border=outer_border is not None,
        outer_border=outer_border if outer_border is not None else border,
        selectable=selectable,
        selection_bg_color=parse_color(selection_bg),
        selection_fg_color=parse_color(selection_fg),
        border_style=border_style if border_style in ("single", "double", "round") else "single",
        border_color=parse_color(border_color) or s.RGBA(1.0, 1.0, 1.0, 1.0),
        border_background_color=parse_color(border_background_color) or s.RGBA(0.0, 0.0, 0.0, 0.0),
        table_background_color=parse_color(background_color) or s.RGBA(0.0, 0.0, 0.0, 0.0),
        default_fg=parse_color(fg) or s.RGBA(1.0, 1.0, 1.0, 1.0),
        default_bg=parse_color(bg) or s.RGBA(0.0, 0.0, 0.0, 0.0),
        default_attributes=attributes,
    )


@dataclass(slots=True)
class CellState:
    text_buffer: NativeTextBuffer
    text_buffer_view: NativeTextBufferView


@dataclass(slots=True)
class TableLayoutState:
    column_widths: list[int] = field(default_factory=list)
    row_heights: list[int] = field(default_factory=list)
    column_offsets: list[int] = field(default_factory=lambda: [0])
    row_offsets: list[int] = field(default_factory=lambda: [0])
    table_width: int = 0
    table_height: int = 0


__all__ = ["TextTableConfig", "resolve_text_table_config", "CellState", "TableLayoutState"]
