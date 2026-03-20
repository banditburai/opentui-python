"""FrameBuffer component for offscreen rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..enums import RenderStrategy
from ..ffi import get_native, is_native_available
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


class FrameBuffer(Renderable):
    """Offscreen rendering buffer that composites to parent buffer.

    Renders children into an internal buffer, then composites the result
    to the parent buffer during render. Useful for caching, clipping,
    or applying effects to a subtree.

    Example:
        fb = FrameBuffer(width=40, height=10)
        fb.add(Text("Hello from offscreen!"))
    """

    def __init__(self, *, internal_buffer: Any = None, **kwargs: Any):
        super().__init__(**kwargs)
        self._internal_buffer = internal_buffer
        self._owned_internal_buffer_ptr: Any = None
        self._owned_internal_buffer_size: tuple[int, int] | None = None
        self._layer_dirty: bool = True

    @property
    def internal_buffer(self) -> Any:
        return self._internal_buffer

    @internal_buffer.setter
    def internal_buffer(self, value: Any) -> None:
        self._release_owned_internal_buffer()
        self._internal_buffer = value
        self._layer_dirty = True

    def get_render_strategy(self) -> RenderStrategy:
        return RenderStrategy.RETAINED_LAYER

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        target = self._ensure_internal_buffer(buffer)
        rerender_subtree = (
            target is buffer
            or self._internal_buffer is None
            or self._layer_dirty
            or bool(self._dirty)
            or bool(self._subtree_dirty)
            or bool(getattr(self, "_paint_subtree_dirty", False))
        )

        if rerender_subtree:
            if target is not buffer:
                target.clear(0.0)
                target.push_offset(-self._x, -self._y)
            try:
                for child in self._children:
                    child.render(target, delta_time)
            finally:
                if target is not buffer:
                    target.pop_offset()
            self._layer_dirty = False

        if target is not buffer:
            self._composite_to(buffer)

        if self._render_after:
            self._render_after(buffer, delta_time, self)

    def destroy(self) -> None:
        self._release_owned_internal_buffer()
        super().destroy()

    def _ensure_internal_buffer(self, buffer: Buffer) -> Buffer:
        if self._internal_buffer is not None:
            width = max(0, int(self._layout_width or 0))
            height = max(0, int(self._layout_height or 0))
            if width > 0 and height > 0 and hasattr(self._internal_buffer, "resize"):
                current_size = (
                    getattr(self._internal_buffer, "width", None),
                    getattr(self._internal_buffer, "height", None),
                )
                if current_size != (width, height):
                    self._internal_buffer.resize(width, height)
            return self._internal_buffer

        width = max(0, int(self._layout_width or 0))
        height = max(0, int(self._layout_height or 0))
        if width <= 0 or height <= 0 or not is_native_available():
            return buffer

        if self._owned_internal_buffer_ptr is None:
            native = get_native()
            ptr = native.buffer.create_optimized_buffer(width, height, True, 0, f"fb-{self.id}")
            from ..renderer import Buffer as RenderBuffer

            self._owned_internal_buffer_ptr = ptr
            self._internal_buffer = RenderBuffer(ptr, native.buffer, native.graphics)
            self._owned_internal_buffer_size = (width, height)
            self._layer_dirty = True
            return self._internal_buffer

        if self._owned_internal_buffer_size != (width, height):
            self._internal_buffer.resize(width, height)
            self._owned_internal_buffer_size = (width, height)
            self._layer_dirty = True

        return self._internal_buffer

    def _release_owned_internal_buffer(self) -> None:
        if self._owned_internal_buffer_ptr is None or not is_native_available():
            self._owned_internal_buffer_ptr = None
            self._owned_internal_buffer_size = None
            return
        try:
            native = get_native()
            native.buffer.destroy_optimized_buffer(self._owned_internal_buffer_ptr)
        except Exception:
            pass
        finally:
            self._owned_internal_buffer_ptr = None
            self._owned_internal_buffer_size = None
            self._layer_dirty = True
            if self._internal_buffer is not None:
                self._internal_buffer = None

    def _composite_to(self, buffer: Buffer) -> None:
        ib = self._internal_buffer
        if ib is None:
            return

        try:
            native = buffer._native
            native.draw_frame_buffer(buffer._ptr, self._x, self._y, ib._ptr)
            return
        except (AttributeError, TypeError):
            pass

        try:
            lines = ib.get_span_lines()
            for row_idx, line in enumerate(lines):
                text = line.get("text", "")
                if text:
                    buffer.draw_text(text, self._x, self._y + row_idx)
        except Exception:
            pass


__all__ = ["FrameBuffer"]
