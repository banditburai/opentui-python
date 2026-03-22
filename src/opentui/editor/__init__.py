"""Editor package — text buffers, edit buffers, editor views, and extmarks."""

from .edit_buffer import EditBuffer, EditorView
from .edit_buffer_native import NativeEditBuffer
from .editor_view_native import NativeEditorView, VisualCursor
from .extmarks import Extmark, ExtmarksController, ExtmarksHistory, ExtmarksSnapshot
from .text_buffer_native import NativeTextBuffer
from .text_view_native import NativeTextBufferView

__all__ = [
    "EditBuffer",
    "EditorView",
    "Extmark",
    "ExtmarksController",
    "ExtmarksHistory",
    "ExtmarksSnapshot",
    "NativeEditBuffer",
    "NativeEditorView",
    "NativeTextBuffer",
    "NativeTextBufferView",
    "VisualCursor",
]
