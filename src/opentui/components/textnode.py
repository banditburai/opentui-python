"""TextNode component for lightweight styled text trees."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .. import structs as s

if TYPE_CHECKING:
    from ..renderer import Buffer


@dataclass
class TextStyle:
    """Style properties for a TextNode."""

    fg: s.RGBA | None = None
    bg: s.RGBA | None = None
    attributes: int = 0
    link: str | None = None


@dataclass
class StyledChunk:
    """A chunk of text with its resolved style."""

    text: str
    style: TextStyle


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
    ):
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
        """Append a child node or string."""
        self._children.append(child)
        return self

    def extend(self, children: list[TextNode | str]) -> TextNode:
        """Append multiple children."""
        self._children.extend(children)
        return self

    def get_style(self) -> TextStyle:
        """Get this node's own style."""
        return TextStyle(
            fg=self._fg,
            bg=self._bg,
            attributes=self._attributes,
            link=self._link,
        )

    def merge_styles(self, parent_style: TextStyle) -> TextStyle:
        """Merge this node's style with a parent style (this node overrides)."""
        return TextStyle(
            fg=self._fg if self._fg is not None else parent_style.fg,
            bg=self._bg if self._bg is not None else parent_style.bg,
            attributes=self._attributes | parent_style.attributes,
            link=self._link if self._link is not None else parent_style.link,
        )

    def to_chunks(self, parent_style: TextStyle | None = None) -> list[StyledChunk]:
        """Flatten the tree to a list of styled text chunks.

        Args:
            parent_style: Style inherited from parent node

        Returns:
            List of StyledChunk with resolved styles
        """
        if parent_style is None:
            parent_style = TextStyle()

        resolved = self.merge_styles(parent_style)
        chunks: list[StyledChunk] = []

        # Add this node's text if any
        if self._text:
            chunks.append(StyledChunk(text=self._text, style=resolved))

        # Process children
        for child in self._children:
            if isinstance(child, str):
                if child:
                    chunks.append(StyledChunk(text=child, style=resolved))
            else:
                chunks.extend(child.to_chunks(resolved))

        return chunks

    def to_plain_text(self) -> str:
        """Flatten the tree to plain text (no style information)."""
        parts = [self._text]
        for child in self._children:
            if isinstance(child, str):
                parts.append(child)
            else:
                parts.append(child.to_plain_text())
        return "".join(parts)

    def __repr__(self) -> str:
        if self._children:
            return f"TextNode({self._text!r}, children={len(self._children)})"
        return f"TextNode({self._text!r})"


def _parse_color(color: s.RGBA | str | None) -> s.RGBA | None:
    """Parse a color string or RGBA to RGBA."""
    if color is None:
        return None
    if isinstance(color, s.RGBA):
        return color
    if isinstance(color, str):
        return s.RGBA.from_hex(color)
    return None


__all__ = ["TextNode", "TextStyle", "StyledChunk"]
