"""Initialization helpers for Renderable."""

from collections.abc import Callable
from typing import Any

# Attrs that default to None and are only conditionally set by _bind_layout_props.
_OPTIONAL_NONE_ATTRS = (
    "_min_width",
    "_min_height",
    "_max_width",
    "_max_height",
    "_flex_basis",
    "_align_self",
    "_row_gap",
    "_column_gap",
    "_background_color",
    "_fg",
    "_border_color",
    "_title",
    "_border_chars",
    "_focused_border_color",
    "_pos_top",
    "_pos_right",
    "_pos_bottom",
    "_pos_left",
)


def initialize_renderable(
    renderable: Any,
    *,
    width: int | str | None,
    height: int | str | None,
    fixed_width: int | None,
    fixed_height: int | None,
    min_width: int | str | None,
    min_height: int | str | None,
    max_width: int | str | None,
    max_height: int | str | None,
    flex_grow: float,
    flex_shrink: float | object,
    unset_flex_shrink: object,
    flex_direction: str,
    flex_wrap: str,
    flex_basis: float | str | None,
    justify_content: str,
    align_items: str,
    align_self: str | None,
    gap: int,
    row_gap: float | None,
    column_gap: float | None,
    overflow: str,
    position: str,
    padding: int,
    padding_top: int | None,
    padding_right: int | None,
    padding_bottom: int | None,
    padding_left: int | None,
    padding_x: int | None,
    padding_y: int | None,
    margin: int,
    margin_top: int | None,
    margin_right: int | None,
    margin_bottom: int | None,
    margin_left: int | None,
    margin_x: int | None,
    margin_y: int | None,
    background_color: Any,
    fg: Any,
    border: bool,
    border_style: str,
    border_color: Any,
    title: str | None,
    title_alignment: str,
    border_top: bool,
    border_right: bool,
    border_bottom: bool,
    border_left: bool,
    border_chars: dict | None,
    focusable: bool,
    focused: bool,
    focused_border_color: Any,
    visible: bool,
    opacity: float,
    clamp_opacity: Callable[[float], float],
    z_index: int,
    top: float | str | None,
    right: float | str | None,
    bottom: float | str | None,
    left: float | str | None,
    translate_x: float,
    translate_y: float,
    live: bool,
    on_mouse_down: Callable | None,
    on_click: Callable[[], None] | None,
    on_mouse_up: Callable | None,
    on_mouse_move: Callable | None,
    on_mouse_drag: Callable | None,
    on_mouse_drag_end: Callable | None,
    on_mouse_drop: Callable | None,
    on_mouse_over: Callable | None,
    on_mouse_out: Callable | None,
    on_mouse_scroll: Callable | None,
    on_key_down: Callable | None,
    on_paste: Callable | None,
    on_size_change: Callable[[int, int], None] | None,
    parse_border_style: Callable[[str], Any],
) -> None:
    width, height, min_width, min_height, max_width, max_height = _resolve_fixed_dimensions(
        width=width,
        height=height,
        fixed_width=fixed_width,
        fixed_height=fixed_height,
        min_width=min_width,
        min_height=min_height,
        max_width=max_width,
        max_height=max_height,
    )
    _validate_dimensions(width, height)
    _initialize_optional_slots(renderable)
    resolved_flex_shrink = _resolve_flex_shrink(width, height, flex_shrink, unset_flex_shrink)

    _bind_layout_props(
        renderable,
        width=width,
        height=height,
        min_width=min_width,
        min_height=min_height,
        max_width=max_width,
        max_height=max_height,
        flex_grow=flex_grow,
        flex_shrink=resolved_flex_shrink,
        flex_direction=flex_direction,
        flex_wrap=flex_wrap,
        flex_basis=flex_basis,
        justify_content=justify_content,
        align_items=align_items,
        align_self=align_self,
        gap=gap,
        row_gap=row_gap,
        column_gap=column_gap,
        overflow=overflow,
        position=position,
        padding=padding,
        padding_top=padding_top,
        padding_right=padding_right,
        padding_bottom=padding_bottom,
        padding_left=padding_left,
        padding_x=padding_x,
        padding_y=padding_y,
        margin=margin,
        margin_top=margin_top,
        margin_right=margin_right,
        margin_bottom=margin_bottom,
        margin_left=margin_left,
        margin_x=margin_x,
        margin_y=margin_y,
        background_color=background_color,
        fg=fg,
        border=border,
        border_style=border_style,
        border_color=border_color,
        title=title,
        title_alignment=title_alignment,
        border_top=border_top,
        border_right=border_right,
        border_bottom=border_bottom,
        border_left=border_left,
        border_chars=border_chars,
        focusable=focusable,
        focused=focused,
        focused_border_color=focused_border_color,
        visible=visible,
        opacity=opacity,
        clamp_opacity=clamp_opacity,
        z_index=z_index,
        top=top,
        right=right,
        bottom=bottom,
        left=left,
        translate_x=translate_x,
        translate_y=translate_y,
        parse_border_style=parse_border_style,
    )
    _initialize_runtime_props(
        renderable,
        live=live,
        on_mouse_down=on_mouse_down,
        on_click=on_click,
        on_mouse_up=on_mouse_up,
        on_mouse_move=on_mouse_move,
        on_mouse_drag=on_mouse_drag,
        on_mouse_drag_end=on_mouse_drag_end,
        on_mouse_drop=on_mouse_drop,
        on_mouse_over=on_mouse_over,
        on_mouse_out=on_mouse_out,
        on_mouse_scroll=on_mouse_scroll,
        on_key_down=on_key_down,
        on_paste=on_paste,
        on_size_change=on_size_change,
    )


