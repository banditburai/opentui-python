from __future__ import annotations

import contextlib
import contextvars
import itertools
from collections.abc import Callable
from operator import attrgetter
from typing import Any, Protocol, runtime_checkable

from .expr import Conditional, Expr, _ensure_expr

_counter = itertools.count()

_tracking_context: contextvars.ContextVar[set[Signal] | None] = contextvars.ContextVar(
    "_tracking_context", default=None
)

# Must load via FFI layer — bare `import opentui_bindings` finds the source
# directory as a namespace package and fails.
_HAS_NATIVE = False
_NativeSignal: Any = None


def _try_load_native_signal() -> None:
    global _HAS_NATIVE, _NativeSignal
    try:
        from . import ffi

        nb = ffi.get_native()
    except ImportError:
        nb = None
    if nb is not None:
        try:
            _NativeSignal = nb.native_signals.NativeSignal
            _HAS_NATIVE = True
        except AttributeError:
            pass


_try_load_native_signal()

_batch_depth: int = 0
_batch_pending: set[Signal] = set()
_flushing: bool = False
_stale_computeds: list[_ComputedSignal] = []  # type: ignore[name-defined]  # forward ref
_depth_key = attrgetter("_depth")
_owner_stack: list[list[Callable[[], Any]]] = []


@runtime_checkable
class ReadableSignal(Protocol):
    """Protocol for any readable signal (Signal or computed)."""

    def __call__(self) -> Any: ...
    @property
    def name(self) -> str: ...
    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]: ...


class _SignalState:
    _instance = None

    def __init__(self):
        self._notified: set[Signal] = set()

    @classmethod
    def get_instance(cls) -> _SignalState:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def has_changes(self) -> bool:
        return bool(self._notified)

    def reset(self) -> None:
        self._notified.clear()


_signal_state: _SignalState = _SignalState.get_instance()
_signal_state_notified: set[Signal] = _signal_state._notified


def _unwrap_val(x):
    """Unwrap reactive values (Expr subclasses, callables) to plain values."""
    return x() if isinstance(x, Expr) else x


