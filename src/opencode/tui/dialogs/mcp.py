"""MCP status dialog — shows connected MCP servers and their status."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from ..components.dialog import dialog_box
from ..themes import get_theme


class McpStatusState:
    """State for the MCP status dialog."""

    def __init__(self, servers: list[dict[str, Any]] | None = None) -> None:
        self.servers = servers or []

    def update(self, servers: list[dict[str, Any]]) -> None:
        self.servers = servers


def mcp_status_dialog(state: McpStatusState) -> Box:
    """Render MCP server status dialog."""
    t = get_theme()

    if not state.servers:
        return dialog_box(
            Text("No MCP servers configured.", fg=t.text_muted),
            Box(
                Text("Add servers in opencode.json under \"mcp_servers\"", fg=t.text_muted),
                padding_top=1,
            ),
            title="MCP Servers",
        )

    children: list[Box | Text] = []
    for server in state.servers:
        name = server.get("name", "unknown")
        status = server.get("status", "disconnected")
        tool_count = len(server.get("tools", []))

        status_color = t.success if status == "connected" else t.error
        status_icon = "\u25cf" if status == "connected" else "\u25cb"

        row = Box(
            Text(f" {status_icon} ", fg=status_color),
            Text(name, fg=t.text, bold=True),
            Text(f"  {status}", fg=status_color),
            Text(f"  ({tool_count} tools)", fg=t.text_muted),
            flex_direction="row",
            padding_left=1,
        )
        children.append(row)

    return dialog_box(
        *children,
        title="MCP Servers",
    )
