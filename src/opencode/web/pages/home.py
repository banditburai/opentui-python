"""Home page — logo, tips, MCP status."""

from __future__ import annotations

from starhtml import Div, H1, P, Pre, Span

_LOGO = r"""
   ____                   ____          __
  / __ \____  ___  ____  / ____/____   __/ /___
 / / / / __ \/ _ \/ __ \/ /   / __ \ / __  / _ \
/ /_/ / /_/ /  __/ / / / /___/ /_/ // /_/ /  __/
\____/ .___/\___/_/ /_/\____/\____/ \__,_/\___/
    /_/
"""


def home_page() -> Div:
    """Render the home/landing page."""
    return Div(
        Div(
            Pre(_LOGO, cls="text-indigo-400 text-xs leading-tight"),
            H1("OpenCode", cls="text-3xl font-bold text-white mt-4"),
            P("AI-powered coding assistant", cls="text-zinc-400 mt-1"),
            Div(
                Span("Ctrl+K", cls="font-mono text-xs bg-zinc-800 px-2 py-1 rounded text-zinc-300"),
                Span(" Command Palette", cls="text-zinc-500 text-sm ml-2"),
                cls="mt-6",
            ),
            Div(
                Span("Ctrl+N", cls="font-mono text-xs bg-zinc-800 px-2 py-1 rounded text-zinc-300"),
                Span(" New Session", cls="text-zinc-500 text-sm ml-2"),
                cls="mt-2",
            ),
            Div(
                Span("Type a message below to start", cls="text-zinc-500 text-sm"),
                cls="mt-8",
            ),
            cls="text-center py-20",
        ),
        cls="flex-1 flex items-center justify-center",
    )
