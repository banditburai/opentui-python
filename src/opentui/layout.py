"""Yoga layout wrapper for OpenTUI Python.

This module wraps yoga-python to provide flexbox layout for terminal UIs.
Uses character-based units (not pixels) to match terminal grid.
"""

from __future__ import annotations

import math
from typing import Any

import yoga

# Global yoga config - created once and reused.
# Typed as Any because yoga-python (nanobind C++ extension) has incomplete stubs.
_config: Any = None


def _get_config() -> Any:
    """Get or create the global yoga config."""
    global _config
    if _config is None:
        _config = yoga.Config()
        _config.use_web_defaults = False
        _config.point_scale_factor = 1.0  # 1 yoga unit = 1 character
    return _config


def create_node() -> yoga.Node:
    """Create a new yoga node with the global config."""
    return yoga.Node(_get_config())


FLEX_DIRECTION_MAP = {
    "row": yoga.FlexDirection.Row,
    "column": yoga.FlexDirection.Column,
    "row-reverse": yoga.FlexDirection.RowReverse,
    "column-reverse": yoga.FlexDirection.ColumnReverse,
}

JUSTIFY_MAP = {
    "flex-start": yoga.Justify.FlexStart,
    "flex-end": yoga.Justify.FlexEnd,
    "center": yoga.Justify.Center,
    "space-between": yoga.Justify.SpaceBetween,
    "space-around": yoga.Justify.SpaceAround,
    "space-evenly": yoga.Justify.SpaceEvenly,
}

ALIGN_MAP = {
    "stretch": yoga.Align.Stretch,
    "flex-start": yoga.Align.FlexStart,
    "flex-end": yoga.Align.FlexEnd,
    "center": yoga.Align.Center,
    "baseline": yoga.Align.Baseline,
    "auto": yoga.Align.Auto,
}

# Edge constants for padding/margin
EDGE_MAP = {
    "top": yoga.Edge.Top,
    "right": yoga.Edge.Right,
    "bottom": yoga.Edge.Bottom,
    "left": yoga.Edge.Left,
    "start": yoga.Edge.Start,
    "end": yoga.Edge.End,
    "horizontal": yoga.Edge.Horizontal,
    "vertical": yoga.Edge.Vertical,
    "all": yoga.Edge.All,
}

WRAP_MAP = {
    "nowrap": yoga.Wrap.NoWrap,
    "wrap": yoga.Wrap.Wrap,
    "wrap-reverse": yoga.Wrap.WrapReverse,
}

OVERFLOW_MAP = {
    "visible": yoga.Overflow.Visible,
    "hidden": yoga.Overflow.Hidden,
    "scroll": yoga.Overflow.Scroll,
}

POSITION_TYPE_MAP = {
    "relative": yoga.PositionType.Relative,
    "absolute": yoga.PositionType.Absolute,
}


# ---------------------------------------------------------------------------
# Yoga option parsers
# ---------------------------------------------------------------------------


def parse_align(value: str | None) -> yoga.Align:
    """Parse an align string to a yoga Align enum. Default: Auto."""
    if value is None:
        return yoga.Align.Auto
    match value.lower():
        case "auto":
            return yoga.Align.Auto
        case "flex-start":
            return yoga.Align.FlexStart
        case "center":
            return yoga.Align.Center
        case "flex-end":
            return yoga.Align.FlexEnd
        case "stretch":
            return yoga.Align.Stretch
        case "baseline":
            return yoga.Align.Baseline
        case "space-between":
            return yoga.Align.SpaceBetween
        case "space-around":
            return yoga.Align.SpaceAround
        case "space-evenly":
            return yoga.Align.SpaceEvenly
        case _:
            return yoga.Align.Auto


def parse_align_items(value: str | None) -> yoga.Align:
    """Parse an align-items string to a yoga Align enum. Default: Stretch."""
    if value is None:
        return yoga.Align.Stretch
    match value.lower():
        case "auto":
            return yoga.Align.Auto
        case "flex-start":
            return yoga.Align.FlexStart
        case "center":
            return yoga.Align.Center
        case "flex-end":
            return yoga.Align.FlexEnd
        case "stretch":
            return yoga.Align.Stretch
        case "baseline":
            return yoga.Align.Baseline
        case "space-between":
            return yoga.Align.SpaceBetween
        case "space-around":
            return yoga.Align.SpaceAround
        case "space-evenly":
            return yoga.Align.SpaceEvenly
        case _:
            return yoga.Align.Stretch


