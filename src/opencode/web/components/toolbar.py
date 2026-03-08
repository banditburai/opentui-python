"""Toolbar component — model name, branch, status display."""

from __future__ import annotations

from starhtml import Div, Span


def toolbar_html(*, title: str = "OpenCode") -> Div:
    """Render the top toolbar."""
    return Div(
        Span(title, cls="font-bold text-lg"),
        Span(
            data_text="$model",
            cls="text-sm text-zinc-400 ml-4",
        ),
        Span(
            data_text="$status",
            cls="text-sm text-zinc-500 ml-auto",
        ),
        cls="flex items-center px-4 py-2 border-b border-zinc-700 bg-zinc-900",
    )
