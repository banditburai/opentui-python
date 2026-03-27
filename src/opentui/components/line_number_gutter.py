"""Line-number gutter dataclasses, helpers, and GutterRenderable.

Extracted from ``line_number_renderable.py`` to keep the
``LineNumberRenderable`` wrapper focused on orchestration.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .. import structs as s
from ..renderer.buffer import Buffer
from ..structs import MUTED_GRAY
from ..structs import display_width as _string_width
from ._raster_cache import RasterCache
from .base import Renderable
from .line_types import LineSign


@dataclass
class LineInfo:
    """Line layout info from a target renderable."""

    line_start_cols: list[int] = field(default_factory=list)
    line_width_cols: list[int] = field(default_factory=list)
    line_width_cols_max: int = 0
    line_sources: list[int] = field(default_factory=list)
    line_wraps: list[int] = field(default_factory=list)

    @classmethod
    def from_native_dict(cls, info: dict) -> "LineInfo":
        """Create from native dict, handling both snake_case and camelCase keys."""
        return cls(
            line_start_cols=info.get("start_cols", info.get("lineStartCols", [])),
            line_width_cols=info.get("width_cols", info.get("lineWidthCols", [])),
            line_width_cols_max=info.get("width_cols_max", info.get("lineWidthColsMax", 0)),
            line_sources=info.get("sources", info.get("lineSources", [])),
            line_wraps=info.get("wraps", info.get("lineWraps", [])),
        )


@runtime_checkable
class LineInfoProvider(Protocol):
    """Protocol for renderables that provide line layout info."""

    @property
    def line_info(self) -> LineInfo | None: ...

    @property
    def line_count(self) -> int: ...

    @property
    def virtual_line_count(self) -> int: ...

    @property
    def scroll_y(self) -> int: ...


_parse_color = s.parse_color_opt


def _darken_color(color: s.RGBA) -> s.RGBA:
    return s.RGBA(color.r * 0.8, color.g * 0.8, color.b * 0.8, color.a)


class GutterRenderable(Renderable):
    """Internal renderable that draws the line number gutter.

    This is managed internally by LineNumberRenderable and should not
    be used directly.
    """

    __slots__ = (
        "_target",
        "_gutter_fg",
        "_gutter_bg",
        "_gutter_min_width",
        "_gutter_padding_right",
        "_line_colors_gutter",
        "_line_colors_content",
        "_line_signs",
        "_line_number_offset",
        "_hide_line_numbers",
        "_line_numbers",
        "_max_before_width",
        "_max_after_width",
        "_last_known_line_count",
        "_last_known_scroll_y",
        "_raster",
    )

    def __init__(
        self,
        target: Any,
        *,
        fg: s.RGBA | None = None,
        bg: s.RGBA | None = None,
        min_width: int = 3,
        padding_right: int = 1,
        line_colors_gutter: dict[int, s.RGBA] | None = None,
        line_colors_content: dict[int, s.RGBA] | None = None,
        line_signs: dict[int, LineSign] | None = None,
        line_number_offset: int = 0,
        hide_line_numbers: set[int] | None = None,
        line_numbers: dict[int, int] | None = None,
        id: str | None = None,
    ):
        super().__init__(
            id=id,
            flex_grow=0,
            flex_shrink=0,
        )

        self._target = target
        self._gutter_fg = fg or MUTED_GRAY
        self._gutter_bg = bg
        self._gutter_min_width = min_width
        self._gutter_padding_right = padding_right
        self._line_colors_gutter: dict[int, s.RGBA] = dict(line_colors_gutter or {})
        self._line_colors_content: dict[int, s.RGBA] = dict(line_colors_content or {})
        self._line_signs: dict[int, LineSign] = dict(line_signs or {})
        self._line_number_offset = line_number_offset
        self._hide_line_numbers: set[int] = set(hide_line_numbers or set())
        self._line_numbers: dict[int, int] = dict(line_numbers or {})
        self._max_before_width: int = 0
        self._max_after_width: int = 0
        self._last_known_line_count: int = 0
        self._last_known_scroll_y: int = 0
        self._raster = RasterCache(f"gutter-{self.id}")

        self._calculate_sign_widths()
        self._last_known_line_count = self._get_target_virtual_line_count()
        self._last_known_scroll_y = self._get_target_scroll_y()
        self._setup_measure_func()

    def mark_dirty(self) -> None:
        self._raster.invalidate()
        super().mark_dirty()

    def mark_paint_dirty(self) -> None:
        self._raster.invalidate()
        super().mark_paint_dirty()

    def _get_target_virtual_line_count(self) -> int:
        if hasattr(self._target, "virtual_line_count"):
            return self._target.virtual_line_count
        if hasattr(self._target, "line_count"):
            return self._target.line_count
        return 1

    def _get_target_scroll_y(self) -> int:
        if hasattr(self._target, "scroll_y"):
            return self._target.scroll_y
        return 0

    def _get_target_line_info(self) -> LineInfo | None:
        if hasattr(self._target, "line_info"):
            return self._target.line_info
        return None

    def _calculate_sign_widths(self) -> None:
        self._max_before_width = 0
        self._max_after_width = 0
        for sign in self._line_signs.values():
            if sign.before:
                w = _string_width(sign.before)
                self._max_before_width = max(self._max_before_width, w)
            if sign.after:
                w = _string_width(sign.after)
                self._max_after_width = max(self._max_after_width, w)

    def _calculate_width(self) -> int:
        total_lines = self._get_target_virtual_line_count()

        # Find max line number, considering both calculated and custom line numbers
        max_line_number = total_lines + self._line_number_offset
        if self._line_numbers:
            for custom_num in self._line_numbers.values():
                max_line_number = max(max_line_number, custom_num)

        digits = int(math.log10(max_line_number)) + 1 if max_line_number > 0 else 1
        # +1 for left padding
        base_width = max(self._gutter_min_width, digits + self._gutter_padding_right + 1)
        return base_width + self._max_before_width + self._max_after_width

    def _setup_measure_func(self) -> None:
        def measure(yoga_node, width, width_mode, height, height_mode):
            gutter_width = self._calculate_width()
            gutter_height = self._get_target_virtual_line_count()
            return (gutter_width, gutter_height)

        self._yoga_node.set_measure_func(measure)

    def remeasure(self) -> None:
        self.mark_dirty()
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()

    def set_line_number_offset(self, offset: int) -> None:
        if self._line_number_offset != offset:
            self._line_number_offset = offset
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()
            self.mark_dirty()

    def set_hide_line_numbers(self, hide_line_numbers: set[int]) -> None:
        self._hide_line_numbers = hide_line_numbers
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.mark_dirty()

    def set_line_numbers(self, line_numbers: dict[int, int]) -> None:
        self._line_numbers = line_numbers
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.mark_dirty()

    def set_line_colors(
        self,
        line_colors_gutter: dict[int, s.RGBA],
        line_colors_content: dict[int, s.RGBA],
    ) -> None:
        self._line_colors_gutter = line_colors_gutter
        self._line_colors_content = line_colors_content
        self.mark_paint_dirty()

    def get_line_colors(self) -> dict:
        return {
            "gutter": dict(self._line_colors_gutter),
            "content": dict(self._line_colors_content),
        }

    def set_line_signs(self, line_signs: dict[int, LineSign]) -> None:
        old_max_before = self._max_before_width
        old_max_after = self._max_after_width

        self._line_signs = line_signs
        self._calculate_sign_widths()

        widths_changed = (
            self._max_before_width != old_max_before or self._max_after_width != old_max_after
        )
        if widths_changed:
            self.mark_dirty()
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()
        else:
            self.mark_paint_dirty()

    def get_line_signs(self) -> dict[int, LineSign]:
        return dict(self._line_signs)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return
        scroll_y = self._get_target_scroll_y()
        line_count = self._get_target_virtual_line_count()
        if scroll_y != self._last_known_scroll_y or line_count != self._last_known_line_count:
            self._last_known_scroll_y = scroll_y
            self._last_known_line_count = line_count
            self._raster.invalidate()

        self._raster.render_cached(
            buffer,
            self._x,
            self._y,
            self._layout_width or self._calculate_width(),
            self._layout_height,
            self._refresh_frame_buffer,
        )

    def _refresh_frame_buffer(self, buffer: Buffer) -> None:
        start_x = self._x
        start_y = self._y
        gutter_width = self._layout_width or self._calculate_width()
        gutter_height = self._layout_height or 0

        if gutter_width <= 0 or gutter_height <= 0:
            return

        bg = self._gutter_bg

        if bg:
            buffer.fill_rect(start_x, start_y, gutter_width, gutter_height, bg)

        line_info = self._get_target_line_info()

        if line_info is None or not line_info.line_sources:
            # Simple case: no wrapping info available
            total = self._get_target_virtual_line_count()
            scroll_y = self._get_target_scroll_y()
            for i in range(min(gutter_height, total - scroll_y)):
                logical_line = scroll_y + i
                line_bg = self._line_colors_gutter.get(logical_line, bg)
                if line_bg and line_bg != bg:
                    buffer.fill_rect(start_x, start_y + i, gutter_width, 1, line_bg)
                self._draw_line_number(
                    buffer,
                    start_x,
                    start_y + i,
                    gutter_width,
                    logical_line,
                    line_bg,
                    is_continuation=False,
                )
            return

        sources = line_info.line_sources
        scroll_y = self._get_target_scroll_y()

        if scroll_y >= len(sources):
            return

        last_source = sources[scroll_y - 1] if scroll_y > 0 else -1

        for i in range(gutter_height):
            visual_line_index = scroll_y + i
            if visual_line_index >= len(sources):
                break

            logical_line = sources[visual_line_index]
            line_bg = self._line_colors_gutter.get(logical_line, bg)

            if line_bg and line_bg != bg:
                buffer.fill_rect(start_x, start_y + i, gutter_width, 1, line_bg)

            is_continuation = logical_line == last_source
            self._draw_line_number(
                buffer,
                start_x,
                start_y + i,
                gutter_width,
                logical_line,
                line_bg,
                is_continuation=is_continuation,
            )

            last_source = logical_line

    def _draw_line_number(
        self,
        buffer: Buffer,
        start_x: int,
        y: int,
        gutter_width: int,
        logical_line: int,
        line_bg: s.RGBA | None,
        is_continuation: bool,
    ) -> None:
        if is_continuation:
            return

        current_x = start_x

        sign = self._line_signs.get(logical_line)
        if sign and sign.before:
            before_width = _string_width(sign.before)
            padding = self._max_before_width - before_width
            current_x += padding
            before_color = _parse_color(sign.before_color) if sign.before_color else self._gutter_fg
            buffer.draw_text(sign.before, current_x, y, before_color, line_bg)
            current_x += before_width
        elif self._max_before_width > 0:
            current_x += self._max_before_width

        if logical_line not in self._hide_line_numbers:
            custom_num = self._line_numbers.get(logical_line)
            if custom_num is not None:
                line_num = custom_num
            else:
                line_num = logical_line + 1 + self._line_number_offset

            line_num_str = str(line_num)
            line_num_width = len(line_num_str)
            available_space = (
                gutter_width
                - self._max_before_width
                - self._max_after_width
                - self._gutter_padding_right
            )
            line_num_x = start_x + self._max_before_width + 1 + available_space - line_num_width - 1

            if line_num_x >= start_x + self._max_before_width + 1:
                buffer.draw_text(line_num_str, line_num_x, y, self._gutter_fg, line_bg)

        if sign and sign.after:
            after_x = start_x + gutter_width - self._gutter_padding_right - self._max_after_width
            after_color = _parse_color(sign.after_color) if sign.after_color else self._gutter_fg
            buffer.draw_text(sign.after, after_x, y, after_color, line_bg)

    def destroy(self) -> None:
        """Release retained raster resources before normal teardown."""
        self._raster.release()
        super().destroy()
