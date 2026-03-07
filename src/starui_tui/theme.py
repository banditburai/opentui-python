"""TUI theme dict mapping (component, variant_axis, variant_value) to OpenTUI props."""

from typing import Any

# Maps (component, variant_axis, variant_value) → OpenTUI Renderable props
TUI_THEME: dict[tuple[str, str, str], dict[str, Any]] = {
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
    # Card subcomponents
    ("card_title", "variant", "default"): {"bold": True},
    ("card_description", "variant", "default"): {"fg": "#888888"},
    ("card_header", "variant", "default"): {"flex_direction": "column"},
    ("card_footer", "variant", "default"): {"flex_direction": "row", "justify_content": "flex-end"},
    # Typography
    ("muted", "variant", "default"): {"fg": "#888888"},
    ("inline_code", "variant", "default"): {"fg": "#d4af37", "bg": "#2d2d44"},
    # Table
    ("table", "variant", "default"): {
        "border": True,
        "border_style": "single",
        "flex_direction": "column",
    },
    ("table_caption", "variant", "default"): {"fg": "#888888"},
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
    # Breadcrumb
    ("breadcrumb_separator", "variant", "default"): {"fg": "#666666"},
    ("breadcrumb_item", "variant", "default"): {"fg": "#3498db"},
    # Pagination
    ("pagination", "variant", "default"): {
        "active_fg": "#ffffff",
        "inactive_fg": "#888888",
        "nav_fg": "#cccccc",
    },
    # Command
    ("command", "variant", "default"): {
        "border": True,
        "border_style": "round",
        "padding": 1,
    },
    # Dialog
    ("dialog_content", "variant", "default"): {
        "border": True,
        "border_style": "round",
        "padding": 1,
    },
    ("dialog_title", "variant", "default"): {"bold": True},
    ("dialog_description", "variant", "default"): {"fg": "#888888"},
    ("dialog_header", "variant", "default"): {"flex_direction": "column"},
    ("dialog_footer", "variant", "default"): {"flex_direction": "row", "justify_content": "flex-end"},
    # Toast
    ("toast", "variant", "default"): {
        "fg": "#e0e0e0",
        "border": True,
        "border_style": "round",
        "padding_x": 1,
    },
    ("toast", "variant", "success"): {
        "fg": "#2ecc71",
        "border": True,
        "border_style": "round",
        "padding_x": 1,
    },
    ("toast", "variant", "error"): {
        "fg": "#e74c3c",
        "border": True,
        "border_style": "round",
        "padding_x": 1,
    },
    ("toast", "variant", "warning"): {
        "fg": "#f39c12",
        "border": True,
        "border_style": "round",
        "padding_x": 1,
    },
    ("tabs", "variant", "line"): {
        "active_fg": "#ffffff",
        "underline": True,
        "inactive_fg": "#888888",
    },
}


# Axis application order: later axes override earlier ones on shared keys.
# "size" intentionally overrides "variant" for geometry props (height, width, padding).
AXIS_ORDER: list[str] = ["variant", "size"]


def resolve_props(component: str, **variants: str) -> dict[str, Any]:
    """Merge theme props for a component across all variant axes.

    Axes are applied in AXIS_ORDER (variant first, then size). If two axes
    define the same prop key, the later axis wins. Any axes not in AXIS_ORDER
    are applied last in arbitrary order.

    Args:
        component: Component name (e.g. "button", "card")
        **variants: Variant axis=value pairs (e.g. variant="default", size="sm")

    Returns:
        Merged dict of OpenTUI Renderable props.
    """
    result: dict[str, Any] = {}
    # Apply ordered axes first
    for axis in AXIS_ORDER:
        if axis in variants:
            key = (component, axis, variants[axis])
            if key in TUI_THEME:
                result.update(TUI_THEME[key])
    # Apply any remaining axes not in AXIS_ORDER
    for axis, value in variants.items():
        if axis not in AXIS_ORDER:
            key = (component, axis, value)
            if key in TUI_THEME:
                result.update(TUI_THEME[key])
    return result
