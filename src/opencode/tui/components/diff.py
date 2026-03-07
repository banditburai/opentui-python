"""Diff viewer — unified diff display with color-coded additions/deletions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opentui.components import Box, Text

from ..theme import APP_THEME

_COLORS = {
    "+": "#81c784",  # green for additions
    "-": "#e57373",  # red for deletions
    " ": "#c0c0c0",  # gray for context
}


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
    parts: list[Box | Text] = []

    if filename:
        t = APP_THEME.get("content", {})
        parts.append(Text(filename, bold=True, fg=t.get("fg", "#e0e0e0")))

    for dl in lines:
        prefix = dl.kind if dl.kind != " " else " "
        color = _COLORS.get(dl.kind, "#c0c0c0")
        parts.append(Text(f"{prefix}{dl.content}", fg=color))

    return Box(
        *parts,
        flex_direction="column",
        background_color="#2a2a3e",
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
        elif line.startswith(" "):
            result.append(DiffLine(kind=" ", content=line[1:]))
    return result
