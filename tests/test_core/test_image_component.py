"""Tests for the Image component."""

from __future__ import annotations


def test_image_component_exported():
    """The Image component should be publicly exported."""
    from opentui import Image

    assert Image is not None


def test_image_component_renders_loaded_image(monkeypatch):
    """Image should render decoded image data through ImageRenderer."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "ascii")

    calls = {}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            calls["buffer"] = buffer
            calls["caps"] = caps

        def draw_image(
            self,
            data,
            x,
            y,
            width,
            height,
            graphics_id=None,
            source_width=None,
            source_height=None,
        ):
            calls["draw"] = (data, x, y, width, height, graphics_id, source_width, source_height)
            return True

    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * 16,
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", fit="fill", width=10, height=6)
    image._x = 3
    image._y = 4
    image._layout_width = 10
    image._layout_height = 6

    buffer = object()
    image.render(buffer)

    assert calls["buffer"] is buffer
    assert calls["caps"].kitty_graphics is False
    assert calls["caps"].sixel is False
    assert calls["draw"][1:5] == (3, 4, 10, 6)
    assert calls["draw"][5] is None
    assert calls["draw"][6:] == (10, 6)
    assert len(calls["draw"][0]) == 10 * 6 * 4


def test_image_component_auto_detects_kitty_from_env(monkeypatch):
    """AUTO protocol should enable kitty graphics for supported terminals."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            calls["caps"] = caps

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            return True

    monkeypatch.setenv("TERM", "xterm-ghostty")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * 16,
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", protocol="auto", width=4, height=4)
    image._layout_width = 4
    image._layout_height = 4
    image.render(object())

    assert calls["caps"].kitty_graphics is True
    assert calls["caps"].sixel is False


def test_image_component_respects_explicit_ascii_protocol(monkeypatch):
    """Explicit ASCII protocol should not enable terminal graphics."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            calls["caps"] = caps

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            return True

    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * 16,
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", protocol="ascii", width=4, height=4)
    image._layout_width = 4
    image._layout_height = 4
    image.render(object())

    assert calls["caps"].kitty_graphics is False
    assert calls["caps"].sixel is False


def test_image_component_uses_grayscale_path_when_requested(monkeypatch):
    """Explicit grayscale protocol should use draw_grayscale first."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {"grayscale": 0}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def draw_grayscale(self, data, x, y, width, height):
            calls["grayscale"] += 1
            return True

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            calls["draw_image"] = True
            return True

    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * 16,
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", protocol="grayscale", width=4, height=4)
    image._layout_width = 4
    image._layout_height = 4
    image.render(object())

    assert calls["grayscale"] == 1
    assert "draw_image" not in calls


def test_image_component_uses_alt_text_when_load_fails(monkeypatch):
    """Image should fall back to alt text when loading fails."""
    from opentui.components.image import Image
    import opentui.components.image as image_component

    class MockBuffer:
        def __init__(self):
            self.calls = []

        def draw_text(self, text, x, y, fg=None, bg=None, attributes=0):
            self.calls.append((text, x, y))

    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: (_ for _ in ()).throw(RuntimeError("broken")),
    )

    image = Image("logo.png", alt="Logo unavailable")
    image._x = 1
    image._y = 2

    buffer = MockBuffer()
    image.render(buffer)

    assert buffer.calls == [("Logo unavailable", 1, 2)]


