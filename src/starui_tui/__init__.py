"""starui_tui — TUI components with the same API as starui (web).

This package provides terminal UI components that share function signatures
with the starui web component library. The same variant names and props
produce appropriate visual output in both web (HTML) and TUI (OpenTUI) modes.
"""

from .accordion import Accordion, AccordionContent, AccordionItem, AccordionTrigger
from .breadcrumb import Breadcrumb, BreadcrumbItem
from .dialog import Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger
from .alert import Alert, AlertDescription, AlertTitle
from .badge import Badge
from .checkbox import Checkbox, RadioGroup, RadioGroupItem
from .command import Command, CommandGroup, CommandInput, CommandItem, CommandList
from .pagination import Pagination
from .progress import Progress
from .select import Select, SelectItem
from .separator import Separator
from .switch import Switch, Toggle
from .table import Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow
from .tabs import Tabs, TabsContent, TabsTrigger
from .toast import Toast, Toaster, use_toast
from .button import Button
from .card import Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle
from .input import Input
from .textarea import Textarea
from .theme import TUI_THEME, resolve_props
from .typography import H1, H2, H3, H4, P, Label, Large, Lead, Muted, Small, InlineCode

__all__ = [
    "TUI_THEME",
    "resolve_props",
    "Accordion",
    "AccordionContent",
    "AccordionItem",
    "AccordionTrigger",
    "Alert",
    "AlertDescription",
    "AlertTitle",
    "Badge",
    "Breadcrumb",
    "BreadcrumbItem",
    "Button",
    "Checkbox",
    "Command",
    "CommandGroup",
    "CommandInput",
    "CommandItem",
    "CommandList",
    "Dialog",
    "DialogContent",
    "DialogDescription",
    "DialogFooter",
    "DialogHeader",
    "DialogTitle",
    "DialogTrigger",
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
    "Pagination",
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
    "Toast",
    "Toaster",
    "Toggle",
    "use_toast",
]
