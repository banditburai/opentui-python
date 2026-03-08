"""Base layout — HTML shell with Datastar SDK and theme CSS vars."""

from __future__ import annotations

from typing import Any

from starhtml import Body, Div, Head, Html, Link, Meta, Script, Style, Title


_THEME_CSS = """
:root {
    --oc-bg: #0a0a0f;
    --oc-bg-panel: #111118;
    --oc-bg-element: #1a1a24;
    --oc-text: #e0e0e8;
    --oc-text-muted: #6b6b7b;
    --oc-primary: #6366f1;
    --oc-accent: #818cf8;
    --oc-border: #2a2a3a;
    --oc-border-active: #4a4a6a;
    --oc-success: #22c55e;
    --oc-warning: #f59e0b;
    --oc-error: #ef4444;
}
body {
    background: var(--oc-bg);
    color: var(--oc-text);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
"""


def base_layout(*children: Any, title: str = "OpenCode") -> Html:
    """Wrap content in the base HTML layout with Datastar and theme."""
    return Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title(title),
            Script(src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"),
            Style(_THEME_CSS),
        ),
        Body(
            Div(
                *children,
                cls="flex flex-col h-screen",
            ),
            cls="antialiased",
        ),
        lang="en",
    )
