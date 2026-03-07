"""Tests for Label + Typography components."""

from opentui.components import Text
from starui_tui.typography import H1, H2, H3, H4, P, Label, Large, Lead, Muted, Small, InlineCode


class TestLabel:
    def test_returns_text(self):
        assert isinstance(Label("Name"), Text)

    def test_bold(self):
        l = Label("Name")
        assert l._bold is True


class TestHeadings:
    def test_h1_bold(self):
        h = H1("Title")
        assert isinstance(h, Text)
        assert h._bold is True

    def test_h2_bold(self):
        h = H2("Subtitle")
        assert isinstance(h, Text)
        assert h._bold is True

    def test_h3_bold(self):
        h = H3("Section")
        assert isinstance(h, Text)
        assert h._bold is True

    def test_h4_bold(self):
        h = H4("Subsection")
        assert isinstance(h, Text)
        assert h._bold is True


class TestParagraphStyles:
    def test_p(self):
        p = P("Body text")
        assert isinstance(p, Text)

    def test_lead(self):
        l = Lead("Introduction")
        assert isinstance(l, Text)

    def test_large(self):
        l = Large("Big text")
        assert isinstance(l, Text)

    def test_small(self):
        s = Small("Fine print")
        assert isinstance(s, Text)

    def test_muted(self):
        m = Muted("Secondary text")
        assert isinstance(m, Text)
        assert m._fg is not None

    def test_inline_code(self):
        c = InlineCode("var x = 1")
        assert isinstance(c, Text)
        assert c._fg is not None

    def test_kwargs_passthrough(self):
        p = P("Custom", fg="#ff0000")
        assert p._fg is not None
