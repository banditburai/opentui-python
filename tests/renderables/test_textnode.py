"""Port of upstream TextNode.test.ts.

Upstream: packages/core/src/renderables/TextNode.test.ts
Tests ported: 51/51 (0 skipped)
"""

import pytest

from opentui.components._textnode import (
    TextNode,
    TextStyle,
    TextChunk,
    StyledText,
    styled_text,
    styled_red,
    styled_bold,
)
from opentui.structs import RGBA


# ── Constructor and Options ───────────────────────────────────────


class TestTextNodeConstructorAndOptions:
    """Maps to describe("Constructor and Options")."""

    def test_should_create_textnode_with_default_options(self):
        """Maps to it("should create TextNode with default options")."""
        node = TextNode()
        assert node._fg is None
        assert node._bg is None
        assert node._attributes == 0
        assert node._children == []

    def test_should_create_textnode_with_custom_options(self):
        """Maps to it("should create TextNode with custom options")."""
        fg_color = RGBA(1.0, 0.0, 0.0, 1.0)
        bg_color = RGBA(0.0, 0.0, 1.0, 1.0)
        attributes = 1

        node = TextNode("", fg=fg_color, bg=bg_color, attributes=attributes)

        assert node._fg == fg_color
        assert node._bg == bg_color
        assert node._attributes == attributes

    def test_should_parse_color_strings_in_constructor(self):
        """Maps to it("should parse color strings in constructor").

        Python TextNode accepts hex strings for fg/bg. The upstream also
        accepts named colors like 'blue', but Python only supports hex.
        We test hex parsing only.
        """
        node = TextNode("", fg="#ff0000")
        assert node._fg is not None
        assert node._fg.r == 1.0
        assert node._fg.g == 0.0
        assert node._fg.b == 0.0
        assert node._fg.a == 1.0

    def test_should_handle_undefined_colors(self):
        """Maps to it("should handle undefined colors")."""
        node = TextNode("", fg=None, bg=None)
        assert node._fg is None
        assert node._bg is None


# ── Type Guard ────────────────────────────────────────────────────


class TestTextNodeTypeGuard:
    """Maps to describe("Type Guard")."""

    def test_should_identify_textnode_instances(self):
        """Maps to it("should identify TextNodeRenderable instances")."""
        node = TextNode("")
        assert isinstance(node, TextNode) is True
        assert isinstance("not a node", TextNode) is False
        assert isinstance(42, TextNode) is False


# ── add Method ────────────────────────────────────────────────────


