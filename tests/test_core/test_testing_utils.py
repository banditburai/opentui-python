"""Tests for MockInput and MockMouse testing utilities."""

import pytest

from opentui.components.base import BaseRenderable, Renderable
from opentui.events import KeyEvent, Keys, MouseButton, PasteEvent
from opentui.hooks import (
    clear_keyboard_handlers,
    clear_paste_handlers,
    clear_resize_handlers,
    clear_selection_handlers,
    get_keyboard_handlers,
    set_renderer,
    use_keyboard,
    use_paste,
)
from opentui.renderer import Buffer, CliRenderer, CliRendererConfig, RootRenderable
from opentui.testing import MockInput, MockMouse


# ---------------------------------------------------------------------------
# Shared fake native
# ---------------------------------------------------------------------------

class _FakeBufferNS:
    def __init__(self):
        self._returns: dict[str, object] = {}

    def _set_return(self, name, value):
        self._returns[name] = value

    def __getattr__(self, name):
        ns = self

        def method(*args, **kwargs):
            return ns._returns.get(name)

        return method


class _FakeRendererNS:
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return None

        return method


class _FakeNative:
    def __init__(self):
        self.renderer = _FakeRendererNS()
        self.buffer = _FakeBufferNS()


def _make_setup():
    """Create a TestSetup-like object without async."""
    native = _FakeNative()
    config = CliRendererConfig(width=80, height=24, testing=True)
    r = CliRenderer(1, config, native)
    r._root = RootRenderable(r)
    set_renderer(r)
    clear_keyboard_handlers()
    clear_paste_handlers()

    # Lightweight stand-in for TestSetup
    class _Setup:
        def __init__(self, renderer):
            self._renderer = renderer

        @property
        def renderer(self):
            return self._renderer

    return _Setup(r), native


# ---------------------------------------------------------------------------
# MockInput — key dispatch
# ---------------------------------------------------------------------------

