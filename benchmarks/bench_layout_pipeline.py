"""Focused layout-pipeline benchmarks for OpenTUI Python.

Run with:
  uv run python benchmarks/bench_layout_pipeline.py
"""

from __future__ import annotations

import asyncio
import time

from opentui import Box, Text, create_test_renderer

try:
    from benchmarks.harness import FRAME_BUCKETS, collect_frame_medians
except ImportError:
    from harness import FRAME_BUCKETS, collect_frame_medians

# Display subset for this benchmark
_DISPLAY_BUCKETS = (
    "layout_ns",
    "configure_yoga_ns",
    "compute_yoga_ns",
    "apply_layout_ns",
    "mount_callbacks_ns",
    "buffer_prepare_ns",
    "buffer_lookup_ns",
    "repaint_plan_ns",
    "buffer_replay_ns",
    "render_tree_ns",
    "flush_ns",
    "post_render_ns",
    "frame_finish_ns",
    "total_ns",
)


async def _run() -> None:
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root
    container = Box(width=120, height=40, flex_direction="column")
    rows = []
    for i in range(300):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=20))
        row.add(Text("x" * 40, flex_grow=1))
        rows.append(row)
        container.add(row)
    root.add(container)

    # Warmup
    setup.render_frame()

    # Paint-only mutate
    paint_index = [0]

    def paint_mutate():
        paint_index[0] += 1
        rows[paint_index[0] % len(rows)]._children[0].fg = (
            "#ff0000" if paint_index[0] % 2 else "#00ff00"
        )

    paint_medians = collect_frame_medians(
        setup, paint_mutate, 50,
        buckets=FRAME_BUCKETS,
        label_prefix="layout_pipeline: paint",
    )

    # Layout mutate
    target = rows[0]._children[1]
    layout_index = [0]

    def layout_mutate():
        layout_index[0] += 1
        target.width = 41 if layout_index[0] % 2 else 40

    layout_medians = collect_frame_medians(
        setup, layout_mutate, 50,
        buckets=FRAME_BUCKETS,
        label_prefix="layout_pipeline: layout",
    )

    print("Layout pipeline benchmark")
    print(f"captured at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    for label, medians in [("paint", paint_medians), ("layout", layout_medians)]:
        print(label)
        for bucket in _DISPLAY_BUCKETS:
            print(f"  {bucket:<18} median={medians[bucket]:>8,}ns")

    setup.destroy()


if __name__ == "__main__":
    asyncio.run(_run())
