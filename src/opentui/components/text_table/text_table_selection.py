from __future__ import annotations

from ..text_renderable_utils import get_scroll_adjusted_position


def should_start_selection(table, x: int, y: int) -> bool:
    if not table._selectable_flag:
        return False
    table._ensure_layout_ready()
    return get_cell_at_local_position(table, x - table._x, y - table._y) is not None


def has_selection(table) -> bool:
    for row in table._cells:
        for cell in row:
            if cell.text_buffer_view.has_selection():
                return True
    return False


def get_selection(table) -> dict[str, int] | None:
    for row in table._cells:
        for cell in row:
            sel = cell.text_buffer_view.get_selection()
            if sel:
                return sel
    return None


def get_selected_text(table) -> str:
    selected_rows: list[str] = []
    for row_idx in range(table._row_count):
        row_selections: list[str] = []
        for col_idx in range(table._column_count):
            cell = (
                table._cells[row_idx][col_idx]
                if row_idx < len(table._cells) and col_idx < len(table._cells[row_idx])
                else None
            )
            if not cell or not cell.text_buffer_view.has_selection():
                continue
            selected_text = cell.text_buffer_view.get_selected_text()
            if selected_text:
                row_selections.append(selected_text)
        if row_selections:
            selected_rows.append("\t".join(row_selections))
    return "\n".join(selected_rows)


def on_selection_changed(table, selection) -> bool:
    table._ensure_layout_ready()

    local_selection = convert_global_to_local_selection(table, selection)
    table._last_local_selection = local_selection

    if not local_selection or not local_selection.get("is_active"):
        reset_cell_selections(table)
        table._last_selection_mode = None
    else:
        is_start = getattr(selection, "is_start", False) if selection else False
        apply_selection_to_cells(table, local_selection, is_start)

    return has_selection(table)


def convert_global_to_local_selection(table, selection) -> dict | None:
    if selection is None:
        return None
    if isinstance(selection, dict):
        anchor_x = selection.get("anchorX", selection.get("anchor_x", 0))
        anchor_y = selection.get("anchorY", selection.get("anchor_y", 0))
        focus_x = selection.get("focusX", selection.get("focus_x", 0))
        focus_y = selection.get("focusY", selection.get("focus_y", 0))
        is_active = selection.get("isActive", selection.get("is_active", False))
    else:
        anchor = selection.anchor
        focus = selection.focus
        anchor_x = anchor["x"]
        anchor_y = anchor["y"]
        focus_x = focus["x"]
        focus_y = focus["y"]
        is_active = getattr(selection, "is_active", True)

    screen_x, screen_y = get_scroll_adjusted_position(table)

    return {
        "anchor_x": anchor_x - screen_x,
        "anchor_y": anchor_y - screen_y,
        "focus_x": focus_x - screen_x,
        "focus_y": focus_y - screen_y,
        "is_active": is_active,
    }


def apply_selection_to_cells(table, local_selection: dict, is_start: bool) -> None:
    min_sel_y = min(local_selection["anchor_y"], local_selection["focus_y"])
    max_sel_y = max(local_selection["anchor_y"], local_selection["focus_y"])

    first_row = find_row_for_local_y(table, min_sel_y)
    last_row = find_row_for_local_y(table, max_sel_y)
    resolution = resolve_selection_resolution(table, local_selection)
    mode_changed = table._last_selection_mode != resolution["mode"]
    table._last_selection_mode = resolution["mode"]
    lock_to_anchor_column = (
        resolution["mode"] == "column-locked" and resolution.get("anchor_column") is not None
    )

    for row_idx in range(table._row_count):
        if row_idx < first_row or row_idx > last_row:
            reset_row_selection(table, row_idx)
            continue

        cell_top = (
            (table._table_layout.row_offsets[row_idx] if row_idx < len(table._table_layout.row_offsets) else 0)
            + 1
            + table._cell_padding
        )

        for col_idx in range(table._column_count):
            cell = (
                table._cells[row_idx][col_idx]
                if row_idx < len(table._cells) and col_idx < len(table._cells[row_idx])
                else None
            )
            if not cell:
                continue

            if lock_to_anchor_column and col_idx != resolution.get("anchor_column"):
                cell.text_buffer_view.reset_local_selection()
                continue

            cell_left = (
                (table._table_layout.column_offsets[col_idx] if col_idx < len(table._table_layout.column_offsets) else 0)
                + 1
                + table._cell_padding
            )
            anchor_x = local_selection["anchor_x"] - cell_left
            anchor_y = local_selection["anchor_y"] - cell_top
            focus_x = local_selection["focus_x"] - cell_left
            focus_y = local_selection["focus_y"] - cell_top

            anchor_cell = resolution.get("anchor_cell")
            is_anchor_cell = (
                anchor_cell is not None and anchor_cell[0] == row_idx and anchor_cell[1] == col_idx
            )
            force_set = is_anchor_cell and resolution["mode"] != "single-cell"

            if force_set:
                col_width = table._table_layout.column_widths[col_idx] if col_idx < len(table._table_layout.column_widths) else 1
                row_height = table._table_layout.row_heights[row_idx] if row_idx < len(table._table_layout.row_heights) else 1
                content_width = max(1, col_width - table._get_cell_padding())
                content_height = max(1, row_height - table._get_cell_padding())
                anchor_x = -1
                anchor_y = 0
                focus_x = content_width
                focus_y = content_height

            if is_start or mode_changed or force_set:
                cell.text_buffer_view.set_local_selection(
                    anchor_x, anchor_y, focus_x, focus_y,
                    bg_color=table._selection_bg_color, fg_color=table._selection_fg_color,
                )
            else:
                cell.text_buffer_view.update_local_selection(
                    anchor_x, anchor_y, focus_x, focus_y,
                    bg_color=table._selection_bg_color, fg_color=table._selection_fg_color,
                )