def parse_box_sizing(value: str | None) -> yoga.BoxSizing:
    """Parse a box-sizing string. Default: BorderBox."""
    if value is None:
        return yoga.BoxSizing.BorderBox
    match value.lower():
        case "border-box":
            return yoga.BoxSizing.BorderBox
        case "content-box":
            return yoga.BoxSizing.ContentBox
        case _:
            return yoga.BoxSizing.BorderBox


def parse_dimension(value: str | None) -> yoga.Dimension:
    """Parse a dimension string ('width'/'height'). Default: Width."""
    if value is None:
        return yoga.Dimension.Width
    match value.lower():
        case "width":
            return yoga.Dimension.Width
        case "height":
            return yoga.Dimension.Height
        case _:
            return yoga.Dimension.Width


def parse_direction(value: str | None) -> yoga.Direction:
    """Parse a direction string. Default: LTR."""
    if value is None:
        return yoga.Direction.LTR
    match value.lower():
        case "inherit":
            return yoga.Direction.Inherit
        case "ltr":
            return yoga.Direction.LTR
        case "rtl":
            return yoga.Direction.RTL
        case _:
            return yoga.Direction.LTR


def parse_display(value: str | None) -> yoga.Display:
    """Parse a display string. Default: Flex."""
    if value is None:
        return yoga.Display.Flex
    match value.lower():
        case "flex":
            return yoga.Display.Flex
        case "none":
            return yoga.Display.None_
        case "contents":
            return yoga.Display.Contents
        case _:
            return yoga.Display.Flex


def parse_edge(value: str | None) -> yoga.Edge:
    """Parse an edge string. Default: All."""
    if value is None:
        return yoga.Edge.All
    match value.lower():
        case "left":
            return yoga.Edge.Left
        case "top":
            return yoga.Edge.Top
        case "right":
            return yoga.Edge.Right
        case "bottom":
            return yoga.Edge.Bottom
        case "start":
            return yoga.Edge.Start
        case "end":
            return yoga.Edge.End
        case "horizontal":
            return yoga.Edge.Horizontal
        case "vertical":
            return yoga.Edge.Vertical
        case "all":
            return yoga.Edge.All
        case _:
            return yoga.Edge.All


def parse_flex_direction(value: str | None) -> yoga.FlexDirection:
    """Parse a flex-direction string. Default: Column."""
    if value is None:
        return yoga.FlexDirection.Column
    match value.lower():
        case "column":
            return yoga.FlexDirection.Column
        case "column-reverse":
            return yoga.FlexDirection.ColumnReverse
        case "row":
            return yoga.FlexDirection.Row
        case "row-reverse":
            return yoga.FlexDirection.RowReverse
        case _:
            return yoga.FlexDirection.Column


def parse_gutter(value: str | None) -> yoga.Gutter:
    """Parse a gutter string. Default: All."""
    if value is None:
        return yoga.Gutter.All
    match value.lower():
        case "column":
            return yoga.Gutter.Column
        case "row":
            return yoga.Gutter.Row
        case "all":
            return yoga.Gutter.All
        case _:
            return yoga.Gutter.All


def parse_justify(value: str | None) -> yoga.Justify:
    """Parse a justify string. Default: FlexStart."""
    if value is None:
        return yoga.Justify.FlexStart
    match value.lower():
        case "flex-start":
            return yoga.Justify.FlexStart
        case "center":
            return yoga.Justify.Center
        case "flex-end":
            return yoga.Justify.FlexEnd
        case "space-between":
            return yoga.Justify.SpaceBetween
        case "space-around":
            return yoga.Justify.SpaceAround
        case "space-evenly":
            return yoga.Justify.SpaceEvenly
        case _:
            return yoga.Justify.FlexStart


def parse_log_level(value: str | None) -> yoga.LogLevel:
    """Parse a log level string. Default: Info."""
    if value is None:
        return yoga.LogLevel.Info
    match value.lower():
        case "error":
            return yoga.LogLevel.Error
        case "warn":
            return yoga.LogLevel.Warn
        case "info":
            return yoga.LogLevel.Info
        case "debug":
            return yoga.LogLevel.Debug
        case "verbose":
            return yoga.LogLevel.Verbose
        case "fatal":
            return yoga.LogLevel.Fatal
        case _:
            return yoga.LogLevel.Info


def parse_measure_mode(value: str | None) -> yoga.MeasureMode:
    """Parse a measure mode string. Default: Undefined."""
    if value is None:
        return yoga.MeasureMode.Undefined
    match value.lower():
        case "undefined":
            return yoga.MeasureMode.Undefined
        case "exactly":
            return yoga.MeasureMode.Exactly
        case "at-most":
            return yoga.MeasureMode.AtMost
        case _:
            return yoga.MeasureMode.Undefined


