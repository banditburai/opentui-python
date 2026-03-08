"""Tests for session view, tool result renderers, todo items, and message parts."""

from __future__ import annotations

import json

import pytest

from opentui.components import Box, Text

from opencode.db.models import MessagePart
from opencode.db.store import Store
from opencode.tui.components.session_view import (
    _render_error_part,
    _render_reasoning_part,
    _render_text_part,
    _render_todo_part,
    _render_tool_call_part,
    _synthesize_parts,
    assistant_message,
    render_part,
    session_view,
    user_message,
)
from opencode.tui.components.todo_item import todo_item
from opencode.tui.components.tool_results import (
    block_tool,
    inline_tool,
    render_bash_result,
    render_edit_result,
    render_generic_result,
    render_glob_result,
    render_grep_result,
    render_read_result,
    render_tool_result,
    render_write_result,
    tool_icon,
)
from opencode.tui.themes import init_theme


@pytest.fixture(autouse=True)
def _theme():
    init_theme("opencode", "dark")


# ---------------------------------------------------------------------------
# Tool result renderers
# ---------------------------------------------------------------------------


class TestToolIcon:
    def test_renders_text(self):
        icon = tool_icon("$", "#ff0000")
        assert isinstance(icon, Text)


class TestInlineTool:
    def test_renders_box(self):
        box = inline_tool(icon="$", label="bash")
        assert isinstance(box, Box)

    def test_with_detail(self):
        box = inline_tool(icon="$", label="bash", detail="(ok)")
        assert isinstance(box, Box)

    def test_error_status(self):
        box = inline_tool(icon="$", label="bash", status="error")
        assert isinstance(box, Box)


class TestBlockTool:
    def test_renders_box(self):
        box = block_tool(title="test", children=[Text("output")])
        assert isinstance(box, Box)

    def test_error_status(self):
        box = block_tool(title="test", children=[Text("err")], status="error")
        assert isinstance(box, Box)


class TestBashRenderer:
    def test_empty_output(self):
        result = render_bash_result("")
        assert isinstance(result, Box)

    def test_with_command(self):
        meta = json.dumps({"command": "ls -la"})
        result = render_bash_result("file1\nfile2", meta)
        assert isinstance(result, Box)

    def test_with_exit_code(self):
        meta = json.dumps({"command": "false", "exit_code": 1})
        result = render_bash_result("error", meta)
        assert isinstance(result, Box)

    def test_truncation(self):
        lines = "\n".join(f"line-{i}" for i in range(50))
        result = render_bash_result(lines)
        assert isinstance(result, Box)


class TestReadRenderer:
    def test_empty(self):
        meta = json.dumps({"path": "test.py"})
        result = render_read_result("", meta)
        assert isinstance(result, Box)

    def test_with_content(self):
        meta = json.dumps({"path": "test.py"})
        result = render_read_result("hello world\nline 2", meta)
        assert isinstance(result, Box)

    def test_truncation(self):
        lines = "\n".join(f"line {i}" for i in range(30))
        meta = json.dumps({"path": "big.py"})
        result = render_read_result(lines, meta)
        assert isinstance(result, Box)


class TestWriteRenderer:
    def test_renders(self):
        meta = json.dumps({"path": "out.txt"})
        result = render_write_result("written", meta)
        assert isinstance(result, Box)


class TestEditRenderer:
    def test_empty(self):
        meta = json.dumps({"path": "file.py"})
        result = render_edit_result("", meta)
        assert isinstance(result, Box)

    def test_with_diff(self):
        diff = "+added\n-removed\n context\n@@ -1,3 +1,3 @@"
        meta = json.dumps({"path": "file.py"})
        result = render_edit_result(diff, meta)
        assert isinstance(result, Box)


class TestGlobRenderer:
    def test_renders(self):
        meta = json.dumps({"pattern": "*.py", "path": "src"})
        result = render_glob_result("a.py\nb.py", meta)
        assert isinstance(result, Box)

    def test_empty_matches(self):
        result = render_glob_result("")
        assert isinstance(result, Box)


class TestGrepRenderer:
    def test_renders(self):
        meta = json.dumps({"pattern": "def ", "path": "."})
        result = render_grep_result("src/a.py:1: def foo", meta)
        assert isinstance(result, Box)


class TestGenericRenderer:
    def test_no_content(self):
        result = render_generic_result("unknown", "")
        assert isinstance(result, Box)

    def test_with_content(self):
        result = render_generic_result("unknown", "some output")
        assert isinstance(result, Box)

    def test_truncation(self):
        lines = "\n".join(f"line-{i}" for i in range(20))
        result = render_generic_result("unknown", lines)
        assert isinstance(result, Box)


