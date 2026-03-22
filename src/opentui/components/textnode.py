"""TextNode component for lightweight styled text trees."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

from .. import structs as s

_textnode_id_counter = itertools.count(1)


@dataclass
class TextStyle:
    fg: s.RGBA | None = None
    bg: s.RGBA | None = None
    attributes: int = 0
    link: str | None = None


@dataclass
class StyledChunk:
    text: str
    style: TextStyle


@dataclass
class TextChunk:
    text: str
    fg: s.RGBA | None = None
    bg: s.RGBA | None = None
    attributes: int = 0
    link: str | None = None


class StyledText:
    """A collection of styled text chunks.

    When added to a TextNode via ``add()`` or ``insert_before()``,
    each chunk is decomposed into a child TextNode with the chunk's
    style properties.
    """

    def __init__(self, chunks: list[TextChunk]) -> None:
        self.chunks = chunks

    def to_text_nodes(self) -> list[TextNode]:
        nodes: list[TextNode] = []
        for chunk in self.chunks:
            node = TextNode(
                "",
                fg=chunk.fg,
                bg=chunk.bg,
                attributes=chunk.attributes,
                link=chunk.link,
            )
            node.append(chunk.text)
            nodes.append(node)
        return nodes


TEXT_ATTR_BOLD = s.TEXT_ATTRIBUTE_BOLD
TEXT_ATTR_ITALIC = s.TEXT_ATTRIBUTE_ITALIC
TEXT_ATTR_UNDERLINE = s.TEXT_ATTRIBUTE_UNDERLINE
TEXT_ATTR_STRIKETHROUGH = s.TEXT_ATTRIBUTE_STRIKETHROUGH
TEXT_ATTR_DIM = s.TEXT_ATTRIBUTE_DIM
TEXT_ATTR_REVERSE = s.TEXT_ATTRIBUTE_INVERSE
TEXT_ATTR_BLINK = s.TEXT_ATTRIBUTE_BLINK


def _create_text_attributes(
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
    dim: bool = False,
    reverse: bool = False,
    blink: bool = False,
) -> int:
    return (
        (TEXT_ATTR_BOLD if bold else 0)
        | (TEXT_ATTR_ITALIC if italic else 0)
        | (TEXT_ATTR_UNDERLINE if underline else 0)
        | (TEXT_ATTR_STRIKETHROUGH if strikethrough else 0)
        | (TEXT_ATTR_DIM if dim else 0)
        | (TEXT_ATTR_REVERSE if reverse else 0)
        | (TEXT_ATTR_BLINK if blink else 0)
    )


def _apply_style(
    input_val: str | int | bool | TextChunk,
    *,
    fg: s.RGBA | str | None = None,
    bg: s.RGBA | str | None = None,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
    dim: bool = False,
    reverse: bool = False,
    blink: bool = False,
) -> TextChunk:
    new_attrs = _create_text_attributes(
        bold=bold,
        italic=italic,
        underline=underline,
        strikethrough=strikethrough,
        dim=dim,
        reverse=reverse,
        blink=blink,
    )
    parsed_fg = _parse_color(fg) if fg is not None else None
    parsed_bg = _parse_color(bg) if bg is not None else None

    if isinstance(input_val, TextChunk):
        return TextChunk(
            text=input_val.text,
            fg=parsed_fg if parsed_fg is not None else input_val.fg,
            bg=parsed_bg if parsed_bg is not None else input_val.bg,
            attributes=input_val.attributes | new_attrs,
            link=input_val.link,
        )
    return TextChunk(
        text=str(input_val),
        fg=parsed_fg,
        bg=parsed_bg,
        attributes=new_attrs,
    )


def styled_red(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, fg=s.RGBA(1.0, 0.0, 0.0, 1.0))


def styled_green(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, fg=s.RGBA(0.0, 1.0, 0.0, 1.0))


def styled_blue(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, fg=s.RGBA(0.0, 0.0, 1.0, 1.0))


def styled_yellow(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, fg=s.RGBA(1.0, 1.0, 0.0, 1.0))


def styled_magenta(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, fg=s.RGBA(1.0, 0.0, 1.0, 1.0))


def styled_cyan(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, fg=s.RGBA(0.0, 1.0, 1.0, 1.0))


def styled_white(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, fg=s.RGBA(1.0, 1.0, 1.0, 1.0))


def styled_black(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, fg=s.RGBA(0.0, 0.0, 0.0, 1.0))


def styled_bold(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, bold=True)


def styled_italic(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, italic=True)


def styled_underline(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, underline=True)


def styled_strikethrough(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, strikethrough=True)


def styled_dim(input_val: str | int | bool | TextChunk) -> TextChunk:
    return _apply_style(input_val, dim=True)


def styled_fg(color: s.RGBA | str):
    def apply(input_val: str | int | bool | TextChunk) -> TextChunk:
        return _apply_style(input_val, fg=color)

    return apply


def styled_bg(color: s.RGBA | str):
    def apply(input_val: str | int | bool | TextChunk) -> TextChunk:
        return _apply_style(input_val, bg=color)

    return apply


def styled_text(*parts: str | TextChunk) -> StyledText:
    """Build a StyledText from a sequence of strings and TextChunks.

    Template helper for building styled text.
    Plain strings become unstyled chunks; TextChunk values retain their style.

    Example:
        st = styled_text("Hello ", styled_red("World"), " with ", styled_bold("bold"), " text!")
    """
    chunks: list[TextChunk] = []
    for part in parts:
        if isinstance(part, TextChunk):
            chunks.append(part)
        else:
            chunks.append(TextChunk(text=str(part), attributes=0))
    return StyledText(chunks)


class TextNode:
    """Lightweight text node with style inheritance.

    Builds a tree of styled text nodes. Styles are inherited from
    parent nodes and can be overridden at any level.

    Example:
        root = TextNode("Hello ", fg=RGBA(1, 1, 1))
        root.append(TextNode("World", fg=RGBA(1, 0, 0), attributes=TEXT_ATTRIBUTE_BOLD))
        root.append("!")  # Plain string, inherits parent style

        chunks = root.to_chunks()
        # [StyledChunk("Hello ", white), StyledChunk("World", red+bold), StyledChunk("!", white)]
    """

    def __init__(
        self,
        text: str = "",
        *,
        fg: s.RGBA | str | None = None,
        bg: s.RGBA | str | None = None,
        attributes: int = 0,
        link: str | None = None,
        children: list[TextNode | str] | None = None,
        id: str | None = None,
    ):
        self._id: str = id if id is not None else f"textnode-{next(_textnode_id_counter)}"
        self._text = text
        self._fg = _parse_color(fg)
        self._bg = _parse_color(bg)
        self._attributes = attributes
        self._link = link
        self._children: list[TextNode | str] = list(children) if children else []

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value

    def append(self, child: TextNode | str) -> TextNode:
        self._children.append(child)
        return self

    def add(self, child: TextNode | str | StyledText, index: int | None = None) -> int:
        if isinstance(child, StyledText):
            nodes = child.to_text_nodes()
            insert_idx = index if index is not None else len(self._children)
            for i, node in enumerate(nodes):
                self._children.insert(insert_idx + i, node)
            return insert_idx

        if not isinstance(child, TextNode | str):
            raise TypeError(
                f"TextNode only accepts strings, TextNode instances, "
                f"or StyledText instances, got {type(child).__name__}"
            )
        if index is not None:
            self._children.insert(index, child)
            return index
        self._children.append(child)
        return len(self._children) - 1

    def insert_before(self, child: TextNode | str | StyledText, anchor: TextNode | str) -> TextNode:
        try:
            idx = self._children.index(anchor)
        except ValueError:
            raise ValueError("Anchor node not found in children") from None

        if isinstance(child, StyledText):
            nodes = child.to_text_nodes()
            for i, node in enumerate(nodes):
                self._children.insert(idx + i, node)
        else:
            self._children.insert(idx, child)
        return self

    def remove(self, child: TextNode | str) -> TextNode:
        try:
            self._children.remove(child)
        except ValueError:
            raise ValueError("Child not found in children") from None
        return self

    def clear(self) -> TextNode:
        self._children.clear()
        return self

    def extend(self, children: list[TextNode | str]) -> TextNode:
        self._children.extend(children)
        return self

    def get_children(self) -> list[TextNode | str]:
        return list(self._children)

    def get_children_count(self) -> int:
        return len(self._children)

    def get_renderable(self, id: str) -> TextNode | None:
        for child in self._children:
            if isinstance(child, TextNode) and child._id == id:
                return child
        return None

    def get_style(self) -> TextStyle:
        return TextStyle(
            fg=self._fg,
            bg=self._bg,
            attributes=self._attributes,
            link=self._link,
        )

    def merge_styles(self, parent_style: TextStyle) -> TextStyle:
        return TextStyle(
            fg=self._fg if self._fg is not None else parent_style.fg,
            bg=self._bg if self._bg is not None else parent_style.bg,
            attributes=self._attributes | parent_style.attributes,
            link=self._link if self._link is not None else parent_style.link,
        )

    def to_chunks(self, parent_style: TextStyle | None = None) -> list[StyledChunk]:
        if parent_style is None:
            parent_style = TextStyle()

        resolved = self.merge_styles(parent_style)
        chunks: list[StyledChunk] = []

        if self._text:
            chunks.append(StyledChunk(text=self._text, style=resolved))

        for child in self._children:
            if isinstance(child, str):
                if child:
                    chunks.append(StyledChunk(text=child, style=resolved))
            else:
                chunks.extend(child.to_chunks(resolved))

        return chunks

    def to_plain_text(self) -> str:
        parts = [self._text]
        for child in self._children:
            if isinstance(child, str):
                parts.append(child)
            else:
                parts.append(child.to_plain_text())
        return "".join(parts)

    @classmethod
    def from_string(cls, text: str) -> TextNode:
        node = cls("")
        node.append(text)
        return node

    @classmethod
    def from_nodes(cls, nodes: list[TextNode | str]) -> TextNode:
        node = cls("")
        for child in nodes:
            node.append(child)
        return node

    def __repr__(self) -> str:
        if self._children:
            return f"TextNode({self._text!r}, children={len(self._children)})"
        return f"TextNode({self._text!r})"


def is_textnode_renderable(obj: Any) -> bool:
    return isinstance(obj, TextNode)


_parse_color = s.parse_color_opt


__all__ = [
    "TextNode",
    "TextStyle",
    "StyledChunk",
    "TextChunk",
    "StyledText",
    "is_textnode_renderable",
    "styled_text",
    "styled_red",
    "styled_green",
    "styled_blue",
    "styled_yellow",
    "styled_magenta",
    "styled_cyan",
    "styled_white",
    "styled_black",
    "styled_bold",
    "styled_italic",
    "styled_underline",
    "styled_strikethrough",
    "styled_dim",
    "styled_fg",
    "styled_bg",
    "TEXT_ATTR_BOLD",
    "TEXT_ATTR_ITALIC",
    "TEXT_ATTR_UNDERLINE",
    "TEXT_ATTR_STRIKETHROUGH",
    "TEXT_ATTR_DIM",
    "TEXT_ATTR_REVERSE",
    "TEXT_ATTR_BLINK",
]
