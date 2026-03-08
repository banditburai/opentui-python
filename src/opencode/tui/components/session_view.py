"""Session view — renders messages with typed parts, tool results, and reasoning."""

from __future__ import annotations

import json
from typing import Any

from opentui.components import Box, Text

from ..themes import get_theme
from . import CURSOR
from .chat import parse_markdown
from .todo_item import todo_item
from .tool_results import render_tool_result


# ---------------------------------------------------------------------------
# Message part renderers
# ---------------------------------------------------------------------------


def _render_text_part(content: str, streaming: bool = False) -> Box:
    """Render a text part with markdown parsing."""
    t = get_theme()
    nodes = parse_markdown(content)
    if streaming:
        nodes.append(Text(CURSOR, fg=t.accent))
    return Box(*nodes, flex_direction="column") if nodes else Box(flex_direction="column")


def _render_reasoning_part(content: str) -> Box:
    """Render a reasoning/thinking part in a muted, bordered box."""
    t = get_theme()
    return Box(
        Text("Thinking:", fg=t.text_muted, italic=True, bold=True),
        Text(content, fg=t.text_muted, italic=True),
        flex_direction="column",
        border=True,
        border_style="round",
        border_color=t.border_subtle,
        padding_left=1,
        padding_right=1,
        margin_left=2,
    )


def _render_tool_call_part(
    tool_name: str,
    content: str,
    status: str = "completed",
    metadata: str | None = None,
) -> Box:
    """Render a tool call with its result."""
    return render_tool_result(tool_name, content, metadata=metadata, status=status)


def _render_error_part(content: str) -> Box:
    """Render an error part."""
    t = get_theme()
    return Box(
        Text("\u2716 Error", fg=t.error, bold=True),
        Text(content, fg=t.error),
        flex_direction="column",
        border=True,
        border_style="round",
        border_color=t.error,
        padding_left=1,
        padding_right=1,
        margin_left=2,
    )


def _render_todo_part(content: str, metadata: str | None = None) -> Box:
    """Render todo items from a tool result."""
    t = get_theme()
    try:
        meta = json.loads(metadata) if metadata else {}
    except (json.JSONDecodeError, TypeError):
        meta = {}

    todos = meta.get("todos", [])
    if not todos and content:
        # Try to parse from content
        try:
            data = json.loads(content)
            if isinstance(data, list):
                todos = data
        except (json.JSONDecodeError, TypeError):
            pass

    if not todos:
        return Box(Text(content or "(no todos)", fg=t.text_muted), flex_direction="column")

    items = [
        todo_item(status=td.get("status", "pending"), content=td.get("content", ""))
        for td in todos
    ]
    return Box(*items, flex_direction="column", margin_left=2)


# ---------------------------------------------------------------------------
# Part dispatcher
# ---------------------------------------------------------------------------

_PART_RENDERERS = {
    "text": lambda part, streaming: _render_text_part(part.get("content", ""), streaming),
    "reasoning": lambda part, _: _render_reasoning_part(part.get("content", "")),
    "tool_call": lambda part, _: _render_tool_call_part(
        part.get("tool_name", "tool"),
        part.get("content", ""),
        part.get("status", "completed"),
        part.get("metadata"),
    ),
    "tool_result": lambda part, _: _render_tool_call_part(
        part.get("tool_name", "tool"),
        part.get("content", ""),
        part.get("status", "completed"),
        part.get("metadata"),
    ),
    "error": lambda part, _: _render_error_part(part.get("content", "")),
    "todo": lambda part, _: _render_todo_part(part.get("content", ""), part.get("metadata")),
}


def render_part(part: dict[str, Any], streaming: bool = False) -> Box | None:
    """Render a single message part dict."""
    part_type = part.get("type", "text")
    renderer = _PART_RENDERERS.get(part_type)
    if renderer:
        return renderer(part, streaming)
    # Unknown part type — render as text
    content = part.get("content", "")
    if content:
        return _render_text_part(content)
    return None


# ---------------------------------------------------------------------------
# User message
# ---------------------------------------------------------------------------


