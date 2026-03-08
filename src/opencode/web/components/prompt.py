"""Prompt component — input area with Datastar bindings."""

from __future__ import annotations

from starhtml import Button, Div, Textarea, post


def prompt_html(*, placeholder: str = "Type a message...") -> Div:
    """Render the prompt input area."""
    return Div(
        Div(
            Textarea(
                placeholder=placeholder,
                data_bind="prompt",
                rows="1",
                cls="w-full bg-transparent text-zinc-200 placeholder-zinc-500 "
                    "resize-none outline-none text-sm py-2 px-3",
            ),
            Button(
                "\u2191",
                data_on_click=post("/api/send"),
                cls="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white "
                    "rounded-md text-sm font-bold ml-2 flex-shrink-0",
            ),
            cls="flex items-end border border-zinc-600 rounded-lg bg-zinc-800 "
                "focus-within:border-blue-500 transition-colors",
        ),
        cls="px-4 py-3 border-t border-zinc-700 bg-zinc-900",
    )
