"""Tests for new CliRenderer wrapper methods — uses _FakeNative with call recording."""

from opentui.renderer import Buffer, CliRenderer, CliRendererConfig, RootRenderable


class _FakeRendererNS:
    """Fake renderer namespace that records all calls."""

    def __init__(self):
        self.calls: dict[str, tuple] = {}
        self._returns: dict[str, object] = {}

    def _set_return(self, name, value):
        self._returns[name] = value

    def __getattr__(self, name):
        ns = self

        def method(*args, **kwargs):
            ns.calls[name] = args
            return ns._returns.get(name)

        return method


class _FakeBufferNS:
    """Fake buffer namespace that records all calls."""

    def __init__(self):
        self.calls: dict[str, tuple] = {}
        self._returns: dict[str, object] = {}

    def _set_return(self, name, value):
        self._returns[name] = value

    def __getattr__(self, name):
        ns = self

        def method(*args, **kwargs):
            ns.calls[name] = args
            return ns._returns.get(name)

        return method


class _FakeNative:
    def __init__(self):
        self.renderer = _FakeRendererNS()
        self.buffer = _FakeBufferNS()


def _make(native=None):
    native = native or _FakeNative()
    config = CliRendererConfig(width=80, height=24, testing=True)
    r = CliRenderer(1, config, native)
    r._root = RootRenderable(r)
    return r, native


class TestCliRendererCursorMethods:
    def test_set_cursor_position(self):
        r, n = _make()
        r.set_cursor_position(5, 10, visible=False)
        assert n.renderer.calls["set_cursor_position"] == (1, 5, 10, False)

    def test_get_cursor_state(self):
        r, n = _make()
        n.renderer._set_return("get_cursor_state", {"x": 3, "y": 7, "visible": True})
        result = r.get_cursor_state()
        assert result == {"x": 3, "y": 7, "visible": True}


class TestCliRendererClipboard:
    def test_copy_to_clipboard(self):
        r, n = _make()
        n.renderer._set_return("copy_to_clipboard_osc52", True)
        result = r.copy_to_clipboard(0, "hello")
        assert result is True
        assert n.renderer.calls["copy_to_clipboard_osc52"] == (1, 0, "hello")

    def test_clear_clipboard(self):
        r, n = _make()
        n.renderer._set_return("clear_clipboard_osc52", True)
        result = r.clear_clipboard(1)
        assert result is True
        assert n.renderer.calls["clear_clipboard_osc52"] == (1, 1)


class TestCliRendererDebugAndStats:
    def test_set_debug_overlay(self):
        r, n = _make()
        r.set_debug_overlay(True, flags=3)
        assert n.renderer.calls["set_debug_overlay"] == (1, True, 3)

    def test_update_stats(self):
        r, n = _make()
        r.update_stats(60.0, 100, 16.5)
        assert n.renderer.calls["update_stats"] == (1, 60.0, 100, 16.5)


class TestCliRendererIO:
    def test_write_out(self):
        r, n = _make()
        r.write_out(b"\x1b[2J")
        assert n.renderer.calls["write_out"] == (1, b"\x1b[2J")


class TestCliRendererKittyFlags:
    def test_set_kitty_keyboard_flags(self):
        r, n = _make()
        r.set_kitty_keyboard_flags(7)
        assert n.renderer.calls["set_kitty_keyboard_flags"] == (1, 7)

    def test_get_kitty_keyboard_flags(self):
        r, n = _make()
        n.renderer._set_return("get_kitty_keyboard_flags", 3)
        assert r.get_kitty_keyboard_flags() == 3


class TestCliRendererMisc:
    def test_set_background_color(self):
        r, n = _make()
        r.set_background_color()
        assert "set_background_color" in n.renderer.calls

    def test_set_render_offset(self):
        r, n = _make()
        r.set_render_offset(42)
        assert n.renderer.calls["set_render_offset"] == (1, 42)

    def test_query_pixel_resolution(self):
        r, n = _make()
        r.query_pixel_resolution()
        assert "query_pixel_resolution" in n.renderer.calls


class TestBufferGetPlainText:
    def test_returns_text(self):
        native_buf = _FakeBufferNS()
        native_buf._set_return("buffer_write_resolved_chars", "Hello\nWorld")
        buf = Buffer(1, native_buf)
        assert buf.get_plain_text() == "Hello\nWorld"

    def test_returns_empty_on_none(self):
        native_buf = _FakeBufferNS()
        native_buf._set_return("buffer_write_resolved_chars", None)
        buf = Buffer(1, native_buf)
        assert buf.get_plain_text() == ""

    def test_returns_empty_on_exception(self):
        class _Exploding:
            def buffer_write_resolved_chars(self, *a):
                raise RuntimeError("boom")

        buf = Buffer(1, _Exploding())
        assert buf.get_plain_text() == ""
