"""Text measurement utilities for OpenTUI Python.

Provides text measurement functions for yoga layout integration.
"""

from __future__ import annotations


def measure_text(text: str, max_width: int, wrap: str = "word") -> tuple[int, int]:
    """Measure text dimensions for yoga layout.

    Args:
        text: The text content to measure
        max_width: Maximum width available (0 for unlimited/unwrapped)
        wrap: Wrap mode - "none", "char", or "word"

    Returns:
        Tuple of (width, height) in character cells
    """
    if not text:
        return (0, 1)

    if wrap == "none":
        return (len(text), 1)

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
            max_width_found = max(max_width_found, len(line))

    return (max_width_found, total_height)


def _measure_word_wrap(line: str, max_width: int) -> tuple[int, int]:
    """Measure text with word wrapping.

    Args:
        line: A single line of text
        max_width: Maximum width before wrapping

    Returns:
        Tuple of (max_line_width, additional_lines)
    """
    if max_width <= 0:
        return (len(line), 0)

    words = line.split(" ")
    current_width = 0
    max_line_width = 0
    additional_lines = 0

    for word in words:
        word_width = len(word)
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

    Args:
        line: A single line of text
        max_width: Maximum width before wrapping

    Returns:
        Tuple of (max_line_width, additional_lines)
    """
    if max_width <= 0:
        return (len(line), 0)

    line_len = len(line)
    if line_len <= max_width:
        return (line_len, 0)

    additional_lines = (line_len - 1) // max_width
    return (max_width, additional_lines)
