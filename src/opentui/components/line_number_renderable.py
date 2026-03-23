"""LineNumberRenderable - renders line number gutter alongside a target renderable."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..structs import MUTED_GRAY, MUTED_GRAY_HEX
from .base import Renderable
from .line_types import LineColorConfig, LineSign
from .line_number_gutter import (
    GutterRenderable,
    LineInfo,
    LineInfoProvider,
    _darken_color,
    _parse_color,
)

if TYPE_CHECKING:
    from ..renderer import Buffer


class LineNumberRenderable(Renderable):
    """Renderable that displays line numbers alongside a target renderable.

    Line number gutter for code and diff views.

    Usage:
        text = TextRenderable(content="Line 1\\nLine 2\\nLine 3")
        line_nums = LineNumberRenderable(
            target=text,
            min_width=3,
            padding_right=1,
            fg="white",
        )
        root.add(line_nums)
    """

    __slots__ = (
        "_gutter",
        "_target",
        "_line_colors_gutter",
        "_line_colors_content",
        "_line_signs",
        "_ln_fg",
        "_ln_bg",
        "_ln_min_width",
        "_ln_padding_right",
        "_ln_line_number_offset",
        "_ln_hide_line_numbers",
        "_ln_line_numbers",
        "_is_destroying",
        "_handle_line_info_change",
    )

    def __init__(
        self,
        *,
        target: Any = None,
        fg: s.RGBA | str | None = MUTED_GRAY_HEX,
        bg: s.RGBA | str | None = None,
        min_width: int = 3,
        padding_right: int = 1,
        line_colors: dict[int, Any] | None = None,
        line_signs: dict[int, LineSign] | None = None,
        line_number_offset: int = 0,
        hide_line_numbers: set[int] | None = None,
        line_numbers: dict[int, int] | None = None,
        show_line_numbers: bool = True,
        **kwargs,
    ):
        # Force flex direction to row and height to auto
        kwargs["flex_direction"] = "row"
        super().__init__(**kwargs)

        self._ln_fg = _parse_color(fg) or MUTED_GRAY
        self._ln_bg = _parse_color(bg)
        self._ln_min_width = min_width
        self._ln_padding_right = padding_right
        self._ln_line_number_offset = line_number_offset
        self._ln_hide_line_numbers = set(hide_line_numbers or set())
        self._ln_line_numbers = dict(line_numbers or {})
        self._is_destroying = False

        self._line_colors_gutter: dict[int, s.RGBA] = {}
        self._line_colors_content: dict[int, s.RGBA] = {}
        if line_colors:
            for line, color in line_colors.items():
                self._parse_line_color(line, color)

        self._line_signs: dict[int, LineSign] = {}
        if line_signs:
            for line, sign in line_signs.items():
                self._line_signs[line] = sign

        self._gutter: GutterRenderable | None = None
        self._target: Any = None

        self._handle_line_info_change = self._on_line_info_change

        if target is not None:
            self._set_target(target)

        if not show_line_numbers and self._gutter is not None:
            self._gutter._visible = False

    def _on_line_info_change(self) -> None:
        if self._gutter is not None:
            self._gutter.remeasure()
        self.mark_dirty()

    def _parse_line_color(self, line: int, color: Any) -> None:
        # Normalize dict / LineColorConfig to (gutter_raw, content_raw)
        if isinstance(color, dict) and ("gutter" in color or "content" in color):
            gutter_raw, content_raw = color.get("gutter"), color.get("content")
        elif isinstance(color, LineColorConfig):
            gutter_raw, content_raw = color.gutter, color.content
        elif isinstance(color, str | s.RGBA) or color is None:
            parsed = _parse_color(color)
            if parsed:
                self._line_colors_gutter[line] = parsed
                self._line_colors_content[line] = _darken_color(parsed)
            return
        else:
            return

        if gutter_raw:
            parsed_gutter = _parse_color(gutter_raw)
            if parsed_gutter:
                self._line_colors_gutter[line] = parsed_gutter
        if content_raw:
            parsed_content = _parse_color(content_raw)
            if parsed_content:
                self._line_colors_content[line] = parsed_content
        elif gutter_raw:
            # Only gutter specified — derive darker content color
            parsed_gutter = _parse_color(gutter_raw)
            if parsed_gutter:
                self._line_colors_content[line] = _darken_color(parsed_gutter)

    def _set_target(self, target: Any) -> None:
        if self._target is target:
            return

        if self._target is not None:
            if hasattr(self._target, "off"):
                self._target.off("line-info-change", self._handle_line_info_change)
            super().remove(self._target)

        if self._gutter is not None:
            super().remove(self._gutter)
            self._gutter = None

        self._target = target

        # Ensure the target fills remaining space after gutter in row layout
        if self._target._yoga_node is not None:
            self._target._yoga_node.flex_grow = 1
            self._target._yoga_node.flex_shrink = 1

        # Listen for line info changes
        if hasattr(self._target, "on"):
            self._target.on("line-info-change", self._handle_line_info_change)

        self._gutter = GutterRenderable(
            self._target,
            fg=self._ln_fg,
            bg=self._ln_bg,
            min_width=self._ln_min_width,
            padding_right=self._ln_padding_right,
            line_colors_gutter=self._line_colors_gutter,
            line_colors_content=self._line_colors_content,
            line_signs=self._line_signs,
            line_number_offset=self._ln_line_number_offset,
            hide_line_numbers=self._ln_hide_line_numbers,
            line_numbers=self._ln_line_numbers,
            id=f"{self._id}-gutter" if self._id else None,
        )

        super().add(self._gutter)
        super().add(self._target)

    def add(self, child: Any, index: int | None = None) -> int:
        if self._target is None and self._is_line_info_provider(child):
            self._set_target(child)
            return self.get_children_count() - 1
        return -1

    def _is_line_info_provider(self, obj: Any) -> bool:
        return (
            hasattr(obj, "line_info")
            and hasattr(obj, "line_count")
            and hasattr(obj, "virtual_line_count")
            and hasattr(obj, "scroll_y")
        )

    def remove(self, child: Any) -> None:
        if self._is_destroying:
            super().remove(child)
            return

        if self._gutter is not None and child is self._gutter:
            raise ValueError("LineNumberRenderable: Cannot remove gutter directly.")
        if self._target is not None and child is self._target:
            raise ValueError(
                "LineNumberRenderable: Cannot remove target directly. Use clear_target() instead."
            )
        super().remove(child)

    def destroy(self) -> None:
        self._is_destroying = True
        if self._target is not None and hasattr(self._target, "off"):
            self._target.off("line-info-change", self._handle_line_info_change)
        super().destroy()
        self._gutter = None
        self._target = None

    def destroy_recursively(self) -> None:
        self._is_destroying = True
        if self._target is not None and hasattr(self._target, "off"):
            self._target.off("line-info-change", self._handle_line_info_change)
        super().destroy_recursively()
        self._gutter = None
        self._target = None

    def clear_target(self) -> None:
        if self._target is not None:
            if hasattr(self._target, "off"):
                self._target.off("line-info-change", self._handle_line_info_change)
            super().remove(self._target)
            self._target = None
        if self._gutter is not None:
            super().remove(self._gutter)
            self._gutter = None

    @property
    def gutter(self) -> GutterRenderable | None:
        return self._gutter

    @property
    def target(self) -> Any:
        return self._target

    @property
    def show_line_numbers(self) -> bool:
        if self._gutter is not None:
            return self._gutter._visible
        return False

    @show_line_numbers.setter
    def show_line_numbers(self, value: bool) -> None:
        if self._gutter is not None:
            self._gutter._visible = value
            self.mark_dirty()

    @property
    def line_number_offset(self) -> int:
        return self._ln_line_number_offset

    @line_number_offset.setter
    def line_number_offset(self, value: int) -> None:
        if self._ln_line_number_offset != value:
            self._ln_line_number_offset = value
            if self._gutter is not None:
                self._gutter.set_line_number_offset(value)

    def set_line_color(self, line: int, color: Any) -> None:
        self._parse_line_color(line, color)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def clear_line_color(self, line: int) -> None:
        self._line_colors_gutter.pop(line, None)
        self._line_colors_content.pop(line, None)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def clear_all_line_colors(self) -> None:
        self._line_colors_gutter.clear()
        self._line_colors_content.clear()
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def set_line_colors(self, line_colors: dict[int, Any]) -> None:
        self._line_colors_gutter.clear()
        self._line_colors_content.clear()
        for line, color in line_colors.items():
            self._parse_line_color(line, color)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def get_line_colors(self) -> dict:
        return {
            "gutter": dict(self._line_colors_gutter),
            "content": dict(self._line_colors_content),
        }

    def highlight_lines(self, start_line: int, end_line: int, color: Any) -> None:
        for i in range(start_line, end_line + 1):
            self._parse_line_color(i, color)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def clear_highlight_lines(self, start_line: int, end_line: int) -> None:
        for i in range(start_line, end_line + 1):
            self._line_colors_gutter.pop(i, None)
            self._line_colors_content.pop(i, None)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def set_line_sign(self, line: int, sign: LineSign) -> None:
        self._line_signs[line] = sign
        if self._gutter is not None:
            self._gutter.set_line_signs(self._line_signs)

    def clear_line_sign(self, line: int) -> None:
        self._line_signs.pop(line, None)
        if self._gutter is not None:
            self._gutter.set_line_signs(self._line_signs)

    def clear_all_line_signs(self) -> None:
        self._line_signs.clear()
        if self._gutter is not None:
            self._gutter.set_line_signs(self._line_signs)

    def set_line_signs(self, line_signs: dict[int, LineSign]) -> None:
        self._line_signs.clear()
        for line, sign in line_signs.items():
            self._line_signs[line] = sign
        if self._gutter is not None:
            self._gutter.set_line_signs(self._line_signs)

    def get_line_signs(self) -> dict[int, LineSign]:
        return dict(self._line_signs)

    def set_hide_line_numbers(self, hide_line_numbers: set[int]) -> None:
        self._ln_hide_line_numbers = hide_line_numbers
        if self._gutter is not None:
            self._gutter.set_hide_line_numbers(hide_line_numbers)

    def get_hide_line_numbers(self) -> set[int]:
        return set(self._ln_hide_line_numbers)

    def set_line_numbers_map(self, line_numbers: dict[int, int]) -> None:
        self._ln_line_numbers = line_numbers
        if self._gutter is not None:
            self._gutter.set_line_numbers(line_numbers)

    def get_line_numbers_map(self) -> dict[int, int]:
        return dict(self._ln_line_numbers)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        if self._target is not None and self._gutter is not None:
            self._render_line_backgrounds(buffer)
            self._target.render(buffer, delta_time)
            self._gutter.render(buffer, delta_time)
            return

        for child in self._children:
            child.render(buffer, delta_time)

    def _render_line_backgrounds(self, buffer: Buffer) -> None:
        """Draw full-width background colors for lines with custom colors."""
        line_info = None
        if hasattr(self._target, "line_info"):
            line_info = self._target.line_info

        scroll_y = self._get_target_scroll_y()
        gutter_width = self._gutter._layout_width if self._gutter and self._gutter._visible else 0
        content_width = self._layout_width - gutter_width

        if content_width <= 0:
            return

        if line_info is not None and line_info.line_sources:
            sources = line_info.line_sources
            if scroll_y >= len(sources):
                return

            for i in range(self._layout_height):
                visual_line_index = scroll_y + i
                if visual_line_index >= len(sources):
                    break

                logical_line = sources[visual_line_index]
                line_bg = self._line_colors_content.get(logical_line)

                if line_bg:
                    buffer.fill_rect(
                        self._x + gutter_width,
                        self._y + i,
                        content_width,
                        1,
                        line_bg,
                    )
        else:
            # Simple case: no wrapping
            total = self._get_target_virtual_line_count()
            for i in range(self._layout_height):
                logical_line = scroll_y + i
                if logical_line >= total:
                    break

                line_bg = self._line_colors_content.get(logical_line)
                if line_bg:
                    buffer.fill_rect(
                        self._x + gutter_width,
                        self._y + i,
                        content_width,
                        1,
                        line_bg,
                    )

    def _get_target_scroll_y(self) -> int:
        if self._target and hasattr(self._target, "scroll_y"):
            return self._target.scroll_y
        return 0

    def _get_target_virtual_line_count(self) -> int:
        if self._target and hasattr(self._target, "virtual_line_count"):
            return self._target.virtual_line_count
        if self._target and hasattr(self._target, "line_count"):
            return self._target.line_count
        return 1


__all__ = [
    "LineNumberRenderable",
    "GutterRenderable",
    "LineSign",
    "LineColorConfig",
    "LineInfo",
    "LineInfoProvider",
]
