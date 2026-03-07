"""TUI main layout — toolbar, sidebar, content area, status bar."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from .theme import APP_THEME


def toolbar(*, title: str = "OpenCode", **kwargs: Any) -> Box:
    """Top toolbar with application title."""
    t = APP_THEME["toolbar"]
    return Box(
        Text(title, bold=True, fg=t["accent"]),
        flex_direction="row",
        justify_content="space-between",
        background_color=t["bg"],
        fg=t["fg"],
        padding_left=1,
        padding_right=1,
        **kwargs,
    )


def status_bar(*, model: str = "", branch: str = "", **kwargs: Any) -> Box:
    """Bottom status bar with model and git info."""
    t = APP_THEME["status_bar"]
    children: list[Any] = []
    if model:
        children.append(Text(model, fg=t["fg"]))
    if branch:
        children.append(Text(branch, fg=t["fg"]))
    if not children:
        children.append(Text("Ready", fg=t["fg"]))
    return Box(
        *children,
        flex_direction="row",
        justify_content="space-between",
        background_color=t["bg"],
        padding_left=1,
        padding_right=1,
        **kwargs,
    )


def sidebar(*, sessions: list[dict[str, Any]] | None = None, **kwargs: Any) -> Box:
    """Left sidebar with session list."""
    t = APP_THEME["sidebar"]
    children: list[Any] = [Text("Sessions", bold=True, fg=t["fg"])]
    if sessions:
        for s in sessions:
            children.append(Text(s.get("title", s.get("id", "Untitled")), fg=t["fg"]))
    return Box(
        *children,
        flex_direction="column",
        background_color=t["bg"],
        width=t["width"],
        **kwargs,
    )


def content_area(**kwargs: Any) -> Box:
    """Main content area (placeholder for chat/editor tabs)."""
    t = APP_THEME["content"]
    return Box(
        Text("Chat", fg=t["fg"]),
        flex_direction="column",
        flex_grow=1,
        background_color=t["bg"],
        **kwargs,
    )


def main_layout(*, title: str = "OpenCode", model: str = "", branch: str = "", **kwargs: Any) -> Box:
    """Compose the full TUI layout: toolbar + body (sidebar + content) + status bar."""
    body = Box(
        sidebar(),
        content_area(),
        flex_direction="row",
        flex_grow=1,
    )
    return Box(
        toolbar(title=title),
        body,
        status_bar(model=model, branch=branch),
        flex_direction="column",
        **kwargs,
    )
