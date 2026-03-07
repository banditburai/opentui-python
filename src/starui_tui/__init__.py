"""starui_tui — TUI components with the same API as starui (web).

This package provides terminal UI components that share function signatures
with the starui web component library. The same variant names and props
produce appropriate visual output in both web (HTML) and TUI (OpenTUI) modes.
"""

from .alert import Alert, AlertDescription, AlertTitle
from .badge import Badge
from .checkbox import Checkbox, RadioGroup, RadioGroupItem
from .progress import Progress
from .select import Select, SelectItem
from .separator import Separator
from .switch import Switch, Toggle
from .table import Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow
from .tabs import Tabs, TabsContent, TabsTrigger
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
    "Checkbox",
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
    "RadioGroup",
    "RadioGroupItem",
    "Progress",
    "Select",
    "SelectItem",
    "Separator",
    "Switch",
    "Table",
    "TableBody",
    "TableCaption",
    "TableCell",
    "TableHead",
    "TableHeader",
    "TableRow",
    "Tabs",
    "TabsContent",
    "TabsTrigger",
    "Toggle",
]
