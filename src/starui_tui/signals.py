"""TUI-mode Signal — pure Python reactive state (no JS compilation)."""

from __future__ import annotations

from typing import Any, Callable


class Signal:
    """Reactive state container for TUI mode.

    Same API as StarHTML Signal (set, add, toggle, __call__) but operates
    entirely in Python — no JS compilation or Expr evaluation.
    """

    __slots__ = ("_name", "_value", "_subscribers")

    def __init__(self, name: str, initial: Any = None) -> None:
        self._name = name
        self._value = initial
        self._subscribers: list[Callable[[Any], Any]] = []

    @property
    def name(self) -> str:
        return self._name

    def __call__(self) -> Any:
        """Get current value."""
        return self._value

    def set(self, value: Any) -> None:
        """Set value and notify subscribers."""
        self._value = value
        self._notify()

    def add(self, delta: Any) -> None:
        """Add delta to current value and notify."""
        self._value += delta
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
        for sub in self._subscribers:
            sub(self._value)

    def __repr__(self) -> str:
        return f"Signal({self._name!r}, {self._value!r})"


class _ComputedSignal:
    """Read-only derived signal that updates when dependencies change."""

    __slots__ = ("_fn", "_signal", "_cleanups")

    def __init__(self, fn: Callable[[], Any], *deps: Signal) -> None:
        self._fn = fn
        self._signal = Signal(f"computed_{id(fn)}", fn())
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

    def _recompute(self) -> None:
        self._signal.set(self._fn())


def computed(fn: Callable[[], Any], *deps: Signal) -> _ComputedSignal:
    """Create a derived signal that updates when dependencies change."""
    return _ComputedSignal(fn, *deps)


def effect(fn: Callable[[], Any], *deps: Signal) -> Callable[[], None]:
    """Run a side-effect when dependencies change.

    Runs immediately, then re-runs whenever any dep changes.
    Returns a cleanup function that unsubscribes from all deps.
    """
    cleanups: list[Callable[[], None]] = []
    for dep in deps:
        unsub = dep.subscribe(lambda _: fn())
        cleanups.append(unsub)
    fn()  # Run immediately

    def cleanup() -> None:
        for unsub in cleanups:
            unsub()

    return cleanup
