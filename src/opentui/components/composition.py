"""Composition components for OpenTUI Python."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


class VRenderable(Renderable):
    """Generic renderable that accepts a custom render function.

    Allows creating renderables with custom rendering logic without
    subclassing. The render function receives the buffer, delta time,
    and the VRenderable instance.

    Example:
        def my_render(buffer, dt, self):
            buffer.draw_text("Custom!", self.x, self.y)

        v = VRenderable(render_fn=my_render, width=20, height=1)
    """

    def __init__(
        self,
        *,
        render_fn: Callable[[Buffer, float, VRenderable], None] | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._render_fn = render_fn

    @property
    def render_fn(self) -> Callable | None:
        return self._render_fn

    @render_fn.setter
    def render_fn(self, value: Callable | None) -> None:
        self._render_fn = value
        self.mark_paint_dirty()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        if self._render_fn:
            self._render_fn(buffer, delta_time, self)

        for child in self._children:
            child.render(buffer, delta_time)

        if self._render_after:
            self._render_after(buffer, delta_time, self)


__all__ = ["VRenderable"]
