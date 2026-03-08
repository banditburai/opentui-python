"""Struct definitions for OpenTUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RGBA:
    """RGBA color values (0-1 range)."""

    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 1.0

    @classmethod
    def from_hex(cls, hex_color: str) -> RGBA:
        """Create RGBA from hex color string (e.g., '#FF0000' or '#FF000080')."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16) / 255
            g = int(hex_color[2:4], 16) / 255
            b = int(hex_color[4:6], 16) / 255
            a = 1.0
        elif len(hex_color) == 8:
            r = int(hex_color[0:2], 16) / 255
            g = int(hex_color[2:4], 16) / 255
            b = int(hex_color[4:6], 16) / 255
            a = int(hex_color[6:8], 16) / 255
        else:
            raise ValueError(f"Invalid hex color: {hex_color}")
        return cls(r, g, b, a)

    def to_hex(self) -> str:
        """Convert to hex color string."""
        r = round(self.r * 255)
        g = round(self.g * 255)
        b = round(self.b * 255)
        a = round(self.a * 255)
        if a < 255:
            return f"#{r:02x}{g:02x}{b:02x}{a:02x}"
        return f"#{r:02x}{g:02x}{b:02x}"


TEXT_ATTRIBUTE_BOLD = 1 << 0           # 0x01
TEXT_ATTRIBUTE_DIM = 1 << 1            # 0x02
TEXT_ATTRIBUTE_ITALIC = 1 << 2         # 0x04
TEXT_ATTRIBUTE_UNDERLINE = 1 << 3      # 0x08
TEXT_ATTRIBUTE_BLINK = 1 << 4          # 0x10
TEXT_ATTRIBUTE_INVERSE = 1 << 5        # 0x20
TEXT_ATTRIBUTE_HIDDEN = 1 << 6         # 0x40
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


__all__ = [
    "RGBA",
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
]
