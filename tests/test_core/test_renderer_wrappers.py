"""Tests for new CliRenderer wrapper methods — uses _FakeNative with call recording."""

import select
import sys
import termios
import time

from opentui.components.base import Renderable
from opentui.events import PasteEvent
from opentui.hooks import clear_paste_handlers, use_paste
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
    def test_get_capabilities(self):
        r, n = _make()
        n.renderer._set_return(
            "get_terminal_capabilities",
            {
                "kitty_keyboard": True,
                "kitty_graphics": True,
                "rgb": True,
                "unicode": True,
                "sgr_pixels": False,
                "color_scheme_updates": True,
                "explicit_width": False,
                "scaled_text": False,
                "sixel": False,
                "focus_tracking": True,
                "sync": False,
                "bracketed_paste": True,
                "hyperlinks": True,
                "osc52": True,
                "explicit_cursor_positioning": True,
            },
        )

        caps = r.get_capabilities()

        assert caps.kitty_graphics is True
        assert caps.term_name == ""
        assert caps.term_version == ""

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

    def test_get_event_forwarding_collects_paste_handlers(self):
        r, _ = _make()
        child = Renderable()
        child.on_paste = lambda event: None
        r._root.add(child)

        handlers = r._get_event_forwarding()

        assert len(handlers["paste"]) == 1

    def test_run_registers_tree_and_hook_paste_handlers(self, monkeypatch):
        class _FakeInputHandler:
            def __init__(self):
                self.key_handlers = []
                self.mouse_handlers = []
                self.paste_handlers = []

            def on_key(self, handler):
                self.key_handlers.append(handler)

            def on_mouse(self, handler):
                self.mouse_handlers.append(handler)

            def on_paste(self, handler):
                self.paste_handlers.append(handler)

        class _FakeEventLoop:
            last_instance = None

            def __init__(self, target_fps):
                self.target_fps = target_fps
                self.input_handler = _FakeInputHandler()
                self.frame_callbacks = []
                type(self).last_instance = self

            def on_frame(self, callback):
                self.frame_callbacks.append(callback)

            def run(self):
                return None

        class _FakeStdin:
            def fileno(self):
                return 0

        ticks = {"value": -1}

        def _fake_perf_counter():
            ticks["value"] += 1
            return ticks["value"] * 0.5

        r, _ = _make()
        seen = []
        child = Renderable()
        child.on_paste = lambda event: seen.append(("tree", event.text))
        r._root.add(child)

        clear_paste_handlers()
        use_paste(lambda event: seen.append(("hook", event.text)))

        monkeypatch.setattr("opentui.input.EventLoop", _FakeEventLoop)
        monkeypatch.setattr(r, "setup", lambda: None)
        monkeypatch.setattr(r, "_refresh_mouse_tracking", lambda: None)
        monkeypatch.setattr(r, "_render_frame", lambda dt: None)
        monkeypatch.setattr(sys, "stdin", _FakeStdin())
        monkeypatch.setattr(termios, "tcgetattr", lambda fd: [0, 0, 0, 0, 0, 0, 0])
        monkeypatch.setattr(termios, "tcsetattr", lambda *args: None)
        monkeypatch.setattr(select, "select", lambda *args: ([], [], []))
        monkeypatch.setattr(time, "perf_counter", _fake_perf_counter)

        try:
            r.run()
            event_loop = _FakeEventLoop.last_instance
            assert event_loop is not None
            assert len(event_loop.input_handler.paste_handlers) == 2

            for handler in event_loop.input_handler.paste_handlers:
                handler(PasteEvent(text="clip"))

            assert seen == [("tree", "clip"), ("hook", "clip")]
        finally:
            clear_paste_handlers()


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
