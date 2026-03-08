"""Diff viewer — unified diff display with color-coded additions/deletions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opentui.components import Box, Text

from ..themes import get_theme

@dataclass
class DiffLine:
    """A single line in a diff."""

    kind: str  # "+", "-", or " "
    content: str


def diff_viewer(
    *,
    lines: list[DiffLine],
    filename: str = "",
    **kwargs: Any,
) -> Box:
    """Render a diff as colored lines in a Box."""
    t = get_theme()
    colors = {"+": t.diff_added, "-": t.diff_removed, " ": t.diff_context}
    parts: list[Box | Text] = []

    if filename:
        parts.append(Text(filename, bold=True, fg=t.text))

    for dl in lines:
        color = colors.get(dl.kind, t.diff_context)
        parts.append(Text(f"{dl.kind}{dl.content}", fg=color))

    return Box(
        *parts,
        flex_direction="column",
        background_color=t.background_element,
        padding_left=1,
        padding_right=1,
        **kwargs,
    )


def parse_unified_diff(text: str) -> list[DiffLine]:
    """Parse a unified diff string into DiffLine objects.

    Skips header lines (--- / +++ / @@).
    """
    result: list[DiffLine] = []
    for line in text.splitlines():
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            result.append(DiffLine(kind="+", content=line[1:]))
        elif line.startswith("-"):
            result.append(DiffLine(kind="-", content=line[1:]))
        else:
            result.append(DiffLine(kind=" ", content=line[1:] if line.startswith(" ") else line))
    return result
