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

OVERFLOW_MAP = {
    "visible": yoga.Overflow.Visible,
    "hidden": yoga.Overflow.Hidden,
    "scroll": yoga.Overflow.Scroll,
}


ALIGN_MAP = {
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


def _make_parser(mapping: dict[str, Any], default: Any):
    """None -> default, else dict lookup with default fallback."""

    def parse(value: str | None) -> Any:
        return default if value is None else mapping.get(value.lower(), default)

    return parse


def parse_align(value: str | None, default: yoga.Align = yoga.Align.Auto) -> yoga.Align:
    if value is None:
        return default
    return ALIGN_MAP.get(value.lower(), default)


def parse_align_items(value: str | None) -> yoga.Align:
    return parse_align(value, yoga.Align.Stretch)


_DISPLAY_MAP = {
    "flex": yoga.Display.Flex,
    "none": yoga.Display.None_,
    "contents": yoga.Display.Contents,
}
parse_display = _make_parser(_DISPLAY_MAP, yoga.Display.Flex)

parse_flex_direction = _make_parser(FLEX_DIRECTION_MAP, yoga.FlexDirection.Column)

parse_justify = _make_parser(JUSTIFY_MAP, yoga.Justify.FlexStart)

parse_overflow = _make_parser(OVERFLOW_MAP, yoga.Overflow.Visible)

_POSITION_TYPE_PARSE_MAP = {
    "static": yoga.PositionType.Static,
    "relative": yoga.PositionType.Relative,
    "absolute": yoga.PositionType.Absolute,
}


def parse_position_type(value: str | None) -> yoga.PositionType:
    if value is None:
        return yoga.PositionType.Relative
    return _POSITION_TYPE_PARSE_MAP.get(value.lower(), yoga.PositionType.Static)


_WRAP_PARSE_MAP = {
    "no-wrap": yoga.Wrap.NoWrap,
    "wrap": yoga.Wrap.Wrap,
    "wrap-reverse": yoga.Wrap.WrapReverse,
}
parse_wrap = _make_parser(_WRAP_PARSE_MAP, yoga.Wrap.NoWrap)


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
    # Width/height reset to auto when None to avoid stale values
    # from a previous frame persisting and overriding flex layout.
    set_yoga_prop(node, "width", width)
    set_yoga_prop(node, "height", height)

    # All other props: delegate to table-driven set_yoga_prop, skip if None.
    _props: dict[str, Any] = {
        "min_width": min_width,
        "min_height": min_height,
        "max_width": max_width,
        "max_height": max_height,
        "flex_grow": flex_grow,
        "flex_shrink": flex_shrink,
        "flex_basis": flex_basis,
        "flex_direction": flex_direction,
        "flex_wrap": flex_wrap,
        "justify_content": justify_content,
        "align_items": align_items,
        "align_self": align_self,
        "gap": gap,
        "row_gap": row_gap,
        "column_gap": column_gap,
        "padding": padding,
        "padding_top": padding_top,
        "padding_right": padding_right,
        "padding_bottom": padding_bottom,
        "padding_left": padding_left,
        "margin": margin,
        "margin_top": margin_top,
        "margin_right": margin_right,
        "margin_bottom": margin_bottom,
        "margin_left": margin_left,
        "display": display,
        "position": position_type,
        "overflow": overflow,
        "top": top,
        "right": right,
        "bottom": bottom,
        "left": left,
    }
    for name, val in _props.items():
        if val is not None:
            set_yoga_prop(node, name, val)


def compute_layout(root_node: yoga.Node, width: float, height: float) -> None:
    root_node.calculate_layout(width, height, yoga.Direction.LTR)


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




def _is_flex_basis_type(value: Any) -> bool:
    return value is None or value == "auto" or _is_finite_number(value)


def _set_dimension_prop(
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
    "margin_x": yoga.Edge.Horizontal,
    "margin_y": yoga.Edge.Vertical,
    "margin_top": yoga.Edge.Top,
    "margin_right": yoga.Edge.Right,
    "margin_bottom": yoga.Edge.Bottom,
    "margin_left": yoga.Edge.Left,
}

_PADDING_EDGES: dict[str, Any] = {
    "padding": yoga.Edge.All,
    "padding_x": yoga.Edge.Horizontal,
    "padding_y": yoga.Edge.Vertical,
    "padding_top": yoga.Edge.Top,
    "padding_right": yoga.Edge.Right,
    "padding_bottom": yoga.Edge.Bottom,
    "padding_left": yoga.Edge.Left,
}

_GAP_GUTTERS: dict[str, Any] = {
    "gap": yoga.Gutter.All,
    "row_gap": yoga.Gutter.Row,
    "column_gap": yoga.Gutter.Column,
}

_POSITION_EDGES: dict[str, Any] = {
    "top": yoga.Edge.Top,
    "right": yoga.Edge.Right,
    "bottom": yoga.Edge.Bottom,
    "left": yoga.Edge.Left,
}


_ENUM_YOGA_PROPS: dict[str, tuple[str, Any]] = {
    "flex_direction": ("flex_direction", parse_flex_direction),
    "flex_wrap": ("flex_wrap", parse_wrap),
    "align_items": ("align_items", parse_align_items),
    "justify_content": ("justify_content", parse_justify),
    "align_self": ("align_self", parse_align),
    "align_content": ("align_content", parse_align),
    "overflow": ("overflow", parse_overflow),
    "position": ("position_type", parse_position_type),
    "display": ("display", parse_display),
}

_DIM_YOGA_PROPS: dict[str, tuple[str, str, str]] = {
    "width": ("width", "set_width_percent", "set_width_auto"),
    "height": ("height", "set_height_percent", "set_height_auto"),
}

_MINMAX_YOGA_PROPS: dict[str, tuple[str, str]] = {
    "min_width": ("min_width", "set_min_width_percent"),
    "max_width": ("max_width", "set_max_width_percent"),
    "min_height": ("min_height", "set_min_height_percent"),
    "max_height": ("max_height", "set_max_height_percent"),
}


def set_yoga_prop(node: Any, prop_name: str, value: Any) -> None:
    if prop_name == "flex_grow":
        node.flex_grow = 0 if value is None else float(value)
        return
    if prop_name == "flex_shrink":
        node.flex_shrink = 1 if value is None else float(value)
        return
    if prop_name == "flex_basis":
        if value is None or value == "auto":
            node.flex_basis = float("nan")
        elif _is_flex_basis_type(value):
            node.flex_basis = float(value)
        return

    enum_entry = _ENUM_YOGA_PROPS.get(prop_name)
    if enum_entry is not None:
        attr, parser = enum_entry
        setattr(node, attr, parser(value))
        return

    dim = _DIM_YOGA_PROPS.get(prop_name)
    if dim is not None:
        attr, pct_fn, auto_fn = dim
        if value is None:
            getattr(node, auto_fn)()
        elif _is_margin_type(value):
            _set_dimension_prop(
                value,
                set_point=lambda v, a=attr: setattr(node, a, v),
                set_percent=getattr(node, pct_fn),
                set_auto=getattr(node, auto_fn),
            )
        return

    mm = _MINMAX_YOGA_PROPS.get(prop_name)
    if mm is not None:
        attr, pct_fn = mm
        if _is_size_type(value):
            if value is None:
                setattr(node, attr, float("nan"))
            elif _is_valid_percentage(value):
                getattr(node, pct_fn)(float(value[:-1]))
            else:
                setattr(node, attr, float(value))
        return

    edge = _MARGIN_EDGES.get(prop_name)
    if edge is not None:
        if value is None:
            node.set_margin(edge, 0)
        elif _is_margin_type(value):
            _set_edge_prop(
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

    edge = _POSITION_EDGES.get(prop_name)
    if edge is not None:
        _set_edge_prop(
            edge, value, set_fn=node.set_position, set_percent_fn=node.set_position_percent
        )
        return


# ---------------------------------------------------------------------------
# Viewport culling (SolidJS parity — used for virtualized scroll containers)
# ---------------------------------------------------------------------------


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

        if is_row:
            if child.y + child.height < vp_top or child.y > vp_bottom:
                continue
        else:
            if child.x + child.width < vp_left or child.x > vp_right:
                continue

        visible.append(child)

    if len(visible) > 1:
        visible.sort(key=lambda o: o.z_index)

    return visible


def validate_options(name: str, options: dict[str, Any]) -> None:
    """Validate renderable options — raises ValueError for negative width/height."""
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
    "validate_options",
    "parse_align",
    "parse_align_items",
    "parse_display",
    "parse_flex_direction",
    "parse_justify",
    "parse_overflow",
    "parse_position_type",
    "parse_wrap",
]
