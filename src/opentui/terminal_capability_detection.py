"""Terminal capability response detection utilities.

Detects various terminal capability response sequences:
- DECRPM (DEC Request Mode): ESC[?...;N$y where N is 0,1,2,3,4
- CPR (Cursor Position Report): ESC[row;colR (used for width detection)
- XTVersion: ESC P >| ... ESC \\
- Kitty Graphics: ESC _ G ... ESC \\
- Kitty Keyboard Query: ESC[?Nu where N is 0,1,2,etc
- DA1 (Device Attributes): ESC[?...c
- Pixel Resolution: ESC[4;height;widtht
"""

from __future__ import annotations

import re

# DECRPM: ESC[?digits;digits$y
_DECRPM_RE = re.compile(r"\x1b\[\?\d+(?:;\d+)*\$y")

# CPR for explicit width/scaled text detection: ESC[1;NR where N >= 2
_CPR_WIDTH_RE = re.compile(r"\x1b\[1;(?!1R)\d+R")

# XTVersion: ESC P >| ... ESC \
_XTVERSION_RE = re.compile(r"\x1bP>\|[\s\S]*?\x1b\\")

# Kitty graphics response: ESC _ G ... ESC \
_KITTY_GRAPHICS_RE = re.compile(r"\x1b_G[\s\S]*?\x1b\\")

# Kitty keyboard query response: ESC[?Nu or ESC[?N;Mu
_KITTY_KB_QUERY_RE = re.compile(r"\x1b\[\?\d+(?:;\d+)?u")

# DA1 (Device Attributes): ESC[?...c
_DA1_RE = re.compile(r"\x1b\[\?[0-9;]*c")

# Pixel resolution: ESC[4;height;widtht
_PIXEL_RES_RE = re.compile(r"\x1b\[4;(\d+);(\d+)t")


def is_capability_response(sequence: str) -> bool:
    """Check if a sequence is a terminal capability response."""
    if _DECRPM_RE.search(sequence):
        return True
    if _CPR_WIDTH_RE.search(sequence):
        return True
    if _XTVERSION_RE.search(sequence):
        return True
    if _KITTY_GRAPHICS_RE.search(sequence):
        return True
    if _KITTY_KB_QUERY_RE.search(sequence):
        return True
    return bool(_DA1_RE.search(sequence))


def is_pixel_resolution_response(sequence: str) -> bool:
    """Check if a sequence is a pixel resolution response."""
    return bool(_PIXEL_RES_RE.search(sequence))


def parse_pixel_resolution(sequence: str) -> dict[str, int] | None:
    """Parse pixel resolution from response sequence.

    Returns {"width": ..., "height": ...} or None if not valid.
    """
    match = _PIXEL_RES_RE.search(sequence)
    if match:
        return {"width": int(match.group(2)), "height": int(match.group(1))}
    return None


__all__ = [
    "is_capability_response",
    "is_pixel_resolution_response",
    "parse_pixel_resolution",
]
