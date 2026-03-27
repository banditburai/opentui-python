"""Async resource loading — SolidJS create_resource parity.

Provides ``create_resource(fetcher, source)`` for async data loading
with reactive ``data``, ``loading``, and ``error`` signals.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from .signals import Batch, ReadableSignal, Signal

# Cache the import so we don't pay for it on every Resource creation.
_register_suspense_resource: Callable[..., None] | None = None


def _get_register_suspense_resource() -> Callable[..., None] | None:
    global _register_suspense_resource
    if _register_suspense_resource is None:
        try:
            from .components.structural import _register_suspense_resource as _reg

            _register_suspense_resource = _reg
        except ImportError:
            return None
    return _register_suspense_resource


class Resource:
    """Async data resource with reactive state.

    Wraps an async fetcher function and exposes reactive signals:
    - ``data``: The fetched data (None until loaded)
    - ``loading``: True while fetching
    - ``error``: Exception if fetch failed, else None

    Usage::

        async def fetch_users():
            return await api.get("/users")

        users = create_resource(fetch_users)
        # users.data()  → None (loading)
        # users.loading()  → True
        # ... after fetch completes ...
        # users.data()  → [...]
        # users.loading()  → False

    With a source signal (refetches when source changes)::

        user_id = Signal(1)
        user = create_resource(
            lambda uid: api.get(f"/users/{uid}"),
            source=user_id,
        )
        user_id.set(2)  # triggers refetch
    """

    __slots__ = ("_data", "_loading", "_error", "_fetcher", "_source", "_source_unsub", "_task")

    def __init__(
        self,
        fetcher: Callable[..., Any],
        source: ReadableSignal | None = None,
    ):
        self._data: Signal = Signal(None, name="resource_data")
        self._loading: Signal = Signal(True, name="resource_loading")
        self._error: Signal = Signal(None, name="resource_error")
        self._fetcher = fetcher
        self._source = source
        self._source_unsub: Callable[[], None] | None = None
        self._task: asyncio.Task | None = None

        if source is not None:
            self._source_unsub = source.subscribe(lambda _: self.refetch())

        reg = _get_register_suspense_resource()
        if reg is not None:
            reg(self._loading)

        self._fetch(source.peek() if source is not None else None)

    @property
    def data(self) -> Signal:
        return self._data

    @property
    def loading(self) -> Signal:
        return self._loading

    @property
    def error(self) -> Signal:
        return self._error

    def refetch(self) -> None:
        source_val = self._source() if self._source is not None else None
        self._fetch(source_val)

    def _resolve_success(self, result: Any) -> None:
        with Batch():
            self._data.set(result)
            self._error.set(None)
            self._loading.set(False)

    def _resolve_error(self, err: Exception) -> None:
        with Batch():
            self._error.set(err)
            self._loading.set(False)

    def _call_fetcher(self, source_val: Any) -> Any:
        if self._source is not None:
            return self._fetcher(source_val)
        return self._fetcher()

    def _fetch(self, source_val: Any) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

        self._loading.set(True)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop — run synchronously for testing
            self._run_sync(source_val)
            return

        self._task = loop.create_task(self._run_async(source_val))

    async def _run_async(self, source_val: Any) -> None:
        try:
            result = self._call_fetcher(source_val)

            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                result = await result

            self._resolve_success(result)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._resolve_error(e)

    def _run_sync(self, source_val: Any) -> None:
        try:
            result = self._call_fetcher(source_val)

            # If the fetcher returns a coroutine, we can't await it
            if asyncio.iscoroutine(result):
                result.close()
                self._resolve_error(RuntimeError("Cannot await coroutine without event loop"))
                return

            self._resolve_success(result)
        except Exception as e:
            self._resolve_error(e)

    def dispose(self) -> None:
        if self._source_unsub is not None:
            self._source_unsub()
            self._source_unsub = None
        if self._task is not None and not self._task.done():
            self._task.cancel()
            self._task = None


def create_resource(
    fetcher: Callable[..., Any],
    source: ReadableSignal | None = None,
) -> Resource:
    return Resource(fetcher, source)


__all__ = ["Resource", "create_resource"]
