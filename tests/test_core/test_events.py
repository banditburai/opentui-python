"""Tests for event types."""

from opentui.events import KeyEvent, MouseEvent, PasteEvent, FocusEvent, ResizeEvent, Keys


class TestKeyEvent:
    def test_basic_key(self):
        e = KeyEvent(key="a")
        assert e.key == "a"
        assert e.ctrl is False

    def test_modifier_keys(self):
        e = KeyEvent(key="c", ctrl=True, shift=True)
        assert e.ctrl is True
        assert e.shift is True

    def test_stop_propagation(self):
        e = KeyEvent(key="a")
        assert e.propagation_stopped is False
        e.stop_propagation()
        assert e.propagation_stopped is True

    def test_prevent_default(self):
        e = KeyEvent(key="a")
        assert e.default_prevented is False
        e.prevent_default()
        assert e.default_prevented is True

    def test_name_alias(self):
        e = KeyEvent(key="return")
        assert e.name == "return"

    def test_str_with_modifiers(self):
        e = KeyEvent(key="s", ctrl=True, alt=True)
        s = str(e)
        assert "ctrl" in s
        assert "alt" in s
        assert "s" in s


class TestMouseEvent:
    def test_basic(self):
        e = MouseEvent(type="down", x=10, y=5)
        assert e.x == 10
        assert e.y == 5

    def test_stop_propagation(self):
        e = MouseEvent(type="down", x=0, y=0)
        e.stop_propagation()
        assert e.propagation_stopped is True

    def test_prevent_default(self):
        e = MouseEvent(type="down", x=0, y=0)
        e.prevent_default()
        assert e.default_prevented is True

    def test_name(self):
        e = MouseEvent(type="scroll", x=0, y=0)
        assert e.name == "scroll"


class TestPasteEvent:
    def test_text(self):
        e = PasteEvent(text="hello")
        assert e.text == "hello"

    def test_stop_propagation(self):
        e = PasteEvent(text="x")
        e.stop_propagation()
        assert e.propagation_stopped is True


class TestFocusEvent:
    def test_focus(self):
        e = FocusEvent(type="focus", target=None)
        assert e.type == "focus"


class TestResizeEvent:
    def test_resize(self):
        e = ResizeEvent(width=80, height=24)
        assert e.width == 80
        assert e.height == 24
        assert "80x24" in str(e)


class TestKeys:
    def test_constants(self):
        assert Keys.RETURN == "return"
        assert Keys.ENTER == "return"
        assert Keys.ESCAPE == "escape"
        assert Keys.TAB == "tab"
