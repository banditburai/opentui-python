"""OpenTUI Python - Build terminal UIs with signals.

OpenTUI Python provides a Pythonic API for building terminal user interfaces,
aligned with StarHTML patterns but working directly with Python signals.

Example:
    from opentui import render, Box, Text, Signal

    def App():
        count = Signal("count", 0)

        return Box(
            padding=2,
            children=[
                Text(f"Count: {count()}"),
            ]
        )

    await render(App)
"""

from __future__ import annotations

from collections.abc import Callable

# Re-export for convenience
from . import signals as signals_module

# Components
from .components import (
    AsciiFont,
    BaseRenderable,
    Bold,
    Box,
    Code,
    Diff,
    Input,
    Italic,
    LineBreak,
    LineNumber,
    Link,
    Markdown,
    Renderable,
    ScrollBox,
    Select,
    SelectOption,
    Slider,
    Span,
    TabSelect,
    Text,
    Textarea,
    TextModifier,
    TextTable,
    Underline,
)

# Events
from .events import (
    FocusEvent,
    KeyEvent,
    Keys,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
)

# Hooks
from .hooks import (
    Timeline,
    use_keyboard,
    use_on_resize,
    use_paste,
    use_renderer,
    use_selection_handler,
    use_terminal_dimensions,
    use_timeline,
)

# Core exports
from .renderer import (
    Buffer,
    CliRenderer,
    CliRendererConfig,
    RootRenderable,
    TerminalCapabilities,
    create_cli_renderer,
)

# Edit buffer
from .edit_buffer import (
    EditBuffer,
    EditorView,
    create_edit_buffer,
)

# Signals (StarHTML-aligned)
from .signals import (
    Assignment,
    BinaryOp,
    Conditional,
    Effect,
    Expr,
    Literal,
    MethodCall,
    PropertyAccess,
    Signal,
    UnaryOp,
    all_,
    any_,
    computed,
    effect,
    match,
)

# Component catalogue for extensibility
_component_catalogue: dict[str, type] = {
    "box": Box,
    "scrollbox": ScrollBox,
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
    """Get the current component catalogue."""
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
        def App():
            return Box(
                padding=1,
                children=[
                    Text("Hello, World!"),
                ]
            )

        await render(App)
    """
    if config is None:
        config = CliRendererConfig()
    elif isinstance(config, dict):
        config = CliRendererConfig(**config)

    renderer = await create_cli_renderer(config)

    from .hooks import set_renderer

    set_renderer(renderer)

    from .signals import _SignalState

    signal_state = _SignalState.get_instance()
    signal_state.reset()

    component = component_fn()
    renderer.root.add(component)

    renderer._component_fn = component_fn
    renderer._signal_state = signal_state

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
        setup = await testRender(MyComponent, {"width": 40, "height": 10})
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

    renderer = await create_cli_renderer(config)
    renderer.setup()

    from .hooks import set_renderer

    set_renderer(renderer)

    from .signals import _SignalState

    signal_state = _SignalState.get_instance()
    signal_state.reset()

    component = component_fn()
    renderer.root.add(component)

    renderer._component_fn = component_fn
    renderer._signal_state = signal_state

    return TestSetup(renderer)


class TestSetup:
    """Test setup for testing components."""

    def __init__(self, renderer: CliRenderer):
        self._renderer = renderer

    @property
    def renderer(self) -> CliRenderer:
        return self._renderer

    def get_buffer(self) -> Buffer:
        """Get the current buffer for inspection."""
        return self._renderer.get_current_buffer()

    def render_frame(self) -> None:
        """Render a single frame."""
        self._renderer.render(force=True)

    def destroy(self) -> None:
        """Clean up the test."""
        self._renderer.destroy()


__all__ = [
    # Core
    "render",
    "test_render",
    "TestSetup",
    # Renderer
    "CliRenderer",
    "CliRendererConfig",
    "TerminalCapabilities",
    "Buffer",
    "RootRenderable",
    "create_cli_renderer",
    # EditBuffer
    "EditBuffer",
    "EditorView",
    "create_edit_buffer",
    # Components
    "BaseRenderable",
    "Renderable",
    "Box",
    "ScrollBox",
    "Text",
    "TextModifier",
    "Span",
    "Bold",
    "Italic",
    "Underline",
    "LineBreak",
    "Link",
    "Input",
    "Textarea",
    "Select",
    "SelectOption",
    # Signals
    "Signal",
    "computed",
    "effect",
    "Effect",
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
    "signals",  # Module access
    "Signals",  # Alias for module
    # Events
    "KeyEvent",
    "MouseEvent",
    "PasteEvent",
    "FocusEvent",
    "ResizeEvent",
    "Keys",
    # Hooks
    "use_renderer",
    "use_terminal_dimensions",
    "use_on_resize",
    "use_keyboard",
    "use_paste",
    "use_selection_handler",
    "use_timeline",
    "Timeline",
    # Extension
    "extend",
    "get_component_catalogue",
]

# Alias for module access
Signals = signals_module
