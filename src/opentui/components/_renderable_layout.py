"""Layout helpers for Renderable's Yoga integration."""

from typing import Any

import yoga


def configure_renderable_yoga(
    renderable: Any,
    node: Any,
    *,
    yoga_layout: Any,
    configure_node_fast: Any,
    column: str,
    nowrap: str,
    flex_start: str,
    stretch: str,
    visible: str,
    relative: str,
) -> None:
    bt = 1 if renderable._border and renderable._border_top else 0
    br = 1 if renderable._border and renderable._border_right else 0
    bb = 1 if renderable._border and renderable._border_bottom else 0
    bl = 1 if renderable._border and renderable._border_left else 0

    if not renderable._dirty and renderable._yoga_config_cache is not None:
        return

    config = (
        renderable._width,
        renderable._height,
        renderable._min_width,
        renderable._min_height,
        renderable._max_width,
        renderable._max_height,
        renderable._flex_grow,
        renderable._flex_shrink,
        renderable._flex_basis,
        renderable._flex_direction,
        renderable._flex_wrap,
        renderable._justify_content,
        renderable._align_items,
        renderable._align_self,
        renderable._gap,
        renderable._row_gap,
        renderable._column_gap,
        renderable._overflow,
        renderable._position,
        renderable._padding_top + bt,
        renderable._padding_right + br,
        renderable._padding_bottom + bb,
        renderable._padding_left + bl,
        renderable._margin,
        renderable._margin_top,
        renderable._margin_right,
        renderable._margin_bottom,
        renderable._margin_left,
        renderable._pos_top,
        renderable._pos_right,
        renderable._pos_bottom,
        renderable._pos_left,
    )
    if renderable._yoga_config_cache == config:
        return
    renderable._yoga_config_cache = config

    common_kwargs = {
        "width": renderable._width,
        "height": renderable._height,
        "min_width": renderable._min_width,
        "min_height": renderable._min_height,
        "max_width": renderable._max_width,
        "max_height": renderable._max_height,
        "flex_grow": float(renderable._flex_grow) if renderable._flex_grow else None,
        "flex_shrink": float(renderable._flex_shrink),
        "flex_basis": renderable._flex_basis,
        "flex_direction": renderable._flex_direction
        if renderable._flex_direction is not column
        else None,
        "flex_wrap": renderable._flex_wrap if renderable._flex_wrap is not nowrap else None,
        "justify_content": renderable._justify_content
        if renderable._justify_content is not flex_start
        else None,
        "align_items": renderable._align_items if renderable._align_items is not stretch else None,
        "align_self": renderable._align_self,
        "gap": float(renderable._gap) if renderable._gap else None,
        "overflow": renderable._overflow if renderable._overflow is not visible else None,
        "position_type": renderable._position if renderable._position is not relative else None,
        "padding_top": float(renderable._padding_top + bt),
        "padding_right": float(renderable._padding_right + br),
        "padding_bottom": float(renderable._padding_bottom + bb),
        "padding_left": float(renderable._padding_left + bl),
        "margin": float(renderable._margin) if renderable._margin else None,
        "margin_top": float(renderable._margin_top) if renderable._margin_top is not None else None,
        "margin_right": float(renderable._margin_right)
        if renderable._margin_right is not None
        else None,
        "margin_bottom": float(renderable._margin_bottom)
        if renderable._margin_bottom is not None
        else None,
        "margin_left": float(renderable._margin_left)
        if renderable._margin_left is not None
        else None,
    }
    if callable(configure_node_fast):
        configure_node_fast(
            node,
            **common_kwargs,
            pos_top=renderable._pos_top,
            pos_right=renderable._pos_right,
            pos_bottom=renderable._pos_bottom,
            pos_left=renderable._pos_left,
        )
    else:
        yoga_layout.configure_node(
            node,
            **common_kwargs,
            row_gap=float(renderable._row_gap) if renderable._row_gap else None,
            column_gap=float(renderable._column_gap) if renderable._column_gap else None,
            top=renderable._pos_top,
            right=renderable._pos_right,
            bottom=renderable._pos_bottom,
            left=renderable._pos_left,
            display="flex" if renderable._visible else "none",
        )
    if renderable._row_gap is not None:
        node.set_gap(yoga.Gutter.Row, float(renderable._row_gap))
    if renderable._column_gap is not None:
        node.set_gap(yoga.Gutter.Column, float(renderable._column_gap))


def apply_renderable_layout(renderable: Any) -> None:
    node = renderable._yoga_node
    if node is None:
        return
    old_w = renderable._layout_width
    old_h = renderable._layout_height
    renderable._x, renderable._y, renderable._layout_width, renderable._layout_height = (
        yoga.get_layout_batch(node)
    )

    if renderable._on_size_change and (
        old_w != renderable._layout_width or old_h != renderable._layout_height
    ):
        renderable._on_size_change(renderable._layout_width, renderable._layout_height)


def render_renderable_children(renderable: Any, buffer: Any, delta_time: float = 0) -> None:
    if not renderable._visible:
        return

    if renderable._render_before:
        renderable._render_before(buffer, delta_time, renderable)

    for child in renderable._children:
        child.render(buffer, delta_time)

    if renderable._render_after:
        renderable._render_after(buffer, delta_time, renderable)


__all__ = [
    "apply_renderable_layout",
    "configure_renderable_yoga",
    "render_renderable_children",
]
