"""Sidebar component — session list with selection."""

from __future__ import annotations

from starhtml import Button, Div, H3, Span, get


def session_item_html(*, session_id: str, title: str, active: bool = False) -> Div:
    """Render a single session list item."""
    active_cls = "bg-zinc-700 border-l-2 border-blue-400" if active else "hover:bg-zinc-800"
    return Div(
        Span(title or "Untitled", cls="truncate"),
        data_on_click=get(f"/api/session/{session_id}/switch"),
        cls=f"px-3 py-2 cursor-pointer text-sm text-zinc-300 {active_cls}",
    )


def sidebar_html(*, sessions: list[dict] | None = None, active_id: str = "") -> Div:
    """Render the sidebar with session list."""
    session_items = []
    for s in (sessions or []):
        session_items.append(
            session_item_html(
                session_id=s.get("id", ""),
                title=s.get("title", "Untitled"),
                active=s.get("id") == active_id,
            )
        )

    return Div(
        Div(
            H3("Sessions", cls="text-xs font-semibold text-zinc-500 uppercase tracking-wider"),
            Button(
                "+",
                data_on_click=get("/api/session/new"),
                cls="text-zinc-400 hover:text-white text-lg leading-none",
            ),
            cls="flex items-center justify-between px-3 py-2 border-b border-zinc-700",
        ),
        Div(
            *session_items,
            id="session-list",
            cls="flex flex-col overflow-y-auto",
        ),
        data_show="$sidebar_open",
        cls="w-60 flex-shrink-0 border-r border-zinc-700 bg-zinc-900 flex flex-col h-full",
    )