def parse_overflow(value: str | None) -> yoga.Overflow:
    """Parse an overflow string. Default: Visible."""
    if value is None:
        return yoga.Overflow.Visible
    match value.lower():
        case "visible":
            return yoga.Overflow.Visible
        case "hidden":
            return yoga.Overflow.Hidden
        case "scroll":
            return yoga.Overflow.Scroll
        case _:
            return yoga.Overflow.Visible


def parse_position_type(value: str | None) -> yoga.PositionType:
    """Parse a position type string. Default for None: Relative, for invalid: Static."""
    if value is None:
        return yoga.PositionType.Relative
    match value.lower():
        case "static":
            return yoga.PositionType.Static
        case "relative":
            return yoga.PositionType.Relative
        case "absolute":
            return yoga.PositionType.Absolute
        case _:
            return yoga.PositionType.Static


def parse_unit(value: str | None) -> yoga.Unit:
    """Parse a unit string. Default: Point."""
    if value is None:
        return yoga.Unit.Point
    match value.lower():
        case "undefined":
            return yoga.Unit.Undefined
        case "point":
            return yoga.Unit.Point
        case "percent":
            return yoga.Unit.Percent
        case "auto":
            return yoga.Unit.Auto
        case _:
            return yoga.Unit.Point


def parse_wrap(value: str | None) -> yoga.Wrap:
    """Parse a wrap string. Default: NoWrap."""
    if value is None:
        return yoga.Wrap.NoWrap
    match value.lower():
        case "no-wrap":
            return yoga.Wrap.NoWrap
        case "wrap":
            return yoga.Wrap.Wrap
        case "wrap-reverse":
            return yoga.Wrap.WrapReverse
        case _:
            return yoga.Wrap.NoWrap


# ---------------------------------------------------------------------------
# Layout dimension parsing (internal)
# ---------------------------------------------------------------------------


def _parse_dimension(value: float | str | None) -> tuple[float | None, str | None]:
    """Parse a dimension value that may be a number, percentage string, or 'auto'.

    Returns:
        Tuple of (value, type) where type is 'point', 'percent', or 'auto'.
    """
    if value is None:
        return None, None
    if isinstance(value, str):
        if value == "auto":
            return None, "auto"
        if value.endswith("%"):
            return float(value[:-1]), "percent"
    return float(value), "point"