class Signal(Expr):
    __slots__ = ("_name", "_value", "_subscribers", "_notifying", "_native")

    def __init__(self, value: Any = None, *, name: str | None = None) -> None:
        self._name = name or f"signal_{next(_counter)}"
        self._value = value
        self._subscribers: list[Callable[[Any], Any]] = []
        self._notifying: bool = False

        if _HAS_NATIVE:
            self._native: Any = _NativeSignal(self._name, self._value)
        else:
            self._native = None

    @property
    def name(self) -> str:
        return self._name

    def __set_name__(self, owner: type, name: str) -> None:
        if self._name.startswith("signal_"):
            self._name = name

    def __call__(self) -> Any:
        tracking = _tracking_context.get()
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
        global _flushing
        if self._native is not None and value is not None:
            if _batch_depth > 0:
                if self._native.set_batched(value):
                    self._value = self._native.get()
                    _signal_state_notified.add(self)
                    _batch_pending.add(self)
                return
            # Micro-flush: native set() fires callbacks synchronously,
            # so we enable flushing to defer diamond-dep computeds.
            is_root = not _flushing
            if is_root:
                _flushing = True
            try:
                if self._native.set(value):
                    self._value = self._native.get()
                    _signal_state_notified.add(self)
                if is_root:
                    _drain_stale_computeds()
            finally:
                if is_root:
                    _flushing = False
            return
        if self._value is value or self._value == value:
            return
        self._value = value
        if _batch_depth > 0:
            _signal_state_notified.add(self)
            _batch_pending.add(self)
        else:
            self._notify()

    def add(self, delta: Any) -> None:
        global _flushing
        if self._native is not None:
            if _batch_depth > 0:
                if self._native.add_batched(delta):
                    self._value = self._native.get()
                    _signal_state_notified.add(self)
                    _batch_pending.add(self)
                return
            is_root = not _flushing
            if is_root:
                _flushing = True
            try:
                if self._native.add(delta):
                    self._value = self._native.get()
                    _signal_state_notified.add(self)
                if is_root:
                    _drain_stale_computeds()
            finally:
                if is_root:
                    _flushing = False
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
        global _flushing
        if self._native is not None:
            if _batch_depth > 0:
                self._native.toggle_batched()
                self._value = self._native.get()
                _signal_state_notified.add(self)
                _batch_pending.add(self)
                return
            is_root = not _flushing
            if is_root:
                _flushing = True
            try:
                self._native.toggle()
                self._value = self._native.get()
                _signal_state_notified.add(self)
                if is_root:
                    _drain_stale_computeds()
            finally:
                if is_root:
                    _flushing = False
            return
        self._value = not self._value
        self._notify()

    def update(self, fn: Callable[[Any], Any]) -> None:
        """Apply transform: signal.set(fn(signal.peek()))."""
        self.set(fn(self._value))

    def append(self, item: Any) -> None:
        """Append item to list signal. Raises TypeError if value is not a list."""
        v = self._value
        if not isinstance(v, list):
            raise TypeError(f"append() requires a list-valued signal, got {type(v).__name__}")
        self.set([*v, item])

    def prepend(self, item: Any) -> None:
        """Prepend item to list signal. Raises TypeError if value is not a list."""
        v = self._value
        if not isinstance(v, list):
            raise TypeError(f"prepend() requires a list-valued signal, got {type(v).__name__}")
        self.set([item, *v])

    def remove(self, item: Any) -> bool:
        """Remove first occurrence of item by equality. Returns True if removed."""
        v = self._value
        if not isinstance(v, list):
            raise TypeError(f"remove() requires a list-valued signal, got {type(v).__name__}")
        try:
            idx = v.index(item)
        except ValueError:
            return False
        self.set([*v[:idx], *v[idx + 1 :]])
        return True

    def remove_where(self, predicate: Callable[[Any], Any]) -> bool:
        """Remove first item where predicate returns truthy. Returns True if removed."""
        v = self._value
        if not isinstance(v, list):
            raise TypeError(f"remove_where() requires a list-valued signal, got {type(v).__name__}")
        for i, item in enumerate(v):
            if predicate(item):
                self.set([*v[:i], *v[i + 1 :]])
                return True
        return False

    def subscribe(self, fn: Callable[[Any], Any]) -> Callable[[], None]:
        if self._native is not None:

            def wrapped(value: Any) -> None:
                # Keep Python-side cache coherent before callbacks fire
                self._value = value
                fn(value)

            return self._native.subscribe(wrapped)

        self._subscribers.append(fn)

        def unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._subscribers.remove(fn)

        return unsubscribe

    def _notify(self) -> None:
        global _flushing
        _signal_state_notified.add(self)
        if _batch_depth > 0:
            _batch_pending.add(self)
            return
        # Wrap in micro-flush so computed diamonds are resolved in depth order.
        is_root = not _flushing
        if is_root:
            _flushing = True
        try:
            self._run_subscribers()
            if is_root:
                _drain_stale_computeds()
        finally:
            if is_root:
                _flushing = False

    def _run_subscribers(self) -> None:
        if self._native is not None:
            self._native.set_unchecked(self._value)
            self._value = self._native.get()
            return
        if self._notifying:
            return
        self._notifying = True
        try:
            subs = self._subscribers
            if not subs:
                return
            for sub in list(subs):
                sub(self._value)
        finally:
            self._notifying = False

    def __hash__(self):
        return id(self)

    def __repr__(self) -> str:
        return f"Signal({self._name!r}, {self._value!r})"

    # --- Eager evaluation (Signal-only, NOT inherited from Expr) ---

    def __int__(self) -> int:
        return int(self())

    def __float__(self) -> float:
        return float(self())

    def __len__(self) -> int:
        return len(self())

    def __contains__(self, item) -> bool:
        return item in self()

    def __iter__(self):
        return iter(self())

    def __getitem__(self, key):
        return self()[key]

    # --- In-place operators (mutate signal value) ---

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

    # --- .if_() override: unwraps signal/expr values in branches ---

    def if_(self, true_val, false_val=None):
        s = self
        return Conditional(s, _ensure_expr(true_val), _ensure_expr(false_val))

    # --- .map() override: returns subscribable _ComputedSignal ---

    def map(self, fn: Callable[[Any], Any]) -> _ComputedSignal:
        """Apply *fn* to this signal's value, returning a subscribable _ComputedSignal.

        Unlike ``Expr.map()`` (which returns a non-subscribable ``MappedExpr``),
        this returns a ``_ComputedSignal`` that tracks this signal as a dependency
        and triggers reactive updates when the source changes.
        """
        return _ComputedSignal(lambda: fn(self()), self)

    @property
    def _as_dep(self) -> Signal:
        """Return the underlying Signal for use as a _ComputedSignal dependency."""
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
        self._recompute_cb: Callable[[Any], None] = self._on_dep_changed
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
            token = _tracking_context.set(tracked)
            try:
                initial = fn()
            finally:
                _tracking_context.reset(token)
            self._tracked_deps = set(tracked)
            self._depth = max((getattr(d, "_depth", 0) for d in tracked), default=0) + 1
            resolved_deps = tracked

        self._signal = Signal(initial, name=f"computed_{next(_counter)}")
        for dep in resolved_deps:
            self._dep_unsubs[dep] = dep.subscribe(self._recompute_cb)

    @staticmethod
    def _eval_untracked(fn: Callable[[], Any]) -> Any:
        token = _tracking_context.set(None)
        try:
            return fn()
        finally:
            _tracking_context.reset(token)

    def __call__(self) -> Any:
        if self._stale:
            self._stale = False  # Clear BEFORE recompute to prevent reentrant loop
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
        if _flushing:
            if not self._stale:
                self._stale = True
                _stale_computeds.append(self)
            return
        native = getattr(self._signal, "_native", None)
        has_listeners = (
            native.total_binding_count > 0 if native else bool(self._signal._subscribers)
        )
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
            token = _tracking_context.set(tracked)
            try:
                new_value = self._fn()
            finally:
                _tracking_context.reset(token)

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

    # --- Eager evaluation (Signal-only, NOT inherited from Expr) ---

    def __int__(self) -> int:
        return int(self())

    def __float__(self) -> float:
        return float(self())

    def __len__(self) -> int:
        return len(self())

    def __contains__(self, item) -> bool:
        return item in self()

    def __iter__(self):
        return iter(self())

    def __getitem__(self, key):
        return self()[key]

    # --- Mutation overrides: fail fast (computed is read-only) ---

    def set(self, value: Any) -> None:
        raise AttributeError(f"Cannot set() on computed signal {self._signal._name!r}")

    def add(self, amount: Any) -> None:
        raise AttributeError(f"Cannot add() on computed signal {self._signal._name!r}")

    def toggle(self, *values: Any) -> None:
        raise AttributeError(f"Cannot toggle() on computed signal {self._signal._name!r}")

    # --- .if_() override: same as Signal ---

    def if_(self, true_val, false_val=None):
        s = self
        return Conditional(s, _ensure_expr(true_val), _ensure_expr(false_val))

    # --- .map() override: returns subscribable _ComputedSignal ---

    def map(self, fn: Callable[[Any], Any]) -> _ComputedSignal:
        """Apply *fn* to this computed signal's value, returning a subscribable _ComputedSignal.

        Unlike ``Expr.map()`` (which returns a non-subscribable ``MappedExpr``),
        this returns a ``_ComputedSignal`` that tracks the underlying signal as a
        dependency and triggers reactive updates when the source changes.
        """
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
    """Reconcile dependency subscriptions after re-tracking.

    Callers should guard with ``if new_deps != old_deps`` before calling.
    """
    for dep in old_deps - new_deps:
        unsub = unsubs.pop(dep, None)
        if unsub:
            unsub()
    for dep in new_deps - old_deps:
        unsubs[dep] = dep.subscribe(callback)


