"""Box component - container with borders and layout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..enums import RenderStrategy
from ..signals import is_reactive
from ..structs import display_width as _display_width
from .base import _UNSET_FLEX_SHRINK, BaseRenderable, Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


def _normalize_box_child(child: Any) -> list[BaseRenderable]:
    """Normalize Box children into mounted renderables.

    Common callable/signal child expressions are lowered into Dynamic regions
    so they update locally without forcing parent rebuilds.
    """
    if child is None:
        return []

    if isinstance(child, BaseRenderable):
        return [child]

    if isinstance(child, list | tuple):
        normalized: list[BaseRenderable] = []
        for item in child:
            normalized.extend(_normalize_box_child(item))
        return normalized

    if is_reactive(child):
        from .control_flow import Inserted

        return [Inserted(render=lambda source=child: source())]

    from .text import Text

    if isinstance(child, str):
        return [Text(child)]

    return [Text(str(child))]


class Box(Renderable):
    """Box component - container with optional border and layout.

    Usage:
        box = Box(
            padding=2,
            border=True,
            border_style="rounded",
            children=[
                Text("Hello!"),
            ]
        )
    """

    def __init__(
        self,
        *children: Any,
        # Identity
        key: str | int | None = None,
        id: str | None = None,
        # Layout
        width: int | None = None,
        height: int | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        flex_grow: float = 0,
        flex_shrink: float | object = _UNSET_FLEX_SHRINK,
        flex_basis: float | str | None = None,
        flex_direction: str = "column",
        flex_wrap: str = "nowrap",
        justify_content: str = "flex-start",
        align_items: str = "stretch",
        align_self: str | None = None,
        gap: int = 0,
        # Spacing
        padding: int = 0,
        padding_top: int | None = None,
        padding_right: int | None = None,
        padding_bottom: int | None = None,
        padding_left: int | None = None,
        margin: int = 0,
        margin_top: int | None = None,
        margin_right: int | None = None,
        margin_bottom: int | None = None,
        margin_left: int | None = None,
        # Style
        background_color: s.RGBA | str | None = None,
        fg: s.RGBA | str | None = None,
        border: bool = False,
        border_style: str = "single",
        border_color: s.RGBA | str | None = None,
        title: str | None = None,
        title_alignment: str = "left",
        # Focus
        focusable: bool = False,
        focused: bool = False,
        focused_border_color: s.RGBA | str | None = None,
        # Border sides
        border_top: bool = True,
        border_right: bool = True,
        border_bottom: bool = True,
        border_left: bool = True,
        border_chars: dict | None = None,
        # Overflow
        overflow: str = "visible",
        # Visibility
        visible: bool = True,
        opacity: float = 1.0,
        # Positioning
        position: str = "relative",
        top: float | str | None = None,
        right: float | str | None = None,
        bottom: float | str | None = None,
        left: float | str | None = None,
        z_index: int = 0,
        **kwargs,
    ):
        super().__init__(
            key=key,
            id=id,
            overflow=overflow,
            width=width,
            height=height,
            min_width=min_width,
            min_height=min_height,
            max_width=max_width,
            max_height=max_height,
            flex_grow=flex_grow,
            flex_shrink=flex_shrink,
            flex_basis=flex_basis,
            flex_direction=flex_direction,
            flex_wrap=flex_wrap,
            justify_content=justify_content,
            align_items=align_items,
            align_self=align_self,
            gap=gap,
            padding=padding,
            padding_top=padding_top,
            padding_right=padding_right,
            padding_bottom=padding_bottom,
            padding_left=padding_left,
            margin=margin,
            margin_top=margin_top,
            margin_right=margin_right,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            background_color=background_color,
            fg=fg,
            border=border,
            border_style=border_style,
            border_color=border_color,
            title=title,
            title_alignment=title_alignment,
            focusable=focusable,
            focused=focused,
            focused_border_color=focused_border_color,
            border_top=border_top,
            border_right=border_right,
            border_bottom=border_bottom,
            border_left=border_left,
            border_chars=border_chars,
            visible=visible,
            opacity=opacity,
            position=position,
            top=top,
            right=right,
            bottom=bottom,
            left=left,
            z_index=z_index,
            **kwargs,
        )

        if children:
            normalized = []
            for child in children:
                normalized.extend(_normalize_box_child(child))
            if normalized:
                self.add_children(normalized)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        has_opacity = self._opacity < 1.0
        if has_opacity:
            buffer.push_opacity(self._opacity)

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        # Common container fast path: no chrome, no clipping, just recurse.
        # This avoids width/height setup for plain structural Boxes that wrap
        # stable subtrees or list regions.
        if (
            not self._border
            and not self._focused
            and self._background_color is None
            and self._overflow != "hidden"
        ):
            for child in self._children:
                child.render(buffer, delta_time)
            if self._render_after:
                self._render_after(buffer, delta_time, self)
            if has_opacity:
                buffer.pop_opacity()
            return

        # Use yoga-computed layout dimensions, not the original prop
        width = self._layout_width or buffer.width
        height = self._layout_height or buffer.height

        self._render_chrome(buffer, width, height)

        clip = self._overflow == "hidden"
        if clip:
            buffer.push_scissor_rect(self._x, self._y, width, height)

        for child in self._children:
            child.render(buffer, delta_time)

        if clip:
            buffer.pop_scissor_rect()

        if self._render_after:
            self._render_after(buffer, delta_time, self)

        if has_opacity:
            buffer.pop_opacity()

    def get_render_strategy(self) -> RenderStrategy:
        if (
            self._focused
            or self._overflow == "hidden"
            or self._render_before is not None
            or self._render_after is not None
            or self._border_chars is not None
        ):
            return RenderStrategy.PYTHON_FALLBACK
        return RenderStrategy.COMMON_TREE

    def _render_chrome(self, buffer: Buffer, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return

        use_native_box = self._border and self._border_chars is None
        if use_native_box:
            if self._focused and self._focused_border_color:
                border_color = self._focused_border_color
            else:
                border_color = self._border_color or self._fg
            buffer.draw_box(
                self._x,
                self._y,
                width,
                height,
                self._border_style,
                border_color,
                self._background_color,
                self._title,
                self._title_alignment,
                border_top=self._border_top,
                border_right=self._border_right,
                border_bottom=self._border_bottom,
                border_left=self._border_left,
                should_fill=self._background_color is not None,
            )
        else:
            if self._border:
                self._draw_border(buffer, width, height)
            if self._background_color:
                bg_x = self._x if not self._border else self._x + 1
                bg_y = self._y if not self._border else self._y + 1
                bg_w = width - (2 if self._border else 0)
                bg_h = height - (2 if self._border else 0)
                if bg_w > 0 and bg_h > 0:
                    buffer.fill_rect(bg_x, bg_y, bg_w, bg_h, self._background_color)

        if self._focused:
            self._draw_focus_ring(buffer, width, height)

    def _get_border_chars(self) -> dict:
        if self._border_chars:
            required_keys = {
                "top_left",
                "top_right",
                "bottom_left",
                "bottom_right",
                "horizontal",
                "vertical",
            }
            if required_keys.issubset(self._border_chars.keys()):
                return self._border_chars
        from ..structs import get_border_chars

        return get_border_chars(self._border_style)

    def _draw_border(self, buffer: Buffer, width: int, height: int) -> None:
        if self._focused and self._focused_border_color:
            border_color = self._focused_border_color
        else:
            border_color = self._border_color or self._fg
        bg = self._background_color

        chars = self._get_border_chars()

        if self._border_top and width > 2:
            if self._border_left:
                buffer.draw_text(chars["top_left"], self._x, self._y, border_color, bg)
            start_x = self._x + (1 if self._border_left else 0)
            end_x = self._x + width - (1 if self._border_right else 0)
            if end_x > start_x:
                buffer.draw_text(
                    chars["horizontal"] * (end_x - start_x), start_x, self._y, border_color, bg
                )
            if self._border_right:
                buffer.draw_text(chars["top_right"], self._x + width - 1, self._y, border_color, bg)

        if self._border_bottom and height > 2:
            if self._border_left:
                buffer.draw_text(
                    chars["bottom_left"], self._x, self._y + height - 1, border_color, bg
                )
            start_x = self._x + (1 if self._border_left else 0)
            end_x = self._x + width - (1 if self._border_right else 0)
            if end_x > start_x:
                buffer.draw_text(
                    chars["horizontal"] * (end_x - start_x),
                    start_x,
                    self._y + height - 1,
                    border_color,
                    bg,
                )
            if self._border_right:
                buffer.draw_text(
                    chars["bottom_right"],
                    self._x + width - 1,
                    self._y + height - 1,
                    border_color,
                    bg,
                )

        if self._border_left or self._border_right:
            top_y = self._y + (1 if self._border_top else 0)
            bottom_y = self._y + height - (1 if self._border_bottom else 0)
            for y in range(top_y, bottom_y):
                if self._border_left:
                    buffer.draw_text(chars["vertical"], self._x, y, border_color, bg)
                if self._border_right:
                    buffer.draw_text(chars["vertical"], self._x + width - 1, y, border_color, bg)

        if self._title and self._border_top:
            title_width = _display_width(self._title)
            title_x = self._x + 1
            if self._title_alignment == "center":
                title_x = self._x + (width - title_width) // 2
            elif self._title_alignment == "right":
                title_x = self._x + width - title_width - 2

            buffer.draw_text(self._title, title_x, self._y, border_color, bg)

    def _draw_focus_ring(self, buffer: Buffer, width: int, height: int) -> None:
        focus_color = s.RGBA(0.3, 0.5, 1.0, 1.0)

        top_y = max(0, self._y - 1)
        bottom_y = self._y + height
        left_x = max(0, self._x - 1)
        right_x = self._x + width

        if self._y > 0:
            for x in range(self._x, self._x + width):
                buffer.draw_text("─", x, top_y, focus_color, None)

        if bottom_y < buffer.height:
            for x in range(self._x, self._x + width):
                buffer.draw_text("─", x, bottom_y, focus_color, None)

        if self._x > 0:
            for y in range(self._y, self._y + height):
                buffer.draw_text("│", left_x, y, focus_color, None)

        if right_x < buffer.width:
            for y in range(self._y, self._y + height):
                buffer.draw_text("│", right_x, y, focus_color, None)

        # Corners — only draw when both edges are within bounds
        if self._x > 0 and self._y > 0:
            buffer.draw_text("┌", left_x, top_y, focus_color, None)
        if self._x > 0 and bottom_y < buffer.height:
            buffer.draw_text("└", left_x, bottom_y, focus_color, None)
        if right_x < buffer.width and self._y > 0:
            buffer.draw_text("┐", right_x, top_y, focus_color, None)
        if right_x < buffer.width and bottom_y < buffer.height:
            buffer.draw_text("┘", right_x, bottom_y, focus_color, None)


# Re-export scroll classes for backward compatibility
from .scrollbox import LinearScrollAccel, MacOSScrollAccel, ScrollBox, ScrollContent  # noqa: E402

__all__ = [
    "Box",
    "LinearScrollAccel",
    "MacOSScrollAccel",
    "ScrollBox",
    "ScrollContent",
]
