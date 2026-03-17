"""FrameBuffer component for offscreen rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

    @property
    def internal_buffer(self) -> Any:
        """Get the internal buffer (may be None if not initialized)."""
        return self._internal_buffer

    @internal_buffer.setter
    def internal_buffer(self, value: Any) -> None:
        self._internal_buffer = value

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render children to internal buffer, then composite to parent."""
        if not self._visible:
            return

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        target = self._internal_buffer if self._internal_buffer is not None else buffer

        for child in self._children:
            if isinstance(child, Renderable):
                child.render(target, delta_time)

        if self._internal_buffer is not None and self._internal_buffer is not buffer:
            self._composite_to(buffer)

        if self._render_after:
            self._render_after(buffer, delta_time, self)

    def _composite_to(self, buffer: Buffer) -> None:
        """Composite internal buffer to parent buffer at current position."""
        ib = self._internal_buffer
        if ib is None:
            return

        # Try native compositing first (draw_frame_buffer FFI)
        try:
            native = buffer._native
            native.buffer_draw_frame_buffer(buffer._ptr, ib._ptr, self._x, self._y)
            return
        except (AttributeError, TypeError):
            pass

        # Fallback: copy span lines from internal buffer to parent buffer
        try:
            lines = ib.get_span_lines()
            for row_idx, line in enumerate(lines):
                text = line.get("text", "")
                if text:
                    buffer.draw_text(text, self._x, self._y + row_idx)
        except Exception:
            pass


__all__ = ["FrameBuffer"]
