"""OpenTUI Python - Build terminal UIs with signals.

OpenTUI Python provides a Pythonic API for building terminal user interfaces,
aligned with StarHTML patterns but working directly with Python signals.

Example:
    from opentui import render, Box, Text, Signal, component

    count = Signal(0, name="count")

    @component
    def App():
        return Box(
            Text(lambda: f"Count: {count()}"),
            padding=2,
        )

    await render(App)
"""

from __future__ import annotations

from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("opentui")
except Exception:
    __version__ = "0.1.0"

from . import hooks as hooks
from . import signals as signals

from .context import Context, create_context, use_context

from .enums import (
    AlignItems,
    BorderStyle,
    Display,
    FlexDirection,
    FlexWrap,
    JustifyContent,
    Overflow,
    Position,
    TitleAlignment,
)

from .components import (
    BaseRenderable,
    Bold,
    Box,
    Code,
    Column,
    Diff,
    DiffRenderable,
    Dynamic,
    ErrorBoundary,
    FlexFill,
    For,
    FrameBuffer,
    Image,
    Input,
    InputRenderable,
    Inserted,
    Italic,
    Lazy,
    LayoutRect,
    LineBreak,
    LineColorConfig,
    LineNumber,
    LineNumberRenderable,
    LineSign,
    LinearScrollAccel,
    Link,
    MacOSScrollAccel,
    Markdown,
    Match,
    MemoBlock,
    Mount,
    Portal,
    Renderable,
    Row,
    ScrollBar,
    ScrollBox,
    ScrollContent,
    Select,
    SelectOption,
    SelectRenderable,
    Show,
    Slider,
    Spacer,
    Span,
    Suspense,
    Switch,
    TabSelect,
    Text,
    TextModifier,
    TextRenderable,
    TextTable,
    Textarea,
    TextareaRenderable,
    Underline,
    VRenderable,
    component,
)

from .editor import (
    EditBuffer,
    EditorView,
    StyleDefinition,
    SyntaxStyle,
    create_edit_buffer,
)

from .events import (
    AttachmentPayload,
    FocusEvent,
    KeyEvent,
    Keys,
    MouseButton,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
    click_handler,
    handler,
)


from .image import (
    BlurFilter,
    BrightnessFilter,
    ClipboardHandler,
    ContrastFilter,
    DecodedImage,
    Filter,
    FilterChain,
    GrayscaleFilter,
    ImageFit,
    ImageProtocol,
    ImageRenderer,
    ImageSource,
    InvertFilter,
    SepiaFilter,
    load_image,
    load_svg,
)
from .attachments import detect_dropped_paths, normalize_paste_payload

from .selection import (
    LocalSelectionBounds,
    Selection,
    SelectionAnchor,
    convert_global_to_local_selection,
)

from .animation import Timeline

from .hooks import (
    clear_keyboard_handlers,
    clear_mouse_handlers,
    clear_paste_handlers,
    clear_resize_handlers,
    clear_selection_handlers,
    on_mount,
    use_cursor,
    use_cursor_style,
    use_keyboard,
    use_mouse,
    use_on_resize,
    use_paste,
    use_renderer,
    use_selection_handler,
    use_terminal_dimensions,
    use_timeline,
)

from .renderer import (
    Buffer,
    CliRenderer,
    CliRendererConfig,
    RendererControlState,
    RootRenderable,
    TerminalCapabilities,
    create_cli_renderer,
)

from .resource import Resource, create_resource

from .signals import (
    Batch,
    ReadableSignal,
    Signal,
    computed,
    create_root,
    effect,
    on_cleanup,
    untrack,
    val,
)

from .expr import (
    Conditional,
    Expr,
    MappedExpr,
    all_,
    any_,
    match,
)

from .tree_sitter_client import PyTreeSitterClient


from .app import render
from .diagnostics import enable_diagnostics, disable_diagnostics, get_log_file_path

from .testing import TestSetup, create_test_renderer, test_render


__all__ = [
    "__version__",
    "render",
    "test_render",
    "create_test_renderer",
    "TestSetup",
    "CliRenderer",
    "CliRendererConfig",
    "RendererControlState",
    "TerminalCapabilities",
    "Buffer",
    "RootRenderable",
    "create_cli_renderer",
    "EditBuffer",
    "EditorView",
    "create_edit_buffer",
    "BaseRenderable",
    "LayoutRect",
    "Renderable",
    "Box",
    "Row",
    "Column",
    "FlexFill",
    "Spacer",
    "ScrollContent",
    "ScrollBox",
    "ScrollBar",
    "Dynamic",
    "MemoBlock",
    "Text",
    "TextModifier",
    "Span",
    "Bold",
    "Italic",
    "Underline",
    "LineBreak",
    "LinearScrollAccel",
    "Link",
    "MacOSScrollAccel",
    "Input",
    "Inserted",
    "Textarea",
    "Select",
    "SelectOption",
    "FrameBuffer",
    "Image",
    "InputRenderable",
    "SelectRenderable",
    "TextareaRenderable",
    "TextRenderable",
    "VRenderable",
    "LineColorConfig",
    "LineNumberRenderable",
    "LineSign",
    "For",
    "Lazy",
    "Show",
    "Switch",
    "Match",
    "ErrorBoundary",
    "Suspense",
    "Portal",
    "Mount",
    "component",
    "Code",
    "Diff",
    "DiffRenderable",
    "Markdown",
    "TabSelect",
    "Slider",
    "TextTable",
    "LineNumber",
    "Selection",
    "SelectionAnchor",
    "LocalSelectionBounds",
    "convert_global_to_local_selection",
    "Resource",
    "create_resource",
    "Signal",
    "ReadableSignal",
    "Batch",
    "val",
    "computed",
    "create_root",
    "effect",
    "on_cleanup",
    "untrack",
    "Expr",
    "Conditional",
    "MappedExpr",
    "all_",
    "any_",
    "match",
    "SyntaxStyle",
    "StyleDefinition",
    "PyTreeSitterClient",
    "hooks",
    "signals",
    "Context",
    "create_context",
    "use_context",
    "KeyEvent",
    "MouseEvent",
    "MouseButton",
    "AttachmentPayload",
    "PasteEvent",
    "FocusEvent",
    "ResizeEvent",
    "Keys",
    "handler",
    "click_handler",
    "on_mount",
    "use_renderer",
    "use_terminal_dimensions",
    "use_on_resize",
    "use_keyboard",
    "use_mouse",
    "use_paste",
    "use_cursor",
    "use_cursor_style",
    "use_selection_handler",
    "use_timeline",
    "Timeline",
    "clear_keyboard_handlers",
    "clear_mouse_handlers",
    "clear_paste_handlers",
    "clear_resize_handlers",
    "clear_selection_handlers",
    "ImageRenderer",
    "ClipboardHandler",
    "ImageProtocol",
    "ImageFit",
    "ImageSource",
    "DecodedImage",
    "load_image",
    "load_svg",
    "detect_dropped_paths",
    "normalize_paste_payload",
    "Filter",
    "GrayscaleFilter",
    "BlurFilter",
    "BrightnessFilter",
    "ContrastFilter",
    "SepiaFilter",
    "InvertFilter",
    "FilterChain",
    "enable_diagnostics",
    "disable_diagnostics",
    "get_log_file_path",
    "AlignItems",
    "BorderStyle",
    "Display",
    "FlexDirection",
    "FlexWrap",
    "JustifyContent",
    "Overflow",
    "Position",
    "TitleAlignment",
]
