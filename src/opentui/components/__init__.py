"""Components package."""

from .simple import (
    AsciiFont,
    Code,
    Diff,
    LineNumber,
    Markdown,
    Slider,
    TabSelect,
    TextTable,
)
from .base import BaseRenderable, LayoutRect, Renderable, VRenderable
from .box import Box, Column, FlexFill, Row, Spacer
from .code_renderable import (
    CodeRenderable,
    MockTreeSitterClient,
    SyntaxStyle,
    TreeSitterClient,
)
from .control_flow import (
    Dynamic,
    ErrorBoundary,
    For,
    Lazy,
    Match,
    MemoBlock,
    Mount,
    Portal,
    Show,
    Suspense,
    Switch,
    component,
)
from .diff_renderable import DiffRenderable
from .framebuffer import FrameBuffer
from .image import Image
from .input import Input, Select, SelectOption, Textarea
from .input_renderable import InputRenderable
from .line_number_renderable import (
    GutterRenderable,
    LineColorConfig,
    LineInfo,
    LineInfoProvider,
    LineNumberRenderable,
    LineSign,
)
from .scrollbar import ScrollBar
from .scrollbox import LinearScrollAccel, MacOSScrollAccel, ScrollBox, ScrollContent
from .select_renderable import SelectRenderable
from .slider_renderable import SliderRenderable
from .text import Bold, Italic, LineBreak, Link, Span, Text, TextModifier, Underline
from .text_renderable import TextRenderable
from .textarea_renderable import TextareaRenderable
from .textnode import StyledChunk, TextNode, TextStyle, is_textnode_renderable

__all__ = [
    # Base
    "BaseRenderable",
    "LayoutRect",
    "Renderable",
    # Box
    "Box",
    "ScrollContent",
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
    "Dynamic",
    "For",
    "Lazy",
    "MemoBlock",
    "Mount",
    "Portal",
    "Show",
    "Switch",
    "Match",
    "component",
    "ErrorBoundary",
    "Suspense",
    # New components
    "ScrollBar",
    "FrameBuffer",
    "Image",
    "TextNode",
    "TextStyle",
    "StyledChunk",
    "is_textnode_renderable",
    "TextRenderable",
    "InputRenderable",
    "SelectRenderable",
    "SliderRenderable",
    "TextareaRenderable",
    "DiffRenderable",
    "GutterRenderable",
    "LineColorConfig",
    "LineInfo",
    "LineInfoProvider",
    "LineNumberRenderable",
    "LineSign",
    "VRenderable",
    # Helpers
    "Row",
    "Column",
    "FlexFill",
    "Spacer",
    "CodeRenderable",
    "MockTreeSitterClient",
    "SyntaxStyle",
    "TreeSitterClient",
]