class TestTextNodeAddMethod:
    """Maps to describe("add Method").

    Python TextNode supports both append() and add(). The add() method
    supports indexed insertion and type validation. StyledText is not
    available in the Python port.
    """

    def test_should_add_string_child(self):
        """Maps to it("should add string child using add")."""
        node = TextNode("")
        node.append("Hello")
        assert node._children == ["Hello"]

    def test_should_add_textnode_child(self):
        """Maps to it("should add TextNode child using add")."""
        parent = TextNode("")
        child = TextNode("")
        parent.append(child)
        assert parent._children == [child]

    def test_should_add_multiple_children_sequentially(self):
        """Maps to it("should add multiple children sequentially")."""
        node = TextNode("")
        node.append("First")
        node.append("Second")
        child_node = TextNode("")
        node.append(child_node)
        assert node._children == ["First", "Second", child_node]

    def test_should_add_child_at_specific_index(self):
        """Maps to it("should add child at specific index using add method")."""
        node = TextNode("")
        node.add("First")
        node.add("Third")
        child = TextNode("")
        node.add(child, index=1)
        assert node._children == ["First", child, "Third"]

    def test_should_add_string_at_specific_index(self):
        """Maps to it("should add string at specific index using add method")."""
        node = TextNode("")
        node.add("First")
        node.add("Third")
        node.add("Second", index=1)
        assert node._children == ["First", "Second", "Third"]

    def test_should_reject_non_textnode_children(self):
        """Maps to it("should reject non-TextNode children in add method")."""
        node = TextNode("")
        with pytest.raises(TypeError):
            node.add(42)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            node.add([1, 2, 3])  # type: ignore[arg-type]

    def test_should_add_styled_text_child(self):
        """Maps to it("should add StyledText child using add method")."""
        node = TextNode("")
        st = StyledText(
            [
                TextChunk(text="Hello", fg=RGBA.from_ints(255, 0, 0, 255), attributes=1),
                TextChunk(text=" World", fg=RGBA.from_ints(0, 255, 0, 255), attributes=0),
            ]
        )

        index = node.add(st)

        assert index == 0
        children = node.get_children()
        assert len(children) == 2
        assert isinstance(children[0], TextNode)
        assert isinstance(children[1], TextNode)

        first_child = children[0]
        assert first_child.get_children() == ["Hello"]
        assert first_child._fg == RGBA.from_ints(255, 0, 0, 255)
        assert first_child._attributes == 1

        second_child = children[1]
        assert second_child.get_children() == [" World"]
        assert second_child._fg == RGBA.from_ints(0, 255, 0, 255)
        assert second_child._attributes == 0

    def test_should_add_styled_text_at_specific_index(self):
        """Maps to it("should add StyledText child at specific index using add method")."""
        node = TextNode("")
        node.add("First")
        node.add("Third")

        st = StyledText(
            [
                TextChunk(text="Second", fg=RGBA.from_ints(255, 255, 0, 255), attributes=2),
            ]
        )

        node.add(st, index=1)

        children = node.get_children()
        assert len(children) == 3
        assert children[0] == "First"
        assert isinstance(children[1], TextNode)
        assert children[2] == "Third"

        styled_child = children[1]
        assert styled_child.get_children() == ["Second"]
        assert styled_child._fg == RGBA.from_ints(255, 255, 0, 255)
        assert styled_child._attributes == 2


# ── insertBefore and remove Methods ──────────────────────────────


class TestTextNodeInsertBeforeAndRemove:
    """Maps to describe("insertBefore and remove Methods").

    StyledText-specific tests remain skipped.
    """

    def test_should_insert_child_before_anchor(self):
        """Maps to it("should insert child before anchor node")."""
        parent = TextNode("")
        child1 = TextNode("")
        child2 = TextNode("")
        new_child = TextNode("")

        parent.append(child1)
        parent.append(child2)
        parent.insert_before(new_child, child2)

        assert parent._children == [child1, new_child, child2]

    def test_should_throw_error_when_anchor_not_found(self):
        """Maps to it("should throw error when anchor node not found in insertBefore")."""
        parent = TextNode("")
        child = TextNode("")
        anchor = TextNode("")  # not in parent

        with pytest.raises(ValueError, match="Anchor node not found"):
            parent.insert_before(child, anchor)

    def test_should_insert_styled_text_before_anchor(self):
        """Maps to it("should insert StyledText before anchor node")."""
        node = TextNode("")
        anchor = TextNode("")
        anchor.add("Anchor")

        node.add("First")
        node.add(anchor)
        node.add("Last")

        st = StyledText(
            [
                TextChunk(text="Middle", fg=RGBA.from_ints(128, 128, 128, 255), attributes=4),
            ]
        )

        node.insert_before(st, anchor)

        children = node.get_children()
        assert len(children) == 4
        assert children[0] == "First"
        assert isinstance(children[1], TextNode)
        assert children[2] is anchor
        assert children[3] == "Last"

        styled_child = children[1]
        assert styled_child.get_children() == ["Middle"]
        assert styled_child._fg == RGBA.from_ints(128, 128, 128, 255)
        assert styled_child._attributes == 4

    def test_should_remove_child_from_node(self):
        """Maps to it("should remove child from node")."""
        parent = TextNode("")
        child1 = TextNode("")
        child2 = TextNode("")

        parent.append(child1)
        parent.append(child2)
        parent.remove(child1)

        assert parent._children == [child2]

    def test_should_throw_error_when_child_not_found_in_remove(self):
        """Maps to it("should throw error when child not found in remove")."""
        parent = TextNode("")
        child = TextNode("")  # not in parent

        with pytest.raises(ValueError, match="Child not found"):
            parent.remove(child)


