"""MCP client for connecting to tool servers via stdio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        self._session: Any = None
        self._tools: list[MCPTool] = []

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    async def connect(self) -> None:
        """Connect to the MCP server process."""
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

        transport = await stdio_client(params).__aenter__()
        read_stream, write_stream = transport
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()

        # Discover tools
        result = await self._session.list_tools()
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
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None
            self._tools = []

    def list_tools(self) -> list[MCPTool]:
        """Return discovered tools (empty if not connected)."""
        return list(self._tools)

    async def call_tool(self, name: str, **kwargs: Any) -> str:
        """Call a tool on the MCP server."""
        if self._session is None:
            raise RuntimeError("MCP client not connected")
        result = await self._session.call_tool(name, arguments=kwargs)
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
