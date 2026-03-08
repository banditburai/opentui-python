"""SSE event streaming — GET /event with heartbeat."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencode.bus import EventBus


def event_routes(bus: EventBus) -> list[Any]:
    """SSE event stream routes."""
    from starlette.requests import Request
    from starlette.routing import Route

    from starhtml import EventStream

    async def events_endpoint(request: Request) -> Any:
        """Subscribe to all bus events via SSE."""

        async def event_generator():
            async for event in bus.iter_events():
                if await request.is_disconnected():
                    break
                yield json.dumps({
                    "event": event.type,
                    "session_id": event.session_id,
                    "timestamp": event.timestamp,
                    **event.data,
                })

        async def heartbeat_generator():
            """Merge events with a 15-second heartbeat."""
            event_iter = event_generator().__aiter__()
            while True:
                try:
                    data = await asyncio.wait_for(event_iter.__anext__(), timeout=15.0)
                    yield data
                except TimeoutError:
                    # SSE comment line as heartbeat (keeps connection alive)
                    yield ": heartbeat"
                except StopAsyncIteration:
                    break

        return EventStream(heartbeat_generator())

    return [
        Route("/event", events_endpoint),
    ]
