"""Terminal rendering loop — layout, painting, input dispatch, and native acceleration."""

from __future__ import annotations

import logging
import shutil
import time as _time
from collections.abc import Callable
from typing import Any

from .buffer import Buffer, FrameTimingBuckets

_log = logging.getLogger(__name__)

from .. import diagnostics as _diag
from .. import hooks
from .. import structs as s
from ..components.base import BaseRenderable
from ..ffi import get_native, is_native_available
from ..image.encoding import _clear_kitty_graphics
from ._config import (
    CliRendererConfig,
    RendererControlState,
    TerminalCapabilities,
    _ConfigMixin,
    _LifecycleMixin,
)
from ._cursor import _CursorMixin
from ._debug import (
    adjust_layout_hook_cache_for_subtree,
    debug_dump_tree,
    invalidate_layout_hook_cache,
)
from ._mouse_selection import apply_selection_overlay
from ._eventing import (
    add_post_process_fn,
    cancel_animation_frame,
    collect_event_forwarding,
    emit_renderer_event,
    invalidate_handler_cache,
    register_event_listener,
    remove_frame_callback,
    remove_post_process_fn,
    request_animation_frame,
    set_frame_callback,
)
from ._frame_pipeline import compute_layout, prepare_buffer, run_frame_callbacks
from ._native_render import _NativeRenderMixin
from ._session import (
    bind_event_loop,
    destroy_terminal_session,
    prepare_terminal_session,
    restore_terminal_modes,
    teardown_terminal_session,
)
from .console import TerminalConsole
from .layout import (
    clear_all_dirty,
    clear_handled_layout_dirty_ancestors,
    collect_local_layout_subtree,
    count_tree_custom_update_layout,
    has_custom_update_layout,
)
from .mouse import MouseHandlingMixin
from .native import (
    _NATIVE_LAYOUT_CACHE,
    _NOT_LOADED,
    LayoutRepaintFact,
    _load_native_layout_apply,
)
from .repaint import apply_yoga_layout_native

_SELECTION_BG = s.RGBA(0.3, 0.3, 0.7, 1.0)


def _resolve_terminal_size(config: Any) -> tuple[int, int]:
    if config.testing:
        return config.width, config.height
    try:
        term_size = shutil.get_terminal_size()
        if term_size.columns > 0 and term_size.lines > 0:
            return term_size.columns, term_size.lines
    except (AttributeError, OSError):
        pass
    return config.width, config.height


