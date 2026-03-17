"""TextTableRenderable - table with per-cell native text buffers.

Table component for tabular text layout.
Each cell has its own NativeTextBuffer + NativeTextBufferView for
measurement, wrapping, and rendering.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..native import NativeTextBuffer, NativeTextBufferView, _nb
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer

# Large sentinel height for text measurement.
MEASURE_HEIGHT = 10_000

# Type aliases for table layout
TextTableCellContent = list[dict] | None
TextTableContent = list[list[TextTableCellContent]]
TextTableColumnWidthMode = str  # "content" | "full"
TextTableColumnFitter = str  # "proportional" | "balanced"

# Border characters for grid drawing (single style)
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


class _CellState:
    """State for a single table cell."""

    __slots__ = ("text_buffer", "text_buffer_view")

    def __init__(self, text_buffer: NativeTextBuffer, text_buffer_view: NativeTextBufferView):
        self.text_buffer = text_buffer
        self.text_buffer_view = text_buffer_view


class _TableLayout:
    """Computed table layout."""

    __slots__ = (
        "column_widths",
        "row_heights",
        "column_offsets",
        "row_offsets",
        "table_width",
        "table_height",
    )

    def __init__(self):
        self.column_widths: list[int] = []
        self.row_heights: list[int] = []
        self.column_offsets: list[int] = [0]
        self.row_offsets: list[int] = [0]
        self.table_width: int = 0
        self.table_height: int = 0


class _BorderLayout:
    """Resolved border layout flags."""

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
        # Cell storage
        "_cells",
        "_prev_cell_content",
        "_row_count",
        "_column_count",
        # Layout
        "_table_layout",
        "_layout_dirty",
        "_raster_dirty",
        "_cached_measure_layout",
        "_cached_measure_width",
        # Selection
        "_last_local_selection",
        "_last_selection_mode",
        "_is_selecting",
        "_selection_anchor",
    )

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

        self._content: TextTableContent = content if content is not None else []
        self._wrap_mode_str = wrap_mode if wrap_mode in ("none", "char", "word") else "word"
        self._column_width_mode: str = (
            column_width_mode if column_width_mode in ("content", "full") else "full"
        )
        self._column_fitter: str = self._resolve_column_fitter(column_fitter)
        self._cell_padding: int = self._resolve_cell_padding(cell_padding)
        self._show_borders: bool = show_borders
        self._table_border: bool = border
        self._has_explicit_outer_border: bool = outer_border is not None
        self._outer_border: bool = outer_border if outer_border is not None else border
        self._selectable_flag: bool = selectable
        self._selection_bg_color = self._parse_color(selection_bg)
        self._selection_fg_color = self._parse_color(selection_fg)
        self._border_style_str: str = (
            border_style if border_style in ("single", "double", "round") else "single"
        )
        self._border_color_val: s.RGBA = self._parse_color(border_color) or s.RGBA(
            1.0, 1.0, 1.0, 1.0
        )
        self._border_bg_color: s.RGBA = self._parse_color(border_background_color) or s.RGBA(
            0.0, 0.0, 0.0, 0.0
        )
        self._table_bg_color: s.RGBA = self._parse_color(background_color) or s.RGBA(
            0.0, 0.0, 0.0, 0.0
        )
        self._default_fg: s.RGBA = self._parse_color(fg) or s.RGBA(1.0, 1.0, 1.0, 1.0)
        self._default_bg: s.RGBA = self._parse_color(bg) or s.RGBA(0.0, 0.0, 0.0, 0.0)
        self._default_attributes: int = attributes

        self._cells: list[list[_CellState]] = []
        self._prev_cell_content: list[list[TextTableCellContent]] = []
        self._row_count: int = 0
        self._column_count: int = 0

        self._table_layout: _TableLayout = _TableLayout()
        self._layout_dirty: bool = True
        self._raster_dirty: bool = True
        self._cached_measure_layout: _TableLayout | None = None
        self._cached_measure_width: int | None = None

        self._last_local_selection: dict | None = None
        self._last_selection_mode: str | None = None
        self._is_selecting: bool = False
        self._selection_anchor: tuple[int, int] | None = None

        self._setup_measure_func()
        self._rebuild_cells()
        self._setup_mouse_handlers()

    # ── Properties ──────────────────────────────────────────────────

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
        self._invalidate_raster_only()

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

    # Width/height return computed layout values
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

    # ── Selection ───────────────────────────────────────────────────

    def should_start_selection(self, x: int, y: int) -> bool:
        """Return True if a selection should start at global (x, y).

        Only returns True when the point falls on actual cell content,
        not on border lines.
        """
        if not self._selectable_flag:
            return False
        self._ensure_layout_ready()
        local_x = x - self._x
        local_y = y - self._y
        return self._get_cell_at_local_position(local_x, local_y) is not None

    def has_selection(self) -> bool:
        """Return True if any cell has an active selection."""
        for row in self._cells:
            for cell in row:
                if cell.text_buffer_view.has_selection():
                    return True
        return False

    def get_selection(self) -> dict[str, int] | None:
        """Get the first cell's selection, or None."""
        for row in self._cells:
            for cell in row:
                sel = cell.text_buffer_view.get_selection()
                if sel:
                    return sel
        return None

    def get_selected_text(self) -> str:
        """Get selected text, tab-separated within rows, newline-separated between rows."""
        selected_rows: list[str] = []
        for row_idx in range(self._row_count):
            row_selections: list[str] = []
            for col_idx in range(self._column_count):
                cell = (
                    self._cells[row_idx][col_idx]
                    if row_idx < len(self._cells) and col_idx < len(self._cells[row_idx])
                    else None
                )
                if not cell or not cell.text_buffer_view.has_selection():
                    continue
                selected_text = cell.text_buffer_view.get_selected_text()
                if len(selected_text) > 0:
                    row_selections.append(selected_text)
            if row_selections:
                selected_rows.append("\t".join(row_selections))
        return "\n".join(selected_rows)

    def on_selection_changed(self, selection) -> bool:
        """Handle selection change from the renderer.

        Called by the renderer's selection dispatch with a Selection object
        (from opentui.selection) or None.
        """
        self._ensure_layout_ready()

        local_selection = self._convert_global_to_local_selection(selection)
        self._last_local_selection = local_selection

        if not local_selection or not local_selection.get("is_active"):
            self._reset_cell_selections()
            self._last_selection_mode = None
        else:
            is_start = getattr(selection, "is_start", False) if selection else False
            self._apply_selection_to_cells(local_selection, is_start)

        return self.has_selection()

    def _convert_global_to_local_selection(self, selection) -> dict | None:
        if selection is None:
            return None

        # Support both dict-based (legacy) and Selection object-based API
        if isinstance(selection, dict):
            anchor_x = selection.get("anchorX", selection.get("anchor_x", 0))
            anchor_y = selection.get("anchorY", selection.get("anchor_y", 0))
            focus_x = selection.get("focusX", selection.get("focus_x", 0))
            focus_y = selection.get("focusY", selection.get("focus_y", 0))
            is_active = selection.get("isActive", selection.get("is_active", False))
        else:
            # Selection object
            anchor = selection.anchor
            focus = selection.focus
            anchor_x = anchor["x"]
            anchor_y = anchor["y"]
            focus_x = focus["x"]
            focus_y = focus["y"]
            is_active = getattr(selection, "is_active", True)

        return {
            "anchor_x": anchor_x - self._x,
            "anchor_y": anchor_y - self._y,
            "focus_x": focus_x - self._x,
            "focus_y": focus_y - self._y,
            "is_active": is_active,
        }

    def _apply_selection_to_cells(self, local_selection: dict, is_start: bool) -> None:
        min_sel_y = min(local_selection["anchor_y"], local_selection["focus_y"])
        max_sel_y = max(local_selection["anchor_y"], local_selection["focus_y"])

        first_row = self._find_row_for_local_y(min_sel_y)
        last_row = self._find_row_for_local_y(max_sel_y)
        resolution = self._resolve_selection_resolution(local_selection)
        mode_changed = self._last_selection_mode != resolution["mode"]
        self._last_selection_mode = resolution["mode"]
        lock_to_anchor_column = (
            resolution["mode"] == "column-locked" and resolution.get("anchor_column") is not None
        )

        for row_idx in range(self._row_count):
            if row_idx < first_row or row_idx > last_row:
                self._reset_row_selection(row_idx)
                continue

            cell_top = (
                (
                    self._table_layout.row_offsets[row_idx]
                    if row_idx < len(self._table_layout.row_offsets)
                    else 0
                )
                + 1
                + self._cell_padding
            )

            for col_idx in range(self._column_count):
                cell = (
                    self._cells[row_idx][col_idx]
                    if row_idx < len(self._cells) and col_idx < len(self._cells[row_idx])
                    else None
                )
                if not cell:
                    continue

                if lock_to_anchor_column and col_idx != resolution.get("anchor_column"):
                    cell.text_buffer_view.reset_local_selection()
                    continue

                cell_left = (
                    (
                        self._table_layout.column_offsets[col_idx]
                        if col_idx < len(self._table_layout.column_offsets)
                        else 0
                    )
                    + 1
                    + self._cell_padding
                )

                anchor_x = local_selection["anchor_x"] - cell_left
                anchor_y = local_selection["anchor_y"] - cell_top
                focus_x = local_selection["focus_x"] - cell_left
                focus_y = local_selection["focus_y"] - cell_top

                anchor_cell = resolution.get("anchor_cell")
                is_anchor_cell = (
                    anchor_cell is not None
                    and anchor_cell[0] == row_idx
                    and anchor_cell[1] == col_idx
                )
                force_set = is_anchor_cell and resolution["mode"] != "single-cell"

                if force_set:
                    col_width = (
                        self._table_layout.column_widths[col_idx]
                        if col_idx < len(self._table_layout.column_widths)
                        else 1
                    )
                    row_height = (
                        self._table_layout.row_heights[row_idx]
                        if row_idx < len(self._table_layout.row_heights)
                        else 1
                    )
                    content_width = max(1, col_width - self._get_horizontal_cell_padding())
                    content_height = max(1, row_height - self._get_vertical_cell_padding())
                    anchor_x = -1
                    anchor_y = 0
                    focus_x = content_width
                    focus_y = content_height

                should_use_set = is_start or mode_changed or force_set

                if should_use_set:
                    cell.text_buffer_view.set_local_selection(anchor_x, anchor_y, focus_x, focus_y)
                else:
                    cell.text_buffer_view.update_local_selection(
                        anchor_x, anchor_y, focus_x, focus_y
                    )

    def _resolve_selection_resolution(self, local_selection: dict) -> dict:
        anchor_cell = self._get_cell_at_local_position(
            local_selection["anchor_x"], local_selection["anchor_y"]
        )
        focus_cell = self._get_cell_at_local_position(
            local_selection["focus_x"], local_selection["focus_y"]
        )
        anchor_column = (
            anchor_cell[1]
            if anchor_cell
            else self._get_column_at_local_x(local_selection["anchor_x"])
        )

        if (
            anchor_cell is not None
            and focus_cell is not None
            and anchor_cell[0] == focus_cell[0]
            and anchor_cell[1] == focus_cell[1]
        ):
            return {
                "mode": "single-cell",
                "anchor_cell": anchor_cell,
                "anchor_column": anchor_column,
            }

        focus_column = self._get_column_at_local_x(local_selection["focus_x"])
        if anchor_column is not None and focus_column == anchor_column:
            return {
                "mode": "column-locked",
                "anchor_cell": anchor_cell,
                "anchor_column": anchor_column,
            }

        return {"mode": "grid", "anchor_cell": anchor_cell, "anchor_column": anchor_column}

    def _get_column_at_local_x(self, local_x: int) -> int | None:
        if self._column_count == 0:
            return None
        if local_x < 0 or local_x >= self._table_layout.table_width:
            return None
        for col_idx in range(self._column_count):
            col_start = (
                self._table_layout.column_offsets[col_idx]
                if col_idx < len(self._table_layout.column_offsets)
                else 0
            ) + 1
            col_width = (
                self._table_layout.column_widths[col_idx]
                if col_idx < len(self._table_layout.column_widths)
                else 1
            )
            col_end = col_start + col_width - 1
            if local_x >= col_start and local_x <= col_end:
                return col_idx
        return None

    def _find_row_for_local_y(self, local_y: int) -> int:
        if self._row_count == 0:
            return 0
        if local_y < 0:
            return 0
        for row_idx in range(self._row_count):
            row_start = (
                self._table_layout.row_offsets[row_idx]
                if row_idx < len(self._table_layout.row_offsets)
                else 0
            ) + 1
            row_height = (
                self._table_layout.row_heights[row_idx]
                if row_idx < len(self._table_layout.row_heights)
                else 1
            )
            row_end = row_start + row_height - 1
            if local_y <= row_end:
                return row_idx
        return self._row_count - 1

    def _reset_row_selection(self, row_idx: int) -> None:
        if row_idx >= len(self._cells):
            return
        for cell in self._cells[row_idx]:
            cell.text_buffer_view.reset_local_selection()

    def _reset_cell_selections(self) -> None:
        for row_idx in range(self._row_count):
            self._reset_row_selection(row_idx)

    def _get_cell_at_local_position(self, local_x: int, local_y: int) -> tuple[int, int] | None:
        if self._row_count == 0 or self._column_count == 0:
            return None
        if local_x < 0 or local_y < 0:
            return None
        if local_x >= self._table_layout.table_width or local_y >= self._table_layout.table_height:
            return None

        row_idx = -1
        for idx in range(self._row_count):
            top = (
                self._table_layout.row_offsets[idx]
                if idx < len(self._table_layout.row_offsets)
                else 0
            ) + 1
            row_h = (
                self._table_layout.row_heights[idx]
                if idx < len(self._table_layout.row_heights)
                else 1
            )
            bottom = top + row_h - 1
            if local_y >= top and local_y <= bottom:
                row_idx = idx
                break

        if row_idx < 0:
            return None

        col_idx = -1
        for idx in range(self._column_count):
            left = (
                self._table_layout.column_offsets[idx]
                if idx < len(self._table_layout.column_offsets)
                else 0
            ) + 1
            col_w = (
                self._table_layout.column_widths[idx]
                if idx < len(self._table_layout.column_widths)
                else 1
            )
            right = left + col_w - 1
            if local_x >= left and local_x <= right:
                col_idx = idx
                break

        if col_idx < 0:
            return None

        return (row_idx, col_idx)

    # ── Measure function ────────────────────────────────────────────

    def _setup_measure_func(self) -> None:
        """Set up yoga measure function."""

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

    # ── Mouse handlers (selection) ─────────────────────────────────

    def _setup_mouse_handlers(self) -> None:
        """Wire mouse events to drive the selection system.

        OpenTUI core has a dedicated selection dispatch system
        (startSelection / updateSelection / notifySelectablesOfSelectionChange).
        Since this Python renderer doesn't have that, we drive selection directly
        from the mouse event handlers on the renderable.
        """

        def _on_down(event: Any) -> None:
            x, y = event.x, event.y
            if not self.should_start_selection(x, y):
                return
            self._is_selecting = True
            self._selection_anchor = (x, y)
            self.on_selection_changed(
                {
                    "anchorX": x,
                    "anchorY": y,
                    "focusX": x,
                    "focusY": y,
                    "isActive": True,
                    "is_start": True,
                }
            )

        def _on_drag(event: Any) -> None:
            if not self._is_selecting or self._selection_anchor is None:
                return
            ax, ay = self._selection_anchor
            self.on_selection_changed(
                {
                    "anchorX": ax,
                    "anchorY": ay,
                    "focusX": event.x,
                    "focusY": event.y,
                    "isActive": True,
                    "is_start": False,
                }
            )

        def _on_drag_end(event: Any) -> None:
            if not self._is_selecting:
                return
            self._is_selecting = False
            # Keep the selection active after drag ends (don't clear).

        def _on_up(event: Any) -> None:
            if not self._is_selecting:
                return
            self._is_selecting = False

        self._on_mouse_down = _on_down
        self._on_mouse_drag = _on_drag
        self._on_mouse_drag_end = _on_drag_end
        self._on_mouse_up = _on_up

    # ── Cell management ─────────────────────────────────────────────

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
                row_cells: list[_CellState] = []
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
                row_cells: list[_CellState] = []
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

    def _create_cell(self, content: TextTableCellContent) -> _CellState:
        text = self._cell_content_to_text(content)
        text_buffer = NativeTextBuffer()
        text_buffer.set_text(text)

        text_buffer_view = NativeTextBufferView(text_buffer.ptr, text_buffer)
        text_buffer_view.set_wrap_mode(self._wrap_mode_str)

        return _CellState(text_buffer, text_buffer_view)

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
            parts = []
            for chunk in content:
                if isinstance(chunk, dict):
                    parts.append(chunk.get("text", ""))
                elif isinstance(chunk, str):
                    parts.append(chunk)
                else:
                    parts.append(str(chunk))
            return "".join(parts)
        return str(content)

    # ── Layout computation ──────────────────────────────────────────

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

    def _compute_layout(self, max_table_width: int | None = None) -> _TableLayout:
        if self._row_count == 0 or self._column_count == 0:
            return _TableLayout()

        border_layout = self._resolve_border_layout()
        column_widths = self._compute_column_widths(max_table_width, border_layout)
        row_heights = self._compute_row_heights(column_widths)
        column_offsets = self._compute_offsets(
            column_widths, border_layout.left, border_layout.right, border_layout.inner_vertical
        )
        row_offsets = self._compute_offsets(
            row_heights, border_layout.top, border_layout.bottom, border_layout.inner_horizontal
        )

        layout = _TableLayout()
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
        horizontal_padding = self._get_horizontal_cell_padding()
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

        max_content_width = max(1, max_table_width - self._get_vertical_border_count(border_layout))
        current_width = sum(intrinsic_widths)

        if current_width == max_content_width:
            return intrinsic_widths

        if current_width < max_content_width:
            if self._is_full_width_mode():
                return self._expand_column_widths(intrinsic_widths, max_content_width)
            return intrinsic_widths

        if self._wrap_mode_str == "none":
            return intrinsic_widths

        return self._fit_column_widths(intrinsic_widths, max_content_width)

    def _expand_column_widths(self, widths: list[int], target_content_width: int) -> list[int]:
        base_widths = [max(1, int(w)) for w in widths]
        total_base = sum(base_widths)

        if total_base >= target_content_width:
            return base_widths

        expanded = list(base_widths)
        columns = len(expanded)
        extra_width = target_content_width - total_base
        shared_width = extra_width // columns
        remainder = extra_width % columns

        for idx in range(columns):
            expanded[idx] += shared_width
            if idx < remainder:
                expanded[idx] += 1

        return expanded

    def _fit_column_widths(self, widths: list[int], target_content_width: int) -> list[int]:
        if self._column_fitter == "balanced":
            return self._fit_column_widths_balanced(widths, target_content_width)
        return self._fit_column_widths_proportional(widths, target_content_width)

    def _fit_column_widths_proportional(
        self, widths: list[int], target_content_width: int
    ) -> list[int]:
        min_width = 1 + self._get_horizontal_cell_padding()
        hard_min_widths = [min_width] * len(widths)
        base_widths = [max(1, int(w)) for w in widths]

        preferred_min_widths = [min(w, min_width + 1) for w in base_widths]
        preferred_min_total = sum(preferred_min_widths)

        floor_widths = (
            preferred_min_widths if preferred_min_total <= target_content_width else hard_min_widths
        )
        floor_total = sum(floor_widths)
        clamped_target = max(floor_total, target_content_width)

        total_base_width = sum(base_widths)

        if total_base_width <= clamped_target:
            return base_widths

        shrinkable = [base_widths[i] - floor_widths[i] for i in range(len(base_widths))]
        total_shrinkable = sum(shrinkable)
        if total_shrinkable <= 0:
            return list(floor_widths)

        target_shrink = total_base_width - clamped_target
        integer_shrink = [0] * len(base_widths)
        fractions = [0.0] * len(base_widths)
        used_shrink = 0

        for idx in range(len(base_widths)):
            if shrinkable[idx] <= 0:
                continue
            exact = (shrinkable[idx] / total_shrinkable) * target_shrink
            whole = min(shrinkable[idx], int(exact))
            integer_shrink[idx] = whole
            fractions[idx] = exact - whole
            used_shrink += whole

        remaining_shrink = target_shrink - used_shrink

        while remaining_shrink > 0:
            best_idx = -1
            best_fraction = -1.0

            for idx in range(len(base_widths)):
                if shrinkable[idx] - integer_shrink[idx] <= 0:
                    continue
                if fractions[idx] > best_fraction:
                    best_fraction = fractions[idx]
                    best_idx = idx

            if best_idx == -1:
                break

            integer_shrink[best_idx] += 1
            fractions[best_idx] = 0
            remaining_shrink -= 1

        return [
            max(floor_widths[i], base_widths[i] - integer_shrink[i])
            for i in range(len(base_widths))
        ]

    def _fit_column_widths_balanced(
        self, widths: list[int], target_content_width: int
    ) -> list[int]:
        min_width = 1 + self._get_horizontal_cell_padding()
        hard_min_widths = [min_width] * len(widths)
        base_widths = [max(1, int(w)) for w in widths]
        total_base_width = sum(base_widths)
        columns = len(base_widths)

        if columns == 0 or total_base_width <= target_content_width:
            return base_widths

        even_share = max(min_width, target_content_width // columns)
        preferred_min_widths = [min(w, even_share) for w in base_widths]
        preferred_min_total = sum(preferred_min_widths)
        floor_widths = (
            preferred_min_widths if preferred_min_total <= target_content_width else hard_min_widths
        )
        floor_total = sum(floor_widths)
        clamped_target = max(floor_total, target_content_width)

        if total_base_width <= clamped_target:
            return base_widths

        shrinkable = [base_widths[i] - floor_widths[i] for i in range(len(base_widths))]
        total_shrinkable = sum(shrinkable)
        if total_shrinkable <= 0:
            return list(floor_widths)

        target_shrink = total_base_width - clamped_target
        shrink = self._allocate_shrink_by_weight(shrinkable, target_shrink, "sqrt")

        return [max(floor_widths[i], base_widths[i] - shrink[i]) for i in range(len(base_widths))]

    def _allocate_shrink_by_weight(
        self, shrinkable: list[int], target_shrink: int, mode: str
    ) -> list[int]:
        shrink = [0] * len(shrinkable)

        if target_shrink <= 0:
            return shrink

        weights = []
        for value in shrinkable:
            if value <= 0:
                weights.append(0.0)
            elif mode == "sqrt":
                weights.append(math.sqrt(value))
            else:
                weights.append(float(value))

        total_weight = sum(weights)
        if total_weight <= 0:
            return shrink

        fractions = [0.0] * len(shrinkable)
        used_shrink = 0

        for idx in range(len(shrinkable)):
            if shrinkable[idx] <= 0 or weights[idx] <= 0:
                continue
            exact = (weights[idx] / total_weight) * target_shrink
            whole = min(shrinkable[idx], int(exact))
            shrink[idx] = whole
            fractions[idx] = exact - whole
            used_shrink += whole

        remaining_shrink = target_shrink - used_shrink

        while remaining_shrink > 0:
            best_idx = -1
            best_fraction = -1.0

            for idx in range(len(shrinkable)):
                if shrinkable[idx] - shrink[idx] <= 0:
                    continue
                if (
                    best_idx == -1
                    or fractions[idx] > best_fraction
                    or (fractions[idx] == best_fraction and shrinkable[idx] > shrinkable[best_idx])
                ):
                    best_idx = idx
                    best_fraction = fractions[idx]

            if best_idx == -1:
                break

            shrink[best_idx] += 1
            fractions[best_idx] = 0
            remaining_shrink -= 1

        return shrink

    def _compute_row_heights(self, column_widths: list[int]) -> list[int]:
        horizontal_padding = self._get_horizontal_cell_padding()
        vertical_padding = self._get_vertical_cell_padding()
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
            size = parts[idx] if idx < len(parts) else 1
            has_boundary_after = include_inner if idx < len(parts) - 1 else end_boundary
            cursor += size + (1 if has_boundary_after else 0)
            offsets.append(cursor)

        return offsets

    def _apply_layout_to_views(self, layout: _TableLayout) -> None:
        horizontal_padding = self._get_horizontal_cell_padding()
        vertical_padding = self._get_vertical_cell_padding()

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

                if self._wrap_mode_str == "none":
                    # Don't set wrap width in no-wrap mode
                    pass
                else:
                    cell.text_buffer_view.set_wrap_width(content_width)

                cell.text_buffer_view.set_viewport(0, 0, content_width, content_height)

    # ── Border layout resolution ────────────────────────────────────

    def _resolve_border_layout(self) -> _BorderLayout:
        return _BorderLayout(
            left=self._outer_border,
            right=self._outer_border,
            top=self._outer_border,
            bottom=self._outer_border,
            inner_vertical=self._table_border and self._column_count > 1,
            inner_horizontal=self._table_border and self._row_count > 1,
        )

    def _get_vertical_border_count(self, border_layout: _BorderLayout) -> int:
        count = 0
        if border_layout.left:
            count += 1
        if border_layout.right:
            count += 1
        if border_layout.inner_vertical:
            count += max(0, self._column_count - 1)
        return count

    def _get_horizontal_border_count(self, border_layout: _BorderLayout) -> int:
        count = 0
        if border_layout.top:
            count += 1
        if border_layout.bottom:
            count += 1
        if border_layout.inner_horizontal:
            count += max(0, self._row_count - 1)
        return count

    # ── Padding helpers ─────────────────────────────────────────────

    def _get_horizontal_cell_padding(self) -> int:
        return self._cell_padding * 2

    def _get_vertical_cell_padding(self) -> int:
        return self._cell_padding * 2

    # ── Resolution helpers ──────────────────────────────────────────

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

    # ── Invalidation ────────────────────────────────────────────────

    def _invalidate_layout_and_raster(self, mark_yoga_dirty: bool = True) -> None:
        self._layout_dirty = True
        self._raster_dirty = True
        self._cached_measure_layout = None
        self._cached_measure_width = None
        if mark_yoga_dirty and self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.request_render()

    def _invalidate_raster_only(self) -> None:
        self._raster_dirty = True
        self.request_render()

    # ── Resize ──────────────────────────────────────────────────────

    def _apply_yoga_layout(self) -> None:
        old_w = self._layout_width
        old_h = self._layout_height
        super()._apply_yoga_layout()
        if old_w != self._layout_width or old_h != self._layout_height:
            self._invalidate_layout_and_raster(mark_yoga_dirty=False)
            if self._on_size_change:
                self._on_size_change(self._layout_width, self._layout_height)

    # ── Rendering ───────────────────────────────────────────────────

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        if self._layout_dirty:
            self._rebuild_layout_for_current_width()

        x = self._x
        y = self._y

        if self._show_borders:
            self._draw_borders(buffer, x, y)

        self._draw_cells(buffer, x, y)

        self._raster_dirty = False

    def _draw_borders(self, buffer: Buffer, base_x: int, base_y: int) -> None:
        """Draw grid borders using Python-level drawing."""
        border_layout = self._resolve_border_layout()
        vcount = self._get_vertical_border_count(border_layout)
        hcount = self._get_horizontal_border_count(border_layout)

        if vcount == 0 and hcount == 0:
            return

        chars = _BORDER_CHARS.get(self._border_style_str, _BORDER_CHARS["single"])
        fg = self._border_color_val
        bg = self._border_bg_color if self._border_bg_color.a > 0 else None

        col_offsets = self._table_layout.column_offsets
        row_offsets = self._table_layout.row_offsets
        col_widths = self._table_layout.column_widths
        row_heights = self._table_layout.row_heights
        n_cols = self._column_count
        n_rows = self._row_count

        # Draw horizontal border lines
        for border_idx in range(n_rows + 1):
            # Determine if this border should be drawn
            if border_idx == 0:
                if not border_layout.top:
                    continue
            elif border_idx == n_rows:
                if not border_layout.bottom:
                    continue
            elif not border_layout.inner_horizontal:
                continue

            # Y position of this horizontal border
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

            # Draw horizontal segments and intersections
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

                    ch = self._get_intersection_char(chars, is_top, is_bottom, is_left, is_right)
                    buffer.draw_text(ch, abs_bx, abs_by, fg, bg)

                if col_border_idx < n_cols:
                    if col_border_idx < len(col_offsets):
                        seg_start = col_offsets[col_border_idx] + 1
                    else:
                        continue
                    seg_width = (
                        col_widths[col_border_idx] if col_border_idx < len(col_widths) else 1
                    )
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

    def _get_intersection_char(
        self, chars: dict, is_top: bool, is_bottom: bool, is_left: bool, is_right: bool
    ) -> str:
        """Get the appropriate intersection character based on position."""
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

    def _draw_cells(self, buffer: Buffer, base_x: int, base_y: int) -> None:
        """Draw all cell contents using native text buffer views."""
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
                            text, base_x + cell_x, base_y + cell_y, self._default_fg, None
                        )

    # ── Destruction ─────────────────────────────────────────────────

    def destroy(self) -> None:
        self._cells.clear()
        self._prev_cell_content.clear()
        self._row_count = 0
        self._column_count = 0
        super().destroy()


__all__ = ["TextTableRenderable"]
