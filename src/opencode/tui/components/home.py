"""Home screen — ASCII logo, tips, and MCP status."""

from __future__ import annotations

from typing import Any

from opentui.components import Box, Text

from ..themes import get_theme
from ..tips import format_tip, random_tip

# ASCII art logo
LOGO = r"""
  ___                    ____          _
 / _ \ _ __   ___ _ __  / ___|___   __| | ___
| | | | '_ \ / _ \ '_ \| |   / _ \ / _` |/ _ \
| |_| | |_) |  __/ | | | |__| (_) | (_| |  __/
 \___/| .__/ \___|_| |_|\____\___/ \__,_|\___|
      |_|
"""


def home_screen(
    *,
    mcp_servers: list[dict[str, Any]] | None = None,
    tip: str | None = None,
    **kwargs: Any,
) -> Box:
    """Render the home screen with logo, a tip, and MCP status.

    Pass *tip* to avoid re-randomizing on every re-render.
    """
    t = get_theme()

    # Logo
    logo_lines = [
        Text(line, fg=t.primary)
        for line in LOGO.strip().splitlines()
    ]
    logo = Box(*logo_lines, flex_direction="column", padding_bottom=1)

    # Tip
    tip_text = tip if tip is not None else random_tip()
    tip_segments = format_tip(tip_text)
    tip_parts: list[Text] = []
    for text, highlighted in tip_segments:
        tip_parts.append(
            Text(text, fg=t.accent if highlighted else t.text_muted, bold=highlighted)
        )
    tip_row = Box(*tip_parts, flex_direction="row")
    tip_box = Box(
        Text("Tip: ", fg=t.text_muted, bold=True),
        tip_row,
        flex_direction="row",
        padding_bottom=1,
    )

    # MCP status
    mcp_children: list[Box | Text] = []
    if mcp_servers:
        mcp_children.append(Text("MCP Servers:", bold=True, fg=t.text))
        for srv in mcp_servers:
            name = srv.get("name", "unknown")
            status = srv.get("status", "disconnected")
            color = t.success if status == "connected" else t.text_muted
            icon = "●" if status == "connected" else "○"
            mcp_children.append(
                Box(
                    Text(f"  {icon} {name}", fg=color),
                    flex_direction="row",
                )
            )
    else:
        mcp_children.append(Text("No MCP servers configured", fg=t.text_muted, italic=True))

    mcp_box = Box(*mcp_children, flex_direction="column")

    # Instructions
    instructions = Box(
        Text("Type a message to begin a new session", fg=t.text_muted),
        Text("Press Ctrl+K for command palette", fg=t.text_muted),
        flex_direction="column",
        padding_top=2,
    )

    return Box(
        logo,
        tip_box,
        mcp_box,
        instructions,
        flex_direction="column",
        flex_grow=1,
        padding_left=2,
        padding_top=1,
        **kwargs,
    )
