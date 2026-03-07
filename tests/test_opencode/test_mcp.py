"""Tests for MCP client integration."""

import asyncio

import pytest
from opencode.mcp.client import MCPClient, MCPTool


class TestMCPTool:
    def test_fields(self):
        t = MCPTool(name="read", description="Read a file", input_schema={"type": "object"})
        assert t.name == "read"
        assert t.description == "Read a file"

    def test_to_openai_format(self):
        t = MCPTool(
            name="search",
            description="Search files",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        fmt = t.to_openai_format()
        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "search"
        assert fmt["function"]["parameters"]["properties"]["q"]["type"] == "string"


class TestMCPClient:
    def test_init(self):
        c = MCPClient(command="echo", args=["hello"])
        assert c.command == "echo"
        assert c.args == ["hello"]
        assert not c.is_connected

    def test_init_defaults(self):
        c = MCPClient(command="server")
        assert c.args == []
        assert c.env is None

    def test_connect_requires_mcp(self):
        c = MCPClient(command="echo")

        async def _run():
            with pytest.raises(ImportError, match="mcp"):
                await c.connect()

        asyncio.run(_run())

    def test_disconnect_noop_when_not_connected(self):
        c = MCPClient(command="echo")
        asyncio.run(c.disconnect())
        assert not c.is_connected

    def test_list_tools_when_disconnected(self):
        c = MCPClient(command="echo")
        assert c.list_tools() == []

    def test_call_tool_when_disconnected(self):
        c = MCPClient(command="echo")

        async def _run():
            with pytest.raises(RuntimeError, match="not connected"):
                await c.call_tool("read", path="/tmp/x")

        asyncio.run(_run())

    def test_context_manager_requires_mcp(self):
        async def _run():
            with pytest.raises(ImportError, match="mcp"):
                async with MCPClient(command="echo") as c:
                    pass

        asyncio.run(_run())