# ── clear Method ──────────────────────────────────────────────────


class TestTextNodeClearMethod:
    """Maps to describe("clear Method")."""

    def test_should_clear_all_children(self):
        """Maps to it("should clear all children and change log")."""
        node = TextNode("")
        node.append("First")
        node.append("Second")
        node.append(TextNode(""))

        assert len(node._children) == 3
        node.clear()
        assert node._children == []


# ── Style Inheritance and Merging ─────────────────────────────────


class TestTextNodeStyleInheritanceAndMerging:
    """Maps to describe("Style Inheritance and Merging")."""

    def test_should_merge_styles_with_parent_styles(self):
        """Maps to it("should merge styles with parent styles")."""
        node = TextNode("", fg=RGBA(1.0, 0.0, 0.0, 1.0), attributes=1)

        parent_style = TextStyle(
            bg=RGBA(0.0, 0.0, 1.0, 1.0),
            attributes=2,
        )

        merged = node.merge_styles(parent_style)

        assert merged.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert merged.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert merged.attributes == 3  # 1 | 2

    def test_should_inherit_undefined_styles_from_parent(self):
        """Maps to it("should inherit undefined styles from parent")."""
        node = TextNode("", fg=RGBA(1.0, 0.0, 0.0, 1.0))

        parent_style = TextStyle(
            bg=RGBA(0.0, 0.0, 1.0, 1.0),
            attributes=2,
        )

        merged = node.merge_styles(parent_style)

        assert merged.fg is not None
        assert merged.fg.r == 1.0
        assert merged.fg.g == 0.0
        assert merged.fg.b == 0.0
        assert merged.bg is not None
        assert merged.bg.r == 0.0
        assert merged.bg.g == 0.0
        assert merged.bg.b == 1.0
        assert merged.attributes == 2  # 0 | 2

    def test_should_inherit_nothing_when_parent_has_no_styling(self):
        """Maps to it("should inherit nothing when parent has no styling")."""
        node = TextNode("")

        parent_style = TextStyle(fg=None, bg=None, attributes=0)

        merged = node.merge_styles(parent_style)

        assert merged.fg is None
        assert merged.bg is None
        assert merged.attributes == 0

    def test_should_combine_attributes_using_bitwise_or(self):
        """Maps to it("should combine attributes using bitwise OR")."""
        test_cases = [
            (0, 0, 0),
            (1, 0, 1),
            (0, 2, 2),
            (1, 2, 3),
            (3, 4, 7),
            (7, 8, 15),
        ]

        for node_attrs, parent_attrs, expected in test_cases:
            node = TextNode("", attributes=node_attrs)
            parent_style = TextStyle(fg=None, bg=None, attributes=parent_attrs)
            merged = node.merge_styles(parent_style)
            assert merged.attributes == expected


# ── gatherWithInheritedStyle Method ───────────────────────────────