def configure_node(
    node: yoga.Node,
    *,
    # Dimensions
    width: float | str | None = None,
    height: float | str | None = None,
    min_width: float | str | None = None,
    min_height: float | str | None = None,
    max_width: float | str | None = None,
    max_height: float | str | None = None,
    # Flex
    flex_grow: float | None = None,
    flex_shrink: float | None = None,
    flex_basis: float | str | None = None,
    flex_direction: str | None = None,
    flex_wrap: str | None = None,
    # Alignment
    justify_content: str | None = None,
    align_items: str | None = None,
    align_self: str | None = None,
    # Gap
    gap: float | None = None,
    row_gap: float | None = None,
    column_gap: float | None = None,
    # Spacing
    padding: float | None = None,
    padding_top: float | None = None,
    padding_right: float | None = None,
    padding_bottom: float | None = None,
    padding_left: float | None = None,
    margin: float | None = None,
    margin_top: float | None = None,
    margin_right: float | None = None,
    margin_bottom: float | None = None,
    margin_left: float | None = None,
    # Display
    display: str | None = None,
    position_type: str | None = None,
    # Overflow
    overflow: str | None = None,
    # Position edges
    top: float | str | None = None,
    right: float | str | None = None,
    bottom: float | str | None = None,
    left: float | str | None = None,
) -> None:
    """Configure a yoga node with layout properties."""

    # Dimensions (support percentage and auto).
    # When None, explicitly reset to auto so stale values from a previous
    # frame (written by _apply_yoga_layout → _configure_yoga_node feedback
    # loop) don't persist and override flex layout.
    if width is not None:
        val, kind = _parse_dimension(width)
        if kind == "percent" and val is not None:
            node.set_width_percent(val)
        elif kind == "auto":
            node.set_width_auto()
        elif val is not None:
            node.width = val
    else:
        node.set_width_auto()
    if height is not None:
        val, kind = _parse_dimension(height)
        if kind == "percent" and val is not None:
            node.set_height_percent(val)
        elif kind == "auto":
            node.set_height_auto()
        elif val is not None:
            node.height = val
    else:
        node.set_height_auto()
    if min_width is not None:
        val, kind = _parse_dimension(min_width)
        if kind == "percent" and val is not None:
            node.set_min_width_percent(val)
        elif val is not None:
            node.min_width = val
    if min_height is not None:
        val, kind = _parse_dimension(min_height)
        if kind == "percent" and val is not None:
            node.set_min_height_percent(val)
        elif val is not None:
            node.min_height = val
    if max_width is not None:
        val, kind = _parse_dimension(max_width)
        if kind == "percent" and val is not None:
            node.set_max_width_percent(val)
        elif val is not None:
            node.max_width = val
    if max_height is not None:
        val, kind = _parse_dimension(max_height)
        if kind == "percent" and val is not None:
            node.set_max_height_percent(val)
        elif val is not None:
            node.max_height = val

    # Flex
    if flex_grow is not None:
        node.flex_grow = flex_grow
    if flex_shrink is not None:
        node.flex_shrink = flex_shrink
    if flex_basis is not None:
        val, kind = _parse_dimension(flex_basis)
        if kind == "percent" and val is not None:
            node.flex_basis = val  # yoga treats as percent via YGValue
        elif kind == "auto":
            node.flex_basis = float("nan")  # yoga auto sentinel
        elif val is not None:
            node.flex_basis = val
    if flex_direction is not None:
        node.flex_direction = FLEX_DIRECTION_MAP.get(flex_direction, yoga.FlexDirection.Column)
    if flex_wrap is not None:
        node.flex_wrap = WRAP_MAP.get(flex_wrap, yoga.Wrap.NoWrap)

    # Alignment
    if justify_content is not None:
        node.justify_content = JUSTIFY_MAP.get(justify_content, yoga.Justify.FlexStart)
    if align_items is not None:
        node.align_items = ALIGN_MAP.get(align_items, yoga.Align.Stretch)
    if align_self is not None:
        node.align_self = ALIGN_MAP.get(align_self, yoga.Align.Auto)

    # Gap
    if gap is not None:
        node.set_gap(yoga.Gutter.All, gap)
    if row_gap is not None:
        node.set_gap(yoga.Gutter.Row, row_gap)
    if column_gap is not None:
        node.set_gap(yoga.Gutter.Column, column_gap)

    # Padding
    if padding is not None:
        node.set_padding(yoga.Edge.All, padding)
    if padding_top is not None:
        node.set_padding(yoga.Edge.Top, padding_top)
    if padding_right is not None:
        node.set_padding(yoga.Edge.Right, padding_right)
    if padding_bottom is not None:
        node.set_padding(yoga.Edge.Bottom, padding_bottom)
    if padding_left is not None:
        node.set_padding(yoga.Edge.Left, padding_left)

    # Margin
    if margin is not None:
        node.set_margin(yoga.Edge.All, margin)
    if margin_top is not None:
        node.set_margin(yoga.Edge.Top, margin_top)
    if margin_right is not None:
        node.set_margin(yoga.Edge.Right, margin_right)
    if margin_bottom is not None:
        node.set_margin(yoga.Edge.Bottom, margin_bottom)
    if margin_left is not None:
        node.set_margin(yoga.Edge.Left, margin_left)

    # Display
    if display is not None:
        node.display = yoga.Display.Flex if display == "flex" else yoga.Display.None_
    if position_type is not None:
        node.position_type = POSITION_TYPE_MAP.get(position_type, yoga.PositionType.Relative)

    # Overflow
    if overflow is not None:
        node.overflow = OVERFLOW_MAP.get(overflow, yoga.Overflow.Visible)

    # Position edges (for absolute positioning)
    if top is not None:
        val, kind = _parse_dimension(top)
        if kind == "percent" and val is not None:
            node.set_position_percent(yoga.Edge.Top, val)
        elif val is not None:
            node.set_position(yoga.Edge.Top, val)
    if right is not None:
        val, kind = _parse_dimension(right)
        if kind == "percent" and val is not None:
            node.set_position_percent(yoga.Edge.Right, val)
        elif val is not None:
            node.set_position(yoga.Edge.Right, val)
    if bottom is not None:
        val, kind = _parse_dimension(bottom)
        if kind == "percent" and val is not None:
            node.set_position_percent(yoga.Edge.Bottom, val)
        elif val is not None:
            node.set_position(yoga.Edge.Bottom, val)
    if left is not None:
        val, kind = _parse_dimension(left)
        if kind == "percent" and val is not None:
            node.set_position_percent(yoga.Edge.Left, val)
        elif val is not None:
            node.set_position(yoga.Edge.Left, val)