def _resolve_fixed_dimensions(
    *,
    width: int | str | None,
    height: int | str | None,
    fixed_width: int | None,
    fixed_height: int | None,
    min_width: int | str | None,
    min_height: int | str | None,
    max_width: int | str | None,
    max_height: int | str | None,
) -> tuple[
    int | str | None,
    int | str | None,
    int | str | None,
    int | str | None,
    int | str | None,
    int | str | None,
]:
    if fixed_width is not None:
        if width is not None or min_width is not None or max_width is not None:
            raise ValueError(
                "Cannot combine 'fixed_width' with 'width', 'min_width', or 'max_width'"
            )
        width = min_width = max_width = fixed_width
    if fixed_height is not None:
        if height is not None or min_height is not None or max_height is not None:
            raise ValueError(
                "Cannot combine 'fixed_height' with 'height', 'min_height', or 'max_height'"
            )
        height = min_height = max_height = fixed_height
    return width, height, min_width, min_height, max_width, max_height


def _validate_dimensions(width: int | str | None, height: int | str | None) -> None:
    if isinstance(width, int | float) and width < 0:
        raise ValueError(f"width must be non-negative, got {width}")
    if isinstance(height, int | float) and height < 0:
        raise ValueError(f"height must be non-negative, got {height}")


def _initialize_optional_slots(renderable: Any) -> None:
    for attr in _OPTIONAL_NONE_ATTRS:
        setattr(renderable, attr, None)


def _resolve_flex_shrink(
    width: int | str | None,
    height: int | str | None,
    flex_shrink: float | object,
    unset_flex_shrink: object,
) -> float | object:
    explicit_numeric_size = isinstance(width, int | float) or isinstance(height, int | float)
    return (0 if explicit_numeric_size else 1) if flex_shrink is unset_flex_shrink else flex_shrink