def test_image_component_contain_centers_scaled_image(monkeypatch):
    """Contain fit should preserve aspect ratio and center inside the box."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "ascii")

    calls = {}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def draw_image(
            self,
            data,
            x,
            y,
            width,
            height,
            graphics_id=None,
            source_width=None,
            source_height=None,
        ):
            calls["draw"] = (data, x, y, width, height, graphics_id, source_width, source_height)
            return True

    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (4 * 2 * 4),
            width=4,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", fit="contain", width=10, height=10)
    image._x = 0
    image._y = 0
    image._layout_width = 10
    image._layout_height = 10

    image.render(object())

    assert calls["draw"][1:5] == (0, 2, 10, 5)


def test_image_component_caches_resized_variant(monkeypatch):
    """Image should not recompute the same resized variant every render."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "ascii")

    calls = {"resize": 0}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            return True

    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (2 * 2 * 4),
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(
        image_component,
        "resize_rgba_nearest",
        lambda data, src_w, src_h, dst_w, dst_h: (
            calls.__setitem__("resize", calls["resize"] + 1) or b"\x00" * (dst_w * dst_h * 4)
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", width=6, height=6)
    image._layout_width = 6
    image._layout_height = 6

    image.render(object())
    image.render(object())

    assert calls["resize"] == 1


def test_image_component_does_not_redraw_same_kitty_image_each_frame(monkeypatch):
    """Graphics protocols should not retransmit the same image every render."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {"draw": 0}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            calls["draw"] += 1
            return True

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "kitty")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (2 * 2 * 4),
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", width=6, height=6)
    image._x = 1
    image._y = 2
    image._layout_width = 6
    image._layout_height = 6

    image.render(object())
    image.render(object())

    assert calls["draw"] == 1


def test_image_component_preserves_original_pixels_for_kitty(monkeypatch):
    """Kitty should keep original image pixels and only scale placement in cells."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            calls["caps"] = caps

        def draw_image(
            self,
            data,
            x,
            y,
            width,
            height,
            graphics_id=None,
            source_width=None,
            source_height=None,
        ):
            calls["draw"] = (len(data), x, y, width, height, source_width, source_height)
            return True

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "kitty")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (100 * 50 * 4),
            width=100,
            height=50,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", width=10, height=10)
    image._layout_width = 10
    image._layout_height = 10
    image.render(object())

    assert calls["caps"].kitty_graphics is True
    assert calls["draw"] == (100 * 50 * 4, 0, 4, 10, 2, 100, 50)


def test_image_component_clears_previous_graphics_when_geometry_changes(monkeypatch):
    """A moved/resized graphics image should clear the old placement before redraw."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {"draw": [], "clear": []}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def clear_graphics(self, graphics_id):
            calls["clear"].append(graphics_id)

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            calls["draw"].append((x, y, width, height, graphics_id))
            return True

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "kitty")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (2 * 2 * 4),
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", width=6, height=6)
    image._x = 1
    image._y = 2
    image._layout_width = 6
    image._layout_height = 6
    image.render(object())

    image._x = 3
    image.render(object())

    first_draw, second_draw = calls["draw"]
    assert first_draw[:4] == (1, 3, 6, 3)
    assert second_draw[:4] == (3, 3, 6, 3)
    assert isinstance(first_draw[4], int)
    assert second_draw[4] == first_draw[4]
    assert calls["clear"] == [first_draw[4]]


def test_image_destroy_clears_graphics(monkeypatch):
    """Destroying an Image with an active kitty graphic should emit the clear escape."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component
    import io

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            return True

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "kitty")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (2 * 2 * 4),
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", width=6, height=6)
    image._x = 0
    image._y = 0
    image._layout_width = 6
    image._layout_height = 6
    image.render(object())
    assert image._graphics_id is not None

    gid = image._graphics_id
    fake_stdout = io.BytesIO()
    monkeypatch.setattr("sys.stdout", type("FakeStdout", (), {"buffer": fake_stdout, "write": lambda s, x: None, "flush": lambda s: None})())

    image.destroy()

    written = fake_stdout.getvalue()
    expected = f"\x1b_Ga=d,d=I,i={gid}\x1b\\".encode()
    assert expected in written


def test_image_invisible_clears_graphics(monkeypatch):
    """Setting an Image invisible should clear the kitty graphic and reset signature."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component
    import io

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            return True

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "kitty")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (2 * 2 * 4),
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", width=6, height=6)
    image._x = 0
    image._y = 0
    image._layout_width = 6
    image._layout_height = 6
    image.render(object())
    assert image._graphics_id is not None
    assert image._last_draw_signature is not None

    fake_stdout = io.BytesIO()
    monkeypatch.setattr("sys.stdout", type("FakeStdout", (), {"buffer": fake_stdout, "write": lambda s, x: None, "flush": lambda s: None})())

    image._visible = False
    image.render(object())

    assert image._last_draw_signature is None
    assert image._graphics_id is None
    written = fake_stdout.getvalue()
    assert len(written) > 0  # clear escape was written


# ---------------------------------------------------------------------------
# Graphics suppression tests
# ---------------------------------------------------------------------------


def _kitty_image_helper(monkeypatch):
    """Shared helper: set up a Kitty-protocol Image with fake renderer."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {"draw": 0, "registered": []}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def clear_graphics(self, graphics_id):
            pass

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            calls["draw"] += 1
            return True

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "kitty")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (2 * 2 * 4),
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", alt="Logo", width=6, height=6)
    image._x = 1
    image._y = 2
    image._layout_width = 6
    image._layout_height = 6

    return image, calls


