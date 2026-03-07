"""Accordion component with context injection — TUI equivalent of starui Accordion."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from .signals import Signal


def Accordion(
    *children: Any,
    default_open: set[str] | None = None,
    **kwargs: Any,
) -> Box:
    """Accordion container with collapsible sections.

    Children are AccordionItem callables that receive open_items Signal.
    """
    open_items = Signal("accordion", default_open or set())
    ctx = {"open_items": open_items}

    rendered = []
    for child in children:
        if callable(child) and not isinstance(child, (Box, Text)):
            rendered.append(child(**ctx))
        else:
            rendered.append(child)

    return Box(*rendered, flex_direction="column", **kwargs)


def AccordionItem(
    value: str,
    title: str,
    *children: Any,
    **kwargs: Any,
) -> Any:
    """Accordion item — returns a context-injectable callable."""
    def _(*, open_items: Signal, **_ctx: Any) -> Box:
        is_open = value in open_items()

        trigger = AccordionTrigger(title, item_value=value, open_items=open_items)
        content = AccordionContent(*children, item_value=value, is_open=is_open)

        return Box(trigger, content, flex_direction="column", **kwargs)

    return _


def AccordionTrigger(
    title: str,
    *,
    item_value: str = "",
    open_items: Signal | None = None,
    **kwargs: Any,
) -> Box:
    """Accordion trigger header with expand/collapse indicator."""
    indicator = "▼" if (open_items and item_value in open_items()) else "▶"
    box = Box(
        Text(f"{indicator} {title}", bold=True),
        flex_direction="row",
        **kwargs,
    )

    if open_items is not None:
        def _toggle(_evt: Any) -> None:
            current = open_items()
            if item_value in current:
                open_items.set(current - {item_value})
            else:
                open_items.set(current | {item_value})
        box.on_mouse_down = _toggle

    return box


def AccordionContent(
    *children: Any,
    item_value: str = "",
    is_open: bool = False,
    **kwargs: Any,
) -> Box:
    """Accordion content panel — visible when item is open."""
    return Box(*children, visible=is_open, **kwargs)