def resolve_selection_resolution(table, local_selection: dict) -> dict:
    anchor_cell = get_cell_at_local_position(table, local_selection["anchor_x"], local_selection["anchor_y"])
    focus_cell = get_cell_at_local_position(table, local_selection["focus_x"], local_selection["focus_y"])
    anchor_column = anchor_cell[1] if anchor_cell else get_column_at_local_x(table, local_selection["anchor_x"])

    if (
        anchor_cell is not None
        and focus_cell is not None
        and anchor_cell[0] == focus_cell[0]
        and anchor_cell[1] == focus_cell[1]
    ):
        return {"mode": "single-cell", "anchor_cell": anchor_cell, "anchor_column": anchor_column}

    focus_column = get_column_at_local_x(table, local_selection["focus_x"])
    if anchor_column is not None and focus_column == anchor_column:
        return {"mode": "column-locked", "anchor_cell": anchor_cell, "anchor_column": anchor_column}

    return {"mode": "grid", "anchor_cell": anchor_cell, "anchor_column": anchor_column}


def get_column_at_local_x(table, local_x: int) -> int | None:
    if table._column_count == 0 or local_x < 0 or local_x >= table._table_layout.table_width:
        return None
    for col_idx in range(table._column_count):
        col_start = (table._table_layout.column_offsets[col_idx] if col_idx < len(table._table_layout.column_offsets) else 0) + 1
        col_width = table._table_layout.column_widths[col_idx] if col_idx < len(table._table_layout.column_widths) else 1
        col_end = col_start + col_width - 1
        if col_start <= local_x <= col_end:
            return col_idx
    return None


def find_row_for_local_y(table, local_y: int) -> int:
    if table._row_count == 0 or local_y < 0:
        return 0
    for row_idx in range(table._row_count):
        row_start = (table._table_layout.row_offsets[row_idx] if row_idx < len(table._table_layout.row_offsets) else 0) + 1
        row_height = table._table_layout.row_heights[row_idx] if row_idx < len(table._table_layout.row_heights) else 1
        row_end = row_start + row_height - 1
        if local_y <= row_end:
            return row_idx
    return table._row_count - 1


def reset_row_selection(table, row_idx: int) -> None:
    if row_idx >= len(table._cells):
        return
    for cell in table._cells[row_idx]:
        cell.text_buffer_view.reset_local_selection()


def reset_cell_selections(table) -> None:
    for row_idx in range(table._row_count):
        reset_row_selection(table, row_idx)


def get_cell_at_local_position(table, local_x: int, local_y: int) -> tuple[int, int] | None:
    if table._row_count == 0 or table._column_count == 0:
        return None
    if local_x < 0 or local_y < 0:
        return None
    if local_x >= table._table_layout.table_width or local_y >= table._table_layout.table_height:
        return None

    row_idx = -1
    for idx in range(table._row_count):
        top = (table._table_layout.row_offsets[idx] if idx < len(table._table_layout.row_offsets) else 0) + 1
        row_h = table._table_layout.row_heights[idx] if idx < len(table._table_layout.row_heights) else 1
        bottom = top + row_h - 1
        if top <= local_y <= bottom:
            row_idx = idx
            break
    if row_idx < 0:
        return None

    col_idx = -1
    for idx in range(table._column_count):
        left = (table._table_layout.column_offsets[idx] if idx < len(table._table_layout.column_offsets) else 0) + 1
        col_w = table._table_layout.column_widths[idx] if idx < len(table._table_layout.column_widths) else 1
        right = left + col_w - 1
        if left <= local_x <= right:
            col_idx = idx
            break
    if col_idx < 0:
        return None
    return (row_idx, col_idx)


def setup_mouse_handlers(table) -> None:
    def _on_down(event) -> None:
        x, y = event.x, event.y
        if not should_start_selection(table, x, y):
            return
        table._is_selecting = True
        table._selection_anchor = (x, y)
        on_selection_changed(
            table,
            {"anchorX": x, "anchorY": y, "focusX": x, "focusY": y, "isActive": True, "is_start": True},
        )

    def _on_drag(event) -> None:
        if not table._is_selecting or table._selection_anchor is None:
            return
        ax, ay = table._selection_anchor
        on_selection_changed(
            table,
            {"anchorX": ax, "anchorY": ay, "focusX": event.x, "focusY": event.y, "isActive": True, "is_start": False},
        )

    def _on_drag_end(event) -> None:
        if table._is_selecting:
            table._is_selecting = False

    def _on_up(event) -> None:
        if table._is_selecting:
            table._is_selecting = False

    table._on_mouse_down = _on_down
    table._on_mouse_drag = _on_drag
    table._on_mouse_drag_end = _on_drag_end
    table._on_mouse_up = _on_up


__all__ = ["get_selected_text", "get_selection", "has_selection", "on_selection_changed", "setup_mouse_handlers", "should_start_selection"]