class CliRenderer(_NativeRenderMixin, _LifecycleMixin, _CursorMixin, _ConfigMixin, MouseHandlingMixin):
    """CLI renderer - wraps the native OpenTUI renderer using nanobind."""

    def __init__(self, ptr: Any, config: CliRendererConfig, native: Any):
        self._ptr = ptr
        self._config = config
        self._native = native
        self._control_state: RendererControlState = RendererControlState.IDLE

        # -- runtime state --
        self._running = False
        self._rendering = False
        self._update_scheduled = False
        self._immediate_rerender_requested = False
        self._live_request_counter = 0
        self._idle_futures: list = []
        self._root = None
        self._component_fn = None
        self._signal_state = None
        self._last_frame_timings = FrameTimingBuckets()
        self._tree_has_custom_update_layout = None
        self._tree_custom_update_layout_count = None
        self._common_tree_cache_root = None
        self._common_tree_cache_valid = False
        self._common_tree_cache_eligible = False
        self._pending_structural_clear_rects: list = []
        self._handlers_dirty = True
        self._cached_handlers: dict = {"key": [], "mouse": [], "paste": []}
        self._auto_focus = config.auto_focus
        self._focused_renderable = None
        self._is_dragging = False
        self._post_process_fns: list = []
        self._frame_callbacks: list = []
        self._animation_frame_callbacks: dict = {}
        self._next_animation_id = 0
        self._event_loop = None
        self._force_next_render = True
        self._clear_color = s.parse_color_opt(config.clear_color)

        # -- mouse and selection state --
        self._mouse_enabled = False
        self._mouse_tracking_dirty = True
        self._cached_requires_mouse_tracking = False
        self._captured_renderable = None
        self._current_mouse_pointer_style = "default"
        self._last_over_renderable = None
        self._latest_pointer: dict = {"x": 0, "y": 0}
        self._has_pointer = False
        self._last_pointer_modifiers: dict = {"shift": False, "alt": False, "ctrl": False}
        self._current_selection = None
        self._selection_containers: list = []
        self._pending_selection_start = None

        # -- cursor and graphics state --
        self._cursor_request = None
        self._cursor_style_request = None
        self._cursor_color_request = None
        self._cursor_style = "block"
        self._cursor_color = None
        self._prev_frame_graphics: set = set()
        self._frame_graphics: set = set()
        self._graphics_suppressed = False

        # -- buffers and capabilities --
        graphics = getattr(native, "graphics", None)
        self._next_buffer_wrapper = Buffer(None, native.buffer, graphics)
        self._current_buffer_wrapper = Buffer(None, native.buffer, graphics)
        self._event_listeners: dict = {}
        self._cached_capabilities = None
        self._palette_detector = None
        self._cached_palette = None
        self._palette_detection_promise = None

        # -- terminal geometry --
        width, height = _resolve_terminal_size(config)
        self._width = width
        self._height = height
        self._split_height = 0
        self._render_offset = 0
        self._terminal_height = height
        split_height = config.experimental_split_height or 0
        if split_height > 0:
            self._split_height = split_height
            self._render_offset = self._height - split_height
            self._height = split_height

        # -- console state --
        self._console = TerminalConsole(self, config.console_options)
        self._use_console = True
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

            for gid in stale:
                _sys.stdout.buffer.write(_clear_kitty_graphics(gid))
            _sys.stdout.buffer.flush()
        self._prev_frame_graphics = self._frame_graphics
        self._frame_graphics = set()

    def set_mouse_pointer(self, style: str) -> None:
        self._current_mouse_pointer_style = style

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

    def set_background_color(self, color: s.RGBA | str | None = None) -> None:
        parsed = s.parse_color_opt(color)
        color_tuple = (parsed.r, parsed.g, parsed.b, parsed.a) if parsed else None
        self._native.renderer.set_background_color(self._ptr, color_tuple)

    def query_pixel_resolution(self) -> None:
        self._native.renderer.query_pixel_resolution(self._ptr)

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
        return register_event_listener(self, event, handler)

    def emit_event(self, event: str, *args: Any) -> None:
        emit_renderer_event(self, event, *args)

    def run(self) -> None:
        self._running = True
        os_module, select_module, sys_module = prepare_terminal_session(self)

        from ..input.event_loop import EventLoop

        event_loop = EventLoop(target_fps=self._config.target_fps)
        self._event_loop = event_loop
        bind_event_loop(self, event_loop)

        try:
            event_loop.run()
        except KeyboardInterrupt:
            if not self._config.exit_on_ctrl_c:
                raise
        finally:
            teardown_terminal_session(
                self,
                os_module=os_module,
                select_module=select_module,
                sys_module=sys_module,
            )

    def _run_frame_callbacks(
        self, delta_time: float, timings: FrameTimingBuckets,
    ) -> bool:
        return run_frame_callbacks(self, delta_time, timings)

    def _compute_layout(
        self, delta_time: float, timings: FrameTimingBuckets,
    ) -> tuple[bool, bool, list[LayoutRepaintFact] | None]:
        return compute_layout(self, delta_time, timings)

    def _prepare_buffer(
        self,
        needs_layout: bool,
        layout_failed: bool,
        layout_repaint_facts: list[LayoutRepaintFact] | None,
        timings: FrameTimingBuckets,
    ) -> tuple[
        Buffer,
        bool,
        bool,
        bool,
        list[tuple[Any | None, tuple[int, int, int, int]]] | None,
    ]:
        return prepare_buffer(self, needs_layout, layout_failed, layout_repaint_facts, timings)

    def _render_tree_to_buffer(
        self,
        buffer: Buffer,
        reused_current_buffer: bool,
        repainted_dirty_common_tree: bool,
        repainted_layout_common_tree: bool,
        layout_common_plan: list | None,
        layout_failed: bool,
        delta_time: float,
        timings: FrameTimingBuckets,
    ) -> None:
        """Dispatch tree rendering to the fastest available strategy."""
        if not self._root:
            return
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
            if not layout_failed:
                clear_all_dirty(self._root)
        except Exception:
            _log.exception("Error rendering root")
            self._force_next_render = True
            if self._root is not None:
                self._root.mark_dirty()

    def _run_post_render_phase(self, buffer: Buffer, timings: FrameTimingBuckets) -> bool:
        """Run post-process functions and selection overlay. Returns False if destroyed."""
        t_post = _time.perf_counter_ns()
        for fn in self._post_process_fns:
            fn(buffer)
            if self._ptr is None:
                return False
        self._apply_selection_overlay(buffer)
        if self._ptr is None:
            return False
        timings.post_render_ns = _time.perf_counter_ns() - t_post
        return True

    def _flush_native_output(
        self, hover_recheck_needed: bool, timings: FrameTimingBuckets,
    ) -> None:
        """Native render, graphics cleanup, cursor, and hover recheck."""
        force = self._force_next_render
        self._force_next_render = False
        t_flush = _time.perf_counter_ns()
        self.render(force=force)
        timings.flush_ns = _time.perf_counter_ns() - t_flush

        if self._ptr is None:
            return

        t_finish = _time.perf_counter_ns()
        self._clear_stale_graphics()
        self._apply_cursor()
        if hover_recheck_needed:
            self._recheck_hover_state()
            self.request_selection_update()
        timings.frame_finish_ns = _time.perf_counter_ns() - t_finish

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
            signal_triggered_hover = self._run_frame_callbacks(delta_time, timings)
            if signal_triggered_hover:
                hover_recheck_needed = True

            if self._ptr is None:
                return

            needs_layout, layout_failed, layout_repaint_facts = self._compute_layout(
                delta_time, timings,
            )

            (
                buffer,
                reused_current_buffer,
                repainted_dirty_common_tree,
                repainted_layout_common_tree,
                layout_common_plan,
            ) = self._prepare_buffer(needs_layout, layout_failed, layout_repaint_facts, timings)

            self._render_tree_to_buffer(
                buffer, reused_current_buffer,
                repainted_dirty_common_tree, repainted_layout_common_tree,
                layout_common_plan, layout_failed, delta_time, timings,
            )

            if not self._run_post_render_phase(buffer, timings):
                return

            if self._ptr is None:
                return

            self._flush_native_output(hover_recheck_needed, timings)
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

    def evaluate_component(self, component_fn: Callable) -> Any:
        from .._signals_runtime import _tracking_context

        if getattr(component_fn, "__opentui_component__", False):
            return component_fn()

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

        return component

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
                if _log.isEnabledFor(logging.DEBUG):
                    _log.debug(
                        "_update_layout: needs_layout=%s local_subtree=%s",
                        needs_layout,
                        type(local_subtree[0]).__name__ if local_subtree else None,
                    )
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
        debug_dump_tree(self, node, depth, max_depth)

    def invalidate_handler_cache(self) -> None:
        invalidate_handler_cache(self)

    def invalidate_layout_hook_cache(self) -> None:
        invalidate_layout_hook_cache(self)

    def adjust_layout_hook_cache_for_subtree(self, renderable, delta: int) -> None:
        adjust_layout_hook_cache_for_subtree(
            self,
            renderable,
            delta,
            count_tree_custom_update_layout=count_tree_custom_update_layout,
        )

    def _get_event_forwarding(self) -> dict:
        return collect_event_forwarding(self)

    def add_post_process_fn(self, fn: Callable) -> None:
        add_post_process_fn(self, fn)

    def remove_post_process_fn(self, fn: Callable) -> None:
        remove_post_process_fn(self, fn)

    def _apply_selection_overlay(self, buffer: Buffer) -> None:
        apply_selection_overlay(self, buffer, _SELECTION_BG)

    def set_frame_callback(self, callback: Callable) -> None:
        set_frame_callback(self, callback)

    def remove_frame_callback(self, callback: Callable) -> None:
        remove_frame_callback(self, callback)

    def request_animation_frame(self, callback: Callable) -> int:
        return request_animation_frame(self, callback)

    def cancel_animation_frame(self, handle: int) -> None:
        cancel_animation_frame(self, handle)

    def _restore_terminal_modes(self) -> None:
        restore_terminal_modes(self)

    @property
    def is_destroyed(self) -> bool:
        return self._ptr is None

    def destroy(self) -> None:
        destroy_terminal_session(self)


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


# Re-export kitty keyboard constants from their canonical home in input.key_maps.
from ..input.key_maps import (  # noqa: E402
    KITTY_FLAG_ALL_KEYS_AS_ESCAPES,
    KITTY_FLAG_ALTERNATE_KEYS,
    KITTY_FLAG_DISAMBIGUATE,
    KITTY_FLAG_EVENT_TYPES,
    KITTY_FLAG_REPORT_TEXT,
    build_kitty_keyboard_flags,
)

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
