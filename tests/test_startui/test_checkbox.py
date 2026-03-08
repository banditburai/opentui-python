"""Tests for Checkbox and RadioGroup components."""

from opentui.components import Box, Text
from startui.signals import Signal
from startui.checkbox import Checkbox, RadioGroup, RadioGroupItem


class TestCheckbox:
    def test_returns_box(self):
        assert isinstance(Checkbox(), Box)

    def test_unchecked_display(self):
        cb = Checkbox(checked=False, label="Option")
        children = cb.get_children()
        # Should have indicator + label
        assert len(children) >= 1

    def test_checked_display(self):
        cb = Checkbox(checked=True, label="Option")
        children = cb.get_children()
        assert len(children) >= 1

    def test_with_signal(self):
        s = Signal("checked", False)
        cb = Checkbox(checked=s, label="Toggle")
        assert isinstance(cb, Box)

    def test_label_text(self):
        cb = Checkbox(label="My Option")
        children = cb.get_children()
        # Should contain Text with label
        texts = [c for c in children if isinstance(c, Text)]
        assert any("My Option" in str(getattr(t, '_content', '')) for t in texts)

    def test_kwargs_passthrough(self):
        cb = Checkbox(width=20)
        assert cb._width == 20


class TestRadioGroup:
    def test_returns_box(self):
        rg = RadioGroup(
            RadioGroupItem("a", "Option A"),
            RadioGroupItem("b", "Option B"),
        )
        assert isinstance(rg, Box)

    def test_items_rendered(self):
        rg = RadioGroup(
            RadioGroupItem("a", "Option A"),
            RadioGroupItem("b", "Option B"),
            RadioGroupItem("c", "Option C"),
        )
        children = rg.get_children()
        assert len(children) == 3

    def test_selected_value(self):
        rg = RadioGroup(
            RadioGroupItem("a", "Option A"),
            RadioGroupItem("b", "Option B"),
            value="a",
        )
        assert isinstance(rg, Box)

    def test_with_signal(self):
        s = Signal("choice", "a")
        rg = RadioGroup(
            RadioGroupItem("a", "A"),
            RadioGroupItem("b", "B"),
            value=s,
        )
        assert isinstance(rg, Box)
