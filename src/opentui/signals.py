"""Signal system — consolidated reactive state for OpenTUI.

Combines startui's clean mutation API (set/add/toggle, subscriber pattern,
reentrancy guard) with opentui's _SignalState renderer integration so that
signal changes trigger re-renders.
"""

from __future__ import annotations

import itertools
import threading
from typing import Any, Callable, Protocol, runtime_checkable

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
        self._notified: set[Signal] = set()
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> _SignalState:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, signal: Signal) -> None:
        with self._lock:
            if not any(s is signal for s in self._signals):
                self._signals.append(signal)

    def mark_notified(self, signal: Signal) -> None:
        self._notified.add(signal)

    def has_changes(self) -> bool:
        return len(self._notified) > 0

    def reset(self) -> None:
        self._signals.clear()
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
        """Get current value."""
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
            try:
                self._subscribers.remove(fn)
            except ValueError:
                pass

        return unsubscribe

    def _notify(self) -> None:
        """Notify _SignalState and subscribers."""
        _SignalState.get_instance().mark_notified(self)
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

    Use ``computed(fn, *deps)`` to create. Dependencies must be listed
    explicitly — any signal read inside ``fn`` but not in ``deps`` will
    NOT trigger recomputation.
    """

    __slots__ = ("_fn", "_signal", "_cleanups")

    def __init__(self, fn: Callable[[], Any], *deps: ReadableSignal) -> None:
        self._fn = fn
        self._signal = Signal(f"computed_{next(_counter)}", fn())
        self._cleanups: list[Callable[[], None]] = []
        for dep in deps:
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

    Dependencies must be listed explicitly. Any signal read inside ``fn``
    but not passed as a ``dep`` will NOT trigger recomputation.

    Call ``.dispose()`` when the computed signal is no longer needed to
    prevent memory leaks from lingering subscriptions.
    """
    return _ComputedSignal(fn, *deps)


def effect(fn: Callable[[], Any], *deps: ReadableSignal) -> Callable[[], None]:
    """Run a side-effect when dependencies change.

    Runs immediately, then re-runs whenever any dep changes.
    Returns a cleanup function that unsubscribes from all deps.

    If no deps are provided, runs once and the cleanup is a no-op.
    """
    cleanups: list[Callable[[], None]] = []
    # Run immediately BEFORE subscribing to avoid reentrant triggers
    fn()
    for dep in deps:
        unsub = dep.subscribe(lambda _: fn())
        cleanups.append(unsub)

    def cleanup() -> None:
        for unsub in cleanups:
            unsub()
        cleanups.clear()

    return cleanup


__all__ = [
    "Signal",
    "ReadableSignal",
    "computed",
    "effect",
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
