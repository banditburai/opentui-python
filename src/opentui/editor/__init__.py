"""Editor package — text buffers, edit buffers, editor views, and extmarks."""

from .edit_buffer import EditBuffer, EditorView, create_edit_buffer
from .edit_buffer_native import NativeEditBuffer
from .editor_view_native import NativeEditorView, VisualCursor
from .extmarks import Extmark, ExtmarksController, ExtmarksHistory, ExtmarksSnapshot
from .text_buffer_native import NativeTextBuffer
from .syntax_style import MergedStyle, StyleDefinition, SyntaxStyle, ThemeTokenStyle, convert_theme_to_styles
from .text_view_native import NativeTextBufferView

__all__ = [
    "EditBuffer",
    "EditorView",
    "create_edit_buffer",
    "Extmark",
    "ExtmarksController",
    "ExtmarksHistory",
    "ExtmarksSnapshot",
    "MergedStyle",
    "NativeEditBuffer",
    "NativeEditorView",
    "NativeTextBuffer",
    "NativeTextBufferView",
    "StyleDefinition",
    "SyntaxStyle",
    "ThemeTokenStyle",
    "VisualCursor",
    "convert_theme_to_styles",
]
