"""CliRenderer class - wrapper around native OpenTUI renderer using nanobind."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

_log = logging.getLogger(__name__)

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
        self._scissor_stack: list[tuple[int, int, int, int]] = []
        self._opacity_stack: list[float] = []

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
        # Native buffer_clear takes (buffer, alpha)
        alpha = bg.a if bg else 0.0
        self._native.buffer_clear(self._ptr, alpha)

    def resize(self, width: int, height: int) -> None:
        self._native.buffer_resize(self._ptr, width, height)
        self._width = width
        self._height = height

    def _apply_opacity_to_color(self, color: s.RGBA | None) -> s.RGBA | None:
        """Apply current opacity stack to a color's alpha channel."""
        if color is None or not self._opacity_stack:
            return color
        opacity = self.get_current_opacity()
        if opacity >= 1.0:
            return color
        return s.RGBA(color.r, color.g, color.b, color.a * opacity)

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        fg: s.RGBA | None = None,
        bg: s.RGBA | None = None,
        attributes: int = 0,
    ) -> None:
        # Scissor clipping: skip if entirely outside clip rect
        if self._scissor_stack:
            sx, sy, sw, sh = self._scissor_stack[-1]
            if sw <= 0 or sh <= 0:
                return
            if y < sy or y >= sy + sh:
                return
            # Clip text horizontally
            text_len = len(text)
            if x + text_len <= sx or x >= sx + sw:
                return
            # Trim characters outside scissor rect
            if x < sx:
                trim = sx - x
                text = text[trim:]
                x = sx
            end = sx + sw
            if x + len(text) > end:
                text = text[: end - x]
            if not text:
                return

        # Apply opacity
        fg = self._apply_opacity_to_color(fg)
        bg = self._apply_opacity_to_color(bg)

        if isinstance(text, str):
            text_bytes = text.encode("utf-8")
        else:
            text_bytes = text

        fg_tuple = (fg.r, fg.g, fg.b, fg.a) if fg else None
        bg_tuple = (bg.r, bg.g, bg.b, bg.a) if bg else None

        self._native.buffer_draw_text(
            self._ptr, text_bytes, len(text_bytes), x, y, fg_tuple, bg_tuple, attributes
        )

    def fill_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        bg: s.RGBA | None = None,
    ) -> None:
        # Scissor clipping: intersect fill rect with scissor rect
        if self._scissor_stack:
            sx, sy, sw, sh = self._scissor_stack[-1]
            if sw <= 0 or sh <= 0:
                return
            nx = max(x, sx)
            ny = max(y, sy)
            nw = min(x + width, sx + sw) - nx
            nh = min(y + height, sy + sh) - ny
            if nw <= 0 or nh <= 0:
                return
            x, y, width, height = nx, ny, nw, nh

        # Apply opacity
        bg = self._apply_opacity_to_color(bg)

        bg_tuple = (bg.r, bg.g, bg.b, bg.a) if bg else None
        self._native.buffer_fill_rect(self._ptr, x, y, width, height, bg_tuple)

    def get_plain_text(self) -> str:
        """Get buffer contents as plain text string."""
        try:
            resolved = self._native.buffer_write_resolved_chars(self._ptr, True)
            return resolved if resolved else ""
        except Exception:
            return ""

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

    # Scissor rect stack
    def push_scissor_rect(self, x: int, y: int, width: int, height: int) -> None:
        """Push a scissor rectangle. Drawing is clipped to the intersection of all active rects."""
        if self._scissor_stack:
            # Intersect with current scissor
            cx, cy, cw, ch = self._scissor_stack[-1]
            nx = max(x, cx)
            ny = max(y, cy)
            nw = min(x + width, cx + cw) - nx
            nh = min(y + height, cy + ch) - ny
            self._scissor_stack.append((nx, ny, max(0, nw), max(0, nh)))
        else:
            self._scissor_stack.append((x, y, width, height))

    def pop_scissor_rect(self) -> None:
        """Pop the most recent scissor rectangle."""
        if self._scissor_stack:
            self._scissor_stack.pop()

    def get_scissor_rect(self) -> tuple[int, int, int, int] | None:
        """Get the current scissor rectangle, or None if no clipping."""
        return self._scissor_stack[-1] if self._scissor_stack else None

    def _clip_coords(self, x: int, y: int) -> bool:
        """Check if coordinates are within the current scissor rect."""
        if not self._scissor_stack:
            return True
        sx, sy, sw, sh = self._scissor_stack[-1]
        return sx <= x < sx + sw and sy <= y < sy + sh

    # Opacity stack
    def push_opacity(self, opacity: float) -> None:
        """Push an opacity value. Combined multiplicatively with the stack."""
        self._opacity_stack.append(opacity)

    def pop_opacity(self) -> None:
        """Pop the most recent opacity value."""
        if self._opacity_stack:
            self._opacity_stack.pop()

    def get_current_opacity(self) -> float:
        """Get the current combined opacity (product of all values in the stack)."""
        if not self._opacity_stack:
            return 1.0
        result = 1.0
        for o in self._opacity_stack:
            result *= o
        return result

    # Additional drawing methods
    def draw_rectangle(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        border_style: str = "single",
        border_color: s.RGBA | None = None,
        bg: s.RGBA | None = None,
    ) -> None:
        """Draw a rectangle outline (no fill)."""
        if width < 2 or height < 2:
            return

        chars = _get_border_chars(border_style)
        tl, tr, bl, br, h_char, v_char = chars

        # Top edge
        self.draw_text(tl, x, y, fg=border_color, bg=bg)
        for i in range(1, width - 1):
            self.draw_text(h_char, x + i, y, fg=border_color, bg=bg)
        self.draw_text(tr, x + width - 1, y, fg=border_color, bg=bg)

        # Sides
        for row in range(1, height - 1):
            self.draw_text(v_char, x, y + row, fg=border_color, bg=bg)
            self.draw_text(v_char, x + width - 1, y + row, fg=border_color, bg=bg)

        # Bottom edge
        self.draw_text(bl, x, y + height - 1, fg=border_color, bg=bg)
        for i in range(1, width - 1):
            self.draw_text(h_char, x + i, y + height - 1, fg=border_color, bg=bg)
        self.draw_text(br, x + width - 1, y + height - 1, fg=border_color, bg=bg)

    def draw_box(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        border_style: str = "single",
        border_color: s.RGBA | None = None,
        bg: s.RGBA | None = None,
        title: str | None = None,
        title_alignment: str = "left",
    ) -> None:
        """Draw a full box with border, fill, and optional title."""
        if width < 2 or height < 2:
            return

        # Fill interior
        if bg:
            self.fill_rect(x + 1, y + 1, width - 2, height - 2, bg=bg)

        # Draw border
        self.draw_rectangle(x, y, width, height, border_style, border_color, bg)

        # Draw title
        if title and width > 4:
            max_title_len = width - 4
            display_title = title[:max_title_len]
            title_text = f" {display_title} "

            if title_alignment == "center":
                tx = x + (width - len(title_text)) // 2
            elif title_alignment == "right":
                tx = x + width - len(title_text) - 1
            else:
                tx = x + 1

            self.draw_text(title_text, tx, y, fg=border_color, bg=bg)