def compute_layout(root_node: yoga.Node, width: float, height: float) -> None:
    """Compute layout for the yoga tree.

    Args:
        root_node: The root yoga node
        width: Available width (in character cells)
        height: Available height (in character cells)
    """
    root_node.calculate_layout(width, height, yoga.Direction.LTR)


def get_layout(node: yoga.Node) -> dict[str, float]:
    """Get computed layout from a yoga node.

    Returns:
        Dict with x, y, width, height, and margin values
    """
    return {
        "x": node.layout_left,
        "y": node.layout_top,
        "width": node.layout_width,
        "height": node.layout_height,
        "margin_top": node.layout_margin(yoga.Edge.Top),
        "margin_right": node.layout_margin(yoga.Edge.Right),
        "margin_bottom": node.layout_margin(yoga.Edge.Bottom),
        "margin_left": node.layout_margin(yoga.Edge.Left),
        "padding_top": node.layout_padding(yoga.Edge.Top),
        "padding_right": node.layout_padding(yoga.Edge.Right),
        "padding_bottom": node.layout_padding(yoga.Edge.Bottom),
        "padding_left": node.layout_padding(yoga.Edge.Left),
    }


class ViewportBounds:
    """Axis-aligned rectangle describing a viewport region."""

    __slots__ = ("x", "y", "width", "height")

    def __init__(self, x: float, y: float, width: float, height: float) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class ViewportObject:
    """Minimal interface for objects that can be viewport-culled.

    Subclasses or instances may add extra attributes (e.g. ``id``).
    """

    __slots__ = ("x", "y", "width", "height", "z_index", "__dict__")

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        z_index: float = 0,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.z_index = z_index


def get_objects_in_viewport(
    viewport: ViewportBounds,
    objects: list,
    direction: str = "column",
    padding: float = 10,
    min_trigger_size: int = 16,
) -> list:
    """Return objects that overlap with the viewport bounds.

    Objects must be pre-sorted by their start position (y for column, x for row).
    Uses binary search for efficient culling on the primary axis, then filters
    on the cross axis. Results are sorted by z_index.
    """
    if viewport.width <= 0 or viewport.height <= 0:
        return []

    if len(objects) == 0:
        return []

    if len(objects) < min_trigger_size:
        return list(objects)

    vp_top = viewport.y - padding
    vp_bottom = viewport.y + viewport.height + padding
    vp_left = viewport.x - padding
    vp_right = viewport.x + viewport.width + padding

    is_row = direction == "row"
    total = len(objects)

    vp_start = vp_left if is_row else vp_top
    vp_end = vp_right if is_row else vp_bottom

    # Binary search to find any child that overlaps along the primary axis
    lo = 0
    hi = total - 1
    candidate = -1
    while lo <= hi:
        mid = (lo + hi) >> 1
        c = objects[mid]
        start = c.x if is_row else c.y
        end = (c.x + c.width) if is_row else (c.y + c.height)

        if end < vp_start:
            lo = mid + 1
        elif start > vp_end:
            hi = mid - 1
        else:
            candidate = mid
            break

    if candidate == -1:
        candidate = lo - 1 if lo > 0 else 0

    # Expand left — handle large objects that start early but extend far
    max_look_behind = 50
    left = candidate
    gap_count = 0
    while left - 1 >= 0:
        prev = objects[left - 1]
        prev_end = (prev.x + prev.width) if is_row else (prev.y + prev.height)
        if prev_end <= vp_start:
            gap_count += 1
            if gap_count >= max_look_behind:
                break
        else:
            gap_count = 0
        left -= 1

    # Expand right
    right = candidate + 1
    while right < total:
        nxt = objects[right]
        if (nxt.x if is_row else nxt.y) >= vp_end:
            break
        right += 1

    # Collect candidates that also overlap on the cross axis
    visible: list = []
    for i in range(left, right):
        child = objects[i]
        start = child.x if is_row else child.y
        end = (child.x + child.width) if is_row else (child.y + child.height)

        if end <= vp_start:
            continue
        if start >= vp_end:
            break

        # Cross-axis overlap check
        if is_row:
            if child.y + child.height < vp_top:
                continue
            if child.y > vp_bottom:
                continue
        else:
            if child.x + child.width < vp_left:
                continue
            if child.x > vp_right:
                continue

        visible.append(child)

    if len(visible) > 1:
        visible.sort(key=lambda o: o.z_index)

    return visible


# ---------------------------------------------------------------------------
# set_yoga_prop — Renderable property setters for yoga nodes
# ---------------------------------------------------------------------------


