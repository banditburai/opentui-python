"""AppState — reactive application state + agent loop orchestration.

Signals are updated only on the main thread via AsyncBridge.schedule_update().
The async agent loop publishes events on the EventBus; the bridge translates
them into signal mutations queued for the main thread.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from opentui.signals import Signal

from opencode.ai.provider import LLMProvider
from opencode.ai.tools import ToolRegistry
from opencode.bus import Event, EventBus
from opencode.db.models import Message, Session
from opencode.db.store import Store

from .bridge import AsyncBridge

log = logging.getLogger(__name__)


class AppState:
    """Application state container.

    Owns reactive Signals read by the TUI component tree and non-reactive
    services (store, provider, tool_registry).  Provides async methods for
    the agent loop that publish events on the bus.
    """

    def __init__(
        self,
        *,
        store: Store,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        bridge: AsyncBridge,
        bus: EventBus,
    ) -> None:
        # Reactive state (read on main thread)
        self.messages: Signal = Signal("messages", [])
        self.sessions: Signal = Signal("sessions", [])
        self.current_session_id: Signal = Signal("current_session_id", None)
        self.is_streaming: Signal = Signal("is_streaming", False)
        self.status_text: Signal = Signal("status_text", "Ready")
        self.model_name: Signal = Signal("model_name", provider.model)
        self.sidebar_visible: Signal = Signal("sidebar_visible", True)

        # Services
        self.store = store
        self.provider = provider
        self.tool_registry = tool_registry
        self.bridge = bridge
        self.bus = bus

        # Wire EventBus → bridge.schedule_update → Signal mutations
        self._setup_bus_subscriptions()

    # --- Bus → Signal wiring ---

    def _setup_bus_subscriptions(self) -> None:
        self.bus.subscribe("message.chunk", self._on_message_chunk)
        self.bus.subscribe("message.done", self._on_message_done)
        self.bus.subscribe("tool.start", self._on_tool_start)
        self.bus.subscribe("tool.done", self._on_tool_done)
        self.bus.subscribe("session.created", self._on_session_event)
        self.bus.subscribe("session.switched", self._on_session_event)
        self.bus.subscribe("session.list", self._on_session_list)
        self.bus.subscribe("error", self._on_error)

    def _on_message_chunk(self, event: Event) -> None:
        chunk = event.data.get("content", "")
        def _update() -> None:
            msgs = list(self.messages())
            if msgs and msgs[-1].get("role") == "assistant":
                msgs[-1] = {**msgs[-1], "content": msgs[-1].get("content", "") + chunk}
            else:
                msgs.append({"role": "assistant", "content": chunk})
            self.messages.set(msgs)
        self.bridge.schedule_update(_update)

    def _on_message_done(self, event: Event) -> None:
        def _update() -> None:
            self.is_streaming.set(False)
            self.status_text.set("Ready")
        self.bridge.schedule_update(_update)

    def _on_tool_start(self, event: Event) -> None:
        tool_name = event.data.get("tool_name", "tool")
        def _update() -> None:
            self.status_text.set(f"Running {tool_name}...")
        self.bridge.schedule_update(_update)

    def _on_tool_done(self, event: Event) -> None:
        def _update() -> None:
            self.status_text.set("Thinking...")
        self.bridge.schedule_update(_update)

    def _on_session_event(self, event: Event) -> None:
        session_id = event.data.get("session_id")
        # Fetch session list on the bus thread (not the main/render thread)
        sessions = self.store.list_sessions()
        sessions_data = [
            {"id": s.id, "title": s.title, "updated_at": s.updated_at}
            for s in sessions
        ]
        def _update() -> None:
            if session_id:
                self.current_session_id.set(session_id)
            self.sessions.set(sessions_data)
        self.bridge.schedule_update(_update)

    def _on_session_list(self, event: Event) -> None:
        sessions_data = event.data.get("sessions", [])
        def _update() -> None:
            self.sessions.set(sessions_data)
        self.bridge.schedule_update(_update)

    def _on_error(self, event: Event) -> None:
        error_msg = event.data.get("message", "Error")
        def _update() -> None:
            self.is_streaming.set(False)
            self.status_text.set(f"Error: {error_msg}")
        self.bridge.schedule_update(_update)

    # --- Async operations (run on asyncio thread via bridge.submit) ---

    async def send_message(self, text: str) -> None:
        """Core agent loop: send user message, stream response, handle tool calls."""
        session_id = self.current_session_id()
        if not session_id:
            session_id = await self.create_session()

        # Save user message
        user_msg = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content=text,
        )
        self.store.create_message(user_msg)

        # Update messages signal with user message
        def _add_user_msg() -> None:
            msgs = list(self.messages())
            msgs.append({"role": "user", "content": text})
            self.messages.set(msgs)
            self.is_streaming.set(True)
            self.status_text.set("Thinking...")
        self.bridge.schedule_update(_add_user_msg)

        self.bus.publish(Event("message.chunk", session_id, {"content": ""}))

        # Build conversation history for LLM
        db_messages = self.store.get_messages(session_id)
        llm_messages: list[dict[str, Any]] = []
        for m in db_messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg["tool_calls"] = json.loads(m.tool_calls)
            if m.role == "tool" and m.tool_results:
                msg["content"] = m.tool_results
            llm_messages.append(msg)

        tools = self.tool_registry.to_openai_tools() or None
        await self._stream_and_handle_tools(session_id, llm_messages, tools)

    async def _stream_and_handle_tools(
        self,
        session_id: str,
        llm_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        *,
        max_rounds: int = 15,
    ) -> None:
        """Stream LLM response and iteratively handle tool calls."""
        try:
            for round_num in range(max_rounds):
                full_content = ""
                tool_calls_acc: list[dict[str, Any]] = []

                async for chunk in self.provider.stream(llm_messages, tools=tools):
                    if chunk.content:
                        full_content += chunk.content
                        self.bus.publish(Event(
                            "message.chunk", session_id,
                            {"content": chunk.content},
                        ))

                    if chunk.tool_calls:
                        for tc in chunk.tool_calls:
                            idx = tc.index if hasattr(tc, "index") else 0
                            while len(tool_calls_acc) <= idx:
                                tool_calls_acc.append({"id": "", "function": {"name": "", "arguments": ""}})
                            entry = tool_calls_acc[idx]
                            if hasattr(tc, "id") and tc.id:
                                entry["id"] = tc.id
                            if hasattr(tc, "function") and tc.function:
                                if tc.function.name:
                                    entry["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    entry["function"]["arguments"] += tc.function.arguments

                # Save assistant message
                assistant_msg = Message(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role="assistant",
                    content=full_content,
                    tool_calls=json.dumps(tool_calls_acc) if tool_calls_acc else None,
                    model=self.provider.model,
                )
                self.store.create_message(assistant_msg)

                if not tool_calls_acc:
                    # No tool calls — we're done
                    self.bus.publish(Event("message.done", session_id))
                    self.store.update_session(session_id, title=full_content[:50])
                    return

                # Append assistant message to context once (before processing tools)
                llm_messages.append({
                    "role": "assistant",
                    "content": full_content,
                    "tool_calls": tool_calls_acc,
                })

                # Handle each tool call
                for tc in tool_calls_acc:
                    tool_name = tc["function"]["name"]
                    try:
                        tool_args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                    except json.JSONDecodeError:
                        tool_args = {}

                    self.bus.publish(Event(
                        "tool.start", session_id,
                        {"tool_name": tool_name, "tool_call_id": tc["id"]},
                    ))

                    try:
                        result = await self.tool_registry.execute(tool_name, **tool_args)
                    except Exception as exc:
                        result = f"Error: {exc}"
                        log.warning("Tool %s failed: %s", tool_name, exc)

                    self.bus.publish(Event(
                        "tool.done", session_id,
                        {"tool_name": tool_name, "result": result},
                    ))

                    # Save tool result message
                    tool_msg = Message(
                        id=str(uuid.uuid4()),
                        session_id=session_id,
                        role="tool",
                        content=tool_name,
                        tool_results=result,
                    )
                    self.store.create_message(tool_msg)

                    # Append tool result to LLM context
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                # Loop continues — next iteration will stream again

            log.warning("Tool call loop reached max rounds (%d)", max_rounds)
            self.bus.publish(Event("message.done", session_id))

        except Exception as exc:
            log.error("Agent loop error: %s", exc, exc_info=True)
            self.bus.publish(Event("error", session_id, {"message": str(exc)}))

    async def create_session(self) -> str:
        """Create a new session and switch to it."""
        session = Session(id=str(uuid.uuid4()), model=self.provider.model)
        self.store.create_session(session)
        self.bus.publish(Event("session.created", session.id, {"session_id": session.id}))

        # Load messages for new (empty) session
        def _update() -> None:
            self.messages.set([])
            self.current_session_id.set(session.id)
        self.bridge.schedule_update(_update)
        return session.id

    async def switch_session(self, session_id: str) -> None:
        """Switch to an existing session."""
        db_msgs = self.store.get_messages(session_id)
        msg_dicts = [{"role": m.role, "content": m.content} for m in db_msgs]

        def _update() -> None:
            self.current_session_id.set(session_id)
            self.messages.set(msg_dicts)
        self.bridge.schedule_update(_update)
        self.bus.publish(Event("session.switched", session_id, {"session_id": session_id}))

    async def load_sessions(self) -> None:
        """Load session list from DB."""
        sessions = self.store.list_sessions()
        sessions_data = [
            {"id": s.id, "title": s.title, "updated_at": s.updated_at}
            for s in sessions
        ]
        self.bus.publish(Event("session.list", "", {"sessions": sessions_data}))

        # If there are sessions, switch to the most recent
        if sessions:
            await self.switch_session(sessions[0].id)
