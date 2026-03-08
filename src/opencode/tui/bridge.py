"""AsyncBridge — thread-safe bridge between sync TUI and asyncio backend.

The TUI's main loop runs synchronously on the main thread.  All async work
(LLM streaming, tool execution, DB access) runs on a dedicated asyncio event
loop in a daemon thread.

Communication:
  Main → Async:  bridge.submit(coro) → Future
  Async → Main:  bridge.schedule_update(fn) → deque (GIL-atomic)
  Main drains:   bridge.drain_updates() called each frame via _frame_callbacks
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from concurrent.futures import Future
from typing import Any, Callable, Coroutine

import logging

from opentui.hooks import use_renderer

_log = logging.getLogger(__name__)


class AsyncBridge:
    """Thread-safe bridge between the sync TUI main thread and an asyncio loop."""

    def __init__(self) -> None:
        self._pending: deque[Callable[[], None]] = deque()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    # --- Lifecycle ---

    def start(self) -> None:
        """Start the asyncio event loop in a daemon thread."""
        if self._thread is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Register drain_updates as a frame callback on the renderer
        try:
            renderer = use_renderer()
            renderer.set_frame_callback(self._drain_frame)
        except RuntimeError:
            pass  # No renderer yet — caller must arrange draining

    def stop(self) -> None:
        """Shutdown the asyncio loop and join the thread."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._loop is not None:
            self._loop.close()
            self._loop = None

    # --- Main thread → Async thread ---

    def submit(self, coro: Coroutine[Any, Any, Any]) -> Future[Any]:
        """Submit an async coroutine from the main thread. Returns a Future."""
        if self._loop is None:
            raise RuntimeError("AsyncBridge not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    # --- Async thread → Main thread ---

    def schedule_update(self, fn: Callable[[], None]) -> None:
        """Enqueue a callable to run on the main thread next frame.

        Uses deque.append which is GIL-atomic — no lock needed.
        """
        self._pending.append(fn)

    def drain_updates(self) -> int:
        """Drain all pending updates on the main thread. Returns count drained."""
        count = 0
        while self._pending:
            try:
                fn = self._pending.popleft()
                fn()
                count += 1
            except Exception:
                _log.exception("Error in scheduled update")
        return count

    # --- Internal ---

    def _drain_frame(self, _dt: float) -> None:
        """Frame callback adapter for the renderer."""
        self.drain_updates()

    def _run_loop(self) -> None:
        """Run the asyncio event loop (target for the daemon thread)."""
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
