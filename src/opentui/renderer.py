"""CliRenderer class - wrapper around native OpenTUI renderer using nanobind."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from . import structs as s
from .components.base import BaseRenderable
from .ffi import get_native, is_native_available

if TYPE_CHECKING:
    pass


@dataclass
class CliRendererConfig:
    """Configuration for creating a CLI renderer."""

    width: int = 80
    height: int = 24
    testing: bool = False
    remote: bool = False
    exit_on_ctrl_c: bool = True
    target_fps: int = 60
    console_options: dict | None = None


@dataclass
class TerminalCapabilities:
    """Terminal capabilities."""

    kitty_keyboard: bool = False
    kitty_graphics: bool = False
    rgb: bool = False
    unicode: str = "wcwidth"
    sgr_pixels: bool = False
    color_scheme_updates: bool = False
    explicit_width: bool = False
    scaled_text: bool = False
    sixel: bool = False
    focus_tracking: bool = False
    sync: bool = False
    bracketed_paste: bool = False
    hyperlinks: bool = False
    osc52: bool = False
    explicit_cursor_positioning: bool = False
    term_name: str = ""
    term_version: str = ""


class Buffer:
    """Wrapper around native buffer using nanobind."""

    def __init__(self, ptr: Any, native: Any):
        self._ptr = ptr
        self._native = native
        self._width: int | None = None
        self._height: int | None = None

    @property
    def width(self) -> int:
        if self._width is None:
            self._width = self._native.get_buffer_width(self._ptr)
        return self._width  # type: ignore[return-value]

    @property
    def height(self) -> int:
        if self._height is None:
            self._height = self._native.get_buffer_height(self._ptr)
        return self._height  # type: ignore[return-value]

    def clear(self, bg: s.RGBA | None = None) -> None:
        # Native buffer_clear takes (buffer, alpha) - use alpha from bg or default
        alpha = bg.a if bg else 0.0
        self._native.buffer_clear(self._ptr, alpha)

    def resize(self, width: int, height: int) -> None:
        self._native.buffer_resize(self._ptr, width, height)
        self._width = width
        self._height = height

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        fg: s.RGBA | None = None,
        bg: s.RGBA | None = None,
        attributes: int = 0,
    ) -> None:
        # Native buffer_draw_text takes (buffer, text, x, y) - colors not supported
        # For now, just pass the text and position
        if isinstance(text, str):
            text_bytes = text.encode("utf-8")
        else:
            text_bytes = text
        self._native.buffer_draw_text(self._ptr, text_bytes, len(text_bytes), x, y)

    def fill_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        bg: s.RGBA | None = None,
    ) -> None:
        # Native buffer_fill_rect takes (buffer, x, y, width, height) - bg not supported
        self._native.buffer_fill_rect(self._ptr, x, y, width, height)

    def get_span_lines(self) -> list[dict]:
        """Get span lines for diff testing."""
        w = self.width
        h = self.height

        if w <= 0 or h <= 0:
            return []

        try:
            resolved = self._native.buffer_write_resolved_chars(self._ptr, True)
            real_text = resolved if resolved else ""
        except Exception:
            return []

        lines = real_text.split("\n")
        result = []
        for y in range(h):
            if y < len(lines):
                result.append({"text": lines[y], "width": len(lines[y])})
            else:
                result.append({"text": "", "width": 0})
        return result


class CliRenderer:
    """CLI renderer - wraps the native OpenTUI renderer using nanobind."""

    def __init__(self, ptr: Any, config: CliRendererConfig, native: Any):
        self._ptr = ptr
        self._config = config
        self._native = native
        self._running = False
        self._root: RootRenderable | None = None
        self._event_callbacks: list[Callable] = []
        self._component_fn: Callable | None = None
        self._signal_state: Any = None
        self._last_component: Any = None

        if config.testing:
            self._width = config.width
            self._height = config.height
        else:
            try:
                term_size = shutil.get_terminal_size()
                if term_size.columns > 0 and term_size.lines > 0:
                    self._width = term_size.columns
                    self._height = term_size.lines
                else:
                    self._width = config.width
                    self._height = config.height
            except (AttributeError, OSError):
                self._width = config.width
                self._height = config.height

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def root(self) -> RootRenderable:
        """Get the root renderable."""
        if self._root is None:
            raise RuntimeError("Root not set. Call setup() first.")
        return self._root

    def setup(self) -> None:
        """Set up the terminal."""
        if self._config.testing:
            return
        self._native.renderer.setup_terminal(self._ptr, False)

    def suspend(self) -> None:
        """Suspend the renderer (for Ctrl+Z)."""
        self._native.renderer.suspend_renderer(self._ptr)

    def resume(self) -> None:
        """Resume the renderer."""
        self._native.renderer.resume_renderer(self._ptr)

    def clear(self) -> None:
        """Clear the terminal."""
        self._native.renderer.clear_terminal(self._ptr)

    def set_title(self, title: str) -> None:
        """Set the terminal title."""
        self._native.renderer.set_terminal_title(self._ptr, title)

    def enable_mouse(self, enable_movement: bool = False) -> None:
        """Enable mouse tracking."""
        self._native.renderer.enable_mouse(self._ptr, enable_movement)

    def disable_mouse(self) -> None:
        """Disable mouse tracking."""
        self._native.renderer.disable_mouse(self._ptr)

    def enable_keyboard(self, flags: int = 0) -> None:
        """Enable kitty keyboard protocol."""
        self._native.renderer.enable_kitty_keyboard(self._ptr, flags)

    def disable_keyboard(self) -> None:
        """Disable kitty keyboard protocol."""
        self._native.renderer.disable_kitty_keyboard(self._ptr)

    def get_capabilities(self) -> TerminalCapabilities:
        """Get terminal capabilities."""
        caps_dict = self._native.renderer.get_terminal_capabilities(self._ptr)
        return TerminalCapabilities(
            kitty_keyboard=caps_dict.get("kitty_keyboard", False),
            kitty_graphics=caps_dict.get("kitty_graphics", False),
            rgb=caps_dict.get("rgb", False),
            unicode="unicode" if caps_dict.get("unicode", False) else "wcwidth",
            sgr_pixels=caps_dict.get("sgr_pixels", False),
            color_scheme_updates=caps_dict.get("color_scheme_updates", False),
            explicit_width=caps_dict.get("explicit_width", False),
            scaled_text=caps_dict.get("scaled_text", False),
            sixel=caps_dict.get("sixel", False),
            focus_tracking=caps_dict.get("focus_tracking", False),
            sync=caps_dict.get("sync", False),
            bracketed_paste=caps_dict.get("bracketed_paste", False),
            hyperlinks=caps_dict.get("hyperlinks", False),
            osc52=caps_dict.get("osc52", False),
            explicit_cursor_positioning=caps_dict.get("explicit_cursor_positioning", False),
            term_name="",
            term_version="",
        )

    def get_next_buffer(self) -> Buffer:
        """Get the next buffer."""
        ptr = self._native.renderer.get_next_buffer(self._ptr)
        return Buffer(ptr, self._native.buffer)

    def get_current_buffer(self) -> Buffer:
        """Get the current buffer."""
        ptr = self._native.renderer.get_current_buffer(self._ptr)
        return Buffer(ptr, self._native.buffer)

    def render(self, force: bool = False) -> None:
        """Render the current frame."""
        self._native.renderer.render(self._ptr, force)

    def resize(self, width: int, height: int) -> None:
        """Resize the renderer."""
        self._native.renderer.resize_renderer(self._ptr, width, height)
        self._width = width
        self._height = height

    def request_render(self) -> None:
        """Request a render on the next frame."""
        pass

    def set_event_callback(self, callback: Callable) -> None:
        """Set callback for terminal events."""
        self._event_callbacks.append(callback)

    def run(self) -> None:
        """Run the renderer main loop with event handling."""
        self._running = True
        self.setup()

        from .input import EventLoop

        event_loop = EventLoop(target_fps=self._config.target_fps)
        input_handler = event_loop.input_handler

        for event_type, handlers in self._get_event_forwarding().items():
            if event_type == "key":
                for handler in handlers:
                    input_handler.on_key(handler)

        for handler in hooks.get_keyboard_handlers():
            input_handler.on_key(handler)

        event_loop.on_frame(lambda dt: self._render_frame(dt))

        try:
            event_loop.run()
        except KeyboardInterrupt:
            if self._config.exit_on_ctrl_c:
                pass
            else:
                raise
        finally:
            self._native.renderer.restore_terminal_modes(self._ptr)

    def _render_frame(self, delta_time: float) -> None:
        """Render a single frame."""
        if (
            self._component_fn is not None
            and self._signal_state is not None
            and self._signal_state.has_changes()
        ):
            self._signal_state.reset()
            self._rebuild_component_tree()

        if self._root:
            self._update_layout(self._root, delta_time)

        buffer = self.get_current_buffer()
        buffer.clear()

        if self._root:
            self._root.render(buffer, delta_time)

        self.render()

    def _rebuild_component_tree(self) -> None:
        """Rebuild the component tree from the component function."""
        if self._root is None or self._component_fn is None:
            return

        self._root._children.clear()
        component = self._component_fn()
        self._root.add(component)

    def _update_layout(self, renderable, delta_time: float) -> None:
        """Update layout for a renderable and its children using yoga."""
        if renderable is self._root and self._root and hasattr(self._root, "_build_yoga_tree"):
            root_node = self._root._build_yoga_tree()

            from . import layout as yoga_layout

            yoga_layout.compute_layout(root_node, float(self._width), float(self._height))

            self._apply_yoga_layout_recursive(self._root)

        if hasattr(renderable, "update_layout"):
            renderable.update_layout(delta_time)

        if hasattr(renderable, "get_children"):
            for child in renderable.get_children():
                pass

    def _apply_yoga_layout_recursive(self, renderable) -> None:
        """Apply yoga layout to renderable and all descendants."""
        if hasattr(renderable, "_apply_yoga_layout"):
            renderable._apply_yoga_layout()

        if hasattr(renderable, "get_children"):
            for child in renderable.get_children():
                self._apply_yoga_layout_recursive(child)

    def _get_event_forwarding(self) -> dict:
        """Get event handlers from all renderables."""
        handlers = {"key": [], "mouse": [], "paste": []}

        if self._root:
            self._collect_handlers(self._root, handlers)

        return handlers

    def _collect_handlers(self, renderable, handlers: dict) -> None:
        """Recursively collect event handlers."""
        if hasattr(renderable, "_key_handler"):
            handlers["key"].append(renderable._key_handler)

        if hasattr(renderable, "get_children"):
            for child in renderable.get_children():
                self._collect_handlers(child, handlers)

    def stop(self) -> None:
        """Stop the renderer."""
        self._running = False

    def destroy(self) -> None:
        """Destroy the renderer and free resources."""
        if self._ptr:
            self._native.renderer.destroy_renderer(self._ptr)
            self._ptr = None


class RootRenderable(BaseRenderable):
    """Root renderable - the top-level container."""

    def __init__(self, renderer: CliRenderer):
        super().__init__()
        self._renderer = renderer
        self._width = renderer.width
        self._height = renderer.height

    def _configure_yoga_node(self, node) -> None:
        """Configure root yoga node with renderer's dimensions."""
        node.width = float(self._renderer.width)
        node.height = float(self._renderer.height)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render all children."""
        for child in self._children:
            if hasattr(child, "render"):
                child.render(buffer, delta_time)


async def create_cli_renderer(config: CliRendererConfig | None = None) -> CliRenderer:
    """Create a new CLI renderer using nanobind."""
    if config is None:
        config = CliRendererConfig()

    if not is_native_available():
        raise RuntimeError(
            "OpenTUI native bindings not available. Please ensure nanobind bindings are installed."
        )

    native = get_native()
    if native is None:
        raise RuntimeError("Failed to load native bindings")

    native_renderer = native.renderer.create_renderer(
        config.width,
        config.height,
        config.testing,
        config.remote,
    )

    renderer = CliRenderer(native_renderer, config, native)
    renderer._root = RootRenderable(renderer)

    return renderer


__all__ = [
    "CliRenderer",
    "CliRendererConfig",
    "TerminalCapabilities",
    "Buffer",
    "RootRenderable",
    "create_cli_renderer",
]
