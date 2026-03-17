"""CliRenderer class - wrapper around native OpenTUI renderer using nanobind."""

from __future__ import annotations

import asyncio
import enum
import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .structs import char_width as _char_width
from .structs import display_width as _display_width

_log = logging.getLogger(__name__)


# Mouse event type → handler attribute name (hoisted from _dispatch_mouse_to_tree
# to avoid per-call dict allocation during recursive tree walks).
_MOUSE_HANDLER_MAP = {
    "down": "_on_mouse_down",
    "up": "_on_mouse_up",
    "move": "_on_mouse_move",
    "drag": "_on_mouse_drag",
    "scroll": "_on_mouse_scroll",
}

import contextlib

from . import hooks
from . import structs as s
from .components.base import BaseRenderable
from .console import TerminalConsole
from .ffi import get_native, is_native_available


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
    # Kitty keyboard protocol flags.  Bit layout:
    #   1 = disambiguate escape codes
    #   2 = report event types (press / repeat / release)
    #  16 = report associated text (IME-composed text in CSI-u field 3)
    # Flag 16 is critical for CJK IME — the terminal sends the composed
    # syllable in field 3 instead of raw key codes, so Korean/Chinese/
    # Japanese input works correctly.
    kitty_keyboard_flags: int = 19  # 1 + 2 + 16
    # Whether mouse tracking should be enabled on startup.
    # None means auto-detect (enable when tree has mouse handlers).
    use_mouse: bool | None = None
    # Whether left-click automatically focuses focusable elements.
    auto_focus: bool = True
    # Experimental split-panel rendering: only the bottom N rows of the
    # terminal are used for rendering.  Mouse events above the render area
    # are ignored and y-coordinates are offset so that y=0 corresponds to
    # the top of the rendered region.
    experimental_split_height: int | None = None


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

    def __init__(self, ptr: Any, native: Any, graphics: Any = None):
        self._ptr = ptr
        self._native = native
        self._graphics = graphics
        self._width: int | None = None
        self._height: int | None = None
        self._scissor_stack: list[tuple[int, int, int, int]] = []
        self._opacity_stack: list[float] = []
        self._cached_opacity: float = 1.0
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
        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return

        if self._scissor_stack:
            sx, sy, sw, sh = self._scissor_stack[-1]
            if sw <= 0 or sh <= 0:
                return
            if y < sy or y >= sy + sh:
                return
            text_dw = _display_width(text)
            if x + text_dw <= sx or x >= sx + sw:
                return
            if x < sx:
                # Trim characters from the left until we reach the scissor edge.
                trim_cols = sx - x
                trimmed = 0
                i = 0
                while i < len(text) and trimmed < trim_cols:
                    trimmed += _char_width(text[i])
                    i += 1
                text = text[i:]
                x = sx
            end = sx + sw
            remaining_dw = _display_width(text)
            if x + remaining_dw > end:
                # Trim characters from the right to fit within the scissor.
                max_cols = end - x
                kept = 0
                i = 0
                while i < len(text) and kept + _char_width(text[i]) <= max_cols:
                    kept += _char_width(text[i])
                    i += 1
                text = text[:i]
            if not text:
                return

        # Guard against negative x after scissor clipping (off-screen left).
        if x < 0:
            return

        fg = self._apply_opacity_to_color(fg)
        bg = self._apply_opacity_to_color(bg)

        text_bytes = text.encode("utf-8") if isinstance(text, str) else text

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
        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy

        if x < 0:
            width += x
            x = 0
        if y < 0:
            height += y
            y = 0
        if width <= 0 or height <= 0:
            return

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

    def _check_bounds(self, x: int, y: int) -> None:
        """Validate (x, y) is within buffer dimensions."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise IndexError(f"cell ({x}, {y}) out of bounds for {self.width}x{self.height} buffer")

    def get_bg_color(self, x: int, y: int) -> s.RGBA:
        """Read the background color at (x, y) from the native buffer.

        Returns an RGBA tuple with values in [0.0, 1.0].
        Used for testing line color rendering.
        """
        import ctypes

        self._check_bounds(x, y)
        bg_ptr = self._native.buffer_get_bg_ptr(self._ptr)
        w = self.width
        offset = (y * w + x) * 4
        arr_type = ctypes.c_float * 4
        arr = arr_type.from_address(bg_ptr + offset * ctypes.sizeof(ctypes.c_float))
        return s.RGBA(arr[0], arr[1], arr[2], arr[3])

    def get_fg_color(self, x: int, y: int) -> s.RGBA:
        """Read the foreground color at (x, y) from the native buffer.

        Returns an RGBA tuple with values in [0.0, 1.0].
        Used for testing sign color rendering.
        """
        import ctypes

        self._check_bounds(x, y)
        fg_ptr = self._native.buffer_get_fg_ptr(self._ptr)
        w = self.width
        offset = (y * w + x) * 4
        arr_type = ctypes.c_float * 4
        arr = arr_type.from_address(fg_ptr + offset * ctypes.sizeof(ctypes.c_float))
        return s.RGBA(arr[0], arr[1], arr[2], arr[3])

    def draw_editor_view(self, editor_view: Any, x: int = 0, y: int = 0) -> None:
        """Render an EditorView into this buffer using native drawEditorView.

        This delegates to the native C++ implementation which handles wrapping,
        scrolling, syntax highlighting, and cursor rendering correctly.

        Args:
            editor_view: A NativeEditorView instance (must have a .ptr attribute).
            x: X offset in the buffer.
            y: Y offset in the buffer.
        """
        from .native import _nb

        if self._offset_stack:
            dx, dy = self._offset_stack[-1]
            x += dx
            y += dy
        _nb.editor_view.buffer_draw_editor_view(self._ptr, editor_view.ptr, x, y)

    def get_plain_text(self) -> str:
        """Get buffer contents as plain text string.

        Uses native writeResolvedChars to decode the buffer (including
        grapheme clusters and box-drawing characters) into UTF-8 text.
        Returns newline-separated lines with trailing spaces stripped.
        """
        try:
            raw: bytes = self._native.buffer_write_resolved_chars(self._ptr, True)
            if not raw:
                return ""
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            return ""

        lines = [line.rstrip() for line in text.split("\n")]

        while lines and not lines[-1]:
            lines.pop()

        return "\n".join(lines)

    def get_attributes(self, x: int, y: int) -> int:
        """Read the attributes bitmask at (x, y) from the native buffer."""
        import ctypes

        self._check_bounds(x, y)
        attr_ptr = self._native.buffer_get_attributes_ptr(self._ptr)
        w = self.width
        offset = y * w + x
        arr = (ctypes.c_uint32 * 1).from_address(attr_ptr + offset * ctypes.sizeof(ctypes.c_uint32))
        return arr[0]

    def get_char_code(self, x: int, y: int) -> int:
        """Read the character codepoint at (x, y) from the native buffer."""
        import ctypes

        self._check_bounds(x, y)
        char_ptr = self._native.buffer_get_char_ptr(self._ptr)
        w = self.width
        offset = y * w + x
        arr = (ctypes.c_uint32 * 1).from_address(char_ptr + offset * ctypes.sizeof(ctypes.c_uint32))
        return arr[0]

    def get_span_lines(self) -> list[dict]:
        """Get span lines for diff testing."""
        w = self.width
        h = self.height

        if w <= 0 or h <= 0:
            return []

        try:
            raw: bytes = self._native.buffer_write_resolved_chars(self._ptr, True)
            real_text = raw.decode("utf-8", errors="replace") if raw else ""
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

        # Sync with the native Zig buffer's scissor stack so that native
        # draw calls (e.g. bufferDrawTextBufferView) are clipped too.
        if self._graphics is not None:
            final = self._scissor_stack[-1]
            self._graphics.buffer_push_scissor_rect(
                self._ptr,
                final[0],
                final[1],
                max(0, final[2]),
                max(0, final[3]),
            )

    def pop_scissor_rect(self) -> None:
        """Pop the most recent scissor rectangle."""
        if self._scissor_stack:
            self._scissor_stack.pop()
            if self._graphics is not None:
                self._graphics.buffer_pop_scissor_rect(self._ptr)

    def get_scissor_rect(self) -> tuple[int, int, int, int] | None:
        """Get the current scissor rectangle, or None if no clipping."""
        return self._scissor_stack[-1] if self._scissor_stack else None

    def _clip_coords(self, x: int, y: int) -> bool:
        """Check if coordinates are within the current scissor rect."""
        if not self._scissor_stack:
            return True
        sx, sy, sw, sh = self._scissor_stack[-1]
        return sx <= x < sx + sw and sy <= y < sy + sh

    # Opacity stack (cached product avoids O(n) recomputation per draw call)
    def push_opacity(self, opacity: float) -> None:
        """Push an opacity value. Combined multiplicatively with the stack."""
        self._opacity_stack.append(opacity)
        self._cached_opacity = max(0.0, min(1.0, self._cached_opacity * opacity))

    def pop_opacity(self) -> None:
        """Pop the most recent opacity value."""
        if self._opacity_stack:
            removed = self._opacity_stack.pop()
            if not self._opacity_stack:
                self._cached_opacity = 1.0
            elif removed != 0.0:
                self._cached_opacity = max(0.0, min(1.0, self._cached_opacity / removed))
            else:
                # Recompute from scratch if we divided by zero
                self._cached_opacity = 1.0
                for o in self._opacity_stack:
                    self._cached_opacity *= o
                self._cached_opacity = max(0.0, min(1.0, self._cached_opacity))

    def get_current_opacity(self) -> float:
        """Get the current combined opacity (product of all values in the stack)."""
        return self._cached_opacity

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


_BORDER_CHARS = {
    "single": ("┌", "┐", "└", "┘", "─", "│"),
    "double": ("╔", "╗", "╚", "╝", "═", "║"),
    "round": ("╭", "╮", "╰", "╯", "─", "│"),
    "bold": ("┏", "┓", "┗", "┛", "━", "┃"),
    "block": ("█", "█", "█", "█", "█", "█"),
}


def _get_border_chars(style: str) -> tuple[str, str, str, str, str, str]:
    """Get border characters for a style. Returns (tl, tr, bl, br, horizontal, vertical)."""
    return _BORDER_CHARS.get(style, _BORDER_CHARS["single"])


class RendererControlState(enum.Enum):
    """Renderer control state for the render loop lifecycle."""

    IDLE = "idle"
    AUTO_STARTED = "auto_started"
    EXPLICIT_STARTED = "explicit_started"
    EXPLICIT_PAUSED = "explicit_paused"
    EXPLICIT_SUSPENDED = "explicit_suspended"
    EXPLICIT_STOPPED = "explicit_stopped"


class CliRenderer:
    """CLI renderer - wraps the native OpenTUI renderer using nanobind."""

    def __init__(self, ptr: Any, config: CliRendererConfig, native: Any):
        self._ptr = ptr
        self._config = config
        self._native = native
        self._running = False
        # Control state machine for render loop lifecycle
        self._control_state: RendererControlState = RendererControlState.IDLE
        self._rendering: bool = False
        self._update_scheduled: bool = False
        self._immediate_rerender_requested: bool = False
        self._live_request_counter: int = 0
        self._idle_futures: list[asyncio.Future[None]] = []
        self._root: RootRenderable | None = None
        self._event_callbacks: list[Callable] = []
        self._component_fn: Callable | None = None
        self._signal_state: Any = None
        self._last_component: Any = None
        # Handler cache
        self._handlers_dirty = True
        self._cached_handlers: dict[str, list[Callable]] = {"key": [], "mouse": [], "paste": []}
        # Auto-focus: whether left-click should automatically focus focusable elements.
        # Set to False to prevent click-driven focus changes.
        self._auto_focus: bool = config.auto_focus
        # Currently focused renderable (for auto-focus tracking).
        self._focused_renderable: Any = None
        # Whether a drag operation is in progress (prevents auto-focus during drag).
        self._is_dragging: bool = False
        # Post-processing and frame callbacks
        self._post_process_fns: list[Callable] = []
        self._frame_callbacks: list[Callable] = []
        self._animation_frame_callbacks: dict[int, Callable] = {}
        self._next_animation_id: int = 0
        self._event_loop: Any = None
        self._force_next_render: bool = True  # Force first frame to be a full repaint
        self._clear_color: s.RGBA | None = self._parse_clear_color(config.clear_color)
        self._mouse_enabled: bool = False
        self._captured_renderable: Any = None
        # Per-frame cursor state — components call request_cursor() and
        # request_cursor_style() during render_after callbacks;
        # _apply_cursor() resolves everything after the frame buffer is
        # flushed.
        self._cursor_request: tuple[int, int] | None = None
        self._cursor_style_request: str | None = None
        self._cursor_color_request: str | None = None
        self._cursor_style: str = "block"
        self._cursor_color: str | None = None
        # Per-frame Kitty graphics tracking — Image components register their
        # graphics IDs each frame via register_frame_graphics().  After the
        # frame is flushed, _clear_stale_graphics() deletes any IDs that were
        # active last frame but not this frame (e.g. Image removed from tree,
        # hidden by overlay, or source changed).
        self._prev_frame_graphics: set[int] = set()
        self._frame_graphics: set[int] = set()
        # Graphics suppression — when True, Image components skip Kitty/sixel
        # draws and don't register their IDs, so _clear_stale_graphics()
        # removes them automatically.  Overlays set this to hide graphics
        # that would otherwise bleed through the text layer.
        self._graphics_suppressed: bool = False
        # Mouse pointer (cursor) style — set via set_mouse_pointer().
        # Tracks the OS-level mouse cursor shape (e.g. "pointer", "text").
        self._current_mouse_pointer_style: str = "default"
        # Hover tracking — last renderable the pointer was over, used to
        # dispatch _on_mouse_over / _on_mouse_out events when the element
        # under the pointer changes.
        self._last_over_renderable: Any = None
        # Pointer tracking — last known mouse position and whether the pointer
        # has ever been inside the terminal.  Used by _recheck_hover_state()
        # to fire synthetic over/out events after render even without new
        # mouse movement for hover recheck after render.
        self._latest_pointer: dict[str, int] = {"x": 0, "y": 0}
        self._has_pointer: bool = False
        self._last_pointer_modifiers: dict[str, bool] = {
            "shift": False,
            "alt": False,
            "ctrl": False,
        }
        # Event emitter — listeners for renderer-level events like "focus"/"blur".
        # Event listeners for terminal focus/blur tracking.
        self._event_listeners: dict[str, list[Callable]] = {}
        # Palette detection state
        self._palette_detector: Any = None
        self._cached_palette: Any = None
        self._palette_detection_promise: asyncio.Task | asyncio.Future | None = None
        # Selection state — current text selection model.
        # Current text selection and its container hierarchy.
        self._current_selection: Any = None
        self._selection_containers: list[Any] = []
        # Split-height rendering — when > 0, only the bottom N rows of the
        # terminal are used.  _render_offset is ``terminal_height - split_height``
        # and mouse y-coordinates below that threshold are ignored / offset.
        self._split_height: int = 0
        self._render_offset: int = 0
        self._terminal_height: int = 0  # full terminal height before split

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

        # Apply experimental split-height (must happen after _width/_height are set).
        self._terminal_height = self._height
        sh = config.experimental_split_height or 0
        if sh > 0:
            self._split_height = sh
            self._render_offset = self._height - sh
            self._height = sh

        # Console overlay — intercepts mouse events inside its bounds.
        # Must happen after _width/_height are set so dimension computation works.
        self._console: TerminalConsole = TerminalConsole(self, config.console_options)
        self._use_console: bool = True

        # If use_mouse is explicitly configured, apply it now.
        if config.use_mouse is True:
            self._mouse_enabled = True
        elif config.use_mouse is False:
            self._mouse_enabled = False

    @staticmethod
    def _parse_clear_color(color: s.RGBA | str | None) -> s.RGBA | None:
        if color is None:
            return None
        if isinstance(color, s.RGBA):
            return color
        if isinstance(color, str):
            return s.parse_color(color)
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
    def split_height(self) -> int:
        """Return the current experimental split height (0 = disabled)."""
        return self._split_height

    @split_height.setter
    def split_height(self, value: int) -> None:
        """Set the experimental split height.

        When > 0, only the bottom *value* rows of the terminal are used for
        rendering.  Mouse events with y < render_offset are ignored and
        y-coordinates are shifted so that y=0 is the top of the rendered
        region.
        """
        value = max(value, 0)
        self._split_height = value
        if value > 0:
            self._render_offset = self._terminal_height - value
            self._height = value
        else:
            self._render_offset = 0
            self._height = self._terminal_height

    @property
    def use_console(self) -> bool:
        return self._use_console

    @use_console.setter
    def use_console(self, value: bool) -> None:
        self._use_console = value

    @property
    def console(self) -> TerminalConsole:
        return self._console

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

    @property
    def use_mouse(self) -> bool:
        """Whether mouse tracking is currently enabled."""
        return self._mouse_enabled

    @use_mouse.setter
    def use_mouse(self, value: bool) -> None:
        """Enable or disable mouse tracking."""
        if value:
            self.enable_mouse()
        else:
            self.disable_mouse()

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

    def request_cursor(self, x: int, y: int) -> None:
        """Request the terminal cursor at (x, y) for this frame.

        Components call this from ``render_after`` callbacks when screen
        coordinates are known.  The last request wins — only one cursor
        can be active.  After the frame buffer is flushed, ``_apply_cursor``
        resolves the request via ``set_cursor_position``.
        """
        self._cursor_request = (x, y)

    def request_cursor_style(self, style: str = "block", color: str | None = None) -> None:
        """Request a cursor style (and optional color) for this frame.

        Components call this from ``render_after`` callbacks alongside
        ``request_cursor``.  If no position is requested the style is
        ignored (hidden cursor doesn't need styling).
        """
        self._cursor_style_request = style
        self._cursor_color_request = color

    _DECSCUSR = {
        "block": 1,
        "underline": 3,
        "bar": 5,
        "steady_block": 2,
        "steady_underline": 4,
        "steady_bar": 6,
    }

    def _apply_cursor(self) -> None:
        """Apply (or hide) the cursor after the frame buffer is flushed.

        **Testing mode** delegates to ``set_cursor_position`` + ``write_out``
        for simple assertion-based tests.

        **Live mode** keeps the native cursor permanently hidden so that
        ``render()`` never sends ``\\x1b[?25h`` every frame (which resets
        the terminal's blink timer and prevents blinking).  Instead,
        cursor position, shape, and visibility are managed directly via
        ``sys.stdout`` with a software blink timer that toggles show/hide
        at ~530 ms intervals — matching typical OS cursor blink rates.
        """
        req = self._cursor_request
        style_req = self._cursor_style_request
        color_req = self._cursor_color_request
        self._cursor_request = None
        self._cursor_style_request = None
        self._cursor_color_request = None

        # ── Testing path ──────────────────────────────────────────
        if self._config.testing:
            if req is not None:
                self.set_cursor_position(req[0] + 1, req[1] + 1, visible=True)
                style = style_req or "block"
                code = self._DECSCUSR.get(style, 1)
                esc = f"\x1b[{code} q"
                self._cursor_style = style
                if color_req is not None:
                    self._cursor_color = color_req
                    esc += f"\x1b]12;{color_req}\x07"
                elif self._cursor_color is not None:
                    self._cursor_color = None
                    esc += "\x1b]112\x07"
                self.write_out(esc.encode())
            else:
                self.set_cursor_position(0, 0, visible=False)
            return

        # ── Live path ─────────────────────────────────────────────
        # Keep native cursor hidden so render() emits \x1b[?25l
        # (harmless no-op) instead of \x1b[?25h (which kills blink).
        self.set_cursor_position(0, 0, visible=False)

        if req is not None:
            import time as _time

            # Software blink: alternate visible / hidden at ~530 ms.
            blink_on = int(_time.monotonic() * 1000 / 530) % 2 == 0

            if blink_on:
                col = req[0] + 1
                row = req[1] + 1
                style = style_req or "block"
                # Steady DECSCUSR — shape only; blink handled by our timer.
                _STEADY = {
                    "block": 2,
                    "underline": 4,
                    "bar": 6,
                    "steady_block": 2,
                    "steady_underline": 4,
                    "steady_bar": 6,
                }
                code = _STEADY.get(style, 2)
                self._cursor_style = style

                # CUP (position) → DECSCUSR (shape) → DECTCEM (show)
                esc = f"\x1b[{row};{col}H\x1b[{code} q\x1b[?25h"

                if color_req is not None:
                    self._cursor_color = color_req
                    esc += f"\x1b]12;{color_req}\x07"
                elif self._cursor_color is not None:
                    self._cursor_color = None
                    esc += "\x1b]112\x07"

                import sys as _sys

                _sys.stdout.write(esc)
                _sys.stdout.flush()
            # blink_off: render()'s \x1b[?25l keeps cursor hidden.

    @property
    def graphics_suppressed(self) -> bool:
        """Whether Kitty/sixel graphics drawing is currently suppressed."""
        return self._graphics_suppressed

    def suppress_graphics(self) -> None:
        """Suppress Kitty/sixel graphics drawing.

        While suppressed, Image components skip their graphics protocol draws
        and don't register their IDs.  The stale-graphics tracker then clears
        any previously drawn graphics automatically.  Call
        ``unsuppress_graphics()`` to resume; Images detect the transition and
        force a redraw.

        Typical use: overlay managers call this when a dialog opens and
        ``unsuppress_graphics()`` when it closes.
        """
        self._graphics_suppressed = True

    def unsuppress_graphics(self) -> None:
        """Resume Kitty/sixel graphics drawing after suppression."""
        self._graphics_suppressed = False

    def register_frame_graphics(self, graphics_id: int) -> None:
        """Register a Kitty graphics ID as active for this frame.

        Image components call this during ``render()`` each frame they draw
        (or skip drawing due to an unchanged signature).  After the frame
        buffer is flushed, ``_clear_stale_graphics()`` deletes any IDs that
        were active last frame but not this frame.
        """
        self._frame_graphics.add(graphics_id)

    def _clear_stale_graphics(self) -> None:
        """Delete Kitty graphics IDs that went stale since the last frame."""
        stale = self._prev_frame_graphics - self._frame_graphics
        if stale:
            import sys as _sys

            from .filters import _clear_kitty_graphics

            for gid in stale:
                _sys.stdout.buffer.write(_clear_kitty_graphics(gid))
            _sys.stdout.buffer.flush()
        self._prev_frame_graphics = self._frame_graphics
        self._frame_graphics = set()

    def get_cursor_state(self) -> dict:
        """Get the current cursor state (position, visibility)."""
        return self._native.renderer.get_cursor_state(self._ptr)

    def copy_to_clipboard(self, clipboard_type: int, text: str) -> bool:
        """Copy text to clipboard via OSC 52.

        Returns False without writing if the terminal does not support OSC 52.
        """
        caps = self.get_capabilities()
        if not caps.osc52:
            return False
        return self._native.renderer.copy_to_clipboard_osc52(self._ptr, clipboard_type, text)

    def clear_clipboard(self, clipboard_type: int) -> bool:
        """Clear clipboard via OSC 52.

        Returns False without writing if the terminal does not support OSC 52.
        """
        caps = self.get_capabilities()
        if not caps.osc52:
            return False
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
        return Buffer(ptr, self._native.buffer, self._native.graphics)

    def get_current_buffer(self) -> Buffer:
        """Get the current buffer."""
        ptr = self._native.renderer.get_current_buffer(self._ptr)
        return Buffer(ptr, self._native.buffer, self._native.graphics)

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
        """Request a render on the next frame.

        In test mode this is a no-op (tests drive rendering via
        ``render_frame()``).  In production the control-state machine
        determines whether a frame is scheduled.
        """
        if self._control_state == RendererControlState.EXPLICIT_SUSPENDED:
            return
        if self._running:
            return
        if self._rendering:
            self._immediate_rerender_requested = True
            return
        # In test mode, just mark scheduled (resolved by next render_frame).
        self._update_scheduled = True

    def set_event_callback(self, callback: Callable) -> None:
        """Set callback for terminal events."""
        self._event_callbacks.append(callback)

    def on(self, event: str, handler: Callable) -> Callable[[], None]:
        """Register an event listener on the renderer.

        Supported events: ``"focus"``, ``"blur"``.

        Registers handlers for terminal focus/blur events.

        Returns an unsubscribe function.
        """
        listeners = self._event_listeners.setdefault(event, [])
        listeners.append(handler)

        def _unsub() -> None:
            with contextlib.suppress(ValueError):
                listeners.remove(handler)

        return _unsub

    def emit_event(self, event: str, *args: Any) -> None:
        """Emit a renderer-level event to all registered listeners.

        Called internally when the input handler detects focus-in / focus-out
        sequences.
        """
        for handler in list(self._event_listeners.get(event, [])):
            with contextlib.suppress(Exception):
                handler(*args)

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

        # Enable the kitty keyboard protocol for structured modifier reporting
        # and associated text (flag 16) for CJK IME composition.
        if not self._config.testing and self._config.kitty_keyboard_flags:
            with contextlib.suppress(Exception):
                self.enable_keyboard(self._config.kitty_keyboard_flags)

        # Drain capability responses from stdin so they don't get
        # misinterpreted as user input by the InputHandler.
        # Poll with a deadline; stop early after idle silence.
        _DRAIN_DEADLINE = 0.4  # max seconds to wait for responses
        _DRAIN_IDLE = 0.08  # seconds of silence before declaring done

        deadline = _time.perf_counter() + _DRAIN_DEADLINE
        last_data = _time.perf_counter()
        while _time.perf_counter() < deadline:
            remaining = min(deadline - _time.perf_counter(), _DRAIN_IDLE)
            if remaining <= 0:
                break
            if _sel.select([fd], [], [], remaining)[0]:
                _os.read(fd, 4096)
                last_data = _time.perf_counter()
            elif _time.perf_counter() - last_data >= _DRAIN_IDLE:
                break

        # Restore original terminal attrs (InputHandler.start() will
        # set its own cbreak mode shortly).
        if _pre_attrs is not None:
            with contextlib.suppress(OSError, _termios.error):
                _termios.tcsetattr(fd, _termios.TCSANOW, _pre_attrs)

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

        # Focus event handling — restore terminal modes on focus-in.
        self._should_restore_modes = False

        def _on_focus(focus_type: str) -> None:
            if focus_type == "blur":
                self._should_restore_modes = True
                self.emit_event("blur")
            elif focus_type == "focus":
                if self._should_restore_modes:
                    self._should_restore_modes = False
                    self._restore_terminal_modes()
                self.emit_event("focus")

        input_handler.on_focus(_on_focus)

        for handler in hooks.get_focus_handlers():
            input_handler.on_focus(handler)

        input_handler.on_mouse(self._dispatch_mouse_event)

        # Forward mouse handlers and enable mouse tracking
        for handler in hooks.get_mouse_handlers():
            input_handler.on_mouse(handler)

        self._refresh_mouse_tracking()

        event_loop.on_frame(self._render_frame)

        try:
            event_loop.run()
        except KeyboardInterrupt:
            if self._config.exit_on_ctrl_c:
                pass
            else:
                raise
        finally:
            # Disable kitty keyboard protocol before tearing down the
            # terminal so the shell doesn't receive extended key reports.
            with contextlib.suppress(Exception):
                self.disable_keyboard()

            # Restore terminal default cursor style (DECSCUSR 0) and color
            # (OSC 112) so the shell cursor returns to its normal appearance.
            try:
                import sys as _csys

                _csys.stdout.write("\x1b[0 q\x1b]112\x07")
                _csys.stdout.flush()
            except Exception:
                pass

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
        self._rendering = True
        self._update_scheduled = False
        self._immediate_rerender_requested = False
        try:
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

            # Guard: a frame callback or RAF callback may have destroyed the renderer.
            if self._ptr is None:
                return

            if self._root:
                try:
                    self._update_layout(self._root, delta_time)
                except Exception:
                    _log.exception("Error updating layout")
                    # Force a full layout recomputation on the next frame so
                    # yoga node state left dirty by the failed pass is reset.
                    self._force_next_render = True
                    if self._root is not None:
                        self._root.mark_dirty()

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
                    # Ensure yoga state is re-evaluated on the next frame.
                    self._force_next_render = True
                    if self._root is not None:
                        self._root.mark_dirty()

            # Run post-processing functions after render
            for fn in self._post_process_fns:
                fn(buffer)
                # Guard: post-process may have destroyed the renderer.
                if self._ptr is None:
                    return

            # Guard: if the renderer was destroyed during one of the callbacks
            # above, skip the native render/flush calls to avoid use-after-free.
            if self._ptr is None:
                return

            # Force a full repaint (bypass diff) after resize or on first frame.
            force = self._force_next_render
            if force:
                self._force_next_render = False
            self.render(force=force)

            # Guard again: destroy() may have been called inside post_process or
            # root.render(), and render() above would then use a live ptr, so we
            # only proceed with cursor/graphics if still alive.
            if self._ptr is None:
                return

            # Clear Kitty graphics that were active last frame but not this one.
            self._clear_stale_graphics()

            # Position (or hide) the terminal cursor after the frame is flushed.
            self._apply_cursor()

            # Recheck hover state: if the pointer hasn't moved but the tree
            # changed (e.g. scroll offset changed), fire synthetic over/out.
            # Recheck hover state when hit-grid
            # is dirty after render.  The guard is _has_pointer (not
            # _mouse_enabled) so that hover recheck fires even when mouse
            # tracking is auto-disabled.
            self._recheck_hover_state()
        finally:
            self._rendering = False
            self._resolve_idle_if_needed()

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
            self._root._children_tuple = None
            reconcile(self._root, old_children, new_children)
            t2 = _time.perf_counter_ns()
            _log.debug(
                "rebuild: component_fn=%.2fms reconcile=%.2fms total=%.2fms",
                (t1 - t0) / 1e6,
                (t2 - t1) / 1e6,
                (t2 - t0) / 1e6,
            )
        except Exception:
            _log.exception("Error rebuilding component tree, restoring previous")
            self._root._children = old_children
            self._root._children_tuple = None
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

            yoga_layout.compute_layout(
                self._root._yoga_node, float(self._width), float(self._height)
            )

            self._apply_yoga_layout_recursive(self._root)

        if hasattr(renderable, "update_layout"):
            renderable.update_layout(delta_time)

        # Recurse into children (snapshot to guard against mid-update mutations)
        for child in list(getattr(renderable, "_children", [])):
            if not getattr(child, "_destroyed", False):
                self._update_layout(child, delta_time)

    def _apply_yoga_layout_recursive(
        self, renderable, offset_x: int = 0, offset_y: int = 0
    ) -> None:
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
        with contextlib.suppress(AttributeError):
            handlers["key"].append(renderable._key_handler)

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
        """Dispatch a mouse event through the render tree before global hooks.

        Implements mouse capture: when a drag begins on a renderable, that
        element receives ALL subsequent drag events directly (skipping tree
        traversal) until the mouse button is released.          This is required for click-and-drag
        operations like text selection to work correctly.

        Also integrates text selection:
        - left-button down on a selectable renderable starts selection
        - drag while selection active updates selection focus
        - up while selection active finishes selection (stops dragging)
        - ctrl+click extends an existing selection
        - right click does NOT start selection
        - click without drag clears selection (unless prevented)
        """
        if self._root is None:
            return

        # --- Split-height coordinate adjustment ---
        # When split-height is active, ignore events above the render area
        # and offset y so that y=0 corresponds to the top of the rendered region.
        if self._split_height > 0:
            if event.y < self._render_offset:
                return
            event.y -= self._render_offset

        # Track latest pointer position and modifiers for hover recheck after render.
        self._latest_pointer["x"] = event.x
        self._latest_pointer["y"] = event.y
        self._has_pointer = True
        self._last_pointer_modifiers = {
            "shift": getattr(event, "shift", False),
            "alt": getattr(event, "alt", False),
            "ctrl": getattr(event, "ctrl", False),
        }

        # Console overlay intercept — if visible, check if the event falls
        # inside the console bounds.  If the console handles it, stop here.
        if self._use_console and self._console.visible:
            cb = self._console.bounds
            if (
                cb.x <= event.x < cb.x + cb.width
                and cb.y <= event.y < cb.y + cb.height
                and self._console.handle_mouse(event)
            ):
                return

        if event.type == "scroll":
            self._dispatch_scroll_event(event)
            return

        captured = self._captured_renderable

        if event.type in ("down", "drag", "up"):
            _log.debug(
                "mouse dispatch type=%s x=%s y=%s button=%s captured=%s",
                event.type,
                event.x,
                event.y,
                getattr(event, "button", None),
                type(captured).__name__ if captured is not None else None,
            )

        # --- Selection handling (before normal capture) ---
        # Find the hit target for selection checks.
        hit_renderable = self._find_deepest_hit(self._root, event.x, event.y)
        is_ctrl = getattr(event, "ctrl", False)
        button = getattr(event, "button", 0)

        # 1. left-button down: start selection if target is selectable
        if (
            event.type == "down"
            and button == 0  # left button only
            and not (self._current_selection is not None and self._current_selection.is_dragging)
            and not is_ctrl
        ):
            can_start = bool(
                hit_renderable is not None
                and getattr(hit_renderable, "selectable", False)
                and not getattr(hit_renderable, "_destroyed", False)
                and hit_renderable.should_start_selection(event.x, event.y)
            )
            if can_start:
                self.start_selection(hit_renderable, event.x, event.y)
                # Still dispatch the mouse-down event to the renderable
                self._dispatch_mouse_to_tree(self._root, event)
                return

        # 2. drag while selection isDragging: update selection focus
        if (
            event.type == "drag"
            and self._current_selection is not None
            and self._current_selection.is_dragging
        ):
            self.update_selection(hit_renderable, event.x, event.y)

            # Dispatch drag event with isDragging=True to the hit renderable
            if hit_renderable is not None:
                from .events import MouseEvent

                drag_ev = MouseEvent(
                    type="drag",
                    x=event.x,
                    y=event.y,
                    button=button,
                    is_dragging=True,
                    shift=getattr(event, "shift", False),
                    ctrl=is_ctrl,
                    alt=getattr(event, "alt", False),
                )
                drag_ev.target = hit_renderable
                handler = getattr(hit_renderable, "_on_mouse_drag", None)
                if handler is not None:
                    handler(drag_ev)
            return

        # 3. up while selection isDragging: dispatch up with isDragging, then finish
        if (
            event.type == "up"
            and self._current_selection is not None
            and self._current_selection.is_dragging
        ):
            if hit_renderable is not None:
                from .events import MouseEvent

                up_ev = MouseEvent(
                    type="up",
                    x=event.x,
                    y=event.y,
                    button=button,
                    is_dragging=True,
                    shift=getattr(event, "shift", False),
                    ctrl=is_ctrl,
                    alt=getattr(event, "alt", False),
                )
                up_ev.target = hit_renderable
                handler = getattr(hit_renderable, "_on_mouse_up", None)
                if handler is not None:
                    handler(up_ev)
            self._finish_selection()
            return

        # 4. ctrl+click with existing selection: extend selection
        if event.type == "down" and button == 0 and self._current_selection is not None and is_ctrl:
            self._current_selection.is_dragging = True
            self.update_selection(hit_renderable, event.x, event.y)
            return

        # --- Normal capture-based dispatch ---

        # Route drag/move events directly to captured element (skip tree walk).
        if captured is not None and event.type not in ("up", "down"):
            handler = getattr(captured, "_on_mouse_drag", None)
            if handler is not None:
                event.target = captured
                handler(event)
                _log.debug("mouse capture→drag handler fired on %s", type(captured).__name__)
            else:
                _log.debug(
                    "mouse capture active but no _on_mouse_drag on %s", type(captured).__name__
                )
            return

        # On mouse-up: send drag-end + up to captured element, then release.
        if captured is not None and event.type == "up":
            drag_end_handler = getattr(captured, "_on_mouse_drag_end", None)
            if drag_end_handler is not None:
                event.target = captured
                drag_end_handler(event)
            up_handler = getattr(captured, "_on_mouse_up", None)
            if up_handler is not None:
                event.target = captured
                up_handler(event)
            self._captured_renderable = None
            _log.debug("mouse capture released on up")
            return

        # Track drag state so that auto-focus is suppressed during drag operations.
        if event.type == "down":
            self._is_dragging = False
        elif event.type == "drag":
            self._is_dragging = True
        elif event.type == "up":
            self._is_dragging = False

        # Normal tree dispatch for down/other events.
        self._dispatch_mouse_to_tree(self._root, event)

        target = getattr(event, "target", None)
        _log.debug(
            "mouse tree dispatch result type=%s target=%s has_drag=%s",
            event.type,
            type(target).__name__ if target is not None else None,
            getattr(target, "_on_mouse_drag", None) is not None if target else False,
        )

        # Hover tracking: fire _on_mouse_out / _on_mouse_over when the
        # element under the pointer changes.
        if event.type in ("move", "drag"):
            hit = self._find_deepest_hit(self._root, event.x, event.y)
            last_over = self._last_over_renderable
            if hit is not last_over:
                if last_over is not None and not getattr(last_over, "_destroyed", False):
                    out_handler = getattr(last_over, "_on_mouse_out", None)
                    if out_handler is not None:
                        from .events import MouseEvent

                        out_ev = MouseEvent(type="out", x=event.x, y=event.y)
                        out_ev.target = last_over
                        out_handler(out_ev)
                self._last_over_renderable = hit
                if hit is not None:
                    over_handler = getattr(hit, "_on_mouse_over", None)
                    if over_handler is not None:
                        from .events import MouseEvent

                        over_ev = MouseEvent(type="over", x=event.x, y=event.y)
                        over_ev.target = hit
                        over_handler(over_ev)

        # Auto-focus: on left-button mousedown, find the deepest element under
        # the click position and walk up to its nearest focusable ancestor.
        # preventDefault() on the mousedown event (or any ancestor's handler)
        # blocks auto-focus, as does a button other than left (button 0).
        if (
            event.type == "down"
            and getattr(event, "button", 0) == 0  # left button only
            and not event.default_prevented
            and self._auto_focus
        ):
            # Use the event's target if a handler fired and set it;
            # otherwise fall back to finding the deepest hit element.
            hit = target
            if hit is None:
                hit = self._find_deepest_hit(self._root, event.x, event.y)
            focusable = self._find_focusable_ancestor(hit)
            if focusable is not None:
                self._do_auto_focus(focusable)

        # After dispatching a drag event, capture the target element so
        # subsequent drags bypass the tree walk.
        if event.type == "drag" and target is not None:
            self._captured_renderable = target
            _log.debug("mouse captured %s on drag", type(target).__name__)
        # On mouse-down, capture the target for drag tracking.
        elif event.type == "down" and target is not None:
            handler = getattr(target, "_on_mouse_drag", None)
            if handler is not None:
                self._captured_renderable = target
                _log.debug("mouse captured %s on down (has drag handler)", type(target).__name__)

        # After normal dispatch: if down event and defaultPrevented is not set
        # and there is a current selection, clear it.
        if (
            event.type == "down"
            and not event.default_prevented
            and self._current_selection is not None
        ):
            self.clear_selection()

    def _dispatch_scroll_event(self, event) -> None:
        """Route wheel input through the render tree with parent propagation.

        The deepest
        renderable under the pointer receives the event first, then the
        event bubbles up through parents until something calls
        ``stop_propagation()`` (typically a ScrollBox).

        When nothing in the tree handles the event, falls back to the
        currently focused renderable.
        """
        if self._root is None:
            return

        # Dispatch through the normal tree (propagates from deepest to root).
        self._dispatch_mouse_to_tree(self._root, event)

        if event.propagation_stopped:
            return

        # Fall back to the focused renderable when nothing handled it.
        if self._focused_renderable is not None:
            focused = self._focused_renderable
            if not getattr(focused, "_destroyed", False):
                scroll_handler = getattr(focused, "_on_mouse_scroll", None)
                handle_scroll = getattr(focused, "handle_scroll_event", None)
                if scroll_handler is not None:
                    event.target = focused
                    scroll_handler(event)
                elif handle_scroll is not None:
                    event.target = focused
                    handle_scroll(event)

    # ---- Selection API ----

    @property
    def has_selection(self) -> bool:
        """Return True if there is an active selection."""
        return self._current_selection is not None

    def get_selection(self):
        """Return the current Selection object, or None."""
        return self._current_selection

    def start_selection(self, renderable, x: int, y: int) -> None:
        """Start a new selection at the given coordinates.

        Used by both mouse and keyboard selection.
        """
        if not getattr(renderable, "selectable", False):
            return

        self.clear_selection()

        from .selection import Selection

        parent = getattr(renderable, "_parent", None)
        self._selection_containers.append(parent if parent is not None else self._root)
        self._current_selection = Selection(renderable, {"x": x, "y": y}, {"x": x, "y": y})
        self._current_selection.is_start = True

        self._notify_selectables_of_selection_change()

    def update_selection(
        self, current_renderable, x: int, y: int, *, finish_dragging: bool = False
    ) -> None:
        """Update the focus of the current selection."""
        if self._current_selection is None:
            return

        self._current_selection.is_start = False
        self._current_selection.focus = {"x": x, "y": y}

        if finish_dragging:
            self._current_selection.is_dragging = False

        # Update selection containers based on where the cursor is now
        if self._selection_containers:
            current_container = self._selection_containers[-1]

            if current_renderable is None or not self._is_within_container(
                current_renderable, current_container
            ):
                parent_container = getattr(current_container, "_parent", None)
                if parent_container is None:
                    parent_container = self._root
                self._selection_containers.append(parent_container)
            elif current_renderable is not None and len(self._selection_containers) > 1:
                container_index = -1
                try:
                    container_index = self._selection_containers.index(current_renderable)
                except ValueError:
                    parent = getattr(current_renderable, "_parent", None)
                    if parent is None:
                        parent = self._root
                    with contextlib.suppress(ValueError):
                        container_index = self._selection_containers.index(parent)

                if container_index != -1 and container_index < len(self._selection_containers) - 1:
                    self._selection_containers = self._selection_containers[: container_index + 1]

        self._notify_selectables_of_selection_change()

    def clear_selection(self) -> None:
        """Clear the current selection."""
        if self._current_selection is not None:
            for renderable in self._current_selection.touched_renderables:
                if getattr(renderable, "selectable", False) and not getattr(
                    renderable, "_destroyed", False
                ):
                    renderable.on_selection_changed(None)
            self._current_selection = None
        self._selection_containers = []

    def _finish_selection(self) -> None:
        """Finish the current selection (stop dragging)."""
        if self._current_selection is not None:
            self._current_selection.is_dragging = False
            self._notify_selectables_of_selection_change()

    def _is_within_container(self, renderable, container) -> bool:
        """Check if renderable is a descendant of container."""
        current = renderable
        while current is not None:
            if current is container:
                return True
            current = getattr(current, "_parent", None)
        return False

    def _notify_selectables_of_selection_change(self) -> None:
        """Walk the tree and notify selectable renderables of selection changes."""
        selected_renderables: list = []
        touched_renderables: list = []
        current_container = (
            self._selection_containers[-1] if self._selection_containers else self._root
        )

        if self._current_selection is not None and current_container is not None:
            self._walk_selectable_renderables(
                current_container,
                self._current_selection.bounds,
                selected_renderables,
                touched_renderables,
            )

            # Notify previously-touched renderables that are no longer touched
            for renderable in self._current_selection.touched_renderables:
                if renderable not in touched_renderables and not getattr(
                    renderable, "_destroyed", False
                ):
                    renderable.on_selection_changed(None)

            self._current_selection.update_selected_renderables(selected_renderables)
            self._current_selection.update_touched_renderables(touched_renderables)

    def _walk_selectable_renderables(
        self,
        container,
        selection_bounds: dict,
        selected_renderables: list,
        touched_renderables: list,
    ) -> None:
        """Walk the tree within container and check selectable renderables against bounds."""
        try:
            children = list(container.get_children())
        except AttributeError:
            return

        for child in children:
            # Check if child overlaps with selection bounds
            cx = getattr(child, "_x", 0)
            cy = getattr(child, "_y", 0)
            cw = int(getattr(child, "_layout_width", 0) or 0)
            ch = int(getattr(child, "_layout_height", 0) or 0)

            sx = selection_bounds["x"]
            sy = selection_bounds["y"]
            sw = selection_bounds["width"]
            sh = selection_bounds["height"]

            # Check overlap
            if cx + cw <= sx or cx >= sx + sw or cy + ch <= sy or cy >= sy + sh:
                # No overlap — but still walk children
                if getattr(child, "get_children_count", lambda: 0)() > 0:
                    self._walk_selectable_renderables(
                        child, selection_bounds, selected_renderables, touched_renderables
                    )
                continue

            if getattr(child, "selectable", False):
                has_sel = child.on_selection_changed(self._current_selection)
                if has_sel:
                    selected_renderables.append(child)
                touched_renderables.append(child)

            if getattr(child, "get_children_count", lambda: 0)() > 0:
                self._walk_selectable_renderables(
                    child, selection_bounds, selected_renderables, touched_renderables
                )

    def request_selection_update(self) -> None:
        """Request a selection update using the latest pointer position."""
        if self._current_selection is not None and self._current_selection.is_dragging:
            px = self._latest_pointer["x"]
            py = self._latest_pointer["y"]
            hit = self._find_deepest_hit(self._root, px, py)
            self.update_selection(hit, px, py)

    def _recheck_hover_state(self) -> None:
        """Recheck hover state after the hit-grid may have changed.

        Called after render when the pointer is tracked.  Fires synthetic
        ``_on_mouse_out`` / ``_on_mouse_over`` events when the element
        under the cursor has changed (e.g. because a ScrollBox scrolled
        and different content is now under the stationary pointer).

        Fires synthetic over/out when the element under the cursor has changed.
        """
        if self.is_destroyed or not self._has_pointer:
            return
        # Skip recheck while a renderable is captured (drag in progress).
        if self._captured_renderable is not None:
            return

        px = self._latest_pointer["x"]
        py = self._latest_pointer["y"]
        hit = self._find_deepest_hit(self._root, px, py)
        last_over = self._last_over_renderable

        # Compare by identity — same renderable means no change.
        if hit is last_over:
            return

        from .events import MouseEvent

        # Fire out on old element.
        if last_over is not None and not getattr(last_over, "_destroyed", False):
            out_handler = getattr(last_over, "_on_mouse_out", None)
            if out_handler is not None:
                out_ev = MouseEvent(
                    type="out",
                    x=px,
                    y=py,
                    button=0,
                    shift=self._last_pointer_modifiers.get("shift", False),
                    alt=self._last_pointer_modifiers.get("alt", False),
                    ctrl=self._last_pointer_modifiers.get("ctrl", False),
                )
                out_ev.target = last_over
                out_handler(out_ev)

        self._last_over_renderable = hit

        # Fire over on new element.
        if hit is not None:
            over_handler = getattr(hit, "_on_mouse_over", None)
            if over_handler is not None:
                over_ev = MouseEvent(
                    type="over",
                    x=px,
                    y=py,
                    button=0,
                    shift=self._last_pointer_modifiers.get("shift", False),
                    alt=self._last_pointer_modifiers.get("alt", False),
                    ctrl=self._last_pointer_modifiers.get("ctrl", False),
                )
                over_ev.target = hit
                over_handler(over_ev)

    def _find_deepest_hit(
        self,
        renderable,
        x: int,
        y: int,
        scroll_adjust_x: int = 0,
        scroll_adjust_y: int = 0,
    ) -> Any:
        """Return the deepest renderable in the tree whose bounds contain (x, y).

        *scroll_adjust_x/y* accumulate scroll offsets from ancestor
        ScrollBoxes so that children are checked in content-space
        coordinates (matching _dispatch_mouse_to_tree).

        Also respects ``overflow == "hidden"`` by clipping hits to the
        renderable's layout bounds.
        """
        if renderable is None:
            return None

        check_x = x + scroll_adjust_x
        check_y = y + scroll_adjust_y

        contains_point = getattr(renderable, "contains_point", None)
        inside = True if contains_point is None else contains_point(check_x, check_y)

        if not inside:
            return None

        # If overflow is hidden, further clip to this renderable's bounds
        # using *screen* coordinates (the original x/y before scroll adjust).
        overflow = getattr(renderable, "_overflow", "visible")
        if overflow == "hidden":
            rx = getattr(renderable, "_x", 0)
            ry = getattr(renderable, "_y", 0)
            rw = int(getattr(renderable, "_layout_width", 0) or 0)
            rh = int(getattr(renderable, "_layout_height", 0) or 0)
            if not (rx <= x < rx + rw and ry <= y < ry + rh):
                return None

        # Accumulate scroll offset for children.
        child_sx = scroll_adjust_x
        child_sy = scroll_adjust_y
        if getattr(renderable, "_scroll_y", False):
            fn = getattr(renderable, "_scroll_offset_y_fn", None)
            child_sy += int(fn()) if fn else int(getattr(renderable, "_scroll_offset_y", 0))
        if getattr(renderable, "_scroll_x", False):
            child_sx += int(getattr(renderable, "_scroll_offset_x", 0))

        # Check children first (deepest wins — children are "in front of" parent).
        try:
            children = list(renderable.get_children())
        except AttributeError:
            children = []

        # Sort by z_index so higher z renders last / hits first
        def _z(c):
            return getattr(c, "_z_index", 0)

        for child in sorted(children, key=_z, reverse=True):
            hit = self._find_deepest_hit(child, x, y, child_sx, child_sy)
            if hit is not None:
                return hit

        # This renderable contains the point.
        return renderable

    def hit_test(self, x: int, y: int) -> int:
        """Return the ``num`` of the deepest renderable at screen *(x, y)*.

        Returns 0 when nothing is hit (empty space).

        Walks the render tree via ``_find_deepest_hit`` to find the
        deepest renderable at the given coordinates.

        The root renderable is excluded (returns 0) because it is a
        layout container only and does not draw
        pixels — the root is a layout container only.
        """
        hit = self._find_deepest_hit(self._root, x, y)
        if hit is None or hit is self._root:
            return 0
        return hit._num

    def _find_focusable_ancestor(self, renderable) -> Any:
        """Walk up the tree from *renderable* to find the nearest focusable ancestor.

        Returns the focusable renderable, or None if no focusable element is found.
        Walks up the tree to find the nearest focusable ancestor.
        """
        node = renderable
        while node is not None:
            if getattr(node, "_focusable", False):
                return node
            node = getattr(node, "_parent", None)
        return None

    def _do_auto_focus(self, renderable) -> None:
        """Give focus to *renderable*, blurring any previously focused element.

        Only one element can be focused at a time.
        """
        if self._focused_renderable is renderable:
            return
        # Blur previous
        if self._focused_renderable is not None:
            with contextlib.suppress(Exception):
                self._focused_renderable.blur()
        self._focused_renderable = renderable
        with contextlib.suppress(Exception):
            renderable.focus()

    def _find_scroll_target(
        self, renderable, x: int, y: int, scroll_adjust_x: int = 0, scroll_adjust_y: int = 0
    ):
        """Return the deepest registered scroll target under *(x, y)*."""
        try:
            children = list(renderable.get_children())
        except AttributeError:
            children = []

        # Accumulate scroll offset for children (same as _dispatch_mouse_to_tree)
        child_sx = scroll_adjust_x
        child_sy = scroll_adjust_y
        if getattr(renderable, "_scroll_y", False):
            fn = getattr(renderable, "_scroll_offset_y_fn", None)
            child_sy += int(fn()) if fn else int(getattr(renderable, "_scroll_offset_y", 0))
        if getattr(renderable, "_scroll_x", False):
            child_sx += int(getattr(renderable, "_scroll_offset_x", 0))

        for child in reversed(children):
            found = self._find_scroll_target(child, x, y, child_sx, child_sy)
            if found is not None:
                return found

        check_x = x + scroll_adjust_x
        check_y = y + scroll_adjust_y
        contains_point = getattr(renderable, "contains_point", None)
        inside = True if contains_point is None else contains_point(check_x, check_y)

        if inside and getattr(renderable, "_is_scroll_target", False):
            return renderable
        return None

    def _dispatch_mouse_to_tree(
        self, renderable, event, scroll_adjust_x: int = 0, scroll_adjust_y: int = 0
    ) -> None:
        """Walk children front-to-back and dispatch to the deepest hit target.

        *scroll_adjust_x/y* accumulate scroll offsets from ancestor ScrollBoxes.
        Children inside a ScrollBox have layout coordinates in content space
        (not screen space), so we add the parent's scroll offset to the mouse
        coordinates when checking ``contains_point``.  Children inside
        a ScrollBox use content-space coordinates (parent scroll offset
        is added to mouse coordinates).
        """
        if event.propagation_stopped:
            return

        check_x = event.x + scroll_adjust_x
        check_y = event.y + scroll_adjust_y

        contains_point = getattr(renderable, "contains_point", None)
        inside = True if contains_point is None else contains_point(check_x, check_y)

        try:
            children = list(renderable.get_children())
        except AttributeError:
            children = []

        # If this renderable is a scroll container, accumulate its scroll
        # offset for child hit-testing.  Uses duck-typing to avoid imports.
        child_scroll_x = scroll_adjust_x
        child_scroll_y = scroll_adjust_y
        if getattr(renderable, "_scroll_y", False):
            fn = getattr(renderable, "_scroll_offset_y_fn", None)
            child_scroll_y += int(fn()) if fn else int(getattr(renderable, "_scroll_offset_y", 0))
        if getattr(renderable, "_scroll_x", False):
            child_scroll_x += int(getattr(renderable, "_scroll_offset_x", 0))

        for child in reversed(children):
            child_check_x = event.x + child_scroll_x
            child_check_y = event.y + child_scroll_y
            child_contains = getattr(child, "contains_point", None)
            if child_contains is not None and not child_contains(child_check_x, child_check_y):
                continue
            self._dispatch_mouse_to_tree(child, event, child_scroll_x, child_scroll_y)
            if event.propagation_stopped:
                return

        if not inside:
            return

        attr = _MOUSE_HANDLER_MAP.get(event.type)
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
        """Set cursor style using DECSCUSR escape codes.

        Blinking variants by default:
          ``"block"`` → 1, ``"underline"`` → 3, ``"bar"`` → 5
        Steady variants:
          ``"steady_block"`` → 2, ``"steady_underline"`` → 4, ``"steady_bar"`` → 6
        """
        style_map = {
            "block": 1,
            "underline": 3,
            "bar": 5,
            "steady_block": 2,
            "steady_underline": 4,
            "steady_bar": 6,
        }
        code = style_map.get(style, 1)
        if self._cursor_style == style:
            return
        self._cursor_style = style
        try:
            import sys

            sys.stdout.write(f"\x1b[{code} q")
            sys.stdout.flush()
        except Exception:
            pass

    def set_cursor_color(self, color: str) -> None:
        """Set cursor color (hex string).  Cached — skips write if unchanged."""
        if self._cursor_color == color:
            return
        self._cursor_color = color
        try:
            import sys

            sys.stdout.write(f"\x1b]12;{color}\x07")
            sys.stdout.flush()
        except Exception:
            pass

    def set_mouse_pointer(self, style: str) -> None:
        """Set the OS-level mouse pointer (cursor) style.

        Valid *style* values: ``"default"``, ``"pointer"``, ``"text"``,
        ``"crosshair"``, ``"move"``, ``"not-allowed"``.

        In testing mode this only updates ``_current_mouse_pointer_style``
        (no terminal escape is emitted).  In live mode, the style is also
        forwarded to the native renderer.
        """
        self._current_mouse_pointer_style = style

    def _reset_cursor_color(self) -> None:
        """Reset cursor color to terminal default via OSC 112."""
        self._cursor_color = None
        try:
            import sys

            sys.stdout.write("\x1b]112\x07")
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

    # -- Palette detection ------------------

    @property
    def palette_detection_status(self) -> str:
        """Return the current palette detection status.

        Returns one of ``"idle"``, ``"detecting"``, or ``"cached"``.
        """
        if self._cached_palette is not None:
            return "cached"
        if self._palette_detection_promise is not None:
            return "detecting"
        return "idle"

    def clear_palette_cache(self) -> None:
        """Invalidate the cached palette so the next ``get_palette()`` re-detects."""
        self._cached_palette = None

    async def get_palette(
        self,
        timeout: float = 5000,
        size: int = 16,
        **kwargs,
    ) -> Any:
        """Detect the terminal's colour palette.

        Args:
            timeout: Timeout in milliseconds.
            size: Number of indexed colours to query (default 16).

        Returns:
            A :class:`~opentui.palette.TerminalColors` object.

        Raises:
            RuntimeError: If the renderer is suspended.
        """
        # Accept keyword-style options dict
        if kwargs:
            timeout = kwargs.get("timeout", timeout)
            size = kwargs.get("size", size)

        if self._control_state == RendererControlState.EXPLICIT_SUSPENDED:
            raise RuntimeError("Cannot detect palette while renderer is suspended")

        requested_size = size

        # Invalidate cache if the size changed
        if self._cached_palette is not None and len(self._cached_palette.palette) != requested_size:
            self._cached_palette = None

        # Return cached result immediately
        if self._cached_palette is not None:
            return self._cached_palette

        # Share an in-flight detection promise
        if self._palette_detection_promise is not None:
            return await self._palette_detection_promise

        # Create detector lazily (singleton)
        if self._palette_detector is None:
            from .palette import TerminalPaletteDetector

            # In test mode, use mock streams if no real stdin/stdout
            if self._config.testing:
                from .palette import MockPaletteStdin, MockPaletteStdout

                stdin = MockPaletteStdin(is_tty=False)
                stdout = MockPaletteStdout(is_tty=False)
                self._palette_detector = TerminalPaletteDetector(stdin, stdout)
            else:
                import sys

                self._palette_detector = TerminalPaletteDetector(
                    sys.stdin,
                    sys.stdout,
                    write_fn=lambda data: self.write_out(
                        data.encode() if isinstance(data, str) else data
                    ),
                )

        async def _do_detect() -> Any:
            result = await self._palette_detector.detect(timeout=timeout, size=requested_size)
            self._cached_palette = result
            self._palette_detection_promise = None
            return result

        self._palette_detection_promise = asyncio.ensure_future(_do_detect())
        return await self._palette_detection_promise

    def _restore_terminal_modes(self) -> None:
        """Re-enable terminal modes after a focus-in event.

        When the terminal loses focus and regains it, some terminals
        (particularly tmux, screen) may drop protocol state.  This
        re-sends the kitty keyboard flags, mouse tracking, and
        bracketed paste to ensure the application continues working.
        """
        if self._config.testing:
            return
        try:
            import sys as _sys

            buf = ""
            # Re-enable kitty keyboard protocol
            if self._config.kitty_keyboard_flags:
                self.enable_keyboard(self._config.kitty_keyboard_flags)
            # Re-enable mouse tracking
            if self._mouse_enabled:
                self.enable_mouse()
            # Re-enable bracketed paste mode
            buf += "\x1b[?2004h"
            _sys.stdout.write(buf)
            _sys.stdout.flush()
        except Exception:
            _log.debug("Failed to restore terminal modes on focus", exc_info=True)

    # -- Control state machine ----------------

    @property
    def control_state(self) -> RendererControlState:
        """Current control state of the renderer."""
        return self._control_state

    @property
    def is_running(self) -> bool:
        """Whether the renderer is currently running (alias for _running)."""
        return self._running

    def _is_idle_now(self) -> bool:
        """Return True when the renderer is completely idle."""
        return (
            not self._running
            and not self._rendering
            and not self._update_scheduled
            and not self._immediate_rerender_requested
        )

    def _resolve_idle_if_needed(self) -> None:
        """Resolve any pending idle() futures if the renderer is now idle."""
        if not self._is_idle_now():
            return
        futures = self._idle_futures[:]
        self._idle_futures.clear()
        for fut in futures:
            if not fut.done():
                fut.set_result(None)

    async def idle(self) -> None:
        """Return a coroutine that resolves when the renderer becomes idle.

        Resolves immediately if the
        renderer is already idle or destroyed.  Otherwise, returns an
        ``asyncio.Future`` that is resolved when the renderer transitions
        to an idle state (via ``stop()``, ``pause()``, ``dropLive()``,
        or ``destroy()``).
        """
        if self.is_destroyed:
            return
        if self._is_idle_now():
            return
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[None] = loop.create_future()
        self._idle_futures.append(fut)
        await fut

    def _internal_start(self) -> None:
        """Start the render loop (internal helper)."""
        if not self._running and not self.is_destroyed:
            self._running = True

    def _internal_pause(self) -> None:
        """Pause the render loop (internal helper)."""
        self._running = False
        if not self._rendering:
            self._resolve_idle_if_needed()

    def _internal_stop(self) -> None:
        """Stop the render loop (internal helper)."""
        if self._running and not self.is_destroyed:
            self._running = False
            if not self._rendering:
                self._resolve_idle_if_needed()

    def start(self) -> None:
        """Explicitly start the renderer.

        Sets the control state to EXPLICIT_STARTED and starts the
        internal render loop.
        """
        self._control_state = RendererControlState.EXPLICIT_STARTED
        self._internal_start()

    def pause(self) -> None:
        """Explicitly pause the renderer.

        Sets the control state to EXPLICIT_PAUSED and stops the
        internal render loop, resolving any pending ``idle()`` futures.
        """
        self._control_state = RendererControlState.EXPLICIT_PAUSED
        self._internal_pause()

    def stop(self) -> None:
        """Stop the renderer and event loop.

        Sets the control state to EXPLICIT_STOPPED and stops the
        internal render loop, resolving any pending ``idle()`` futures.
        """
        self._control_state = RendererControlState.EXPLICIT_STOPPED
        self._internal_stop()
        if self._event_loop is not None:
            self._event_loop.stop()

    def request_live(self) -> None:
        """Request a live render session (auto-start if idle).

        Each call increments the live request counter.  When the counter
        transitions from 0 to 1 and the renderer is IDLE, the control
        state changes to AUTO_STARTED and the render loop is started.
        """
        self._live_request_counter += 1
        if self._control_state == RendererControlState.IDLE and self._live_request_counter > 0:
            self._control_state = RendererControlState.AUTO_STARTED
            self._internal_start()

    def drop_live(self) -> None:
        """Drop a live render session (auto-stop when counter reaches 0).

        Each call decrements the live request counter.  When the counter
        reaches 0 and the renderer is AUTO_STARTED, the control state
        returns to IDLE and the render loop is paused.
        """
        self._live_request_counter = max(0, self._live_request_counter - 1)
        if (
            self._control_state == RendererControlState.AUTO_STARTED
            and self._live_request_counter == 0
        ):
            self._control_state = RendererControlState.IDLE
            self._internal_pause()

    @property
    def is_destroyed(self) -> bool:
        """Whether this renderer has been destroyed."""
        return self._ptr is None

    def destroy(self) -> None:
        """Destroy the renderer and free resources."""
        # Reset mouse pointer style to default before teardown.
        self._current_mouse_pointer_style = "default"
        self._last_over_renderable = None
        # Clean up palette detector
        if self._palette_detector is not None:
            self._palette_detector.cleanup()
            self._palette_detector = None
        self._palette_detection_promise = None
        self._cached_palette = None
        if self._ptr:
            self._native.renderer.destroy_renderer(self._ptr)
            self._ptr = None
        self._running = False
        # Resolve any pending idle() futures unconditionally on destroy.
        futures = self._idle_futures[:]
        self._idle_futures.clear()
        for fut in futures:
            if not fut.done():
                fut.set_result(None)


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
            render_fn = getattr(child, "render", None)
            if render_fn is not None:
                render_fn(buffer, delta_time)


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


# ---------------------------------------------------------------------------
# Kitty keyboard protocol flag constants
# See: https://sw.kovidgoyal.net/kitty/keyboard-protocol/#progressive-enhancement
# ---------------------------------------------------------------------------

KITTY_FLAG_DISAMBIGUATE = 0b1  # bit 0: disambiguated escape codes
KITTY_FLAG_EVENT_TYPES = 0b10  # bit 1: press/repeat/release event types
KITTY_FLAG_ALTERNATE_KEYS = 0b100  # bit 2: alternate keys (numpad, shifted)
KITTY_FLAG_ALL_KEYS_AS_ESCAPES = 0b1000  # bit 3: all keys as escape codes
KITTY_FLAG_REPORT_TEXT = 0b10000  # bit 4: associated text with key events


def build_kitty_keyboard_flags(options: dict[str, bool] | None = None) -> int:
    """Build kitty keyboard protocol flags bitmask from options dict.

    By default, ``disambiguate`` and ``alternate_keys`` are True.
    Optional flags (``events``, ``all_keys_as_escapes``, ``report_text``)
    default to False.

    Returns 0 for *None* input (protocol disabled).
    """
    if options is None:
        return 0
    flags = 0
    if options.get("disambiguate", True):
        flags |= KITTY_FLAG_DISAMBIGUATE
    if options.get("alternateKeys", True):
        flags |= KITTY_FLAG_ALTERNATE_KEYS
    if options.get("events", False):
        flags |= KITTY_FLAG_EVENT_TYPES
    if options.get("allKeysAsEscapes", False):
        flags |= KITTY_FLAG_ALL_KEYS_AS_ESCAPES
    if options.get("reportText", False):
        flags |= KITTY_FLAG_REPORT_TEXT
    return flags


__all__ = [
    "CliRenderer",
    "CliRendererConfig",
    "RendererControlState",
    "TerminalCapabilities",
    "Buffer",
    "RootRenderable",
    "create_cli_renderer",
    "build_kitty_keyboard_flags",
    "KITTY_FLAG_DISAMBIGUATE",
    "KITTY_FLAG_EVENT_TYPES",
    "KITTY_FLAG_ALTERNATE_KEYS",
    "KITTY_FLAG_ALL_KEYS_AS_ESCAPES",
    "KITTY_FLAG_REPORT_TEXT",
]
