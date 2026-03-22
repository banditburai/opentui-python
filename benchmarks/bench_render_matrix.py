"""Systematic render-path benchmark matrix for OpenTUI Python.

This benchmark is meant to guide architecture work, not just micro-tuning.
It focuses on broad render-path classes:

- plain container + single-line text trees
- wrapped text trees
- retained subtree/layer rendering
- heavy component-local raster caches
- mixed roots with multiple render strategies side by side

Reactivity-specific workloads already live in ``bench_reactivity.py``.

Run with:
  uv run python benchmarks/bench_render_matrix.py
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from opentui import (
    Box,
    FrameBuffer,
    LineNumberRenderable,
    SelectOption,
    Text,
    TextRenderable,
    create_test_renderer,
)
from opentui.components.control_flow import Portal
from opentui.components.diff_renderable import DiffRenderable
from opentui.components.markdown_renderable import MarkdownRenderable
from opentui.components.select_renderable import SelectRenderable
from opentui.components.text_table_renderable import TextTableRenderable

try:
    from benchmarks.harness import FRAME_BUCKETS, collect_frame_medians
except ImportError:
    from harness import FRAME_BUCKETS, collect_frame_medians

# Display subset: skip signal_handling_ns, update_layout_hooks_ns, post_render_ns
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
    "frame_finish_ns",
    "total_ns",
)


@dataclass(slots=True)
class Scenario:
    name: str
    category: str
    iterations: int
    build: Callable
    mutate: Callable | None = None


async def _plain_box_text_tree_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root
    container = Box(width=120, height=40, flex_direction="column")
    rows: list[Box] = []
    for i in range(300):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=20))
        row.add(Text("x" * 40, flex_grow=1))
        rows.append(row)
        container.add(row)
    root.add(container)
    return setup, {"rows": rows}


async def _plain_box_text_tree_paint():
    setup, refs = await _plain_box_text_tree_clean()
    rows = refs["rows"]
    index = [0]

    def mutate():
        row = rows[index[0] % len(rows)]
        text = row._children[0]
        text.fg = "#ff0000" if index[0] % 2 else "#00ff00"
        index[0] += 1

    return setup, mutate


async def _plain_box_text_background_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root
    container = Box(width=120, height=40, flex_direction="column")
    for i in range(300):
        row = Box(height=1, flex_direction="row", background_color="#112233")
        row.add(Text(f"row {i}", width=20))
        row.add(Text("x" * 40, flex_grow=1))
        container.add(row)
    root.add(container)
    return setup, {}


async def _plain_box_text_border_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root
    container = Box(width=120, height=40, flex_direction="column")
    for i in range(80):
        row = Box(height=3, flex_direction="row", border=True)
        row.add(Text(f"row {i}", width=12))
        row.add(Text("x" * 18, flex_grow=1))
        container.add(row)
    root.add(container)
    return setup, {}


async def _plain_box_text_tree_layout():
    setup, refs = await _plain_box_text_tree_clean()
    target = refs["rows"][0]._children[1]
    widths = [40, 41]
    index = [0]

    def mutate():
        index[0] = (index[0] + 1) % len(widths)
        target.width = widths[index[0]]

    return setup, mutate


async def _plain_box_text_shared_parent_layout():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root
    container = Box(width=120, height=40, flex_direction="column")
    rows: list[Box] = []
    for i in range(300):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"left {i}", width=12))
        row.add(Text(f"mid {i}", width=12))
        row.add(Text("x" * 30, flex_grow=1))
        rows.append(row)
        container.add(row)
    root.add(container)

    widths = [(12, 12), (10, 11)]
    index = [0]

    def mutate():
        row = rows[index[0] % len(rows)]
        pair = widths[index[0] % len(widths)]
        row._children[0].width = pair[0]
        row._children[1].width = pair[1]
        index[0] += 1

    return setup, mutate


async def _wrapped_text_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root
    container = Box(width=120, height=40, flex_direction="column")
    sample = (
        "This is a wrapped text node that should exercise the multiline "
        "rendering path and avoid selection handling. "
    )
    nodes: list[Text] = []
    for i in range(80):
        node = Text(sample + str(i), width=40, wrap_mode="word")
        nodes.append(node)
        container.add(node)
    root.add(container)
    return setup, {"nodes": nodes}


async def _wrapped_text_paint():
    setup, refs = await _wrapped_text_clean()
    nodes = refs["nodes"]
    index = [0]

    def mutate():
        node = nodes[index[0] % len(nodes)]
        node.fg = "#ffcc00" if index[0] % 2 else "#00ccff"
        index[0] += 1

    return setup, mutate


async def _retained_framebuffer_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root
    layer = FrameBuffer(width=120, height=40)
    container = Box(width=120, height=40, flex_direction="column")
    for i in range(160):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"item {i}", width=16))
        row.add(Text("cached subtree content", flex_grow=1))
        container.add(row)
    layer.add(container)
    root.add(layer)
    return setup, {}


async def _text_table_clean():
    setup = await create_test_renderer(100, 24)
    root = setup.renderer.root
    table = TextTableRenderable(
        content=[
            ["Name", "Role", "Status"],
            *[
                [f"User {i}", "Maintainer" if i % 3 == 0 else "Contributor", "Active"]
                for i in range(40)
            ],
        ],
        width=100,
        height=24,
    )
    root.add(table)
    return setup, {}


async def _diff_clean():
    setup = await create_test_renderer(100, 24)
    root = setup.renderer.root
    diff = DiffRenderable(
        diff="""\
