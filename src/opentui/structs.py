"""Struct definitions for OpenTUI."""

from __future__ import annotations

import math
import re
import unicodedata
import warnings
from dataclasses import dataclass
from typing import Any

_HEX_RE = re.compile(r"[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
_RGBA_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)")


@dataclass(slots=True)
class RGBA:
    """RGBA color values (0-1 range)."""

    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 1.0

    @classmethod
    def from_array(cls, values: Any) -> RGBA:
        return cls(float(values[0]), float(values[1]), float(values[2]), float(values[3]))

    @classmethod
    def from_ints(cls, r: int, g: int, b: int, a: int = 255) -> RGBA:
        return cls(r / 255, g / 255, b / 255, a / 255)

    @classmethod
    def from_hex(cls, hex_color: str) -> RGBA:
        """Create RGBA from hex color string.

        Supports: #RGB, #RGBA, #RRGGBB, #RRGGBBAA (with or without #).
        Returns magenta for invalid hex strings.
        """
        hex_color = hex_color.lstrip("#")

        if len(hex_color) == 3:
            hex_color = hex_color[0] * 2 + hex_color[1] * 2 + hex_color[2] * 2
        elif len(hex_color) == 4:
            hex_color = hex_color[0] * 2 + hex_color[1] * 2 + hex_color[2] * 2 + hex_color[3] * 2

        if not _HEX_RE.fullmatch(hex_color):
            warnings.warn(f"Invalid hex color: {hex_color}, defaulting to magenta", stacklevel=2)
            return cls(1.0, 0.0, 1.0, 1.0)

        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        a = int(hex_color[6:8], 16) / 255 if len(hex_color) == 8 else 1.0
        return cls(r, g, b, a)

    def to_ints(self) -> tuple[int, int, int, int]:
        return (round(self.r * 255), round(self.g * 255), round(self.b * 255), round(self.a * 255))

    def to_hex(self) -> str:
        def _c(x: float) -> int:
            return math.floor(max(0.0, min(1.0, x)) * 255)

        if self.a == 1:
            return f"#{_c(self.r):02x}{_c(self.g):02x}{_c(self.b):02x}"
        return f"#{_c(self.r):02x}{_c(self.g):02x}{_c(self.b):02x}{_c(self.a):02x}"

    def __str__(self) -> str:
        return f"rgba({self.r:.2f}, {self.g:.2f}, {self.b:.2f}, {self.a:.2f})"


ColorInput = str | RGBA

CSS_COLOR_NAMES: dict[str, str] = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#008000",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "silver": "#C0C0C0",
    "gray": "#808080",
    "grey": "#808080",
    "maroon": "#800000",
    "olive": "#808000",
    "lime": "#00FF00",
    "aqua": "#00FFFF",
    "teal": "#008080",
    "navy": "#000080",
    "fuchsia": "#FF00FF",
    "purple": "#800080",
    "orange": "#FFA500",
    "brightblack": "#666666",
    "brightred": "#FF6666",
    "brightgreen": "#66FF66",
    "brightblue": "#6666FF",
    "brightyellow": "#FFFF66",
    "brightcyan": "#66FFFF",
    "brightmagenta": "#FF66FF",
    "brightwhite": "#FFFFFF",
}


def parse_color(color: ColorInput) -> RGBA:
    """Parse a color input (string or RGBA) into an RGBA value.

    Supports: hex strings, rgb()/rgba() strings, CSS color names, 'transparent',
    and RGBA pass-through.
    """
    if isinstance(color, RGBA):
        return color

    lower = color.lower().strip()

    if lower == "transparent":
        return RGBA(0.0, 0.0, 0.0, 0.0)

    if lower in CSS_COLOR_NAMES:
        return RGBA.from_hex(CSS_COLOR_NAMES[lower])

    m = _RGBA_RE.match(lower)
    if m:
        r = min(255, max(0, int(m.group(1))))
        g = min(255, max(0, int(m.group(2))))
        b = min(255, max(0, int(m.group(3))))
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        # If alpha > 1, treat as 0-255 integer
        if a > 1:
            a = a / 255
        a = min(1.0, max(0.0, a))
        return RGBA(r / 255, g / 255, b / 255, a)

    return RGBA.from_hex(color)


