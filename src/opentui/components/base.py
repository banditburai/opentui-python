"""Base renderable classes."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .. import layout as yoga_layout
from .. import structs as s
from . import _renderable_base
from ._renderable_base import (
    BaseRenderable,
    LayoutRect,
    _Prop,
    _PropBinding,
    _RenderableBehaviorMixin,
    _get_configure_node_fast,
)
from ._renderable_constants import (
    _COLUMN,
    _FLEX_START,
    _LEFT,
    _NOWRAP,
    _RELATIVE,
    _SINGLE,
    _STRETCH,
    _UNSET_FLEX_SHRINK,
    _VISIBLE,
)

is_renderable = _renderable_base.is_renderable


if TYPE_CHECKING:
    from ..events import KeyEvent, MouseEvent, PasteEvent
    from ..renderer import Buffer


def _clamp_opacity(v: float) -> float:
    return max(0.0, min(1.0, v))


_parse_color_static = s.parse_color_opt


from ._reactive_binding import _ReactiveBindingMixin
from ._renderable_init import initialize_renderable
from ._renderable_layout import (
    apply_renderable_layout,
    configure_renderable_yoga,
    render_renderable_children,
)


class Renderable(_ReactiveBindingMixin, _RenderableBehaviorMixin, BaseRenderable):
    __slots__ = (
        "_min_width",
        "_min_height",
        "_max_width",
        "_max_height",
        "_flex_grow",
        "_flex_shrink",
        "_flex_direction",
        "_flex_wrap",
        "_flex_basis",
        "_justify_content",
        "_align_items",
        "_align_self",
        "_gap",
        "_row_gap",
        "_column_gap",
        "_overflow",
        "_position",
        "_padding",
        "_padding_top",
        "_padding_right",
        "_padding_bottom",
        "_padding_left",
        "_margin",
        "_margin_top",
        "_margin_right",
        "_margin_bottom",
        "_margin_left",
        "_background_color",
        "_fg",
        "_border",
        "_border_style",
        "_border_color",
        "_title",
        "_title_alignment",
        "_border_top",
        "_border_right",
        "_border_bottom",
        "_border_left",
        "_border_chars",
        "_focusable",
        "_focused",
        "_focused_border_color",
        "_opacity",
        "_z_index",
        "_pos_top",
        "_pos_right",
        "_pos_bottom",
        "_pos_left",
        "_translate_x",
        "_translate_y",
        "_render_before",
        "_render_after",
        "_on_size_change",
        "_on_mouse_down",
        "_on_mouse_up",
        "_on_mouse_move",
        "_on_mouse_drag",
        "_on_mouse_drag_end",
        "_on_mouse_drop",
        "_on_mouse_over",
        "_on_mouse_out",
        "_on_mouse_scroll",
        "_on_key_down",
        "_on_paste",
        "_live",
        "_live_count",
        "_handle_paste",
        "_selectable",
        "_on_lifecycle_pass",
        "_prop_bindings",
        "_yoga_config_cache",
        "_is_simple",
    )

    _LAYOUT_PROPS: frozenset[str] = frozenset(
        {
            "_content",
            "_wrap_mode",
            "_width",
            "_height",
            "_min_width",
            "_min_height",
            "_max_width",
            "_max_height",
            "_flex_grow",
            "_flex_shrink",
            "_flex_direction",
            "_flex_wrap",
            "_flex_basis",
            "_justify_content",
            "_align_items",
            "_align_self",
            "_gap",
            "_row_gap",
            "_column_gap",
            "_padding",
            "_padding_top",
            "_padding_right",
            "_padding_bottom",
            "_padding_left",
            "_margin",
            "_margin_top",
            "_margin_right",
            "_margin_bottom",
            "_margin_left",
            "_overflow",
            "_position",
            "_pos_top",
            "_pos_right",
            "_pos_bottom",
            "_pos_left",
            "_border",
            "_border_top",
            "_border_right",
            "_border_bottom",
            "_border_left",
        }
    )

    def __init__(
        self,
        *,
        key: str | int | None = None,
        id: str | None = None,
        width: int | str | None = None,
        height: int | str | None = None,
        fixed_width: int | None = None,
        fixed_height: int | None = None,
        min_width: int | str | None = None,
        min_height: int | str | None = None,
        max_width: int | str | None = None,
        max_height: int | str | None = None,
        flex_grow: float = 0,
        flex_shrink: float | object = _UNSET_FLEX_SHRINK,
        flex_direction: str = _COLUMN,
        flex_wrap: str = _NOWRAP,
        flex_basis: float | str | None = None,
        justify_content: str = _FLEX_START,
        align_items: str = _STRETCH,
        align_self: str | None = None,
        gap: int = 0,
        row_gap: float | None = None,
        column_gap: float | None = None,
        overflow: str = _VISIBLE,
        position: str = _RELATIVE,
        padding: int = 0,
        padding_top: int | None = None,
        padding_right: int | None = None,
        padding_bottom: int | None = None,
        padding_left: int | None = None,
        padding_x: int | None = None,
        padding_y: int | None = None,
        margin: int = 0,
        margin_top: int | None = None,
        margin_right: int | None = None,
        margin_bottom: int | None = None,
        margin_left: int | None = None,
        margin_x: int | None = None,
        margin_y: int | None = None,
        background_color: s.RGBA | str | None = None,
        fg: s.RGBA | str | None = None,
        border: bool = False,
        border_style: str = _SINGLE,
        border_color: s.RGBA | str | None = None,
        title: str | None = None,
        title_alignment: str = _LEFT,
        border_top: bool = True,
        border_right: bool = True,
        border_bottom: bool = True,
        border_left: bool = True,
        border_chars: dict | None = None,
        focusable: bool = False,
        focused: bool = False,
        focused_border_color: s.RGBA | str | None = None,
        visible: bool = True,
        opacity: float = 1.0,
        z_index: int = 0,
        top: float | str | None = None,
        right: float | str | None = None,
        bottom: float | str | None = None,
        left: float | str | None = None,
        translate_x: float = 0,
        translate_y: float = 0,
        live: bool = False,
        on_mouse_down: Callable[[MouseEvent], None] | None = None,
        on_click: Callable[[], None] | None = None,
        on_mouse_up: Callable[[MouseEvent], None] | None = None,
        on_mouse_move: Callable[[MouseEvent], None] | None = None,
        on_mouse_drag: Callable[[MouseEvent], None] | None = None,
        on_mouse_drag_end: Callable[[MouseEvent], None] | None = None,
        on_mouse_drop: Callable[[MouseEvent], None] | None = None,
        on_mouse_over: Callable[[MouseEvent], None] | None = None,
        on_mouse_out: Callable[[MouseEvent], None] | None = None,
        on_mouse_scroll: Callable[[MouseEvent], None] | None = None,
        on_key_down: Callable[[KeyEvent], None] | None = None,
        on_paste: Callable[[PasteEvent], None] | None = None,
        on_size_change: Callable[[int, int], None] | None = None,
    ):
        super().__init__(key=key, id=id)

        self._prop_bindings: dict[str, _PropBinding] | None = None
        self._yoga_config_cache: tuple | None = None
        self._is_simple: bool = True
        initialize_renderable(
            self,
            width=width,
            height=height,
            fixed_width=fixed_width,
            fixed_height=fixed_height,
            min_width=min_width,
            min_height=min_height,
            max_width=max_width,
            max_height=max_height,
            flex_grow=flex_grow,
            flex_shrink=flex_shrink,
            unset_flex_shrink=_UNSET_FLEX_SHRINK,
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
            clamp_opacity=_clamp_opacity,
            z_index=z_index,
            top=top,
            right=right,
            bottom=bottom,
            left=left,
            translate_x=translate_x,
            translate_y=translate_y,
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
            parse_border_style=s.parse_border_style,
        )

    _parse_color = staticmethod(_parse_color_static)

    @property
    def width(self) -> int | str | None:
        return self._width

    @width.setter
    def width(self, value: int | str | None) -> None:
        self._width = value
        if isinstance(value, int | float) and self._flex_shrink == 1:
            self._flex_shrink = 0
        self.mark_dirty()

    @property
    def height(self) -> int | str | None:
        return self._height

    @height.setter
    def height(self, value: int | str | None) -> None:
        self._height = value
        if isinstance(value, int | float) and self._flex_shrink == 1:
            self._flex_shrink = 0
        self.mark_dirty()

    min_width = _Prop("_min_width")

    min_height = _Prop("_min_height")

    max_width = _Prop("_max_width")

    max_height = _Prop("_max_height")

    flex_grow = _Prop("_flex_grow")

    flex_shrink = _Prop("_flex_shrink")

    flex_direction = _Prop("_flex_direction")

    flex_wrap = _Prop("_flex_wrap")

    flex_basis = _Prop("_flex_basis")

    justify_content = _Prop("_justify_content")

    align_items = _Prop("_align_items")

    align_self = _Prop("_align_self")

    gap = _Prop("_gap")

    row_gap = _Prop("_row_gap")

    column_gap = _Prop("_column_gap")

    @property
    def padding(self) -> int:
        return self._padding

    @padding.setter
    def padding(self, value: int) -> None:
        self._padding = value
        self._padding_top = value
        self._padding_right = value
        self._padding_bottom = value
        self._padding_left = value
        self.mark_dirty()

    padding_top = _Prop("_padding_top")

    padding_right = _Prop("_padding_right")

    padding_bottom = _Prop("_padding_bottom")

    padding_left = _Prop("_padding_left")

    @property
    def layout_rect(self) -> LayoutRect:
        return LayoutRect(
            self._x,
            self._y,
            self._layout_width,
            self._layout_height,
            self._padding_left,
            self._padding_right,
            self._padding_top,
            self._padding_bottom,
        )

    overflow = _Prop("_overflow")

    position = _Prop("_position")

    background_color = _Prop("_background_color", _parse_color_static, paint_only=True)

    fg = _Prop("_fg", _parse_color_static, paint_only=True)

    @property
    def border(self) -> bool:
        return self._border

    border_style = _Prop("_border_style", s.parse_border_style, paint_only=True)

    border_color = _Prop("_border_color", _parse_color_static, paint_only=True)

    title = _Prop("_title", paint_only=True)

    @property
    def focusable(self) -> bool:
        return self._focusable

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        if self._focused == value:
            return
        self._focused = value
        self.mark_paint_dirty()

    opacity = _Prop("_opacity", _clamp_opacity, paint_only=True)

    z_index = _Prop("_z_index", hit_paint=True)

    pos_top = _Prop("_pos_top")

    pos_right = _Prop("_pos_right")

    pos_bottom = _Prop("_pos_bottom")

    pos_left = _Prop("_pos_left")

    translate_x = _Prop("_translate_x")

    translate_y = _Prop("_translate_y")

    render_before = _Prop("_render_before", dirty=False)
    render_after = _Prop("_render_after", dirty=False)
    on_size_change = _Prop("_on_size_change", dirty=False)

    on_mouse_down = _Prop("_on_mouse_down", dirty=False)
    on_mouse_up = _Prop("_on_mouse_up", dirty=False)
    on_mouse_move = _Prop("_on_mouse_move", dirty=False)
    on_mouse_drag = _Prop("_on_mouse_drag", dirty=False)
    on_mouse_drag_end = _Prop("_on_mouse_drag_end", dirty=False)
    on_mouse_drop = _Prop("_on_mouse_drop", dirty=False)
    on_mouse_over = _Prop("_on_mouse_over", dirty=False)
    on_mouse_out = _Prop("_on_mouse_out", dirty=False)
    on_mouse_scroll = _Prop("_on_mouse_scroll", dirty=False)
    on_key_down = _Prop("_on_key_down", dirty=False)
    on_paste = _Prop("_on_paste", dirty=False)
    handle_paste = _Prop("_handle_paste", dirty=False)

    selectable = _Prop("_selectable", dirty=False)

    on_lifecycle_pass = _Prop("_on_lifecycle_pass", dirty=False)

    def _configure_yoga_node(self, node: Any) -> None:
        configure_renderable_yoga(
            self,
            node,
            yoga_layout=yoga_layout,
            configure_node_fast=_get_configure_node_fast(),
            column=_COLUMN,
            nowrap=_NOWRAP,
            flex_start=_FLEX_START,
            stretch=_STRETCH,
            visible=_VISIBLE,
            relative=_RELATIVE,
        )

    def _apply_yoga_layout(self) -> None:
        apply_renderable_layout(self)

    def update_layout(self, delta_time: float = 0) -> None:
        pass

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        render_renderable_children(self, buffer, delta_time)


class VRenderable(Renderable):
    """Renderable with a custom render function callback."""

    def __init__(
        self,
        *,
        render_fn: Callable[[Buffer, float, "VRenderable"], None] | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._render_fn = render_fn

    @property
    def render_fn(self) -> Callable | None:
        return self._render_fn

    @render_fn.setter
    def render_fn(self, value: Callable | None) -> None:
        self._render_fn = value
        self.mark_paint_dirty()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return
        if self._render_before:
            self._render_before(buffer, delta_time, self)
        if self._render_fn:
            self._render_fn(buffer, delta_time, self)
        for child in self._children:
            child.render(buffer, delta_time)
        if self._render_after:
            self._render_after(buffer, delta_time, self)


__all__ = [
    "BaseRenderable",
    "LayoutRect",
    "Renderable",
    "VRenderable",
]