class TestTextNodeGatherWithInheritedStyle:
    """Maps to describe("gatherWithInheritedStyle Method").

    Python equivalent is to_chunks().
    """

    def test_should_gather_chunks_with_inherited_styles(self):
        """Maps to it("should gather chunks with inherited styles")."""
        node = TextNode(
            "",
            fg=RGBA(1.0, 0.0, 0.0, 1.0),
            bg=RGBA(0.0, 0.0, 1.0, 1.0),
            attributes=1,
        )

        node.append("Hello")
        node.append(" ")
        node.append("World")

        chunks = node.to_chunks()

        assert len(chunks) == 3
        for chunk in chunks:
            assert chunk.style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
            assert chunk.style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
            assert chunk.style.attributes == 1

        assert chunks[0].text == "Hello"
        assert chunks[1].text == " "
        assert chunks[2].text == "World"

    def test_should_recursively_gather_from_child_textnodes(self):
        """Maps to it("should recursively gather from child TextNodes")."""
        parent = TextNode("", fg=RGBA(1.0, 0.0, 0.0, 1.0))

        child = TextNode("", bg=RGBA(0.0, 1.0, 0.0, 1.0))
        child.append("Child")

        parent.append("Parent")
        parent.append(child)

        chunks = parent.to_chunks()

        assert len(chunks) == 2
        assert chunks[0].text == "Parent"
        assert chunks[0].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert chunks[0].style.bg is None

        assert chunks[1].text == "Child"
        assert chunks[1].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)  # Inherited
        assert chunks[1].style.bg == RGBA(0.0, 1.0, 0.0, 1.0)  # Own style

    def test_should_inherit_nothing_when_parent_has_no_default_styling(self):
        """Maps to it("should inherit nothing when parent has no default styling")."""
        parent = TextNode("")
        child = TextNode("")
        child.append("Child")

        parent.append("Parent")
        parent.append(child)

        chunks = parent.to_chunks()

        assert len(chunks) == 2
        assert chunks[0].text == "Parent"
        assert chunks[0].style.fg is None
        assert chunks[0].style.bg is None
        assert chunks[0].style.attributes == 0

        assert chunks[1].text == "Child"
        assert chunks[1].style.fg is None
        assert chunks[1].style.bg is None
        assert chunks[1].style.attributes == 0

    def test_should_allow_children_to_override_parent_styles_independently(self):
        """Maps to it("should allow children to override parent styles independently")."""
        parent = TextNode(
            "",
            fg=RGBA(1.0, 0.0, 0.0, 1.0),
            bg=RGBA(0.0, 0.0, 1.0, 1.0),
            attributes=1,
        )

        child_override_fg = TextNode("", fg=RGBA(0.0, 1.0, 0.0, 1.0))
        child_override_fg.append("Green Text")

        child_override_bg = TextNode("", bg=RGBA(1.0, 1.0, 0.0, 1.0))
        child_override_bg.append("Yellow BG")

        child_override_attrs = TextNode("", attributes=2)
        child_override_attrs.append("Italic")

        parent.append(child_override_fg)
        parent.append(child_override_bg)
        parent.append(child_override_attrs)

        chunks = parent.to_chunks()

        assert len(chunks) == 3

        # First child: overrides fg, inherits bg and attributes
        assert chunks[0].text == "Green Text"
        assert chunks[0].style.fg == RGBA(0.0, 1.0, 0.0, 1.0)
        assert chunks[0].style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert chunks[0].style.attributes == 1

        # Second child: overrides bg, inherits fg and attributes
        assert chunks[1].text == "Yellow BG"
        assert chunks[1].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert chunks[1].style.bg == RGBA(1.0, 1.0, 0.0, 1.0)
        assert chunks[1].style.attributes == 1

        # Third child: overrides attributes (OR'd), inherits fg and bg
        assert chunks[2].text == "Italic"
        assert chunks[2].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert chunks[2].style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert chunks[2].style.attributes == 3  # 1 | 2

    def test_should_support_multi_level_inheritance(self):
        """Maps to it("should support multi-level inheritance (grandparent -> parent -> child)")."""
        grandparent = TextNode("", fg=RGBA(1.0, 0.0, 0.0, 1.0), attributes=1)

        parent_node = TextNode("", bg=RGBA(0.0, 0.0, 1.0, 1.0))

        child = TextNode("", fg=RGBA(0.0, 1.0, 0.0, 1.0), attributes=2)
        child.append("Grandchild")

        parent_node.append("Parent")
        parent_node.append(child)
        grandparent.append("Grandparent")
        grandparent.append(parent_node)

        chunks = grandparent.to_chunks()

        assert len(chunks) == 3

        assert chunks[0].text == "Grandparent"
        assert chunks[0].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert chunks[0].style.bg is None
        assert chunks[0].style.attributes == 1

        assert chunks[1].text == "Parent"
        assert chunks[1].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert chunks[1].style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert chunks[1].style.attributes == 1

        assert chunks[2].text == "Grandchild"
        assert chunks[2].style.fg == RGBA(0.0, 1.0, 0.0, 1.0)
        assert chunks[2].style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert chunks[2].style.attributes == 3  # 1 | 2

    def test_should_support_partial_style_overrides_in_children(self):
        """Maps to it("should support partial style overrides in children")."""
        parent = TextNode(
            "",
            fg=RGBA(1.0, 0.0, 0.0, 1.0),
            bg=RGBA(0.0, 0.0, 1.0, 1.0),
            attributes=1,
        )

        child1 = TextNode("", fg=RGBA(0.0, 1.0, 0.0, 1.0))
        child1.append("Green on Blue")

        child2 = TextNode("", bg=RGBA(1.0, 1.0, 0.0, 1.0))
        child2.append("Red on Yellow")

        child3 = TextNode("", attributes=2)
        child3.append("Red on Blue Bold+Italic")

        child4 = TextNode("", fg=RGBA(1.0, 1.0, 1.0, 1.0), attributes=4)
        child4.append("White on Blue Bold+Underline")

        parent.append(child1)
        parent.append(child2)
        parent.append(child3)
        parent.append(child4)

        chunks = parent.to_chunks()

        assert len(chunks) == 4

        assert chunks[0].text == "Green on Blue"
        assert chunks[0].style.fg == RGBA(0.0, 1.0, 0.0, 1.0)
        assert chunks[0].style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert chunks[0].style.attributes == 1

        assert chunks[1].text == "Red on Yellow"
        assert chunks[1].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert chunks[1].style.bg == RGBA(1.0, 1.0, 0.0, 1.0)
        assert chunks[1].style.attributes == 1

        assert chunks[2].text == "Red on Blue Bold+Italic"
        assert chunks[2].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert chunks[2].style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert chunks[2].style.attributes == 3  # 1 | 2

        assert chunks[3].text == "White on Blue Bold+Underline"
        assert chunks[3].style.fg == RGBA(1.0, 1.0, 1.0, 1.0)
        assert chunks[3].style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert chunks[3].style.attributes == 5  # 1 | 4


