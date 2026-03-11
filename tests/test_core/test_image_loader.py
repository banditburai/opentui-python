"""Tests for image loading and SVG rasterization."""

from __future__ import annotations

from pathlib import Path

import pytest


class _FakeOpenedImage:
    def __init__(self, *, mode: str = "RGBA", size: tuple[int, int] = (2, 3), data: bytes | None = None):
        self.mode = mode
        self.size = size
        self._data = data if data is not None else bytes([255, 0, 0, 255] * (size[0] * size[1]))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def convert(self, mode: str):
        return _FakeOpenedImage(mode=mode, size=self.size, data=self._data)

    def tobytes(self) -> bytes:
        return self._data


class _FakePillowImageModule:
    def __init__(self, expected: bytes | None = None):
        self.expected = expected

    def open(self, source):
        if hasattr(source, "read") and self.expected is not None:
            assert source.read() == self.expected
            source.seek(0)
        elif isinstance(source, (str, Path)):
            assert str(source).endswith(".png")
        return _FakeOpenedImage()


def test_load_raster_without_pillow_raises_clear_error(monkeypatch):
    """Raster loading should explain when Pillow is missing."""
    import opentui.image_loader as image_loader

    monkeypatch.setattr(
        image_loader,
        "_import_pillow_image",
        lambda: (_ for _ in ()).throw(ImportError("missing pillow")),
    )

    with pytest.raises(ImportError, match="Pillow required for raster image loading"):
        image_loader.load_image("logo.png")


def test_load_png_path_to_rgba(tmp_path, monkeypatch):
    """Raster file paths should decode to RGBA bytes."""
    import opentui.image_loader as image_loader

    path = tmp_path / "sample.png"
    path.write_bytes(b"fake png bytes")

    monkeypatch.setattr(image_loader, "_import_pillow_image", lambda: _FakePillowImageModule())

    decoded = image_loader.load_image(path)

    assert decoded.width == 2
    assert decoded.height == 3
    assert decoded.mime_type == "image/png"
    assert decoded.source is not None
    assert decoded.source.path == str(path)
    assert len(decoded.data) == 2 * 3 * 4


def test_load_png_bytes_to_rgba(monkeypatch):
    """Raster bytes should decode to RGBA bytes."""
    import opentui.image_loader as image_loader

    png_bytes = b"\x89PNG\r\n\x1a\npayload"

    monkeypatch.setattr(
        image_loader,
        "_import_pillow_image",
        lambda: _FakePillowImageModule(expected=png_bytes),
    )

    decoded = image_loader.load_image(png_bytes, mime_type="image/png")

    assert decoded.width == 2
    assert decoded.height == 3
    assert decoded.mime_type == "image/png"
    assert decoded.source is not None
    assert decoded.source.data == png_bytes


def test_load_svg_without_backend_raises_clear_error(monkeypatch):
    """SVG rasterization should explain when the backend is missing."""
    import opentui.image_loader as image_loader

    monkeypatch.setattr(
        image_loader,
        "_import_cairosvg",
        lambda: (_ for _ in ()).throw(ImportError("missing cairosvg")),
    )

    with pytest.raises(ImportError, match="cairosvg required for SVG rasterization"):
        image_loader.load_svg("<svg/>")


def test_load_svg_to_rgba_with_backend(monkeypatch):
    """SVG sources should rasterize through the configured backend."""
    import opentui.image_loader as image_loader

    class FakeCairoSVG:
        @staticmethod
        def svg2png(bytestring: bytes, output_width=None, output_height=None):
            assert b"<svg" in bytestring
            assert output_width is None
            assert output_height is None
            return b"\x89PNG\r\n\x1a\npayload"

    monkeypatch.setattr(image_loader, "_import_cairosvg", lambda: FakeCairoSVG)
    monkeypatch.setattr(
        image_loader,
        "_import_pillow_image",
        lambda: _FakePillowImageModule(expected=b"\x89PNG\r\n\x1a\npayload"),
    )

    decoded = image_loader.load_svg("<svg xmlns='http://www.w3.org/2000/svg' />")

    assert decoded.width == 2
    assert decoded.height == 3
    assert decoded.mime_type == "image/svg+xml"
    assert len(decoded.data) == 2 * 3 * 4
