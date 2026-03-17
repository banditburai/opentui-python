"""Struct definitions for OpenTUI."""

from __future__ import annotations

import math
import re
import unicodedata
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class RGBA:
    """RGBA color values (0-1 range)."""

    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 1.0

    @classmethod
    def from_array(cls, values: Any) -> RGBA:
        """Create RGBA from an array-like sequence of 4 floats.

        Python dataclass fields are independent values, so this always copies
        the data.
        """
        return cls(float(values[0]), float(values[1]), float(values[2]), float(values[3]))

    @classmethod
    def from_ints(cls, r: int, g: int, b: int, a: int = 255) -> RGBA:
        """Create RGBA from integer values (0-255)."""
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

        if not (
            re.fullmatch(r"[0-9A-Fa-f]{6}", hex_color) or re.fullmatch(r"[0-9A-Fa-f]{8}", hex_color)
        ):
            warnings.warn(f"Invalid hex color: {hex_color}, defaulting to magenta", stacklevel=2)
            return cls(1.0, 0.0, 1.0, 1.0)

        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        a = int(hex_color[6:8], 16) / 255 if len(hex_color) == 8 else 1.0
        return cls(r, g, b, a)

    def to_ints(self) -> tuple[int, int, int, int]:
        """Convert to integer values (0-255)."""
        return (round(self.r * 255), round(self.g * 255), round(self.b * 255), round(self.a * 255))

    def to_hex(self) -> str:
        """Convert to hex color string. Clamps values to 0-1 range."""
        components = [self.r, self.g, self.b] if self.a == 1 else [self.r, self.g, self.b, self.a]
        hex_parts = []
        for x in components:
            val = math.floor(max(0.0, min(1.0, x)) * 255)
            h = format(val, "x")
            hex_parts.append(h.zfill(2))
        return "#" + "".join(hex_parts)

    def map(self, fn: Callable[[float], T]) -> list[T]:
        """Apply function to each channel, return [fn(r), fn(g), fn(b), fn(a)]."""
        return [fn(self.r), fn(self.g), fn(self.b), fn(self.a)]

    def __str__(self) -> str:
        """Format as rgba string with 2 decimal places."""
        return f"rgba({self.r:.2f}, {self.g:.2f}, {self.b:.2f}, {self.a:.2f})"

    def equals(self, other: RGBA | None) -> bool:
        """Check equality with another RGBA."""
        if other is None:
            return False
        return self.r == other.r and self.g == other.g and self.b == other.b and self.a == other.a


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

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


def hsv_to_rgb(h: float, s: float, v: float) -> RGBA:
    """Convert HSV to RGBA. Hue in degrees (0-360), S and V in 0-1."""
    i = math.floor(h / 60) % 6
    f = h / 60 - math.floor(h / 60)
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)

    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q

    return RGBA(r, g, b, 1.0)


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

    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)", lower)
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


# ---------------------------------------------------------------------------
# Border utilities
# ---------------------------------------------------------------------------

VALID_BORDER_STYLES = ("single", "double", "rounded", "heavy")

BorderStyle = str  # one of VALID_BORDER_STYLES


def is_valid_border_style(value: Any) -> bool:
    """Check if value is a valid border style string."""
    return isinstance(value, str) and value in VALID_BORDER_STYLES


def parse_border_style(value: Any, fallback: str = "single") -> str:
    """Parse a border style, returning *fallback* for invalid values.

    Logs a warning for invalid non-None values.
    """
    if is_valid_border_style(value):
        return value

    if value is not None:
        warnings.warn(
            f'Invalid borderStyle "{value}", falling back to "{fallback}". '
            f"Valid values are: {', '.join(VALID_BORDER_STYLES)}",
            stacklevel=2,
        )
    return fallback


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEXT_ATTRIBUTE_BOLD = 1 << 0  # 0x01
TEXT_ATTRIBUTE_DIM = 1 << 1  # 0x02
TEXT_ATTRIBUTE_ITALIC = 1 << 2  # 0x04
TEXT_ATTRIBUTE_UNDERLINE = 1 << 3  # 0x08
TEXT_ATTRIBUTE_BLINK = 1 << 4  # 0x10
TEXT_ATTRIBUTE_INVERSE = 1 << 5  # 0x20
TEXT_ATTRIBUTE_HIDDEN = 1 << 6  # 0x40
TEXT_ATTRIBUTE_STRIKETHROUGH = 1 << 7  # 0x80


