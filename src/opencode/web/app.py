"""Web app — StarHTML application that mounts the API and serves pages."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.bus import EventBus
    from opencode.tui.state import AppState


def create_web_app(bus: EventBus, state: AppState) -> Any:
    """Create a StarHTML web app with API routes mounted.

    Serves the web UI at / and API at /api/.
    """
    from starhtml import Div, star_app, sse, signals

    from .components.dialogs import command_palette_html
    from .components.message import message_html
    from .components.prompt import prompt_html
    from .components.sidebar import sidebar_html
    from .components.toolbar import toolbar_html
    from .pages.home import home_page
    from .pages.layout import base_layout
    from .pages.session import session_page
    from .signals import app_signals

    app, rt = star_app(
        title="OpenCode",
    )

    # Mount API routes
    from opencode.server.app import create_app as create_api_app

    api_app = create_api_app(bus, state)
    app.mount("/api", api_app)

    sigs = app_signals()

    # --- Pages ---

    @rt("/")
    def index():
        """Main page — home or session view based on state."""
        sessions = state.store.list_sessions()
        session_id = state.current_session_id()

        sessions_data = [
            {"id": s.id, "title": s.title}
            for s in sessions
        ]

        if session_id:
            messages = state.store.get_messages(session_id)
            msg_dicts = [
                {
                    "role": m.role,
                    "content": m.content,
                    "model": m.model or "",
                    "tool_calls": json.loads(m.tool_calls) if m.tool_calls else None,
                }
                for m in messages
            ]
            content = session_page(messages=msg_dicts)
        else:
            content = home_page()

        commands = []
        from opencode.tui.commands import default_commands
        for cmd in default_commands().list():
            commands.append({"name": cmd.name, "keybinding": cmd.keybinding})

        return base_layout(
            *sigs.values(),
            toolbar_html(),
            Div(
                sidebar_html(sessions=sessions_data, active_id=session_id or ""),
                content,
                cls="flex flex-1 overflow-hidden",
            ),
            command_palette_html(commands=commands),
        )

    # --- SSE Actions ---

    @rt("/api/send")
    @sse
    async def send_message(request: Any = None):
        """Send a message from the web UI."""
        # Extract prompt value from request data (StarHTML signal values)
        text = ""
        if request is not None:
            try:
                body = await request.json()
                text = body.get("prompt", "")
            except Exception:
                text = str(sigs.get("prompt", ""))
        else:
            text = str(sigs.get("prompt", ""))

        yield signals(prompt="", status="Thinking...", streaming=True)

        if text:
            await state.send_message(text)

        yield signals(status="Ready", streaming=False)

    @rt("/api/session/new")
    @sse
    async def new_session():
        """Create a new session."""
        session_id = await state.create_session()
        yield signals(session_id=session_id, status="New session created")

    @rt("/api/session/{session_id}/switch")
    @sse
    async def switch_session(session_id: str):
        """Switch to a different session."""
        await state.switch_session(session_id)
        yield signals(session_id=session_id)

    return app