class TestToolResultDispatcher:
    def test_bash(self):
        result = render_tool_result("bash", "output")
        assert isinstance(result, Box)

    def test_shell(self):
        result = render_tool_result("shell", "output")
        assert isinstance(result, Box)

    def test_read(self):
        result = render_tool_result("read", "content")
        assert isinstance(result, Box)

    def test_write(self):
        result = render_tool_result("write", "ok")
        assert isinstance(result, Box)

    def test_edit(self):
        result = render_tool_result("edit", "+line")
        assert isinstance(result, Box)

    def test_glob(self):
        result = render_tool_result("glob", "a.py")
        assert isinstance(result, Box)

    def test_grep(self):
        result = render_tool_result("grep", "match")
        assert isinstance(result, Box)

    def test_unknown(self):
        result = render_tool_result("my_custom_tool", "data")
        assert isinstance(result, Box)

    def test_read_file_alias(self):
        result = render_tool_result("read_file", "content")
        assert isinstance(result, Box)

    def test_search_files_alias(self):
        result = render_tool_result("search_files", "a.py")
        assert isinstance(result, Box)


# ---------------------------------------------------------------------------
# Todo item
# ---------------------------------------------------------------------------


class TestTodoItem:
    def test_completed(self):
        box = todo_item(status="completed", content="Done task")
        assert isinstance(box, Box)

    def test_in_progress(self):
        box = todo_item(status="in_progress", content="Working")
        assert isinstance(box, Box)

    def test_pending(self):
        box = todo_item(status="pending", content="Not started")
        assert isinstance(box, Box)


# ---------------------------------------------------------------------------
# Session view part renderers
# ---------------------------------------------------------------------------


class TestPartRenderers:
    def test_text_part(self):
        box = _render_text_part("hello **world**")
        assert isinstance(box, Box)

    def test_text_part_streaming(self):
        box = _render_text_part("typing...", streaming=True)
        assert isinstance(box, Box)

    def test_reasoning_part(self):
        box = _render_reasoning_part("I need to think about this...")
        assert isinstance(box, Box)

    def test_tool_call_part(self):
        box = _render_tool_call_part("bash", "output", status="completed")
        assert isinstance(box, Box)

    def test_error_part(self):
        box = _render_error_part("Something went wrong")
        assert isinstance(box, Box)

    def test_todo_part_with_metadata(self):
        meta = json.dumps({"todos": [
            {"status": "completed", "content": "Task 1"},
            {"status": "pending", "content": "Task 2"},
        ]})
        box = _render_todo_part("", meta)
        assert isinstance(box, Box)

    def test_todo_part_from_content(self):
        content = json.dumps([
            {"status": "in_progress", "content": "Working on it"},
        ])
        box = _render_todo_part(content)
        assert isinstance(box, Box)


class TestRenderPart:
    def test_text(self):
        box = render_part({"type": "text", "content": "hello"})
        assert isinstance(box, Box)

    def test_reasoning(self):
        box = render_part({"type": "reasoning", "content": "thinking"})
        assert isinstance(box, Box)

    def test_tool_call(self):
        box = render_part({"type": "tool_call", "tool_name": "bash", "content": "out"})
        assert isinstance(box, Box)

    def test_error(self):
        box = render_part({"type": "error", "content": "fail"})
        assert isinstance(box, Box)

    def test_unknown_with_content(self):
        box = render_part({"type": "custom_type", "content": "data"})
        assert isinstance(box, Box)

    def test_unknown_empty(self):
        result = render_part({"type": "custom_type"})
        assert result is None


# ---------------------------------------------------------------------------
# User and assistant messages
# ---------------------------------------------------------------------------


class TestUserMessage:
    def test_basic(self):
        box = user_message(content="Hello!")
        assert isinstance(box, Box)

    def test_with_parts(self):
        parts = [{"type": "text", "content": "Hello from parts"}]
        box = user_message(content="", parts=parts)
        assert isinstance(box, Box)


class TestAssistantMessage:
    def test_basic(self):
        box = assistant_message(content="I can help with that.")
        assert isinstance(box, Box)

    def test_streaming(self):
        box = assistant_message(content="Thinking", streaming=True)
        assert isinstance(box, Box)

    def test_with_model(self):
        box = assistant_message(content="Done.", model="gpt-4")
        assert isinstance(box, Box)

    def test_with_error(self):
        box = assistant_message(content="", error="API timeout")
        assert isinstance(box, Box)

    def test_with_parts(self):
        parts = [
            {"type": "text", "content": "Let me help."},
            {"type": "tool_call", "tool_name": "bash", "content": "file1"},
            {"type": "text", "content": "Here's the result."},
        ]
        box = assistant_message(content="", parts=parts)
        assert isinstance(box, Box)


