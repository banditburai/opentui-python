"""Image component."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..filters import ImageRenderer
from ..image import ImageFit, ImageProtocol, ImageSource, resize_rgba_nearest
from ..image_cache import ImageCache
from ..image_loader import load_image
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


@dataclass(frozen=True, slots=True)
class _ImageCapabilities:
    kitty_graphics: bool = False
    sixel: bool = False


def _env_protocol_override() -> ImageProtocol | None:
    value = os.environ.get("OPENTUI_IMAGE_PROTOCOL", "").strip().lower()
    if value in {"kitty", "sixel", "ascii", "grayscale"}:
        return ImageProtocol(value)
    return None


def _auto_image_capabilities() -> _ImageCapabilities:
    override = _env_protocol_override()
    if override == ImageProtocol.KITTY:
        return _ImageCapabilities(kitty_graphics=True)
    if override == ImageProtocol.SIXEL:
        return _ImageCapabilities(sixel=True)
    if override in {ImageProtocol.ASCII, ImageProtocol.GRAYSCALE}:
        return _ImageCapabilities()

    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if os.environ.get("KITTY_WINDOW_ID"):
        return _ImageCapabilities(kitty_graphics=True)
    if any(token in term for token in ("kitty", "ghostty", "wezterm")):
        return _ImageCapabilities(kitty_graphics=True)
    if term_program in {"wezterm", "iterm.app", "ghostty"}:
        return _ImageCapabilities(kitty_graphics=True)
    return _ImageCapabilities()


def _protocol_capabilities(protocol: ImageProtocol) -> _ImageCapabilities:
    if protocol == ImageProtocol.KITTY:
        return _ImageCapabilities(kitty_graphics=True)
    if protocol == ImageProtocol.SIXEL:
        return _ImageCapabilities(sixel=True)
    if protocol == ImageProtocol.AUTO:
        return _auto_image_capabilities()
    return _ImageCapabilities()


class Image(Renderable):
    """Renderable image component with text fallback."""

    _next_graphics_id: int = 0
    _graphics_cell_height_ratio: float = 2.0

    def __init__(
        self,
        src: ImageSource | str | bytes,
        *,
        alt: str | None = None,
        fit: ImageFit | str = ImageFit.CONTAIN,
        protocol: ImageProtocol | str = ImageProtocol.AUTO,
        mime_type: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._source = ImageSource.from_value(src, mime_type=mime_type)
        self._alt = alt or ""
        self._fit = ImageFit(fit)
        self._protocol = ImageProtocol(protocol)
        self._decoded = None
        self._last_draw_signature: tuple[ImageSource, int, int, int, int, ImageProtocol] | None = None
        self._graphics_id: int | None = None
        self._was_suppressed: bool = False
        self._cache = ImageCache()
        self.on_cleanup(lambda: self._cache.clear())
        self.on_cleanup(self._clear_graphics_on_destroy)

    def _register_active_graphics(self) -> None:
        """Register this image's graphics ID with the renderer for stale tracking."""
        if self._graphics_id is not None:
            from ..hooks import get_renderer
            cli = get_renderer()
            if cli is not None:
                cli.register_frame_graphics(self._graphics_id)

    def _clear_graphics_on_destroy(self) -> None:
        if self._graphics_id is not None:
            import sys
            try:
                from ..filters import _clear_kitty_graphics
                sys.stdout.buffer.write(_clear_kitty_graphics(self._graphics_id))
                sys.stdout.buffer.flush()
            except Exception:
                pass
            self._graphics_id = None

    @property
    def source(self) -> ImageSource:
        return self._source

    @classmethod
    def _allocate_graphics_id(cls) -> int:
        cls._next_graphics_id += 1
        return cls._next_graphics_id

    def _resolve_box(self, decoded_width: int, decoded_height: int) -> tuple[int, int]:
        width = int(self._layout_width) if self._layout_width else int(self._width or decoded_width)
        height = int(self._layout_height) if self._layout_height else int(self._height or decoded_height)
        return max(1, width), max(1, height)

    def _fit_size(self, src_width: int, src_height: int, box_width: int, box_height: int) -> tuple[int, int]:
        if self._fit == ImageFit.FILL:
            return box_width, box_height
        if self._fit == ImageFit.NONE:
            return min(src_width, box_width), min(src_height, box_height)

        contain_scale = min(box_width / src_width, box_height / src_height)
        if self._fit == ImageFit.COVER:
            scale = max(box_width / src_width, box_height / src_height)
        elif self._fit == ImageFit.SCALE_DOWN:
            scale = min(1.0, contain_scale)
        else:
            scale = contain_scale

        return max(1, math.floor(src_width * scale)), max(1, math.floor(src_height * scale))

    def _fit_graphics_cells(
        self, src_width: int, src_height: int, box_width: int, box_height: int
    ) -> tuple[int, int]:
        """Fit an image into terminal cells while accounting for tall cell geometry."""
        if self._fit == ImageFit.FILL:
            return box_width, box_height
        if self._fit == ImageFit.NONE:
            return min(src_width, box_width), min(src_height, box_height)

        cell_w = 1.0
        cell_h = self._graphics_cell_height_ratio
        scale = min((box_width * cell_w) / src_width, (box_height * cell_h) / src_height)
        if self._fit == ImageFit.COVER:
            scale = max((box_width * cell_w) / src_width, (box_height * cell_h) / src_height)
        elif self._fit == ImageFit.SCALE_DOWN:
            scale = min(1.0, scale)

        width_cells = max(1, math.floor((src_width * scale) / cell_w))
        height_cells = max(1, math.floor((src_height * scale) / cell_h))
        return min(box_width, width_cells), min(box_height, height_cells)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the image or fallback alt text."""
        if not self._visible:
            if self._graphics_id is not None and self._last_draw_signature is not None:
                self._clear_graphics_on_destroy()
                self._last_draw_signature = None
            return

        try:
            self._decoded = self._cache.get_decoded(self._source, lambda: load_image(self._source))
            box_width, box_height = self._resolve_box(self._decoded.width, self._decoded.height)
            capabilities = _protocol_capabilities(self._protocol)
            renderer = ImageRenderer(buffer, capabilities)
            use_graphics_protocol = capabilities.kitty_graphics or capabilities.sixel

            # Check renderer-level suppression (e.g. overlay active).  When
            # suppressed we skip the graphics draw and don't register our ID,
            # so the stale-graphics tracker clears us automatically.  We
            # record the state so we can force a redraw when unsuppressed.
            if use_graphics_protocol:
                from ..hooks import get_renderer as _get_renderer
                cli = _get_renderer()
                suppressed = cli is not None and cli.graphics_suppressed
                if suppressed:
                    self._was_suppressed = True
                    # Show alt text while graphics are suppressed
                    if self._alt and hasattr(buffer, "draw_text"):
                        buffer.draw_text(self._alt, self._x, self._y)
                    return
                if self._was_suppressed:
                    # Transitioning from suppressed → active: force redraw
                    self._was_suppressed = False
                    self._last_draw_signature = None

            if use_graphics_protocol:
                width, height = self._fit_graphics_cells(
                    self._decoded.width, self._decoded.height, box_width, box_height
                )
            else:
                width, height = self._fit_size(self._decoded.width, self._decoded.height, box_width, box_height)
            x = self._x + max(0, (box_width - width) // 2)
            y = self._y + max(0, (box_height - height) // 2)
            draw_signature = (self._source, x, y, width, height, self._protocol)
            if capabilities.kitty_graphics:
                data = self._decoded.data
                source_width = self._decoded.width
                source_height = self._decoded.height
            else:
                data = self._cache.get_variant(
                    self._decoded,
                    width,
                    height,
                    lambda: resize_rgba_nearest(
                        self._decoded.data,
                        self._decoded.width,
                        self._decoded.height,
                        width,
                        height,
                    ),
                )
                source_width = width
                source_height = height
            if use_graphics_protocol:
                if self._last_draw_signature == draw_signature:
                    self._register_active_graphics()
                    return
                if self._last_draw_signature is not None and self._graphics_id is not None:
                    renderer.clear_graphics(self._graphics_id)
                if self._graphics_id is None:
                    self._graphics_id = self._allocate_graphics_id()
            if self._protocol == ImageProtocol.GRAYSCALE and renderer.draw_grayscale(data, x, y, width, height):
                return
            if renderer.draw_image(
                data,
                x,
                y,
                width,
                height,
                graphics_id=self._graphics_id,
                source_width=source_width,
                source_height=source_height,
            ):
                if use_graphics_protocol:
                    self._last_draw_signature = draw_signature
                    self._register_active_graphics()
                return
        except Exception:
            pass

        if self._alt and hasattr(buffer, "draw_text"):
            buffer.draw_text(self._alt, self._x, self._y)


__all__ = ["Image"]
