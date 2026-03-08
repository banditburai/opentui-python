"""Theme system — reactive theme management with 33 built-in themes.

Usage::

    from opencode.tui.themes import get_theme, set_theme, list_themes

    theme = get_theme()         # current ThemeColors
    set_theme("dracula")        # switch (triggers re-render)
    names = list_themes()       # all available theme names
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from opentui.signals import Signal

from .colors import ThemeColors
from .loader import load_theme_file, load_theme_json

__all__ = [
    "ThemeColors",
    "get_theme",
    "set_theme",
    "get_mode",
    "set_mode",
    "list_themes",
    "load_custom_theme",
    "reset",
    "theme_signal",
]

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent / "data"

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_mode: str = "dark"
_active_name: str = "opencode"
_custom_themes: dict[str, dict[str, Any]] = {}

# Reactive signal — components subscribe to this for re-renders
theme_signal: Signal = Signal("theme", None)  # type: ignore[arg-type]


def _builtin_names() -> list[str]:
    """List built-in theme names from the data directory."""
    return sorted(p.stem for p in _DATA_DIR.glob("*.json"))


def _resolve_active() -> ThemeColors:
    """Resolve the active theme name + mode to a ThemeColors instance."""
    # Check custom themes first
    if _active_name in _custom_themes:
        return load_theme_json(_custom_themes[_active_name], _mode)

    # Built-in theme
    path = _DATA_DIR / f"{_active_name}.json"
    if path.is_file():
        return load_theme_file(path, _mode)

    # Fallback to opencode
    log.warning("Theme %r not found, falling back to opencode", _active_name)
    fallback = _DATA_DIR / "opencode.json"
    if fallback.is_file():
        return load_theme_file(fallback, _mode)

    # Ultimate fallback — hardcoded dark theme
    return _fallback_theme()


def _fallback_theme() -> ThemeColors:
    """Minimal hardcoded dark theme for when no JSON files are available."""
    return ThemeColors(
        primary="#fab283", secondary="#a0a0a0", accent="#fab283",
        error="#e57373", warning="#ffb74d", success="#81c784", info="#4fc3f7",
        text="#e0e0e0", text_muted="#888888", selected_list_item_text="#0a0a0a",
        background="#0a0a0a", background_panel="#111111",
        background_element="#1a1a1a", background_menu="#1a1a1a",
        border="#333333", border_active="#fab283", border_subtle="#222222",
        diff_added="#81c784", diff_removed="#e57373", diff_context="#888888",
        diff_hunk_header="#4fc3f7", diff_highlight_added="#a5d6a7",
        diff_highlight_removed="#ef9a9a", diff_added_bg="#1b3d1b",
        diff_removed_bg="#3d1b1b", diff_context_bg="#111111",
        diff_line_number="#555555", diff_added_line_number_bg="#1b3d1b",
        diff_removed_line_number_bg="#3d1b1b",
        markdown_text="#e0e0e0", markdown_heading="#fab283",
        markdown_link="#4fc3f7", markdown_link_text="#888888",
        markdown_code="#a0a0a0", markdown_block_quote="#888888",
        markdown_emph="#e0e0e0", markdown_strong="#e0e0e0",
        markdown_horizontal_rule="#333333", markdown_list_item="#e0e0e0",
        markdown_list_enumeration="#e0e0e0", markdown_image="#4fc3f7",
        markdown_image_text="#888888", markdown_code_block="#e0e0e0",
        syntax_comment="#666666", syntax_keyword="#c678dd",
        syntax_function="#61afef", syntax_variable="#e0e0e0",
        syntax_string="#98c379", syntax_number="#d19a66",
        syntax_type="#e5c07b", syntax_operator="#c678dd",
        syntax_punctuation="#e0e0e0",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_theme() -> ThemeColors:
    """Return the currently active resolved ThemeColors."""
    current = theme_signal()
    if current is None:
        colors = _resolve_active()
        theme_signal.set(colors)
        return colors
    return current


def set_theme(name: str) -> None:
    """Switch to a theme by name. Triggers re-render via signal."""
    global _active_name
    _active_name = name
    theme_signal.set(_resolve_active())


def get_mode() -> str:
    """Return the current color mode (``"dark"`` or ``"light"``)."""
    return _mode


def set_mode(mode: str) -> None:
    """Switch between dark and light mode. Triggers re-render."""
    global _mode
    if mode not in ("dark", "light"):
        raise ValueError(f"Mode must be 'dark' or 'light', got {mode!r}")
    _mode = mode
    theme_signal.set(_resolve_active())


def list_themes() -> list[str]:
    """Return sorted list of all available theme names (built-in + custom)."""
    names = set(_builtin_names())
    names.update(_custom_themes)
    return sorted(names)


def load_custom_theme(path: Path | str) -> str:
    """Load a custom theme JSON file and register it.

    Returns the theme name (derived from filename).
    """
    path = Path(path)
    data = json.loads(path.read_text())
    name = path.stem
    _custom_themes[name] = data
    return name


def get_active_name() -> str:
    """Return the name of the currently active theme."""
    return _active_name


def reset() -> None:
    """Reset theme system to defaults (useful for testing)."""
    global _active_name, _mode
    _active_name = "opencode"
    _mode = "dark"
    _custom_themes.clear()
    theme_signal.set(None)


def init_theme(name: str = "opencode", mode: str = "dark") -> ThemeColors:
    """Initialize the theme system with a name and mode.

    Called during app startup from config.
    """
    global _active_name, _mode
    _active_name = name
    _mode = mode
    colors = _resolve_active()
    theme_signal.set(colors)
    return colors
