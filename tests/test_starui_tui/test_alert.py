"""Tests for Alert component."""

from opentui.components import Box, Text
from starui_tui.alert import Alert, AlertDescription, AlertTitle


class TestAlert:
    def test_returns_box(self):
        assert isinstance(Alert(), Box)

    def test_default_has_border(self):
        a = Alert()
        assert a.border is True

    def test_destructive_variant(self):
        a = Alert(variant="destructive")
        assert a.border is True

    def test_string_children_become_text(self):
        a = Alert("Warning message")
        children = a.get_children()
        assert len(children) >= 1
        assert isinstance(children[0], Text)

    def test_composition(self):
        a = Alert(
            AlertTitle("Heads up!"),
            AlertDescription("Something happened."),
            variant="default",
        )
        assert isinstance(a, Box)
        children = a.get_children()
        assert len(children) == 2


class TestAlertSubcomponents:
    def test_alert_title_bold(self):
        t = AlertTitle("Warning")
        assert isinstance(t, Text)
        assert t._bold is True

    def test_alert_description(self):
        d = AlertDescription("Details here")
        assert isinstance(d, Text)
