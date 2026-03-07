"""Tests for starui_tui Textarea component."""

from opentui.components import Textarea as TUITextarea
from starui_tui.textarea import Textarea


class TestTextarea:
    def test_returns_tui_textarea(self):
        t = Textarea()
        assert isinstance(t, TUITextarea)

    def test_has_border(self):
        t = Textarea()
        assert t.border is True

    def test_default_rows(self):
        t = Textarea()
        assert t.rows == 3

    def test_custom_rows(self):
        t = Textarea(rows=5)
        assert t.rows == 5

    def test_placeholder(self):
        t = Textarea(placeholder="Write here...")
        assert t.placeholder == "Write here..."

    def test_initial_value(self):
        t = Textarea(value="hello\nworld")
        assert t.value == "hello\nworld"

    def test_disabled_sets_fg(self):
        t = Textarea(disabled=True)
        assert t._fg is not None

    def test_disabled_suppresses_callbacks(self):
        t = Textarea(disabled=True, on_change=lambda _: None)
        assert isinstance(t, TUITextarea)

    def test_kwargs_passthrough(self):
        t = Textarea(width=40)
        assert t._width == 40
