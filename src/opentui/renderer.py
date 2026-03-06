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

    def __init__(self, ptr: int, lib: ffi.OpenTUILibrary, native_buffer: Any = None):
        self._ptr = ptr
        self._lib = lib
        self._native = native_buffer  # Nanobind buffer (if available)

    @property
    def width(self) -> int:
        if self._native:
            return self._native.get_buffer_width(self._ptr)
        if hasattr(self._lib, "get_buffer_width"):
            return self._lib.get_buffer_width(self._ptr)
        return 80

    @property
    def height(self) -> int:
        if self._native:
            return self._native.get_buffer_height(self._ptr)
        if hasattr(self._lib, "get_buffer_height"):
            return self._lib.get_buffer_height(self._ptr)
        return 24

    def clear(self, bg: s.RGBA | None = None) -> None:
        """Clear buffer using nanobind or ctypes."""
        if self._native:
            self._native.buffer_clear(self._ptr)
        else:
            if bg is None:
                bg = s.RGBA(0, 0, 0, 1)
            bg_tuple = (bg.r, bg.g, bg.b, bg.a)
            buffer_ptr = int(self._ptr) if hasattr(self._ptr, "__int__") else self._ptr
            self._lib.buffer_clear(buffer_ptr, bg_tuple)

    def resize(self, width: int, height: int) -> None:
        if self._native:
            self._native.buffer_resize(self._ptr, width, height)
        else:
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
        """Draw text at position using nanobind or ctypes."""
        if isinstance(text, str):
            text_bytes = text.encode("utf-8")
        else:
            text_bytes = text

        if self._native:
            self._native.buffer_draw_text(self._ptr, text_bytes, len(text_bytes), x, y)
        else:
            fg_tuple = None
            if fg:
                fg_tuple = (fg.r, fg.g, fg.b, fg.a)

            bg_tuple = None
            if bg:
                bg_tuple = (bg.r, bg.g, bg.b, bg.a)

            buffer_ptr = int(self._ptr) if hasattr(self._ptr, "__int__") else self._ptr
            self._lib.buffer_draw_text(
                buffer_ptr,
                text,
                x,
                y,
                fg_tuple,
                bg_tuple,
                attributes,
            )

    def fill_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        bg: s.RGBA | None = None,
    ) -> None:
        """Fill rectangle using nanobind or ctypes."""
        if self._native:
            self._native.buffer_fill_rect(self._ptr, x, y, width, height)
        else:
            if bg is None:
                bg = s.RGBA(0, 0, 0, 1)
            bg_tuple = (bg.r, bg.g, bg.b, bg.a)

            buffer_ptr = int(self._ptr) if hasattr(self._ptr, "__int__") else self._ptr
            self._lib.buffer_fill_rect(buffer_ptr, x, y, width, height, char=0x20, bg=bg_tuple)

    def get_span_lines(self) -> list[dict]:
        """Get span lines for diff testing.

        Returns a list of lines, where each line is a dict with 'spans'.
        Each span has: text, fg (rgba), bg (rgba), attributes, width.
        """
        import ctypes

        # Try nanobind first, fall back to ctypes
        if self._native:
            try:
                w = self._native.get_buffer_width(self._ptr)
                h = self._native.get_buffer_height(self._ptr)
            except Exception:
                return []
        else:
            if not hasattr(self._lib, "bufferWriteResolvedChars"):
                return []

            try:
                w = (
                    self._lib.getBufferWidth(self._ptr)
                    if hasattr(self._lib, "getBufferWidth")
                    else 0
                )
                h = (
                    self._lib.getBufferHeight(self._ptr)
                    if hasattr(self._lib, "getBufferHeight")
                    else 0
                )
            except Exception:
                return []

        if w <= 0 or h <= 0:
            return []

        try:
            if self._native:
                # For nanobind, use buffer_write_resolved_chars - it returns a string
                resolved = self._native.buffer_write_resolved_chars(self._ptr, True)
                real_text = resolved if resolved else ""
            else:
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
        self._native: Any = None  # Native nanobind renderer if available

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
        # In testing mode, skip terminal setup to avoid I/O issues
        if self._config.testing:
            return

        if self._native:
            self._native.renderer.setup_terminal(self._ptr, False)
        else:
            self._lib.setupTerminal(self._ptr, c_bool(False))

    def suspend(self) -> None:
        """Suspend the renderer (for Ctrl+Z)."""
        if self._native:
            self._native.renderer.suspend_renderer(self._ptr)
        else:
            self._lib.suspendRenderer(self._ptr)

    def resume(self) -> None:
        """Resume the renderer."""
        if self._native:
            self._native.renderer.resume_renderer(self._ptr)
        else:
            self._lib.resumeRenderer(self._ptr)

    def clear(self) -> None:
        """Clear the terminal."""
        if self._native:
            self._native.renderer.clear_terminal(self._ptr)
        else:
            self._lib.clearTerminal(self._ptr)

    def set_title(self, title: str) -> None:
        """Set the terminal title."""
        if self._native:
            self._native.renderer.set_terminal_title(self._ptr, title)
        else:
            title_bytes = title.encode("utf-8")
            self._lib.setTerminalTitle(self._ptr, title_bytes, len(title_bytes))

    def enable_mouse(self, enable_movement: bool = False) -> None:
        """Enable mouse tracking."""
        if self._native:
            self._native.renderer.enable_mouse(self._ptr, enable_movement)
        else:
            self._lib.enableMouse(self._ptr, c_bool(enable_movement))

    def disable_mouse(self) -> None:
        """Disable mouse tracking."""
        if self._native:
            self._native.renderer.disable_mouse(self._ptr)
        else:
            self._lib.disableMouse(self._ptr)

    def enable_keyboard(self, flags: int = 0) -> None:
        """Enable kitty keyboard protocol."""
        if self._native:
            self._native.renderer.enable_kitty_keyboard(self._ptr, flags)
        else:
            self._lib.enableKittyKeyboard(self._ptr, c_uint8(flags))

    def disable_keyboard(self) -> None:
        """Disable kitty keyboard protocol."""
        if self._native:
            self._native.renderer.disable_kitty_keyboard(self._ptr)
        else:
            self._lib.disableKittyKeyboard(self._ptr)

    def get_capabilities(self) -> TerminalCapabilities:
        """Get terminal capabilities."""
        # Try nanobind first
        if self._native and hasattr(self._native.renderer, "get_terminal_capabilities"):
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

        # Fall back to ctypes
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
        """Get the next buffer."""
        # Get buffer pointer via nanobind or ctypes
        if self._native:
            # self._native is the full nb module (has .renderer and .buffer)
            # Don't convert to int - nanobind expects the capsule
            ptr = self._native.renderer.get_next_buffer(self._ptr)
            return Buffer(ptr, self._lib, self._native.buffer)
        else:
            ptr = int(self._lib.getNextBuffer(self._ptr))
            return Buffer(ptr, self._lib, None)

    def get_current_buffer(self) -> Buffer:
        """Get the current buffer."""
        if self._native:
            # Don't convert to int - nanobind expects the capsule
            ptr = self._native.renderer.get_current_buffer(self._ptr)
            return Buffer(ptr, self._lib, self._native.buffer)
        else:
            ptr = int(self._lib.getCurrentBuffer(self._ptr))
            return Buffer(ptr, self._lib, None)

    def render(self, force: bool = False) -> None:
        """Render the current frame."""
        if self._native:
            self._native.renderer.render(self._ptr, force)
        else:
            self._lib.render(self._ptr, c_bool(force))

    def resize(self, width: int, height: int) -> None:
        """Resize the renderer."""
        if self._native:
            self._native.renderer.resize_renderer(self._ptr, width, height)
        else:
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
            if self._native:
                self._native.renderer.restore_terminal_modes(self._ptr)
            elif hasattr(self._lib, "restoreTerminalModes"):
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
            if self._native:
                self._native.renderer.destroy_renderer(self._ptr)
            else:
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

    # Try to use nanobind for renderer operations
    from opentui import ffi as ffi_module

    native_module = None  # Full nanobind module (includes renderer and buffer)
    native_renderer = None  # Nanobind-created renderer capsule

    if ffi_module.is_native_available():
        try:
            nb = ffi_module.get_native()
            if nb and hasattr(nb, "renderer"):
                # Use nanobind directly for renderer operations
                native_renderer = nb.renderer.create_renderer(
                    config.width,
                    config.height,
                    config.testing,
                    config.remote,
                )
                native_module = nb  # Store full module for buffer access
                print("Using nanobind bindings for renderer")
        except Exception as e:
            print(f"Nanobind renderer failed: {e}, falling back to ctypes")
            native_renderer = None

    # Use nanobind renderer if available, otherwise create with ctypes
    if native_renderer is not None:
        ptr = native_renderer
    else:
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
    # Store native module for buffer operations (nb.buffer) and renderer for renderer ops (nb.renderer)
    renderer._native = native_module

    return renderer


__all__ = [
    "CliRenderer",
    "CliRendererConfig",
    "TerminalCapabilities",
    "Buffer",
    "RootRenderable",
    "create_cli_renderer",
]
