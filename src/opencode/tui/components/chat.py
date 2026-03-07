"""Chat panel — message list with markdown rendering and streaming."""

from __future__ import annotations

import re
from typing import Any

from opentui.components import Box, Text

from ..theme import APP_THEME

# Streaming cursor character
_CURSOR = "\u2588"

# Inline markdown regex: **bold**, *italic*, `code`
_INLINE_RE = re.compile(
    r"(\*\*(.+?)\*\*"  # **bold**
    r"|\*(.+?)\*"  # *italic*
    r"|`([^`]+)`)"  # `code`
)


def parse_markdown(text: str) -> list[Text | Box]:
    """Parse markdown text into a list of Text/Box nodes.

    Supports: **bold**, *italic*, `inline code`, and fenced code blocks.
    """
    if not text:
        return []

    nodes: list[Text | Box] = []

    # Split on fenced code blocks first
    parts = re.split(r"(```\w*\n.*?\n```)", text, flags=re.DOTALL)

    for part in parts:
        fence_match = re.match(r"```(\w*)\n(.*?)\n```", part, flags=re.DOTALL)
        if fence_match:
            lang = fence_match.group(1) or ""
            code = fence_match.group(2)
            nodes.append(code_block(code, language=lang))
        else:
            nodes.extend(_parse_inline(part))

    return nodes


def _parse_inline(text: str) -> list[Text]:
    """Parse inline markdown (bold, italic, code) into Text nodes."""
    if not text:
        return []

    nodes: list[Text] = []
    last_end = 0

    for m in _INLINE_RE.finditer(text):
        # Text before this match
        before = text[last_end : m.start()]
        if before:
            nodes.append(Text(before))

        if m.group(2) is not None:
            # **bold**
            nodes.append(Text(m.group(2), bold=True))
        elif m.group(3) is not None:
            # *italic*
            nodes.append(Text(m.group(3), italic=True))
        elif m.group(4) is not None:
            # `code`
            nodes.append(Text(m.group(4), fg="#a0a0a0"))

        last_end = m.end()

    # Remaining text after last match
    remaining = text[last_end:]
    if remaining:
        nodes.append(Text(remaining))

    return nodes


def code_block(code: str, *, language: str = "", **kwargs: Any) -> Box:  # noqa: ARG001
    """Render a fenced code block as a bordered Box."""
    return Box(
        Text(code, fg="#c0c0c0"),
        background_color="#2a2a3e",
        padding_left=1,
        padding_right=1,
        border=True,
        border_style="round",
        border_color="#444444",
        **kwargs,
    )


_ROLE_COLORS = {
    "user": "#4fc3f7",
    "assistant": "#81c784",
}


def chat_message(
    *,
    role: str,
    content: str,
    streaming: bool = False,
    **kwargs: Any,
) -> Box:
    """Render a single chat message with role label and parsed content."""
    t = APP_THEME.get("content", {})
    role_color = _ROLE_COLORS.get(role, t.get("fg", "#e0e0e0"))

    # Role label
    label = Text(role.capitalize(), bold=True, fg=role_color)

    # Content nodes (with markdown parsing)
    body_nodes = parse_markdown(content)

    # Append streaming cursor
    if streaming:
        body_nodes.append(Text(_CURSOR, fg=role_color))

    body = Box(
        *body_nodes,
        flex_direction="column",
    )

    return Box(
        label,
        body,
        flex_direction="column",
        padding_left=1,
        padding_right=1,
        padding_bottom=1,
        **kwargs,
    )


def chat_panel(
    *,
    messages: list[dict[str, Any]],
    streaming: bool = False,
    **kwargs: Any,
) -> Box:
    """Render a scrollable chat panel with a list of messages.

    Each message dict should have 'role' and 'content' keys.
    When streaming=True, the last assistant message shows a cursor.
    """
    t = APP_THEME.get("content", {})
    children: list[Box] = []

    for i, msg in enumerate(messages):
        is_last = i == len(messages) - 1
        is_streaming = streaming and is_last and msg.get("role") == "assistant"
        children.append(
            chat_message(
                role=msg["role"],
                content=msg.get("content", ""),
                streaming=is_streaming,
            )
        )

    return Box(
        *children,
        flex_direction="column",
        gap=1,
        flex_grow=1,
        background_color=t.get("bg", "#1a1a2e"),
        **kwargs,
    )
