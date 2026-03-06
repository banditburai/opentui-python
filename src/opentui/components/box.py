"""Box component - container with borders and layout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import structs as s
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


# Border style characters
BORDER_CHARS = {
    "single": {
        "top_left": "┌",
        "top_right": "┐",
        "bottom_left": "└",
        "bottom_right": "┘",
        "horizontal": "─",
        "vertical": "│",
    },
    "double": {
        "top_left": "╔",
        "top_right": "╗",
        "bottom_left": "╚",
        "bottom_right": "╝",
        "horizontal": "═",
        "vertical": "║",
    },
    "round": {
        "top_left": "╭",
        "top_right": "╮",
        "bottom_left": "╰",
        "bottom_right": "╯",
        "horizontal": "─",
        "vertical": "│",
    },
    "bold": {
        "top_left": "┏",
        "top_right": "┓",
        "bottom_left": "┗",
        "bottom_right": "┛",
        "horizontal": "━",
        "vertical": "┃",
    },
    "block": {
        "top_left": "█",
        "top_right": "█",
        "bottom_left": "█",
        "bottom_right": "█",
        "horizontal": "█",
        "vertical": "█",
    },
}


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
        # Positional for content
        # Layout
        width: int | None = None,
        height: int | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        flex_grow: float = 0,
        flex_shrink: float = 1,
        flex_direction: str = "column",
        justify_content: str = "flex-start",
        align_items: str = "stretch",
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
        focused: bool = False,
        # Visibility
        visible: bool = True,
        opacity: float = 1.0,
    ):
        super().__init__(
            width=width,
            height=height,
            min_width=min_width,
            min_height=min_height,
            max_width=max_width,
            max_height=max_height,
            flex_grow=flex_grow,
            flex_shrink=flex_shrink,
            flex_direction=flex_direction,
            justify_content=justify_content,
            align_items=align_items,
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
            focused=focused,
            visible=visible,
            opacity=opacity,
        )

        # Add children (both positional and keyword)
        all_children = list(children) if children else []
        for child in all_children:
            if isinstance(child, Renderable):
                self.add(child)
            elif isinstance(child, str):
                from .text import Text

                self.add(Text(child))
            else:
                # Try to render as text
                from .text import Text

                self.add(Text(str(child)))

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the box with border."""
        if not self._visible:
            return

        # Get dimensions
        width = self._width or buffer.width
        height = self._height or buffer.height

        # Draw border if enabled
        if self._border and width > 0 and height > 0:
            self._draw_border(buffer, width, height)

        # Calculate content area
        content_x = self._x + self._padding_left
        content_y = self._y + self._padding_top
        # content_width/content_height available for child layout calculations

        # Draw background for the box
        if self._background_color:
            bg_x = self._x if not self._border else self._x + 1
            bg_y = self._y if not self._border else self._y + 1
            bg_w = width - (2 if self._border else 0)
            bg_h = height - (2 if self._border else 0)
            if bg_w > 0 and bg_h > 0:
                buffer.fill_rect(bg_x, bg_y, bg_w, bg_h, self._background_color)

        # Render children in content area
        for child in self._children:
            if isinstance(child, Renderable):
                # Update child position
                child._x = content_x
                child._y = content_y
                child.render(buffer, delta_time)

    def _draw_border(self, buffer: Buffer, width: int, height: int) -> None:
        """Draw the box border."""
        chars = BORDER_CHARS.get(self._border_style, BORDER_CHARS["single"])

        border_color = self._border_color or self._fg
        bg = self._background_color

        # Top border
        if width > 2:
            buffer.draw_text(chars["top_left"], self._x, self._y, border_color, bg)
            buffer.draw_text(
                chars["horizontal"] * (width - 2), self._x + 1, self._y, border_color, bg
            )
            buffer.draw_text(chars["top_right"], self._x + width - 1, self._y, border_color, bg)

        # Bottom border
        if height > 2:
            buffer.draw_text(chars["bottom_left"], self._x, self._y + height - 1, border_color, bg)
            buffer.draw_text(
                chars["horizontal"] * (width - 2),
                self._x + 1,
                self._y + height - 1,
                border_color,
                bg,
            )
            buffer.draw_text(
                chars["bottom_right"], self._x + width - 1, self._y + height - 1, border_color, bg
            )

        # Left and right borders
        for y in range(self._y + 1, self._y + height - 1):
            buffer.draw_text(chars["vertical"], self._x, y, border_color, bg)
            buffer.draw_text(chars["vertical"], self._x + width - 1, y, border_color, bg)

        # Title
        if self._title:
            title_x = self._x + 1
            if self._title_alignment == "center":
                title_x = self._x + (width - len(self._title)) // 2
            elif self._title_alignment == "right":
                title_x = self._x + width - len(self._title) - 2

            buffer.draw_text(self._title, title_x, self._y, border_color, bg)


class ScrollBox(Box):
    """Scrollable box container.

    Usage:
        scroll = ScrollBox(
            height=10,
            children=[...long content...]
        )
    """

    def __init__(
        self,
        *children: Any,
        # Scroll options
        scroll_x: bool = False,
        scroll_y: bool = True,
        show_scrollbar: bool = True,
        scrollbar_position: str = "right",
        # Box options
        **kwargs,
    ):
        super().__init__(*children, **kwargs)

        self._scroll_x = scroll_x
        self._scroll_y = scroll_y
        self._show_scrollbar = show_scrollbar
        self._scrollbar_position = scrollbar_position
        self._scroll_offset_x = 0
        self._scroll_offset_y = 0

    @property
    def scroll_x(self) -> bool:
        return self._scroll_x

    @property
    def scroll_y(self) -> bool:
        return self._scroll_y

    def scroll_to(self, x: int = 0, y: int = 0) -> None:
        """Scroll to position."""
        if self._scroll_x:
            self._scroll_offset_x = max(0, x)
        if self._scroll_y:
            self._scroll_offset_y = max(0, y)


__all__ = [
    "Box",
    "ScrollBox",
]
