"""Message components — user and assistant message rendering."""

from __future__ import annotations

from starhtml import Code, Div, Pre, Span


def _role_icon(role: str) -> Span:
    """Role indicator."""
    if role == "user":
        return Span("U", cls="w-6 h-6 rounded bg-blue-600 text-white text-xs flex items-center justify-center font-bold")
    return Span("A", cls="w-6 h-6 rounded bg-green-600 text-white text-xs flex items-center justify-center font-bold")


def tool_result_html(*, tool_name: str, content: str) -> Div:
    """Render a tool result block."""
    return Div(
        Div(
            Span(tool_name, cls="text-xs font-mono text-zinc-400"),
            cls="px-3 py-1 border-b border-zinc-700",
        ),
        Pre(
            Code(content[:500], cls="text-xs"),
            cls="px-3 py-2 overflow-x-auto text-zinc-300 max-h-40 overflow-y-auto",
        ) if content else Div(cls="hidden"),
        cls="border border-zinc-700 rounded-md bg-zinc-800/50 my-2",
    )


def message_html(*, role: str, content: str, model: str = "", tool_calls: list | None = None) -> Div:
    """Render a chat message with optional tool calls."""
    children = []

    # Message body
    body_cls = "prose prose-invert prose-sm max-w-none"
    children.append(
        Div(content, cls=body_cls) if content else Div(cls="hidden"),
    )

    # Tool calls
    if tool_calls:
        for tc in tool_calls:
            fn = tc.get("function", {})
            children.append(
                tool_result_html(
                    tool_name=fn.get("name", "tool"),
                    content=fn.get("arguments", ""),
                )
            )

    # Model footer
    if model and role == "assistant":
        children.append(
            Span(f"\u2014 {model}", cls="text-xs text-zinc-500 mt-2 block"),
        )

    role_label = "User" if role == "user" else "Assistant"
    return Div(
        Div(
            _role_icon(role),
            Span(role_label, cls="text-xs font-semibold text-zinc-400"),
            cls="flex items-center gap-2 mb-2",
        ),
        Div(*children, cls="pl-8"),
        cls="px-4 py-3",
    )