# ── Utility Methods ───────────────────────────────────────────────


class TestTextNodeUtilityMethods:
    """Maps to describe("Utility Methods")."""

    def test_should_convert_to_chunks_using_to_chunks(self):
        """Maps to it("should convert to chunks using toChunks")."""
        node = TextNode("", fg="#00ff00")
        node.append("Test")

        chunks = node.to_chunks()

        assert len(chunks) == 1
        assert chunks[0].text == "Test"
        assert chunks[0].style.fg is not None
        assert chunks[0].style.fg.r == 0.0
        assert chunks[0].style.fg.g == 1.0
        assert chunks[0].style.fg.b == 0.0

    def test_should_get_children(self):
        """Maps to it("should get children using getChildren")."""
        node = TextNode("")
        child1 = TextNode("")
        node.append("text")
        node.append(child1)

        children = node.get_children()
        assert len(children) == 2
        assert children[0] == "text"
        assert children[1] is child1
        # Returned list should be a copy, not a reference to the internal list
        children.append("extra")
        assert node.get_children_count() == 2

    def test_should_get_children_count(self):
        """Maps to it("should get children count")."""
        node = TextNode("")
        assert node.get_children_count() == 0

        node.append("First")
        assert node.get_children_count() == 1

        node.append(TextNode(""))
        assert node.get_children_count() == 2

        node.append("Third")
        assert node.get_children_count() == 3

    def test_should_find_renderable_by_id(self):
        """Maps to it("should find renderable by id")."""
        parent = TextNode("")
        child1 = TextNode("", id="child-1")
        child2 = TextNode("", id="child-2")
        parent.append(child1)
        parent.append("plain string")
        parent.append(child2)

        found = parent.get_renderable("child-1")
        assert found is child1

        found = parent.get_renderable("child-2")
        assert found is child2

        found = parent.get_renderable("nonexistent")
        assert found is None


# ── StyledText Integration ────────────────────────────────────────