--- a/example.py
+++ b/example.py
@@ -1,5 +1,5 @@
 def greet(name):
-    return f"hello {name}"
+    return f"hello, {name}"

-print(greet("world"))
+print(greet("team"))
""",
        width=100,
        height=24,
        view="unified",
        show_line_numbers=True,
    )
    root.add(diff)
    return setup, {}


async def _line_number_clean():
    setup = await create_test_renderer(100, 24)
    root = setup.renderer.root
    text = TextRenderable(
        content="\n".join(f"line {i} content that can wrap slightly" for i in range(80)),
        width="100%",
        height="100%",
        wrap_mode="char",
    )
    line_numbers = LineNumberRenderable(
        target=text,
        width=100,
        height=24,
        show_line_numbers=True,
    )
    root.add(line_numbers)
    return setup, {}


async def _select_clean():
    setup = await create_test_renderer(100, 24)
    root = setup.renderer.root
    select = SelectRenderable(
        options=[
            SelectOption(f"Option {i}", value=f"v{i}", description=f"Description {i}")
            for i in range(20)
        ],
        width=100,
        height=24,
        show_description=True,
    )
    root.add(select)
    return setup, {}


async def _markdown_clean():
    setup = await create_test_renderer(100, 24)
    root = setup.renderer.root
    markdown = MarkdownRenderable(
        content=(
            "# Heading\n\n"
            "This is a markdown paragraph with **formatting** and `inline code`.\n\n"
            "- item one\n"
            "- item two\n\n"
            "Another paragraph that should remain stable across clean frames."
        ),
        width=100,
        height=24,
    )
    root.add(markdown)
    return setup, {}


async def _mixed_root_common_plus_retained_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root

    common = Box(width=60, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("common subtree content", flex_grow=1, wrap_mode="none"))
        common.add(row)

    retained = FrameBuffer(width=60, height=40, left=60)
    retained_content = Box(width=60, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"cache {i}", width=16))
        row.add(Text("retained subtree content", flex_grow=1, wrap_mode="none"))
        retained_content.add(row)
    retained.add(retained_content)

    root.add(common)
    root.add(retained)
    return setup, {}


async def _mixed_root_common_plus_heavy_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root

    common = Box(width=60, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("common subtree content", flex_grow=1, wrap_mode="none"))
        common.add(row)

    table = TextTableRenderable(
        content=[
            ["Name", "Role", "Status"],
            *[
                [f"User {i}", "Maintainer" if i % 3 == 0 else "Contributor", "Active"]
                for i in range(20)
            ],
        ],
        width=60,
        height=40,
        left=60,
    )

    root.add(common)
    root.add(table)
    return setup, {}


async def _portal_overlay_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root

    page = Box(width=120, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("page content beneath modal overlay", flex_grow=1, wrap_mode="none"))
        page.add(row)

    modal_content = Box(
        width=48,
        height=16,
        left=36,
        top=8,
        position="absolute",
        border=True,
        background_color="#112233",
    )
    for i in range(10):
        modal_content.add(Text(f"Modal line {i}", width=40, left=2))

    portal = Portal(modal_content, mount=root, key="modal")
    page.add(portal)
    root.add(page)
    return setup, {}


async def _overlay_direct_clean():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root

    page = Box(width=120, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("page content beneath modal overlay", flex_grow=1, wrap_mode="none"))
        page.add(row)

    modal_content = Box(
        width=48,
        height=16,
        left=36,
        top=8,
        position="absolute",
        border=True,
        background_color="#112233",
    )
    for i in range(10):
        modal_content.add(Text(f"Modal line {i}", width=40, left=2))

    root.add(page)
    root.add(modal_content)
    return setup, {}


async def _overlay_direct_paint():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root

    page = Box(width=120, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("page content beneath modal overlay", flex_grow=1, wrap_mode="none"))
        page.add(row)

    modal_content = Box(
        width=48, height=16, left=36, top=8, border=True, background_color="#112233"
    )
    lines: list[Text] = []
    for i in range(10):
        line = Text(f"Modal line {i}", width=40, left=2)
        lines.append(line)
        modal_content.add(line)

    root.add(page)
    root.add(modal_content)

    index = [0]

    def mutate():
        line = lines[index[0] % len(lines)]
        line.fg = "#ffcc00" if index[0] % 2 else "#00ccff"
        index[0] += 1

    return setup, mutate


async def _overlay_direct_mount_toggle():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root

    page = Box(width=120, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("page content beneath modal overlay", flex_grow=1, wrap_mode="none"))
        page.add(row)
    root.add(page)

    state = {"overlay": None, "mounted": False, "counter": 0}

    def build_overlay() -> Box:
        modal_content = Box(
            width=48,
            height=16,
            left=36,
            top=8,
            position="absolute",
            border=True,
            background_color="#112233",
        )
        for i in range(10):
            modal_content.add(Text(f"Modal line {state['counter']}-{i}", width=40, left=2))
        state["counter"] += 1
        return modal_content

    overlay = build_overlay()
    root.add(overlay)
    state["overlay"] = overlay
    state["mounted"] = True

    def mutate():
        overlay = state["overlay"]
        if state["mounted"]:
            root.remove(overlay)
            overlay.destroy_recursively()
            state["overlay"] = None
            state["mounted"] = False
            return
        overlay = build_overlay()
        root.add(overlay)
        state["overlay"] = overlay
        state["mounted"] = True

    return setup, mutate


async def _portal_overlay_paint():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root

    page = Box(width=120, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("page content beneath modal overlay", flex_grow=1, wrap_mode="none"))
        page.add(row)

    modal_content = Box(
        width=48, height=16, left=36, top=8, border=True, background_color="#112233"
    )
    lines: list[Text] = []
    for i in range(10):
        line = Text(f"Modal line {i}", width=40, left=2)
        lines.append(line)
        modal_content.add(line)

    portal = Portal(modal_content, mount=root, key="modal")
    page.add(portal)
    root.add(page)

    index = [0]

    def mutate():
        line = lines[index[0] % len(lines)]
        line.fg = "#ffcc00" if index[0] % 2 else "#00ccff"
        index[0] += 1

    return setup, mutate


async def _portal_overlay_mount_toggle():
    setup = await create_test_renderer(120, 40)
    root = setup.renderer.root

    page = Box(width=120, height=40, flex_direction="column")
    for i in range(120):
        row = Box(height=1, flex_direction="row")
        row.add(Text(f"row {i}", width=16))
        row.add(Text("page content beneath modal overlay", flex_grow=1, wrap_mode="none"))
        page.add(row)
    root.add(page)

    state = {"portal": None, "mounted": False, "counter": 0}

    def build_portal() -> Portal:
        modal_content = Box(
            width=48,
            height=16,
            left=36,
            top=8,
            border=True,
            background_color="#112233",
        )
        for i in range(10):
            modal_content.add(Text(f"Modal line {state['counter']}-{i}", width=40, left=2))
        state["counter"] += 1
        return Portal(modal_content, mount=root, key="modal")

    portal = build_portal()
    page.add(portal)
    state["portal"] = portal
    state["mounted"] = True

    def mutate():
        portal = state["portal"]
        if state["mounted"]:
            page.remove(portal)
            portal.destroy()
            state["portal"] = None
            state["mounted"] = False
            return
        portal = build_portal()
        page.add(portal)
        state["portal"] = portal
        state["mounted"] = True

    return setup, mutate


_SCENARIOS = (
    Scenario("plain_box_text_clean", "common_nodes", 120, _plain_box_text_tree_clean),
    Scenario("plain_box_text_paint", "common_nodes", 120, _plain_box_text_tree_paint),
    Scenario(
        "plain_box_text_background_clean", "common_nodes", 120, _plain_box_text_background_clean
    ),
    Scenario("plain_box_text_border_clean", "common_nodes", 120, _plain_box_text_border_clean),
    Scenario("plain_box_text_layout", "common_nodes", 80, _plain_box_text_tree_layout),
    Scenario(
        "plain_box_text_shared_parent_layout",
        "common_nodes",
        80,
        _plain_box_text_shared_parent_layout,
    ),
    Scenario("wrapped_text_clean", "wrapped_text", 120, _wrapped_text_clean),
    Scenario("wrapped_text_paint", "wrapped_text", 120, _wrapped_text_paint),
    Scenario("retained_framebuffer_clean", "retained_layers", 120, _retained_framebuffer_clean),
    Scenario("text_table_clean", "heavy_components", 120, _text_table_clean),
    Scenario("diff_clean", "heavy_components", 120, _diff_clean),
    Scenario("line_number_clean", "heavy_components", 120, _line_number_clean),
    Scenario("select_clean", "heavy_components", 120, _select_clean),
    Scenario("markdown_clean", "heavy_components", 120, _markdown_clean),
    Scenario("overlay_direct_clean", "portal", 120, _overlay_direct_clean),
    Scenario("overlay_direct_paint", "portal", 120, _overlay_direct_paint),
    Scenario("overlay_direct_mount_toggle", "portal", 80, _overlay_direct_mount_toggle),
    Scenario("portal_overlay_clean", "portal", 120, _portal_overlay_clean),
    Scenario("portal_overlay_paint", "portal", 120, _portal_overlay_paint),
    Scenario("portal_overlay_mount_toggle", "portal", 80, _portal_overlay_mount_toggle),
    Scenario(
        "mixed_root_common_plus_retained_clean",
        "mixed_roots",
        120,
        _mixed_root_common_plus_retained_clean,
    ),
    Scenario(
        "mixed_root_common_plus_heavy_clean",
        "mixed_roots",
        120,
        _mixed_root_common_plus_heavy_clean,
    ),
)


async def _run_scenario(scenario: Scenario) -> tuple[str, str, dict[str, int]]:
    built = await scenario.build()
    if isinstance(built[1], dict):
        setup = built[0]
        mutate = None
    else:
        setup = built[0]
        mutate = built[1]
    try:
        medians = collect_frame_medians(
            setup,
            mutate,
            scenario.iterations,
            buckets=FRAME_BUCKETS,
            label_prefix=scenario.name,
        )
        return scenario.name, scenario.category, medians
    finally:
        setup.destroy()


async def _run() -> None:
    print("Render matrix benchmark")
    print(f"captured at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(
        "note: reactivity/control-flow workloads are covered separately in benchmarks/bench_reactivity.py"
    )
    for scenario in _SCENARIOS:
        name, category, result = await _run_scenario(scenario)
        print(f"\n{name} [{category}]")
        for bucket in _DISPLAY_BUCKETS:
            print(f"  {bucket:<18} median={result[bucket]:>8,}ns")


if __name__ == "__main__":
    asyncio.run(_run())