def is_reactive(value: object) -> bool:
    """Check if value is a Signal, ComputedSignal, or callable (excluding str/type)."""
    return isinstance(value, (Signal, _ComputedSignal)) or (
        callable(value) and not isinstance(value, str | type)
    )


def val(s: Any) -> Any:
    """Unwrap a Signal/computed/Expr/callable to its current value.

    Returns plain values unchanged. Uses peek semantics (no tracking) for Signal
    and _ComputedSignal.
    """
    if isinstance(s, Signal):
        return s._value
    if isinstance(s, _ComputedSignal):
        if s._stale:
            s._recompute()
        return s._signal._value
    if isinstance(s, Expr):
        return s()
    if callable(s) and not isinstance(s, str | type):
        return s()
    return s


def computed(fn: Callable[[], Any], *deps: ReadableSignal) -> _ComputedSignal:
    return _ComputedSignal(fn, *deps)


def effect(fn: Callable[[], Any], *deps: ReadableSignal) -> Callable[[], None]:
    """Run a side-effect when dependencies change. Returns a dispose function.

    Supports ``on_cleanup(fn)`` inside the effect body: cleanup functions
    fire before each re-execution and on final disposal.
    """
    effect_cleanups: list[Callable[[], Any]] = []
    unsub_fns: list[Callable[[], None]] = []

    def _flush_cleanups() -> None:
        if effect_cleanups:
            for cb in effect_cleanups:
                with contextlib.suppress(Exception):
                    cb()
            effect_cleanups.clear()

    if deps:

        def _rerun(_: Any) -> None:
            _flush_cleanups()
            _owner_stack.append(effect_cleanups)
            try:
                fn()
            finally:
                _owner_stack.pop()

        _owner_stack.append(effect_cleanups)
        try:
            fn()
        finally:
            _owner_stack.pop()
        for dep in deps:
            unsub_fns.append(dep.subscribe(_rerun))
    else:
        dep_unsubs: dict[Signal, Callable[[], None]] = {}
        tracked_deps: set[Signal] = set()

        def _run(_: Any = None) -> None:
            nonlocal tracked_deps
            _flush_cleanups()
            _owner_stack.append(effect_cleanups)
            try:
                tracked: set[Signal] = set()
                token = _tracking_context.set(tracked)
                try:
                    fn()
                finally:
                    _tracking_context.reset(token)
            finally:
                _owner_stack.pop()

            if tracked != tracked_deps:
                _sync_tracked_deps(tracked_deps, tracked, dep_unsubs, _run)
                tracked_deps = set(tracked)

        _run()

    if deps:

        def dispose() -> None:
            _flush_cleanups()
            for unsub in unsub_fns:
                unsub()
            unsub_fns.clear()
    else:

        def dispose() -> None:
            _flush_cleanups()
            for unsub in dep_unsubs.values():
                unsub()
            dep_unsubs.clear()

    return dispose


