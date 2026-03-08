"""Tests for Accordion with context injection."""

from opentui.components import Box, Text
from startui.signals import Signal
from startui.accordion import Accordion, AccordionItem, AccordionTrigger, AccordionContent


class TestAccordion:
    def test_returns_box(self):
        a = Accordion(
            AccordionItem("section1", "Title 1", Text("Content 1")),
        )
        assert isinstance(a, Box)

    def test_multiple_items(self):
        a = Accordion(
            AccordionItem("s1", "Title 1", Text("Content 1")),
            AccordionItem("s2", "Title 2", Text("Content 2")),
        )
        children = a.get_children()
        assert len(children) == 2


class TestAccordionItem:
    def test_returns_box(self):
        item = AccordionItem("s1", "Title", Text("Content"))
        sig = Signal("accordion", set())
        result = item(open_items=sig)
        assert isinstance(result, Box)

    def test_closed_hides_content(self):
        item = AccordionItem("s1", "Title", Text("Content"))
        sig = Signal("accordion", set())
        result = item(open_items=sig)
        children = result.get_children()
        # Should have trigger + hidden content
        assert len(children) == 2

    def test_open_shows_content(self):
        item = AccordionItem("s1", "Title", Text("Content"))
        sig = Signal("accordion", {"s1"})
        result = item(open_items=sig)
        children = result.get_children()
        assert len(children) == 2


class TestAccordionTrigger:
    def test_returns_box(self):
        t = AccordionTrigger("Click me")
        assert isinstance(t, Box)

    def test_has_click_handler(self):
        sig = Signal("accordion", set())
        t = AccordionTrigger("Click me", item_value="s1", open_items=sig)
        assert t.on_mouse_down is not None


class TestAccordionContent:
    def test_visible_when_open(self):
        c = AccordionContent(Text("Content"), item_value="s1", is_open=True)
        assert c._visible is True

    def test_hidden_when_closed(self):
        c = AccordionContent(Text("Content"), item_value="s1", is_open=False)
        assert c._visible is False