def _bind_layout_props(renderable: Any, **kwargs: Any) -> None:
    width = kwargs["width"]
    height = kwargs["height"]
    min_width = kwargs["min_width"]
    min_height = kwargs["min_height"]
    max_width = kwargs["max_width"]
    max_height = kwargs["max_height"]
    flex_basis = kwargs["flex_basis"]
    align_self = kwargs["align_self"]
    row_gap = kwargs["row_gap"]
    column_gap = kwargs["column_gap"]
    background_color = kwargs["background_color"]
    fg = kwargs["fg"]
    border_color = kwargs["border_color"]
    title = kwargs["title"]
    border_chars = kwargs["border_chars"]
    focused_border_color = kwargs["focused_border_color"]
    top = kwargs["top"]
    right = kwargs["right"]
    bottom = kwargs["bottom"]
    left = kwargs["left"]

    if width is not None:
        renderable._set_or_bind("_width", width)
    if height is not None:
        renderable._set_or_bind("_height", height)
    if min_width is not None:
        renderable._set_or_bind("_min_width", min_width)
    if min_height is not None:
        renderable._set_or_bind("_min_height", min_height)
    if max_width is not None:
        renderable._set_or_bind("_max_width", max_width)
    if max_height is not None:
        renderable._set_or_bind("_max_height", max_height)
    renderable._set_or_bind("_flex_grow", kwargs["flex_grow"])
    renderable._set_or_bind("_flex_shrink", kwargs["flex_shrink"])
    renderable._set_or_bind("_flex_direction", kwargs["flex_direction"])
    renderable._set_or_bind("_flex_wrap", kwargs["flex_wrap"])
    if flex_basis is not None:
        renderable._set_or_bind("_flex_basis", flex_basis)
    renderable._set_or_bind("_justify_content", kwargs["justify_content"])
    renderable._set_or_bind("_align_items", kwargs["align_items"])
    if align_self is not None:
        renderable._set_or_bind("_align_self", align_self)
    renderable._set_or_bind("_gap", kwargs["gap"])
    if row_gap is not None:
        renderable._set_or_bind("_row_gap", row_gap)
    if column_gap is not None:
        renderable._set_or_bind("_column_gap", column_gap)
    renderable._set_or_bind("_overflow", kwargs["overflow"])
    renderable._set_or_bind("_position", kwargs["position"])

    padding = kwargs["padding"]
    renderable._padding = padding
    for attr, specific, axis in (
        ("_padding_top", kwargs["padding_top"], kwargs["padding_y"]),
        ("_padding_right", kwargs["padding_right"], kwargs["padding_x"]),
        ("_padding_bottom", kwargs["padding_bottom"], kwargs["padding_y"]),
        ("_padding_left", kwargs["padding_left"], kwargs["padding_x"]),
    ):
        renderable._set_or_bind(
            attr, specific if specific is not None else (axis if axis is not None else padding)
        )

    margin = kwargs["margin"]
    renderable._margin = margin
    for attr, specific, axis in (
        ("_margin_top", kwargs["margin_top"], kwargs["margin_y"]),
        ("_margin_right", kwargs["margin_right"], kwargs["margin_x"]),
        ("_margin_bottom", kwargs["margin_bottom"], kwargs["margin_y"]),
        ("_margin_left", kwargs["margin_left"], kwargs["margin_x"]),
    ):
        renderable._set_or_bind(
            attr, specific if specific is not None else (axis if axis is not None else margin)
        )

    if background_color is not None:
        renderable._set_or_bind(
            "_background_color", background_color, transform=renderable._parse_color
        )
    if fg is not None:
        renderable._set_or_bind("_fg", fg, transform=renderable._parse_color)
    renderable._set_or_bind("_border", kwargs["border"])
    renderable._set_or_bind(
        "_border_style", kwargs["border_style"], transform=kwargs["parse_border_style"]
    )
    if border_color is not None:
        renderable._set_or_bind("_border_color", border_color, transform=renderable._parse_color)
    if title is not None:
        renderable._set_or_bind("_title", title)
    renderable._set_or_bind("_title_alignment", kwargs["title_alignment"])
    renderable._set_or_bind("_border_top", kwargs["border_top"])
    renderable._set_or_bind("_border_right", kwargs["border_right"])
    renderable._set_or_bind("_border_bottom", kwargs["border_bottom"])
    renderable._set_or_bind("_border_left", kwargs["border_left"])
    if border_chars is not None:
        renderable._set_or_bind("_border_chars", border_chars)

    renderable._set_or_bind("_focusable", kwargs["focusable"])
    renderable._set_or_bind("_focused", kwargs["focused"])
    if focused_border_color is not None:
        renderable._set_or_bind(
            "_focused_border_color", focused_border_color, transform=renderable._parse_color
        )
    if renderable._focused_border_color and not renderable._border:
        renderable._border = True

    renderable._set_or_bind("_visible", kwargs["visible"])
    renderable._sync_yoga_display()
    renderable._set_or_bind("_opacity", kwargs["opacity"], transform=kwargs["clamp_opacity"])
    renderable._set_or_bind("_z_index", kwargs["z_index"])

    if top is not None:
        renderable._set_or_bind("_pos_top", top)
    if right is not None:
        renderable._set_or_bind("_pos_right", right)
    if bottom is not None:
        renderable._set_or_bind("_pos_bottom", bottom)
    if left is not None:
        renderable._set_or_bind("_pos_left", left)

    renderable._set_or_bind("_translate_x", kwargs["translate_x"])
    renderable._set_or_bind("_translate_y", kwargs["translate_y"])


def _initialize_runtime_props(
    renderable: Any,
    *,
    live: bool,
    on_mouse_down: Callable | None,
    on_click: Callable[[], None] | None,
    on_mouse_up: Callable | None,
    on_mouse_move: Callable | None,
    on_mouse_drag: Callable | None,
    on_mouse_drag_end: Callable | None,
    on_mouse_drop: Callable | None,
    on_mouse_over: Callable | None,
    on_mouse_out: Callable | None,
    on_mouse_scroll: Callable | None,
    on_key_down: Callable | None,
    on_paste: Callable | None,
    on_size_change: Callable[[int, int], None] | None,
) -> None:
    renderable._render_before = None
    renderable._render_after = None
    renderable._on_size_change = on_size_change

    if on_click is not None:
        if on_mouse_down is not None:
            raise ValueError("Cannot pass both 'on_click' and 'on_mouse_down'")
        click_cb = on_click

        def _on_click_wrapper(event: Any) -> None:
            if getattr(event, "button", -1) != 0:
                return
            event.stop_propagation()
            click_cb()

        on_mouse_down = _on_click_wrapper

    renderable._on_mouse_down = on_mouse_down
    renderable._on_mouse_up = on_mouse_up
    renderable._on_mouse_move = on_mouse_move
    renderable._on_mouse_drag = on_mouse_drag
    renderable._on_mouse_drag_end = on_mouse_drag_end
    renderable._on_mouse_drop = on_mouse_drop
    renderable._on_mouse_over = on_mouse_over
    renderable._on_mouse_out = on_mouse_out
    renderable._on_mouse_scroll = on_mouse_scroll
    renderable._on_key_down = on_key_down
    renderable._on_paste = on_paste
    renderable._live = live
    renderable._live_count = 1 if live and renderable._visible else 0
    renderable._handle_paste = None
    renderable._on_lifecycle_pass = None
    renderable._selectable = False


__all__ = ["initialize_renderable"]
