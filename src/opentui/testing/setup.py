"""TestSetup class and factory functions for OpenTUI test infrastructure."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import hooks
from ..hooks import (
    clear_keyboard_handlers,
    clear_mouse_handlers,
    clear_paste_handlers,
    clear_resize_handlers,
    clear_selection_handlers,
)
from ..renderer import Buffer, CliRenderer, CliRendererConfig, create_cli_renderer
from .input import MockInput, MockMouse


async def test_render(
    component_fn: Callable,
    options: dict | None = None,
) -> TestSetup:
    """Args:
        component_fn: A callable that returns a component tree
        options: Test options like {"width": 80, "height": 24}

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

    from ..signals import _signal_state

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
    """Unlike ``test_render()``, this does not create a component tree.
    Callers add renderables directly to ``setup.renderer.root``.

    Args:
        width: Terminal width
        height: Terminal height
        use_mouse: If True/False, explicitly set mouse tracking state.
        auto_focus: If False, disable click-to-focus behaviour.

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

    from ..hooks import set_renderer

    set_renderer(renderer)
    clear_keyboard_handlers()
    clear_mouse_handlers()
    clear_paste_handlers()
    clear_resize_handlers()
    clear_selection_handlers()

    from ..signals import _signal_state

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
            from .input import MockInput

            self._mock_input = MockInput(self)
        return self._mock_input

    @property
    def mock_mouse(self) -> MockMouse:
        """Lazy-created MockMouse instance (high-level, bypasses input parser)."""
        if self._mock_mouse is None:
            from .input import MockMouse

            self._mock_mouse = MockMouse(self)
        return self._mock_mouse

    def _ensure_stdin_input(self) -> None:
        """Lazily create the stdin-level TestInputHandler and wire up
        the same event handlers that ``CliRenderer.run()`` would register."""
        if self._test_input_handler is not None:
            return

        from ..input.event_loop import TestInputHandler
        from .sgr import _TestStdinBridge

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
            from .input import MockKeys

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
            from .sgr import SGRMockMouse

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
        from .capture import capture_spans as _capture_spans

        return _capture_spans(self._renderer)

    def destroy(self) -> None:
        self._renderer.destroy()
        if self._test_input_handler is not None:
            self._test_input_handler.destroy()
            self._test_input_handler = None
