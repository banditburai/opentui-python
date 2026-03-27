import contextlib
from collections.abc import Callable
from typing import Any

from . import _signals_runtime as _rt
from ._signal_types import ReadableSignal, Signal, _ComputedSignal, _sync_tracked_deps
from .expr import Expr


def is_reactive(value: object) -> bool:
    return isinstance(value, (Signal, _ComputedSignal)) or (
        callable(value) and not isinstance(value, str | type)
    )


def val(s: Any) -> Any:
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
            _rt._runtime.owner_stack.append(effect_cleanups)
            try:
                fn()
            finally:
                _rt._runtime.owner_stack.pop()

        _rt._runtime.owner_stack.append(effect_cleanups)
        try:
            fn()
        finally:
            _rt._runtime.owner_stack.pop()
        for dep in deps:
            unsub_fns.append(dep.subscribe(_rerun))
    else:
        dep_unsubs: dict[Signal, Callable[[], None]] = {}
        tracked_deps: set[Signal] = set()

        def _run(_: Any = None) -> None:
            nonlocal tracked_deps
            _flush_cleanups()
            _rt._runtime.owner_stack.append(effect_cleanups)
            try:
                tracked: set[Signal] = set()
                token = _rt._tracking_context.set(tracked)
                try:
                    fn()
                finally:
                    _rt._tracking_context.reset(token)
            finally:
                _rt._runtime.owner_stack.pop()

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
    if _rt._runtime.owner_stack:
        _rt._runtime.owner_stack[-1].append(fn)


def create_root(fn: Callable[[Callable[[], None]], Any]) -> Any:
    root_cleanups: list[Callable[[], Any]] = []

    def dispose() -> None:
        for cb in reversed(root_cleanups):
            with contextlib.suppress(Exception):
                cb()
        root_cleanups.clear()

    _rt._runtime.owner_stack.append(root_cleanups)
    try:
        return fn(dispose)
    finally:
        _rt._runtime.owner_stack.pop()


def untrack(fn: Callable[[], Any]) -> Any:
    token = _rt._tracking_context.set(None)
    try:
        return fn()
    finally:
        _rt._tracking_context.reset(token)


def _drain_stale_computeds() -> None:
    from ._signal_types import _drain_stale_computeds as _drain

    _drain()


def _flush_batch() -> None:
    _rt._runtime.flushing = True
    try:
        pending = _rt._runtime.batch_pending
        _rt._runtime.batch_pending = set()
        for signal in pending:
            signal._run_subscribers()

        _drain_stale_computeds()
    finally:
        _rt._runtime.flushing = False


Batch = _rt.Batch


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
]
