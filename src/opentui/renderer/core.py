"""Terminal rendering loop — layout, painting, input dispatch, and native acceleration."""

from __future__ import annotations

import asyncio
import enum
import logging
import shutil
import time as _time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .buffer import Buffer, FrameTimingBuckets

_log = logging.getLogger(__name__)

import contextlib

from .. import diagnostics as _diag
from .. import hooks
from .. import structs as s
from ..components.base import BaseRenderable
from ..console import TerminalConsole
from ..ffi import get_native, is_native_available
from .layout import (
    clear_all_dirty,
    clear_handled_layout_dirty_ancestors,
    collect_local_layout_subtree,
    count_tree_custom_update_layout,
    has_custom_update_layout,
    supports_common_tree_strategy,
)
from .mouse import MouseHandlingMixin
from .native import (
    _COMMON_RENDER_CACHE,
    _CURSOR_STYLE_MAP,
    _CURSOR_STYLE_MAP_STEADY,
    _NATIVE_LAYOUT_CACHE,
    _NOT_LOADED,
    LayoutRepaintFact,
    _ensure_common_render_loaded,
    _has_instance_render_override,
    _load_native_layout_apply,
)
from .repaint import (
    apply_yoga_layout_native,
    dedupe_common_roots,
    dedupe_common_roots_from_facts,
    layout_repaint_rect_from_fact,
    node_bounds_rect,
    promote_layout_repaint_root_from_facts,
)


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


class RendererControlState(enum.Enum):
    """Renderer control state for the render loop lifecycle."""

    IDLE = "idle"
    AUTO_STARTED = "auto_started"
    EXPLICIT_STARTED = "explicit_started"
    EXPLICIT_PAUSED = "explicit_paused"
    EXPLICIT_SUSPENDED = "explicit_suspended"
    EXPLICIT_STOPPED = "explicit_stopped"


# Software cursor blink interval in milliseconds (~matches typical OS blink rate).
_CURSOR_BLINK_MS = 530


