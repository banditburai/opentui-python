"""Yoga layout wrapper for OpenTUI — flexbox in character-cell units."""

from __future__ import annotations

import math
from typing import Any

import yoga

_config: Any = None


def _get_config() -> Any:
    global _config
    if _config is None:
        _config = yoga.Config()
        _config.use_web_defaults = False
        _config.point_scale_factor = 1.0
    return _config


def create_node() -> yoga.Node:
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


_ALIGN_MAP = {
    "auto": yoga.Align.Auto,
    "flex-start": yoga.Align.FlexStart,
    "center": yoga.Align.Center,
    "flex-end": yoga.Align.FlexEnd,
    "stretch": yoga.Align.Stretch,
    "baseline": yoga.Align.Baseline,
    "space-between": yoga.Align.SpaceBetween,
    "space-around": yoga.Align.SpaceAround,
    "space-evenly": yoga.Align.SpaceEvenly,
}


def parse_align(value: str | None, default: yoga.Align = yoga.Align.Auto) -> yoga.Align:
    if value is None:
        return default
    return _ALIGN_MAP.get(value.lower(), default)


def parse_align_items(value: str | None) -> yoga.Align:
    return parse_align(value, yoga.Align.Stretch)


def parse_box_sizing(value: str | None) -> yoga.BoxSizing:
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


def _parse_dimension(value: float | str | None) -> tuple[float | None, str | None]:
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
    width: float | str | None = None,
    height: float | str | None = None,
    min_width: float | str | None = None,
    min_height: float | str | None = None,
    max_width: float | str | None = None,
    max_height: float | str | None = None,
    flex_grow: float | None = None,
    flex_shrink: float | None = None,
    flex_basis: float | str | None = None,
    flex_direction: str | None = None,
    flex_wrap: str | None = None,
    justify_content: str | None = None,
    align_items: str | None = None,
    align_self: str | None = None,
    gap: float | None = None,
    row_gap: float | None = None,
    column_gap: float | None = None,
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
    display: str | None = None,
    position_type: str | None = None,
    overflow: str | None = None,
    top: float | str | None = None,
    right: float | str | None = None,
    bottom: float | str | None = None,
    left: float | str | None = None,
) -> None:
    # When None, reset to auto to avoid stale values from a previous
    # frame persisting and overriding flex layout.

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

    if justify_content is not None:
        node.justify_content = JUSTIFY_MAP.get(justify_content, yoga.Justify.FlexStart)
    if align_items is not None:
        node.align_items = ALIGN_MAP.get(align_items, yoga.Align.Stretch)
    if align_self is not None:
        node.align_self = ALIGN_MAP.get(align_self, yoga.Align.Auto)

    if gap is not None:
        node.set_gap(yoga.Gutter.All, gap)
    if row_gap is not None:
        node.set_gap(yoga.Gutter.Row, row_gap)
    if column_gap is not None:
        node.set_gap(yoga.Gutter.Column, column_gap)

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

    if display is not None:
        node.display = yoga.Display.Flex if display == "flex" else yoga.Display.None_
    if position_type is not None:
        node.position_type = POSITION_TYPE_MAP.get(position_type, yoga.PositionType.Relative)

    if overflow is not None:
        node.overflow = OVERFLOW_MAP.get(overflow, yoga.Overflow.Visible)

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
    root_node.calculate_layout(width, height, yoga.Direction.LTR)


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

    if not objects:
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


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, int | float) and not (isinstance(value, float) and math.isnan(value))


def _is_valid_percentage(value: Any) -> bool:
    if isinstance(value, str) and value.endswith("%"):
        try:
            float(value[:-1])
            return True
        except (ValueError, TypeError):
            return False
    return False


def _is_padding_type(value: Any) -> bool:
    return _is_finite_number(value) or _is_valid_percentage(value)


def _is_margin_type(value: Any) -> bool:
    return _is_finite_number(value) or value == "auto" or _is_valid_percentage(value)