def _is_valid_percentage(value: Any) -> bool:
    """Check if value is a valid percentage string like "50%"."""
    if isinstance(value, str) and value.endswith("%"):
        try:
            float(value[:-1])
            return True
        except (ValueError, TypeError):
            return False
    return False


def _is_padding_type(value: Any) -> bool:
    """Check if value is a valid padding type (number or percentage)."""
    if isinstance(value, int | float):
        return not (isinstance(value, float) and math.isnan(value))
    return _is_valid_percentage(value)


def _is_margin_type(value: Any) -> bool:
    """Check if value is a valid margin type (number, "auto", or percentage)."""
    if isinstance(value, int | float):
        return not (isinstance(value, float) and math.isnan(value))
    if value == "auto":
        return True
    return _is_valid_percentage(value)


def _is_size_type(value: Any) -> bool:
    """Check if value is a valid size type (number, percentage, or None/undefined)."""
    if value is None:
        return True
    if isinstance(value, int | float):
        return not (isinstance(value, float) and math.isnan(value))
    return _is_valid_percentage(value)


def _is_dimension_type(value: Any) -> bool:
    """Check if value is a valid dimension type (number, "auto", or percentage)."""
    if isinstance(value, int | float):
        return not (isinstance(value, float) and math.isnan(value))
    if value == "auto":
        return True
    return _is_valid_percentage(value)


def _is_flex_basis_type(value: Any) -> bool:
    """Check if value is a valid flex basis type (number, "auto", or None/undefined)."""
    if value is None or value == "auto":
        return True
    if isinstance(value, int | float):
        return not (isinstance(value, float) and math.isnan(value))
    return False


def _set_dimension_prop(
    node: Any,
    value: Any,
    set_point: Any,
    set_percent: Any,
    set_auto: Any,
) -> None:
    """Set a dimension property (width/height) supporting number, percent, and auto."""
    if value is None:
        if set_auto is not None:
            set_auto()
        return
    if isinstance(value, str):
        if value == "auto":
            if set_auto is not None:
                set_auto()
            return
        if value.endswith("%"):
            pct = float(value[:-1])
            set_percent(pct)
            return
    set_point(float(value))


def _set_edge_prop(
    node: Any,
    edge: Any,
    value: Any,
    set_fn: Any,
    set_percent_fn: Any = None,
    set_auto_fn: Any = None,
) -> None:
    """Set an edge-based property (margin/padding) supporting number, percent, auto."""
    if isinstance(value, str):
        if value == "auto" and set_auto_fn is not None:
            set_auto_fn(edge)
            return
        if value.endswith("%") and set_percent_fn is not None:
            pct = float(value[:-1])
            set_percent_fn(edge, pct)
            return
    set_fn(edge, float(value))


