"""Signal system — consolidated reactive state for OpenTUI.

Combines startui's clean mutation API (set/add/toggle, subscriber pattern,
reentrancy guard) with opentui's _SignalState renderer integration so that
signal changes trigger re-renders.
"""

from __future__ import annotations

import contextlib
import contextvars
import itertools
import threading
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

# Re-export Expr types for backward compatibility
from .expr import (
    Assignment,
    BinaryOp,
    Conditional,
    Expr,
    Literal,
    MethodCall,
    PropertyAccess,
    UnaryOp,
    _ensure_expr,
    all_,
    any_,
    match,
)

_counter = itertools.count()

# Context variable for auto-tracking signal reads inside computed/effect
_tracking_context: contextvars.ContextVar[set[Signal] | None] = contextvars.ContextVar(
    "_tracking_context", default=None
)

# ── Batching state ──────────────────────────────────────────────────
# Module-level globals for zero-overhead access on the hot path.
# Single-threaded assumption (matches the rest of the signal system).
_batch_depth: int = 0
_batch_pending: set[Signal] = set()


@runtime_checkable
class ReadableSignal(Protocol):
    """Protocol for any readable signal (Signal or computed)."""

    def __call__(self) -> Any: ...
    @property
    def name(self) -> str: ...
    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]: ...


class _SignalState:
    """Global signal state for tracking changes between renders."""

    _instance = None

    def __init__(self):
        self._signals: list[Signal] = []
        self._signal_ids: set[int] = set()
        self._notified: set[Signal] = set()
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> _SignalState:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, signal: Signal) -> None:
        sid = id(signal)
        with self._lock:
            if sid not in self._signal_ids:
                self._signal_ids.add(sid)
                self._signals.append(signal)

    def mark_notified(self, signal: Signal) -> None:
        self._notified.add(signal)

    def has_changes(self) -> bool:
        return len(self._notified) > 0

    def reset(self) -> None:
        self._signals.clear()
        self._signal_ids.clear()
        self._notified.clear()


class Signal:
    """Reactive state container.

    Combines startui's clean API with opentui's renderer integration:
    - Direct mutation: set(), add(), toggle()
    - Subscriber pattern with unsubscribe
    - Reentrancy guard to prevent recursive notification
    - _SignalState integration for renderer change detection

    Usage:
        count = Signal("count", 0)
        count.set(5)
        print(count())  # 5
        count.add(1)    # 6
        count.toggle()  # For booleans
    """

    __slots__ = ("_name", "_value", "_subscribers", "_notifying")

    def __init__(self, name: str, initial: Any = None) -> None:
        self._name = name
        self._value = initial
        self._subscribers: list[Callable[[Any], Any]] = []
        self._notifying: bool = False

        _SignalState.get_instance().register(self)

    @property
    def name(self) -> str:
        return self._name

    def __call__(self) -> Any:
        """Get current value. Registers with tracking context if active."""
        tracking = _tracking_context.get()
        if tracking is not None:
            tracking.add(self)
        return self._value

    def get(self) -> Any:
        """Get the current value (explicit)."""
        return self._value

    def set(self, value: Any) -> None:
        """Set value and notify subscribers. No-op if value unchanged."""
        if self._value is value or self._value == value:
            return
        self._value = value
        self._notify()

    def add(self, delta: Any) -> None:
        """Add delta to current value and notify."""
        new_value = self._value + delta
        if new_value == self._value:
            return
        self._value = new_value
        self._notify()

    def toggle(self) -> None:
        """Toggle boolean value and notify."""
        self._value = not self._value
        self._notify()

    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]:
        """Subscribe to value changes. Returns an unsubscribe function."""
        self._subscribers.append(fn)

        def unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._subscribers.remove(fn)

        return unsubscribe

    def _notify(self) -> None:
        """Notify _SignalState and subscribers (deferred if inside a batch)."""
        _SignalState.get_instance().mark_notified(self)
        if _batch_depth > 0:
            _batch_pending.add(self)
            return
        self._run_subscribers()

    def _run_subscribers(self) -> None:
        """Fire subscriber callbacks with current value."""
        if self._notifying:
            return  # Prevent reentrant notification
        self._notifying = True
        try:
            for sub in list(self._subscribers):  # Snapshot for safe mutation
                sub(self._value)
        finally:
            self._notifying = False

    def __hash__(self):
        return id(self)

    def __repr__(self) -> str:
        return f"Signal({self._name!r}, {self._value!r})"


