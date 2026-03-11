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
    use_alternate_screen: bool = True
    exit_on_ctrl_c: bool = True
    target_fps: int = 60
    console_options: dict | None = None
    clear_color: s.RGBA | str | None = None


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
        self._offset_stack: list[tuple[int, int]] = []

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

    # Drawing offset stack (equivalent to OpenCode's translateX/translateY)
    def push_offset(self, dx: int, dy: int) -> None:
        """Push a drawing offset. All draw/scissor operations shift by (dx, dy).

        Offsets are cumulative — pushing (0, -5) then (0, -3) results in
        an effective offset of (0, -8).  This mirrors OpenCode's translateY
        which is a pure render-time transform that never triggers layout.
        """
        if self._offset_stack:
            cur_dx, cur_dy = self._offset_stack[-1]
            self._offset_stack.append((cur_dx + dx, cur_dy + dy))
        else:
            self._offset_stack.append((dx, dy))

    def pop_offset(self) -> None:
        """Pop the most recent drawing offset."""
        if self._offset_stack:
            self._offset_stack.pop()

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        fg: s.RGBA | None = None,
        bg: s.RGBA | None = None,
        attributes: int = 0,
    ) -> None:
        # Apply drawing offset (render-time translation, like OpenCode translateY)
        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

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
        # Apply drawing offset
        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

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
        # Apply drawing offset so nested scissor rects within a scrolled
        # container use the same coordinate space as draw operations.
        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

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
        self._force_next_render: bool = True  # Force first frame to be a full repaint
        self._clear_color: s.RGBA | None = self._parse_clear_color(config.clear_color)
        self._mouse_enabled: bool = False

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

    @staticmethod
    def _parse_clear_color(color: s.RGBA | str | None) -> s.RGBA | None:
        if color is None:
            return None
        if isinstance(color, s.RGBA):
            return color
        if isinstance(color, str):
            return s.RGBA.from_hex(color)
        return None

    def set_clear_color(self, color: s.RGBA | str | None) -> None:
        """Set the background color used to fill the buffer before each frame.

        This ensures every cell has an explicit background, preventing the
        terminal's native background from showing through.
        """
        self._clear_color = self._parse_clear_color(color)

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
        self._native.renderer.setup_terminal(self._ptr, self._config.use_alternate_screen)

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
        if self._config.testing or self._ptr is None:
            self._mouse_enabled = True
            return
        self._native.renderer.enable_mouse(self._ptr, enable_movement)
        self._mouse_enabled = True

    def disable_mouse(self) -> None:
        """Disable mouse tracking."""
        if self._config.testing or self._ptr is None:
            self._mouse_enabled = False
            return
        self._native.renderer.disable_mouse(self._ptr)
        self._mouse_enabled = False

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
            term_name=caps_dict.get("term_name", ""),
            term_version=caps_dict.get("term_version", ""),
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
        """Resize the renderer and force a full repaint on the next frame."""
        self._native.renderer.resize_renderer(self._ptr, width, height)
        self._width = width
        self._height = height
        self._force_next_render = True

    def clear_terminal(self) -> None:
        """Clear the terminal screen (wipe reflow artifacts after resize)."""
        self._native.renderer.clear_terminal(self._ptr)

    def request_render(self) -> None:
        """Request a render on the next frame."""
        pass

    def set_event_callback(self, callback: Callable) -> None:
        """Set callback for terminal events."""
        self._event_callbacks.append(callback)

    def run(self) -> None:
        """Run the renderer main loop with event handling."""
        import os as _os
        import select as _sel
        import sys as _sys
        import termios as _termios
        import time as _time

        self._running = True

        # Disable echo BEFORE setup_terminal() so capability responses
        # (e.g. Ghostty's DCS "P>|ghostty 1.3.0...") aren't echoed to
        # the screen.  setup_terminal()'s native code sends queries
        # (xtversion, DECRQM, etc.) before entering raw mode — responses
        # arriving in that window would be visible without this.
        fd = _sys.stdin.fileno()
        try:
            _pre_attrs = _termios.tcgetattr(fd)
            _noecho = _termios.tcgetattr(fd)
            _noecho[3] &= ~_termios.ECHO  # lflags: disable echo
            _termios.tcsetattr(fd, _termios.TCSANOW, _noecho)
        except (OSError, _termios.error):
            _pre_attrs = None

        self.setup()

        # Drain capability responses from stdin so they don't get
        # misinterpreted as user input by the InputHandler.
        # Poll with a deadline; stop early after idle silence.
        _DRAIN_DEADLINE = 0.4  # max seconds to wait for responses
        _DRAIN_IDLE = 0.08     # seconds of silence before declaring done

        deadline = _time.perf_counter() + _DRAIN_DEADLINE
        last_data = _time.perf_counter()
        while _time.perf_counter() < deadline:
            remaining = min(deadline - _time.perf_counter(), _DRAIN_IDLE)
            if remaining <= 0:
                break
            if _sel.select([fd], [], [], remaining)[0]:
                _os.read(fd, 4096)
                last_data = _time.perf_counter()
            else:
                if _time.perf_counter() - last_data >= _DRAIN_IDLE:
                    break

        # Restore original terminal attrs (InputHandler.start() will
        # set its own cbreak mode shortly).
        if _pre_attrs is not None:
            try:
                _termios.tcsetattr(fd, _termios.TCSANOW, _pre_attrs)
            except (OSError, _termios.error):
                pass

        from .input import EventLoop

        event_loop = EventLoop(target_fps=self._config.target_fps)
        self._event_loop = event_loop
        input_handler = event_loop.input_handler

        for event_type, handlers in self._get_event_forwarding().items():
            if event_type == "key":
                for handler in handlers:
                    input_handler.on_key(handler)
            elif event_type == "paste":
                for handler in handlers:
                    input_handler.on_paste(handler)

        for handler in hooks.get_keyboard_handlers():
            input_handler.on_key(handler)

        for handler in hooks.get_paste_handlers():
            input_handler.on_paste(handler)

        input_handler.on_mouse(self._dispatch_mouse_event)

        # Forward mouse handlers and enable mouse tracking
        for handler in hooks.get_mouse_handlers():
            input_handler.on_mouse(handler)

        self._refresh_mouse_tracking()

        event_loop.on_frame(lambda dt: self._render_frame(dt))

        try:
            event_loop.run()
        except KeyboardInterrupt:
            if self._config.exit_on_ctrl_c:
                pass
            else:
                raise
        finally:
            # Native destroy_renderer() performs the real renderer shutdown
            # sequence, including alt-screen exit and terminal state reset.
            # This Python-side cleanup should only drain in-flight stdin data
            # so terminal responses do not leak into the shell.
            import os as _os2
            import select as _sel2
            import sys as _sys2
            import time as _time2

            # Drain stdin aggressively: catch mouse events, capability
            # responses, and other escape sequences that were in-flight.
            # Without this, leftover bytes leak into the shell after exit.
            # Multiple rounds ensure late-arriving bytes are caught.
            try:
                fd2 = _sys2.stdin.fileno()
                for _ in range(3):
                    _time2.sleep(0.03)
                    while _sel2.select([fd2], [], [], 0.02)[0]:
                        _os2.read(fd2, 4096)
            except (OSError, ValueError):
                pass

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

        self._refresh_mouse_tracking()

        if self._root:
            try:
                self._update_layout(self._root, delta_time)
            except Exception:
                _log.exception("Error updating layout")

        buffer = self.get_next_buffer()
        buffer.clear()

        # Fill entire buffer with clear color so every cell has an explicit
        # background.  Without this, transparent cells show the terminal's
        # native background color (e.g. Ghostty's gray).
        if self._clear_color:
            buffer.fill_rect(0, 0, self._width, self._height, self._clear_color)

        if self._root:
            try:
                self._root.render(buffer, delta_time)
            except Exception:
                _log.exception("Error rendering root")

        # Run post-processing functions after render
        for fn in self._post_process_fns:
            fn(buffer)

        # Force a full repaint (bypass diff) after resize or on first frame.
        force = self._force_next_render
        if force:
            self._force_next_render = False
        self.render(force=force)

    def _rebuild_component_tree(self) -> None:
        """Rebuild the component tree from the component function."""
        if self._root is None or self._component_fn is None:
            return

        import time as _time
        from .reconciler import reconcile

        t0 = _time.perf_counter_ns()
        old_children = list(self._root._children)
        try:
            component = self._component_fn()
            t1 = _time.perf_counter_ns()
            new_children = [component]
            self._root._children.clear()
            reconcile(self._root, old_children, new_children)
            t2 = _time.perf_counter_ns()
            _log.debug(
                "rebuild: component_fn=%.2fms reconcile=%.2fms total=%.2fms",
                (t1 - t0) / 1e6, (t2 - t1) / 1e6, (t2 - t0) / 1e6,
            )
        except Exception:
            _log.exception("Error rebuilding component tree, restoring previous")
            self._root._children = old_children
            for child in old_children:
                child._parent = self._root
            # Restore yoga children to match restored _children
            self._root._yoga_node.remove_all_children()
            for child in old_children:
                self._root._yoga_node.insert_child(
                    child._yoga_node, self._root._yoga_node.child_count
                )

    def _refresh_mouse_tracking(self) -> None:
        """Enable or disable mouse tracking based on the current tree."""
        should_enable = (
            bool(hooks.get_mouse_handlers())
            or self._tree_has_mouse_handlers(self._root)
            or self._tree_has_scroll_targets(self._root)
        )
        if should_enable and not self._mouse_enabled:
            self.enable_mouse()
        elif not should_enable and self._mouse_enabled:
            self.disable_mouse()

    def _update_layout(self, renderable, delta_time: float) -> None:
        """Update layout for a renderable and its children using yoga."""
        if renderable is self._root and self._root:
            # Configure yoga properties (children already synced by add/remove/reconciler)
            self._root._configure_yoga_properties()

            from . import layout as yoga_layout

            yoga_layout.compute_layout(self._root._yoga_node, float(self._width), float(self._height))

            self._apply_yoga_layout_recursive(self._root)

        if hasattr(renderable, "update_layout"):
            renderable.update_layout(delta_time)

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
            handler = renderable._on_paste
            if handler is not None:
                handlers["paste"].append(handler)
        except AttributeError:
            pass

        try:
            for child in renderable.get_children():
                self._collect_handlers(child, handlers)
        except AttributeError:
            pass

    def _tree_has_mouse_handlers(self, renderable) -> bool:
        """Return True when any renderable in the tree handles mouse events."""
        if renderable is None:
            return False

        try:
            for attr in (
                "_on_mouse_down",
                "_on_mouse_up",
                "_on_mouse_move",
                "_on_mouse_drag",
                "_on_mouse_scroll",
            ):
                if getattr(renderable, attr, None) is not None:
                    return True
        except AttributeError:
            pass

        try:
            return any(self._tree_has_mouse_handlers(child) for child in renderable.get_children())
        except AttributeError:
            return False

    def _tree_has_scroll_targets(self, renderable) -> bool:
        """Return True when any renderable in the tree owns wheel scrolling."""
        if renderable is None:
            return False
        if getattr(renderable, "_is_scroll_target", False):
            return True
        try:
            return any(self._tree_has_scroll_targets(child) for child in renderable.get_children())
        except AttributeError:
            return False

    def _dispatch_mouse_event(self, event) -> None:
        """Dispatch a mouse event through the render tree before global hooks."""
        if self._root is None:
            return
        if event.type == "scroll":
            self._dispatch_scroll_event(event)
            return
        self._dispatch_mouse_to_tree(self._root, event)

    def _dispatch_scroll_event(self, event) -> None:
        """Route wheel input to the deepest scroll target under the pointer."""
        if self._root is None:
            return

        target = self._find_scroll_target(self._root, event.x, event.y)
        if target is not None:
            event.target = target
            handler = getattr(target, "handle_scroll_event", None)
            if handler is not None:
                handler(event)
            else:
                fallback = getattr(target, "_on_mouse_scroll", None)
                if fallback is not None:
                    fallback(event)

    def _find_scroll_target(self, renderable, x: int, y: int):
        """Return the deepest registered scroll target under *(x, y)*."""
        try:
            children = list(renderable.get_children())
        except AttributeError:
            children = []

        for child in reversed(children):
            found = self._find_scroll_target(child, x, y)
            if found is not None:
                return found

        contains_point = getattr(renderable, "contains_point", None)
        inside = True if contains_point is None else contains_point(x, y)

        if inside and getattr(renderable, "_is_scroll_target", False):
            return renderable
        return None

    def _dispatch_mouse_to_tree(self, renderable, event) -> None:
        """Walk children front-to-back and dispatch to the deepest hit target."""
        if event.propagation_stopped:
            return

        contains_point = getattr(renderable, "contains_point", None)
        inside = True if contains_point is None else contains_point(event.x, event.y)

        try:
            children = list(renderable.get_children())
        except AttributeError:
            children = []

        for child in reversed(children):
            child_contains = getattr(child, "contains_point", None)
            if child_contains is not None and not child_contains(event.x, event.y):
                continue
            self._dispatch_mouse_to_tree(child, event)
            if event.propagation_stopped:
                return

        if not inside:
            return

        handler_map = {
            "down": "_on_mouse_down",
            "up": "_on_mouse_up",
            "move": "_on_mouse_move",
            "drag": "_on_mouse_drag",
            "scroll": "_on_mouse_scroll",
        }
        attr = handler_map.get(event.type)
        if not attr:
            return

        handler = getattr(renderable, attr, None)
        if handler is not None:
            event.target = renderable
            handler(event)

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
