"""Tests for Badge component."""

from opentui.components import Text
from startui.badge import Badge


class TestBadge:
    def test_returns_text(self):
        assert isinstance(Badge("New"), Text)

    def test_default_variant(self):
        b = Badge("OK")
        assert b._fg is not None  # Should have themed color

    def test_destructive_variant(self):
        b = Badge("Error", variant="destructive")
        assert isinstance(b, Text)

    def test_outline_variant_has_fg(self):
        b = Badge("Info", variant="outline")
        assert isinstance(b, Text)
        assert b._fg is not None

    def test_secondary_variant(self):
        b = Badge("Note", variant="secondary")
        assert isinstance(b, Text)

    def test_kwargs_passthrough(self):
        b = Badge("Bold", bold=True)
        assert b._bold is True

    def test_all_variants(self):
        for v in ("default", "secondary", "destructive", "outline"):
            assert isinstance(Badge("X", variant=v), Text)