class CliRenderer(MouseHandlingMixin):
    """CLI renderer - wraps the native OpenTUI renderer using nanobind."""

    def __init__(self, ptr: Any, config: CliRendererConfig, native: Any):
        self._ptr = ptr
        self._config = config
        self._native = native
        self._running = False
        self._control_state: RendererControlState = RendererControlState.IDLE
        self._rendering: bool = False
        self._update_scheduled: bool = False
        self._immediate_rerender_requested: bool = False
        self._live_request_counter: int = 0
        self._idle_futures: list[asyncio.Future[None]] = []
        self._root: RootRenderable | None = None
        self._component_fn: Callable | None = None
        self._signal_state: Any = None
        self._last_frame_timings: FrameTimingBuckets = FrameTimingBuckets()
        self._tree_has_custom_update_layout: bool | None = None
        self._tree_custom_update_layout_count: int | None = None
        self._common_tree_cache_root: Any = None
        self._common_tree_cache_valid: bool = False
        self._common_tree_cache_eligible: bool = False
        self._pending_structural_clear_rects: list[tuple[int, int, int, int]] = []
        self._handlers_dirty = True
        self._cached_handlers: dict[str, list[Callable]] = {"key": [], "mouse": [], "paste": []}
        self._auto_focus: bool = config.auto_focus
        self._focused_renderable: Any = None
        self._is_dragging: bool = False
        self._post_process_fns: list[Callable] = []
        self._frame_callbacks: list[Callable] = []
        self._animation_frame_callbacks: dict[int, Callable] = {}
        self._next_animation_id: int = 0
        self._event_loop: Any = None
        self._force_next_render: bool = True  # Force first frame to be a full repaint
        self._clear_color: s.RGBA | None = s.parse_color_opt(config.clear_color)
        self._mouse_enabled: bool = False
        self._mouse_tracking_dirty: bool = True
        self._cached_requires_mouse_tracking: bool = False
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
        graphics = getattr(self._native, "graphics", None)
        self._next_buffer_wrapper = Buffer(None, self._native.buffer, graphics)
        self._current_buffer_wrapper = Buffer(None, self._native.buffer, graphics)
        self._last_pointer_modifiers: dict[str, bool] = {
            "shift": False,
            "alt": False,
            "ctrl": False,
        }
        self._event_listeners: dict[str, list[Callable]] = {}
        self._cached_capabilities: TerminalCapabilities | None = None
        self._palette_detector: Any = None
        self._cached_palette: Any = None
        self._palette_detection_promise: asyncio.Task | asyncio.Future | None = None
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

        if config.use_mouse is not None:
            self._mouse_enabled = config.use_mouse

    def set_clear_color(self, color: s.RGBA | str | None) -> None:
        parsed = s.parse_color_opt(color)
        if parsed != self._clear_color:
            self._clear_color = parsed
            self._force_next_render = True

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def split_height(self) -> int:
        return self._split_height

    @split_height.setter
    def split_height(self, value: int) -> None:
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
        if self._root is None:
            raise RuntimeError("Root not set. Call setup() first.")
        return self._root

    def setup(self) -> None:
        if self._config.testing:
            return
        self._native.renderer.setup_terminal(self._ptr, self._config.use_alternate_screen)
        self._cached_capabilities = None
        try:
            caps = self.capabilities
            self._native.renderer.set_hyperlinks_capability(self._ptr, caps.hyperlinks)
        except Exception:
            _log.debug("Failed to set hyperlinks capability", exc_info=True)

    def suspend(self) -> None:
        self._native.renderer.suspend_renderer(self._ptr)

    def resume(self) -> None:
        self._native.renderer.resume_renderer(self._ptr)

    def clear(self) -> None:
        self._native.renderer.clear_terminal(self._ptr)

    def set_title(self, title: str) -> None:
        self._native.renderer.set_terminal_title(self._ptr, title)

    @property
    def use_mouse(self) -> bool:
        return self._mouse_enabled

    @use_mouse.setter
    def use_mouse(self, value: bool) -> None:
        if value:
            self.enable_mouse()
        else:
            self.disable_mouse()

    def enable_mouse(self, enable_movement: bool = False) -> None:
        if self._config.testing or self._ptr is None:
            self._mouse_enabled = True
            return
        self._native.renderer.enable_mouse(self._ptr, enable_movement)
        self._mouse_enabled = True

    def disable_mouse(self) -> None:
        if self._config.testing or self._ptr is None:
            self._mouse_enabled = False
            return
        self._native.renderer.disable_mouse(self._ptr)
        self._mouse_enabled = False

    def enable_keyboard(self, flags: int = 0) -> None:
        self._native.renderer.enable_kitty_keyboard(self._ptr, flags)

    def disable_keyboard(self) -> None:
        self._native.renderer.disable_kitty_keyboard(self._ptr)

    def set_cursor_position(self, x: int, y: int, visible: bool = True) -> None:
        self._native.renderer.set_cursor_position(self._ptr, x, y, visible)

    def request_cursor(self, x: int, y: int) -> None:
        self._cursor_request = (x, y)

    def request_cursor_style(self, style: str = "block", color: str | None = None) -> None:
        self._cursor_style_request = style
        self._cursor_color_request = color

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

        if self._config.testing:
            if req is not None:
                self.set_cursor_position(req[0] + 1, req[1] + 1, visible=True)
                style = style_req or "block"
                code = _CURSOR_STYLE_MAP.get(style, 1)
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

        # Keep native cursor hidden so render() emits \x1b[?25l
        # (harmless no-op) instead of \x1b[?25h (which kills blink).
        self.set_cursor_position(0, 0, visible=False)

        if req is not None:
            blink_on = int(_time.monotonic() * 1000 / _CURSOR_BLINK_MS) % 2 == 0

            if blink_on:
                col = req[0] + 1
                row = req[1] + 1
                style = style_req or "block"
                # Steady DECSCUSR — shape only; blink handled by our timer.
                code = _CURSOR_STYLE_MAP_STEADY.get(style, 2)
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
        return self._graphics_suppressed

    def suppress_graphics(self) -> None:
        self._graphics_suppressed = True

    def unsuppress_graphics(self) -> None:
        self._graphics_suppressed = False

    def register_frame_graphics(self, graphics_id: int) -> None:
        self._frame_graphics.add(graphics_id)

    def _clear_stale_graphics(self) -> None:
        stale = self._prev_frame_graphics - self._frame_graphics
        if stale:
            import sys as _sys

            from ..image.encoding import _clear_kitty_graphics

            for gid in stale:
                _sys.stdout.buffer.write(_clear_kitty_graphics(gid))
            _sys.stdout.buffer.flush()
        self._prev_frame_graphics = self._frame_graphics
        self._frame_graphics = set()

    def get_cursor_state(self) -> dict:
        return self._native.renderer.get_cursor_state(self._ptr)

    def copy_to_clipboard(self, clipboard_type: int, text: str) -> bool:
        if not self.capabilities.osc52:
            return False
        return self._native.renderer.copy_to_clipboard_osc52(self._ptr, clipboard_type, text)

    def clear_clipboard(self, clipboard_type: int) -> bool:
        if not self.capabilities.osc52:
            return False
        return self._native.renderer.clear_clipboard_osc52(self._ptr, clipboard_type)

    def set_debug_overlay(self, enable: bool, flags: int = 0) -> None:
        self._native.renderer.set_debug_overlay(self._ptr, enable, flags)

    def update_stats(self, fps: float, frame_count: int, avg_frame_time: float) -> None:
        self._native.renderer.update_stats(self._ptr, fps, frame_count, avg_frame_time)

    def write_out(self, data: bytes) -> None:
        self._native.renderer.write_out(self._ptr, data)

    def set_kitty_keyboard_flags(self, flags: int) -> None:
        self._native.renderer.set_kitty_keyboard_flags(self._ptr, flags)

    def get_kitty_keyboard_flags(self) -> int:
        return self._native.renderer.get_kitty_keyboard_flags(self._ptr)

    def set_background_color(self) -> None:
        self._native.renderer.set_background_color(self._ptr)

    def set_render_offset(self, offset: int) -> None:
        self._native.renderer.set_render_offset(self._ptr, offset)

    def query_pixel_resolution(self) -> None:
        self._native.renderer.query_pixel_resolution(self._ptr)

    @property
    def capabilities(self) -> TerminalCapabilities:
        if self._cached_capabilities is None:
            self._cached_capabilities = self.get_capabilities()
        return self._cached_capabilities

    def get_capabilities(self) -> TerminalCapabilities:
        d = self._native.renderer.get_terminal_capabilities(self._ptr)
        d["unicode"] = "unicode" if d.get("unicode", False) else "wcwidth"
        caps = TerminalCapabilities(
            **{
                f: d.get(f, fd.default)
                for f, fd in TerminalCapabilities.__dataclass_fields__.items()
            }
        )
        self._cached_capabilities = caps
        return caps

    def get_next_buffer(self) -> Buffer:
        ptr = self._native.renderer.get_next_buffer(self._ptr)
        return self._next_buffer_wrapper._retarget(ptr)

    def get_current_buffer(self) -> Buffer:
        ptr = self._native.renderer.get_current_buffer(self._ptr)
        return self._current_buffer_wrapper._retarget(ptr)

    def render(self, force: bool = False) -> None:
        self._native.renderer.render(self._ptr, force)

    @property
    def last_frame_timings(self) -> FrameTimingBuckets:
        return self._last_frame_timings

    def resize(self, width: int, height: int) -> None:
        if _diag._enabled & _diag.RESIZE:
            _diag.log_resize(self._width, self._height, width, height)
        self._native.renderer.resize_renderer(self._ptr, width, height)
        self._width = width
        self._height = height
        self._force_next_render = True
        if self._root is not None:
            self._root.mark_dirty()

    def clear_terminal(self) -> None:
        self._native.renderer.clear_terminal(self._ptr)

    def request_render(self) -> None:
        if self._control_state == RendererControlState.EXPLICIT_SUSPENDED:
            return
        if self._running:
            return
        if self._rendering:
            self._immediate_rerender_requested = True
            return
        self._update_scheduled = True

    def on(self, event: str, handler: Callable) -> Callable[[], None]:
        listeners = self._event_listeners.setdefault(event, [])
        listeners.append(handler)

        def _unsub() -> None:
            with contextlib.suppress(ValueError):
                listeners.remove(handler)

        return _unsub

    def emit_event(self, event: str, *args: Any) -> None:
        for handler in list(self._event_listeners.get(event, [])):
            with contextlib.suppress(Exception):
                handler(*args)

    def run(self) -> None:
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

        # Flag 16 provides associated text for CJK IME composition.
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

        from ..input.event_loop import EventLoop

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

        for handler in hooks.get_mouse_handlers():
            input_handler.on_mouse(handler)

        self._refresh_mouse_tracking()

        event_loop.on_frame(self._render_frame)

        try:
            event_loop.run()
        except KeyboardInterrupt:
            if not self._config.exit_on_ctrl_c:
                raise
        finally:
            # Disable kitty keyboard protocol before tearing down the
            # terminal so the shell doesn't receive extended key reports.
            with contextlib.suppress(Exception):
                self.disable_keyboard()

            # Restore terminal default cursor style (DECSCUSR 0) and color
            # (OSC 112) so the shell cursor returns to its normal appearance.
            with contextlib.suppress(Exception):
                import sys as _csys

                _csys.stdout.write("\x1b[0 q\x1b]112\x07")
                _csys.stdout.flush()

            # Native destroy_renderer() performs the real renderer shutdown
            # sequence, including alt-screen exit and terminal state reset.
            # This Python-side cleanup should only drain in-flight stdin data
            # so terminal responses do not leak into the shell.
            # Drain stdin aggressively: catch mouse events, capability
            # responses, and other escape sequences that were in-flight.
            # Without this, leftover bytes leak into the shell after exit.
            # Multiple rounds ensure late-arriving bytes are caught.
            try:
                fd2 = _sys.stdin.fileno()
                for _ in range(3):
                    _time.sleep(0.03)
                    while _sel.select([fd2], [], [], 0.02)[0]:
                        _os.read(fd2, 4096)
            except (OSError, ValueError):
                pass

    def _render_frame(self, delta_time: float) -> None:
        self._rendering = True
        self._update_scheduled = False
        self._immediate_rerender_requested = False
        if hasattr(self._native.buffer, "clear_global_link_pool"):
            self._native.buffer.clear_global_link_pool()
        timings = FrameTimingBuckets()
        frame_start = _time.perf_counter_ns()
        layout_failed = False
        hover_recheck_needed = self._force_next_render or bool(
            self._root
            and (
                getattr(self._root, "_dirty", False)
                or getattr(self._root, "_subtree_dirty", False)
                or getattr(self._root, "_hit_paint_dirty", False)
            )
        )
        try:
            for cb in self._frame_callbacks:
                cb(delta_time)

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
                t_signal = _time.perf_counter_ns()
                notified = self._signal_state._notified
                hover_recheck_needed = True
                self._signal_state.reset()
                _log.debug("signals handled reactively: %d signal(s)", len(notified))
                timings.signal_handling_ns = _time.perf_counter_ns() - t_signal

            self._refresh_mouse_tracking()

            # Guard: a frame callback or RAF callback may have destroyed the renderer.
            if self._ptr is None:
                return

            needs_layout = False
            layout_failed = False
            layout_repaint_facts: list[LayoutRepaintFact] | None = None
            if self._root:
                try:
                    t_layout = _time.perf_counter_ns()
                    (
                        timings.configure_yoga_ns,
                        timings.compute_yoga_ns,
                        timings.apply_layout_ns,
                        timings.update_layout_hooks_ns,
                        needs_layout,
                        layout_repaint_facts,
                    ) = self._update_layout(self._root, delta_time)  # type: ignore[assignment]
                    timings.layout_ns = _time.perf_counter_ns() - t_layout
                except Exception:
                    _log.exception("Error updating layout")
                    layout_failed = True
                    # Force a full layout recomputation on the next frame so
                    # yoga node state left dirty by the failed pass is reset.
                    self._force_next_render = True
                    if self._root is not None:
                        self._root.mark_dirty()

            if self._force_next_render and self._root and _log.isEnabledFor(logging.DEBUG):
                _log.debug(
                    "=== FIRST FRAME === layout=%s failed=%s %dx%d",
                    needs_layout,
                    layout_failed,
                    self._width,
                    self._height,
                )
                self._debug_dump_tree(self._root, max_depth=16)

            if not layout_failed:
                t_mount = _time.perf_counter_ns()
                hooks.flush_mount_callbacks()
                timings.mount_callbacks_ns = _time.perf_counter_ns() - t_mount

            t_buffer_prepare = t_buffer_lookup = _time.perf_counter_ns()
            buffer = self.get_next_buffer()
            timings.buffer_lookup_ns = _time.perf_counter_ns() - t_buffer_lookup
            reused_current_buffer = False
            repainted_dirty_common_tree = False
            repainted_layout_common_tree = False
            layout_common_plan: list[tuple[Any | None, tuple[int, int, int, int]]] | None = None
            if not needs_layout and self._can_reuse_current_buffer_frame():
                t_buffer_lookup = _time.perf_counter_ns()
                current = self.get_current_buffer()
                timings.buffer_lookup_ns += _time.perf_counter_ns() - t_buffer_lookup
                try:
                    t_replay = _time.perf_counter_ns()
                    buffer._native.draw_frame_buffer(buffer._ptr, 0, 0, current._ptr)
                    timings.buffer_replay_ns = _time.perf_counter_ns() - t_replay
                    reused_current_buffer = True
                except Exception:
                    reused_current_buffer = False
            elif (
                not needs_layout
                and not layout_failed
                and self._can_incremental_common_tree_repaint()
            ):
                t_buffer_lookup = _time.perf_counter_ns()
                current = self.get_current_buffer()
                timings.buffer_lookup_ns += _time.perf_counter_ns() - t_buffer_lookup
                try:
                    t_replay = _time.perf_counter_ns()
                    buffer._native.draw_frame_buffer(buffer._ptr, 0, 0, current._ptr)
                    timings.buffer_replay_ns = _time.perf_counter_ns() - t_replay
                    repainted_dirty_common_tree = True
                except Exception:
                    repainted_dirty_common_tree = False
            elif needs_layout and not layout_failed:
                t_plan = _time.perf_counter_ns()
                repaint_plan = self._compute_layout_common_repaint_plan(
                    layout_repaint_facts or [],
                )
                timings.repaint_plan_ns = _time.perf_counter_ns() - t_plan
                if repaint_plan:
                    t_buffer_lookup = _time.perf_counter_ns()
                    current = self.get_current_buffer()
                    timings.buffer_lookup_ns += _time.perf_counter_ns() - t_buffer_lookup
                    try:
                        t_replay = _time.perf_counter_ns()
                        buffer._native.draw_frame_buffer(buffer._ptr, 0, 0, current._ptr)
                        timings.buffer_replay_ns = _time.perf_counter_ns() - t_replay
                        layout_common_plan = repaint_plan
                        repainted_layout_common_tree = True
                    except Exception:
                        layout_common_plan = None
                        repainted_layout_common_tree = False

            if (
                not reused_current_buffer
                and not repainted_dirty_common_tree
                and not repainted_layout_common_tree
            ):
                buffer.clear()

                # Fill entire buffer with clear color so every cell has an explicit
                # background.  Without this, transparent cells show the terminal's
                # native background color (e.g. Ghostty's gray).
                if self._clear_color:
                    buffer.fill_rect(0, 0, self._width, self._height, self._clear_color)
            timings.buffer_prepare_ns = _time.perf_counter_ns() - t_buffer_prepare

            if self._root:
                try:
                    t_render = _time.perf_counter_ns()
                    if repainted_dirty_common_tree:
                        self._render_dirty_common_subtrees_fast(self._root, buffer, delta_time)
                    elif repainted_layout_common_tree and layout_common_plan is not None:
                        self._render_common_plan_fast(layout_common_plan, buffer, delta_time)
                    elif (
                        not reused_current_buffer
                        and not self._render_common_tree_fast(self._root, buffer)
                        and not self._render_hybrid_tree_fast(self._root, buffer, delta_time)
                    ):
                        self._root.render(buffer, delta_time)
                    timings.render_tree_ns = _time.perf_counter_ns() - t_render
                    # Successful frames clear dirty state after rendering.
                    # Layout apply clears layout dirtiness in native code, but
                    # paint dirtiness may still have been propagated by size
                    # change callbacks or component-local invalidation.
                    if not layout_failed:
                        clear_all_dirty(self._root)
                except Exception:
                    _log.exception("Error rendering root")
                    # Ensure yoga state is re-evaluated on the next frame.
                    self._force_next_render = True
                    if self._root is not None:
                        self._root.mark_dirty()

            t_post = _time.perf_counter_ns()
            for fn in self._post_process_fns:
                fn(buffer)
                # Guard: post-process may have destroyed the renderer.
                if self._ptr is None:
                    return
            timings.post_render_ns = _time.perf_counter_ns() - t_post

            # Guard: if the renderer was destroyed during one of the callbacks
            # above, skip the native render/flush calls to avoid use-after-free.
            if self._ptr is None:
                return

            force = self._force_next_render
            self._force_next_render = False
            t_flush = _time.perf_counter_ns()
            self.render(force=force)
            timings.flush_ns = _time.perf_counter_ns() - t_flush

            # Guard again: destroy() may have been called inside post_process or
            # root.render(), and render() above would then use a live ptr, so we
            # only proceed with cursor/graphics if still alive.
            if self._ptr is None:
                return

            t_finish = _time.perf_counter_ns()
            self._clear_stale_graphics()
            self._apply_cursor()

            # Recheck hover state when the hit-grid is dirty after render.
            # If the pointer hasn't moved but the tree changed (e.g. scroll
            # offset changed), fire synthetic over/out.  The guard is
            # _has_pointer (not _mouse_enabled) so hover recheck fires even
            # when mouse tracking is auto-disabled.
            if hover_recheck_needed:
                self._recheck_hover_state()
            timings.frame_finish_ns = _time.perf_counter_ns() - t_finish
        finally:
            if not layout_failed:
                self._pending_structural_clear_rects.clear()
            timings.total_ns = _time.perf_counter_ns() - frame_start
            self._last_frame_timings = timings
            self._rendering = False
            self._resolve_idle_if_needed()

    def queue_structural_clear_rect(self, rect: tuple[int, int, int, int]) -> None:
        x, y, width, height = rect
        if width <= 0 or height <= 0:
            return
        self._pending_structural_clear_rects.append((x, y, width, height))

    def evaluate_component(self, component_fn: Callable) -> tuple[Any, set, str]:
        from ..signals import _tracking_context

        if getattr(component_fn, "__opentui_component__", False):
            return component_fn(), set(), "template"

        tracked: set = set()
        token = _tracking_context.set(tracked)
        try:
            component = component_fn()
        finally:
            _tracking_context.reset(token)

        if tracked:
            signal_names = ", ".join(sorted(s._name for s in tracked if s._name))
            comp_name = getattr(
                component_fn, "__qualname__", getattr(component_fn, "__name__", "<unknown>")
            )
            short_name = comp_name.split(".")[-1]
            raise RuntimeError(
                f"Component '{comp_name}' reads signals in its body: [{signal_names}]\n"
                f"This triggers a full tree rebuild on every signal change.\n\n"
                f"Fix: use @component for reactive props:\n"
                f"  @component\n"
                f"  def {short_name}():\n"
                f"      return Text(lambda: f'value: {{signal_name()}}')\n\n"
                f"Alternatives: Show/Switch/For for control flow."
            )

        return component, set(), "template"

    def _refresh_mouse_tracking(self) -> None:
        if not self._mouse_tracking_dirty:
            should_enable = self._cached_requires_mouse_tracking
        else:
            should_enable = (
                bool(hooks.get_mouse_handlers())
                or self._tree_has_mouse_handlers(self._root)
                or self._tree_has_scroll_targets(self._root)
            )
            self._cached_requires_mouse_tracking = should_enable
            self._mouse_tracking_dirty = False

        if should_enable and not self._mouse_enabled:
            self.enable_mouse()
        elif not should_enable and self._mouse_enabled:
            self.disable_mouse()

    def _update_layout(
        self, renderable, delta_time: float
    ) -> tuple[
        int,
        int,
        int,
        int,
        bool,
        list[LayoutRepaintFact] | None,
    ]:
        configure_yoga_ns = 0
        compute_yoga_ns = 0
        apply_layout_ns = 0
        update_layout_hooks_ns = 0
        needs_layout = False
        layout_repaint_facts: list[LayoutRepaintFact] | None = None
        if renderable is self._root and self._root is not None:
            needs_layout = self._root._subtree_dirty
            if needs_layout:
                if _NATIVE_LAYOUT_CACHE["fn"] is _NOT_LOADED:
                    _load_native_layout_apply(self._root)
                local_subtree = collect_local_layout_subtree(self._root)
                if local_subtree is None:
                    # Children already synced by add/remove/reconciler
                    t_configure = _time.perf_counter_ns()
                    self._root._configure_yoga_properties()
                    configure_yoga_ns = _time.perf_counter_ns() - t_configure

                    from .. import layout as yoga_layout

                    t_compute = _time.perf_counter_ns()
                    yoga_layout.compute_layout(
                        self._root._yoga_node, float(self._width), float(self._height)
                    )
                    compute_yoga_ns = _time.perf_counter_ns() - t_compute

                    t_apply = _time.perf_counter_ns()
                    layout_repaint_facts = apply_yoga_layout_native(self._root)
                    apply_layout_ns = _time.perf_counter_ns() - t_apply
                else:
                    subtree, avail_width, avail_height, origin_x, origin_y = local_subtree
                    t_configure = _time.perf_counter_ns()
                    subtree._configure_yoga_properties()
                    configure_yoga_ns = _time.perf_counter_ns() - t_configure

                    from .. import layout as yoga_layout

                    t_compute = _time.perf_counter_ns()
                    yoga_layout.compute_layout(subtree._yoga_node, avail_width, avail_height)
                    compute_yoga_ns = _time.perf_counter_ns() - t_compute

                    t_apply = _time.perf_counter_ns()
                    layout_repaint_facts = apply_yoga_layout_native(
                        subtree,
                        origin_x=origin_x,
                        origin_y=origin_y,
                    )
                    clear_handled_layout_dirty_ancestors(subtree)
                    apply_layout_ns = _time.perf_counter_ns() - t_apply

            if _diag._enabled & _diag.LAYOUT:
                _diag.log_layout_facts(layout_repaint_facts)

            if self._tree_has_custom_update_layout is None:
                self._tree_custom_update_layout_count = count_tree_custom_update_layout(self._root)
                self._tree_has_custom_update_layout = self._tree_custom_update_layout_count > 0

        t_hooks = _time.perf_counter_ns()
        if has_custom_update_layout(renderable):
            renderable.update_layout(delta_time)

        # Recurse only when a subtree was structurally/layout dirty or a node
        # defines a real update_layout hook. Yoga layout has already been
        # applied tree-wide above; this walk is only for post-layout hooks.
        if self._tree_has_custom_update_layout:
            for child in list(getattr(renderable, "_children", [])):
                if not getattr(child, "_destroyed", False):
                    _, _, _, child_hooks_ns, _, _ = self._update_layout(child, delta_time)
                    update_layout_hooks_ns += child_hooks_ns
        update_layout_hooks_ns += _time.perf_counter_ns() - t_hooks

        return (
            configure_yoga_ns,
            compute_yoga_ns,
            apply_layout_ns,
            update_layout_hooks_ns,
            needs_layout,
            layout_repaint_facts,
        )

    def _debug_dump_tree(self, node, depth: int = 0, max_depth: int = 8) -> None:
        if depth > max_depth:
            _log.warning("%s  ... (max depth)", "  " * depth)
            return
        indent = "  " * depth
        name = type(node).__name__
        lw = getattr(node, "_layout_width", "?")
        lh = getattr(node, "_layout_height", "?")
        x = getattr(node, "_x", "?")
        y = getattr(node, "_y", "?")
        fg = getattr(node, "_flex_grow", "?")
        vis = getattr(node, "_visible", "?")
        key = getattr(node, "_key", None)
        nkids = len(getattr(node, "_children", []))
        yoga_info = ""
        yoga_node = getattr(node, "_yoga_node", None)
        if yoga_node:
            yoga_info = f" yoga={yoga_node.layout_width}x{yoga_node.layout_height}"
        key_str = f" key={key}" if key else ""
        content = ""
        c = getattr(node, "_content", None)
        if c is not None:
            content = f' "{c[:30]}"' if c else ""
        _log.debug(
            "%s%s: %sx%s @(%s,%s) fg=%s vis=%s kids=%d%s%s%s",
            indent,
            name,
            lw,
            lh,
            x,
            y,
            fg,
            vis,
            nkids,
            yoga_info,
            key_str,
            content,
        )
        for child in getattr(node, "_children", []):
            self._debug_dump_tree(child, depth + 1, max_depth)

    def _render_common_tree_fast(self, root, buffer: Buffer) -> bool:
        if not self._prepare_common_tree_render(root):
            return False

        return self._render_common_tree_unchecked_fast(root, buffer)

    def _render_common_tree_unchecked_fast(self, root, buffer: Buffer) -> bool:
        render_fn = _COMMON_RENDER_CACHE["render_fn"]
        offsets = _COMMON_RENDER_CACHE["offsets"]
        root_type = _COMMON_RENDER_CACHE["root_type"]
        box_type = _COMMON_RENDER_CACHE["box_type"]
        text_type = _COMMON_RENDER_CACHE["text_type"]
        portal_type = _COMMON_RENDER_CACHE["portal_type"]

        if None in (render_fn, offsets, root_type, box_type, text_type, portal_type):
            return False

        try:
            return bool(
                render_fn(buffer._ptr, root, root_type, box_type, text_type, portal_type, offsets)
            )
        except Exception:
            _log.debug("native common render path unavailable", exc_info=True)
            self._common_tree_cache_root = root
            self._common_tree_cache_valid = False
            self._common_tree_cache_eligible = False
            return False

    def _render_hybrid_tree_fast(self, root, buffer: Buffer, delta_time: float) -> bool:
        if _has_instance_render_override(root):
            return False

        c = _ensure_common_render_loaded(root)
        hybrid_fn, offsets = c["hybrid_fn"], c["offsets"]
        root_type, box_type, text_type, portal_type = (
            c["root_type"],
            c["box_type"],
            c["text_type"],
            c["portal_type"],
        )

        if None in (hybrid_fn, offsets, root_type, box_type, text_type, portal_type):
            return False

        def py_fallback(node):
            node.render(buffer, delta_time)

        try:
            return bool(
                hybrid_fn(
                    buffer._ptr,
                    root,
                    root_type,
                    box_type,
                    text_type,
                    portal_type,
                    offsets,
                    py_fallback,
                )
            )
        except Exception:
            _log.debug("hybrid render path failed", exc_info=True)
            return False

    def _prepare_common_tree_render(self, root) -> bool:
        if _has_instance_render_override(root):
            return False
        if not supports_common_tree_strategy(root):
            self._common_tree_cache_root = root
            self._common_tree_cache_valid = True
            self._common_tree_cache_eligible = False
            return False

        c = _ensure_common_render_loaded(root)
        validate_fn, render_fn, offsets = c["validate_fn"], c["render_fn"], c["offsets"]
        root_type, box_type, text_type, portal_type = (
            c["root_type"],
            c["box_type"],
            c["text_type"],
            c["portal_type"],
        )

        if None in (validate_fn, render_fn, offsets, root_type, box_type, text_type, portal_type):
            return False

        tree_dirty = bool(
            getattr(root, "_dirty", False)
            or getattr(root, "_subtree_dirty", False)
            or getattr(root, "_paint_subtree_dirty", False)
        )
        cache_stale = root is not self._common_tree_cache_root or not self._common_tree_cache_valid

        try:
            if tree_dirty or cache_stale:
                eligible = bool(
                    validate_fn(root, root_type, box_type, text_type, portal_type, offsets)
                )
                self._common_tree_cache_root = root
                self._common_tree_cache_valid = True
                self._common_tree_cache_eligible = eligible
                if not eligible:
                    return False
            elif not self._common_tree_cache_eligible:
                return False
            return True
        except Exception:
            _log.debug("native common render path unavailable", exc_info=True)
            self._common_tree_cache_root = root
            self._common_tree_cache_valid = False
            self._common_tree_cache_eligible = False
            return False

    def _can_reuse_current_buffer_frame(self) -> bool:
        root = self._root
        if root is None or self._force_next_render or self._post_process_fns:
            return False
        if (
            getattr(root, "_dirty", False)
            or getattr(root, "_subtree_dirty", False)
            or getattr(root, "_paint_subtree_dirty", False)
        ):
            return False
        return self._prepare_common_tree_render(root)

    def _can_incremental_common_tree_repaint(self) -> bool:
        root = self._root
        if root is None or self._force_next_render:
            return False
        if getattr(root, "_dirty", False) or getattr(root, "_subtree_dirty", False):
            return False
        if not getattr(root, "_paint_subtree_dirty", False):
            return False
        return self._prepare_common_tree_render(root)

    def _compute_layout_common_repaint_plan(
        self,
        layout_repaint_facts: list[LayoutRepaintFact],
    ) -> list[tuple[Any, tuple[int, int, int, int]]] | None:
        root = self._root
        if (
            root is None
            or self._force_next_render
            or self._post_process_fns
            or self._tree_has_custom_update_layout
            or not layout_repaint_facts
        ):
            return None
        if not self._prepare_common_tree_render(root):
            return None

        return self._compute_layout_common_repaint_plan_from_facts(root, layout_repaint_facts)

    def _compute_layout_common_repaint_plan_from_facts(
        self,
        root,
        facts: list[LayoutRepaintFact],
    ) -> list[tuple[Any | None, tuple[int, int, int, int]]] | None:
        if len(facts) <= 8:
            return self._compute_layout_common_repaint_plan_small_facts(root, facts)

        root_id = id(root)
        facts_by_id: dict[int, LayoutRepaintFact] = {}
        for fact in facts:
            node = fact[0]
            facts_by_id[id(node)] = fact
        if not facts_by_id:
            return None
        if root_id in facts_by_id:
            return self._compute_structural_common_repaint_plan(root, facts_by_id[root_id])

        promoted: list[Any] = []
        for fact in facts_by_id.values():
            promoted_node = promote_layout_repaint_root_from_facts(fact, facts_by_id, root_id, root)
            if promoted_node is root:
                return None
            promoted.append(promoted_node)

        roots = dedupe_common_roots_from_facts(promoted, facts_by_id, root_id)
        if not roots:
            return None

        fact_by_node = {fact[0]: fact for fact in facts}
        return [
            (
                node,
                layout_repaint_rect_from_fact(fact_by_node.get(node))
                if node in fact_by_node
                else node_bounds_rect(node),
            )
            for node in roots
        ]

    def _compute_layout_common_repaint_plan_small_facts(
        self,
        root,
        facts: list[LayoutRepaintFact],
    ) -> list[tuple[Any | None, tuple[int, int, int, int]]] | None:
        root_id = id(root)
        node_ids = [id(fact[0]) for fact in facts]

        for idx, node_id in enumerate(node_ids):
            if node_id == root_id:
                return self._compute_structural_common_repaint_plan(root, facts[idx])

        promoted: list[Any] = []
        for fact in facts:
            current_fact = fact
            current_node = fact[0]
            parent_id = fact[1]
            while parent_id and parent_id != root_id:
                parent_fact = None
                for idx, node_id in enumerate(node_ids):
                    if node_id == parent_id:
                        parent_fact = facts[idx]
                        break
                if parent_fact is None:
                    break
                current_fact = parent_fact
                current_node = current_fact[0]
                parent_id = current_fact[1]

            has_children = bool(current_fact[2])
            if parent_id == root_id and not has_children:
                return None
            if not has_children and parent_id and parent_id != root_id:
                parent = getattr(current_node, "_parent", None)
                if parent is not None:
                    current_node = parent
            promoted.append(current_node)

        roots = dedupe_common_roots(promoted, root)
        if not roots:
            return None

        plan: list[tuple[Any | None, tuple[int, int, int, int]]] = []
        for node in roots:
            node_fact = None
            for fact in facts:
                if fact[0] is node:
                    node_fact = fact
                    break
            rect = (
                layout_repaint_rect_from_fact(node_fact)
                if node_fact is not None
                else node_bounds_rect(node)
            )
            plan.append((node, rect))
        return plan

    def _compute_structural_common_repaint_plan(
        self,
        root,
        root_fact: LayoutRepaintFact,
    ) -> list[tuple[Any | None, tuple[int, int, int, int]]] | None:
        if root_fact[4:8] != root_fact[8:12]:
            return None

        plan: list[tuple[Any | None, tuple[int, int, int, int]]] = [
            (None, rect) for rect in self._pending_structural_clear_rects
        ]
        dirty_roots: list[Any] = []
        self._collect_structural_common_roots(root, dirty_roots)
        for node in dedupe_common_roots(dirty_roots, root):
            plan.append((node, node_bounds_rect(node)))
        return plan or None

    def _render_common_plan_fast(
        self,
        plan: list[tuple[Any | None, tuple[int, int, int, int]]],
        buffer: Buffer,
        delta_time: float,
    ) -> None:
        for node, rect in plan:
            self._clear_common_repaint_rect(buffer, rect)
            if node is None:
                continue
            if not self._render_common_tree_unchecked_fast(node, buffer):
                node.render(buffer, delta_time)

    def _clear_common_repaint_rect(
        self,
        buffer: Buffer,
        rect: tuple[int, int, int, int],
    ) -> None:
        x, y, width, height = rect
        if width <= 0 or height <= 0:
            return
        buffer.fill_rect(x, y, width, height, self._clear_color)

    def _render_dirty_common_subtrees_fast(self, root, buffer: Buffer, delta_time: float) -> None:
        dirty_roots: list[Any] = []
        self._collect_dirty_common_roots(root, dirty_roots)
        self._render_common_plan_fast(
            [(node, node_bounds_rect(node)) for node in dirty_roots],
            buffer,
            delta_time,
        )

    def _collect_structural_common_roots(self, node, out: list[Any]) -> None:
        for child in getattr(node, "_children", ()):
            if getattr(child, "_destroyed", False):
                continue
            if not (
                getattr(child, "_dirty", False)
                or getattr(child, "_subtree_dirty", False)
                or getattr(child, "_paint_subtree_dirty", False)
            ):
                continue
            if supports_common_tree_strategy(child) and not _has_instance_render_override(child):
                out.append(child)
                continue
            self._collect_structural_common_roots(child, out)

    def _collect_dirty_common_roots(self, node, out: list[Any]) -> None:
        if getattr(node, "_dirty", False):
            out.append(node)
            return
        for child in getattr(node, "_children", ()):
            if getattr(child, "_dirty", False) or getattr(child, "_paint_subtree_dirty", False):
                self._collect_dirty_common_roots(child, out)

    def invalidate_handler_cache(self) -> None:
        self._handlers_dirty = True
        self._mouse_tracking_dirty = True

    def invalidate_layout_hook_cache(self) -> None:
        self._tree_has_custom_update_layout = None
        self._tree_custom_update_layout_count = None

    def adjust_layout_hook_cache_for_subtree(self, renderable, delta: int) -> None:
        if self._tree_custom_update_layout_count is None:
            return
        subtree_count = count_tree_custom_update_layout(renderable)
        self._tree_custom_update_layout_count = max(
            0,
            self._tree_custom_update_layout_count + (subtree_count * delta),
        )
        self._tree_has_custom_update_layout = self._tree_custom_update_layout_count > 0

    def _get_event_forwarding(self) -> dict:
        if not self._handlers_dirty:
            return self._cached_handlers

        handlers: dict[str, list[Callable]] = {"key": [], "mouse": [], "paste": []}

        if self._root:
            self._collect_handlers(self._root, handlers)

        self._cached_handlers = handlers
        self._handlers_dirty = False
        return handlers

    def _collect_handlers(self, renderable, handlers: dict) -> None:
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

    def add_post_process_fn(self, fn: Callable) -> None:
        self._post_process_fns.append(fn)

    def remove_post_process_fn(self, fn: Callable) -> None:
        with contextlib.suppress(ValueError):
            self._post_process_fns.remove(fn)

    def set_frame_callback(self, callback: Callable) -> None:
        self._frame_callbacks.append(callback)

    def remove_frame_callback(self, callback: Callable) -> None:
        with contextlib.suppress(ValueError):
            self._frame_callbacks.remove(callback)

    def request_animation_frame(self, callback: Callable) -> int:
        handle = self._next_animation_id
        self._next_animation_id += 1
        self._animation_frame_callbacks[handle] = callback
        return handle

    def cancel_animation_frame(self, handle: int) -> None:
        self._animation_frame_callbacks.pop(handle, None)

    @staticmethod
    def _write_stdout(data: str) -> None:
        try:
            import sys

            sys.stdout.write(data)
            sys.stdout.flush()
        except Exception:
            pass

    def set_cursor_style(self, style: str) -> None:
        if self._cursor_style == style:
            return
        self._cursor_style = style
        self._write_stdout(f"\x1b[{_CURSOR_STYLE_MAP.get(style, 1)} q")

    def set_cursor_color(self, color: str) -> None:
        if self._cursor_color == color:
            return
        self._cursor_color = color
        self._write_stdout(f"\x1b]12;{color}\x07")

    def set_mouse_pointer(self, style: str) -> None:
        self._current_mouse_pointer_style = style

    def _reset_cursor_color(self) -> None:
        self._cursor_color = None
        self._write_stdout("\x1b]112\x07")

    @property
    def palette_detection_status(self) -> str:
        if self._cached_palette is not None:
            return "cached"
        if self._palette_detection_promise is not None:
            return "detecting"
        return "idle"

    def clear_palette_cache(self) -> None:
        self._cached_palette = None

    async def get_palette(
        self,
        timeout: float = 5000,
        size: int = 16,
    ) -> Any:
        if self._control_state == RendererControlState.EXPLICIT_SUSPENDED:
            raise RuntimeError("Cannot detect palette while renderer is suspended")

        if self._cached_palette is not None and len(self._cached_palette.palette) != size:
            self._cached_palette = None

        if self._cached_palette is not None:
            return self._cached_palette

        if self._palette_detection_promise is not None:
            return await self._palette_detection_promise

        if self._palette_detector is None:
            from ..palette import TerminalPaletteDetector

            if self._config.testing:
                from ..palette import MockPaletteStdin, MockPaletteStdout

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
            result = await self._palette_detector.detect(timeout=timeout, size=size)
            self._cached_palette = result
            self._palette_detection_promise = None
            return result

        self._palette_detection_promise = asyncio.ensure_future(_do_detect())
        return await self._palette_detection_promise

    def _restore_terminal_modes(self) -> None:
        """Some terminals (tmux, screen) drop protocol state on focus loss;
        re-send kitty keyboard flags, mouse tracking, and bracketed paste.
        """
        if self._config.testing:
            return
        try:
            import sys as _sys

            buf = ""
            if self._config.kitty_keyboard_flags:
                self.enable_keyboard(self._config.kitty_keyboard_flags)
            if self._mouse_enabled:
                self.enable_mouse()
            buf += "\x1b[?2004h"
            _sys.stdout.write(buf)
            _sys.stdout.flush()
        except Exception:
            _log.debug("Failed to restore terminal modes on focus", exc_info=True)

    @property
    def control_state(self) -> RendererControlState:
        return self._control_state

    @property
    def is_running(self) -> bool:
        return self._running

    def _is_idle_now(self) -> bool:
        return (
            not self._running
            and not self._rendering
            and not self._update_scheduled
            and not self._immediate_rerender_requested
        )

    def _resolve_idle_if_needed(self) -> None:
        if not self._is_idle_now():
            return
        futures = self._idle_futures[:]
        self._idle_futures.clear()
        for fut in futures:
            if not fut.done():
                fut.set_result(None)

    async def idle(self) -> None:
        if self.is_destroyed:
            return
        if self._is_idle_now():
            return
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[None] = loop.create_future()
        self._idle_futures.append(fut)
        await fut

    def _internal_start(self) -> None:
        if not self._running and not self.is_destroyed:
            self._running = True

    def _internal_pause(self) -> None:
        self._running = False
        if not self._rendering:
            self._resolve_idle_if_needed()

    def _internal_stop(self) -> None:
        if self._running and not self.is_destroyed:
            self._running = False
            if not self._rendering:
                self._resolve_idle_if_needed()

    def start(self) -> None:
        self._control_state = RendererControlState.EXPLICIT_STARTED
        self._internal_start()

    def pause(self) -> None:
        self._control_state = RendererControlState.EXPLICIT_PAUSED
        self._internal_pause()

    def stop(self) -> None:
        self._control_state = RendererControlState.EXPLICIT_STOPPED
        self._internal_stop()
        if self._event_loop is not None:
            self._event_loop.stop()

    def request_live(self) -> None:
        self._live_request_counter += 1
        if self._control_state == RendererControlState.IDLE and self._live_request_counter > 0:
            self._control_state = RendererControlState.AUTO_STARTED
            self._internal_start()

    def drop_live(self) -> None:
        self._live_request_counter = max(0, self._live_request_counter - 1)
        if (
            self._control_state == RendererControlState.AUTO_STARTED
            and self._live_request_counter == 0
        ):
            self._control_state = RendererControlState.IDLE
            self._internal_pause()

    @property
    def is_destroyed(self) -> bool:
        return self._ptr is None

    def destroy(self) -> None:
        self._current_mouse_pointer_style = "default"
        self._last_over_renderable = None
        if self._palette_detector is not None:
            self._palette_detector.cleanup()
            self._palette_detector = None
        self._palette_detection_promise = None
        self._cached_palette = None
        if self._ptr:
            self._native.renderer.destroy_renderer(self._ptr)
            self._ptr = None
        self._running = False
        futures = self._idle_futures[:]
        self._idle_futures.clear()
        for fut in futures:
            if not fut.done():
                fut.set_result(None)


class RootRenderable(BaseRenderable):
    def __init__(self, renderer: CliRenderer):
        super().__init__()
        self._renderer = renderer
        self._width = renderer.width
        self._height = renderer.height

    def _configure_yoga_node(self, node) -> None:
        node.width = float(self._renderer.width)
        node.height = float(self._renderer.height)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        for child in self._children:
            child.render(buffer, delta_time)


async def create_cli_renderer(config: CliRendererConfig | None = None) -> CliRenderer:
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
