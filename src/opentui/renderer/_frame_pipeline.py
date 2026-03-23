"""Frame pipeline helpers for CliRenderer."""

from __future__ import annotations

import logging
import time as _time
from typing import Any

from .. import hooks
from .buffer import Buffer, FrameTimingBuckets
from .native import LayoutRepaintFact

_log = logging.getLogger(__name__)


def run_frame_callbacks(renderer: Any, delta_time: float, timings: FrameTimingBuckets) -> bool:
    for cb in renderer._frame_callbacks:
        cb(delta_time)

    if renderer._animation_frame_callbacks:
        pending = dict(renderer._animation_frame_callbacks)
        renderer._animation_frame_callbacks.clear()
        for cb in pending.values():
            cb(delta_time)

    signal_triggered_hover = False
    if (
        renderer._component_fn is not None
        and renderer._signal_state is not None
        and renderer._signal_state.has_changes()
    ):
        t_signal = _time.perf_counter_ns()
        signal_count = len(renderer._signal_state._notified)
        signal_triggered_hover = True
        renderer._signal_state.reset()
        _log.debug("signals handled reactively: %d signal(s)", signal_count)
        timings.signal_handling_ns = _time.perf_counter_ns() - t_signal

    renderer._refresh_mouse_tracking()
    return signal_triggered_hover


def compute_layout(
    renderer: Any,
    delta_time: float,
    timings: FrameTimingBuckets,
) -> tuple[bool, bool, list[LayoutRepaintFact] | None]:
    needs_layout = False
    layout_failed = False
    layout_repaint_facts: list[LayoutRepaintFact] | None = None
    if renderer._root:
        try:
            t_layout = _time.perf_counter_ns()
            (
                timings.configure_yoga_ns,
                timings.compute_yoga_ns,
                timings.apply_layout_ns,
                timings.update_layout_hooks_ns,
                needs_layout,
                layout_repaint_facts,
            ) = renderer._update_layout(renderer._root, delta_time)
            timings.layout_ns = _time.perf_counter_ns() - t_layout
        except Exception:
            _log.exception("Error updating layout")
            layout_failed = True
            renderer._force_next_render = True
            if renderer._root is not None:
                renderer._root.mark_dirty()

    if renderer._force_next_render and renderer._root and _log.isEnabledFor(logging.DEBUG):
        _log.debug(
            "=== FIRST FRAME === layout=%s failed=%s %dx%d",
            needs_layout,
            layout_failed,
            renderer._width,
            renderer._height,
        )
        renderer._debug_dump_tree(renderer._root, max_depth=16)

    if not layout_failed:
        t_mount = _time.perf_counter_ns()
        hooks.flush_mount_callbacks()
        timings.mount_callbacks_ns = _time.perf_counter_ns() - t_mount

    return needs_layout, layout_failed, layout_repaint_facts


def prepare_buffer(
    renderer: Any,
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
    t_buffer_prepare = t_buffer_lookup = _time.perf_counter_ns()
    buffer = renderer.get_next_buffer()
    timings.buffer_lookup_ns = _time.perf_counter_ns() - t_buffer_lookup
    reused_current_buffer = False
    repainted_dirty_common_tree = False
    repainted_layout_common_tree = False
    layout_common_plan: list[tuple[Any | None, tuple[int, int, int, int]]] | None = None

    if not needs_layout and renderer._can_reuse_current_buffer_frame():
        t_buffer_lookup = _time.perf_counter_ns()
        current = renderer.get_current_buffer()
        timings.buffer_lookup_ns += _time.perf_counter_ns() - t_buffer_lookup
        try:
            t_replay = _time.perf_counter_ns()
            buffer._native.draw_frame_buffer(buffer._ptr, 0, 0, current._ptr)
            timings.buffer_replay_ns = _time.perf_counter_ns() - t_replay
            reused_current_buffer = True
        except Exception:
            reused_current_buffer = False
    elif not needs_layout and not layout_failed and renderer._can_incremental_common_tree_repaint():
        t_buffer_lookup = _time.perf_counter_ns()
        current = renderer.get_current_buffer()
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
        repaint_plan = renderer._compute_layout_common_repaint_plan(layout_repaint_facts or [])
        timings.repaint_plan_ns = _time.perf_counter_ns() - t_plan
        if repaint_plan:
            t_buffer_lookup = _time.perf_counter_ns()
            current = renderer.get_current_buffer()
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

    if not reused_current_buffer and not repainted_dirty_common_tree and not repainted_layout_common_tree:
        buffer.clear()
        if renderer._clear_color:
            buffer.fill_rect(0, 0, renderer._width, renderer._height, renderer._clear_color)
    timings.buffer_prepare_ns = _time.perf_counter_ns() - t_buffer_prepare

    return (
        buffer,
        reused_current_buffer,
        repainted_dirty_common_tree,
        repainted_layout_common_tree,
        layout_common_plan,
    )


__all__ = ["compute_layout", "prepare_buffer", "run_frame_callbacks"]
