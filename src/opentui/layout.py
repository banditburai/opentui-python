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


def configure_node(
    node: yoga.Node,
    *,
    # Dimensions
    width: float | None = None,
    height: float | None = None,
    min_width: float | None = None,
    min_height: float | None = None,
    max_width: float | None = None,
    max_height: float | None = None,
    # Flex
    flex_grow: float | None = None,
    flex_shrink: float | None = None,
    flex_basis: float | None = None,
    flex_direction: str | None = None,
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
) -> None:
    """Configure a yoga node with layout properties."""

    # Dimensions
    if width is not None:
        node.width = width
    if height is not None:
        node.height = height
    if min_width is not None:
        node.min_width = min_width
    if min_height is not None:
        node.min_height = min_height
    if max_width is not None:
        node.max_width = max_width
    if max_height is not None:
        node.max_height = max_height

    # Flex
    if flex_grow is not None:
        node.flex_grow = flex_grow
    if flex_shrink is not None:
        node.flex_shrink = flex_shrink
    if flex_basis is not None:
        node.set_flex_basis(flex_basis)
    if flex_direction is not None:
        node.flex_direction = FLEX_DIRECTION_MAP.get(flex_direction, yoga.FlexDirection.COLUMN)

    # Alignment
    if justify_content is not None:
        node.justify_content = JUSTIFY_MAP.get(justify_content, yoga.Justify.FLEX_START)
    if align_items is not None:
        node.align_items = ALIGN_MAP.get(align_items, yoga.Align.STRETCH)
    if align_self is not None:
        node.align_self = ALIGN_MAP.get(align_self, yoga.Align.AUTO)

    # Gap
    if gap is not None:
        node.gap = gap
    if row_gap is not None:
        node.set_gap(yoga.Gutter.ROW, row_gap)
    if column_gap is not None:
        node.set_gap(yoga.Gutter.COLUMN, column_gap)

    # Padding
    if padding is not None:
        node.set_padding(yoga.Edge.ALL, padding)
    if padding_top is not None:
        node.set_padding(yoga.Edge.TOP, padding_top)
    if padding_right is not None:
        node.set_padding(yoga.Edge.RIGHT, padding_right)
    if padding_bottom is not None:
        node.set_padding(yoga.Edge.BOTTOM, padding_bottom)
    if padding_left is not None:
        node.set_padding(yoga.Edge.LEFT, padding_left)

    # Margin
    if margin is not None:
        node.set_margin(yoga.Edge.ALL, margin)
    if margin_top is not None:
        node.set_margin(yoga.Edge.TOP, margin_top)
    if margin_right is not None:
        node.set_margin(yoga.Edge.RIGHT, margin_right)
    if margin_bottom is not None:
        node.set_margin(yoga.Edge.BOTTOM, margin_bottom)
    if margin_left is not None:
        node.set_margin(yoga.Edge.LEFT, margin_left)

    # Display
    if display is not None:
        node.display = yoga.Display.FLEX if display == "flex" else yoga.Display.NONE
    if position_type is not None:
        node.position_type = (
            yoga.PositionType.ABSOLUTE
            if position_type == "absolute"
            else yoga.PositionType.RELATIVE
        )


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
]