# ---------------------------------------------------------------------------
# Session view
# ---------------------------------------------------------------------------


class TestSessionView:
    def test_empty(self):
        box = session_view(messages=[])
        assert isinstance(box, Box)

    def test_user_only(self):
        box = session_view(messages=[{"role": "user", "content": "hi"}])
        assert isinstance(box, Box)

    def test_conversation(self):
        msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        box = session_view(messages=msgs)
        assert isinstance(box, Box)

    def test_with_tool_messages(self):
        msgs = [
            {"role": "user", "content": "List files"},
            {"role": "assistant", "content": "Sure.", "tool_calls": json.dumps([
                {"id": "tc1", "function": {"name": "bash", "arguments": '{"command": "ls"}'}}
            ])},
            {"role": "tool", "content": "bash", "tool_results": "file1\nfile2"},
            {"role": "assistant", "content": "Here are the files."},
        ]
        box = session_view(messages=msgs)
        assert isinstance(box, Box)

    def test_streaming(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "I'm typing..."},
        ]
        box = session_view(messages=msgs, streaming=True)
        assert isinstance(box, Box)


class TestSynthesizeParts:
    def test_no_tool_calls(self):
        result = _synthesize_parts({"content": "hello"})
        assert result is None

    def test_with_tool_calls(self):
        msg = {
            "content": "Let me check.",
            "tool_calls": json.dumps([
                {"id": "tc1", "function": {"name": "bash", "arguments": "{}"}}
            ]),
        }
        parts = _synthesize_parts(msg)
        assert parts is not None
        assert len(parts) == 2  # text + tool_call
        assert parts[0]["type"] == "text"
        assert parts[1]["type"] == "tool_call"
        assert parts[1]["tool_name"] == "bash"

    def test_invalid_json(self):
        msg = {"content": "", "tool_calls": "not json"}
        parts = _synthesize_parts(msg)
        assert parts is None or parts == []


# ---------------------------------------------------------------------------
# MessagePart model + store
# ---------------------------------------------------------------------------


class TestMessagePartModel:
    def test_create(self):
        part = MessagePart(
            id="p1",
            message_id="m1",
            type="text",
            content="hello",
        )
        assert part.type == "text"
        assert part.status == "completed"

    def test_tool_call_part(self):
        part = MessagePart(
            id="p2",
            message_id="m1",
            type="tool_call",
            tool_name="bash",
            tool_call_id="tc1",
            status="running",
        )
        assert part.tool_name == "bash"
        assert part.status == "running"


class TestMessagePartStore:
    def test_create_and_get(self):
        store = Store(":memory:")
        # Need a session + message first
        from opencode.db.models import Message, Session

        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="assistant"))

        part = MessagePart(id="p1", message_id="m1", type="text", content="hello")
        store.create_message_part(part)

        parts = store.get_message_parts("m1")
        assert len(parts) == 1
        assert parts[0].content == "hello"

    def test_get_session_parts(self):
        store = Store(":memory:")
        from opencode.db.models import Message, Session

        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="user"))
        store.create_message(Message(id="m2", session_id="s1", role="assistant"))

        store.create_message_part(MessagePart(id="p1", message_id="m1", type="text", content="hi"))
        store.create_message_part(MessagePart(id="p2", message_id="m2", type="text", content="hello"))
        store.create_message_part(MessagePart(id="p3", message_id="m2", type="tool_call", tool_name="bash"))

        session_parts = store.get_session_parts("s1")
        assert "m1" in session_parts
        assert "m2" in session_parts
        assert len(session_parts["m1"]) == 1
        assert len(session_parts["m2"]) == 2

    def test_update_part(self):
        store = Store(":memory:")
        from opencode.db.models import Message, Session

        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="assistant"))

        store.create_message_part(
            MessagePart(id="p1", message_id="m1", type="tool_call", status="running")
        )
        store.update_message_part("p1", status="completed", content="done")

        parts = store.get_message_parts("m1")
        assert parts[0].status == "completed"
        assert parts[0].content == "done"

    def test_update_invalid_column(self):
        store = Store(":memory:")
        with pytest.raises(ValueError, match="Invalid column"):
            store.update_message_part("p1", tool_name="bad")

    def test_cascade_delete(self):
        store = Store(":memory:")
        from opencode.db.models import Message, Session

        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="assistant"))
        store.create_message_part(MessagePart(id="p1", message_id="m1", type="text"))

        store.delete_message("m1")
        parts = store.get_message_parts("m1")
        assert len(parts) == 0
