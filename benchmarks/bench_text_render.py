"""Focused text-render benchmarks for OpenTUI Python.

Run with:
  uv run python benchmarks/bench_text_render.py
"""

from __future__ import annotations

import asyncio
import time

from opentui import Box, Text, create_test_renderer

try:
    from benchmarks.harness import collect_frame_medians
except ImportError:
    from harness import collect_frame_medians

_TEXT_RENDER_BUCKETS = ("total_ns", "render_tree_ns")


async def _bench_wrapped_text() -> dict[str, int]:
    setup = await create_test_renderer(120, 40)
    try:
        root = setup.renderer.root
        container = Box(width=120, height=40, flex_direction="column")
        sample = (
            "This is a wrapped text node that should exercise the multiline "
            "rendering path and avoid selection handling. "
        )
        for i in range(80):
            container.add(Text(sample + str(i), width=40, wrap_mode="word"))
        root.add(container)

        return collect_frame_medians(
            setup, None, 300,
            buckets=_TEXT_RENDER_BUCKETS,
            label_prefix="text_render: wrapped_text",
        )
    finally:
        setup.destroy()


async def _run() -> None:
    wrapped = await _bench_wrapped_text()
    print("Text render benchmark")
    print(f"captured at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("wrapped_text")
    for bucket, value in wrapped.items():
        print(f"  {bucket:<18} median={value:>8,}ns")


if __name__ == "__main__":
    asyncio.run(_run())
