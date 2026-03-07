"""Label + Typography components — TUI text styling wrappers."""

from __future__ import annotations

from typing import Any

from opentui.components import Text


def Label(content: str = "", **kwargs: Any) -> Text:
    """Styled label (bold text)."""
    return Text(content, bold=True, **kwargs)


def H1(content: str = "", **kwargs: Any) -> Text:
    """Heading level 1 (bold)."""
    return Text(content, bold=True, **kwargs)


def H2(content: str = "", **kwargs: Any) -> Text:
    """Heading level 2 (bold)."""
    return Text(content, bold=True, **kwargs)


def H3(content: str = "", **kwargs: Any) -> Text:
    """Heading level 3 (bold)."""
    return Text(content, bold=True, **kwargs)


def H4(content: str = "", **kwargs: Any) -> Text:
    """Heading level 4 (bold)."""
    return Text(content, bold=True, **kwargs)


def P(content: str = "", **kwargs: Any) -> Text:
    """Paragraph text."""
    return Text(content, **kwargs)


def Lead(content: str = "", **kwargs: Any) -> Text:
    """Lead paragraph (slightly larger/emphasized)."""
    return Text(content, **kwargs)


def Large(content: str = "", **kwargs: Any) -> Text:
    """Large text."""
    return Text(content, **kwargs)


def Small(content: str = "", **kwargs: Any) -> Text:
    """Small text."""
    return Text(content, **kwargs)


def Muted(content: str = "", **kwargs: Any) -> Text:
    """Muted/secondary text."""
    return Text(content, fg="#888888", **kwargs)


def InlineCode(content: str = "", **kwargs: Any) -> Text:
    """Inline code snippet."""
    return Text(content, **kwargs)
