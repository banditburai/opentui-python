"""Shared line decoration types used by both diff and line-number components."""

from dataclasses import dataclass

from .. import structs as s


@dataclass
class LineSign:
    """Decorative marker for a line number gutter."""

    before: str | None = None
    before_color: s.RGBA | None = None
    after: str | None = None
    after_color: s.RGBA | None = None


@dataclass
class LineColorConfig:
    """Separate gutter and content background colors for a line."""

    gutter: s.RGBA | None = None
    content: s.RGBA | None = None


__all__ = ["LineSign", "LineColorConfig"]