def _make_fake_renderer(*, suppressed: bool = False):
    """Create a minimal fake CliRenderer for suppression tests."""
    registered = []

    class _FakeRenderer:
        _graphics_suppressed = suppressed

        @property
        def graphics_suppressed(self):
            return self._graphics_suppressed

        def register_frame_graphics(self, gid):
            registered.append(gid)

    return _FakeRenderer(), registered


def test_image_suppressed_shows_alt_text(monkeypatch):
    """When graphics are suppressed, Image should render alt text instead."""
    image, calls = _kitty_image_helper(monkeypatch)

    renderer, registered = _make_fake_renderer(suppressed=True)
    monkeypatch.setattr("opentui.hooks.get_renderer", lambda: renderer)

    drawn_text = []

    class MockBuffer:
        def draw_text(self, text, x, y, **kw):
            drawn_text.append((text, x, y))

    image.render(MockBuffer())

    assert calls["draw"] == 0, "Graphics draw should be skipped when suppressed"
    assert drawn_text == [("Logo", 1, 2)], "Alt text should be rendered"
    assert image._was_suppressed is True


def test_image_suppressed_does_not_register_graphics(monkeypatch):
    """Suppressed images should not register their graphics ID."""
    image, calls = _kitty_image_helper(monkeypatch)

    renderer, registered = _make_fake_renderer(suppressed=True)
    monkeypatch.setattr("opentui.hooks.get_renderer", lambda: renderer)

    class MockBuffer:
        def draw_text(self, *a, **kw):
            pass

    image.render(MockBuffer())

    assert registered == [], "No graphics ID should be registered when suppressed"


def test_image_unsuppressed_forces_redraw(monkeypatch):
    """Transitioning from suppressed → active should force a full redraw."""
    image, calls = _kitty_image_helper(monkeypatch)

    # First render: normal (active)
    renderer, registered = _make_fake_renderer(suppressed=False)
    monkeypatch.setattr("opentui.hooks.get_renderer", lambda: renderer)
    image.render(object())
    assert calls["draw"] == 1
    assert image._last_draw_signature is not None

    # Second render: suppressed — skip draw, set _was_suppressed
    renderer._graphics_suppressed = True

    class MockBuffer:
        def draw_text(self, *a, **kw):
            pass

    image.render(MockBuffer())
    assert calls["draw"] == 1, "No draw during suppression"
    assert image._was_suppressed is True

    # Third render: unsuppressed — should force redraw (signature cleared)
    renderer._graphics_suppressed = False
    image.render(object())
    assert calls["draw"] == 2, "Image should redraw after unsuppression"
    assert image._was_suppressed is False


def test_image_no_alt_suppressed_still_skips_draw(monkeypatch):
    """Suppression should skip graphics even when no alt text is set."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {"draw": 0}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            calls["draw"] += 1
            return True

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "kitty")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (2 * 2 * 4),
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    image = Image("logo.png", width=6, height=6)  # No alt text
    image._x = 0
    image._y = 0
    image._layout_width = 6
    image._layout_height = 6

    renderer, _ = _make_fake_renderer(suppressed=True)
    monkeypatch.setattr("opentui.hooks.get_renderer", lambda: renderer)

    image.render(object())
    assert calls["draw"] == 0


def test_image_ascii_protocol_ignores_suppression(monkeypatch):
    """ASCII protocol images should not check suppression (no graphics layer)."""
    from opentui.image import DecodedImage, ImageSource
    from opentui.components.image import Image
    import opentui.components.image as image_component

    calls = {"draw": 0}

    class FakeImageRenderer:
        def __init__(self, buffer, caps=None):
            pass

        def draw_image(self, data, x, y, width, height, graphics_id=None, source_width=None, source_height=None):
            calls["draw"] += 1
            return True

    monkeypatch.setenv("OPENTUI_IMAGE_PROTOCOL", "ascii")
    monkeypatch.setattr(
        image_component,
        "load_image",
        lambda src, mime_type=None: DecodedImage(
            data=b"\x00" * (2 * 2 * 4),
            width=2,
            height=2,
            mime_type="image/png",
            source=ImageSource.from_value(src, mime_type=mime_type),
        ),
    )
    monkeypatch.setattr(image_component, "ImageRenderer", FakeImageRenderer)

    # Even with a suppressed renderer, ASCII should still draw
    renderer, _ = _make_fake_renderer(suppressed=True)
    monkeypatch.setattr("opentui.hooks.get_renderer", lambda: renderer)

    image = Image("logo.png", protocol="ascii", width=6, height=6)
    image._layout_width = 6
    image._layout_height = 6
    image.render(object())

    assert calls["draw"] == 1, "ASCII protocol should ignore suppression"
