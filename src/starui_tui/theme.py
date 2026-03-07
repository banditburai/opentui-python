"""TUI theme dict mapping (component, variant_axis, variant_value) to OpenTUI props."""

from __future__ import annotations

# Maps (component, variant_axis, variant_value) → OpenTUI Renderable props
TUI_THEME: dict[tuple[str, str, str], dict] = {
    # Button variants
    ("button", "variant", "default"): {
        "border": True,
        "border_style": "round",
        "bg": "#1a1a2e",
        "fg": "#e0e0e0",
    },
    ("button", "variant", "destructive"): {
        "border": True,
        "border_style": "bold",
        "bg": "#e74c3c",
        "fg": "#ffffff",
    },
    ("button", "variant", "outline"): {
        "border": True,
        "border_style": "single",
        "bg": None,
        "fg": "#cccccc",
    },
    ("button", "variant", "secondary"): {
        "border": True,
        "border_style": "single",
        "bg": "#2d2d44",
        "fg": "#e0e0e0",
    },
    ("button", "variant", "ghost"): {
        "border": False,
        "bg": None,
        "fg": "#cccccc",
    },
    ("button", "variant", "link"): {
        "border": False,
        "bg": None,
        "fg": "#3498db",
        "underline": True,
    },
    # Button sizes
    ("button", "size", "default"): {"height": 1, "padding_x": 2},
    ("button", "size", "sm"): {"height": 1, "padding_x": 1},
    ("button", "size", "lg"): {"height": 1, "padding_x": 3},
    ("button", "size", "icon"): {"width": 3, "height": 1, "padding_x": 0},
    # Card
    ("card", "variant", "default"): {
        "border": True,
        "border_style": "round",
        "bg": "#1e1e2e",
        "padding": 1,
    },
    # Badge
    ("badge", "variant", "default"): {"bg": "#3498db", "fg": "#ffffff"},
    ("badge", "variant", "secondary"): {"bg": "#2d2d44", "fg": "#e0e0e0"},
    ("badge", "variant", "destructive"): {"bg": "#e74c3c", "fg": "#ffffff"},
    ("badge", "variant", "outline"): {
        "border": True,
        "border_style": "single",
        "fg": "#cccccc",
    },
    # Alert
    ("alert", "variant", "default"): {
        "border": True,
        "border_style": "round",
        "fg": "#e0e0e0",
        "padding": 1,
    },
    ("alert", "variant", "destructive"): {
        "border": True,
        "border_style": "bold",
        "fg": "#e74c3c",
        "padding": 1,
    },
    # Input
    ("input", "variant", "default"): {
        "border": True,
        "border_style": "single",
        "fg": "#e0e0e0",
        "height": 1,
    },
    # Separator
    ("separator", "variant", "default"): {"border_char": "\u2500"},
    # Progress
    ("progress", "variant", "default"): {
        "fill_char": "\u2588",
        "empty_char": "\u2591",
        "fg": "#3498db",
    },
    # Tabs
    ("tabs", "variant", "default"): {
        "active_fg": "#ffffff",
        "active_bg": "#3498db",
        "inactive_fg": "#888888",
    },
    ("tabs", "variant", "line"): {
        "active_fg": "#ffffff",
        "underline": True,
        "inactive_fg": "#888888",
    },
}


def resolve_props(component: str, **variants: str) -> dict:
    """Merge theme props for a component across all variant axes.

    Args:
        component: Component name (e.g. "button", "card")
        **variants: Variant axis=value pairs (e.g. variant="default", size="sm")

    Returns:
        Merged dict of OpenTUI Renderable props.
    """
    result: dict = {}
    for axis, value in variants.items():
        key = (component, axis, value)
        if key in TUI_THEME:
            result.update(TUI_THEME[key])
    return result
