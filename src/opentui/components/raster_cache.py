"""Retained raster buffer cache for offscreen rendering."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..native import _nb

if TYPE_CHECKING:
    from ..renderer.buffer import Buffer


class RasterCache:
    """Manages a retained offscreen buffer with dirty-flag caching.

    Usage in a renderable::

        self._raster = RasterCache(f"diff-{self.id}")

        # In render():
        self._raster.render_cached(buffer, self._x, self._y,
                                   self._layout_width, self._layout_height,
                                   self._render_contents)

        # In destroy():
        self._raster.release()
    """

    __slots__ = ("_buffer", "_ptr", "_size", "_dirty", "_id")

    def __init__(self, buffer_id: str = "") -> None:
        self._buffer: Buffer | None = None
        self._ptr: Any = None
        self._size: tuple[int, int] | None = None
        self._dirty = True
        self._id = buffer_id

    @property
    def dirty(self) -> bool:
        return self._dirty

    def invalidate(self) -> None:
        self._dirty = True

    def ensure(self, width: int, height: int) -> Buffer | None:
        """Ensure buffer exists at the given size. Returns None for degenerate sizes."""
        if width <= 0 or height <= 0:
            return None

        if self._ptr is None:
            from ..renderer.buffer import Buffer as RenderBuffer

            ptr = _nb.buffer.create_optimized_buffer(width, height, True, 0, self._id)
            self._ptr = ptr
            self._buffer = RenderBuffer(ptr, _nb.buffer, _nb.graphics)
            self._size = (width, height)
            self._dirty = True
            return self._buffer

        if self._size != (width, height):
            assert self._buffer is not None
            self._buffer.resize(width, height)
            self._size = (width, height)
            self._dirty = True

        return self._buffer

    def mark_clean(self) -> None:
        self._dirty = False

    def render_cached(
        self,
        buffer: Buffer,
        x: int,
        y: int,
        width: int | None,
        height: int | None,
        render_fn: Callable[[Buffer], None],
    ) -> None:
        """Render using the cached offscreen buffer, falling back to direct rendering.

        Encapsulates the ensure -> clear -> push_offset -> render -> pop_offset ->
        mark_clean -> draw_frame_buffer pattern shared by multiple renderables.
        """
        w = max(0, int(width or 0))
        h = max(0, int(height or 0))
        raster = self.ensure(w, h)
        if raster is not None:
            if self._dirty:
                raster.clear(0.0)
                raster.push_offset(-x, -y)
                try:
                    render_fn(raster)
                finally:
                    raster.pop_offset()
                self._dirty = False

            try:
                buffer._native.draw_frame_buffer(buffer._ptr, x, y, raster._ptr)
                return
            except Exception:
                pass

        render_fn(buffer)
        self._dirty = False

    def release(self) -> None:
        if self._ptr is None:
            return
        try:
            _nb.buffer.destroy_optimized_buffer(self._ptr)
        except Exception:
            pass
        finally:
            self._buffer = None
            self._ptr = None
            self._size = None
