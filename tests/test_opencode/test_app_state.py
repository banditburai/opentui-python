"""Tests for AppState agent loop with mock provider."""

import asyncio
import json

import pytest

from opencode.ai.provider import LLMProvider
from opencode.ai.stream import StreamChunk
from opencode.ai.tools import Tool, ToolRegistry
from opencode.bus import EventBus
from opencode.db.store import Store
from opencode.tui.bridge import AsyncBridge
from opencode.tui.state import AppState


class MockStreamIterator:
    """Async iterator that yields pre-configured chunks."""

    def __init__(self, chunks):
        self._chunks = chunks
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


class MockProvider:
    """Mock LLM provider for testing."""

    def __init__(self, chunks=None, model="test-model"):
        self.model = model
        self._chunks = chunks or [
            StreamChunk(content="Hello ", finish_reason=None),
            StreamChunk(content="world!", finish_reason="stop"),
        ]

    async def stream(self, messages, *, tools=None, **kwargs):
        for chunk in self._chunks:
            yield chunk


def make_state(provider=None, tools=None):
    """Create an AppState with in-memory store and mock provider."""
    store = Store(":memory:")
    bus = EventBus()
    bridge = AsyncBridge()

    if provider is None:
        provider = MockProvider()
    if tools is None:
        tools = ToolRegistry()

    state = AppState(
        store=store,
        provider=provider,
        tool_registry=tools,
        bridge=bridge,
        bus=bus,
    )
    return state


class TestAppState:
    def test_initial_signals(self):
        state = make_state()
        assert state.messages() == []
        assert state.sessions() == []
        assert state.current_session_id() is None
        assert state.is_streaming() is False
        assert state.status_text() == "Ready"
        assert state.model_name() == "test-model"
        assert state.sidebar_visible() is True

    def test_create_session(self):
        state = make_state()

        async def _run():
            session_id = await state.create_session()
            state.bridge.drain_updates()
            return session_id

        session_id = asyncio.run(_run())
        assert session_id is not None
        assert state.current_session_id() == session_id
        assert state.messages() == []

        # Session exists in DB
        s = state.store.get_session(session_id)
        assert s is not None
        assert s.id == session_id

    def test_send_message_basic(self):
        state = make_state()
        events = []
        state.bus.subscribe("*", lambda e: events.append(e))

        async def _run():
            await state.send_message("Hi")
            state.bridge.drain_updates()

        asyncio.run(_run())

        # Check events were published
        event_types = [e.type for e in events]
        assert "session.created" in event_types
        assert "message.chunk" in event_types
        assert "message.done" in event_types

        # After draining, messages signal should have user + assistant
        state.bridge.drain_updates()
        msgs = state.messages()
        assert any(m.get("role") == "assistant" for m in msgs)

    def test_send_message_with_tool_calls(self):
        # Provider that returns a tool call then a final response
        tool_call_chunk = StreamChunk(content="", finish_reason="tool_calls")
        tool_call_chunk.tool_calls = [
            type("ToolCall", (), {
                "index": 0,
                "id": "tc_1",
                "function": type("Fn", (), {"name": "echo", "arguments": '{"msg": "test"}'})(),
            })()
        ]

        call_count = {"n": 0}

        class ToolCallProvider:
            model = "test"
            async def stream(self, messages, *, tools=None, **kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    yield tool_call_chunk
                else:
                    yield StreamChunk(content="Done!", finish_reason="stop")

        async def echo_tool(**kwargs):
            return kwargs.get("msg", "")

        tools = ToolRegistry()
        tools.register(Tool(name="echo", description="echo", parameters={}, execute=echo_tool))

        state = make_state(provider=ToolCallProvider(), tools=tools)

        events = []
        state.bus.subscribe("*", lambda e: events.append(e))

        asyncio.run(state.send_message("test tools"))

        event_types = [e.type for e in events]
        assert "tool.start" in event_types
        assert "tool.done" in event_types
        assert "message.done" in event_types

    def test_switch_session(self):
        state = make_state()

        async def _run():
            s1 = await state.create_session()
            s2 = await state.create_session()
            state.bridge.drain_updates()
            assert state.current_session_id() == s2

            await state.switch_session(s1)
            state.bridge.drain_updates()
            assert state.current_session_id() == s1

        asyncio.run(_run())

    def test_load_sessions(self):
        state = make_state()

        async def _run():
            await state.create_session()
            await state.create_session()
            await state.load_sessions()
            state.bridge.drain_updates()

        asyncio.run(_run())
        sessions = state.sessions()
        assert len(sessions) == 2

    def test_error_event_on_provider_failure(self):
        class FailProvider:
            model = "fail"
            async def stream(self, messages, *, tools=None, **kwargs):
                raise RuntimeError("LLM unavailable")
                yield  # Make it a generator  # noqa: E501

        state = make_state(provider=FailProvider())
        events = []
        state.bus.subscribe("error", lambda e: events.append(e))

        asyncio.run(state.send_message("fail"))

        assert len(events) == 1
        assert "LLM unavailable" in events[0].data["message"]
