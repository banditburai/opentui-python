"""starui_tui — TUI components with the same API as starui (web).

This package provides terminal UI components that share function signatures
with the starui web component library. The same variant names and props
produce appropriate visual output in both web (HTML) and TUI (OpenTUI) modes.
"""

from .theme import TUI_THEME, resolve_props

__all__ = ["TUI_THEME", "resolve_props"]
