"""Tests for prop utilities."""

from startui.props import split_props, resolve_value


class TestSplitProps:
    def test_fg_goes_to_text(self):
        text_p, box_p = split_props({"fg": "#FFF"})
        assert "fg" in text_p
        assert "fg" not in box_p

    def test_bold_goes_to_text(self):
        text_p, box_p = split_props({"bold": True})
        assert "bold" in text_p

    def test_bg_mapped_to_background_color(self):
        text_p, box_p = split_props({"bg": "#000"})
        assert "background_color" in box_p
        assert "bg" not in box_p

    def test_padding_x_expanded(self):
        text_p, box_p = split_props({"padding_x": 2})
        assert box_p["padding_left"] == 2
        assert box_p["padding_right"] == 2

    def test_padding_y_expanded(self):
        text_p, box_p = split_props({"padding_y": 1})
        assert box_p["padding_top"] == 1
        assert box_p["padding_bottom"] == 1

    def test_regular_goes_to_box(self):
        text_p, box_p = split_props({"width": 100, "height": 50})
        assert box_p["width"] == 100
        assert box_p["height"] == 50

    def test_empty_props(self):
        text_p, box_p = split_props({})
        assert text_p == {}
        assert box_p == {}

    def test_mixed_props(self):
        text_p, box_p = split_props({
            "fg": "#FFF",
            "bold": True,
            "bg": "#000",
            "padding_x": 2,
            "width": 100,
        })
        assert "fg" in text_p
        assert "bold" in text_p
        assert "background_color" in box_p
        assert "padding_left" in box_p
        assert "width" in box_p


class TestResolveValue:
    def test_plain_value(self):
        assert resolve_value(42) == 42
        assert resolve_value("hello") == "hello"

    def test_none(self):
        assert resolve_value(None) is None

    def test_signal_like(self):
        class FakeSignal:
            def __init__(self, val):
                self._value = val
            def get(self):
                return self._value
            def __call__(self):
                return self._value

        sig = FakeSignal(42)
        assert resolve_value(sig) == 42
