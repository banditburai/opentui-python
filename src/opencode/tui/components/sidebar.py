"""Session management sidebar — session list with active highlighting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from opentui.components import Box, Text

from ..theme import APP_THEME


@dataclass
class SessionItem:
    """Lightweight session descriptor for sidebar display."""

    id: str
    title: str
    updated_at: datetime


def session_list(
    *,
    sessions: list[SessionItem],
    active_id: str = "",
    **kwargs: Any,
) -> Box:
    """Render a list of sessions, highlighting the active one."""
    t = APP_THEME.get("sidebar", {})

    if not sessions:
        return Box(
            Text("No sessions", fg="#666666", italic=True),
            flex_direction="column",
            **kwargs,
        )

    children: list[Box] = []
    for s in sessions:
        display_title = s.title or "Untitled"
        is_active = s.id == active_id

        fg = t.get("fg", "#e0e0e0")
        label = Text(
            display_title,
            bold=is_active,
            fg="#4fc3f7" if is_active else fg,
        )
        children.append(
            Box(label, flex_direction="row", padding_left=1)
        )

    return Box(*children, flex_direction="column", **kwargs)


def sidebar_panel(
    *,
    sessions: list[SessionItem],
    active_id: str = "",
    **kwargs: Any,
) -> Box:
    """Full sidebar panel with header and session list."""
    t = APP_THEME.get("sidebar", {})

    header = Text("Sessions", bold=True, fg=t.get("fg", "#e0e0e0"))
    sl = session_list(sessions=sessions, active_id=active_id)

    defaults = dict(
        flex_direction="column",
        background_color=t.get("bg", "#0f3460"),
        width=t.get("width", 30),
        padding_top=1,
        gap=1,
    )
    defaults.update(kwargs)

    return Box(header, sl, **defaults)
