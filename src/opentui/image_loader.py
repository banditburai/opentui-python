"""Image decoding and SVG rasterization helpers."""

from __future__ import annotations

import io
from pathlib import Path

from .image import DecodedImage, ImageSource


def _import_pillow_image():
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError("Pillow required for raster image loading") from exc
    return Image


def _import_cairosvg():
    try:
        import cairosvg  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError("cairosvg required for SVG rasterization") from exc
    return cairosvg


def _guess_mime_type(source: ImageSource) -> str | None:
    if source.mime_type:
        return source.mime_type
    if source.path:
        suffix = Path(source.path).suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }.get(suffix)
    if source.data:
        if source.data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if source.data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if source.data.lstrip().startswith(b"<svg"):
            return "image/svg+xml"
    return None


def _decode_raster(source: ImageSource, mime_type: str | None = None) -> DecodedImage:
    try:
        image_module = _import_pillow_image()
    except ImportError as exc:
        raise ImportError("Pillow required for raster image loading") from exc

    if source.data is not None:
        opened = image_module.open(io.BytesIO(source.data))
    elif source.path is not None:
        opened = image_module.open(source.path)
    else:
        raise ValueError("Image source must include path or data")

    with opened as img:
        converted = img.convert("RGBA") if img.mode != "RGBA" else img
        width, height = converted.size
        return DecodedImage(
            data=converted.tobytes(),
            width=width,
            height=height,
            mime_type=mime_type,
            source=source,
        )


def load_svg(
    value: ImageSource | str | bytes | Path,
    *,
    width: int | None = None,
    height: int | None = None,
    mime_type: str | None = "image/svg+xml",
) -> DecodedImage:
    """Rasterize SVG input and decode it to RGBA data."""
    if isinstance(value, str) and value.lstrip().startswith("<svg"):
        source = ImageSource.from_value(value.encode("utf-8"), mime_type=mime_type)
    else:
        source = ImageSource.from_value(value, mime_type=mime_type)
    try:
        cairosvg = _import_cairosvg()
    except ImportError as exc:
        raise ImportError("cairosvg required for SVG rasterization") from exc

    if source.data is not None:
        svg_bytes = source.data
    elif source.path is not None:
        svg_bytes = Path(source.path).read_bytes()
    else:
        raise ValueError("Image source must include path or data")

    png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_width=width, output_height=height)
    raster_source = ImageSource.from_value(png_bytes, mime_type="image/png")
    decoded = _decode_raster(raster_source, mime_type=mime_type)
    return DecodedImage(
        data=decoded.data,
        width=decoded.width,
        height=decoded.height,
        mime_type=mime_type,
        source=source,
    )


def load_image(
    value: ImageSource | str | bytes | Path,
    *,
    mime_type: str | None = None,
) -> DecodedImage:
    """Load an image source into RGBA bytes."""
    source = ImageSource.from_value(value, mime_type=mime_type)
    resolved_mime_type = _guess_mime_type(source)
    if resolved_mime_type == "image/svg+xml":
        return load_svg(source)
    return _decode_raster(source, mime_type=resolved_mime_type)


__all__ = ["load_image", "load_svg"]
