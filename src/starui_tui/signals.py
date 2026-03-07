"""TUI-mode Signal — pure Python reactive state for starui_tui components.

This module provides the reactive primitives for TUI mode. Unlike StarHTML
signals which compile to JavaScript, these operate entirely in Python.
"""

from __future__ import annotations

import itertools
from typing import Any, Callable, Protocol, runtime_checkable


_counter = itertools.count()


@runtime_checkable
class ReadableSignal(Protocol):
    """Protocol for any readable signal (Signal or computed)."""

    def __call__(self) -> Any: ...
    @property
    def name(self) -> str: ...
    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]: ...


class Signal:
    """Reactive state container for TUI mode.

    Same API as StarHTML Signal (set, add, toggle, __call__) but operates
    entirely in Python — no JS compilation or Expr evaluation.
    """

    __slots__ = ("_name", "_value", "_subscribers", "_notifying")

    def __init__(self, name: str, initial: Any = None) -> None:
        self._name = name
        self._value = initial
        self._subscribers: list[Callable[[Any], Any]] = []
        self._notifying: bool = False

    @property
    def name(self) -> str:
        return self._name

    def __call__(self) -> Any:
        """Get current value."""
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
        if self._notifying:
            return  # Prevent reentrant notification
        self._notifying = True
        try:
            for sub in list(self._subscribers):  # Snapshot for safe mutation
                sub(self._value)
        finally:
            self._notifying = False

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
