"""Dialog component — TUI equivalent of starui Dialog."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from .signals import Signal


def Dialog(
    *children: Any,
    signal: Signal | None = None,
    **kwargs: Any,
) -> Box:
    """Dialog container with open/close state.

    Uses a Signal(bool) to track open state. DialogTrigger toggles it,
    DialogContent visibility is bound to it.
    """
    is_open = signal() if signal else False

    rendered = []
    for child in children:
        if callable(child) and not isinstance(child, (Box, Text)):
            rendered.append(child(is_open=is_open))
        else:
            rendered.append(child)

    return Box(*rendered, flex_direction="column", **kwargs)


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
            signal.set(not signal())
        box.on_mouse_down = _toggle

    return box


def DialogContent(
    *children: Any,
    is_open: bool = False,
    **kwargs: Any,
) -> Box:
    """Dialog content panel — visible when dialog is open."""
    return Box(
        *children,
        visible=is_open,
        border=True,
        border_style="round",
        padding=1,
        **kwargs,
    )


def DialogHeader(*children: Any, **kwargs: Any) -> Box:
    """Dialog header section."""
    return Box(*children, flex_direction="column", **kwargs)


def DialogTitle(text: str, **kwargs: Any) -> Text:
    """Dialog title — bold text."""
    return Text(text, bold=True, **kwargs)


def DialogDescription(text: str, **kwargs: Any) -> Text:
    """Dialog description text."""
    return Text(text, fg="#888888", **kwargs)


def DialogFooter(*children: Any, **kwargs: Any) -> Box:
    """Dialog footer section."""
    return Box(*children, flex_direction="row", justify_content="flex-end", **kwargs)
