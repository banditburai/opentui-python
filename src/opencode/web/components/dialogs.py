"""Dialog components — command palette, theme picker."""

from __future__ import annotations

from starhtml import Button, Div, H3, Input, Span


def command_palette_html(*, commands: list[dict] | None = None) -> Div:
    """Render the command palette overlay."""
    items = []
    for cmd in (commands or []):
        items.append(
            Div(
                Span(cmd.get("name", ""), cls="text-sm text-zinc-200"),
                Span(
                    cmd.get("keybinding", ""),
                    cls="text-xs text-zinc-500 ml-auto font-mono",
                ),
                cls="flex items-center px-3 py-2 hover:bg-zinc-700 cursor-pointer rounded",
            )
        )

    return Div(
        Div(
            Div(
                H3("Command Palette", cls="text-sm font-semibold text-zinc-300 mb-2"),
                Input(
                    type="text",
                    placeholder="Type a command...",
                    data_bind="command_query",
                    cls="w-full bg-zinc-800 text-zinc-200 px-3 py-2 rounded "
                        "border border-zinc-600 text-sm outline-none "
                        "focus:border-blue-500",
                ),
                Div(
                    *items,
                    cls="mt-2 max-h-60 overflow-y-auto",
                ),
                cls="p-4",
            ),
            cls="bg-zinc-800 border border-zinc-600 rounded-xl shadow-2xl "
                "w-full max-w-md mx-auto mt-20",
        ),
        data_show="$command_palette_open",
        cls="fixed inset-0 bg-black/50 z-50 flex justify-center",
    )


def theme_picker_html(*, themes: list[str] | None = None, active: str = "") -> Div:
    """Render a theme picker dialog."""
    items = []
    for name in (themes or []):
        is_active = name == active
        check = "\u2713 " if is_active else "  "
        items.append(
            Div(
                Span(check, cls="text-green-400 w-4"),
                Span(name, cls="text-sm text-zinc-200"),
                cls="flex items-center px-3 py-1.5 hover:bg-zinc-700 cursor-pointer rounded",
            )
        )

    return Div(
        Div(
            H3("Theme", cls="text-sm font-semibold text-zinc-300 p-4 border-b border-zinc-700"),
            Div(
                *items,
                cls="p-2 max-h-60 overflow-y-auto",
            ),
            cls="bg-zinc-800 border border-zinc-600 rounded-xl shadow-2xl "
                "w-full max-w-sm mx-auto mt-20",
        ),
        cls="fixed inset-0 bg-black/50 z-50 flex justify-center",
    )
