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
from .textarea import Textarea
from .theme import TUI_THEME, resolve_props
from .typography import H1, H2, H3, H4, P, Label, Large, Lead, Muted, Small, InlineCode

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
    "Textarea",
    "Label",
    "H1",
    "H2",
    "H3",
    "H4",
    "P",
    "Lead",
    "Large",
    "Small",
    "Muted",
    "InlineCode",
]