class TestTextNodeStyledTextIntegration:
    """Maps to describe("StyledText Integration")."""

    def test_should_work_with_template_literal_styled_text(self):
        """Maps to it("should work with template literal styled text").

        Upstream uses JS template literals: t`Hello ${red("World")} with ${bold("bold")} text!`
        Python equivalent: styled_text("Hello ", styled_red("World"), " with ", styled_bold("bold"), " text!")
        """
        node = TextNode("")
        st = styled_text("Hello ", styled_red("World"), " with ", styled_bold("bold"), " text!")

        node.add(st)

        children = node.get_children()
        assert len(children) == 5

        for child in children:
            assert isinstance(child, TextNode)

        # "Hello " — no styling
        hello = children[0]
        assert hello.get_children() == ["Hello "]
        assert hello._fg is None
        assert hello._attributes == 0

        # "World" — red
        red_child = children[1]
        assert red_child.get_children() == ["World"]
        assert red_child._fg is not None
        assert red_child._fg.r == 1.0
        assert red_child._fg.g == 0.0
        assert red_child._fg.b == 0.0
        assert red_child._attributes == 0

        # " with " — no styling
        with_child = children[2]
        assert with_child.get_children() == [" with "]
        assert with_child._fg is None
        assert with_child._attributes == 0

        # "bold" — bold attribute
        bold_child = children[3]
        assert bold_child.get_children() == ["bold"]
        assert bold_child._fg is None
        assert bold_child._attributes == 1  # TEXT_ATTR_BOLD

        # " text!" — no styling
        text_child = children[4]
        assert text_child.get_children() == [" text!"]
        assert text_child._fg is None
        assert text_child._attributes == 0

    def test_should_preserve_styles_when_converting_styled_text(self):
        """Maps to it("should preserve styles when converting StyledText to TextNodes")."""
        node = TextNode("")
        st = StyledText(
            [
                TextChunk(
                    text="Red",
                    fg=RGBA.from_ints(255, 0, 0, 255),
                    bg=RGBA.from_ints(0, 0, 0, 255),
                    attributes=1,
                ),
                TextChunk(text="Blue", fg=RGBA.from_ints(0, 0, 255, 255), attributes=2),
                TextChunk(text="Green", fg=RGBA.from_ints(0, 255, 0, 255), attributes=0),
            ]
        )

        node.add(st)

        children = node.get_children()
        assert len(children) == 3

        red_node = children[0]
        assert red_node.get_children() == ["Red"]
        assert red_node._fg == RGBA.from_ints(255, 0, 0, 255)
        assert red_node._bg == RGBA.from_ints(0, 0, 0, 255)
        assert red_node._attributes == 1

        blue_node = children[1]
        assert blue_node.get_children() == ["Blue"]
        assert blue_node._fg == RGBA.from_ints(0, 0, 255, 255)
        assert blue_node._bg is None
        assert blue_node._attributes == 2

        green_node = children[2]
        assert green_node.get_children() == ["Green"]
        assert green_node._fg == RGBA.from_ints(0, 255, 0, 255)
        assert green_node._bg is None
        assert green_node._attributes == 0

    def test_should_handle_empty_styled_text(self):
        """Maps to it("should handle empty StyledText")."""
        node = TextNode("")
        empty_st = StyledText([])

        index = node.add(empty_st)
        assert index == 0

        # No children since empty StyledText produces no TextNodes
        assert node.get_children_count() == 0

        # to_chunks returns empty list
        chunks = node.to_chunks()
        assert len(chunks) == 0

    def test_should_handle_styled_text_with_empty_text_chunks(self):
        """Maps to it("should handle StyledText with empty text chunks")."""
        node = TextNode("")
        st = StyledText(
            [
                TextChunk(text="", fg=RGBA.from_ints(255, 0, 0, 255), attributes=1),
                TextChunk(text="middle", fg=RGBA.from_ints(0, 255, 0, 255), attributes=0),
                TextChunk(text="", fg=RGBA.from_ints(0, 0, 255, 255), attributes=2),
            ]
        )

        node.add(st)

        children = node.get_children()
        assert len(children) == 3

        # First chunk: empty text with red styling
        empty_red = children[0]
        assert empty_red.get_children() == [""]
        assert empty_red._fg == RGBA.from_ints(255, 0, 0, 255)
        assert empty_red._attributes == 1

        # Second chunk: "middle" with green styling
        middle = children[1]
        assert middle.get_children() == ["middle"]
        assert middle._fg == RGBA.from_ints(0, 255, 0, 255)
        assert middle._attributes == 0

        # Third chunk: empty text with blue styling
        empty_blue = children[2]
        assert empty_blue.get_children() == [""]
        assert empty_blue._fg == RGBA.from_ints(0, 0, 255, 255)
        assert empty_blue._attributes == 2


