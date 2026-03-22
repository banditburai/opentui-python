"""Tests for the normalized image API.

Upstream: N/A (Python-specific)
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest


def test_image_api_exports():
    """The normalized image API should be publicly exported."""
    from opentui import DecodedImage, ImageFit, ImageProtocol, ImageSource

    assert ImageProtocol.AUTO == "auto"
    assert ImageFit.CONTAIN == "contain"
    assert ImageSource is not None
    assert DecodedImage is not None


def test_image_source_from_path():
    """Path sources should normalize to an ImageSource."""
    from opentui.image.types import ImageSource

    source = ImageSource.from_value("logo.png")

    assert source.path == "logo.png"
    assert source.data is None
    assert source.mime_type is None


def test_image_source_from_bytes():
    """Byte sources should normalize to an ImageSource."""
    from opentui.image.types import ImageSource

    source = ImageSource.from_value(b"\x89PNG\r\n\x1a\n", mime_type="image/png")

    assert source.path is None
    assert source.data == b"\x89PNG\r\n\x1a\n"
    assert source.mime_type == "image/png"


def test_decoded_image_is_frozen():
    """Decoded image metadata should be immutable."""
    from opentui.image.types import DecodedImage

    image = DecodedImage(data=b"\x00" * 16, width=2, height=2)

    with pytest.raises(FrozenInstanceError):
        image.width = 4


def test_image_source_rejects_empty_input():
    """Normalization should reject empty values."""
    from opentui.image.types import ImageSource

    with pytest.raises(ValueError, match="Image source cannot be empty"):
        ImageSource.from_value("")
