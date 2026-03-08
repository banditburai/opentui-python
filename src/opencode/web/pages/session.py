"""Session page — chat view with messages and prompt."""

from __future__ import annotations

from starhtml import Div, get

from ..components.message import message_html
from ..components.prompt import prompt_html


def session_page(
    *,
    messages: list[dict] | None = None,
    streaming: bool = False,
) -> Div:
    """Render the session/chat view."""
    msg_children = []
    for msg in (messages or []):
        msg_children.append(
            message_html(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                model=msg.get("model", ""),
                tool_calls=msg.get("tool_calls"),
            )
        )

    return Div(
        # Chat area
        Div(
            *msg_children,
            id="messages",
            data_on_load=get("/api/event"),
            cls="flex-1 overflow-y-auto",
        ),
        # Prompt
        prompt_html(),
        cls="flex flex-col flex-1",
    )
