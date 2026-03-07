"""Tests for Switch and Toggle components."""

from opentui.components import Box, Text
from starui_tui.signals import Signal
from starui_tui.switch import Switch, Toggle


class TestSwitch:
    def test_returns_box(self):
        assert isinstance(Switch(), Box)

    def test_off_display(self):
        s = Switch(checked=False)
        children = s.get_children()
        texts = [c for c in children if isinstance(c, Text)]
        assert len(texts) >= 1

    def test_on_display(self):
        s = Switch(checked=True)
        assert isinstance(s, Box)

    def test_with_signal(self):
        sig = Signal("on", False)
        s = Switch(checked=sig)
        assert isinstance(s, Box)

    def test_on_change(self):
        changes = []
        s = Switch(on_change=lambda v: changes.append(v))
        assert s.on_mouse_down is not None

    def test_kwargs_passthrough(self):
        s = Switch(width=10)
        assert s._width == 10


class TestToggle:
    def test_returns_box(self):
        assert isinstance(Toggle("Bold"), Box)

    def test_pressed_state(self):
        t = Toggle("B", pressed=True)
        assert isinstance(t, Box)

    def test_unpressed_state(self):
        t = Toggle("B", pressed=False)
        assert isinstance(t, Box)

    def test_with_signal(self):
        sig = Signal("bold", False)
        t = Toggle("B", pressed=sig)
        assert isinstance(t, Box)