def set_yoga_prop(node: Any, prop_name: str, value: Any) -> None:
    """Set a yoga property on a node by name.

    Accepts a yoga Node, a property name string (camelCase), and a value.
    Uses the parse_* functions for enum conversion and handles None/undefined
    by applying sensible defaults matching OpenTUI core behavior.

    Args:
        node: A yoga.Node instance
        prop_name: Property name in camelCase (e.g. "flexGrow", "width", "paddingTop")
        value: The value to set; None means reset to default
    """
    # --- Flex numeric properties ---
    if prop_name == "flexGrow":
        if value is None:
            node.flex_grow = 0
        else:
            node.flex_grow = float(value)
        return

    if prop_name == "flexShrink":
        if value is None:
            node.flex_shrink = 1
        else:
            node.flex_shrink = float(value)
        return

    # --- Flex enum properties ---
    if prop_name == "flexDirection":
        node.flex_direction = parse_flex_direction(value)
        return

    if prop_name == "flexWrap":
        node.flex_wrap = parse_wrap(value)
        return

    if prop_name == "alignItems":
        node.align_items = parse_align_items(value)
        return

    if prop_name == "justifyContent":
        node.justify_content = parse_justify(value)
        return

    if prop_name == "alignSelf":
        node.align_self = parse_align(value)
        return

    if prop_name == "alignContent":
        node.align_content = parse_align(value)
        return

    if prop_name == "overflow":
        node.overflow = parse_overflow(value)
        return

    if prop_name == "position":
        node.position_type = parse_position_type(value)
        return

    if prop_name == "display":
        node.display = parse_display(value)
        return

    # --- Flex basis ---
    if prop_name == "flexBasis":
        if value is None or value == "auto":
            # Reset to undefined (yoga-python has no set_flex_basis_auto)
            node.flex_basis = float("nan")
            return
        if _is_flex_basis_type(value):
            node.flex_basis = float(value)
        return

    # --- Dimension properties (width, height) ---
    if prop_name == "width":
        if value is None:
            node.set_width_auto()
            return
        if _is_dimension_type(value):
            _set_dimension_prop(
                node,
                value,
                set_point=lambda v: setattr(node, "width", v),
                set_percent=node.set_width_percent,
                set_auto=node.set_width_auto,
            )
        return

    if prop_name == "height":
        if value is None:
            node.set_height_auto()
            return
        if _is_dimension_type(value):
            _set_dimension_prop(
                node,
                value,
                set_point=lambda v: setattr(node, "height", v),
                set_percent=node.set_height_percent,
                set_auto=node.set_height_auto,
            )
        return

    # --- Min/max dimension properties ---
    if prop_name == "minWidth":
        if _is_size_type(value):
            if value is None:
                node.min_width = float("nan")
                return
            if _is_valid_percentage(value):
                node.set_min_width_percent(float(value[:-1]))
            else:
                node.min_width = float(value)
        return

    if prop_name == "maxWidth":
        if _is_size_type(value):
            if value is None:
                node.max_width = float("nan")
                return
            if _is_valid_percentage(value):
                node.set_max_width_percent(float(value[:-1]))
            else:
                node.max_width = float(value)
        return

    if prop_name == "minHeight":
        if _is_size_type(value):
            if value is None:
                node.min_height = float("nan")
                return
            if _is_valid_percentage(value):
                node.set_min_height_percent(float(value[:-1]))
            else:
                node.min_height = float(value)
        return

    if prop_name == "maxHeight":
        if _is_size_type(value):
            if value is None:
                node.max_height = float("nan")
                return
            if _is_valid_percentage(value):
                node.set_max_height_percent(float(value[:-1]))
            else:
                node.max_height = float(value)
        return

    # --- Margin properties ---
    if prop_name == "margin":
        if value is None:
            node.set_margin(yoga.Edge.All, 0)
            return
        if _is_margin_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.All,
                value,
                set_fn=node.set_margin,
                set_percent_fn=node.set_margin_percent,
                set_auto_fn=node.set_margin_auto,
            )
        return

    if prop_name == "marginX":
        if value is None:
            node.set_margin(yoga.Edge.Horizontal, 0)
            return
        if _is_margin_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Horizontal,
                value,
                set_fn=node.set_margin,
                set_percent_fn=node.set_margin_percent,
                set_auto_fn=node.set_margin_auto,
            )
        return

    if prop_name == "marginY":
        if value is None:
            node.set_margin(yoga.Edge.Vertical, 0)
            return
        if _is_margin_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Vertical,
                value,
                set_fn=node.set_margin,
                set_percent_fn=node.set_margin_percent,
                set_auto_fn=node.set_margin_auto,
            )
        return

    if prop_name == "marginTop":
        if value is None:
            node.set_margin(yoga.Edge.Top, 0)
            return
        if _is_margin_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Top,
                value,
                set_fn=node.set_margin,
                set_percent_fn=node.set_margin_percent,
                set_auto_fn=node.set_margin_auto,
            )
        return

    if prop_name == "marginRight":
        if value is None:
            node.set_margin(yoga.Edge.Right, 0)
            return
        if _is_margin_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Right,
                value,
                set_fn=node.set_margin,
                set_percent_fn=node.set_margin_percent,
                set_auto_fn=node.set_margin_auto,
            )
        return

    if prop_name == "marginBottom":
        if value is None:
            node.set_margin(yoga.Edge.Bottom, 0)
            return
        if _is_margin_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Bottom,
                value,
                set_fn=node.set_margin,
                set_percent_fn=node.set_margin_percent,
                set_auto_fn=node.set_margin_auto,
            )
        return

    if prop_name == "marginLeft":
        if value is None:
            node.set_margin(yoga.Edge.Left, 0)
            return
        if _is_margin_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Left,
                value,
                set_fn=node.set_margin,
                set_percent_fn=node.set_margin_percent,
                set_auto_fn=node.set_margin_auto,
            )
        return

    # --- Padding properties ---
    if prop_name == "padding":
        if value is None:
            node.set_padding(yoga.Edge.All, 0)
            return
        if _is_padding_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.All,
                value,
                set_fn=node.set_padding,
                set_percent_fn=node.set_padding_percent,
            )
        return

    if prop_name == "paddingX":
        if value is None:
            node.set_padding(yoga.Edge.Horizontal, 0)
            return
        if _is_padding_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Horizontal,
                value,
                set_fn=node.set_padding,
                set_percent_fn=node.set_padding_percent,
            )
        return

    if prop_name == "paddingY":
        if value is None:
            node.set_padding(yoga.Edge.Vertical, 0)
            return
        if _is_padding_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Vertical,
                value,
                set_fn=node.set_padding,
                set_percent_fn=node.set_padding_percent,
            )
        return

    if prop_name == "paddingTop":
        if value is None:
            node.set_padding(yoga.Edge.Top, 0)
            return
        if _is_padding_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Top,
                value,
                set_fn=node.set_padding,
                set_percent_fn=node.set_padding_percent,
            )
        return

    if prop_name == "paddingRight":
        if value is None:
            node.set_padding(yoga.Edge.Right, 0)
            return
        if _is_padding_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Right,
                value,
                set_fn=node.set_padding,
                set_percent_fn=node.set_padding_percent,
            )
        return

    if prop_name == "paddingBottom":
        if value is None:
            node.set_padding(yoga.Edge.Bottom, 0)
            return
        if _is_padding_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Bottom,
                value,
                set_fn=node.set_padding,
                set_percent_fn=node.set_padding_percent,
            )
        return

    if prop_name == "paddingLeft":
        if value is None:
            node.set_padding(yoga.Edge.Left, 0)
            return
        if _is_padding_type(value):
            _set_edge_prop(
                node,
                yoga.Edge.Left,
                value,
                set_fn=node.set_padding,
                set_percent_fn=node.set_padding_percent,
            )
        return

    # --- Gap properties ---
    if prop_name == "gap":
        if value is None:
            node.set_gap(yoga.Gutter.All, 0)
        else:
            node.set_gap(yoga.Gutter.All, float(value))
        return

    if prop_name == "rowGap":
        if value is None:
            node.set_gap(yoga.Gutter.Row, 0)
        else:
            node.set_gap(yoga.Gutter.Row, float(value))
        return

    if prop_name == "columnGap":
        if value is None:
            node.set_gap(yoga.Gutter.Column, 0)
        else:
            node.set_gap(yoga.Gutter.Column, float(value))
        return


