from __future__ import annotations

import pytest

from opentui import Box, FrameBuffer, Text, create_test_renderer
from opentui.components.code_renderable import CodeRenderable
from opentui.components.diff_renderable import DiffRenderable
from opentui.components.markdown_renderable import MarkdownRenderable
from opentui.components.select_renderable import SelectRenderable
from opentui.components.text_table_renderable import TextTableRenderable
from opentui.components.textarea_renderable import TextareaRenderable
from opentui.enums import RenderStrategy
from opentui.renderer.layout import supports_common_tree_strategy


def test_box_uses_common_tree_strategy_when_simple() -> None:
    box = Box(border=True, title="hello")
    assert box.get_render_strategy() is RenderStrategy.COMMON_TREE


def test_box_uses_python_fallback_strategy_when_custom_border_chars_present() -> None:
    box = Box(
        border=True,
        border_chars={
            "top_left": "+",
            "top_right": "+",
            "bottom_left": "+",
            "bottom_right": "+",
            "horizontal": "-",
            "vertical": "|",
        },
    )
    assert box.get_render_strategy() is RenderStrategy.PYTHON_FALLBACK


def test_wrapped_text_uses_native_text_strategy() -> None:
    text = Text("alpha beta gamma", wrap_mode="word")
    assert text.get_render_strategy() is RenderStrategy.NATIVE_TEXT


def test_simple_text_uses_common_tree_strategy() -> None:
    text = Text("alpha", wrap_mode="none")
    assert text.get_render_strategy() is RenderStrategy.COMMON_TREE


def test_framebuffer_uses_retained_layer_strategy() -> None:
    layer = FrameBuffer(width=10, height=5)
    assert layer.get_render_strategy() is RenderStrategy.RETAINED_LAYER


def test_heavy_widgets_are_classified_explicitly() -> None:
    assert (
        TextTableRenderable(content=[[None]]).get_render_strategy() is RenderStrategy.HEAVY_WIDGET
    )
    assert MarkdownRenderable(content="hello").get_render_strategy() is RenderStrategy.HEAVY_WIDGET
    assert (
        CodeRenderable(content="x", filetype="python").get_render_strategy()
        is RenderStrategy.HEAVY_WIDGET
    )
    assert (
        TextareaRenderable(initial_value="x").get_render_strategy() is RenderStrategy.HEAVY_WIDGET
    )
    assert DiffRenderable(diff="").get_render_strategy() is RenderStrategy.HEAVY_WIDGET
    assert SelectRenderable().get_render_strategy() is RenderStrategy.HEAVY_WIDGET


@pytest.mark.asyncio
async def test_renderer_common_tree_strategy_rejects_retained_layers_and_heavy_widgets() -> None:
    setup = await create_test_renderer(30, 10)
    try:
        root = setup.renderer.root

        retained = FrameBuffer(width=10, height=3)
        retained.add(Text("cached", wrap_mode="none"))
        root.add(retained)
        assert supports_common_tree_strategy(root) is False

        root.remove(retained)
        table = TextTableRenderable(content=[[None]], width=10, height=3)
        root.add(table)
        assert supports_common_tree_strategy(root) is False
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_renderer_common_tree_strategy_accepts_simple_common_subtrees() -> None:
    setup = await create_test_renderer(30, 10)
    try:
        root = setup.renderer.root
        box = Box(width=10, height=3, border=True, title="ok")
        box.add(Text("plain", wrap_mode="none"))
        root.add(box)
        assert supports_common_tree_strategy(root) is True
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_layout_frame_repaints_promoted_common_subtree_root(monkeypatch) -> None:
    setup = await create_test_renderer(40, 10)
    try:
        renderer = setup.renderer
        root = renderer.root
        container = Box(width=20, height=3, flex_direction="row", border=True)
        left = Text("A", width=4, wrap_mode="none")
        right = Text("B", width=4, wrap_mode="none")
        container.add(left)
        container.add(right)
        root.add(container)

        setup.render_frame()

        calls: list[object] = []
        original = renderer._render_common_tree_unchecked_fast

        def wrapped(node, buffer):
            calls.append(node)
            return original(node, buffer)

        monkeypatch.setattr(renderer, "_render_common_tree_unchecked_fast", wrapped)

        left.width = 5
        setup.render_frame()

        assert container in calls
        assert root not in calls
        assert setup.renderer.get_current_buffer().get_plain_text().count("B") == 1
    finally:
        setup.destroy()
