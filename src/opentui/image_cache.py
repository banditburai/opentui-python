"""Image cache helpers."""

from __future__ import annotations

import hashlib

from .image import DecodedImage, ImageSource


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

    def get_decoded(self, source: ImageSource, loader) -> DecodedImage:
        key = _source_key(source)
        cached = self._decoded.get(key)
        if cached is not None:
            return cached
        decoded = loader()
        self._decoded[key] = decoded
        return decoded

    def get_variant(self, decoded: DecodedImage, width: int, height: int, scaler) -> bytes:
        source = decoded.source or ImageSource(data=decoded.data, mime_type=decoded.mime_type)
        key = (_source_key(source), width, height)
        cached = self._variants.get(key)
        if cached is not None:
            return cached
        variant = scaler()
        self._variants[key] = variant
        return variant

    def clear(self) -> None:
        self._decoded.clear()
        self._variants.clear()


__all__ = ["ImageCache"]
