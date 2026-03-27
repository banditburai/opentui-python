"""OSC response regexes and hex conversion shared by palette detector and terminal palette."""

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


def parse_osc4_responses(data: str) -> dict[int, str]:
    """Parse all OSC 4 colour responses from *data* and return {index: hex}."""
    results: dict[int, str] = {}
    for m in OSC4_RE.finditer(data):
        idx = int(m.group(1))
        results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))
    return results


def parse_osc_special_responses(data: str) -> dict[int, str]:
    """Parse all OSC special colour responses from *data* and return {code: hex}."""
    results: dict[int, str] = {}
    for m in OSC_SPECIAL_RE.finditer(data):
        idx = int(m.group(1))
        results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))
    return results


def has_osc4_response(data: str) -> bool:
    """Return ``True`` if *data* contains at least one valid OSC 4 response."""
    return bool(OSC4_RE.search(data))


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
