"""Retained raster buffer cache for offscreen rendering."""

import logging
from collections.abc import Callable
from typing import Any

from ..native import _nb
from ..renderer.buffer import Buffer

_log = logging.getLogger(__name__)


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
            ptr = _nb.buffer.create_optimized_buffer(width, height, True, 0, self._id)
            self._ptr = ptr
            self._buffer = Buffer(ptr, _nb.buffer, _nb.graphics)
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
                raster.clear()
                raster.push_offset(-x, -y)
                try:
                    render_fn(raster)
                finally:
                    raster.pop_offset()
                self._dirty = False

            try:
                # Apply the parent buffer's offset stack (e.g. ScrollBox scroll
                # offset) so the blit lands at the correct screen position.
                blit_x, blit_y = x, y
                if buffer._offset_stack:
                    dx, dy = buffer._offset_stack[-1]
                    blit_x += dx
                    blit_y += dy
                buffer._native.draw_frame_buffer(buffer._ptr, blit_x, blit_y, raster._ptr)
                return
            except Exception:
                _log.debug("raster cache blit failed, falling back to direct render", exc_info=True)

        render_fn(buffer)
        self._dirty = False

    def release(self) -> None:
        if self._ptr is None:
            return
        try:
            _nb.buffer.destroy_optimized_buffer(self._ptr)
        except Exception:
            _log.debug("failed to destroy optimized buffer %s", self._id, exc_info=True)
        finally:
            self._buffer = None
            self._ptr = None
            self._size = None
