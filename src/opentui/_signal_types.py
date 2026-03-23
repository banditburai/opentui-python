"""Private core signal types and dependency wiring."""

from __future__ import annotations

import contextlib
import itertools
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from . import _signals_runtime as _rt
from .expr import Expr

_counter = itertools.count()


def _load_native_signal() -> Any:
    try:
        from . import ffi

        nb = ffi.get_native()
    except ImportError:
        nb = None
    if nb is not None:
        try:
            return nb.native_signals.NativeSignal
        except AttributeError:
            return None
    return None


_NativeSignal = _load_native_signal()
_HAS_NATIVE = _NativeSignal is not None


@runtime_checkable
class ReadableSignal(Protocol):
    def __call__(self) -> Any: ...
    @property
    def name(self) -> str: ...
    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]: ...


def _unwrap_val(x):
    return x() if isinstance(x, Expr) else x


class Signal(Expr):
    __slots__ = ("_name", "_value", "_subscribers", "_notifying", "_native")

    def __init__(self, value: Any = None, *, name: str | None = None) -> None:
        self._name = name or f"signal_{next(_counter)}"
        self._value = value
        self._subscribers: list[Callable[[Any], Any]] = []
        self._notifying = False
        self._native = _NativeSignal(self._name, self._value) if _HAS_NATIVE else None

    @property
    def name(self) -> str:
        return self._name

    def __set_name__(self, owner: type, name: str) -> None:
        if self._name.startswith("signal_"):
            self._name = name

    def __call__(self) -> Any:
        tracking = _rt._tracking_context.get()
        if tracking is not None:
            tracking.add(self)
        return self._value

    def evaluate(self) -> Any:
        return self()

    def to_js(self) -> str:
        return self._name

    def peek(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        if self._native is not None and value is not None:
            if _rt._runtime.batch_depth > 0:
                if self._native.set_batched(value):
                    self._value = self._native.get()
                    _rt._signal_state_notified.add(self)
                    _rt._runtime.batch_pending.add(self)
                return
            is_root = _rt._begin_micro_flush()
            try:
                if self._native.set(value):
                    self._value = self._native.get()
                    _rt._signal_state_notified.add(self)
            finally:
                _rt._end_micro_flush(_drain_stale_computeds, is_root)
            return
        if self._value is value or self._value == value:
            return
        self._value = value
        if _rt._runtime.batch_depth > 0:
            _rt._signal_state_notified.add(self)
            _rt._runtime.batch_pending.add(self)
        else:
            self._notify()

    def add(self, delta: Any) -> None:
        if self._native is not None:
            if _rt._runtime.batch_depth > 0:
                if self._native.add_batched(delta):
                    self._value = self._native.get()
                    _rt._signal_state_notified.add(self)
                    _rt._runtime.batch_pending.add(self)
                return
            is_root = _rt._begin_micro_flush()
            try:
                if self._native.add(delta):
                    self._value = self._native.get()
                    _rt._signal_state_notified.add(self)
            finally:
                _rt._end_micro_flush(_drain_stale_computeds, is_root)
            return
        new_value = self._value + delta
        if new_value == self._value:
            return
        self._value = new_value
        self._notify()

    def toggle(self, *values: Any) -> None:
        if values:
            current = self._value
            for i, v in enumerate(values):
                if current == v:
                    self.set(values[(i + 1) % len(values)])
                    return
            self.set(values[0])
            return
        if self._native is not None:
            if _rt._runtime.batch_depth > 0:
                self._native.toggle_batched()
                self._value = self._native.get()
                _rt._signal_state_notified.add(self)
                _rt._runtime.batch_pending.add(self)
                return
            is_root = _rt._begin_micro_flush()
            try:
                self._native.toggle()
                self._value = self._native.get()
                _rt._signal_state_notified.add(self)
            finally:
                _rt._end_micro_flush(_drain_stale_computeds, is_root)
            return
        self._value = not self._value
        self._notify()

    def update(self, fn: Callable[[Any], Any]) -> None:
        self.set(fn(self._value))

    def append(self, item: Any) -> None:
        value = self._value
        if not isinstance(value, list):
            raise TypeError(f"append() requires a list-valued signal, got {type(value).__name__}")
        self.set([*value, item])

    def prepend(self, item: Any) -> None:
        value = self._value
        if not isinstance(value, list):
            raise TypeError(f"prepend() requires a list-valued signal, got {type(value).__name__}")
        self.set([item, *value])

    def remove(self, item: Any) -> bool:
        value = self._value
        if not isinstance(value, list):
            raise TypeError(f"remove() requires a list-valued signal, got {type(value).__name__}")
        try:
            idx = value.index(item)
        except ValueError:
            return False
        self.set([*value[:idx], *value[idx + 1 :]])
        return True

    def remove_where(self, predicate: Callable[[Any], Any]) -> bool:
        value = self._value
        if not isinstance(value, list):
            raise TypeError(
                f"remove_where() requires a list-valued signal, got {type(value).__name__}"
            )
        for i, item in enumerate(value):
            if predicate(item):
                self.set([*value[:i], *value[i + 1 :]])
                return True
        return False

    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]:
        if self._native is not None:
            def wrapped(value: Any) -> None:
                self._value = value
                fn(value)
            return self._native.subscribe(wrapped)

        self._subscribers.append(fn)

        def unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._subscribers.remove(fn)

        return unsubscribe

    def _notify(self) -> None:
        _rt._signal_state_notified.add(self)
        if _rt._runtime.batch_depth > 0:
            _rt._runtime.batch_pending.add(self)
            return
        is_root = _rt._begin_micro_flush()
        try:
            self._run_subscribers()
        finally:
            _rt._end_micro_flush(_drain_stale_computeds, is_root)

    def _run_subscribers(self) -> None:
        if self._native is not None:
            self._native.set_unchecked(self._value)
            self._value = self._native.get()
            return
        if self._notifying:
            return
        self._notifying = True
        try:
            if not self._subscribers:
                return
            for sub in list(self._subscribers):
                sub(self._value)
        finally:
            self._notifying = False

    def __hash__(self):
        return id(self)

    def __repr__(self) -> str:
        return f"Signal({self._name!r}, {self._value!r})"

    def __iadd__(self, other):
        self.add(_unwrap_val(other))
        return self

    def __isub__(self, other):
        self.set(self._value - _unwrap_val(other))
        return self

    def __imul__(self, other):
        self.set(self._value * _unwrap_val(other))
        return self

    def __itruediv__(self, other):
        self.set(self._value / _unwrap_val(other))
        return self

    def __ifloordiv__(self, other):
        self.set(self._value // _unwrap_val(other))
        return self

    def __imod__(self, other):
        self.set(self._value % _unwrap_val(other))
        return self

    def __ipow__(self, other):
        self.set(self._value ** _unwrap_val(other))
        return self

    def map(self, fn: Callable[[Any], Any]) -> _ComputedSignal:
        return _ComputedSignal(lambda: fn(self()), self)

    @property
    def _as_dep(self) -> Signal:
        return self


class _ComputedSignal(Expr):
    __slots__ = (
        "_fn",
        "_signal",
        "_auto_tracked",
        "_tracked_deps",
        "_dep_unsubs",
        "_recompute_cb",
        "_computing",
        "_stale",
        "_depth",
    )

    def __init__(self, fn: Callable[[], Any], *deps: ReadableSignal) -> None:
        self._fn = fn
        self._recompute_cb = self._on_dep_changed
        self._computing = False
        self._stale = False
        self._dep_unsubs: dict[ReadableSignal, Callable[[], None]] = {}

        if deps:
            self._auto_tracked = False
            self._tracked_deps: set[Signal] = set()
            self._depth = max((getattr(d, "_depth", 0) for d in deps), default=0) + 1
            initial = self._eval_untracked(fn)
            resolved_deps = deps
        else:
            self._auto_tracked = True
            tracked: set[Signal] = set()
            token = _rt._tracking_context.set(tracked)
            try:
                initial = fn()
            finally:
                _rt._tracking_context.reset(token)
            self._tracked_deps = set(tracked)
            self._depth = max((getattr(d, "_depth", 0) for d in tracked), default=0) + 1
            resolved_deps = tracked

        self._signal = Signal(initial, name=f"computed_{next(_counter)}")
        for dep in resolved_deps:
            self._dep_unsubs[dep] = dep.subscribe(self._recompute_cb)

    @staticmethod
    def _eval_untracked(fn: Callable[[], Any]) -> Any:
        token = _rt._tracking_context.set(None)
        try:
            return fn()
        finally:
            _rt._tracking_context.reset(token)

    def __call__(self) -> Any:
        if self._stale:
            self._stale = False
            self._recompute()
        return self._signal()

    def evaluate(self) -> Any:
        return self()

    def to_js(self) -> str:
        return self._signal._name

    @property
    def name(self) -> str:
        return self._signal.name

    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]:
        if self._stale:
            self._stale = False
            self._recompute()
        return self._signal.subscribe(fn)

    def dispose(self) -> None:
        for unsub in self._dep_unsubs.values():
            unsub()
        self._dep_unsubs.clear()
        self._tracked_deps = set()

    def _on_dep_changed(self, _: Any) -> None:
        if _rt._runtime.flushing:
            if not self._stale:
                self._stale = True
                _rt._runtime.stale_computeds.append(self)
            return
        native = getattr(self._signal, "_native", None)
        has_listeners = native.total_binding_count > 0 if native else bool(self._signal._subscribers)
        if has_listeners:
            self._recompute()
        else:
            self._stale = True

    def _recompute(self) -> None:
        if self._computing:
            return
        if not self._auto_tracked:
            self._signal.set(self._fn())
            return

        self._computing = True
        try:
            tracked: set[Signal] = set()
            token = _rt._tracking_context.set(tracked)
            try:
                new_value = self._fn()
            finally:
                _rt._tracking_context.reset(token)

            self._stale = False
            self._signal.set(new_value)

            if tracked != self._tracked_deps:
                _sync_tracked_deps(
                    self._tracked_deps, tracked, self._dep_unsubs, self._recompute_cb
                )
                self._tracked_deps = set(tracked)
                self._depth = max((getattr(d, "_depth", 0) for d in tracked), default=0) + 1
        finally:
            self._computing = False

    def __hash__(self):
        return id(self)

    def __repr__(self) -> str:
        return f"Computed({self._signal._name!r}, {self._signal._value!r})"

    def set(self, value: Any) -> None:
        raise AttributeError(f"Cannot set() on computed signal {self._signal._name!r}")

    def add(self, amount: Any) -> None:
        raise AttributeError(f"Cannot add() on computed signal {self._signal._name!r}")

    def toggle(self, *values: Any) -> None:
        raise AttributeError(f"Cannot toggle() on computed signal {self._signal._name!r}")

    def map(self, fn: Callable[[Any], Any]) -> _ComputedSignal:
        return _ComputedSignal(lambda: fn(self()), self._as_dep)

    @property
    def _as_dep(self) -> Signal:
        return self._signal


def _sync_tracked_deps(
    old_deps: set[Signal],
    new_deps: set[Signal],
    unsubs: dict[ReadableSignal, Callable[[], None]],
    callback: Callable[[Any], None],
) -> None:
    for dep in old_deps - new_deps:
        unsub = unsubs.pop(dep, None)
        if unsub:
            unsub()
    for dep in new_deps - old_deps:
        unsubs[dep] = dep.subscribe(callback)


def _drain_stale_computeds() -> None:
    while _rt._runtime.stale_computeds:
        batch, _rt._runtime.stale_computeds = _rt._runtime.stale_computeds, []
        batch.sort(key=_rt._runtime.depth_key)
        for comp in batch:
            if comp._stale:
                comp._stale = False
                comp._recompute()

__all__ = [
    "ReadableSignal",
    "Signal",
    "_ComputedSignal",
    "_HAS_NATIVE",
    "_sync_tracked_deps",
    "_unwrap_val",
]
