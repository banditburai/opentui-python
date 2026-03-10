"""Components package."""

from .advanced import (
    AsciiFont,
    Code,
    Diff,
    LineNumber,
    Markdown,
    Slider,
    TabSelect,
    TextTable,
)
from .base import BaseRenderable, LayoutOptions, Renderable, StyleOptions
from .box import Box, LinearScrollAccel, MacOSScrollAccel, ScrollBox
from .composition import VRenderable
from .control_flow import For, Match, Show, Switch
from .framebuffer import FrameBuffer
from .input import Input, Select, SelectOption, Textarea
from .scrollbar import ScrollBar
from .text import Bold, Italic, LineBreak, Link, Span, Text, TextModifier, Underline
from .textnode import StyledChunk, TextNode, TextStyle

__all__ = [
    # Base
    "BaseRenderable",
    "Renderable",
    "LayoutOptions",
    "StyleOptions",
    # Box
    "Box",
    "LinearScrollAccel",
    "MacOSScrollAccel",
    "ScrollBox",
    # Text
    "Text",
    "TextModifier",
    "Span",
    "Bold",
    "Italic",
    "Underline",
    "LineBreak",
    "Link",
    # Input
    "Input",
    "Textarea",
    "Select",
    "SelectOption",
    # Advanced
    "Code",
    "Diff",
    "Markdown",
    "LineNumber",
    "AsciiFont",
    "TabSelect",
    "Slider",
    "TextTable",
    # Control flow
    "For",
    "Show",
    "Switch",
    "Match",
    # New components
    "ScrollBar",
    "FrameBuffer",
    "TextNode",
    "TextStyle",
    "StyledChunk",
    "VRenderable",
]
