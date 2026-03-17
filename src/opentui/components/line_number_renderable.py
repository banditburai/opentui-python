"""LineNumberRenderable - renders line number gutter alongside a target renderable.

Line number gutter component for code and diff views.
Renders line numbers, line signs, and line-level background colors
alongside a target renderable that implements the LineInfoProvider protocol.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from .. import structs as s
from ..structs import display_width as _string_width
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


# ── Types ─────────────────────────────────────────────────────────────


@dataclass
class LineSign:
    """Decorative marker for a line number gutter."""

    before: str | None = None
    before_color: s.RGBA | str | None = None
    after: str | None = None
    after_color: s.RGBA | str | None = None


@dataclass
class LineColorConfig:
    """Separate gutter and content background colors for a line."""

    gutter: s.RGBA | str | None = None
    content: s.RGBA | str | None = None


@dataclass
class LineInfo:
    """Line layout info from a target renderable."""

    line_start_cols: list[int] = field(default_factory=list)
    line_width_cols: list[int] = field(default_factory=list)
    line_width_cols_max: int = 0
    line_sources: list[int] = field(default_factory=list)
    line_wraps: list[int] = field(default_factory=list)


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


# ── Helpers ───────────────────────────────────────────────────────────


def _parse_color(color: s.RGBA | str | None) -> s.RGBA | None:
    """Parse a color value to RGBA."""
    if color is None:
        return None
    if isinstance(color, s.RGBA):
        return color
    if isinstance(color, str):
        if color in ("transparent", "none"):
            return None
        return s.parse_color(color)
    return None


def _darken_color(color: s.RGBA) -> s.RGBA:
    """Darken an RGBA color by 20%."""
    return s.RGBA(color.r * 0.8, color.g * 0.8, color.b * 0.8, color.a)


# ── GutterRenderable ─────────────────────────────────────────────────


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
        self._gutter_fg = fg or s.RGBA(0.5, 0.5, 0.5, 1.0)
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

        self._calculate_sign_widths()
        self._last_known_line_count = self._get_target_virtual_line_count()
        self._last_known_scroll_y = self._get_target_scroll_y()
        self._setup_measure_func()

    def _get_target_virtual_line_count(self) -> int:
        """Get virtual line count from target."""
        if hasattr(self._target, "virtual_line_count"):
            return self._target.virtual_line_count
        if hasattr(self._target, "line_count"):
            return self._target.line_count
        return 1

    def _get_target_scroll_y(self) -> int:
        """Get scroll Y from target."""
        if hasattr(self._target, "scroll_y"):
            return self._target.scroll_y
        return 0

    def _get_target_line_info(self) -> LineInfo | None:
        """Get line info from target."""
        if hasattr(self._target, "line_info"):
            return self._target.line_info
        return None

    def _calculate_sign_widths(self) -> None:
        """Calculate max before/after sign widths."""
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
        """Calculate gutter width based on target's line count."""
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
        """Set up yoga measure function for the gutter."""

        def measure(yoga_node, width, width_mode, height, height_mode):
            gutter_width = self._calculate_width()
            gutter_height = self._get_target_virtual_line_count()
            return (gutter_width, gutter_height)

        self._yoga_node.set_measure_func(measure)

    def remeasure(self) -> None:
        """Mark the yoga node as dirty to trigger re-measurement."""
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()

    def set_line_number_offset(self, offset: int) -> None:
        """Set the line number offset."""
        if self._line_number_offset != offset:
            self._line_number_offset = offset
            if self._yoga_node is not None:
                self._yoga_node.mark_dirty()
            self.request_render()

    def set_hide_line_numbers(self, hide_line_numbers: set[int]) -> None:
        """Set which line numbers to hide."""
        self._hide_line_numbers = hide_line_numbers
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.request_render()

    def set_line_numbers(self, line_numbers: dict[int, int]) -> None:
        """Set custom line number mapping."""
        self._line_numbers = line_numbers
        if self._yoga_node is not None:
            self._yoga_node.mark_dirty()
        self.request_render()

    def set_line_colors(
        self,
        line_colors_gutter: dict[int, s.RGBA],
        line_colors_content: dict[int, s.RGBA],
    ) -> None:
        """Update line colors."""
        self._line_colors_gutter = line_colors_gutter
        self._line_colors_content = line_colors_content
        self.request_render()

    def get_line_colors(self) -> dict:
        """Get current line colors."""
        return {
            "gutter": dict(self._line_colors_gutter),
            "content": dict(self._line_colors_content),
        }

    def set_line_signs(self, line_signs: dict[int, LineSign]) -> None:
        """Update line signs."""
        old_max_before = self._max_before_width
        old_max_after = self._max_after_width

        self._line_signs = line_signs
        self._calculate_sign_widths()

        if (
            self._max_before_width != old_max_before or self._max_after_width != old_max_after
        ) and self._yoga_node is not None:
            self._yoga_node.mark_dirty()

        self.request_render()

    def get_line_signs(self) -> dict[int, LineSign]:
        """Get current line signs."""
        return dict(self._line_signs)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the gutter."""
        if not self._visible:
            return
        self._refresh_frame_buffer(buffer)

    def _refresh_frame_buffer(self, buffer: Buffer) -> None:
        """Draw the gutter content to the buffer."""
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
        """Draw a single line number (or nothing for continuation lines)."""
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


# ── LineNumberRenderable ──────────────────────────────────────────────


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
        fg: s.RGBA | str | None = "#888888",
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

        self._ln_fg = _parse_color(fg) or s.RGBA(0.53, 0.53, 0.53, 1.0)
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
        """When line info changes in the target, remeasure the gutter."""
        if self._gutter is not None:
            self._gutter.remeasure()
        self.request_render()

    def _parse_line_color(self, line: int, color: Any) -> None:
        """Parse a line color value into gutter and content colors."""
        if isinstance(color, dict) and ("gutter" in color or "content" in color):
            # LineColorConfig format
            if color.get("gutter"):
                parsed_gutter = _parse_color(color["gutter"])
                if parsed_gutter:
                    self._line_colors_gutter[line] = parsed_gutter
            if color.get("content"):
                parsed_content = _parse_color(color["content"])
                if parsed_content:
                    self._line_colors_content[line] = parsed_content
            elif color.get("gutter"):
                # If only gutter is specified, use a darker version for content
                parsed_gutter = _parse_color(color["gutter"])
                if parsed_gutter:
                    self._line_colors_content[line] = _darken_color(parsed_gutter)
        elif isinstance(color, LineColorConfig):
            if color.gutter:
                parsed_gutter = _parse_color(color.gutter)
                if parsed_gutter:
                    self._line_colors_gutter[line] = parsed_gutter
            if color.content:
                parsed_content = _parse_color(color.content)
                if parsed_content:
                    self._line_colors_content[line] = parsed_content
            elif color.gutter:
                parsed_gutter = _parse_color(color.gutter)
                if parsed_gutter:
                    self._line_colors_content[line] = _darken_color(parsed_gutter)
        elif isinstance(color, str | s.RGBA) or color is None:
            # Simple format - same color for both, but content is darker
            parsed = _parse_color(color)
            if parsed:
                self._line_colors_gutter[line] = parsed
                self._line_colors_content[line] = _darken_color(parsed)

    def _set_target(self, target: Any) -> None:
        """Set up the target renderable."""
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

        # Create gutter
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
        """Override add to intercept and set as target if it's a LineInfoProvider."""
        if self._target is None and self._is_line_info_provider(child):
            self._set_target(child)
            return self.get_children_count() - 1
        return -1

    def _is_line_info_provider(self, obj: Any) -> bool:
        """Check if an object implements the LineInfoProvider interface."""
        return (
            hasattr(obj, "line_info")
            and hasattr(obj, "line_count")
            and hasattr(obj, "virtual_line_count")
            and hasattr(obj, "scroll_y")
        )

    def remove(self, child: Any) -> None:
        """Override remove to prevent removing gutter/target directly."""
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
        """Destroy this renderable and clean up."""
        self._is_destroying = True
        if self._target is not None and hasattr(self._target, "off"):
            self._target.off("line-info-change", self._handle_line_info_change)
        super().destroy()
        self._gutter = None
        self._target = None

    def destroy_recursively(self) -> None:
        """Destroy this renderable and all descendants."""
        self._is_destroying = True
        if self._target is not None and hasattr(self._target, "off"):
            self._target.off("line-info-change", self._handle_line_info_change)
        super().destroy_recursively()
        self._gutter = None
        self._target = None

    def clear_target(self) -> None:
        """Remove the current target."""
        if self._target is not None:
            if hasattr(self._target, "off"):
                self._target.off("line-info-change", self._handle_line_info_change)
            super().remove(self._target)
            self._target = None
        if self._gutter is not None:
            super().remove(self._gutter)
            self._gutter = None

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def gutter(self) -> GutterRenderable | None:
        """Get the gutter renderable (for testing)."""
        return self._gutter

    @property
    def target(self) -> Any:
        """Get the target renderable."""
        return self._target

    @property
    def show_line_numbers(self) -> bool:
        """Get whether line numbers are visible."""
        if self._gutter is not None:
            return self._gutter._visible
        return False

    @show_line_numbers.setter
    def show_line_numbers(self, value: bool) -> None:
        """Set whether line numbers are visible."""
        if self._gutter is not None:
            self._gutter._visible = value
            self.mark_dirty()

    @property
    def line_number_offset(self) -> int:
        """Get the line number offset."""
        return self._ln_line_number_offset

    @line_number_offset.setter
    def line_number_offset(self, value: int) -> None:
        """Set the line number offset."""
        if self._ln_line_number_offset != value:
            self._ln_line_number_offset = value
            if self._gutter is not None:
                self._gutter.set_line_number_offset(value)

    # ── Line color methods ──────────────────────────────────────────────

    def set_line_color(self, line: int, color: Any) -> None:
        """Set color for a specific line."""
        self._parse_line_color(line, color)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def clear_line_color(self, line: int) -> None:
        """Clear color for a specific line."""
        self._line_colors_gutter.pop(line, None)
        self._line_colors_content.pop(line, None)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def clear_all_line_colors(self) -> None:
        """Clear all line colors."""
        self._line_colors_gutter.clear()
        self._line_colors_content.clear()
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def set_line_colors(self, line_colors: dict[int, Any]) -> None:
        """Set multiple line colors at once."""
        self._line_colors_gutter.clear()
        self._line_colors_content.clear()
        for line, color in line_colors.items():
            self._parse_line_color(line, color)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def get_line_colors(self) -> dict:
        """Get current line colors as {gutter: dict, content: dict}."""
        return {
            "gutter": dict(self._line_colors_gutter),
            "content": dict(self._line_colors_content),
        }

    def highlight_lines(self, start_line: int, end_line: int, color: Any) -> None:
        """Apply color to a range of lines (inclusive)."""
        for i in range(start_line, end_line + 1):
            self._parse_line_color(i, color)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    def clear_highlight_lines(self, start_line: int, end_line: int) -> None:
        """Clear color from a range of lines (inclusive)."""
        for i in range(start_line, end_line + 1):
            self._line_colors_gutter.pop(i, None)
            self._line_colors_content.pop(i, None)
        if self._gutter is not None:
            self._gutter.set_line_colors(self._line_colors_gutter, self._line_colors_content)

    # ── Line sign methods ──────────────────────────────────────────────

    def set_line_sign(self, line: int, sign: LineSign) -> None:
        """Set a sign for a specific line."""
        self._line_signs[line] = sign
        if self._gutter is not None:
            self._gutter.set_line_signs(self._line_signs)

    def clear_line_sign(self, line: int) -> None:
        """Clear sign for a specific line."""
        self._line_signs.pop(line, None)
        if self._gutter is not None:
            self._gutter.set_line_signs(self._line_signs)

    def clear_all_line_signs(self) -> None:
        """Clear all line signs."""
        self._line_signs.clear()
        if self._gutter is not None:
            self._gutter.set_line_signs(self._line_signs)

    def set_line_signs(self, line_signs: dict[int, LineSign]) -> None:
        """Set multiple line signs at once."""
        self._line_signs.clear()
        for line, sign in line_signs.items():
            self._line_signs[line] = sign
        if self._gutter is not None:
            self._gutter.set_line_signs(self._line_signs)

    def get_line_signs(self) -> dict[int, LineSign]:
        """Get current line signs."""
        return dict(self._line_signs)

    # ── Hidden line numbers ───────────────────────────────────────────

    def set_hide_line_numbers(self, hide_line_numbers: set[int]) -> None:
        """Set which line numbers to hide."""
        self._ln_hide_line_numbers = hide_line_numbers
        if self._gutter is not None:
            self._gutter.set_hide_line_numbers(hide_line_numbers)

    def get_hide_line_numbers(self) -> set[int]:
        """Get the set of hidden line numbers."""
        return set(self._ln_hide_line_numbers)

    def set_line_numbers_map(self, line_numbers: dict[int, int]) -> None:
        """Set custom line number mapping."""
        self._ln_line_numbers = line_numbers
        if self._gutter is not None:
            self._gutter.set_line_numbers(line_numbers)

    def get_line_numbers_map(self) -> dict[int, int]:
        """Get custom line number mapping."""
        return dict(self._ln_line_numbers)

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the line number renderable and its children."""
        if not self._visible:
            return

        if self._target is not None and self._gutter is not None:
            self._render_line_backgrounds(buffer)

        for child in self._children:
            if isinstance(child, Renderable):
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
        """Get scroll Y from target."""
        if self._target and hasattr(self._target, "scroll_y"):
            return self._target.scroll_y
        return 0

    def _get_target_virtual_line_count(self) -> int:
        """Get virtual line count from target."""
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
