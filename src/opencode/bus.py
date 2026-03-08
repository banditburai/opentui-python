"""EventBus — typed in-process pub/sub for OpenCode.

All backend operations publish events here; TUI and SSE server subscribe.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Event:
    """A typed event flowing through the bus."""

    type: str
    session_id: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """In-process pub/sub event bus.

    Subscribers register for specific topics (event types) or "*" for all.
    Supports both callback-based and async-iterator consumption.
    """

    def __init__(self, *, history_size: int = 200) -> None:
        self._subscribers: dict[str, list[Callable[[Event], Any]]] = defaultdict(list)
        self._history: deque[Event] = deque(maxlen=history_size)
        self._async_queues: list[asyncio.Queue[Event]] = []

    def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers."""
        self._history.append(event)

        # Notify topic-specific subscribers
        for handler in self._subscribers.get(event.type, []):
            handler(event)

        # Notify wildcard subscribers
        for handler in self._subscribers.get("*", []):
            handler(event)

        # Push to async queues for iter_events consumers
        for q in self._async_queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop oldest if consumer is slow

    def subscribe(self, topic: str, handler: Callable[[Event], Any]) -> Callable[[], None]:
        """Subscribe to events on a topic. Returns an unsubscribe callable.

        Raises ``TypeError`` if handler is a coroutine function — async
        consumers should use ``iter_events()`` instead.
        """
        if asyncio.iscoroutinefunction(handler):
            raise TypeError(
                f"Cannot subscribe async handler {handler!r} — "
                "use bus.iter_events() for async consumers"
            )
        self._subscribers[topic].append(handler)

        def unsubscribe() -> None:
            try:
                self._subscribers[topic].remove(handler)
            except ValueError:
                pass

        return unsubscribe

    async def iter_events(self, topic: str = "*") -> Any:
        """Async iterator over events. Use ``async for event in bus.iter_events()``."""
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)
        self._async_queues.append(q)
        try:
            while True:
                event = await q.get()
                if topic == "*" or event.type == topic:
                    yield event
        finally:
            self._async_queues.remove(q)

    def recent(self, n: int = 50) -> list[Event]:
        """Return up to *n* most recent events."""
        items = list(self._history)
        return items[-n:]
