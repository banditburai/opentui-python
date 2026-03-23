"""TextTableRenderable - table with per-cell native text buffers."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..editor.text_buffer_native import NativeTextBuffer
from ..editor.text_view_native import NativeTextBufferView
from ..enums import RenderStrategy
from ..native import _nb
from .base import Renderable
from .raster_cache import RasterCache
from .text_table_borders import (
    _BorderLayout,
    draw_borders,
    get_horizontal_border_count,
    get_vertical_border_count,
    resolve_border_layout,
)
from .text_table_fitting import (
    expand_column_widths,
    fit_column_widths,
)
from .text_table_config import resolve_text_table_config
from .text_table_selection import (
    get_selected_text as _get_selected_text,
)
from .text_table_selection import (
    get_selection as _get_selection,
)
from .text_table_selection import (
    has_selection as _has_selection,
)
from .text_table_selection import (
    on_selection_changed as _on_selection_changed,
)
from .text_table_selection import (
    setup_mouse_handlers as _setup_text_table_mouse_handlers,
)
from .text_table_selection import (
    should_start_selection as _should_start_selection,
)
from .text_table_config import CellState, TableLayoutState

if TYPE_CHECKING:
    from ..renderer import Buffer

# Large sentinel height for text measurement.
MEASURE_HEIGHT = 10_000

TextTableCellContent = list[dict] | None
TextTableContent = list[list[TextTableCellContent]]


class TextTableRenderable(Renderable):
    """Table renderable with per-cell native text buffers.

    Each cell owns a NativeTextBuffer + NativeTextBufferView pair for
    measurement, wrapping, and rendering.  The table computes column
    widths and row heights, draws grid borders, then renders cells.

    Usage:
        table = TextTableRenderable(
            content=[
                [cell("Name"), cell("Status")],
                [cell("Alpha"), cell("OK")],
            ],
            width=60,
            wrap_mode="word",
        )
    """

    __slots__ = (
        "_content",
        "_wrap_mode_str",
        "_column_width_mode",
        "_column_fitter",
        "_cell_padding",
        "_show_borders",
        "_table_border",
        "_outer_border",
        "_has_explicit_outer_border",
        "_border_style_str",
        "_border_color_val",
        "_border_bg_color",
        "_table_bg_color",
        "_default_fg",
        "_default_bg",
        "_default_attributes",
        "_selectable_flag",
        "_selection_bg_color",
        "_selection_fg_color",
        "_cells",
        "_prev_cell_content",
        "_row_count",
        "_column_count",
        "_table_layout",
        "_layout_dirty",
        "_raster",
        "_cached_measure_layout",
        "_cached_measure_width",
        "_last_local_selection",
        "_last_selection_mode",
        "_is_selecting",
        "_selection_anchor",
    )

    def get_render_strategy(self) -> RenderStrategy:
        return RenderStrategy.HEAVY_WIDGET

    def __init__(
        self,
        *,
        content: TextTableContent | None = None,
        wrap_mode: str = "word",
        column_width_mode: str = "full",
        column_fitter: str = "proportional",
        cell_padding: int = 0,
        show_borders: bool = True,
        border: bool = True,
        outer_border: bool | None = None,
        selectable: bool = True,
        selection_bg: s.RGBA | str | None = None,
        selection_fg: s.RGBA | str | None = None,
        border_style: str = "single",
        border_color: s.RGBA | str | None = None,
        border_background_color: s.RGBA | str | None = None,
        background_color: s.RGBA | str | None = None,
        fg: s.RGBA | str | None = None,
        bg: s.RGBA | str | None = None,
        attributes: int = 0,
        # Renderable pass-through
        **kwargs,
    ):
        # Default flex_shrink to 0 for tables
        kwargs.setdefault("flex_shrink", 0)
        super().__init__(**kwargs)

        config = resolve_text_table_config(
            self._parse_color,
            self._resolve_column_fitter,
            self._resolve_cell_padding,
            content=content,
            wrap_mode=wrap_mode,
            column_width_mode=column_width_mode,
            column_fitter=column_fitter,
            cell_padding=cell_padding,
            show_borders=show_borders,
            border=border,
            outer_border=outer_border,
            selectable=selectable,
            selection_bg=selection_bg,
            selection_fg=selection_fg,
            border_style=border_style,
            border_color=border_color,
            border_background_color=border_background_color,
            background_color=background_color,
            fg=fg,
            bg=bg,
            attributes=attributes,
        )
        self._content: TextTableContent = config.content
        self._wrap_mode_str = config.wrap_mode
        self._column_width_mode = config.column_width_mode
        self._column_fitter = config.column_fitter
        self._cell_padding = config.cell_padding
        self._show_borders = config.show_borders
        self._table_border = config.table_border
        self._has_explicit_outer_border = config.has_explicit_outer_border
        self._outer_border = config.outer_border
        self._selectable_flag = config.selectable
        self._selection_bg_color = config.selection_bg_color
        self._selection_fg_color = config.selection_fg_color
        self._border_style_str = config.border_style
        self._border_color_val = config.border_color
        self._border_bg_color = config.border_background_color
        self._table_bg_color = config.table_background_color
        self._default_fg = config.default_fg
        self._default_bg = config.default_bg
        self._default_attributes = config.default_attributes

        self._cells: list[list[CellState]] = []
        self._prev_cell_content: list[list[TextTableCellContent]] = []
        self._row_count: int = 0
        self._column_count: int = 0

        self._table_layout: TableLayoutState = TableLayoutState()
        self._layout_dirty: bool = True
        self._raster = RasterCache(f"text-table-{self.id}")
        self._cached_measure_layout: TableLayoutState | None = None
        self._cached_measure_width: int | None = None

        self._last_local_selection: dict | None = None
        self._last_selection_mode: str | None = None
        self._is_selecting: bool = False
        self._selection_anchor: tuple[int, int] | None = None

        self._setup_measure_func()
        self._rebuild_cells()
        self._setup_mouse_handlers()

        # Chain _on_size_change: invalidate table layout when dimensions change.
        # Preserve any user-provided on_size_change callback from kwargs.
        _prev_on_size_change = self._on_size_change

        def _on_table_size_change(w, h):
            self._invalidate_layout_and_raster(mark_yoga_dirty=False)
            if _prev_on_size_change is not None:
                _prev_on_size_change(w, h)

        self._on_size_change = _on_table_size_change

    @property
    def content(self) -> TextTableContent:
        return self._content

    @content.setter
    def content(self, value: TextTableContent) -> None:
        self._content = value if value is not None else []
        self._rebuild_cells()

    @property
    def wrap_mode(self) -> str:
        return self._wrap_mode_str

    @wrap_mode.setter
    def wrap_mode(self, value: str) -> None:
        if self._wrap_mode_str == value:
            return
        self._wrap_mode_str = value
        for row in self._cells:
            for cell in row:
                cell.text_buffer_view.set_wrap_mode(value)
        self._invalidate_layout_and_raster()

    @property
    def column_width_mode(self) -> str:
        return self._column_width_mode

    @column_width_mode.setter
    def column_width_mode(self, value: str) -> None:
        if self._column_width_mode == value:
            return
        self._column_width_mode = value
        self._invalidate_layout_and_raster()

    @property
    def column_fitter(self) -> str:
        return self._column_fitter

    @column_fitter.setter
    def column_fitter(self, value: str) -> None:
        next_val = self._resolve_column_fitter(value)
        if self._column_fitter == next_val:
            return
        self._column_fitter = next_val
        self._invalidate_layout_and_raster()

    @property
    def cell_padding(self) -> int:
        return self._cell_padding

    @cell_padding.setter
    def cell_padding(self, value: int) -> None:
        next_val = self._resolve_cell_padding(value)
        if self._cell_padding == next_val:
            return
        self._cell_padding = next_val
        self._invalidate_layout_and_raster()

    @property
    def show_borders(self) -> bool:
        return self._show_borders

    @show_borders.setter
    def show_borders(self, value: bool) -> None:
        if self._show_borders == value:
            return
        self._show_borders = value
        self._invalidate_layout_and_raster()

    @property
    def outer_border(self) -> bool:
        return self._outer_border

    @outer_border.setter
    def outer_border(self, value: bool) -> None:
        if self._outer_border == value:
            return
        self._has_explicit_outer_border = True
        self._outer_border = value
        self._invalidate_layout_and_raster()

    @property
    def table_border(self) -> bool:
        return self._table_border

    @table_border.setter
    def table_border(self, value: bool) -> None:
        if self._table_border == value:
            return
        self._table_border = value
        if not self._has_explicit_outer_border:
            self._outer_border = value
        self._invalidate_layout_and_raster()

    @property
    def border_style(self) -> str:
        return self._border_style_str

    @border_style.setter
    def border_style(self, value: str) -> None:
        next_val = value if value in ("single", "double", "round") else "single"
        if self._border_style_str == next_val:
            return
        self._border_style_str = next_val
        self._invalidate_raster_only()

    @property
    def selectable(self) -> bool:
        return self._selectable_flag

    @selectable.setter
    def selectable(self, value: bool) -> None:
        self._selectable_flag = value

    @property
    def width(self) -> int:
        return self._layout_width

    @width.setter
    def width(self, value: int | str | None) -> None:
        self._width = value
        self.mark_dirty()

    @property
    def height(self) -> int:
        return self._layout_height

    @height.setter
    def height(self, value: int | str | None) -> None:
        self._height = value
        self.mark_dirty()

    def should_start_selection(self, x: int, y: int) -> bool:
        return _should_start_selection(self, x, y)

    def has_selection(self) -> bool:
        return _has_selection(self)

    def get_selection(self) -> dict[str, int] | None:
        return _get_selection(self)

    def get_selected_text(self) -> str:
        return _get_selected_text(self)

    def on_selection_changed(self, selection) -> bool:
        return _on_selection_changed(self, selection)

    def _setup_measure_func(self) -> None:
        def measure(
            yoga_node: Any, width: float, width_mode: Any, height: float, height_mode: Any
        ) -> tuple[float, float]:
            import yoga

            has_width_constraint = width_mode != yoga.MeasureMode.Undefined and math.isfinite(width)
            raw_width_constraint = max(1, int(width)) if has_width_constraint else None
            width_constraint = self._resolve_layout_width_constraint(raw_width_constraint)
            measured_layout = self._compute_layout(width_constraint)
            self._cached_measure_layout = measured_layout
            self._cached_measure_width = width_constraint

            measured_w = measured_layout.table_width if measured_layout.table_width > 0 else 1
            measured_h = measured_layout.table_height if measured_layout.table_height > 0 else 1

            if (
                width_mode == yoga.MeasureMode.AtMost
                and raw_width_constraint is not None
                and self._position != "absolute"
            ):
                measured_w = min(raw_width_constraint, measured_w)

            return (measured_w, measured_h)

        self._yoga_node.set_measure_func(measure)

    def _setup_mouse_handlers(self) -> None:
        _setup_text_table_mouse_handlers(self)

    def _rebuild_cells(self) -> None:
        new_row_count = len(self._content)
        new_column_count = max((len(row) for row in self._content), default=0)

        if not self._cells:
            self._row_count = new_row_count
            self._column_count = new_column_count
            self._cells = []
            self._prev_cell_content = []

            for row_idx in range(new_row_count):
                row_data = self._content[row_idx] if row_idx < len(self._content) else []
                row_cells: list[CellState] = []
                row_refs: list[TextTableCellContent] = []

                for col_idx in range(new_column_count):
                    cell_content = row_data[col_idx] if col_idx < len(row_data) else None
                    row_cells.append(self._create_cell(cell_content))
                    row_refs.append(cell_content)

                self._cells.append(row_cells)
                self._prev_cell_content.append(row_refs)

            self._invalidate_layout_and_raster()
            return

        self._update_cells_diff(new_row_count, new_column_count)
        self._invalidate_layout_and_raster()

    def _update_cells_diff(self, new_row_count: int, new_column_count: int) -> None:
        old_row_count = self._row_count
        old_column_count = self._column_count
        keep_rows = min(old_row_count, new_row_count)
        keep_cols = min(old_column_count, new_column_count)

        for row_idx in range(keep_rows):
            new_row = self._content[row_idx] if row_idx < len(self._content) else []
            cell_row = self._cells[row_idx]
            ref_row = self._prev_cell_content[row_idx]

            for col_idx in range(keep_cols):
                cell_content = new_row[col_idx] if col_idx < len(new_row) else None
                if cell_content is ref_row[col_idx]:
                    continue
                cell_row[col_idx] = self._create_cell(cell_content)
                ref_row[col_idx] = cell_content

            if new_column_count > old_column_count:
                for col_idx in range(old_column_count, new_column_count):
                    cell_content = new_row[col_idx] if col_idx < len(new_row) else None
                    cell_row.append(self._create_cell(cell_content))
                    ref_row.append(cell_content)
            elif new_column_count < old_column_count:
                del cell_row[new_column_count:]
                del ref_row[new_column_count:]

        if new_row_count > old_row_count:
            for row_idx in range(old_row_count, new_row_count):
                new_row = self._content[row_idx] if row_idx < len(self._content) else []
                row_cells: list[CellState] = []
                row_refs: list[TextTableCellContent] = []
                for col_idx in range(new_column_count):
                    cell_content = new_row[col_idx] if col_idx < len(new_row) else None
                    row_cells.append(self._create_cell(cell_content))
                    row_refs.append(cell_content)
                self._cells.append(row_cells)
                self._prev_cell_content.append(row_refs)
        elif new_row_count < old_row_count:
            del self._cells[new_row_count:]
            del self._prev_cell_content[new_row_count:]

        self._row_count = new_row_count
        self._column_count = new_column_count

    def _create_cell(self, content: TextTableCellContent) -> CellState:
        text = self._cell_content_to_text(content)
        text_buffer = NativeTextBuffer()
        text_buffer.set_text(text)

        text_buffer_view = NativeTextBufferView(text_buffer.ptr, text_buffer)
        text_buffer_view.set_wrap_mode(self._wrap_mode_str)

        return CellState(text_buffer, text_buffer_view)

    def _cell_content_to_text(self, content: TextTableCellContent) -> str:
        """Convert cell content to plain text.

        Content can be:
        - None/empty -> ""
        - list of TextChunk dicts with "text" key -> concatenated text
        - string -> direct text
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                for chunk in content
            )
        return str(content)

    def _ensure_layout_ready(self) -> None:
        if not self._layout_dirty:
            return
        self._rebuild_layout_for_current_width()

    def _rebuild_layout_for_current_width(self) -> None:
        max_table_width = self._resolve_layout_width_constraint(self._layout_width)

        if (
            self._cached_measure_layout is not None
            and self._cached_measure_width == max_table_width
        ):
            layout = self._cached_measure_layout
        else:
            layout = self._compute_layout(max_table_width)

        self._cached_measure_layout = None
        self._cached_measure_width = None

        self._table_layout = layout
        self._apply_layout_to_views(layout)
        self._layout_dirty = False

    def _compute_layout(self, max_table_width: int | None = None) -> TableLayoutState:
        if self._row_count == 0 or self._column_count == 0:
            return TableLayoutState()

        border_layout = self._resolve_border_layout()
        column_widths = self._compute_column_widths(max_table_width, border_layout)
        row_heights = self._compute_row_heights(column_widths)
        column_offsets = self._compute_offsets(
            column_widths, border_layout.left, border_layout.right, border_layout.inner_vertical
        )
        row_offsets = self._compute_offsets(
            row_heights, border_layout.top, border_layout.bottom, border_layout.inner_horizontal
        )

        layout = TableLayoutState()
        layout.column_widths = column_widths
        layout.row_heights = row_heights
        layout.column_offsets = column_offsets
        layout.row_offsets = row_offsets
        layout.table_width = (column_offsets[-1] if column_offsets else 0) + 1
        layout.table_height = (row_offsets[-1] if row_offsets else 0) + 1

        return layout

    def _is_full_width_mode(self) -> bool:
        return self._column_width_mode == "full"

    def _compute_column_widths(
        self, max_table_width: int | None, border_layout: _BorderLayout
    ) -> list[int]:
        horizontal_padding = self._get_cell_padding()
        intrinsic_widths = [1 + horizontal_padding] * self._column_count

        for row_idx in range(self._row_count):
            for col_idx in range(self._column_count):
                if row_idx >= len(self._cells) or col_idx >= len(self._cells[row_idx]):
                    continue
                cell = self._cells[row_idx][col_idx]
                result = cell.text_buffer_view.measure_for_dimensions(0, MEASURE_HEIGHT)
                measured_width = (
                    max(1, result["widthColsMax"] if result else 0) + horizontal_padding
                )
                intrinsic_widths[col_idx] = max(intrinsic_widths[col_idx], measured_width)

        if max_table_width is None or max_table_width <= 0:
            return intrinsic_widths

        max_content_width = max(
            1, max_table_width - get_vertical_border_count(border_layout, self._column_count)
        )
        current_width = sum(intrinsic_widths)

        if current_width == max_content_width:
            return intrinsic_widths

        if current_width < max_content_width:
            if self._is_full_width_mode():
                return expand_column_widths(intrinsic_widths, max_content_width)
            return intrinsic_widths

        if self._wrap_mode_str == "none":
            return intrinsic_widths

        return fit_column_widths(
            intrinsic_widths,
            max_content_width,
            self._column_fitter,
            self._get_cell_padding(),
        )

    def _compute_row_heights(self, column_widths: list[int]) -> list[int]:
        horizontal_padding = self._get_cell_padding()
        vertical_padding = self._get_cell_padding()
        row_heights = [1 + vertical_padding] * self._row_count

        for row_idx in range(self._row_count):
            for col_idx in range(self._column_count):
                if row_idx >= len(self._cells) or col_idx >= len(self._cells[row_idx]):
                    continue
                cell = self._cells[row_idx][col_idx]
                col_w = column_widths[col_idx] if col_idx < len(column_widths) else 1
                content_width = max(1, col_w - horizontal_padding)
                result = cell.text_buffer_view.measure_for_dimensions(content_width, MEASURE_HEIGHT)
                line_count = max(1, result["lineCount"] if result else 1)
                row_heights[row_idx] = max(row_heights[row_idx], line_count + vertical_padding)

        return row_heights

    def _compute_offsets(
        self, parts: list[int], start_boundary: bool, end_boundary: bool, include_inner: bool
    ) -> list[int]:
        offsets: list[int] = [0 if start_boundary else -1]
        cursor = offsets[0]

        for idx in range(len(parts)):
            size = parts[idx]
            has_boundary_after = include_inner if idx < len(parts) - 1 else end_boundary
            cursor += size + (1 if has_boundary_after else 0)
            offsets.append(cursor)

        return offsets

    def _apply_layout_to_views(self, layout: TableLayoutState) -> None:
        horizontal_padding = self._get_cell_padding()
        vertical_padding = self._get_cell_padding()

        for row_idx in range(self._row_count):
            for col_idx in range(self._column_count):
                if row_idx >= len(self._cells) or col_idx >= len(self._cells[row_idx]):
                    continue
                cell = self._cells[row_idx][col_idx]
                col_width = (
                    layout.column_widths[col_idx] if col_idx < len(layout.column_widths) else 1
                )
                row_height = layout.row_heights[row_idx] if row_idx < len(layout.row_heights) else 1
                content_width = max(1, col_width - horizontal_padding)
                content_height = max(1, row_height - vertical_padding)

                if self._wrap_mode_str != "none":
                    cell.text_buffer_view.set_wrap_width(content_width)

                cell.text_buffer_view.set_viewport(0, 0, content_width, content_height)

    def _resolve_border_layout(self) -> _BorderLayout:
        return resolve_border_layout(
            self._outer_border, self._table_border, self._column_count, self._row_count
        )

    def _get_cell_padding(self) -> int:
        return self._cell_padding * 2

    def _resolve_layout_width_constraint(self, width: int | None) -> int | None:
        if width is None or width <= 0:
            return None
        if self._wrap_mode_str != "none" or self._is_full_width_mode():
            return max(1, int(width))
        return None

    def _resolve_column_fitter(self, value: str | None) -> str:
        if value is None:
            return "proportional"
        return "balanced" if value == "balanced" else "proportional"

    def _resolve_cell_padding(self, value: int | None) -> int:
        if value is None:
            return 0
        return max(0, int(value))

    def _invalidate_layout_and_raster(self, mark_yoga_dirty: bool = True) -> None:
        self._layout_dirty = True
        self._raster.invalidate()
        self._cached_measure_layout = None
        self._cached_measure_width = None
        if mark_yoga_dirty and self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.mark_dirty()

    def _invalidate_raster_only(self) -> None:
        self._raster.invalidate()
        self.mark_paint_dirty()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        if self._layout_dirty:
            self._rebuild_layout_for_current_width()

        self._raster.render_cached(
            buffer,
            self._x,
            self._y,
            self._layout_width,
            self._layout_height,
            self._render_table_contents,
        )

    def _render_table_contents(self, buffer: Buffer) -> None:
        x = self._x
        y = self._y
        if self._table_bg_color.a > 0:
            buffer.fill_rect(x, y, self._layout_width, self._layout_height, self._table_bg_color)
        if self._show_borders:
            self._draw_borders(buffer, x, y)

        self._draw_cells(buffer, x, y)

    def _draw_borders(self, buffer: Buffer, base_x: int, base_y: int) -> None:
        """Draw grid borders, preferring the core native grid primitive."""
        border_layout = self._resolve_border_layout()
        vcount = get_vertical_border_count(border_layout, self._column_count)
        hcount = get_horizontal_border_count(border_layout, self._row_count)

        if vcount == 0 and hcount == 0:
            return

        if border_layout.left == border_layout.right == border_layout.top == border_layout.bottom:
            try:
                _nb.buffer.buffer_draw_grid(
                    buffer._ptr,
                    self._border_style_str,
                    (
                        self._border_color_val.r,
                        self._border_color_val.g,
                        self._border_color_val.b,
                        self._border_color_val.a,
                    ),
                    (
                        self._border_bg_color.r,
                        self._border_bg_color.g,
                        self._border_bg_color.b,
                        self._border_bg_color.a,
                    ),
                    self._table_layout.column_offsets,
                    self._table_layout.row_offsets,
                    border_layout.inner_vertical or border_layout.inner_horizontal,
                    border_layout.left,
                )
                return
            except Exception:
                pass

        fg = self._border_color_val
        bg = self._border_bg_color if self._border_bg_color.a > 0 else None
        draw_borders(
            buffer,
            base_x,
            base_y,
            self._border_style_str,
            fg,
            bg,
            border_layout,
            self._table_layout,
            self._column_count,
            self._row_count,
        )

    def _draw_cells(self, buffer: Buffer, base_x: int, base_y: int) -> None:
        col_offsets = self._table_layout.column_offsets
        row_offsets = self._table_layout.row_offsets
        cell_padding = self._cell_padding

        for row_idx in range(self._row_count):
            if row_idx >= len(self._cells) or row_idx >= len(row_offsets):
                continue
            cell_y = row_offsets[row_idx] + 1 + cell_padding

            for col_idx in range(self._column_count):
                if col_idx >= len(self._cells[row_idx]) or col_idx >= len(col_offsets):
                    continue
                cell = self._cells[row_idx][col_idx]
                cell_x = col_offsets[col_idx] + 1 + cell_padding

                try:
                    _nb.text_buffer.buffer_draw_text_buffer_view(
                        buffer._ptr, cell.text_buffer_view.ptr, base_x + cell_x, base_y + cell_y
                    )
                except Exception:
                    text = cell.text_buffer.get_plain_text()
                    if text:
                        buffer.draw_text(
                            text, base_x + cell_x, base_y + cell_y,
                            self._default_fg,
                            self._default_bg if self._default_bg.a > 0 else None,
                            self._default_attributes,
                        )

    def destroy(self) -> None:
        self._raster.release()
        self._cells.clear()
        self._prev_cell_content.clear()
        self._row_count = 0
        self._column_count = 0
        super().destroy()


__all__ = ["TextTableRenderable"]
