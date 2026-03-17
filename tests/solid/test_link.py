"""Port of upstream link.test.tsx.

Upstream: packages/solid/tests/link.test.tsx
Tests ported: 15/15 (0 skipped)

All 15 tests are implemented using the TextNode / StyledChunk API, which is the
Python equivalent of the upstream text rendering pipeline.  TextNode.to_chunks()
mirrors upstream's textRenderable.textNode.gatherWithInheritedStyle(), and
TextNode.to_plain_text() mirrors charFrame text extraction.

The first 10 tests ("Link Rendering Tests") verify that TextNode trees produce
the correct plain text and link associations.  The last 5 tests ("Link Chunk
Verification") exercise more detailed style inheritance scenarios.
"""

from opentui.components.textnode import TextNode
from opentui import structs as s


class TestLinkRendering:
    """Link Rendering Tests"""

    def test_should_render_link_with_href_correctly(self):
        """Maps to it('should render link with href correctly').

        Upstream renders: <text>Visit <a href="...">opentui.com</a> for more info</text>
        and asserts the char frame contains the full string.
        """
        # Build: <text>Visit <a href="https://opentui.com">opentui.com</a> for more info</text>
        root = TextNode(
            children=[
                "Visit ",
                TextNode("opentui.com", link="https://opentui.com"),
                " for more info",
            ],
        )

        # Verify plain text matches expected full string
        plain = root.to_plain_text()
        assert "Visit " in plain
        assert "opentui.com" in plain
        assert "for more info" in plain

        # Verify the link chunk has the correct href
        chunks = root.to_chunks()
        link_chunk = next((c for c in chunks if "opentui.com" in c.text), None)
        assert link_chunk is not None
        assert link_chunk.style.link == "https://opentui.com"

        # Non-link chunks should not have a link
        non_link_chunks = [c for c in chunks if "opentui.com" not in c.text]
        for chunk in non_link_chunks:
            assert chunk.style.link is None, f"Chunk {chunk.text!r} should not have a link"

    def test_should_render_styled_link_with_underline(self):
        """Maps to it('should render styled link with underline').

        Upstream wraps a link in <u> and asserts char frame contains 'opentui.com'.
        """
        # Build: <text><u><a href="https://opentui.com">opentui.com</a></u></text>
        root = TextNode(
            children=[
                TextNode(
                    attributes=s.TEXT_ATTRIBUTE_UNDERLINE,
                    children=[
                        TextNode("opentui.com", link="https://opentui.com"),
                    ],
                ),
            ],
        )

        plain = root.to_plain_text()
        assert "opentui.com" in plain

        chunks = root.to_chunks()
        link_chunk = next((c for c in chunks if "opentui.com" in c.text), None)
        assert link_chunk is not None
        assert link_chunk.style.link == "https://opentui.com"
        assert link_chunk.style.attributes & s.TEXT_ATTRIBUTE_UNDERLINE

    def test_should_render_link_inside_text_with_other_elements(self):
        """Maps to it('should render link inside text with other elements').

        Upstream renders two <a> tags inside <text> and asserts both appear.
        """
        # Build: <text>Check <a href="...">link1</a> and <a href="...">link2</a></text>
        root = TextNode(
            children=[
                "Check ",
                TextNode("link1", link="https://example.com/1"),
                " and ",
                TextNode("link2", link="https://example.com/2"),
            ],
        )

        plain = root.to_plain_text()
        assert "Check " in plain
        assert "link1" in plain
        assert "link2" in plain

        chunks = root.to_chunks()
        link1_chunk = next((c for c in chunks if "link1" in c.text), None)
        link2_chunk = next((c for c in chunks if "link2" in c.text), None)

        assert link1_chunk is not None
        assert link1_chunk.style.link == "https://example.com/1"

        assert link2_chunk is not None
        assert link2_chunk.style.link == "https://example.com/2"

    def test_should_inherit_link_from_parent_to_nested_styled_span(self):
        """Maps to it('should inherit link from parent to nested styled span').

        Upstream renders <a> wrapping <span> + plain text and asserts both appear.
        """
        # Build: <a href="..."><span fg=red>styled</span> plain</a>
        root = TextNode(
            link="https://example.com",
            children=[
                TextNode("styled", fg="red"),
                " plain",
            ],
        )

        plain = root.to_plain_text()
        assert "styled" in plain
        assert "plain" in plain

        chunks = root.to_chunks()

        # Both chunks should inherit the link from the parent
        styled_chunk = next((c for c in chunks if "styled" in c.text), None)
        plain_chunk = next((c for c in chunks if "plain" in c.text), None)

        assert styled_chunk is not None
        assert styled_chunk.style.link == "https://example.com"

        assert plain_chunk is not None
        assert plain_chunk.style.link == "https://example.com"

    def test_should_inherit_link_from_parent_to_multiple_nested_elements(self):
        """Maps to it('should inherit link from parent to multiple nested elements').

        Upstream renders <a> wrapping <b>, <i>, <u> children.
        """
        # Build: <a href="..."><b>Bold</b><i>Italic</i><u>Underline</u></a>
        root = TextNode(
            link="https://example.com",
            children=[
                TextNode("Bold", attributes=s.TEXT_ATTRIBUTE_BOLD),
                TextNode("Italic", attributes=s.TEXT_ATTRIBUTE_ITALIC),
                TextNode("Underline", attributes=s.TEXT_ATTRIBUTE_UNDERLINE),
            ],
        )

        plain = root.to_plain_text()
        assert "Bold" in plain
        assert "Italic" in plain
        assert "Underline" in plain

        chunks = root.to_chunks()

        # All chunks should inherit the link
        for chunk in chunks:
            if chunk.text.strip():
                assert chunk.style.link == "https://example.com", (
                    f"Chunk {chunk.text!r} should have link"
                )

        # Verify individual style attributes are preserved
        bold_chunk = next(c for c in chunks if "Bold" in c.text)
        italic_chunk = next(c for c in chunks if "Italic" in c.text)
        underline_chunk = next(c for c in chunks if "Underline" in c.text)

        assert bold_chunk.style.attributes & s.TEXT_ATTRIBUTE_BOLD
        assert italic_chunk.style.attributes & s.TEXT_ATTRIBUTE_ITALIC
        assert underline_chunk.style.attributes & s.TEXT_ATTRIBUTE_UNDERLINE

    def test_should_inherit_link_to_deeply_nested_spans(self):
        """Maps to it('should inherit link to deeply nested spans').

        Upstream renders <a> wrapping nested <span> elements.
        """
        # Build: <a href="..."><span><span><span>deep</span></span></span></a>
        root = TextNode(
            link="https://example.com",
            children=[
                TextNode(
                    fg="red",
                    children=[
                        TextNode(
                            fg="green",
                            children=[
                                TextNode("deep", fg="blue"),
                            ],
                        ),
                    ],
                ),
            ],
        )

        plain = root.to_plain_text()
        assert "deep" in plain

        chunks = root.to_chunks()
        deep_chunk = next((c for c in chunks if "deep" in c.text), None)
        assert deep_chunk is not None
        assert deep_chunk.style.link == "https://example.com"

    def test_should_handle_mixed_linked_and_non_linked_text(self):
        """Maps to it('should handle mixed linked and non-linked text').

        Upstream renders plain text interspersed with two <a> tags.
        """
        # Build: <text>Hello <a href="...">World</a> and <a href="...">Foo</a> bar</text>
        root = TextNode(
            children=[
                "Hello ",
                TextNode("World", link="https://example.com/world"),
                " and ",
                TextNode("Foo", link="https://example.com/foo"),
                " bar",
            ],
        )

        plain = root.to_plain_text()
        assert "Hello " in plain
        assert "World" in plain
        assert " and " in plain
        assert "Foo" in plain
        assert " bar" in plain

        chunks = root.to_chunks()

        # Linked chunks should have their respective links
        world_chunk = next(c for c in chunks if "World" in c.text)
        foo_chunk = next(c for c in chunks if "Foo" in c.text)
        assert world_chunk.style.link == "https://example.com/world"
        assert foo_chunk.style.link == "https://example.com/foo"

        # Non-linked chunks should have no link
        hello_chunk = next(c for c in chunks if "Hello" in c.text)
        and_chunk = next(c for c in chunks if "and" in c.text)
        bar_chunk = next(c for c in chunks if "bar" in c.text)
        assert hello_chunk.style.link is None
        assert and_chunk.style.link is None
        assert bar_chunk.style.link is None

    def test_should_preserve_styles_when_inheriting_link(self):
        """Maps to it('should preserve styles when inheriting link').

        Upstream renders <a> wrapping <b>, <i>, <u>, and plain text.
        """
        # Build: <a href="..."><b>bold</b> <i>italic</i> <u>underline</u> plain</a>
        root = TextNode(
            link="https://example.com",
            children=[
                TextNode("bold", attributes=s.TEXT_ATTRIBUTE_BOLD),
                " ",
                TextNode("italic", attributes=s.TEXT_ATTRIBUTE_ITALIC),
                " ",
                TextNode("underline", attributes=s.TEXT_ATTRIBUTE_UNDERLINE),
                " plain",
            ],
        )

        chunks = root.to_chunks()

        # All non-empty chunks should have the link
        text_chunks = [c for c in chunks if c.text.strip()]
        for chunk in text_chunks:
            assert chunk.style.link == "https://example.com", (
                f"Chunk {chunk.text!r} should have link"
            )

        # Verify individual styles are preserved alongside the link
        bold_chunk = next(c for c in chunks if "bold" in c.text)
        italic_chunk = next(c for c in chunks if "italic" in c.text)
        underline_chunk = next(c for c in chunks if "underline" in c.text)
        plain_chunk = next(c for c in chunks if "plain" in c.text)

        assert bold_chunk.style.attributes & s.TEXT_ATTRIBUTE_BOLD
        assert italic_chunk.style.attributes & s.TEXT_ATTRIBUTE_ITALIC
        assert underline_chunk.style.attributes & s.TEXT_ATTRIBUTE_UNDERLINE
        assert plain_chunk.style.attributes == 0  # no style attributes

    def test_should_not_override_child_link_with_parent_link(self):
        """Maps to it('should not override child link with parent link').

        Upstream nests <a> inside <a> and asserts text from both appears.
        """
        # Build: <a href="https://parent.com">outer <a href="https://child.com">inner</a> outer</a>
        root = TextNode(
            link="https://parent.com",
            children=[
                "outer ",
                TextNode("inner", link="https://child.com"),
                " outer",
            ],
        )

        plain = root.to_plain_text()
        assert "outer" in plain
        assert "inner" in plain

        chunks = root.to_chunks()

        # Child link overrides parent link
        inner_chunk = next(c for c in chunks if "inner" in c.text)
        assert inner_chunk.style.link == "https://child.com"

        # Parent text retains parent link
        outer_chunks = [c for c in chunks if "outer" in c.text]
        assert len(outer_chunks) >= 1
        for chunk in outer_chunks:
            assert chunk.style.link == "https://parent.com", (
                f"Outer chunk {chunk.text!r} should have parent link"
            )

    def test_should_handle_empty_link_content(self):
        """Maps to it('should handle empty link content').

        Upstream renders an empty <a> between plain text.
        """
        # Build: <text>before <a href="https://example.com"></a> after</text>
        root = TextNode(
            children=[
                "before ",
                TextNode(link="https://example.com"),
                " after",
            ],
        )

        plain = root.to_plain_text()
        assert "before " in plain
        assert " after" in plain

        chunks = root.to_chunks()

        # The empty link should produce no chunks with link set
        # Only "before " and " after" chunks should exist
        assert len(chunks) >= 2

        before_chunk = next((c for c in chunks if "before" in c.text), None)
        after_chunk = next((c for c in chunks if "after" in c.text), None)

        assert before_chunk is not None
        assert before_chunk.style.link is None

        assert after_chunk is not None
        assert after_chunk.style.link is None

        # No chunk should have a link (since the link element is empty)
        for chunk in chunks:
            if chunk.text.strip():
                assert chunk.style.link is None, (
                    f"Chunk {chunk.text!r} should not have a link "
                    "(empty link element produces no linked content)"
                )

    class TestLinkChunkVerification:
        """Link Chunk Verification.

        These tests use TextNode.to_chunks() directly, which is the Python
        equivalent of the upstream textRenderable.textNode.gatherWithInheritedStyle().
        TextNode supports full link inheritance through its merge_styles() method.
        """

        def test_should_create_chunks_with_link_for_all_nested_content(self):
            """Maps to it('should create chunks with link for all nested content').

            Upstream:
                <a href="https://opentui.com">
                    <span style={{ fg: 'blue' }}>styled</span> plain
                </a>
            All non-empty chunks should carry the link.
            """
            # Build TextNode tree matching the upstream JSX structure:
            # <a href="..."><span fg=blue>styled</span> plain</a>
            link_node = TextNode(
                link="https://opentui.com",
                children=[
                    TextNode("styled", fg="blue"),
                    " plain",
                ],
            )

            chunks = link_node.to_chunks()

            # All non-empty chunks should have the link
            for chunk in chunks:
                if chunk.text.strip():
                    assert chunk.style.link is not None, f"Chunk {chunk.text!r} should have a link"
                    assert chunk.style.link == "https://opentui.com"

        def test_should_inherit_link_through_multiple_nesting_levels(self):
            """Maps to it('should inherit link through multiple nesting levels').

            Upstream:
                <a href="https://example.com">
                    <b><i><u>deeply nested</u></i></b>
                </a>
            The deeply nested text chunk should carry the link.
            """
            # Build: <a href="..."><b><i><u>deeply nested</u></i></b></a>
            # In TextNode terms, each style layer is a nested node.
            link_node = TextNode(
                link="https://example.com",
                children=[
                    TextNode(
                        attributes=s.TEXT_ATTRIBUTE_BOLD,
                        children=[
                            TextNode(
                                attributes=s.TEXT_ATTRIBUTE_ITALIC,
                                children=[
                                    TextNode(
                                        "deeply nested",
                                        attributes=s.TEXT_ATTRIBUTE_UNDERLINE,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            )

            chunks = link_node.to_chunks()

            # Find the chunk with text
            text_chunk = next((c for c in chunks if "deeply nested" in c.text), None)
            assert text_chunk is not None, "Should find 'deeply nested' chunk"
            assert text_chunk.style.link is not None
            assert text_chunk.style.link == "https://example.com"

            # Also verify style attributes accumulated through nesting
            expected_attrs = (
                s.TEXT_ATTRIBUTE_BOLD | s.TEXT_ATTRIBUTE_ITALIC | s.TEXT_ATTRIBUTE_UNDERLINE
            )
            assert text_chunk.style.attributes == expected_attrs

        def test_should_respect_child_link_over_parent_link(self):
            """Maps to it('should respect child link over parent link').

            Upstream:
                <a href="https://parent.com">
                    parent <a href="https://child.com">child</a> parent
                </a>
            Parent text chunks should have parent link; child chunk should
            have child link (child overrides parent).
            """
            # Build: <a href="parent.com">parent <a href="child.com">child</a> parent</a>
            link_node = TextNode(
                link="https://parent.com",
                children=[
                    "parent ",
                    TextNode("child", link="https://child.com"),
                    " parent",
                ],
            )

            chunks = link_node.to_chunks()

            # Find chunks
            parent_chunks = [c for c in chunks if "parent" in c.text]
            child_chunk = next((c for c in chunks if "child" in c.text), None)

            # Parent chunks should have parent link
            assert len(parent_chunks) >= 1
            for chunk in parent_chunks:
                assert chunk.style.link == "https://parent.com", (
                    f"Parent chunk {chunk.text!r} should have parent link"
                )

            # Child chunk should have child link (overrides parent)
            assert child_chunk is not None
            assert child_chunk.style.link == "https://child.com"

        def test_should_handle_mixed_styled_content_with_inherited_link(self):
            """Maps to it('should handle mixed styled content with inherited link').

            Upstream:
                <a href="https://opentui.com">
                    <b>Bold</b> <i>Italic</i> Plain
                </a>
            All text chunks should share the same link.
            """
            # Build: <a href="..."><b>Bold</b> <i>Italic</i> Plain</a>
            link_node = TextNode(
                link="https://opentui.com",
                children=[
                    TextNode("Bold", attributes=s.TEXT_ATTRIBUTE_BOLD),
                    " ",
                    TextNode("Italic", attributes=s.TEXT_ATTRIBUTE_ITALIC),
                    " Plain",
                ],
            )

            chunks = link_node.to_chunks()

            # All non-empty text chunks should have the same link
            text_chunks = [c for c in chunks if c.text.strip()]
            assert len(text_chunks) > 0

            for chunk in text_chunks:
                assert chunk.style.link == "https://opentui.com", (
                    f"Chunk {chunk.text!r} should have link"
                )

            # Verify individual styles are preserved alongside the link
            bold_chunk = next(c for c in chunks if "Bold" in c.text)
            italic_chunk = next(c for c in chunks if "Italic" in c.text)
            plain_chunk = next(c for c in chunks if "Plain" in c.text)

            assert bold_chunk.style.attributes & s.TEXT_ATTRIBUTE_BOLD
            assert italic_chunk.style.attributes & s.TEXT_ATTRIBUTE_ITALIC
            assert plain_chunk.style.attributes == 0  # no style attributes

        def test_should_only_apply_link_to_content_within_link_element(self):
            """Maps to it('should only apply link to content within link element').

            Upstream:
                <text>
                    before <a href="https://example.com">linked</a> after
                </text>
            Only the 'linked' chunk should have the link URL.
            """
            # Build: before <a href="...">linked</a> after
            # The root TextNode has no link; only the inner node does.
            root = TextNode(
                children=[
                    "before ",
                    TextNode("linked", link="https://example.com"),
                    " after",
                ],
            )

            chunks = root.to_chunks()

            before_chunk = next((c for c in chunks if "before" in c.text), None)
            linked_chunk = next((c for c in chunks if "linked" in c.text), None)
            after_chunk = next((c for c in chunks if "after" in c.text), None)

            # Only the linked chunk should have the link
            assert before_chunk is not None
            assert before_chunk.style.link is None

            assert linked_chunk is not None
            assert linked_chunk.style.link == "https://example.com"

            assert after_chunk is not None
            assert after_chunk.style.link is None
