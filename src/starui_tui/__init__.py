"""starui_tui — TUI components with the same API as starui (web).

This package provides terminal UI components that share function signatures
with the starui web component library. The same variant names and props
produce appropriate visual output in both web (HTML) and TUI (OpenTUI) modes.
"""

from .alert import Alert, AlertDescription, AlertTitle
from .badge import Badge
from .button import Button
from .card import Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle
from .input import Input
from .theme import TUI_THEME, resolve_props

__all__ = [
    "TUI_THEME",
    "resolve_props",
    "Alert",
    "AlertDescription",
    "AlertTitle",
    "Badge",
    "Button",
    "Card",
    "CardContent",
    "CardDescription",
    "CardFooter",
    "CardHeader",
    "CardTitle",
    "Input",
]
