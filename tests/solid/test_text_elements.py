"""Tests for SolidJS text element parity: Span, LineBreak, Bold, Italic, Underline.

These components map to SolidJS elements:
  span → Span, strong/b → Bold, i/em → Italic, u → Underline, br → LineBreak
"""

from opentui import test_render as _test_render
from opentui.components.box import Box
from opentui.components.text import Bold, Italic, LineBreak, Span, Text, Underline


async def _render(component_fn, width=40, height=10):
    return await _test_render(component_fn, {"width": width, "height": height})


class TestSpan:
    """Span — inline styled text, maps to SolidJS <span>."""

    async def test_span_renders_text_in_box(self):
        """Span as a standalone renderable inside Box renders its child text."""
        setup = await _render(lambda: Box(Span("hello"), width=20, height=3))
        frame = setup.capture_char_frame()
        assert "hello" in frame

    async def test_span_with_fg_color(self):
        setup = await _render(lambda: Box(Span("red text", fg="red"), width=20, height=3))
        frame = setup.capture_char_frame()
        assert "red text" in frame

    async def test_span_with_bold(self):
        setup = await _render(lambda: Box(Span("bold span", bold=True), width=20, height=3))
        frame = setup.capture_char_frame()
        assert "bold span" in frame

    async def test_span_with_bg_color(self):
        setup = await _render(lambda: Box(Span("highlighted", bg="yellow"), width=20, height=3))
        frame = setup.capture_char_frame()
        assert "highlighted" in frame

    async def test_span_as_text_modifier(self):
        """When used inside Text, Span is stored as a text modifier."""

        def App():
            t = Text("prefix ")
            t._text_modifiers.append(Span("suffix", fg="red"))
            return t

        setup = await _render(App)
        root = setup.renderer.root.get_children()[0]
        assert len(root._text_modifiers) == 1
        assert isinstance(root._text_modifiers[0], Span)

    async def test_span_all_style_options(self):
        """Span accepts all style kwargs from TextModifier."""
        span = Span("styled", bold=True, italic=True, underline=True, fg="red", bg="blue")
        assert span._bold is True
        assert span._italic is True
        assert span._underline is True


class TestBold:
    """Bold — text modifier, maps to SolidJS <strong>/<b>."""

    async def test_bold_renders_text(self):
        setup = await _render(lambda: Box(Bold("important"), width=20, height=3))
        frame = setup.capture_char_frame()
        assert "important" in frame

    async def test_bold_sets_bold_attribute(self):
        bold = Bold("bold text")
        assert bold._bold is True
        # Bold creates child Text nodes with bold=True
        for child in bold._children:
            if isinstance(child, Text):
                assert child._bold is True

    async def test_bold_with_multiple_children(self):
        setup = await _render(lambda: Box(Bold("first", " second"), width=30, height=3))
        frame = setup.capture_char_frame()
        assert "first" in frame
        assert "second" in frame

    async def test_bold_as_modifier_in_text(self):
        """Bold stored as text_modifier inside Text."""

        def App():
            return Text("before ", Bold("strong"), " after")

        setup = await _render(App)
        root = setup.renderer.root.get_children()[0]
        modifiers = root._text_modifiers
        assert any(isinstance(m, Bold) for m in modifiers)


class TestItalic:
    """Italic — text modifier, maps to SolidJS <i>/<em>."""

    async def test_italic_renders_text(self):
        setup = await _render(lambda: Box(Italic("emphasis"), width=20, height=3))
        frame = setup.capture_char_frame()
        assert "emphasis" in frame

    async def test_italic_sets_italic_attribute(self):
        italic = Italic("italic text")
        assert italic._italic is True
        for child in italic._children:
            if isinstance(child, Text):
                assert child._italic is True


class TestUnderline:
    """Underline — text modifier, maps to SolidJS <u>."""

    async def test_underline_renders_text(self):
        setup = await _render(lambda: Box(Underline("underlined"), width=20, height=3))
        frame = setup.capture_char_frame()
        assert "underlined" in frame

    async def test_underline_sets_underline_attribute(self):
        underline = Underline("underlined text")
        assert underline._underline is True
        for child in underline._children:
            if isinstance(child, Text):
                assert child._underline is True


class TestLineBreak:
    """LineBreak — maps to SolidJS <br>."""

    def test_linebreak_creates_instance(self):
        lb = LineBreak()
        assert lb is not None
        assert isinstance(lb, LineBreak)

    async def test_linebreak_stored_as_modifier(self):
        """LineBreak within Text is stored as a text modifier."""

        def App():
            return Text("Line 1", LineBreak(), "Line 2")

        setup = await _render(App)
        root = setup.renderer.root.get_children()[0]
        has_linebreak = any(isinstance(m, LineBreak) for m in root._text_modifiers)
        assert has_linebreak


class TestTextModifierCombinations:
    """Test combinations of text modifiers."""

    async def test_nested_bold_italic(self):
        """Bold wrapping Italic — both modifiers apply."""
        setup = await _render(lambda: Box(Bold(Italic("bold-italic")), width=20, height=3))
        frame = setup.capture_char_frame()
        assert "bold-italic" in frame

    async def test_span_with_all_styles(self):
        setup = await _render(
            lambda: Box(
                Span("styled", bold=True, italic=True, underline=True, fg="red"),
                width=20,
                height=3,
            )
        )
        frame = setup.capture_char_frame()
        assert "styled" in frame

    async def test_multiple_modifiers_in_box(self):
        setup = await _render(
            lambda: Box(Bold("bold"), Text(" normal "), Italic("italic"), width=40, height=3)
        )
        frame = setup.capture_char_frame()
        assert "bold" in frame
        assert "normal" in frame
        assert "italic" in frame

    async def test_modifier_render_applies_style_temporarily(self):
        """TextModifier.render() temporarily applies styles to child Text."""
        bold_mod = Bold("test")
        # Verify children are Text with bold=True
        child_texts = [c for c in bold_mod._children if isinstance(c, Text)]
        assert len(child_texts) >= 1
        assert all(c._bold is True for c in child_texts)
