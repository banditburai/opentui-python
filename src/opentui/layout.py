"""Yoga layout wrapper for OpenTUI Python.

This module wraps yoga-python to provide flexbox layout for terminal UIs.
Uses character-based units (not pixels) to match terminal grid.
"""

from __future__ import annotations

import yoga
from typing import Any

# Global yoga config - created once and reused
_config: yoga.Config | None = None


def _get_config() -> yoga.Config:
    """Get or create the global yoga config."""
    global _config
    if _config is None:
        _config = yoga.Config.create()
        _config.set_use_web_defaults(False)
        _config.set_point_scale_factor(1)  # 1 yoga unit = 1 character
    return _config


def create_node() -> yoga.Node:
    """Create a new yoga node with the global config."""
    return yoga.Node()


# Flex direction mapping (yoga-python uses PascalCase)
FLEX_DIRECTION_MAP = {
    "row": yoga.FlexDirection.Row,
    "column": yoga.FlexDirection.Column,
    "row-reverse": yoga.FlexDirection.RowReverse,
    "column-reverse": yoga.FlexDirection.ColumnReverse,
}

# Justify content mapping
JUSTIFY_MAP = {
    "flex-start": yoga.Justify.FlexStart,
    "flex-end": yoga.Justify.FlexEnd,
    "center": yoga.Justify.Center,
    "space-between": yoga.Justify.SpaceBetween,
    "space-around": yoga.Justify.SpaceAround,
    "space-evenly": yoga.Justify.SpaceEvenly,
}

# Align items mapping
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

# Wrap mapping
WRAP_MAP = {
    "nowrap": yoga.Wrap.NoWrap,
    "wrap": yoga.Wrap.Wrap,
    "wrap-reverse": yoga.Wrap.WrapReverse,
}

# Overflow mapping
OVERFLOW_MAP = {
    "visible": yoga.Overflow.Visible,
    "hidden": yoga.Overflow.Hidden,
    "scroll": yoga.Overflow.Scroll,
}

# Position type mapping
POSITION_TYPE_MAP = {
    "relative": yoga.PositionType.Relative,
    "absolute": yoga.PositionType.Absolute,
}


def _parse_dimension(value):
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

    # Dimensions (support percentage and auto)
    if width is not None:
        val, kind = _parse_dimension(width)
        if kind == "percent":
            node.set_width_percent(val)
        elif kind == "auto":
            node.set_width_auto()
        else:
            node.width = val
    if height is not None:
        val, kind = _parse_dimension(height)
        if kind == "percent":
            node.set_height_percent(val)
        elif kind == "auto":
            node.set_height_auto()
        else:
            node.height = val
    if min_width is not None:
        val, kind = _parse_dimension(min_width)
        if kind == "percent":
            node.set_min_width_percent(val)
        else:
            node.min_width = val
    if min_height is not None:
        val, kind = _parse_dimension(min_height)
        if kind == "percent":
            node.set_min_height_percent(val)
        else:
            node.min_height = val
    if max_width is not None:
        val, kind = _parse_dimension(max_width)
        if kind == "percent":
            node.set_max_width_percent(val)
        else:
            node.max_width = val
    if max_height is not None:
        val, kind = _parse_dimension(max_height)
        if kind == "percent":
            node.set_max_height_percent(val)
        else:
            node.max_height = val

    # Flex
    if flex_grow is not None:
        node.flex_grow = flex_grow
    if flex_shrink is not None:
        node.flex_shrink = flex_shrink
    if flex_basis is not None:
        val, kind = _parse_dimension(flex_basis)
        if kind == "percent":
            node.set_flex_basis_percent(val)
        elif kind == "auto":
            node.set_flex_basis_auto()
        else:
            node.set_flex_basis(val)
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
        node.gap = gap
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
        if kind == "percent":
            node.set_position_percent(yoga.Edge.Top, val)
        elif val is not None:
            node.set_position(yoga.Edge.Top, val)
    if right is not None:
        val, kind = _parse_dimension(right)
        if kind == "percent":
            node.set_position_percent(yoga.Edge.Right, val)
        elif val is not None:
            node.set_position(yoga.Edge.Right, val)
    if bottom is not None:
        val, kind = _parse_dimension(bottom)
        if kind == "percent":
            node.set_position_percent(yoga.Edge.Bottom, val)
        elif val is not None:
            node.set_position(yoga.Edge.Bottom, val)
    if left is not None:
        val, kind = _parse_dimension(left)
        if kind == "percent":
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


__all__ = [
    "create_node",
    "configure_node",
    "compute_layout",
    "get_layout",
    "FLEX_DIRECTION_MAP",
    "JUSTIFY_MAP",
    "ALIGN_MAP",
    "EDGE_MAP",
    "WRAP_MAP",
    "OVERFLOW_MAP",
    "POSITION_TYPE_MAP",
]
