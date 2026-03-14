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
                self.focus_handlers = []

            def on_key(self, handler):
                self.key_handlers.append(handler)

            def on_mouse(self, handler):
                self.mouse_handlers.append(handler)

            def on_paste(self, handler):
                self.paste_handlers.append(handler)

            def on_focus(self, handler):
                self.focus_handlers.append(handler)

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


class TestRendererCursorRequest:
    """Tests for the per-frame cursor request/apply infrastructure."""

    def test_request_cursor_applies_position(self):
        r, n = _make()
        r.request_cursor(10, 5)
        r._apply_cursor()
        # use_cursor takes 0-based coords; _apply_cursor adds +1 for 1-based native API
        assert n.renderer.calls["set_cursor_position"] == (1, 11, 6, True)

    def test_no_request_hides_cursor(self):
        r, n = _make()
        r._apply_cursor()
        assert n.renderer.calls["set_cursor_position"] == (1, 0, 0, False)

    def test_last_request_wins(self):
        r, n = _make()
        r.request_cursor(1, 2)
        r.request_cursor(30, 15)
        r._apply_cursor()
        # 0-based (30, 15) → 1-based (31, 16)
        assert n.renderer.calls["set_cursor_position"] == (1, 31, 16, True)

    def test_request_cleared_each_frame(self):
        r, n = _make()
        # Frame 1: cursor requested — 0-based (5, 5) → 1-based (6, 6)
        r.request_cursor(5, 5)
        r._apply_cursor()
        assert n.renderer.calls["set_cursor_position"] == (1, 6, 6, True)
        # Frame 2: no request → cursor hidden
        r._apply_cursor()
        assert n.renderer.calls["set_cursor_position"] == (1, 0, 0, False)


class TestRendererStaleGraphics:
    """Tests for per-frame Kitty graphics tracking and stale cleanup."""

    def test_register_frame_graphics_tracks_id(self):
        r, _ = _make()
        r.register_frame_graphics(42)
        assert 42 in r._frame_graphics

    def test_stale_graphics_cleared(self, monkeypatch):
        """Graphics active last frame but not this frame are cleared."""
        import io

        fake_buf = io.BytesIO()

        class _FakeStdout:
            buffer = fake_buf

        monkeypatch.setattr(sys, "stdout", _FakeStdout())

        r, _ = _make()

        # Frame 1: register graphics ID 10
        r.register_frame_graphics(10)
        r._clear_stale_graphics()
        # No stale IDs — nothing cleared
        assert fake_buf.getvalue() == b""
        assert 10 in r._prev_frame_graphics

        # Frame 2: don't register ID 10 → it's stale
        r._clear_stale_graphics()
        output = fake_buf.getvalue()
        assert b"Ga=d,d=I,i=10" in output

    def test_active_graphics_not_cleared(self, monkeypatch):
        """Graphics re-registered each frame are never cleared."""
        import io

        fake_buf = io.BytesIO()

        class _FakeStdout:
            buffer = fake_buf

        monkeypatch.setattr(sys, "stdout", _FakeStdout())

        r, _ = _make()

        # Frame 1
        r.register_frame_graphics(5)
        r._clear_stale_graphics()
        # Frame 2 — still active
        r.register_frame_graphics(5)
        r._clear_stale_graphics()

        assert fake_buf.getvalue() == b""

    def test_multiple_stale_ids_all_cleared(self, monkeypatch):
        """Multiple stale IDs from one frame are all cleared."""
        import io

        fake_buf = io.BytesIO()

        class _FakeStdout:
            buffer = fake_buf

        monkeypatch.setattr(sys, "stdout", _FakeStdout())

        r, _ = _make()
        r.register_frame_graphics(1)
        r.register_frame_graphics(2)
        r.register_frame_graphics(3)
        r._clear_stale_graphics()

        # Frame 2: only ID 2 survives
        r.register_frame_graphics(2)
        r._clear_stale_graphics()

        output = fake_buf.getvalue()
        assert b"i=1" in output
        assert b"i=3" in output
        assert b"i=2" not in output


