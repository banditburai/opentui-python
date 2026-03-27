"""StrEnum types for OpenTUI layout properties.

Every member value is ``sys.intern()``-ed so that identity (``is``)
comparisons, dict look-ups, and the Yoga C++ binding's interned-pointer
fast path all work transparently.  Because ``StrEnum`` inherits from
``str``, plain string equality (``==``) continues to work as well —
this module is purely additive.
"""

import sys
from enum import StrEnum


class FlexDirection(StrEnum):
    ROW = sys.intern("row")
    COLUMN = sys.intern("column")
    ROW_REVERSE = sys.intern("row-reverse")
    COLUMN_REVERSE = sys.intern("column-reverse")


class JustifyContent(StrEnum):
    FLEX_START = sys.intern("flex-start")
    FLEX_END = sys.intern("flex-end")
    CENTER = sys.intern("center")
    SPACE_BETWEEN = sys.intern("space-between")
    SPACE_AROUND = sys.intern("space-around")
    SPACE_EVENLY = sys.intern("space-evenly")


class AlignItems(StrEnum):
    STRETCH = sys.intern("stretch")
    FLEX_START = sys.intern("flex-start")
    FLEX_END = sys.intern("flex-end")
    CENTER = sys.intern("center")
    BASELINE = sys.intern("baseline")
    AUTO = sys.intern("auto")


class FlexWrap(StrEnum):
    NOWRAP = sys.intern("nowrap")
    WRAP = sys.intern("wrap")
    WRAP_REVERSE = sys.intern("wrap-reverse")


class Overflow(StrEnum):
    VISIBLE = sys.intern("visible")
    HIDDEN = sys.intern("hidden")
    SCROLL = sys.intern("scroll")


class Position(StrEnum):
    RELATIVE = sys.intern("relative")
    ABSOLUTE = sys.intern("absolute")


class Display(StrEnum):
    FLEX = sys.intern("flex")
    NONE = sys.intern("none")


class BorderStyle(StrEnum):
    SINGLE = sys.intern("single")
    DOUBLE = sys.intern("double")
    ROUND = sys.intern("round")
    BOLD = sys.intern("bold")
    BLOCK = sys.intern("block")


class TitleAlignment(StrEnum):
    LEFT = sys.intern("left")
    CENTER = sys.intern("center")
    RIGHT = sys.intern("right")


class RenderStrategy(StrEnum):
    """Stable render categories used to guide optimization architecture."""

    COMMON_TREE = sys.intern("common_tree")
    NATIVE_TEXT = sys.intern("native_text")
    RETAINED_LAYER = sys.intern("retained_layer")
    HEAVY_WIDGET = sys.intern("heavy_widget")
    PYTHON_FALLBACK = sys.intern("python_fallback")


__all__ = [
    "FlexDirection",
    "JustifyContent",
    "AlignItems",
    "FlexWrap",
    "Overflow",
    "Position",
    "Display",
    "BorderStyle",
    "TitleAlignment",
    "RenderStrategy",
]
