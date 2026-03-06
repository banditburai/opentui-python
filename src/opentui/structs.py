"""ctypes struct definitions for OpenTUI FFI."""

import ctypes
from ctypes import (
    POINTER,
    c_bool,
    c_char_p,
    c_float,
    c_size_t,
    c_uint8,
    c_uint32,
    c_uint64,
)


class RGBA(ctypes.Structure):
    """RGBA color values (0-1 range)."""

    _fields_ = [
        ("r", c_float),
        ("g", c_float),
        ("b", c_float),
        ("a", c_float),
    ]

    def __init__(self, r: float = 0, g: float = 0, b: float = 0, a: float = 1):
        super().__init__(r, g, b, a)

    @classmethod
    def from_hex(cls, hex_color: str) -> "RGBA":
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
        r = int(self.r * 255)
        g = int(self.g * 255)
        b = int(self.b * 255)
        a = int(self.a * 255)
        if a < 255:
            return f"#{r:02x}{g:02x}{b:02x}{a:02x}"
        return f"#{r:02x}{g:02x}{b:02x}"


class ExternalCapabilities(ctypes.Structure):
    """Terminal capabilities from the core."""

    _fields_ = [
        ("kitty_keyboard", c_bool),
        ("kitty_graphics", c_bool),
        ("rgb", c_bool),
        ("unicode", c_uint8),
        ("sgr_pixels", c_bool),
        ("color_scheme_updates", c_bool),
        ("explicit_width", c_bool),
        ("scaled_text", c_bool),
        ("sixel", c_bool),
        ("focus_tracking", c_bool),
        ("sync", c_bool),
        ("bracketed_paste", c_bool),
        ("hyperlinks", c_bool),
        ("osc52", c_bool),
        ("explicit_cursor_positioning", c_bool),
        ("term_name", c_char_p),
        ("term_name_len", c_size_t),
        ("term_version", c_char_p),
        ("term_version_len", c_size_t),
        ("term_from_xtversion", c_bool),
    ]


class ExternalCursorState(ctypes.Structure):
    """Cursor state from the core."""

    _fields_ = [
        ("x", c_uint32),
        ("y", c_uint32),
        ("visible", c_bool),
        ("style", c_uint8),
        ("blinking", c_bool),
        ("r", c_float),
        ("g", c_float),
        ("b", c_float),
        ("a", c_float),
    ]


class CursorStyleOptions(ctypes.Structure):
    """Cursor style options."""

    _fields_ = [
        ("style", c_uint8),
        ("blinking", c_uint8),
        ("color", POINTER(c_float)),
        ("cursor", c_uint8),
    ]


class ExternalGridDrawOptions(ctypes.Structure):
    """Grid drawing options."""

    _fields_ = [
        ("draw_inner", c_bool),
        ("draw_outer", c_bool),
    ]


class ExternalBuildOptions(ctypes.Structure):
    """Build options from the core."""

    _fields_ = [
        ("debug", c_bool),
        ("testing", c_bool),
        ("verbose", c_bool),
    ]


class ExternalAllocatorStats(ctypes.Structure):
    """Allocator statistics."""

    _fields_ = [
        ("allocated_bytes", c_uint64),
        ("peak_bytes", c_uint64),
        ("current_allocations", c_uint32),
        ("peak_allocations", c_uint32),
    ]


class ExternalVisualCursor(ctypes.Structure):
    """Visual cursor information."""

    _fields_ = [
        ("x", c_uint32),
        ("y", c_uint32),
        ("width", c_uint32),
        ("height", c_uint32),
    ]


# Text attribute flags
TEXT_ATTRIBUTE_BOLD = 0x0001
TEXT_ATTRIBUTE_ITALIC = 0x0002
TEXT_ATTRIBUTE_UNDERLINE = 0x0004
TEXT_ATTRIBUTE_STRIKETHROUGH = 0x0008
TEXT_ATTRIBUTE_INVERSE = 0x0010
TEXT_ATTRIBUTE_HIDDEN = 0x0020
TEXT_ATTRIBUTE_BLINK = 0x0040


# Border styles
BORDER_STYLE_NONE = 0
BORDER_STYLE_SINGLE = 1
BORDER_STYLE_DOUBLE = 2
BORDER_STYLE_ROUND = 3
BORDER_STYLE_BOLD = 4
BORDER_STYLE_DOUBLE_SINGLE_H = 5
BORDER_STYLE_DOUBLE_SINGLE_V = 6
BORDER_STYLE_BLOCK = 7


# Alignments
ALIGNMENT_LEFT = 0
ALIGNMENT_CENTER = 1
ALIGNMENT_RIGHT = 2


# Flex directions
FLEX_DIRECTION_ROW = 0
FLEX_DIRECTION_COLUMN = 1


# Justify content
JUSTIFY_FLEX_START = 0
JUSTIFY_CENTER = 1
JUSTIFY_FLEX_END = 2
JUSTIFY_SPACE_BETWEEN = 3
JUSTIFY_SPACE_AROUND = 4
JUSTIFY_SPACE_EVENLY = 5


# Align items
ALIGN_ITEMS_FLEX_START = 0
ALIGN_ITEMS_CENTER = 1
ALIGN_ITEMS_FLEX_END = 2
ALIGN_ITEMS_STRETCH = 3
ALIGN_ITEMS_BASELINE = 4


# Width methods
WIDTH_METHOD_WCWIDTH = 0
WIDTH_METHOD_UNICODE = 1


# Buffer ID constants
TEXT_BUFFER_MAIN = 0
TEXT_BUFFER_SELECTION = 1
TEXT_BUFFER_HIGHLIGHT = 2


__all__ = [
    "RGBA",
    "ExternalCapabilities",
    "ExternalCursorState",
    "CursorStyleOptions",
    "ExternalGridDrawOptions",
    "ExternalBuildOptions",
    "ExternalAllocatorStats",
    "ExternalVisualCursor",
    "TEXT_ATTRIBUTE_BOLD",
    "TEXT_ATTRIBUTE_ITALIC",
    "TEXT_ATTRIBUTE_UNDERLINE",
    "TEXT_ATTRIBUTE_STRIKETHROUGH",
    "TEXT_ATTRIBUTE_INVERSE",
    "TEXT_ATTRIBUTE_HIDDEN",
    "TEXT_ATTRIBUTE_BLINK",
    "BORDER_STYLE_NONE",
    "BORDER_STYLE_SINGLE",
    "BORDER_STYLE_DOUBLE",
    "BORDER_STYLE_ROUND",
    "BORDER_STYLE_BOLD",
    "FLEX_DIRECTION_ROW",
    "FLEX_DIRECTION_COLUMN",
    "JUSTIFY_FLEX_START",
    "JUSTIFY_CENTER",
    "JUSTIFY_FLEX_END",
    "ALIGNMENT_LEFT",
    "ALIGNMENT_CENTER",
    "ALIGNMENT_RIGHT",
]