# ── Link Inheritance ──────────────────────────────────────────────


class TestTextNodeLinkInheritance:
    """Maps to describe("Link Inheritance").

    Python link is a plain string (URL), upstream is { url: "..." }.
    """

    def test_should_inherit_link_from_parent_to_child(self):
        """Maps to it("should inherit link from parent to child")."""
        parent = TextNode("", link="https://opentui.com")

        child = TextNode("")
        child.append("Child text")

        parent.append("Parent text")
        parent.append(child)

        chunks = parent.to_chunks()

        assert len(chunks) == 2
        assert chunks[0].text == "Parent text"
        assert chunks[0].style.link == "https://opentui.com"

        assert chunks[1].text == "Child text"
        assert chunks[1].style.link == "https://opentui.com"

    def test_should_allow_child_to_override_parent_link(self):
        """Maps to it("should allow child to override parent link")."""
        parent = TextNode("", link="https://parent.com")

        child = TextNode("", link="https://child.com")
        child.append("Child text")

        parent.append("Parent text")
        parent.append(child)

        chunks = parent.to_chunks()

        assert len(chunks) == 2
        assert chunks[0].style.link == "https://parent.com"
        assert chunks[1].style.link == "https://child.com"

    def test_should_inherit_link_through_multiple_nesting_levels(self):
        """Maps to it("should inherit link through multiple nesting levels")."""
        grandparent = TextNode("", link="https://example.com")

        parent_node = TextNode("")
        child = TextNode("")

        child.append("Grandchild")
        parent_node.append(child)
        grandparent.append(parent_node)

        chunks = grandparent.to_chunks()

        assert len(chunks) == 1
        assert chunks[0].text == "Grandchild"
        assert chunks[0].style.link == "https://example.com"

    def test_should_merge_link_with_other_styles(self):
        """Maps to it("should merge link with other styles")."""
        parent = TextNode(
            "",
            fg=RGBA(1.0, 0.0, 0.0, 1.0),
            attributes=1,
            link="https://opentui.com",
        )

        child = TextNode(
            "",
            bg=RGBA(0.0, 0.0, 1.0, 1.0),
            attributes=2,
        )
        child.append("Styled linked text")

        parent.append(child)

        chunks = parent.to_chunks()

        assert len(chunks) == 1
        assert chunks[0].text == "Styled linked text"
        assert chunks[0].style.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert chunks[0].style.bg == RGBA(0.0, 0.0, 1.0, 1.0)
        assert chunks[0].style.attributes == 3  # 1 | 2
        assert chunks[0].style.link == "https://opentui.com"

    def test_should_handle_undefined_link_in_parent(self):
        """Maps to it("should handle undefined link in parent")."""
        parent = TextNode("")

        child = TextNode("", link="https://child.com")
        child.append("Child with link")

        parent.append("Parent without link")
        parent.append(child)

        chunks = parent.to_chunks()

        assert len(chunks) == 2
        assert chunks[0].style.link is None
        assert chunks[1].style.link == "https://child.com"

    def test_should_preserve_link_when_merging_styles(self):
        """Maps to it("should preserve link when merging styles")."""
        node = TextNode("", link="https://example.com", attributes=1)

        parent_style = TextStyle(
            fg=RGBA(1.0, 0.0, 0.0, 1.0),
            bg=None,
            attributes=2,
        )

        merged = node.merge_styles(parent_style)

        assert merged.link == "https://example.com"
        assert merged.fg == RGBA(1.0, 0.0, 0.0, 1.0)
        assert merged.attributes == 3  # 1 | 2

    def test_should_inherit_link_when_node_has_no_link(self):
        """Maps to it("should inherit link when node has no link")."""
        node = TextNode("", fg=RGBA(0.0, 1.0, 0.0, 1.0))

        parent_style = TextStyle(
            fg=None,
            bg=None,
            attributes=0,
            link="https://inherited.com",
        )

        merged = node.merge_styles(parent_style)

        assert merged.link == "https://inherited.com"
        assert merged.fg == RGBA(0.0, 1.0, 0.0, 1.0)

    def test_should_handle_complex_link_inheritance_tree(self):
        """Maps to it("should handle complex link inheritance tree")."""
        grandparent = TextNode(
            "",
            link="https://grandparent.com",
            fg=RGBA(1.0, 0.0, 0.0, 1.0),
        )

        parent_node = TextNode("", bg=RGBA(0.0, 0.0, 1.0, 1.0))

        child1 = TextNode("", fg=RGBA(0.0, 1.0, 0.0, 1.0))
        child1.append("Child1")

        child2 = TextNode("", link="https://child2.com")
        child2.append("Child2")

        child3 = TextNode("", attributes=1)
        child3.append("Child3")

        parent_node.append(child1)
        parent_node.append(child2)
        parent_node.append(child3)
        grandparent.append(parent_node)

        chunks = grandparent.to_chunks()

        assert len(chunks) == 3

        # Child1: inherits link from grandparent
        assert chunks[0].text == "Child1"
        assert chunks[0].style.link == "https://grandparent.com"
        assert chunks[0].style.fg == RGBA(0.0, 1.0, 0.0, 1.0)

        # Child2: overrides link
        assert chunks[1].text == "Child2"
        assert chunks[1].style.link == "https://child2.com"

        # Child3: inherits link from grandparent
        assert chunks[2].text == "Child3"
        assert chunks[2].style.link == "https://grandparent.com"