class _ComputedSignal:
    """Read-only derived signal that updates when dependencies change.

    Use ``computed(fn, *deps)`` to create. If no deps are provided, deps
    are auto-discovered by running ``fn`` inside a tracking context.
    """

    __slots__ = ("_fn", "_signal", "_cleanups")

    def __init__(self, fn: Callable[[], Any], *deps: ReadableSignal) -> None:
        self._fn = fn
        self._cleanups: list[Callable[[], None]] = []

        if deps:
            # Explicit deps — evaluate normally
            self._signal = Signal(f"computed_{next(_counter)}", fn())
            for dep in deps:
                unsub = dep.subscribe(lambda _: self._recompute())
                self._cleanups.append(unsub)
        else:
            # Auto-track: run fn in tracking context to discover deps
            tracked: set[Signal] = set()
            token = _tracking_context.set(tracked)
            try:
                initial = fn()
            finally:
                _tracking_context.reset(token)
            self._signal = Signal(f"computed_{next(_counter)}", initial)
            for dep in tracked:
                unsub = dep.subscribe(lambda _: self._recompute())
                self._cleanups.append(unsub)

    def __call__(self) -> Any:
        return self._signal()

    @property
    def name(self) -> str:
        return self._signal.name

    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]:
        return self._signal.subscribe(fn)

    def dispose(self) -> None:
        """Unsubscribe from all dependencies. Prevents memory leaks."""
        for unsub in self._cleanups:
            unsub()
        self._cleanups.clear()

    def _recompute(self) -> None:
        self._signal.set(self._fn())

    def __repr__(self) -> str:
        return f"Computed({self._signal._name!r}, {self._signal._value!r})"


def computed(fn: Callable[[], Any], *deps: ReadableSignal) -> _ComputedSignal:
    """Create a derived signal that updates when dependencies change.

    If deps are provided, only those trigger recomputation. If no deps
    are provided, dependencies are auto-discovered by running ``fn``
    in a tracking context.

    Call ``.dispose()`` when the computed signal is no longer needed to
    prevent memory leaks from lingering subscriptions.
    """
    return _ComputedSignal(fn, *deps)


def effect(fn: Callable[[], Any], *deps: ReadableSignal) -> Callable[[], None]:
    """Run a side-effect when dependencies change.

    Runs immediately, then re-runs whenever any dep changes.
    Returns a cleanup function that unsubscribes from all deps.

    If no deps are provided, auto-discovers deps by running ``fn``
    in a tracking context.
    """
    cleanups: list[Callable[[], None]] = []

    if deps:
        # Explicit deps — run immediately then subscribe
        fn()
        for dep in deps:
            unsub = dep.subscribe(lambda _: fn())
            cleanups.append(unsub)
    else:
        # Auto-track: run fn in tracking context to discover deps
        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            fn()
        finally:
            _tracking_context.reset(token)
        for dep in tracked:
            unsub = dep.subscribe(lambda _: fn())
            cleanups.append(unsub)

    def cleanup() -> None:
        for unsub in cleanups:
            unsub()
        cleanups.clear()

    return cleanup


def _flush_batch() -> None:
    """Flush all pending signal notifications after outermost batch exits."""
    global _batch_pending
    # Snapshot and clear before notifying — subscribers may call .set()
    # on other signals, which will fire immediately (non-batched).
    pending = _batch_pending
    _batch_pending = set()
    for signal in pending:
        signal._run_subscribers()


class Batch:
    """Defer subscriber notifications until the outermost batch exits.

    Values update immediately so reads within the batch see new state.
    Subscribers fire at most once per signal with the final value.
    Batches can nest — only the outermost flush triggers notifications.

    Usage::

        with Batch():
            name.set("plan")
            color.set("yellow")
            model.set("claude-haiku")
        # all subscribers notified once here
    """

    __slots__ = ()

    def __enter__(self) -> None:
        global _batch_depth
        _batch_depth += 1

    def __exit__(self, *_: Any) -> None:
        global _batch_depth
        if _batch_depth <= 0:
            return
        _batch_depth -= 1
        if _batch_depth == 0:
            _flush_batch()


__all__ = [
    "Signal",
    "ReadableSignal",
    "computed",
    "effect",
    "Batch",
    "_SignalState",
    "_ComputedSignal",
    # Re-exported from expr for backward compat
    "Expr",
    "Literal",
    "BinaryOp",
    "UnaryOp",
    "Conditional",
    "PropertyAccess",
    "MethodCall",
    "Assignment",
    "_ensure_expr",
    "all_",
    "any_",
    "match",
]