def user_message(
    *,
    content: str,
    parts: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> Box:
    """Render a user message with role label and content."""
    t = get_theme()
    children: list[Box | Text] = [
        Text("User", bold=True, fg=t.info),
    ]

    if parts:
        for p in parts:
            node = render_part(p)
            if node:
                children.append(node)
    else:
        # Fallback: render content as text
        nodes = parse_markdown(content)
        if nodes:
            children.append(Box(*nodes, flex_direction="column"))

    return Box(
        *children,
        flex_direction="column",
        padding_left=1,
        padding_right=1,
        padding_bottom=1,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Assistant message
# ---------------------------------------------------------------------------


def assistant_message(
    *,
    content: str,
    parts: list[dict[str, Any]] | None = None,
    streaming: bool = False,
    model: str = "",
    error: str | None = None,
    **kwargs: Any,
) -> Box:
    """Render an assistant message with parts, tool results, and metadata."""
    t = get_theme()
    children: list[Box | Text] = [
        Text("Assistant", bold=True, fg=t.success),
    ]

    if parts:
        for i, p in enumerate(parts):
            is_last = i == len(parts) - 1
            is_text_streaming = streaming and is_last and p.get("type") == "text"
            node = render_part(p, streaming=is_text_streaming)
            if node:
                children.append(node)
    else:
        # Fallback: render content as text
        nodes = parse_markdown(content)
        if streaming:
            nodes.append(Text(CURSOR, fg=t.accent))
        if nodes:
            children.append(Box(*nodes, flex_direction="column"))

    # Error display
    if error:
        children.append(_render_error_part(error))

    # Model metadata footer
    if model and not streaming:
        children.append(Text(f"  \u2014 {model}", fg=t.text_muted))

    return Box(
        *children,
        flex_direction="column",
        padding_left=1,
        padding_right=1,
        padding_bottom=1,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Session view (replaces chat_panel for rich rendering)
# ---------------------------------------------------------------------------


def session_view(
    *,
    messages: list[dict[str, Any]],
    streaming: bool = False,
    **kwargs: Any,
) -> Box:
    """Render a session as a scrollable list of user/assistant messages with parts.

    Each message dict should have:
    - role: 'user' | 'assistant'
    - content: str
    - parts: list[dict] (optional, typed parts)
    - model: str (optional)
    - error: str | None (optional)
    - tool_calls: str | None (optional, JSON)
    - tool_results: str | None (optional, JSON)
    """
    t = get_theme()
    children: list[Box] = []

    for i, msg in enumerate(messages):
        is_last = i == len(messages) - 1
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts = msg.get("parts")
        model = msg.get("model", "")
        error = msg.get("error")

        # If no parts, synthesize from tool_calls/tool_results
        if not parts:
            parts = _synthesize_parts(msg)

        if role == "user":
            children.append(user_message(content=content, parts=parts))
        elif role == "assistant":
            is_streaming = streaming and is_last
            children.append(
                assistant_message(
                    content=content,
                    parts=parts,
                    streaming=is_streaming,
                    model=model,
                    error=error,
                )
            )
        elif role == "tool":
            # Tool messages rendered inline with previous assistant
            tool_name = content or "tool"
            result = msg.get("tool_results", "")
            children.append(
                Box(
                    render_tool_result(tool_name, result),
                    padding_left=1,
                )
            )

    return Box(
        *children,
        flex_direction="column",
        gap=1,
        flex_grow=1,
        background_color=t.background,
        **kwargs,
    )


def _synthesize_parts(msg: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Synthesize parts from legacy tool_calls/tool_results fields."""
    content = msg.get("content", "")
    tool_calls_json = msg.get("tool_calls")

    if not tool_calls_json:
        return None  # Use content fallback

    parts: list[dict[str, Any]] = []

    # Add text content if present
    if content:
        parts.append({"type": "text", "content": content})

    # Parse tool calls
    try:
        tool_calls = json.loads(tool_calls_json) if isinstance(tool_calls_json, str) else tool_calls_json
    except (json.JSONDecodeError, TypeError):
        return parts or None

    if isinstance(tool_calls, list):
        for tc in tool_calls:
            fn = tc.get("function", {})
            parts.append({
                "type": "tool_call",
                "tool_name": fn.get("name", "tool"),
                "content": "",
                "status": "completed",
                "tool_call_id": tc.get("id", ""),
            })

    return parts or None