class TestMockInputKeyDispatch:
    def setup_method(self):
        clear_keyboard_handlers()

    def test_press_key_dispatches_to_handlers(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append(e.key))
        mi.press_key("a")
        assert received == ["a"]

    def test_modifiers_work(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append((e.key, e.ctrl, e.shift)))
        mi.press_key("x", ctrl=True, shift=True)
        assert received == [("x", True, True)]

    def test_type_text_sends_per_char(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append(e.key))
        mi.type_text("hi")
        assert received == ["h", "i"]

    def test_convenience_enter(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append(e.key))
        mi.press_enter()
        assert received == [Keys.RETURN]

    def test_convenience_escape(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append(e.key))
        mi.press_escape()
        assert received == [Keys.ESCAPE]

    def test_convenience_tab(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append(e.key))
        mi.press_tab()
        assert received == [Keys.TAB]

    def test_convenience_backspace(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append(e.key))
        mi.press_backspace()
        assert received == [Keys.BACKSPACE]

    def test_convenience_arrow(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append(e.key))
        mi.press_arrow("up")
        mi.press_arrow("down")
        assert received == [Keys.UP, Keys.DOWN]

    def test_convenience_ctrl_c(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append((e.key, e.ctrl)))
        mi.press_ctrl_c()
        assert received == [("c", True)]

    def test_stop_propagation_respected(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []

        def stopper(e):
            received.append("first")
            e.stop_propagation()

        use_keyboard(stopper)
        use_keyboard(lambda e: received.append("second"))
        mi.press_key("a")
        assert received == ["first"]

    def test_press_keys_sequence(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_keyboard(lambda e: received.append(e.key))
        mi.press_keys(["a", "b", "c"])
        assert received == ["a", "b", "c"]

    def test_invalid_arrow_raises(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        with pytest.raises(ValueError, match="Invalid arrow direction"):
            mi.press_arrow("diagonal")


# ---------------------------------------------------------------------------
# MockInput — paste
# ---------------------------------------------------------------------------

class TestMockInputPaste:
    def setup_method(self):
        clear_paste_handlers()

    def test_paste_text_dispatches_to_paste_handlers(self):
        setup, _ = _make_setup()
        mi = MockInput(setup)
        received = []
        use_paste(lambda event: received.append(event))
        mi.paste_text("clipboard data")
        assert len(received) == 1
        assert isinstance(received[0], PasteEvent)
        assert received[0].text == "clipboard data"


# ---------------------------------------------------------------------------
# MockMouse
# ---------------------------------------------------------------------------

class TestMockMouse:
    def test_click_dispatches_down_and_up(self):
        setup, _ = _make_setup()
        mm = MockMouse(setup)
        events = []
        child = Renderable()
        child._x, child._y, child._width, child._height = 0, 0, 80, 24
        child._on_mouse_down = lambda e: events.append(("down", e.x, e.y))
        child._on_mouse_up = lambda e: events.append(("up", e.x, e.y))
        setup.renderer.root.add(child)
        mm.click(5, 10)
        assert ("down", 5, 10) in events
        assert ("up", 5, 10) in events

    def test_scroll_dispatches_with_delta(self):
        setup, _ = _make_setup()
        mm = MockMouse(setup)
        events = []
        child = Renderable()
        child._x, child._y, child._width, child._height = 0, 0, 80, 24
        child._on_mouse_scroll = lambda e: events.append(("scroll", e.scroll_delta))
        setup.renderer.root.add(child)
        mm.scroll(5, 5, direction="down", delta=3)
        assert ("scroll", 3) in events

    def test_drag_produces_down_move_up(self):
        setup, _ = _make_setup()
        mm = MockMouse(setup)
        events = []
        child = Renderable()
        child._x, child._y, child._width, child._height = 0, 0, 80, 24
        child._on_mouse_down = lambda e: events.append("down")
        child._on_mouse_drag = lambda e: events.append("drag")
        child._on_mouse_up = lambda e: events.append("up")
        setup.renderer.root.add(child)
        mm.drag(0, 0, 10, 10, steps=3)
        assert events[0] == "down"
        assert events[-1] == "up"
        assert "drag" in events

    def test_position_tracking(self):
        setup, _ = _make_setup()
        mm = MockMouse(setup)
        assert mm.position == (0, 0)
        mm.move_to(15, 20)
        assert mm.position == (15, 20)

    def test_pressed_buttons_tracking(self):
        setup, _ = _make_setup()
        mm = MockMouse(setup)
        assert mm.pressed_buttons == set()
        mm.press_down(0, 0, MouseButton.LEFT)
        assert MouseButton.LEFT in mm.pressed_buttons
        mm.release(0, 0, MouseButton.LEFT)
        assert mm.pressed_buttons == set()

    def test_stop_propagation_prevents_parent_handler(self):
        setup, _ = _make_setup()
        mm = MockMouse(setup)
        parent_events = []
        child_events = []

        parent = Renderable()
        parent._x, parent._y, parent._width, parent._height = 0, 0, 80, 24
        parent._on_mouse_down = lambda e: parent_events.append("parent_down")

        child = Renderable()
        child._x, child._y, child._width, child._height = 0, 0, 40, 12

        def child_handler(e):
            child_events.append("child_down")
            e.stop_propagation()

        child._on_mouse_down = child_handler
        parent.add(child)
        setup.renderer.root.add(parent)

        mm.click(5, 5)
        assert "child_down" in child_events
        assert parent_events == []


# ---------------------------------------------------------------------------
# TestSetup extensions
# ---------------------------------------------------------------------------

class TestTestSetup:
    def test_mock_input_returns_correct_type(self):
        setup, _ = _make_setup()
        # Wrap in an object matching TestSetup interface
        from opentui import TestSetup as TS

        ts = TS(setup.renderer)
        assert isinstance(ts.mock_input, MockInput)

    def test_mock_mouse_returns_correct_type(self):
        setup, _ = _make_setup()
        from opentui import TestSetup as TS

        ts = TS(setup.renderer)
        assert isinstance(ts.mock_mouse, MockMouse)

    def test_resize_calls_handlers(self):
        setup, _ = _make_setup()
        from opentui import TestSetup as TS
        from opentui.hooks import clear_resize_handlers, use_on_resize

        clear_resize_handlers()
        ts = TS(setup.renderer)
        received = []
        use_on_resize(lambda w, h: received.append((w, h)))
        ts.resize(120, 40)
        assert received == [(120, 40)]

    def test_resize_updates_root_dimensions(self):
        setup, _ = _make_setup()
        from opentui import TestSetup as TS

        ts = TS(setup.renderer)
        ts.resize(100, 50)
        assert ts.renderer.root._width == 100
        assert ts.renderer.root._height == 50

    def test_capture_char_frame_returns_string(self):
        setup, native = _make_setup()
        from opentui import TestSetup as TS

        native.buffer._set_return("buffer_write_resolved_chars", "Hello\nWorld")
        ts = TS(setup.renderer)
        result = ts.capture_char_frame()
        assert isinstance(result, str)
        assert "Hello" in result
