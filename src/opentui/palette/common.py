"""OSC response regexes and hex conversion shared by palette detector and terminal palette."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

OSC4_RE = re.compile(
    r"\x1b\]4;(\d+);"
    r"(?:(?:rgb:)([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)"
    r"|#([0-9a-fA-F]{6}))"
    r"(?:\x07|\x1b\\)"
)

OSC_SPECIAL_RE = re.compile(
    r"\x1b\](\d+);"
    r"(?:(?:rgb:)([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)"
    r"|#([0-9a-fA-F]{6}))"
    r"(?:\x07|\x1b\\)"
)


def _scale_component(comp: str) -> str:
    """Scale a hex colour component of arbitrary width to 2 hex digits (0-255)."""
    val = int(comp, 16)
    max_in = (1 << (4 * len(comp))) - 1
    return format(round((val / max_in) * 255), "02x")


def _to_hex(
    r: str | None = None,
    g: str | None = None,
    b: str | None = None,
    hex6: str | None = None,
) -> str:
    """Convert parsed OSC colour components to a ``#rrggbb`` string."""
    if hex6:
        return f"#{hex6.lower()}"
    if r and g and b:
        return f"#{_scale_component(r)}{_scale_component(g)}{_scale_component(b)}"
    return "#000000"


Hex = str | None  # "#rrggbb" or None


@dataclass
class TerminalColors:
    """Result of a palette detection query."""

    palette: list[str | None] = field(default_factory=list)
    default_foreground: str | None = None
    default_background: str | None = None
    cursor_color: str | None = None
    mouse_foreground: str | None = None
    mouse_background: str | None = None
    tek_foreground: str | None = None
    tek_background: str | None = None
    highlight_background: str | None = None
    highlight_foreground: str | None = None
