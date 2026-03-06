"""CliRenderer class - wrapper around native OpenTUI renderer."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import ffi
from . import hooks
from . import structs as s
from .components.base import BaseRenderable
from .ffi import POINTER, c_bool, c_float, c_uint8, c_uint32, c_void_p, get_library


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
    """Wrapper around native buffer."""

    def __init__(self, ptr: c_void_p, lib: ffi.OpenTUILibrary):
        self._ptr = ptr
        self._lib = lib

    @property
    def width(self) -> int:
        if hasattr(self._lib, "bufferGetWidth"):
            return self._lib.bufferGetWidth(self._ptr)
        return 80

    @property
    def height(self) -> int:
        if hasattr(self._lib, "bufferGetHeight"):
            return self._lib.bufferGetHeight(self._ptr)
        return 24

    def clear(self, bg: s.RGBA | None = None) -> None:
        if bg is None:
            bg = s.RGBA(0, 0, 0, 1)
        bg_array = (c_float * 4)(bg.r, bg.g, bg.b, bg.a)
        self._lib.bufferClear(self._ptr, bg_array)

    def resize(self, width: int, height: int) -> None:
        self._lib.bufferResize(self._ptr, c_uint32(width), c_uint32(height))

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        fg: s.RGBA | None = None,
        bg: s.RGBA | None = None,
        attributes: int = 0,
    ) -> None:
        """Draw text at position."""
        text_bytes = text.encode("utf-8")

        fg_array = None
        if fg:
            fg_array = (c_float * 4)(fg.r, fg.g, fg.b, fg.a)

        bg_array = None
        if bg:
            bg_array = (c_float * 4)(bg.r, bg.g, bg.b, bg.a)

        self._lib.bufferDrawText(
            self._ptr,
            text_bytes,
            len(text_bytes),
            c_uint32(x),
            c_uint32(y),
            fg_array,
            bg_array,
            c_uint32(attributes),
        )

    def fill_rect(self, x: int, y: int, width: int, height: int, bg: s.RGBA | None = None) -> None:
        """Fill a rectangle with background color."""
        if bg is None:
            bg = s.RGBA(0, 0, 0, 1)
        bg_array = (c_float * 4)(bg.r, bg.g, bg.b, bg.a)
        self._lib.bufferFillRect(
            self._ptr, c_uint32(x), c_uint32(y), c_uint32(width), c_uint32(height), bg_array
        )

    def get_span_lines(self) -> list[dict]:
        """Get span lines for diff testing.

        Returns a list of lines, where each line is a dict with 'spans'.
        Each span has: text, fg (rgba), bg (rgba), attributes, width.
        """
        import ctypes

        if not hasattr(self._lib, "bufferWriteResolvedChars"):
            return []

        try:
            w = self._lib.getBufferWidth(self._ptr) if hasattr(self._lib, "getBufferWidth") else 0
            h = self._lib.getBufferHeight(self._ptr) if hasattr(self._lib, "getBufferHeight") else 0
        except Exception:
            return []

        if w <= 0 or h <= 0:
            return []

        try:
            real_size = self._lib.bufferGetRealCharSize(self._ptr)
            if real_size <= 0:
                return []
            output_buffer = ctypes.create_string_buffer(real_size)
            bytes_written = self._lib.bufferWriteResolvedChars(
                self._ptr, ctypes.byref(output_buffer), ctypes.c_bool(True)
            )
            if bytes_written <= 0:
                return []
            real_text = output_buffer.raw[:bytes_written].decode("utf-8", errors="replace")
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
    """CLI renderer - wraps the native OpenTUI renderer."""

    def __init__(self, ptr: c_void_p, config: CliRendererConfig):
        self._ptr = ptr
        self._config = config
        self._lib = get_library()
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
        self._lib.setupTerminal(self._ptr, c_bool(True))

    def suspend(self) -> None:
        """Suspend the renderer (for Ctrl+Z)."""
        self._lib.suspendRenderer(self._ptr)

    def resume(self) -> None:
        """Resume the renderer."""
        self._lib.resumeRenderer(self._ptr)

    def clear(self) -> None:
        """Clear the terminal."""
        self._lib.clearTerminal(self._ptr)

    def set_title(self, title: str) -> None:
        """Set the terminal title."""
        title_bytes = title.encode("utf-8")
        self._lib.setTerminalTitle(self._ptr, title_bytes, len(title_bytes))

    def enable_mouse(self, enable_movement: bool = False) -> None:
        """Enable mouse tracking."""
        self._lib.enableMouse(self._ptr, c_bool(enable_movement))

    def disable_mouse(self) -> None:
        """Disable mouse tracking."""
        self._lib.disableMouse(self._ptr)

    def enable_keyboard(self, flags: int = 0) -> None:
        """Enable kitty keyboard protocol."""
        self._lib.enableKittyKeyboard(self._ptr, c_uint8(flags))

    def disable_keyboard(self) -> None:
        """Disable kitty keyboard protocol."""
        self._lib.disableKittyKeyboard(self._ptr)

    def get_capabilities(self) -> TerminalCapabilities:
        """Get terminal capabilities."""
        caps = s.ExternalCapabilities()
        self._lib.getTerminalCapabilities(self._ptr, POINTER(s.ExternalCapabilities)(caps))

        return TerminalCapabilities(
            kitty_keyboard=caps.kitty_keyboard,
            kitty_graphics=caps.kitty_graphics,
            rgb=caps.rgb,
            unicode="unicode" if caps.unicode else "wcwidth",
            sgr_pixels=caps.sgr_pixels,
            color_scheme_updates=caps.color_scheme_updates,
            explicit_width=caps.explicit_width,
            scaled_text=caps.scaled_text,
            sixel=caps.sixel,
            focus_tracking=caps.focus_tracking,
            sync=caps.sync,
            bracketed_paste=caps.bracketed_paste,
            hyperlinks=caps.hyperlinks,
            osc52=caps.osc52,
            explicit_cursor_positioning=caps.explicit_cursor_positioning,
            term_name=caps.term_name.decode() if caps.term_name else "",
            term_version=caps.term_version.decode() if caps.term_version else "",
        )

    def get_next_buffer(self) -> Buffer:
        """Get the next buffer for rendering."""
        ptr = self._lib.getNextBuffer(self._ptr)
        return Buffer(ptr, self._lib)

    def get_current_buffer(self) -> Buffer:
        """Get the current buffer."""
        ptr = self._lib.getCurrentBuffer(self._ptr)
        return Buffer(ptr, self._lib)

    def render(self, force: bool = False) -> None:
        """Render the current frame."""
        self._lib.render(self._ptr, c_bool(force))

    def resize(self, width: int, height: int) -> None:
        """Resize the renderer."""
        self._lib.resizeRenderer(self._ptr, c_uint32(width), c_uint32(height))
        self._width = width
        self._height = height

    def request_render(self) -> None:
        """Request a render on the next frame."""
        # This would typically set a flag that the render loop checks
        pass

    def set_event_callback(self, callback: Callable) -> None:
        """Set callback for terminal events."""
        self._event_callbacks.append(callback)

    def run(self) -> None:
        """Run the renderer main loop with event handling."""
        self._running = True
        self.setup()

        # Import here to avoid circular imports
        from .input import EventLoop

        # Create event loop
        event_loop = EventLoop(target_fps=self._config.target_fps)

        # Set up input handler with key handlers
        input_handler = event_loop.input_handler

        # Forward events to component handlers
        for event_type, handlers in self._get_event_forwarding().items():
            if event_type == "key":
                for handler in handlers:
                    input_handler.on_key(handler)

        # Register global keyboard handlers from hooks
        for handler in hooks.get_keyboard_handlers():
            input_handler.on_key(handler)

        # Set up render callback
        event_loop.on_frame(lambda dt: self._render_frame(dt))

        try:
            event_loop.run()
        except KeyboardInterrupt:
            if self._config.exit_on_ctrl_c:
                pass  # Exit cleanly
            else:
                raise
        finally:
            # Restore terminal
            if hasattr(self._lib, "restoreTerminalModes"):
                self._lib.restoreTerminalModes(self._ptr)

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
        # Only build and compute layout once at the top level
        if renderable is self._root and self._root and hasattr(self._root, "_build_yoga_tree"):
            root_node = self._root._build_yoga_tree()

            from . import layout as yoga_layout

            yoga_layout.compute_layout(root_node, float(self._width), float(self._height))

            self._apply_yoga_layout_recursive(self._root)

        # For children, just call update_layout (which does nothing currently)
        if hasattr(renderable, "update_layout"):
            renderable.update_layout(delta_time)

        if hasattr(renderable, "get_children"):
            for child in renderable.get_children():
                # Don't recursively call _update_layout - we've already handled the whole tree
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
        # Collect key handlers from Input components
        handlers = {"key": [], "mouse": [], "paste": []}

        if self._root:
            self._collect_handlers(self._root, handlers)

        return handlers

    def _collect_handlers(self, renderable, handlers: dict) -> None:
        """Recursively collect event handlers."""
        # Check for input-focused renderables
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
            self._lib.destroyRenderer(self._ptr)
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
    """Create a new CLI renderer."""
    if config is None:
        config = CliRendererConfig()

    lib = get_library()

    ptr = lib.createRenderer(
        c_uint32(config.width),
        c_uint32(config.height),
        c_bool(config.testing),
        c_bool(config.remote),
    )

    if not ptr:
        raise RuntimeError("Failed to create renderer")

    renderer = CliRenderer(ptr, config)
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
