"""Image component."""

import hashlib
import logging
import math
import os

from ..image.encoding import ImageRenderer

_log = logging.getLogger(__name__)
from ..image.loader import load_image
from ..image.types import DecodedImage, ImageFit, ImageProtocol, ImageSource, resize_rgba_nearest
from ..renderer import TerminalCapabilities
from ..renderer.buffer import Buffer
from .base import Renderable


def _env_protocol_override() -> ImageProtocol | None:
    value = os.environ.get("OPENTUI_IMAGE_PROTOCOL", "").strip().lower()
    if value in {"kitty", "sixel", "ascii", "grayscale"}:
        return ImageProtocol(value)
    return None


def _auto_image_capabilities() -> TerminalCapabilities:
    override = _env_protocol_override()
    if override == ImageProtocol.KITTY:
        return TerminalCapabilities(kitty_graphics=True)
    if override == ImageProtocol.SIXEL:
        return TerminalCapabilities(sixel=True)
    if override in {ImageProtocol.ASCII, ImageProtocol.GRAYSCALE}:
        return TerminalCapabilities()

    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if os.environ.get("KITTY_WINDOW_ID"):
        return TerminalCapabilities(kitty_graphics=True)
    if any(token in term for token in ("kitty", "ghostty", "wezterm")):
        return TerminalCapabilities(kitty_graphics=True)
    if term_program in {"wezterm", "iterm.app", "ghostty"}:
        return TerminalCapabilities(kitty_graphics=True)
    return TerminalCapabilities()


def _protocol_capabilities(protocol: ImageProtocol) -> TerminalCapabilities:
    if protocol == ImageProtocol.KITTY:
        return TerminalCapabilities(kitty_graphics=True)
    if protocol == ImageProtocol.SIXEL:
        return TerminalCapabilities(sixel=True)
    if protocol == ImageProtocol.AUTO:
        return _auto_image_capabilities()
    return TerminalCapabilities()


def _source_key(source: ImageSource) -> str:
    if source.path is not None:
        return f"path:{source.path}|mime:{source.mime_type or ''}"
    if source.data is not None:
        digest = hashlib.sha1(source.data).hexdigest()
        return f"bytes:{digest}|mime:{source.mime_type or ''}"
    return "empty"


