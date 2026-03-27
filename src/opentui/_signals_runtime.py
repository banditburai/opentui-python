"""Private runtime state for the signals subsystem."""

import contextvars
from collections.abc import Callable
from operator import attrgetter
from typing import Any

_tracking_context: contextvars.ContextVar[set[Any] | None] = contextvars.ContextVar(
    "_tracking_context", default=None
)


class _RuntimeState:
    __slots__ = (
        "batch_depth",
        "batch_pending",
        "depth_key",
        "flushing",
        "owner_stack",
        "stale_computeds",
    )

    def __init__(self) -> None:
        self.batch_depth = 0
        self.batch_pending: set[Any] = set()
        self.flushing = False
        self.stale_computeds: list[Any] = []
        self.depth_key = attrgetter("_depth")
        self.owner_stack: list[list[Callable[[], Any]]] = []


_runtime = _RuntimeState()


class _SignalState:
    __slots__ = ("_notified",)

    def __init__(self):
        self._notified: set[Any] = set()

    def has_changes(self) -> bool:
        return bool(self._notified)

    def reset(self) -> None:
        self._notified.clear()


_signal_state: _SignalState = _SignalState()
_signal_state_notified: set[Any] = _signal_state._notified


def _begin_micro_flush() -> bool:
    is_root = not _runtime.flushing
    if is_root:
        _runtime.flushing = True
    return is_root


def _end_micro_flush(drain_stale_computeds: Callable[[], None], is_root: bool) -> None:
    if is_root:
        try:
            drain_stale_computeds()
        finally:
            _runtime.flushing = False


class Batch:
    """Defer notifications until outermost batch exits. Batches nest."""

    __slots__ = ()

    def __enter__(self) -> None:
        _runtime.batch_depth += 1

    def __exit__(self, *_: Any) -> None:
        if _runtime.batch_depth <= 0:
            return
        _runtime.batch_depth -= 1
        if _runtime.batch_depth == 0:
            from .signals import _flush_batch

            _flush_batch()


__all__ = ["Batch", "_SignalState", "_runtime", "_signal_state", "_tracking_context"]
