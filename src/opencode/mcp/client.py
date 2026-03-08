"""MCP client for connecting to tool servers via stdio."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """A tool exposed by an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class MCPClient:
    """MCP client using stdio transport.

    Connects to an MCP server process and exposes its tools.
    Requires the `mcp` package: pip install mcp
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env
        self._transport_cm: Any = None
        self._session_cm: Any = None
        self._session: Any = None
        self._tools: list[MCPTool] = []

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    async def connect(self) -> None:
        """Connect to the MCP server process."""
        if self._session is not None:
            raise RuntimeError("Already connected; call disconnect() first")

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as e:
            raise ImportError("mcp is required: pip install mcp") from e

        params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )

        self._transport_cm = stdio_client(params)
        transport = await self._transport_cm.__aenter__()
        read_stream, write_stream = transport
        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await self._session_cm.__aenter__()
        await asyncio.wait_for(self._session.initialize(), timeout=30)

        # Discover tools
        result = await asyncio.wait_for(self._session.list_tools(), timeout=30)
        self._tools = [
            MCPTool(
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema or {},
            )
            for t in result.tools
        ]

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._session is not None:
            if self._session_cm is not None:
                try:
                    await self._session_cm.__aexit__(None, None, None)
                except Exception:
                    logger.debug("Error closing MCP session", exc_info=True)
                self._session_cm = None
            if self._transport_cm is not None:
                try:
                    await self._transport_cm.__aexit__(None, None, None)
                except Exception:
                    logger.debug("Error closing MCP transport", exc_info=True)
                self._transport_cm = None
            self._session = None
            self._tools = []

    def list_tools(self) -> list[MCPTool]:
        """Return discovered tools (empty if not connected)."""
        return list(self._tools)

    async def call_tool(self, name: str, **kwargs: Any) -> str:
        """Call a tool on the MCP server."""
        if self._session is None:
            raise RuntimeError("MCP client not connected")
        known = {t.name for t in self._tools}
        if name not in known:
            raise ValueError(f"Unknown tool {name!r}; available: {sorted(known)}")
        result = await asyncio.wait_for(
            self._session.call_tool(name, arguments=kwargs), timeout=30
        )
        # MCP returns a list of content blocks
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else ""

    async def __aenter__(self) -> MCPClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.disconnect()
