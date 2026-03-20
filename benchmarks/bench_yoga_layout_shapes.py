"""Focused Yoga layout-shape benchmarks for OpenTUI Python.

Run with:
  uv run python benchmarks/bench_yoga_layout_shapes.py
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass

from opentui import Box, Text, create_test_renderer
from opentui import layout as yoga_layout

try:
    from benchmarks.harness import registry
except ImportError:
    from harness import registry


def _median(values: list[int]) -> int:
    values = sorted(values)
    return values[len(values) // 2]


@dataclass(slots=True)
class Scenario:
    name: str
    build: object


async def _build_plain_flow():
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
    root._configure_yoga_properties()
    return setup, rows


async def _build_absolute_overlay():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root
    page = Box(width=120, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("page content beneath modal overlay", flex_grow=1, wrap_mode="none"))
        page.add(row)
    overlay = Box(
        width=48,
        height=16,
        left=36,
        top=8,
        position="absolute",
        border=True,
        background_color="#112233",
    )
    for i in range(10):
        overlay.add(Text(f"Modal line {i}", width=40, left=2))
    root.add(page)
    root.add(overlay)
    root._configure_yoga_properties()
    return setup, overlay


def _time_compute(
    root, width: int, height: int, iterations: int = 80, *, label: str = "",
) -> dict[str, int]:
    samples: list[int] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        yoga_layout.compute_layout(root._yoga_node, float(width), float(height))
        samples.append(time.perf_counter_ns() - start)
    if label:
        registry.record(samples, label=label)
    return {
        "median_ns": _median(samples),
        "mean_ns": int(statistics.mean(samples)),
    }


def _time_mutating_compute(
    root,
    width: int,
    height: int,
    mutate,
    *,
    iterations: int = 80,
    label: str = "",
) -> dict[str, int]:
    samples: list[int] = []
    for i in range(iterations):
        mutate(i)
        root._configure_yoga_properties()
        start = time.perf_counter_ns()
        yoga_layout.compute_layout(root._yoga_node, float(width), float(height))
        samples.append(time.perf_counter_ns() - start)
    if label:
        registry.record(samples, label=label)
    return {
        "median_ns": _median(samples),
        "mean_ns": int(statistics.mean(samples)),
    }


async def _run() -> None:
    print("Yoga layout shape benchmark")
    print(f"captured at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    flow_setup, rows = await _build_plain_flow()
    try:
        target = rows[0]._children[1]
        width_toggle = _time_mutating_compute(
            flow_setup.renderer.root,
            120,
            40,
            lambda i: setattr(target, "width", 41 if i % 2 else 40),
            label="yoga: plain_flow width_toggle",
        )
        print("\nplain_flow")
        print(f"  width_toggle median={width_toggle['median_ns']:>8,}ns mean={width_toggle['mean_ns']:>8,}ns")
    finally:
        flow_setup.destroy()

    absolute_setup, overlay = await _build_absolute_overlay()
    try:
        root = absolute_setup.renderer.root

        state = {"overlay": overlay}

        def toggle_overlay(i: int) -> None:
            current = state["overlay"]
            if current is not None:
                root.remove(current)
                current.destroy_recursively()
                state["overlay"] = None
                return
            modal = Box(
                width=48,
                height=16,
                left=36,
                top=8,
                position="absolute",
                border=True,
                background_color="#112233",
            )
            for line in range(10):
                modal.add(Text(f"Modal line {i}-{line}", width=40, left=2))
            root.add(modal)
            state["overlay"] = modal

        toggle_case = _time_mutating_compute(
            root, 120, 40, toggle_overlay, label="yoga: absolute_overlay mount_toggle",
        )
        print("\nabsolute_overlay")
        print(f"  mount_toggle median={toggle_case['median_ns']:>8,}ns mean={toggle_case['mean_ns']:>8,}ns")
    finally:
        absolute_setup.destroy()


if __name__ == "__main__":
    asyncio.run(_run())
