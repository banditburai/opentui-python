"""OpenTUI Python - Build terminal UIs with signals.

OpenTUI Python provides a Pythonic API for building terminal user interfaces,
aligned with StarHTML patterns but working directly with Python signals.

Example:
    from opentui import render, Box, Text, Signal, reactive, template_component

    count = Signal(0, name="count")

    @template_component
    def App():
        return Box(
            Text(reactive(lambda: f"Count: {count()}"), id="count"),
            padding=2,
        )

    await render(App)
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import version as _pkg_version
from typing import Any

try:
    __version__ = _pkg_version("opentui")
except Exception:
    __version__ = "0.1.0"

from . import hooks as hooks
from . import signals as signals_module

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
    AsciiFont,
    BaseRenderable,
    Bold,
    Box,
    Code,
    Diff,
    DiffRenderable,
    Dynamic,
    ErrorBoundary,
    For,
    FrameBuffer,
    GutterRenderable,
    Image,
    Input,
    Italic,
    LayoutOptions,
    LineBreak,
    LineColorConfig,
    LineInfo,
    LineInfoProvider,
    LineNumber,
    LineNumberRenderable,
    LineSign,
    Link,
    LinearScrollAccel,
    MacOSScrollAccel,
    Markdown,
    Match,
    MemoBlock,
    MountedTemplate,
    Portal,
    Renderable,
    ScrollBar,
    ScrollBox,
    ScrollContent,
    Select,
    SelectOption,
    Show,
    Slider,
    Span,
    Suspense,
    StyleOptions,
    StyledChunk,
    Switch,
    TabSelect,
    Text,
    Textarea,
    TextModifier,
    TextNode,
    InputRenderable,
    SelectRenderable,
    TextareaRenderable,
    TextRenderable,
    TextStyle,
    TextTable,
    Template,
    TemplateBinding,
    Underline,
    VRenderable,
    bind,
    reactive,
    template,
    template_component,
)

from .edit_buffer import (
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
)

from .filters import (
    BlurFilter,
    BrightnessFilter,
    ContrastFilter,
    Filter,
    FilterChain,
    GrayscaleFilter,
    ImageRenderer,
    InvertFilter,
    SepiaFilter,
    ClipboardHandler,
)

from .image import (
    DecodedImage,
    ImageFit,
    ImageProtocol,
    ImageSource,
)
from .image_loader import load_image, load_svg
from .attachments import detect_dropped_paths, normalize_paste_payload

from .selection import (
    LocalSelectionBounds,
    Selection,
    SelectionAnchor,
    convert_global_to_local_selection,
)

from .hooks import (
    Animation,
    Timeline,
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

from .testing import MockInput, MockMouse

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
)

from .expr import (
    Assignment,
    BinaryOp,
    Conditional,
    Expr,
    Literal,
    MethodCall,
    PropertyAccess,
    UnaryOp,
    all_,
    any_,
    match,
)

_component_catalogue: dict[str, type] = {
    "box": Box,
    "scrollbox": ScrollBox,
    "scrollcontent": ScrollContent,
    "scrollbar": ScrollBar,
    "text": Text,
    "span": Span,
    "b": Bold,
    "bold": Bold,
    "i": Italic,
    "italic": Italic,
    "u": Underline,
    "underline": Underline,
    "br": LineBreak,
    "link": Link,
    "input": Input,
    "textarea": Textarea,
    "select": Select,
    "tab_select": TabSelect,
    "code": Code,
    "diff": Diff,
    "markdown": Markdown,
    "line_number": LineNumber,
    "ascii_font": AsciiFont,
    "slider": Slider,
    "table": TextTable,
    "framebuffer": FrameBuffer,
    "vrenderable": VRenderable,
}


def extend(components: dict[str, type]) -> None:
    """Extend the component catalogue with custom components.

    Args:
        components: Dict mapping component names to classes

    Example:
        class CustomButton(Box):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, border=True, **kwargs)

        extend({"custom_button": CustomButton})
    """
    _component_catalogue.update(components)


def get_component_catalogue() -> dict[str, type]:
    return _component_catalogue.copy()


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
        @template_component
        def App():
            return Box(
                padding=1,
                Text(reactive(lambda: "Hello, World!"), id="greeting"),
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

    from .signals import _signal_state

    _signal_state.reset()

    component, _, _ = renderer.evaluate_component(component_fn)

    import logging as _logging

    _render_log = _logging.getLogger("opentui.renderer")
    _render_log.warning(
        "evaluate_component: result type=%s flex_grow=%s children=%d",
        type(component).__name__,
        getattr(component, "_flex_grow", "?"),
        len(getattr(component, "_children", [])),
    )
    _render_log.warning(
        "root before add: type=%s children=%d size=%dx%d",
        type(renderer.root).__name__,
        len(renderer.root._children),
        renderer.width,
        renderer.height,
    )

    renderer.root.add(component)

    _render_log.warning(
        "root after add: children=%d subtree_dirty=%s",
        len(renderer.root._children),
        renderer.root._subtree_dirty,
    )

    renderer._component_fn = component_fn
    renderer._signal_state = _signal_state

    try:
        renderer.run()
    finally:
        renderer.destroy()


async def test_render(
    component_fn: Callable,
    options: dict | None = None,
) -> TestSetup:
    """Create a test renderer for testing components.

    Args:
        component_fn: A callable that returns a component tree
        options: Test options like {"width": 80, "height": 24}

    Returns:
        TestSetup with renderer and utilities

    Example:
        setup = await test_render(MyComponent, {"width": 40, "height": 10})
        buffer = setup.get_buffer()
        # Assert on buffer contents
    """
    test_options = options or {}

    config = CliRendererConfig(
        width=test_options.get("width", 80),
        height=test_options.get("height", 24),
        testing=True,
        exit_on_ctrl_c=False,
    )

    setup = await _init_test_renderer(config)

    from .signals import _signal_state

    component, _, _ = setup.renderer.evaluate_component(component_fn)

    setup.renderer.root.add(component)

    setup.renderer._component_fn = component_fn
    setup.renderer._signal_state = _signal_state

    return setup


async def create_test_renderer(
    width: int = 80,
    height: int = 24,
    **options,
) -> TestSetup:
    """Create a test renderer without an initial component.

    Unlike ``test_render()``, this does not create a component tree.
    Callers add renderables directly to ``setup.renderer.root``.

    Args:
        width: Terminal width
        height: Terminal height
        use_mouse: If True/False, explicitly set mouse tracking state.
        auto_focus: If False, disable click-to-focus behaviour.

    Returns:
        TestSetup with renderer and utilities

    Example:
        setup = await create_test_renderer(40, 10)
        text = TextRenderable(content="Hello")
        setup.renderer.root.add(text)
        frame = setup.capture_char_frame()
    """
    config = CliRendererConfig(
        width=width,
        height=height,
        testing=True,
        exit_on_ctrl_c=False,
        use_mouse=options.get("use_mouse"),
        auto_focus=options.get("auto_focus", True),
        experimental_split_height=options.get("experimental_split_height"),
    )

    return await _init_test_renderer(config)


async def _init_test_renderer(config: CliRendererConfig) -> TestSetup:
    """Shared setup for test_render() and create_test_renderer()."""
    renderer = await create_cli_renderer(config)
    renderer.setup()

    from .hooks import set_renderer

    set_renderer(renderer)
    clear_keyboard_handlers()
    clear_mouse_handlers()
    clear_paste_handlers()
    clear_resize_handlers()
    clear_selection_handlers()

    from .signals import _signal_state

    _signal_state.reset()

    return TestSetup(renderer)


class TestSetup:
    __test__ = False  # Not a pytest test class

    def __init__(self, renderer: CliRenderer):
        self._renderer = renderer
        self._mock_input: MockInput | None = None
        self._mock_mouse: MockMouse | None = None
        self._test_input_handler: Any = None
        self._stdin_bridge: Any = None
        self._stdin_input: Any = None
        self._stdin_mouse: Any = None

    @property
    def renderer(self) -> CliRenderer:
        return self._renderer

    @property
    def mock_input(self) -> MockInput:
        """Lazy-created MockInput instance (high-level, bypasses input parser)."""
        if self._mock_input is None:
            from .testing import MockInput

            self._mock_input = MockInput(self)
        return self._mock_input

    @property
    def mock_mouse(self) -> MockMouse:
        """Lazy-created MockMouse instance (high-level, bypasses input parser)."""
        if self._mock_mouse is None:
            from .testing import MockMouse

            self._mock_mouse = MockMouse(self)
        return self._mock_mouse

    def _ensure_stdin_input(self) -> None:
        """Lazily create the stdin-level TestInputHandler and wire up
        the same event handlers that ``CliRenderer.run()`` would register."""
        if self._test_input_handler is not None:
            return

        from .input import TestInputHandler
        from .testing import _TestStdinBridge

        handler = TestInputHandler()
        handler.start()

        # Use dynamic dispatchers so handlers registered *after* setup
        # (e.g. by components during mount) are picked up at event time.
        def _key_dispatcher(event: Any) -> None:
            for h in self._renderer._get_event_forwarding().get("key", []):
                if event.propagation_stopped:
                    break
                h(event)
            for h in list(hooks.get_keyboard_handlers()):
                if event.propagation_stopped:
                    break
                h(event)

        def _paste_dispatcher(event: Any) -> None:
            for h in self._renderer._get_event_forwarding().get("paste", []):
                if event.propagation_stopped:
                    break
                h(event)
            for h in list(hooks.get_paste_handlers()):
                if event.propagation_stopped:
                    break
                h(event)

        handler.on_key(_key_dispatcher)
        handler.on_paste(_paste_dispatcher)
        handler.on_mouse(self._renderer._dispatch_mouse_event)

        renderer = self._renderer
        renderer._should_restore_modes = False

        def _on_focus(focus_type: str) -> None:
            if focus_type == "blur":
                renderer._should_restore_modes = True
                renderer.emit_event("blur")
            elif focus_type == "focus":
                if renderer._should_restore_modes:
                    renderer._should_restore_modes = False
                    renderer._restore_terminal_modes()
                renderer.emit_event("focus")
            # Forward to registered focus handlers
            for h in hooks.get_focus_handlers():
                h(focus_type)

        handler.on_focus(_on_focus)

        def _on_capability(cap: dict) -> None:
            renderer.emit_event("capabilities", cap)

        handler.on_capability(_on_capability)

        self._test_input_handler = handler
        self._stdin_bridge = _TestStdinBridge(handler)

    @property
    def stdin_input(self) -> Any:
        """Stdin-level mock keyboard (raw escape sequences through full parser).

        Returns a :class:`MockKeys` instance wired to a ``TestInputHandler``
        that parses raw bytes through the same pipeline as production input.
        """
        self._ensure_stdin_input()
        if self._stdin_input is None:
            from .testing import MockKeys

            self._stdin_input = MockKeys(self._stdin_bridge)
        return self._stdin_input

    @property
    def stdin_mouse(self) -> Any:
        """Stdin-level mock mouse (SGR escape sequences through full parser).

        Returns an :class:`SGRMockMouse` instance wired to a ``TestInputHandler``
        that parses raw mouse sequences through the same pipeline as production.
        """
        self._ensure_stdin_input()
        if self._stdin_mouse is None:
            from .testing import SGRMockMouse

            self._stdin_mouse = SGRMockMouse(self._stdin_bridge)
        return self._stdin_mouse

    @property
    def stdin(self) -> Any:
        """Raw stdin bridge — call ``setup.stdin.emit("data", bytes)`` to feed
        raw escape sequences through the full parser pipeline.
        """
        self._ensure_stdin_input()
        return self._stdin_bridge

    def get_buffer(self) -> Buffer:
        return self._renderer.get_current_buffer()

    def capture_char_frame(self) -> str:
        self.render_frame()
        buf = self.get_buffer()
        return buf.get_plain_text()

    def render_frame(self) -> None:
        self._renderer._render_frame(1.0 / 60)

    def resize(self, width: int, height: int) -> None:
        self._renderer.resize(width, height)
        if self._renderer._root is not None:
            self._renderer._root._width = width
            self._renderer._root._height = height
        hooks._set_terminal_dimensions(width, height)
        for handler in hooks.get_resize_handlers():
            handler(width, height)

    def capture_spans(self) -> Any:
        """Capture the current buffer as styled spans.

        Returns a :class:`CapturedFrame` with cols, rows, lines, and cursor.
        """
        from .testing import capture_spans as _capture_spans

        return _capture_spans(self._renderer)

    def destroy(self) -> None:
        self._renderer.destroy()
        if self._test_input_handler is not None:
            self._test_input_handler.destroy()
            self._test_input_handler = None


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
    "Renderable",
    "LayoutOptions",
    "StyleOptions",
    "Box",
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
    "TextNode",
    "InputRenderable",
    "SelectRenderable",
    "TextareaRenderable",
    "TextRenderable",
    "TextStyle",
    "StyledChunk",
    "GutterRenderable",
    "LineColorConfig",
    "LineInfo",
    "LineInfoProvider",
    "LineNumberRenderable",
    "LineSign",
    "VRenderable",
    "For",
    "Show",
    "Switch",
    "Match",
    "ErrorBoundary",
    "Suspense",
    "Portal",
    "MountedTemplate",
    "Template",
    "TemplateBinding",
    "reactive",
    "bind",
    "template",
    "template_component",
    "Code",
    "Diff",
    "DiffRenderable",
    "Markdown",
    "AsciiFont",
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
    "computed",
    "create_root",
    "effect",
    "on_cleanup",
    "untrack",
    "Expr",
    "Literal",
    "BinaryOp",
    "UnaryOp",
    "Conditional",
    "PropertyAccess",
    "MethodCall",
    "Assignment",
    "all_",
    "any_",
    "match",
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
    "Animation",
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
    "MockInput",
    "MockMouse",
    "AlignItems",
    "BorderStyle",
    "Display",
    "FlexDirection",
    "FlexWrap",
    "JustifyContent",
    "Overflow",
    "Position",
    "TitleAlignment",
    "extend",
    "get_component_catalogue",
]

signals = signals_module
