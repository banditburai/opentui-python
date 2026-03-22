"""Integration tests for the lightweight Text component."""

from __future__ import annotations

import pytest

from opentui import Box, Text, create_test_renderer


@pytest.mark.asyncio
async def test_text_reuses_wrap_cache_when_clean(monkeypatch):
    import opentui.components.text as text_module

    setup = await create_test_renderer(20, 5)
    try:
        calls = {"wrap": 0}
        original_wrap = text_module.wrap_text

        def counting_wrap(*args, **kwargs):
            calls["wrap"] += 1
            return original_wrap(*args, **kwargs)

        monkeypatch.setattr(text_module, "wrap_text", counting_wrap)

        root = setup.renderer.root
        box = Box(width=10, height=3)
        box.add(Text("alpha beta gamma", wrap_mode="word"))
        root.add(box)
        setup.render_frame()
        assert "alpha" in setup.get_buffer().get_plain_text()

        first_calls = calls["wrap"]
        setup.render_frame()
        assert calls["wrap"] == first_calls
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_common_render_fast_path_accepts_plain_box_text_tree():
    setup = await create_test_renderer(40, 6)
    try:
        root = setup.renderer.root
        box = Box(width=40, height=6, flex_direction="column")
        box.add(Text("alpha", width=10))
        box.add(Text("beta", width=10))
        root.add(box)
        setup.render_frame()

        fast = setup.renderer._render_common_tree_fast(root, setup.renderer.get_next_buffer())
        assert fast is True
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_common_render_fast_path_rejects_wrapped_text_tree():
    setup = await create_test_renderer(20, 6)
    try:
        root = setup.renderer.root
        box = Box(width=10, height=6)
        box.add(Text("alpha beta gamma", wrap_mode="word"))
        root.add(box)
        setup.render_frame()

        fast = setup.renderer._render_common_tree_fast(root, setup.renderer.get_next_buffer())
        assert fast is False
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_common_render_fast_path_handles_default_fg_without_crashing():
    setup = await create_test_renderer(20, 4)
    try:
        root = setup.renderer.root
        root.add(Text("plain", width=5))

        frame = setup.capture_char_frame()
        assert "plain" in frame

        fast = setup.renderer._render_common_tree_fast(root, setup.renderer.get_next_buffer())
        assert fast is True
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_common_render_fast_path_handles_explicit_background():
    setup = await create_test_renderer(20, 4)
    try:
        root = setup.renderer.root
        root.add(Text("with-bg", width=7, bg="#112233"))

        frame = setup.capture_char_frame()
        assert "with-bg" in frame

        fast = setup.renderer._render_common_tree_fast(root, setup.renderer.get_next_buffer())
        assert fast is True
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_common_render_fast_path_handles_box_background():
    setup = await create_test_renderer(20, 4)
    try:
        root = setup.renderer.root
        box = Box(width=20, height=4, background_color="#223344")
        box.add(Text("boxed", width=5))
        root.add(box)

        frame = setup.capture_char_frame()
        assert "boxed" in frame

        fast = setup.renderer._render_common_tree_fast(root, setup.renderer.get_next_buffer())
        assert fast is True
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_common_render_fast_path_handles_simple_box_border():
    setup = await create_test_renderer(20, 6)
    try:
        root = setup.renderer.root
        box = Box(width=12, height=4, border=True)
        box.add(Text("edge", width=4))
        root.add(box)

        frame = setup.capture_char_frame()
        assert "┌" in frame
        assert "┐" in frame
        assert "edge" in frame

        fast = setup.renderer._render_common_tree_fast(root, setup.renderer.get_next_buffer())
        assert fast is True
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_common_render_fast_path_handles_box_title_and_partial_border():
    setup = await create_test_renderer(24, 6)
    try:
        root = setup.renderer.root
        box = Box(
            width=16,
            height=4,
            border=True,
            border_left=False,
            title="head",
            title_alignment="center",
        )
        box.add(Text("body", width=4))
        root.add(box)

        frame = setup.capture_char_frame()
        assert "head" in frame
        assert "body" in frame

        fast = setup.renderer._render_common_tree_fast(root, setup.renderer.get_next_buffer())
        assert fast is True
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_clean_common_tree_frame_reuses_current_buffer(monkeypatch):
    setup = await create_test_renderer(40, 6)
    try:
        root = setup.renderer.root
        box = Box(width=40, height=6, flex_direction="column")
        box.add(Text("alpha", width=10))
        box.add(Text("beta", width=10))
        root.add(box)
        setup.render_frame()

        calls = {"copy": 0}
        native_buffer = setup.renderer._native.buffer
        original_draw_frame_buffer = native_buffer.draw_frame_buffer

        def counting_draw_frame_buffer(*args, **kwargs):
            calls["copy"] += 1
            return original_draw_frame_buffer(*args, **kwargs)

        monkeypatch.setattr(native_buffer, "draw_frame_buffer", counting_draw_frame_buffer)

        setup.render_frame()
        assert calls["copy"] == 1
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_layout_common_tree_frame_reuses_current_buffer_for_top_level_child_move(monkeypatch):
    setup = await create_test_renderer(20, 4)
    try:
        root = setup.renderer.root
        row = Box(width=20, height=1, flex_direction="row")
        left = Text("AAAAA", width=5)
        right = Text("BBBBB", width=5)
        row.add(left)
        row.add(right)
        root.add(row)
        setup.render_frame()

        calls = {"copy": 0, "clear": 0}
        native_buffer = setup.renderer._native.buffer
        original_draw_frame_buffer = native_buffer.draw_frame_buffer
        original_clear = native_buffer.buffer_clear

        def counting_draw_frame_buffer(*args, **kwargs):
            calls["copy"] += 1
            return original_draw_frame_buffer(*args, **kwargs)

        def counting_clear(*args, **kwargs):
            calls["clear"] += 1
            return original_clear(*args, **kwargs)

        monkeypatch.setattr(native_buffer, "draw_frame_buffer", counting_draw_frame_buffer)
        monkeypatch.setattr(native_buffer, "buffer_clear", counting_clear)

        left.width = 3
        setup.render_frame()

        assert calls["copy"] == 1
        assert calls["clear"] == 0
        assert setup.get_buffer().get_plain_text().splitlines()[0].startswith("AAABBBBB")
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_layout_common_tree_frame_reuses_current_buffer_for_shared_parent_sibling_moves(
    monkeypatch,
):
    setup = await create_test_renderer(20, 4)
    try:
        root = setup.renderer.root
        row = Box(width=20, height=1, flex_direction="row")
        left = Text("AAAAA", width=5)
        middle = Text("MMMMM", width=5)
        right = Text("BBBBB", width=5)
        row.add(left)
        row.add(middle)
        row.add(right)
        root.add(row)
        setup.render_frame()

        calls = {"copy": 0, "clear": 0}
        native_buffer = setup.renderer._native.buffer
        original_draw_frame_buffer = native_buffer.draw_frame_buffer
        original_clear = native_buffer.buffer_clear

        def counting_draw_frame_buffer(*args, **kwargs):
            calls["copy"] += 1
            return original_draw_frame_buffer(*args, **kwargs)

        def counting_clear(*args, **kwargs):
            calls["clear"] += 1
            return original_clear(*args, **kwargs)

        monkeypatch.setattr(native_buffer, "draw_frame_buffer", counting_draw_frame_buffer)
        monkeypatch.setattr(native_buffer, "buffer_clear", counting_clear)

        left.width = 3
        middle.width = 4
        setup.render_frame()

        assert calls["copy"] == 1
        assert calls["clear"] == 0
        assert setup.get_buffer().get_plain_text().splitlines()[0].startswith("AAAMMMMBBBBB")
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_layout_common_tree_repaint_clears_stale_pixels_after_shrink():
    setup = await create_test_renderer(20, 4)
    try:
        root = setup.renderer.root
        row = Box(width=20, height=1, flex_direction="row")
        left = Text("AAAAA", width=5)
        right = Text("BBBBB", width=5)
        row.add(left)
        row.add(right)
        root.add(row)

        initial = setup.capture_char_frame()
        assert "AAAAABBBBB" in initial

        left.width = 3
        updated = setup.capture_char_frame()
        first_line = updated.splitlines()[0]

        assert first_line.startswith("AAABBBBB")
        assert "AAA  BBBBB" not in first_line
        assert "AAAAABBBBB" not in first_line
    finally:
        setup.destroy()