def parse_color_opt(color: RGBA | str | None) -> RGBA | None:
    """Parse a color with None/transparent/none → None (no color).

    Use this when ``None`` means "no color, terminal default shows through".
    ``parse_color()`` maps "transparent" → ``RGBA(0,0,0,0)`` which would
    paint black; this function maps it to ``None`` so no fill occurs.
    """
    if color is None:
        return None
    if isinstance(color, RGBA):
        return color
    if isinstance(color, str):
        if color in ("transparent", "none"):
            return None
        return parse_color(color)
    return None


VALID_BORDER_STYLES = ("single", "double", "rounded", "heavy", "round", "bold", "block")

BORDER_CHARS: dict[str, dict[str, str]] = {
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
    "rounded": {
        "top_left": "╭",
        "top_right": "╮",
        "bottom_left": "╰",
        "bottom_right": "╯",
        "horizontal": "─",
        "vertical": "│",
    },
    "heavy": {
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
# Legacy aliases
BORDER_CHARS["round"] = BORDER_CHARS["rounded"]
BORDER_CHARS["bold"] = BORDER_CHARS["heavy"]


def get_border_chars(style: str) -> dict[str, str]:
    """Get border characters for a style. Falls back to 'single'."""
    return BORDER_CHARS.get(style, BORDER_CHARS["single"])


def is_valid_border_style(value: Any) -> bool:
    """Check if value is a valid border style string."""
    return isinstance(value, str) and value in VALID_BORDER_STYLES


def parse_border_style(value: Any, fallback: str = "single") -> str:
    """Parse a border style, returning *fallback* for invalid values.

    Logs a warning for invalid non-None values.
    """
    if value == "round":
        value = "rounded"
    elif value == "bold":
        value = "heavy"
    if is_valid_border_style(value):
        return value

    if value is not None:
        warnings.warn(
            f'Invalid borderStyle "{value}", falling back to "{fallback}". '
            f"Valid values are: {', '.join(VALID_BORDER_STYLES)}",
            stacklevel=2,
        )
    return fallback


TEXT_ATTRIBUTE_BOLD = 1 << 0
TEXT_ATTRIBUTE_DIM = 1 << 1
TEXT_ATTRIBUTE_ITALIC = 1 << 2
TEXT_ATTRIBUTE_UNDERLINE = 1 << 3
TEXT_ATTRIBUTE_BLINK = 1 << 4
TEXT_ATTRIBUTE_INVERSE = 1 << 5
TEXT_ATTRIBUTE_HIDDEN = 1 << 6
TEXT_ATTRIBUTE_STRIKETHROUGH = 1 << 7


def char_width(ch: str) -> int:
    """Return the display width of a single character (1 or 2)."""
    eaw = unicodedata.east_asian_width(ch)
    return 2 if eaw in ("W", "F") else 1


def display_width(text: str) -> int:
    """Return the display width of *text*, accounting for wide (CJK/emoji) characters."""
    if text.isascii():
        return len(text)
    w = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


# Named color constants
MUTED_GRAY = RGBA(0.5, 0.5, 0.5, 1.0)
MUTED_GRAY_HEX = "#888888"
FOCUS_RING_BLUE = RGBA(0.3, 0.5, 1.0, 1.0)
SELECTION_BG = RGBA(0.3, 0.3, 0.7, 1.0)
SELECTED_TAB_BG = RGBA(0.2, 0.2, 0.4, 1.0)


__all__ = [
    "RGBA",
    "ColorInput",
    "CSS_COLOR_NAMES",
    "parse_color",
    "is_valid_border_style",
    "parse_border_style",
    "VALID_BORDER_STYLES",
    "BORDER_CHARS",
    "get_border_chars",
    "TEXT_ATTRIBUTE_BOLD",
    "TEXT_ATTRIBUTE_DIM",
    "TEXT_ATTRIBUTE_ITALIC",
    "TEXT_ATTRIBUTE_UNDERLINE",
    "TEXT_ATTRIBUTE_BLINK",
    "TEXT_ATTRIBUTE_INVERSE",
    "TEXT_ATTRIBUTE_HIDDEN",
    "TEXT_ATTRIBUTE_STRIKETHROUGH",
    "parse_color_opt",
    "char_width",
    "display_width",
    "MUTED_GRAY",
    "MUTED_GRAY_HEX",
    "FOCUS_RING_BLUE",
    "SELECTION_BG",
    "SELECTED_TAB_BG",
]