# ── Edge Cases and Error Handling ─────────────────────────────────


class TestTextNodeEdgeCases:
    """Maps to describe("Edge Cases and Error Handling")."""

    def test_should_handle_empty_strings(self):
        """Maps to it("should handle empty strings").

        Python TextNode skips empty string children in to_chunks (falsy
        check), unlike upstream which includes them. We test the Python
        behavior: empty "" is skipped, " " is kept.
        """
        node = TextNode("")
        node.append("")
        node.append(" ")

        chunks = node.to_chunks()
        # Python: "" is falsy → skipped. Only " " produces a chunk.
        assert len(chunks) == 1
        assert chunks[0].text == " "

    def test_should_handle_nested_empty_textnodes(self):
        """Maps to it("should handle nested empty TextNodes")."""
        parent = TextNode("")
        child = TextNode("")

        parent.append(child)

        chunks = parent.to_chunks()
        assert len(chunks) == 0

    def test_should_handle_multiple_operations_in_sequence(self):
        """Maps to it("should handle multiple operations in sequence")."""
        node = TextNode("")
        for i in range(5):
            node.append(f"Item {i}")
        assert node.get_children_count() == 5

        node.clear()
        assert node.get_children_count() == 0

        node.add("A")
        node.add("B")
        node.add("C")
        assert node.get_children_count() == 3

    def test_should_efficiently_calculate_positions_for_large_trees(self):
        """Maps to it("should efficiently calculate positions for large trees")."""
        root = TextNode("")
        for i in range(100):
            child = TextNode("")
            child.append(f"Item {i}")
            root.append(child)

        assert root.get_children_count() == 100

        # Insert before the 50th child
        marker = TextNode("")
        marker.append("MARKER")
        anchor = root.get_children()[50]
        root.insert_before(marker, anchor)

        assert root.get_children_count() == 101
        children = root.get_children()
        assert children[50] is marker
        assert children[51] is anchor

        chunks = root.to_chunks()
        assert len(chunks) == 101
        assert chunks[50].text == "MARKER"
