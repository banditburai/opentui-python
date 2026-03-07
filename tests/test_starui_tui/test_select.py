"""Tests for Select component."""

from opentui.components import Box, Text
from starui_tui.select import Select, SelectItem


class TestSelect:
    def test_returns_box(self):
        s = Select(
            SelectItem("a", "Option A"),
            SelectItem("b", "Option B"),
        )
        assert isinstance(s, Box)

    def test_trigger_shows_selected(self):
        s = Select(
            SelectItem("a", "Option A"),
            SelectItem("b", "Option B"),
            value="a",
        )
        assert isinstance(s, Box)

    def test_no_selection_shows_placeholder(self):
        s = Select(
            SelectItem("a", "Option A"),
            placeholder="Pick one...",
        )
        assert isinstance(s, Box)

    def test_items_present(self):
        s = Select(
            SelectItem("a", "Alpha"),
            SelectItem("b", "Beta"),
            SelectItem("c", "Charlie"),
        )
        assert isinstance(s, Box)

    def test_has_border(self):
        s = Select(
            SelectItem("a", "Option A"),
        )
        assert s.border is True

    def test_kwargs_passthrough(self):
        s = Select(
            SelectItem("a", "A"),
            width=30,
        )
        assert s._width == 30


class TestSelectItem:
    def test_value_and_label(self):
        item = SelectItem("val", "Label")
        assert item.value == "val"
        assert item.label == "Label"