@pytest.mark.asyncio
async def test_layout_common_tree_reuses_current_buffer_for_direct_overlay_remove(monkeypatch):
    setup = await create_test_renderer(30, 8)
    try:
        root = setup.renderer.root
        page = Box(width=30, height=8, flex_direction="column")
        page.add(Text("background", width=10))
        overlay = Box(width=10, height=3, left=5, top=2, border=True)
        overlay.add(Text("modal", width=5))
        root.add(page)
        root.add(overlay)
        setup.render_frame()

        calls = {"copy": 0, "clear": 0}
        native_buffer = setup.renderer._native.buffer
        original_draw_frame_buffer = native_buffer.draw_frame_buffer
        original_clear = native_buffer.buffer_clear

        def counting_draw_frame_buffer(*args, **kwargs):
            calls["copy"] += 1
            return original_draw_frame_buffer(*args, **kwargs)

        def counting_clear(*args, **kwargs):
            calls["clear"] += 1
            return original_clear(*args, **kwargs)

        monkeypatch.setattr(native_buffer, "draw_frame_buffer", counting_draw_frame_buffer)
        monkeypatch.setattr(native_buffer, "buffer_clear", counting_clear)

        root.remove(overlay)
        overlay.destroy_recursively()
        setup.render_frame()

        assert calls["copy"] == 1
        assert calls["clear"] == 0
        assert "modal" not in setup.get_buffer().get_plain_text()
    finally:
        setup.destroy()
