"""Session management sidebar — session list with active highlighting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from opentui.components import Box, Text

from ..themes import get_theme


@dataclass
class SessionItem:
    """Lightweight session descriptor for sidebar display."""

    id: str
    title: str
    updated_at: datetime


SIDEBAR_WIDTH = 30


def session_list(
    *,
    sessions: list[SessionItem],
    active_id: str = "",
    **kwargs: Any,
) -> Box:
    """Render a list of sessions, highlighting the active one."""
    t = get_theme()

    if not sessions:
        return Box(
            Text("No sessions", fg=t.text_muted, italic=True),
            flex_direction="column",
            **kwargs,
        )

    max_title_len = SIDEBAR_WIDTH - 2
    children: list[Box] = []
    for s in sessions:
        display_title = (s.title or "Untitled")[:max_title_len]
        is_active = s.id == active_id

        label = Text(
            display_title,
            bold=is_active,
            fg=t.primary if is_active else t.text,
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
    t = get_theme()

    header = Text("Sessions", bold=True, fg=t.text)
    sl = session_list(sessions=sessions, active_id=active_id)

    defaults = dict(
        flex_direction="column",
        background_color=t.background_panel,
        width=SIDEBAR_WIDTH,
        padding_top=1,
        gap=1,
    )
    defaults.update(kwargs)

    return Box(header, sl, **defaults)