BORDER_STYLE_NONE = 0
BORDER_STYLE_SINGLE = 1
BORDER_STYLE_DOUBLE = 2
BORDER_STYLE_ROUND = 3
BORDER_STYLE_BOLD = 4
BORDER_STYLE_DOUBLE_SINGLE_H = 5
BORDER_STYLE_DOUBLE_SINGLE_V = 6
BORDER_STYLE_BLOCK = 7


ALIGNMENT_LEFT = 0
ALIGNMENT_CENTER = 1
ALIGNMENT_RIGHT = 2


FLEX_DIRECTION_ROW = 0
FLEX_DIRECTION_COLUMN = 1


JUSTIFY_FLEX_START = 0
JUSTIFY_CENTER = 1
JUSTIFY_FLEX_END = 2
JUSTIFY_SPACE_BETWEEN = 3
JUSTIFY_SPACE_AROUND = 4
JUSTIFY_SPACE_EVENLY = 5


ALIGN_ITEMS_FLEX_START = 0
ALIGN_ITEMS_CENTER = 1
ALIGN_ITEMS_FLEX_END = 2
ALIGN_ITEMS_STRETCH = 3
ALIGN_ITEMS_BASELINE = 4


WIDTH_METHOD_WCWIDTH = 0
WIDTH_METHOD_UNICODE = 1


TEXT_BUFFER_MAIN = 0
TEXT_BUFFER_SELECTION = 1
TEXT_BUFFER_HIGHLIGHT = 2


# ---------------------------------------------------------------------------
# Display width utilities
# ---------------------------------------------------------------------------


def char_width(ch: str) -> int:
    """Return the display width of a single character (1 or 2)."""
    eaw = unicodedata.east_asian_width(ch)
    return 2 if eaw in ("W", "F") else 1


def display_width(text: str) -> int:
    """Return the display width of *text*, accounting for wide (CJK/emoji) characters."""
    if all(c < "\x80" for c in text):
        return len(text)
    w = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


__all__ = [
    "RGBA",
    "ColorInput",
    "CSS_COLOR_NAMES",
    "hsv_to_rgb",
    "parse_color",
    "is_valid_border_style",
    "parse_border_style",
    "VALID_BORDER_STYLES",
    "TEXT_ATTRIBUTE_BOLD",
    "TEXT_ATTRIBUTE_DIM",
    "TEXT_ATTRIBUTE_ITALIC",
    "TEXT_ATTRIBUTE_UNDERLINE",
    "TEXT_ATTRIBUTE_BLINK",
    "TEXT_ATTRIBUTE_INVERSE",
    "TEXT_ATTRIBUTE_HIDDEN",
    "TEXT_ATTRIBUTE_STRIKETHROUGH",
    "BORDER_STYLE_NONE",
    "BORDER_STYLE_SINGLE",
    "BORDER_STYLE_DOUBLE",
    "BORDER_STYLE_ROUND",
    "BORDER_STYLE_BOLD",
    "BORDER_STYLE_DOUBLE_SINGLE_H",
    "BORDER_STYLE_DOUBLE_SINGLE_V",
    "BORDER_STYLE_BLOCK",
    "ALIGNMENT_LEFT",
    "ALIGNMENT_CENTER",
    "ALIGNMENT_RIGHT",
    "FLEX_DIRECTION_ROW",
    "FLEX_DIRECTION_COLUMN",
    "JUSTIFY_FLEX_START",
    "JUSTIFY_CENTER",
    "JUSTIFY_FLEX_END",
    "JUSTIFY_SPACE_BETWEEN",
    "JUSTIFY_SPACE_AROUND",
    "JUSTIFY_SPACE_EVENLY",
    "ALIGN_ITEMS_FLEX_START",
    "ALIGN_ITEMS_CENTER",
    "ALIGN_ITEMS_FLEX_END",
    "ALIGN_ITEMS_STRETCH",
    "ALIGN_ITEMS_BASELINE",
    "WIDTH_METHOD_WCWIDTH",
    "WIDTH_METHOD_UNICODE",
    "TEXT_BUFFER_MAIN",
    "TEXT_BUFFER_SELECTION",
    "TEXT_BUFFER_HIGHLIGHT",
    "char_width",
    "display_width",
]
