"""Tests for Card component."""

from opentui.components import Box, Text
from starui_tui.card import Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle


class TestCard:
    def test_returns_box(self):
        assert isinstance(Card(), Box)

    def test_has_border(self):
        c = Card()
        assert c.border is True

    def test_has_round_border_style(self):
        c = Card()
        assert c.border_style == "round"

    def test_has_background_color(self):
        c = Card()
        assert c._background_color is not None

    def test_has_padding(self):
        c = Card()
        assert c._padding_top == 1

    def test_children_passed_through(self):
        inner = Text("hello")
        c = Card(inner)
        assert inner in c.get_children()

    def test_kwargs_override_theme(self):
        c = Card(border=False)
        assert c.border is False


class TestCardSubcomponents:
    def test_card_header(self):
        assert isinstance(CardHeader(), Box)

    def test_card_header_column_direction(self):
        h = CardHeader()
        assert h._flex_direction == "column"

    def test_card_title(self):
        t = CardTitle("Title")
        assert isinstance(t, Text)
        assert t._bold is True

    def test_card_description(self):
        d = CardDescription("Desc")
        assert isinstance(d, Text)

    def test_card_description_muted_fg(self):
        d = CardDescription("Desc")
        assert d._fg is not None

    def test_card_content(self):
        assert isinstance(CardContent(), Box)

    def test_card_footer_row_direction(self):
        f = CardFooter()
        assert isinstance(f, Box)
        assert f._flex_direction == "row"

    def test_card_footer_end_justify(self):
        f = CardFooter()
        assert f._justify_content == "flex-end"

    def test_full_card_composition(self):
        card = Card(
            CardHeader(
                CardTitle("My Card"),
                CardDescription("A description"),
            ),
            CardContent(Text("Body text")),
            CardFooter(Text("Footer")),
        )
        assert isinstance(card, Box)
        assert len(card.get_children()) == 3
