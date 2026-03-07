"""Tests for the agent tool system."""

import asyncio
import os
from pathlib import Path

import pytest
from opencode.ai.tools import ToolRegistry, Tool
from opencode.ai.tools.file import read_file_tool, write_file_tool, search_files_tool
from opencode.ai.tools.shell import shell_tool


# --- Tool dataclass ---

class TestTool:
    def test_tool_fields(self):
        async def noop(**kwargs):
            return ""
        t = Tool(
            name="test",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            execute=noop,
        )
        assert t.name == "test"
        assert t.description == "A test tool"
        assert callable(t.execute)

    def test_to_openai_format(self):
        async def noop(**kwargs):
            return ""
        t = Tool(
            name="read",
            description="Read a file",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            execute=noop,
        )
        fmt = t.to_openai_format()
        assert fmt["type"] == "function"
        assert fmt["function"]["name"] == "read"
        assert fmt["function"]["description"] == "Read a file"
        assert "path" in fmt["function"]["parameters"]["properties"]


# --- ToolRegistry ---

class TestToolRegistry:
    def test_register_and_get(self):
        async def noop(**kwargs):
            return ""
        reg = ToolRegistry()
        tool = Tool(name="foo", description="d", parameters={}, execute=noop)
        reg.register(tool)
        assert reg.get("foo") is tool

    def test_get_unknown_returns_none(self):
        reg = ToolRegistry()
        assert reg.get("missing") is None

    def test_list_tools(self):
        async def noop(**kwargs):
            return ""
        reg = ToolRegistry()
        reg.register(Tool(name="a", description="d", parameters={}, execute=noop))
        reg.register(Tool(name="b", description="d", parameters={}, execute=noop))
        assert [t.name for t in reg.list()] == ["a", "b"]

    def test_to_openai_tools(self):
        async def noop(**kwargs):
            return ""
        reg = ToolRegistry()
        reg.register(Tool(name="x", description="d", parameters={"type": "object"}, execute=noop))
        tools = reg.to_openai_tools()
        assert len(tools) == 1
        assert tools[0]["type"] == "function"

    def test_execute_tool(self):
        async def echo(**kwargs):
            return kwargs.get("msg", "")
        reg = ToolRegistry()
        reg.register(Tool(name="echo", description="d", parameters={}, execute=echo))

        async def _run():
            return await reg.execute("echo", msg="hello")
        result = asyncio.run(_run())
        assert result == "hello"

    def test_execute_unknown_raises(self):
        reg = ToolRegistry()
        async def _run():
            await reg.execute("nope")
        with pytest.raises(KeyError, match="nope"):
            asyncio.run(_run())


# --- File tools ---

class TestReadFileTool:
    def test_tool_metadata(self):
        t = read_file_tool()
        assert t.name == "read_file"
        assert "path" in t.parameters["properties"]

    def test_read_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        t = read_file_tool()
        result = asyncio.run(t.execute(path=str(f)))
        assert result == "hello world"

    def test_read_nonexistent_file(self, tmp_path):
        t = read_file_tool()
        result = asyncio.run(t.execute(path=str(tmp_path / "nope.txt")))
        assert "error" in result.lower() or "not found" in result.lower()


class TestWriteFileTool:
    def test_tool_metadata(self):
        t = write_file_tool()
        assert t.name == "write_file"
        assert "path" in t.parameters["properties"]
        assert "content" in t.parameters["properties"]

    def test_write_new_file(self, tmp_path):
        target = tmp_path / "out.txt"
        t = write_file_tool()
        result = asyncio.run(t.execute(path=str(target), content="data"))
        assert target.read_text() == "data"
        assert "wrote" in result.lower() or "success" in result.lower()

    def test_write_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "sub" / "dir" / "file.txt"
        t = write_file_tool()
        asyncio.run(t.execute(path=str(target), content="nested"))
        assert target.read_text() == "nested"


class TestSearchFilesTool:
    def test_tool_metadata(self):
        t = search_files_tool()
        assert t.name == "search_files"
        assert "pattern" in t.parameters["properties"]

    def test_search_finds_files(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        t = search_files_tool()
        result = asyncio.run(t.execute(pattern="*.py", directory=str(tmp_path)))
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result

    def test_search_no_matches(self, tmp_path):
        t = search_files_tool()
        result = asyncio.run(t.execute(pattern="*.xyz", directory=str(tmp_path)))
        assert "no matches" in result.lower() or result.strip() == ""


# --- Shell tool ---

class TestShellTool:
    def test_tool_metadata(self):
        t = shell_tool()
        assert t.name == "shell"
        assert "command" in t.parameters["properties"]

    def test_run_simple_command(self):
        t = shell_tool()
        result = asyncio.run(t.execute(command="echo hello"))
        assert "hello" in result

    def test_run_failing_command(self):
        t = shell_tool()
        result = asyncio.run(t.execute(command="false"))
        assert "exit code" in result.lower() or "error" in result.lower() or result == ""

    def test_timeout(self):
        t = shell_tool(timeout=1)
        result = asyncio.run(t.execute(command="sleep 10"))
        assert "timeout" in result.lower() or "timed out" in result.lower()