class ImageCache:
    """Caches decoded images and resized variants."""

    def __init__(self):
        self._decoded: dict[str, DecodedImage] = {}
        self._variants: dict[tuple[str, int, int], bytes] = {}

    @property
    def decoded_count(self) -> int:
        return len(self._decoded)

    @property
    def variant_count(self) -> int:
        return len(self._variants)

    def get_decoded(self, source: ImageSource, loader, *, key: str | None = None) -> DecodedImage:
        k = key if key is not None else _source_key(source)
        cached = self._decoded.get(k)
        if cached is not None:
            return cached
        decoded = loader()
        self._decoded[k] = decoded
        return decoded

    _VARIANT_MAX = 32

    def get_variant(self, decoded: DecodedImage, width: int, height: int, scaler) -> bytes:
        source = decoded.source or ImageSource(data=decoded.data, mime_type=decoded.mime_type)
        key = (_source_key(source), width, height)
        cached = self._variants.get(key)
        if cached is not None:
            return cached
        variant = scaler()
        if len(self._variants) >= self._VARIANT_MAX:
            # Evict oldest half when cache is full (dict preserves insertion order).
            excess = len(self._variants) - self._VARIANT_MAX // 2
            for k in list(self._variants.keys())[:excess]:
                del self._variants[k]
        self._variants[key] = variant
        return variant

    def clear(self) -> None:
        self._decoded.clear()
        self._variants.clear()


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
        # Split draw cache into intrinsic params (data identity) and position
        # so scroll-only changes skip the expensive clear+retransmit cycle.
        self._last_intrinsic: tuple[ImageSource, int, int, ImageProtocol] | None = None
        self._last_draw_pos: tuple[int, int] | None = None
        self._graphics_id: int | None = None
        self._was_suppressed: bool = False
        self._cache = ImageCache()
        # Cache immutable per-instance lookups to avoid per-frame overhead.
        self._cached_source_key = _source_key(self._source)
        self._cached_capabilities: TerminalCapabilities | None = None
        self.on_cleanup(self._cache.clear)
        self.on_cleanup(self._clear_graphics_on_destroy)

    def _register_active_graphics(self) -> None:
        if self._graphics_id is not None:
            from ..hooks import get_renderer

            cli = get_renderer()
            if cli is not None:
                cli.register_frame_graphics(self._graphics_id)

    def _clear_graphics_on_destroy(self) -> None:
        if self._graphics_id is not None:
            import sys

            try:
                from ..image.encoding import _clear_kitty_graphics

                sys.stdout.buffer.write(_clear_kitty_graphics(self._graphics_id))
                sys.stdout.buffer.flush()
            except Exception:
                _log.debug("failed to clear kitty graphics id=%s", self._graphics_id, exc_info=True)
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
        height = (
            int(self._layout_height) if self._layout_height else int(self._height or decoded_height)
        )
        return max(1, width), max(1, height)

    def _fit_size(
        self, src_width: int, src_height: int, box_width: int, box_height: int
    ) -> tuple[int, int]:
        if self._fit == ImageFit.FILL:
            return box_width, box_height
        if self._fit == ImageFit.NONE:
            return min(src_width, box_width), min(src_height, box_height)

        if src_width == 0 or src_height == 0:
            return (0, 0)

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
        if not self._visible and self._graphics_id is not None and self._last_intrinsic is not None:
            self._clear_graphics_on_destroy()
            self._last_intrinsic = None
            self._last_draw_pos = None
            return

        try:
            self._decoded = self._cache.get_decoded(
                self._source,
                lambda: load_image(self._source),
                key=self._cached_source_key,
            )
            decoded = self._decoded
            box_width, box_height = self._resolve_box(decoded.width, decoded.height)
            if self._cached_capabilities is None:
                self._cached_capabilities = _protocol_capabilities(self._protocol)
            capabilities = self._cached_capabilities
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
                    self._last_intrinsic = None
                    self._last_draw_pos = None

            if use_graphics_protocol:
                width, height = self._fit_graphics_cells(
                    decoded.width, decoded.height, box_width, box_height
                )
            else:
                width, height = self._fit_size(decoded.width, decoded.height, box_width, box_height)
            x = self._x + max(0, (box_width - width) // 2)
            y = self._y + max(0, (box_height - height) // 2)

            # For graphics protocols (Kitty/SIXEL), translate layout
            # coordinates to screen coordinates using the buffer's drawing
            # offset.  Kitty/SIXEL use absolute terminal cursor positioning
            # so the image must stay within the visible viewport.
            draw_x, draw_y = x, y
            if use_graphics_protocol:
                buf_offset = buffer.get_offset()
                draw_x += buf_offset[0]
                draw_y += buf_offset[1]

                # Determine the visible rect: scissor if inside a scroll
                # container, otherwise the full buffer.
                scissor = buffer.get_scissor_rect()
                if scissor is not None:
                    vx, vy, vw, vh = scissor
                else:
                    vx, vy, vw, vh = 0, 0, buffer.width, buffer.height

                # Clamp the layout box to the visible viewport and re-fit
                # the image proportionally.  This ensures the image always
                # renders at whatever size fits on screen (e.g. after a
                # terminal resize) rather than disappearing entirely.
                box_sx = self._x + buf_offset[0]
                box_sy = self._y + buf_offset[1]
                eff_left = max(vx, box_sx)
                eff_top = max(vy, box_sy)
                eff_w = min(box_sx + box_width, vx + vw) - eff_left
                eff_h = min(box_sy + box_height, vy + vh) - eff_top

                if eff_w <= 0 or eff_h <= 0:
                    if self._graphics_id is not None and self._last_intrinsic is not None:
                        renderer.clear_graphics(self._graphics_id)
                        self._last_intrinsic = None
                        self._last_draw_pos = None
                    return

                # Re-fit and re-center when the visible area is smaller
                # than the layout box (terminal narrower than image).
                if eff_w < box_width or eff_h < box_height:
                    width, height = self._fit_graphics_cells(
                        decoded.width,
                        decoded.height,
                        eff_w,
                        eff_h,
                    )
                    draw_x = eff_left + max(0, (eff_w - width) // 2)
                    draw_y = eff_top + max(0, (eff_h - height) // 2)

            intrinsic = (self._source, width, height, self._protocol)
            if capabilities.kitty_graphics:
                data = decoded.data
                source_width = decoded.width
                source_height = decoded.height
            else:
                data = self._cache.get_variant(
                    decoded,
                    width,
                    height,
                    lambda: resize_rgba_nearest(
                        decoded.data,
                        decoded.width,
                        decoded.height,
                        width,
                        height,
                    ),
                )
                source_width = width
                source_height = height
            if use_graphics_protocol:
                draw_pos = (draw_x, draw_y)
                if self._last_intrinsic == intrinsic and self._last_draw_pos == draw_pos:
                    # Completely unchanged — skip draw entirely.
                    self._register_active_graphics()
                    return
                if (
                    (self._last_intrinsic != intrinsic or self._last_draw_pos != draw_pos)
                    and self._graphics_id is not None
                    and self._last_intrinsic is not None
                ):
                    # Image data/size/position changed — clear old placement
                    # and retransmit.  We cannot use Kitty a=p (placement)
                    # because Ghostty's d=I deletes image data, not just
                    # placements, causing "ENOENT: image not found".
                    renderer.clear_graphics(self._graphics_id)
                if self._graphics_id is None:
                    self._graphics_id = self._allocate_graphics_id()
            if self._protocol == ImageProtocol.GRAYSCALE and renderer.draw_grayscale(
                data, draw_x, draw_y, width, height
            ):
                return
            if renderer.draw_image(
                data,
                draw_x,
                draw_y,
                width,
                height,
                graphics_id=self._graphics_id,
                source_width=source_width,
                source_height=source_height,
            ):
                if use_graphics_protocol:
                    self._last_intrinsic = intrinsic
                    self._last_draw_pos = (draw_x, draw_y)
                    self._register_active_graphics()
                return
        except Exception:
            _log.debug("image render failed, falling back to alt text", exc_info=True)

        if self._alt and hasattr(buffer, "draw_text"):
            buffer.draw_text(self._alt, self._x, self._y)


__all__ = ["Image"]