# ---------------------------------------------------------------------------
# Public validation functions for renderable options
# ---------------------------------------------------------------------------

# Public aliases for the private helpers
is_valid_percentage = _is_valid_percentage
is_padding_type = _is_padding_type
is_margin_type = _is_margin_type
is_size_type = _is_size_type
is_dimension_type = _is_dimension_type
is_flex_basis_type = _is_flex_basis_type


def is_position_type(value: Any) -> bool:
    """Check if value is a valid position type (number, "auto", or percentage)."""
    if isinstance(value, int | float):
        return not (isinstance(value, float) and math.isnan(value))
    if value == "auto":
        return True
    return _is_valid_percentage(value)


def is_position_type_value(value: Any) -> bool:
    """Check if value is a valid CSS position type string ("relative" or "absolute")."""
    return value in ("relative", "absolute")


def is_overflow_type(value: Any) -> bool:
    """Check if value is a valid overflow type string ("visible", "hidden", or "scroll")."""
    return value in ("visible", "hidden", "scroll")


def validate_options(name: str, options: dict[str, Any]) -> None:
    """Validate renderable options.

    Raises TypeError for invalid width/height values.
    """
    width = options.get("width")
    height = options.get("height")
    if isinstance(width, int | float) and width < 0:
        raise TypeError(f"{name}: width must be non-negative, got {width}")
    if isinstance(height, int | float) and height < 0:
        raise TypeError(f"{name}: height must be non-negative, got {height}")


__all__ = [
    "create_node",
    "configure_node",
    "compute_layout",
    "get_layout",
    "set_yoga_prop",
    "ViewportBounds",
    "ViewportObject",
    "get_objects_in_viewport",
    "FLEX_DIRECTION_MAP",
    "JUSTIFY_MAP",
    "ALIGN_MAP",
    "EDGE_MAP",
    "WRAP_MAP",
    "OVERFLOW_MAP",
    "POSITION_TYPE_MAP",
    "parse_align",
    "parse_align_items",
    "parse_box_sizing",
    "parse_dimension",
    "parse_direction",
    "parse_display",
    "parse_edge",
    "parse_flex_direction",
    "parse_gutter",
    "parse_justify",
    "parse_log_level",
    "parse_measure_mode",
    "parse_overflow",
    "parse_position_type",
    "parse_unit",
    "parse_wrap",
    "is_valid_percentage",
    "is_padding_type",
    "is_margin_type",
    "is_size_type",
    "is_dimension_type",
    "is_flex_basis_type",
    "is_position_type",
    "is_position_type_value",
    "is_overflow_type",
    "validate_options",
]