def _is_size_type(value: Any) -> bool:
    return value is None or _is_finite_number(value) or _is_valid_percentage(value)


def _is_dimension_type(value: Any) -> bool:
    return _is_finite_number(value) or value == "auto" or _is_valid_percentage(value)


def _is_flex_basis_type(value: Any) -> bool:
    return value is None or value == "auto" or _is_finite_number(value)


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


_MARGIN_EDGES: dict[str, Any] = {
    "margin": yoga.Edge.All,
    "marginX": yoga.Edge.Horizontal,
    "marginY": yoga.Edge.Vertical,
    "marginTop": yoga.Edge.Top,
    "marginRight": yoga.Edge.Right,
    "marginBottom": yoga.Edge.Bottom,
    "marginLeft": yoga.Edge.Left,
}

_PADDING_EDGES: dict[str, Any] = {
    "padding": yoga.Edge.All,
    "paddingX": yoga.Edge.Horizontal,
    "paddingY": yoga.Edge.Vertical,
    "paddingTop": yoga.Edge.Top,
    "paddingRight": yoga.Edge.Right,
    "paddingBottom": yoga.Edge.Bottom,
    "paddingLeft": yoga.Edge.Left,
}

_GAP_GUTTERS: dict[str, Any] = {
    "gap": yoga.Gutter.All,
    "rowGap": yoga.Gutter.Row,
    "columnGap": yoga.Gutter.Column,
}


def set_yoga_prop(node: Any, prop_name: str, value: Any) -> None:
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

    if prop_name == "flexBasis":
        if value is None or value == "auto":
            # Reset to undefined (yoga-python has no set_flex_basis_auto)
            node.flex_basis = float("nan")
            return
        if _is_flex_basis_type(value):
            node.flex_basis = float(value)
        return

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

    edge = _MARGIN_EDGES.get(prop_name)
    if edge is not None:
        if value is None:
            node.set_margin(edge, 0)
        elif _is_margin_type(value):
            _set_edge_prop(
                node,
                edge,
                value,
                set_fn=node.set_margin,
                set_percent_fn=node.set_margin_percent,
                set_auto_fn=node.set_margin_auto,
            )
        return

    edge = _PADDING_EDGES.get(prop_name)
    if edge is not None:
        if value is None:
            node.set_padding(edge, 0)
        elif _is_padding_type(value):
            _set_edge_prop(
                node,
                edge,
                value,
                set_fn=node.set_padding,
                set_percent_fn=node.set_padding_percent,
            )
        return

    gutter = _GAP_GUTTERS.get(prop_name)
    if gutter is not None:
        node.set_gap(gutter, 0 if value is None else float(value))
        return


is_valid_percentage = _is_valid_percentage
is_padding_type = _is_padding_type
is_margin_type = _is_margin_type
is_size_type = _is_size_type
is_dimension_type = _is_dimension_type
is_flex_basis_type = _is_flex_basis_type


def is_position_type(value: Any) -> bool:
    return _is_finite_number(value) or value == "auto" or _is_valid_percentage(value)


def is_position_type_value(value: Any) -> bool:
    """Check if value is a valid CSS position type string ("relative" or "absolute")."""
    return value in ("relative", "absolute")


def is_overflow_type(value: Any) -> bool:
    """Check if value is a valid overflow type string ("visible", "hidden", or "scroll")."""
    return value in ("visible", "hidden", "scroll")


def validate_options(name: str, options: dict[str, Any]) -> None:
    """Validate renderable options.

    Raises ValueError for negative width/height values.
    """
    width = options.get("width")
    height = options.get("height")
    if isinstance(width, int | float) and width < 0:
        raise ValueError(f"{name}: width must be non-negative, got {width}")
    if isinstance(height, int | float) and height < 0:
        raise ValueError(f"{name}: height must be non-negative, got {height}")


__all__ = [
    "create_node",
    "configure_node",
    "compute_layout",
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
