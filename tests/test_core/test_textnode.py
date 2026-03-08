"""Tests for TextNode component."""

from opentui.components.textnode import TextNode, TextStyle, StyledChunk
from opentui.structs import RGBA, TEXT_ATTRIBUTE_BOLD, TEXT_ATTRIBUTE_ITALIC


class TestTextNode:
    def test_basic_text(self):
        n = TextNode("hello")
        assert n.text == "hello"

    def test_set_text(self):
        n = TextNode("old")
        n.text = "new"
        assert n.text == "new"

    def test_to_plain_text(self):
        n = TextNode("hello ")
        n.append("world")
        assert n.to_plain_text() == "hello world"

    def test_to_plain_text_nested(self):
        root = TextNode("a")
        child = TextNode("b")
        child.append("c")
        root.append(child)
        assert root.to_plain_text() == "abc"

    def test_append_returns_self(self):
        n = TextNode("x")
        result = n.append("y")
        assert result is n

    def test_extend(self):
        n = TextNode("a")
        n.extend(["b", "c"])
        assert n.to_plain_text() == "abc"

    def test_to_chunks_simple(self):
        n = TextNode("hello", fg=RGBA(1, 0, 0))
        chunks = n.to_chunks()
        assert len(chunks) == 1
        assert chunks[0].text == "hello"
        assert chunks[0].style.fg == RGBA(1, 0, 0)

    def test_to_chunks_with_children(self):
        root = TextNode("parent ", fg=RGBA(1, 1, 1))
        root.append(TextNode("child", fg=RGBA(1, 0, 0)))
        chunks = root.to_chunks()
        assert len(chunks) == 2
        assert chunks[0].text == "parent "
        assert chunks[1].text == "child"
        assert chunks[1].style.fg == RGBA(1, 0, 0)

    def test_style_inheritance(self):
        root = TextNode("", fg=RGBA(1, 1, 1))
        root.append(TextNode("child"))  # No fg
        chunks = root.to_chunks()
        assert len(chunks) == 1
        assert chunks[0].style.fg == RGBA(1, 1, 1)  # Inherited

    def test_attribute_merge(self):
        root = TextNode("", attributes=TEXT_ATTRIBUTE_BOLD)
        root.append(TextNode("text", attributes=TEXT_ATTRIBUTE_ITALIC))
        chunks = root.to_chunks()
        assert chunks[0].style.attributes == (TEXT_ATTRIBUTE_BOLD | TEXT_ATTRIBUTE_ITALIC)

    def test_string_child_inherits_style(self):
        root = TextNode("", fg=RGBA(0, 1, 0))
        root.append("green text")
        chunks = root.to_chunks()
        assert chunks[0].text == "green text"
        assert chunks[0].style.fg == RGBA(0, 1, 0)

    def test_empty_text_skipped(self):
        n = TextNode("")
        chunks = n.to_chunks()
        assert len(chunks) == 0

    def test_repr(self):
        n = TextNode("hello")
        assert "hello" in repr(n)

    def test_repr_with_children(self):
        n = TextNode("parent")
        n.append(TextNode("child"))
        assert "children=1" in repr(n)

    def test_color_from_hex_string(self):
        n = TextNode("red", fg="#FF0000")
        chunks = n.to_chunks()
        assert chunks[0].style.fg is not None
        assert chunks[0].style.fg.r == 1.0


class TestTextStyle:
    def test_defaults(self):
        s = TextStyle()
        assert s.fg is None
        assert s.bg is None
        assert s.attributes == 0
        assert s.link is None
