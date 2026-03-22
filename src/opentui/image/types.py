"""Normalized image model types for OpenTUI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ImageProtocol(StrEnum):
    """Supported rendering protocols for terminal images."""

    AUTO = "auto"
    KITTY = "kitty"
    SIXEL = "sixel"
    GRAYSCALE = "grayscale"
    ASCII = "ascii"


class ImageFit(StrEnum):
    """How an image should fit within its layout bounds."""

    CONTAIN = "contain"
    COVER = "cover"
    FILL = "fill"
    NONE = "none"
    SCALE_DOWN = "scale_down"


@dataclass(frozen=True, slots=True)
class ImageSource:
    """Normalized reference to image input data."""

    path: str | None = None
    data: bytes | None = None
    mime_type: str | None = None

    @classmethod
    def from_value(
        cls,
        value: ImageSource | str | bytes | Path,
        *,
        mime_type: str | None = None,
    ) -> ImageSource:
        """Normalize common source inputs to an ImageSource."""
        if isinstance(value, cls):
            return value
        if isinstance(value, Path):
            value = str(value)
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("Image source cannot be empty")
            return cls(path=value, mime_type=mime_type)
        if isinstance(value, bytes):
            if not value:
                raise ValueError("Image source cannot be empty")
            return cls(data=value, mime_type=mime_type)
        raise TypeError(f"Unsupported image source type: {type(value)!r}")


@dataclass(frozen=True, slots=True)
class DecodedImage:
    """Decoded image data ready for rendering."""

    data: bytes
    width: int
    height: int
    mime_type: str | None = None
    source: ImageSource | None = None


__all__ = [
    "DecodedImage",
    "ImageFit",
    "ImageProtocol",
    "ImageSource",
]


def resize_rgba_nearest(
    data: bytes, src_width: int, src_height: int, dst_width: int, dst_height: int
) -> bytes:
    """Resize RGBA image data using nearest-neighbor scaling."""
    if src_width <= 0 or src_height <= 0 or dst_width <= 0 or dst_height <= 0:
        return b""

    if src_width == dst_width and src_height == dst_height:
        return data

    # Precompute source x indices for all destination columns
    src_x_indices = [min(src_width - 1, (x * src_width) // dst_width) for x in range(dst_width)]

    out = bytearray(dst_width * dst_height * 4)
    for y in range(dst_height):
        src_y = min(src_height - 1, (y * src_height) // dst_height)
        src_row_offset = src_y * src_width
        dst_row_offset = y * dst_width
        for x in range(dst_width):
            src_idx = (src_row_offset + src_x_indices[x]) * 4
            dst_idx = (dst_row_offset + x) * 4
            out[dst_idx : dst_idx + 4] = data[src_idx : src_idx + 4]
    return bytes(out)


__all__.append("resize_rgba_nearest")