class TestRendererGraphicsSuppression:
    """Tests for renderer-level graphics suppression."""

    def test_suppress_unsuppress(self):
        r, _ = _make()
        assert r.graphics_suppressed is False
        r.suppress_graphics()
        assert r.graphics_suppressed is True
        r.unsuppress_graphics()
        assert r.graphics_suppressed is False

    def test_suppressed_graphics_become_stale(self, monkeypatch):
        """When suppressed, unregistered graphics are cleared by stale tracker."""
        import io

        fake_buf = io.BytesIO()

        class _FakeStdout:
            buffer = fake_buf

        monkeypatch.setattr(sys, "stdout", _FakeStdout())

        r, _ = _make()

        # Frame 1: image active
        r.register_frame_graphics(7)
        r._clear_stale_graphics()
        assert fake_buf.getvalue() == b""

        # Frame 2: suppressed — image doesn't register
        r.suppress_graphics()
        r._clear_stale_graphics()
        output = fake_buf.getvalue()
        assert b"Ga=d,d=I,i=7" in output

    def test_unsuppress_does_not_auto_redraw(self):
        """Unsuppress only flips the flag — Images detect the transition themselves."""
        r, _ = _make()
        r.suppress_graphics()
        r.unsuppress_graphics()
        # No side effects — just a boolean flip
        assert r.graphics_suppressed is False
        assert r._frame_graphics == set()


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


class TestRendererCursorStyleRequest:
    """Tests for the per-frame cursor style request/apply infrastructure.

    Style and color escapes go through ``write_out`` (native output) so
    they land in the same byte stream as the cursor position call.
    """

    def test_request_cursor_style_applies(self):
        """Style is applied via DECSCUSR when cursor + style both requested."""
        r, n = _make()
        r.request_cursor(10, 5)
        r.request_cursor_style("bar")
        r._apply_cursor()

        # bar → DECSCUSR 5 ("\x1b[5 q") sent through write_out
        assert "write_out" in n.renderer.calls
        written = n.renderer.calls["write_out"][1]  # (ptr, data)
        assert b"\x1b[5 q" in written
        # Position set first (0-based → 1-based)
        assert n.renderer.calls["set_cursor_position"] == (1, 11, 6, True)

    def test_no_style_request_defaults_to_block(self):
        """Position only → block style (DECSCUSR 1)."""
        r, n = _make()
        r.request_cursor(0, 0)
        # No request_cursor_style() call
        r._apply_cursor()

        written = n.renderer.calls["write_out"][1]
        assert b"\x1b[1 q" in written  # block → 1

    def test_style_without_position_ignored(self):
        """Style only, no position → cursor hidden, no style write."""
        r, n = _make()
        r.request_cursor_style("bar")
        # No request_cursor()
        r._apply_cursor()

        # Cursor hidden
        assert n.renderer.calls["set_cursor_position"] == (1, 0, 0, False)
        # No write_out for style
        assert "write_out" not in n.renderer.calls

    def test_cursor_color_request(self):
        """Color applied via OSC 12 when both position and color requested."""
        r, n = _make()
        r.request_cursor(5, 5)
        r.request_cursor_style("block", color="#ff0000")
        r._apply_cursor()

        written = n.renderer.calls["write_out"][1]
        assert b"\x1b]12;#ff0000\x07" in written

    def test_color_reset_when_not_requested(self):
        """Previous color cleared via OSC 112 when not requested this frame."""
        r, n = _make()
        # Simulate a previous frame that set a color
        r._cursor_color = "#ff0000"

        # This frame: position but no color requested
        r.request_cursor(5, 5)
        r._apply_cursor()

        written = n.renderer.calls["write_out"][1]
        assert b"\x1b]112\x07" in written
