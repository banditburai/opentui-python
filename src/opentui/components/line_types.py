"""Shared line decoration types used by both diff and line-number components."""

from __future__ import annotations

from dataclasses import dataclass

from .. import structs as s


@dataclass
class LineSign:
    """Decorative marker for a line number gutter."""

    before: str | None = None
    before_color: s.RGBA | str | None = None
    after: str | None = None
    after_color: s.RGBA | str | None = None


@dataclass
class LineColorConfig:
    """Separate gutter and content background colors for a line."""

    gutter: s.RGBA | str | None = None
    content: s.RGBA | str | None = None


__all__ = ["LineSign", "LineColorConfig"]