def on_cleanup(fn: Callable[[], Any]) -> None:
    if _owner_stack:
        _owner_stack[-1].append(fn)


def create_root(fn: Callable[[Callable[[], None]], Any]) -> Any:
    root_cleanups: list[Callable[[], Any]] = []

    def dispose() -> None:
        for cb in reversed(root_cleanups):
            with contextlib.suppress(Exception):
                cb()
        root_cleanups.clear()

    _owner_stack.append(root_cleanups)
    try:
        return fn(dispose)
    finally:
        _owner_stack.pop()


def untrack(fn: Callable[[], Any]) -> Any:
    token = _tracking_context.set(None)
    try:
        return fn()
    finally:
        _tracking_context.reset(token)


def _drain_stale_computeds() -> None:
    """Process stale computeds in topological (depth) order."""
    global _stale_computeds
    while _stale_computeds:
        batch, _stale_computeds = _stale_computeds, []
        batch.sort(key=_depth_key)
        for comp in batch:
            if comp._stale:
                comp._stale = False
                comp._recompute()


def _flush_batch() -> None:
    """Two-phase flush: base signals first, then stale computeds in depth order."""
    global _batch_pending, _flushing
    _flushing = True
    try:
        pending = _batch_pending
        _batch_pending = set()
        for signal in pending:
            signal._run_subscribers()

        _drain_stale_computeds()
    finally:
        _flushing = False


class Batch:
    """Defer notifications until outermost batch exits. Batches nest."""

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
    "is_reactive",
    "val",
    "computed",
    "create_root",
    "effect",
    "on_cleanup",
    "untrack",
    "Batch",
    "_SignalState",
    "_signal_state",
    "_ComputedSignal",
]
