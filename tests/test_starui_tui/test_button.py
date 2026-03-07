"""Tests for Button component."""

from opentui.components import Box, Text
from starui_tui.button import Button


class TestButton:
    def test_returns_box(self):
        btn = Button("Click me")
        assert isinstance(btn, Box)

    def test_contains_text(self):
        btn = Button("Hello")
        children = btn.get_children()
        assert len(children) >= 1
        text_child = children[0]
        assert isinstance(text_child, Text)

    def test_default_variant_has_border(self):
        btn = Button("OK", variant="default")
        assert btn.border is True

    def test_destructive_variant(self):
        btn = Button("Delete", variant="destructive")
        assert btn.border is True

    def test_ghost_variant_no_border(self):
        btn = Button("Ghost", variant="ghost")
        assert btn.border is False

    def test_disabled_dims_text(self):
        btn = Button("No", disabled=True)
        children = btn.get_children()
        text_child = children[0]
        # Disabled button should have dimmed fg
        assert text_child._fg is not None

    def test_on_click_handler(self):
        clicked = []
        btn = Button("Click", on_click=lambda: clicked.append(True))
        assert btn.on_mouse_down is not None

    def test_size_sm(self):
        btn = Button("Small", size="sm")
        assert btn._padding_left == 1

    def test_size_lg(self):
        btn = Button("Large", size="lg")
        # lg has padding_x=3

    def test_kwargs_passthrough(self):
        btn = Button("Custom", width=20)
        assert btn._width == 20

    def test_multiple_children(self):
        btn = Button("Hello", "World")
        children = btn.get_children()
        text = children[0]
        assert isinstance(text, Text)

    def test_all_variants(self):
        for variant in ("default", "destructive", "outline", "secondary", "ghost", "link"):
            btn = Button("Test", variant=variant)
            assert isinstance(btn, Box)
