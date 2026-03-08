"""Dialog components — centered modals with backdrop for pickers and prompts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from opentui.components import Box, Text

from ..fuzzy import FuzzyMatch, fuzzy_filter
from ..themes import get_theme


# ---------------------------------------------------------------------------
# Base dialog shell
# ---------------------------------------------------------------------------


def dialog_box(
    *children: Box | Text,
    title: str = "",
    size: str = "medium",
    **kwargs: Any,
) -> Box:
    """Centered dialog box with optional title.

    *size*: ``"medium"`` (60%w/50%h) or ``"large"`` (80%w/70%h).
    """
    t = get_theme()

    width = 60 if size == "medium" else 80
    height = 20 if size == "medium" else 30

    header_children: list[Text] = []
    if title:
        header_children.append(Text(title, bold=True, fg=t.primary))

    header = Box(
        *header_children,
        flex_direction="row",
        padding_left=1,
        padding_right=1,
        padding_bottom=1,
    ) if header_children else None

    body = Box(
        *children,
        flex_direction="column",
        flex_grow=1,
        padding_left=1,
        padding_right=1,
    )

    parts = [header, body] if header else [body]

    return Box(
        *[p for p in parts if p],
        flex_direction="column",
        width=width,
        height=height,
        background_color=t.background_panel,
        border=True,
        border_style="round",
        border_color=t.border_active,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# SelectDialog — fuzzy-searchable list with optional categories
# ---------------------------------------------------------------------------


def select_item(
    *,
    label: str,
    description: str = "",
    selected: bool = False,
    keybinding: str = "",
) -> Box:
    """Render a single selectable item in a list dialog."""
    t = get_theme()
    fg = t.selected_list_item_text if selected else t.text

    parts: list[Text] = [Text(label, fg=fg, bold=selected)]
    if description:
        parts.append(Text(f"  {description}", fg=t.text_muted))
    if keybinding:
        parts.append(Text(f"  {keybinding}", fg=t.text_muted))

    kwargs: dict[str, Any] = dict(
        flex_direction="row",
        padding_left=1,
        padding_right=1,
    )
    if selected:
        kwargs["background_color"] = t.primary

    return Box(*parts, **kwargs)


def select_dialog(
    *,
    title: str,
    items: list[dict[str, str]],
    query: str = "",
    selected_index: int = 0,
    size: str = "medium",
) -> Box:
    """Render a fuzzy-searchable selection dialog.

    Each item dict should have ``"label"`` and optionally
    ``"description"``, ``"category"``, ``"keybinding"``.
    """
    t = get_theme()

    # Filter items by query — preserve fuzzy-scored order
    labels = [item["label"] for item in items]
    if query:
        filtered = fuzzy_filter(query, labels)
        label_to_item = {item["label"]: item for item in items}
        visible_items = [label_to_item[label] for label, _ in filtered if label in label_to_item]
    else:
        visible_items = items

    # Clamp selected_index to valid range
    if visible_items:
        selected_index = max(0, min(selected_index, len(visible_items) - 1))
    else:
        selected_index = 0

    # Search input
    search_text = query or ""
    search = Box(
        Text(f"> {search_text}", fg=t.text),
        border=True,
        border_style="round",
        border_color=t.border,
        padding_left=1,
    )

    # Item list
    children: list[Box] = []
    current_category = ""
    for i, item in enumerate(visible_items):
        cat = item.get("category", "")
        if cat and cat != current_category:
            current_category = cat
            children.append(
                Box(Text(cat, fg=t.text_muted, bold=True), padding_left=1, padding_top=1)
            )
        children.append(
            select_item(
                label=item["label"],
                description=item.get("description", ""),
                selected=(i == selected_index),
                keybinding=item.get("keybinding", ""),
            )
        )

    item_list = Box(*children, flex_direction="column", flex_grow=1)

    # Footer
    footer = Box(
        Text("↑↓ Navigate  Enter Select  Esc Cancel", fg=t.text_muted),
        padding_left=1,
    )

    return dialog_box(search, item_list, footer, title=title, size=size)


# ---------------------------------------------------------------------------
# Simple dialogs
# ---------------------------------------------------------------------------


def alert_dialog(*, title: str, message: str) -> Box:
    """Simple alert dialog with a message."""
    t = get_theme()
    return dialog_box(
        Text(message, fg=t.text),
        Box(Text("Press Esc to close", fg=t.text_muted), padding_top=1),
        title=title,
        size="medium",
    )


def confirm_dialog(*, title: str, message: str) -> Box:
    """Confirmation dialog with yes/no prompt."""
    t = get_theme()
    return dialog_box(
        Text(message, fg=t.text),
        Box(
            Text("Enter Confirm  Esc Cancel", fg=t.text_muted),
            padding_top=1,
        ),
        title=title,
        size="medium",
    )


def prompt_dialog(*, title: str, value: str = "", placeholder: str = "") -> Box:
    """Text input dialog."""
    t = get_theme()
    display = value or placeholder
    fg = t.text if value else t.text_muted

    return dialog_box(
        Box(
            Text(display, fg=fg),
            border=True,
            border_style="round",
            border_color=t.border,
            padding_left=1,
        ),
        Box(
            Text("Enter Submit  Esc Cancel", fg=t.text_muted),
            padding_top=1,
        ),
        title=title,
        size="medium",
    )


def help_dialog(*, bindings: list[tuple[str, str]]) -> Box:
    """Help dialog showing keybinding reference."""
    t = get_theme()
    children: list[Box] = []
    for key, desc in bindings:
        children.append(
            Box(
                Text(key.ljust(20), fg=t.accent),
                Text(desc, fg=t.text),
                flex_direction="row",
                padding_left=1,
            )
        )

    return dialog_box(
        *children,
        title="Keyboard Shortcuts",
        size="large",
    )
