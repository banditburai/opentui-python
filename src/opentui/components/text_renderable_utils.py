"""Content, wrapping, and layout helpers for TextRenderable."""

from __future__ import annotations

import math
from typing import Any

import yoga

_MEASURE_UNDEFINED = yoga.MeasureMode.Undefined
_MEASURE_AT_MOST = yoga.MeasureMode.AtMost


def get_scroll_adjusted_position(renderable) -> tuple[int, int]:
    sx, sy = 0, 0
    parent = getattr(renderable, "_parent", None)
    while parent is not None:
        if getattr(parent, "_scroll_y", False):
            fn = getattr(parent, "_scroll_offset_y_fn", None)
            sy += int(fn()) if fn else int(getattr(parent, "_scroll_offset_y", 0))
        if getattr(parent, "_scroll_x", False):
            sx += int(getattr(parent, "_scroll_offset_x", 0))
        parent = getattr(parent, "_parent", None)
    return renderable._x - sx, renderable._y - sy


def word_wrap(text: str, width: int) -> list[str]:
    if not text or width <= 0:
        return [text]

    lines: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= width:
            lines.append(remaining)
            break

        break_pos = remaining.rfind(" ", 0, width + 1)
        if break_pos <= 0:
            break_pos = width
            lines.append(remaining[:break_pos])
            remaining = remaining[break_pos:]
        else:
            lines.append(remaining[:break_pos])
            remaining = remaining[break_pos + 1 :]

    return lines if lines else [""]


def coord_to_offset(text_renderable, local_x: int, local_y: int) -> int:
    text = text_renderable.plain_text
    if not text:
        return 0

    orig_lines = text.split("\n")

    if text_renderable._wrap_mode_str == "none" or (text_renderable._layout_width or 0) <= 0:
        y = max(0, local_y + text_renderable._scroll_y)
        if y >= len(orig_lines):
            return len(text)
        offset = sum(len(orig_lines[i]) + 1 for i in range(y))
        offset += max(0, min(local_x, len(orig_lines[y])))
        return min(offset, len(text))

    width = text_renderable._layout_width
    visual_line_offsets: list[int] = []
    base_offset = 0
    for orig_line in orig_lines:
        if not orig_line or len(orig_line) <= width:
            visual_line_offsets.append(base_offset)
        elif text_renderable._wrap_mode_str == "word":
            wrapped = word_wrap(orig_line, width)
            pos = 0
            for wrapped_line in wrapped:
                visual_line_offsets.append(base_offset + pos)
                pos += len(wrapped_line)
                if pos < len(orig_line) and orig_line[pos] == " ":
                    pos += 1
        else:
            for i in range(0, len(orig_line), width):
                visual_line_offsets.append(base_offset + i)
        base_offset += len(orig_line) + 1

    y = max(0, local_y + text_renderable._scroll_y)
    if y >= len(visual_line_offsets):
        return len(text)

    line_start = visual_line_offsets[y]
    if y + 1 < len(visual_line_offsets):
        line_end = visual_line_offsets[y + 1]
        if line_end > 0 and line_end - 1 < len(text) and text[line_end - 1] == "\n":
            line_end -= 1
    else:
        line_end = len(text)

    line_len = line_end - line_start
    col = max(0, min(local_x, line_len))
    return min(line_start + col, len(text))


def sync_text_from_nodes(text_renderable) -> None:
    if text_renderable._has_manual_styled_text:
        return
    plain_text = text_renderable._root_text_node.to_plain_text()
    text_renderable._text_buffer.set_text(plain_text)
    update_text_info(text_renderable)


def update_text_info(text_renderable) -> None:
    if text_renderable._yoga_node is not None:
        text_renderable._yoga_node.mark_dirty()
    update_viewport_offset(text_renderable)
    text_renderable.mark_dirty()


def update_viewport_offset(text_renderable) -> None:
    width = text_renderable._layout_width or 0
    height = text_renderable._layout_height or 0
    if width > 0 and height > 0:
        text_renderable._text_buffer_view.set_viewport(
            text_renderable._scroll_x,
            text_renderable._scroll_y,
            width,
            height,
        )


def setup_text_measure_func(text_renderable) -> None:
    def measure(
        yoga_node: Any, width: float, width_mode: Any, height: float, height_mode: Any
    ) -> tuple[float, float]:
        if width_mode == _MEASURE_UNDEFINED:
            effective_width = 0
        else:
            effective_width = 0 if math.isnan(width) else int(width)

        effective_height = 1 if math.isnan(height) else int(height)
        if effective_height <= 0:
            effective_height = 1

        if effective_width > 0:
            text_renderable._text_buffer_view.set_wrap_width(effective_width)

        result = text_renderable._text_buffer_view.measure_for_dimensions(
            effective_width, max(1, effective_height)
        )

        if result:
            measured_w = max(1, result["widthColsMax"])
            measured_h = max(1, result["lineCount"])
        else:
            measured_w = 1
            measured_h = 1

        if width_mode == _MEASURE_AT_MOST:
            measured_w = min(int(width), measured_w)

        return (measured_w, measured_h)

    text_renderable._yoga_node.set_measure_func(measure)


__all__ = [
    "coord_to_offset",
    "get_scroll_adjusted_position",
    "setup_text_measure_func",
    "sync_text_from_nodes",
    "update_text_info",
    "update_viewport_offset",
    "word_wrap",
]
