"""Tests for image caching and resizing."""

from __future__ import annotations

from opentui.image import DecodedImage, ImageSource


def test_image_cache_reuses_decoded_asset():
    """Decoded images should be cached by source identity."""
    from opentui.image_cache import ImageCache

    cache = ImageCache()
    source = ImageSource.from_value("logo.png", mime_type="image/png")
    calls = {"count": 0}

    def loader():
        calls["count"] += 1
        return DecodedImage(data=b"\x00" * 16, width=2, height=2, source=source, mime_type="image/png")

    first = cache.get_decoded(source, loader)
    second = cache.get_decoded(source, loader)

    assert first is second
    assert calls["count"] == 1


def test_image_cache_reuses_resized_variant():
    """Resized variants should be cached by dimensions."""
    from opentui.image_cache import ImageCache

    cache = ImageCache()
    decoded = DecodedImage(data=bytes([255, 0, 0, 255] * 4), width=2, height=2)
    calls = {"count": 0}

    def scaler():
        calls["count"] += 1
        return b"\x00" * (4 * 4 * 4)

    first = cache.get_variant(decoded, 4, 4, scaler)
    second = cache.get_variant(decoded, 4, 4, scaler)

    assert first == second
    assert calls["count"] == 1


def test_image_cache_invalidates_on_clear():
    """Clearing the cache should drop decoded and resized entries."""
    from opentui.image_cache import ImageCache

    cache = ImageCache()
    source = ImageSource.from_value("logo.png")
    decoded = DecodedImage(data=b"\x00" * 16, width=2, height=2, source=source)

    cache.get_decoded(source, lambda: decoded)
    cache.get_variant(decoded, 3, 3, lambda: b"\x00" * 36)

    cache.clear()

    assert cache.decoded_count == 0
    assert cache.variant_count == 0
