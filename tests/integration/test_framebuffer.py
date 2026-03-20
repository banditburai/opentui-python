"""FrameBuffer integration tests."""

from __future__ import annotations

import pytest

from opentui import FrameBuffer, Renderable, create_test_renderer


class _CountingRenderable(Renderable):
    def __init__(self, counter: list[int], **kwargs):
        super().__init__(**kwargs)
        self._counter = counter

    def render(self, buffer, delta_time: float = 0) -> None:
        self._counter[0] += 1
        buffer.draw_text("X", self._x, self._y)


@pytest.mark.asyncio
async def test_framebuffer_reuses_cached_subtree_when_clean():
    setup = await create_test_renderer(20, 5)
    try:
        root = setup.renderer.root
        counter = [0]
        fb = FrameBuffer(width=10, height=1)
        child = _CountingRenderable(counter, width=1, height=1)
        fb.add(child)
        root.add(fb)

        setup.render_frame()
        assert counter[0] == 1

        setup.render_frame()
        assert counter[0] == 1

        child.mark_paint_dirty()
        setup.render_frame()
        assert counter[0] == 2
    finally:
        setup.destroy()
