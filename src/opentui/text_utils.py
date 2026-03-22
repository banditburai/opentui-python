"""Text measurement utilities for OpenTUI Python.

Provides text measurement functions for yoga layout integration.
Uses display_width() for correct CJK/emoji double-width handling.
"""

from __future__ import annotations

from .structs import display_width as _dw


def measure_text(text: str, max_width: int, wrap: str = "word") -> tuple[int, int]:
    """Measure text dimensions for yoga layout.

    Args:
        text: The text content to measure
        max_width: Maximum width available (0 for unlimited/unwrapped)
        wrap: Wrap mode - "none", "char", or "word"

    Returns:
        Tuple of (width, height) in display columns
    """
    if not text:
        return (0, 1)

    if wrap == "none":
        return (_dw(text), 1)

    lines = text.split("\n")
    total_height = len(lines)
    max_width_found = 0

    for line in lines:
        if wrap == "word":
            width, additional_lines = _measure_word_wrap(line, max_width)
            total_height += additional_lines
            max_width_found = max(max_width_found, width)
        elif wrap == "char":
            width, additional_lines = _measure_char_wrap(line, max_width)
            total_height += additional_lines
            max_width_found = max(max_width_found, width)
        else:
            max_width_found = max(max_width_found, _dw(line))

    return (max_width_found, total_height)


def _measure_word_wrap(line: str, max_width: int) -> tuple[int, int]:
    """Measure text with word wrapping.

    Returns:
        Tuple of (max_line_width, additional_lines) in display columns
    """
    if max_width <= 0:
        return (_dw(line), 0)

    words = line.split(" ")
    current_width = 0
    max_line_width = 0
    additional_lines = 0

    for word in words:
        word_width = _dw(word)
        if current_width == 0:
            current_width = word_width
        elif current_width + 1 + word_width > max_width:
            max_line_width = max(max_line_width, current_width)
            additional_lines += 1
            current_width = word_width
        else:
            current_width += 1 + word_width

    max_line_width = max(max_line_width, current_width)
    return (max_line_width, additional_lines)


def _measure_char_wrap(line: str, max_width: int) -> tuple[int, int]:
    """Measure text with character wrapping.

    Returns:
        Tuple of (max_line_width, additional_lines) in display columns
    """
    if max_width <= 0:
        return (_dw(line), 0)

    line_width = _dw(line)
    if line_width <= max_width:
        return (line_width, 0)

    additional_lines = (line_width - 1) // max_width
    return (max_width, additional_lines)


def wrap_text(text: str, max_width: int, wrap: str = "word") -> list[str]:
    """Wrap text into lines that fit within max_width.

    Uses display_width() for correct CJK/emoji handling.

    Args:
        text: The text content to wrap
        max_width: Maximum width available (0 for unlimited)
        wrap: Wrap mode - "none", "char", or "word"

    Returns:
        List of wrapped lines
    """
    if not text:
        return [""]

    if wrap == "none" or max_width <= 0:
        return text.split("\n")

    result: list[str] = []
    for line in text.split("\n"):
        if not line:
            result.append("")
            continue

        if wrap == "word":
            result.extend(_wrap_line_word(line, max_width))
        elif wrap == "char":
            result.extend(_wrap_line_char(line, max_width))
        else:
            result.append(line)

    return result


def _wrap_line_word(line: str, max_width: int) -> list[str]:
    """Word-wrap a single line. Returns list of wrapped lines."""
    if _dw(line) <= max_width:
        return [line]

    words = line.split(" ")
    lines: list[str] = []
    current: list[str] = []
    current_width = 0

    for word in words:
        word_width = _dw(word)
        if current_width == 0:
            current.append(word)
            current_width = word_width
        elif current_width + 1 + word_width > max_width:
            lines.append(" ".join(current))
            current = [word]
            current_width = word_width
        else:
            current.append(word)
            current_width += 1 + word_width

    if current:
        lines.append(" ".join(current))

    return lines or [""]


def _wrap_line_char(line: str, max_width: int) -> list[str]:
    """Character-wrap a single line with display-width-aware boundaries."""
    if _dw(line) <= max_width:
        return [line]

    lines: list[str] = []
    current: list[str] = []
    current_width = 0

    for ch in line:
        ch_width = _dw(ch)
        if current_width + ch_width > max_width and current:
            lines.append("".join(current))
            current = [ch]
            current_width = ch_width
        else:
            current.append(ch)
            current_width += ch_width

    if current:
        lines.append("".join(current))

    return lines or [""]
