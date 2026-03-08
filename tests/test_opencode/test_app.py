"""Integration test: boot app, submit message, verify signal updates."""

import asyncio

from opencode.ai.stream import StreamChunk
from opencode.ai.tools import ToolRegistry
from opencode.bus import EventBus
from opencode.db.store import Store
from opencode.tui.bridge import AsyncBridge
from opencode.tui.state import AppState


class MockProvider:
    model = "test-model"

    async def stream(self, messages, *, tools=None, **kwargs):
        yield StreamChunk(content="Hello!", finish_reason="stop")


class TestAppIntegration:
    def test_full_lifecycle(self):
        """Boot → create session → send message → verify signals."""
        store = Store(":memory:")
        bus = EventBus()
        bridge = AsyncBridge()
        provider = MockProvider()
        tool_registry = ToolRegistry()

        state = AppState(
            store=store,
            provider=provider,
            tool_registry=tool_registry,
            bridge=bridge,
            bus=bus,
        )

        # Verify initial state
        assert state.messages() == []
        assert state.current_session_id() is None

        async def _run():
            # Create session
            session_id = await state.create_session()
            bridge.drain_updates()

            assert state.current_session_id() == session_id
            assert len(store.list_sessions()) == 1

            # Send a message
            await state.send_message("Hi!")
            bridge.drain_updates()

            # User message + assistant message should be in DB
            db_msgs = store.get_messages(session_id)
            assert len(db_msgs) >= 2

            user_msgs = [m for m in db_msgs if m.role == "user"]
            assert len(user_msgs) == 1
            assert user_msgs[0].content == "Hi!"

            assistant_msgs = [m for m in db_msgs if m.role == "assistant"]
            assert len(assistant_msgs) == 1
            assert "Hello!" in assistant_msgs[0].content

        asyncio.run(_run())
        store.close()

    def test_bus_events_flow(self):
        """Verify that events flow from agent loop to bus."""
        store = Store(":memory:")
        bus = EventBus()
        bridge = AsyncBridge()
        provider = MockProvider()

        state = AppState(
            store=store,
            provider=provider,
            tool_registry=ToolRegistry(),
            bridge=bridge,
            bus=bus,
        )

        events = []
        bus.subscribe("*", lambda e: events.append(e.type))

        async def _run():
            await state.send_message("test")

        asyncio.run(_run())

        assert "session.created" in events
        assert "message.chunk" in events
        assert "message.done" in events

    def test_multiple_sessions(self):
        """Create multiple sessions and switch between them."""
        store = Store(":memory:")
        bus = EventBus()
        bridge = AsyncBridge()
        provider = MockProvider()

        state = AppState(
            store=store,
            provider=provider,
            tool_registry=ToolRegistry(),
            bridge=bridge,
            bus=bus,
        )

        async def _run():
            s1 = await state.create_session()
            bridge.drain_updates()
            await state.send_message("msg1")
            bridge.drain_updates()

            s2 = await state.create_session()
            bridge.drain_updates()
            assert state.current_session_id() == s2

            await state.switch_session(s1)
            bridge.drain_updates()
            assert state.current_session_id() == s1

            msgs = state.messages()
            assert any(m.get("content") == "msg1" for m in msgs)

        asyncio.run(_run())
        store.close()
