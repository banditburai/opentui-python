"""Tabs component with context injection — TUI equivalent of starui Tabs."""

from __future__ import annotations

from typing import Any, Callable, Literal

from opentui.components import Box, Text

from .signals import Signal
from .theme import resolve_props

TabsVariant = Literal["default", "line"]


def Tabs(
    *children: Any,
    value: str = "",
    signal: Signal | None = None,
    variant: TabsVariant = "default",
    **kwargs: Any,
) -> Box:
    """Tabbed container using context injection.

    Children that are callables (TabsTrigger, TabsContent) receive
    the tabs context (tabs_state, variant) as kwargs.
    """
    tabs_state = signal or Signal("tabs", value)
    ctx = {"tabs_state": tabs_state, "variant": variant}

    rendered = []
    for child in children:
        if callable(child) and not isinstance(child, (Box, Text)):
            rendered.append(child(**ctx))
        else:
            rendered.append(child)

    return Box(*rendered, flex_direction="column", **kwargs)


def TabsTrigger(
    *children: Any,
    value: str | None = None,
    **kwargs: Any,
) -> Callable:
    """Tab trigger button — returns a context-injectable callable."""
    def _(*, tabs_state: Signal, variant: str = "default", **_ctx: Any) -> Box:
        theme = resolve_props("tabs", variant=variant)
        is_active = tabs_state() == value

        active_fg = theme.get("active_fg", "#ffffff")
        inactive_fg = theme.get("inactive_fg", "#888888")
        active_bg = theme.get("active_bg", "#3498db")

        text_content = " ".join(str(c) for c in children if isinstance(c, str))
        text_node = Text(
            text_content,
            fg=active_fg if is_active else inactive_fg,
            bold=is_active,
        )

        box = Box(
            text_node,
            background_color=active_bg if is_active else None,
            padding_left=1,
            padding_right=1,
            **kwargs,
        )
        box.on_mouse_down = lambda _: tabs_state.set(value)
        return box

    return _


def TabsContent(
    *children: Any,
    value: str | None = None,
    **kwargs: Any,
) -> Callable:
    """Tab content panel — returns a context-injectable callable."""
    def _(*, tabs_state: Signal, **_ctx: Any) -> Box:
        if tabs_state() != value:
            return Box(visible=False)
        return Box(*children, **kwargs)

    return _
