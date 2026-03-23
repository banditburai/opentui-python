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

from collections.abc import Callable
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
    Box,
    Code,
    Column,
    Diff,
    Dynamic,
    ErrorBoundary,
    FlexFill,
    For,
    FrameBuffer,
    Image,
    Input,
    Italic,
    Lazy,
    LineBreak,
    LineNumber,
    Link,
    LinearScrollAccel,
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
    Show,
    Slider,
    Spacer,
    Span,
    Suspense,
    Switch,
    TabSelect,
    Text,
    Textarea,
    TextTable,
    Underline,
    component,
)
from .components.base import BaseRenderable, LayoutRect, VRenderable
from .components.line_types import LineColorConfig, LineSign
from .components.diff_renderable import DiffRenderable
from .components.input_renderable import InputRenderable
from .components.line_number_renderable import LineNumberRenderable
from .components.select_renderable import SelectRenderable
from .components.text import Bold, TextModifier
from .components.text_renderable import TextRenderable
from .components.textarea_renderable import TextareaRenderable

from .editor.edit_buffer import (
    EditBuffer,
    EditorView,
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

from .helpers import panel, pick

from .image.encoding import (
    ClipboardHandler,
    ImageRenderer,
)
from .image.filters import (
    BlurFilter,
    BrightnessFilter,
    ContrastFilter,
    Filter,
    FilterChain,
    GrayscaleFilter,
    InvertFilter,
    SepiaFilter,
)

from .image.types import (
    DecodedImage,
    ImageFit,
    ImageProtocol,
    ImageSource,
)
from .image.loader import load_image, load_svg
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

from .editor.syntax_style import StyleDefinition, SyntaxStyle as NativeSyntaxStyle
from .tree_sitter_client import PyTreeSitterClient


async def render(
    component_fn: Callable,
    config: CliRendererConfig | dict | None = None,
) -> None:
    """Render a component to the terminal.

    This is the main entry point for OpenTUI Python, matching @opentui/solid's API.

    Args:
        component_fn: A callable that returns a component tree
        config: Optional renderer configuration

    Example:
        @component
        def App():
            return Box(
                Text("Hello, World!"),
                padding=1,
            )

        await render(App)
    """
    if isinstance(config, dict):
        config = CliRendererConfig(**config)
    if config is None:
        config = CliRendererConfig()

    if not config.testing:
        import shutil

        term_size = shutil.get_terminal_size((80, 24))
        if term_size.columns > 0 and term_size.lines > 0:
            from dataclasses import replace

            config = replace(config, width=term_size.columns, height=term_size.lines)

    renderer = await create_cli_renderer(config)

    from .hooks import set_renderer

    set_renderer(renderer)

    from ._signals_runtime import _signal_state

    _signal_state.reset()

    component, _, _ = renderer.evaluate_component(component_fn)

    renderer.root.add(component)

    renderer._component_fn = component_fn
    renderer._signal_state = _signal_state

    try:
        renderer.run()
    finally:
        renderer.destroy()


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
    "NativeSyntaxStyle",
    "StyleDefinition",
    "PyTreeSitterClient",
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
    "panel",
    "pick",
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