def _get_border_chars(style: str) -> tuple[str, str, str, str, str, str]:
    """Get border characters for a style. Returns (tl, tr, bl, br, horizontal, vertical)."""
    borders = {
        "single": ("┌", "┐", "└", "┘", "─", "│"),
        "double": ("╔", "╗", "╚", "╝", "═", "║"),
        "round": ("╭", "╮", "╰", "╯", "─", "│"),
        "bold": ("┏", "┓", "┗", "┛", "━", "┃"),
        "block": ("█", "█", "█", "█", "█", "█"),
    }
    return borders.get(style, borders["single"])


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
        # Handler cache
        self._handlers_dirty = True
        self._cached_handlers: dict[str, list[Callable]] = {"key": [], "mouse": [], "paste": []}
        # Post-processing and frame callbacks
        self._post_process_fns: list[Callable] = []
        self._frame_callbacks: list[Callable] = []
        self._animation_frame_callbacks: dict[int, Callable] = {}
        self._next_animation_id: int = 0
        self._event_loop: Any = None

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

    def set_cursor_position(self, x: int, y: int, visible: bool = True) -> None:
        """Set the cursor position and visibility."""
        self._native.renderer.set_cursor_position(self._ptr, x, y, visible)

    def get_cursor_state(self) -> dict:
        """Get the current cursor state (position, visibility)."""
        return self._native.renderer.get_cursor_state(self._ptr)

    def copy_to_clipboard(self, clipboard_type: int, text: str) -> bool:
        """Copy text to clipboard via OSC 52."""
        return self._native.renderer.copy_to_clipboard_osc52(self._ptr, clipboard_type, text)

    def clear_clipboard(self, clipboard_type: int) -> bool:
        """Clear clipboard via OSC 52."""
        return self._native.renderer.clear_clipboard_osc52(self._ptr, clipboard_type)

    def set_debug_overlay(self, enable: bool, flags: int = 0) -> None:
        """Enable or disable the debug overlay."""
        self._native.renderer.set_debug_overlay(self._ptr, enable, flags)

    def update_stats(self, fps: float, frame_count: int, avg_frame_time: float) -> None:
        """Update renderer statistics."""
        self._native.renderer.update_stats(self._ptr, fps, frame_count, avg_frame_time)

    def write_out(self, data: bytes) -> None:
        """Write raw bytes to the output."""
        self._native.renderer.write_out(self._ptr, data)

    def set_kitty_keyboard_flags(self, flags: int) -> None:
        """Set kitty keyboard protocol flags."""
        self._native.renderer.set_kitty_keyboard_flags(self._ptr, flags)

    def get_kitty_keyboard_flags(self) -> int:
        """Get current kitty keyboard protocol flags."""
        return self._native.renderer.get_kitty_keyboard_flags(self._ptr)

    def set_background_color(self) -> None:
        """Set the terminal background color from detected theme."""
        self._native.renderer.set_background_color(self._ptr)

    def set_render_offset(self, offset: int) -> None:
        """Set the render offset for scrolling."""
        self._native.renderer.set_render_offset(self._ptr, offset)

    def query_pixel_resolution(self) -> None:
        """Query the terminal's pixel resolution."""
        self._native.renderer.query_pixel_resolution(self._ptr)

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

        # Drain terminal capability responses from stdin so they don't
        # get misinterpreted as user input by the InputHandler.
        import os as _os
        import select as _sel
        import sys as _sys
        import time as _time

        _time.sleep(0.05)  # Give terminal time to send responses
        fd = _sys.stdin.fileno()
        while _sel.select([fd], [], [], 0)[0]:
            _os.read(fd, 4096)

        from .input import EventLoop

        event_loop = EventLoop(target_fps=self._config.target_fps)
        self._event_loop = event_loop
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
        # Run frame callbacks before render
        for cb in self._frame_callbacks:
            cb(delta_time)

        # Run one-shot animation frame callbacks
        if self._animation_frame_callbacks:
            pending = dict(self._animation_frame_callbacks)
            self._animation_frame_callbacks.clear()
            for cb in pending.values():
                cb(delta_time)

        if (
            self._component_fn is not None
            and self._signal_state is not None
            and self._signal_state.has_changes()
        ):
            self._signal_state.reset()
            self._rebuild_component_tree()

        if self._root:
            try:
                self._update_layout(self._root, delta_time)
            except Exception:
                _log.exception("Error updating layout")

        buffer = self.get_next_buffer()
        buffer.clear()

        if self._root:
            try:
                self._root.render(buffer, delta_time)
            except Exception:
                _log.exception("Error rendering root")

        # Run post-processing functions after render
        for fn in self._post_process_fns:
            fn(buffer)

        self.render()

    def _rebuild_component_tree(self) -> None:
        """Rebuild the component tree from the component function."""
        if self._root is None or self._component_fn is None:
            return

        from .reconciler import reconcile

        old_children = list(self._root._children)
        try:
            component = self._component_fn()
            new_children = [component]
            self._root._children.clear()
            reconcile(self._root, old_children, new_children)
        except Exception:
            _log.exception("Error rebuilding component tree, restoring previous")
            self._root._children = old_children
            for child in old_children:
                child._parent = self._root

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

    def _apply_yoga_layout_recursive(self, renderable, offset_x: int = 0, offset_y: int = 0) -> None:
        """Apply yoga layout to renderable and all descendants.

        Yoga computes positions relative to the parent. This method converts
        them to absolute screen coordinates by accumulating parent offsets.
        """
        if hasattr(renderable, "_apply_yoga_layout"):
            renderable._apply_yoga_layout()
            # Convert relative yoga position to absolute screen coordinates
            renderable._x += offset_x
            renderable._y += offset_y

        # Children's positions will be relative to this renderable's absolute position
        abs_x = getattr(renderable, "_x", offset_x)
        abs_y = getattr(renderable, "_y", offset_y)

        if hasattr(renderable, "get_children"):
            for child in renderable.get_children():
                self._apply_yoga_layout_recursive(child, abs_x, abs_y)

    def invalidate_handler_cache(self) -> None:
        """Mark handler cache as dirty (call when tree structure changes)."""
        self._handlers_dirty = True

    def _get_event_forwarding(self) -> dict:
        """Get event handlers from all renderables (cached)."""
        if not self._handlers_dirty:
            return self._cached_handlers

        handlers: dict[str, list[Callable]] = {"key": [], "mouse": [], "paste": []}

        if self._root:
            self._collect_handlers(self._root, handlers)

        self._cached_handlers = handlers
        self._handlers_dirty = False
        return handlers

    def _collect_handlers(self, renderable, handlers: dict) -> None:
        """Recursively collect event handlers."""
        try:
            handlers["key"].append(renderable._key_handler)
        except AttributeError:
            pass

        try:
            handler = renderable._on_key_down
            if handler is not None:
                handlers["key"].append(handler)
        except AttributeError:
            pass

        try:
            for child in renderable.get_children():
                self._collect_handlers(child, handlers)
        except AttributeError:
            pass

    # Post-processing pipeline
    def add_post_process_fn(self, fn: Callable) -> None:
        """Add a post-processing function called after each render."""
        self._post_process_fns.append(fn)

    def remove_post_process_fn(self, fn: Callable) -> None:
        """Remove a post-processing function."""
        self._post_process_fns = [f for f in self._post_process_fns if f is not fn]

    def set_frame_callback(self, callback: Callable) -> None:
        """Add a callback called before each frame render."""
        self._frame_callbacks.append(callback)

    def remove_frame_callback(self, callback: Callable) -> None:
        """Remove a frame callback."""
        self._frame_callbacks = [f for f in self._frame_callbacks if f is not callback]

    def request_animation_frame(self, callback: Callable) -> int:
        """Request a callback on the next animation frame. Returns handle for cancellation."""
        handle = self._next_animation_id
        self._next_animation_id += 1
        self._animation_frame_callbacks[handle] = callback
        return handle

    def cancel_animation_frame(self, handle: int) -> None:
        """Cancel a previously requested animation frame callback."""
        self._animation_frame_callbacks.pop(handle, None)

    # Cursor and theme
    def set_cursor_style(self, style: str) -> None:
        """Set cursor style ('block', 'underline', 'bar')."""
        style_map = {"block": 2, "underline": 4, "bar": 6}
        code = style_map.get(style, 2)
        try:
            import sys
            sys.stdout.write(f"\x1b[{code} q")
            sys.stdout.flush()
        except Exception:
            pass

    def set_cursor_color(self, color: str) -> None:
        """Set cursor color (hex string)."""
        try:
            import sys
            sys.stdout.write(f"\x1b]12;{color}\x07")
            sys.stdout.flush()
        except Exception:
            pass

    def get_theme_mode(self) -> str | None:
        """Get terminal theme mode ('dark', 'light', or None if unknown)."""
        # Most terminals default to dark mode
        try:
            import os
            colorfgbg = os.environ.get("COLORFGBG", "")
            if colorfgbg:
                parts = colorfgbg.split(";")
                if len(parts) >= 2:
                    bg = int(parts[-1])
                    return "light" if bg > 8 else "dark"
        except (ValueError, IndexError):
            pass
        return None

    def stop(self) -> None:
        """Stop the renderer and event loop."""
        self._running = False
        if self._event_loop is not None:
            self._event_loop.stop()

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
