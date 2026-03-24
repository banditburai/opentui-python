"""Terminal palette parsing helpers — OSC 4/10-19 response parsers.

Pure-function utilities for parsing ANSI terminal palette responses.
The async detection logic lives in ``detector.py``.
"""

from __future__ import annotations

from .common import (
    OSC4_RE as OSC4_RESPONSE,
)
from .common import (
    OSC_SPECIAL_RE as OSC_SPECIAL_RESPONSE,
)
from .common import (
    _to_hex,
)


def parse_osc4_responses(data: str) -> dict[int, str]:
    """Parse all OSC 4 colour responses from *data* and return {index: hex}."""
    results: dict[int, str] = {}
    for m in OSC4_RESPONSE.finditer(data):
        idx = int(m.group(1))
        results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))
    return results


def parse_osc_special_responses(data: str) -> dict[int, str]:
    """Parse all OSC special colour responses from *data* and return {code: hex}."""
    results: dict[int, str] = {}
    for m in OSC_SPECIAL_RESPONSE.finditer(data):
        idx = int(m.group(1))
        results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))
    return results


def has_osc4_response(data: str) -> bool:
    """Return ``True`` if *data* contains at least one valid OSC 4 response."""
    return bool(OSC4_RESPONSE.search(data))
