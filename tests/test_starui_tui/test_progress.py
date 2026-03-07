"""Tests for Progress and Separator components."""

from opentui.components import Box, Text
from starui_tui.progress import Progress
from starui_tui.separator import Separator


class TestProgress:
    def test_returns_box(self):
        assert isinstance(Progress(value=50), Box)

    def test_zero_value(self):
        p = Progress(value=0)
        assert isinstance(p, Box)

    def test_full_value(self):
        p = Progress(value=100)
        assert isinstance(p, Box)

    def test_custom_max(self):
        p = Progress(value=50, max=200)
        assert isinstance(p, Box)

    def test_has_children(self):
        p = Progress(value=50, width=20)
        children = p.get_children()
        assert len(children) >= 1

    def test_kwargs_passthrough(self):
        p = Progress(value=50, width=30)
        assert p._width == 30


class TestSeparator:
    def test_returns_text(self):
        s = Separator()
        assert isinstance(s, Text)

    def test_horizontal(self):
        s = Separator(orientation="horizontal", width=10)
        assert isinstance(s, Text)

    def test_vertical(self):
        s = Separator(orientation="vertical")
        assert isinstance(s, Text)

    def test_kwargs_passthrough(self):
        s = Separator(fg="#ff0000")
        assert s._fg is not None
