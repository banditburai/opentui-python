"""Theme JSON loader — resolves defs references and dark/light variants."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .colors import ThemeColors, _CAMEL_TO_SNAKE

log = logging.getLogger(__name__)


def _resolve_color(
    value: Any,
    defs: dict[str, Any],
    theme_section: dict[str, Any],
    mode: str,
    *,
    _seen: frozenset[str] = frozenset(),
) -> str:
    """Resolve a color value to a hex string.

    Handles: hex strings, def references, dark/light variant objects,
    ``"transparent"``/``"none"``, and recursive references.
    """
    if isinstance(value, dict):
        # {dark: ..., light: ...} variant
        return _resolve_color(value.get(mode, value.get("dark", "#000000")), defs, theme_section, mode, _seen=_seen)

    if not isinstance(value, str):
        return "#000000"

    if value in ("transparent", "none"):
        return "transparent"

    if value.startswith("#"):
        return value

    # Named reference — check defs first, then theme section
    if value in _seen:
        return "#000000"  # circular reference guard
    _seen = _seen | {value}

    if value in defs:
        return _resolve_color(defs[value], defs, theme_section, mode, _seen=_seen)
    if value in theme_section:
        return _resolve_color(theme_section[value], defs, theme_section, mode, _seen=_seen)

    log.warning("Unresolved color reference: %s", value)
    return "#000000"


def load_theme_json(data: dict[str, Any], mode: str = "dark") -> ThemeColors:
    """Resolve a theme JSON structure into a ``ThemeColors`` instance.

    Parameters
    ----------
    data:
        Parsed JSON with ``defs`` and ``theme`` sections (upstream format).
    mode:
        ``"dark"`` or ``"light"``.
    """
    defs = data.get("defs", {})
    theme_section = data.get("theme", {})

    resolved: dict[str, str] = {}
    for camel_key, snake_key in _CAMEL_TO_SNAKE.items():
        if camel_key in ("selectedListItemText", "backgroundMenu"):
            continue  # handled separately below
        raw = theme_section.get(camel_key)
        if raw is not None:
            resolved[snake_key] = _resolve_color(raw, defs, theme_section, mode)
        else:
            resolved[snake_key] = "#000000"

    # Optional tokens with fallbacks
    if "selectedListItemText" in theme_section:
        resolved["selected_list_item_text"] = _resolve_color(
            theme_section["selectedListItemText"], defs, theme_section, mode,
        )
    else:
        resolved["selected_list_item_text"] = resolved.get("background", "#000000")

    if "backgroundMenu" in theme_section:
        resolved["background_menu"] = _resolve_color(
            theme_section["backgroundMenu"], defs, theme_section, mode,
        )
    else:
        resolved["background_menu"] = resolved.get("background_element", "#000000")

    thinking_opacity = theme_section.get("thinkingOpacity", 0.6)

    return ThemeColors(**resolved, thinking_opacity=thinking_opacity)


def load_theme_file(path: Path | str, mode: str = "dark") -> ThemeColors:
    """Load a theme from a JSON file path."""
    path = Path(path)
    data = json.loads(path.read_text())
    return load_theme_json(data, mode)
