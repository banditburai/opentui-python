"""Dialog component — TUI equivalent of starui Dialog."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from .props import split_props
from .signals import Signal
from .theme import resolve_props


def Dialog(
    *children: Any,
    signal: Signal | None = None,
    **kwargs: Any,
) -> Box:
    """Dialog container with open/close state.

    Uses a Signal(bool) to track open state. DialogTrigger toggles it,
    DialogContent visibility is bound to it. The signal is explicitly
    threaded to subcomponents by the caller.
    """
    return Box(*children, flex_direction="column", **kwargs)


def DialogTrigger(
    label: str,
    *,
    signal: Signal | None = None,
    **kwargs: Any,
) -> Box:
    """Dialog trigger button that toggles the dialog signal."""
    box = Box(
        Text(label),
        **kwargs,
    )

    if signal is not None:
        def _toggle(_evt: Any) -> None:
            signal.toggle()
        box.on_mouse_down = _toggle

    return box


def DialogContent(
    *children: Any,
    is_open: bool = False,
    **kwargs: Any,
) -> Box:
    """Dialog content panel — visible when dialog is open."""
    props = {**resolve_props("dialog_content", variant="default"), **kwargs}
    _, box_props = split_props(props)
    return Box(*children, visible=is_open, **box_props)


def DialogHeader(*children: Any, **kwargs: Any) -> Box:
    """Dialog header section."""
    props = {**resolve_props("dialog_header", variant="default"), **kwargs}
    _, box_props = split_props(props)
    return Box(*children, **box_props)


def DialogTitle(text: str, **kwargs: Any) -> Text:
    """Dialog title — bold text."""
    props = resolve_props("dialog_title", variant="default")
    text_props, _ = split_props(props)
    return Text(text, **text_props, **kwargs)


def DialogDescription(text: str, **kwargs: Any) -> Text:
    """Dialog description text."""
    props = resolve_props("dialog_description", variant="default")
    text_props, _ = split_props(props)
    return Text(text, **text_props, **kwargs)


def DialogFooter(*children: Any, **kwargs: Any) -> Box:
    """Dialog footer section."""
    props = {**resolve_props("dialog_footer", variant="default"), **kwargs}
    _, box_props = split_props(props)
    return Box(*children, **box_props)
