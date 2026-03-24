"""Structural control flow - For, Show, Switch.

Fine-grained reactive control flow primitives that subscribe to their
signal dependencies and update their children reactively, without
requiring a full tree rebuild.  Follows Solid.js semantics: each
primitive auto-tracks the signals it reads and re-evaluates only when
those specific signals change.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .. import diagnostics as _diag
from .._signal_types import Signal, _ComputedSignal
from ._control_flow_branching import Show, Switch
from ._control_flow_for import reconcile_for_children as _reconcile_for_children
from ._control_flow_region import apply_region_children as _apply_region_children
from ._control_flow_region import detach_children as _detach_children
from ._control_flow_region import evict_lru_branches as _evict_lru_branches
from ._control_flow_region import normalize_inserted_children as _normalize_inserted_children
from ._control_flow_region import normalize_render_result as _normalize_render_result
from ._control_flow_region import subscribe_signals as _subscribe_signals
from ._control_flow_region import track_signals as _track_signals
from .base import BaseRenderable, Renderable
from .structural import (
    ErrorBoundary,
    Match,
    Portal,
    Suspense,
)
from .template import (
    Mount,
    component,
)

_log = logging.getLogger(__name__)


class Inserted(Renderable):
    """Mounted child expression with a scalar Text fast path.

    This is the closer Python analogue to Solid's child insertion logic:
    scalar expressions update a persistent Text child directly, while
    renderable expressions reconcile mounted children in place.
    """

    __slots__ = (
        "_render_fn",
        "_data_cleanup",
        "_tracked_signals",
        "_updating",
    )

    def __init__(
        self,
        *,
        render: Callable[[], BaseRenderable | list[Any] | tuple[Any, ...] | str | Any | None],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._render_fn = render
        self._data_cleanup: Callable[[], None] | None = None
        self._tracked_signals: frozenset[Signal] = frozenset()
        self._updating = False
        self._setup_reactive_region()

    def _setup_reactive_region(self) -> None:
        tracked, result = _track_signals(self._render_fn)
        mode, payload = _normalize_inserted_children(result)
        self._apply_region(mode, payload)
        self._subscribe_data(tracked)

    def _subscribe_data(self, tracked: set[Signal]) -> None:
        next_tracked = frozenset(tracked)
        if next_tracked == self._tracked_signals:
            return

        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
            self._tracked_signals = frozenset()

        self._data_cleanup = _subscribe_signals(tracked, self._reactive_update)
        self._tracked_signals = next_tracked

    def _apply_region(self, mode: str, payload: str | list[BaseRenderable]) -> None:
        from .text import Text

        if mode == "text":
            content = payload
            if (
                len(self._children) == 1
                and isinstance(self._children[0], Text)
                and self._children[0].key is None
            ):
                self._children[0].content = content
                return
            _apply_region_children(self, [Text(content)])
            return

        if mode == "single_node":
            _apply_region_children(self, [payload])
            return

        _apply_region_children(self, payload)

    def _reactive_update(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            tracked, result = _track_signals(self._render_fn)
            mode, payload = _normalize_inserted_children(result)
            self._apply_region(mode, payload)
            self._subscribe_data(tracked)
            self.mark_dirty()
            # Mark parent dirty so the renderer's local-subtree layout
            # optimization doesn't use stale parent dimensions as constraints.
            # Without this, Yoga runs with the old parent height, producing
            # incorrect child positions on the first layout pass.
            if self._parent is not None:
                self._parent.mark_dirty()
        finally:
            self._updating = False

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
        self._tracked_signals = frozenset()
        super().destroy()


class For(Renderable):
    """Keyed list - only renders genuinely new items, preserves existing.

    Auto-tracks signals read by ``each`` and reactively reconciles
    children when those signals change, without requiring a full tree
    rebuild.  Existing items keep their identity, state, and yoga nodes.

    Usage:
        For(
            log_entry,               # fn(item) -> Renderable
            each=log_entries,        # Signal or callable returning list
            key_fn=lambda e: str(e["id"]),
            key="entry-list",
            flex_grow=1,
        )
    """

    __slots__ = (
        "_each_source",
        "_render_fn",
        "_key_fn",
        "_data_cleanup",
        "_reconciling",
        "_last_items",
    )

    def __init__(
        self,
        render_fn: Callable[[Any], BaseRenderable],
        *,
        each: Signal | _ComputedSignal | Callable[[], Any] | list | tuple,
        key_fn: Callable[[Any], Any] | str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._each_source = each
        self._render_fn = render_fn
        if isinstance(key_fn, str):
            attr = key_fn
            self._key_fn = lambda item, _a=attr: getattr(item, _a, None)
        else:
            self._key_fn = key_fn if key_fn is not None else id
        self._data_cleanup: Callable[[], None] | None = None
        self._reconciling = False
        self._last_items: list[Any] | None = None
        self._setup_reactive_data()

    def _setup_reactive_data(self) -> None:
        source = self._each_source
        tracked, _ = _track_signals(lambda: source() if callable(source) else source)
        self._subscribe_data(tracked)

    def _subscribe_data(self, tracked: set[Signal]) -> None:
        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None

        self._data_cleanup = _subscribe_signals(tracked, self._reactive_reconcile)

    def _reactive_reconcile(self) -> None:
        if self._reconciling:
            return
        self._reconciling = True
        try:
            # Track only the source() call, NOT _reconcile_children().
            # Render functions inside _reconcile_children may read unrelated
            # signals (e.g. theme) that should not be For's data deps.
            source = self._each_source
            tracked, _ = _track_signals(lambda: source() if callable(source) else source)
            self._reconcile_children()
            self._subscribe_data(tracked)
            self.mark_dirty()
        finally:
            self._reconciling = False

    def _reconcile_children(self):
        _reconcile_for_children(self, _diag, _log)

    def _pre_configure_yoga(self) -> None:
        self._reconcile_children()

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
        super().destroy()


class Dynamic(Renderable):
    """Mounted reactive region that reconciles only its own children.

    The render callable is tracked independently from the parent component
    body. Signal changes read inside ``render`` update this region in place
    instead of forcing a full component rebuild.
    """

    __slots__ = (
        "_render_fn",
        "_data_cleanup",
        "_tracked_signals",
        "_updating",
        "_cache_key_fn",
        "_current_cache_key",
        "_branch_cache",
        "_max_cached_branches",
    )

    def __init__(
        self,
        *,
        render: Callable[
            [], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...] | None
        ],
        cache_key: Callable[[], Any] | None = None,
        max_cached_branches: int = 4,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._render_fn = render
        self._data_cleanup: Callable[[], None] | None = None
        self._tracked_signals: frozenset[Signal] = frozenset()
        self._updating = False
        self._cache_key_fn = cache_key
        self._current_cache_key: Any = None
        self._branch_cache: dict[Any, list[BaseRenderable]] = {}
        self._max_cached_branches = max_cached_branches
        self._setup_reactive_region()

    def _setup_reactive_region(self) -> None:
        tracked, result = self._evaluate_region()
        cache_key, mode, payload = result
        self._apply_region(cache_key, mode, payload)
        self._subscribe_data(tracked)

    def _subscribe_data(self, tracked: set[Signal]) -> None:
        next_tracked = frozenset(tracked)
        if next_tracked == self._tracked_signals:
            return

        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
            self._tracked_signals = frozenset()

        self._data_cleanup = _subscribe_signals(tracked, self._reactive_update)
        self._tracked_signals = next_tracked

    def _evaluate_region(self) -> tuple[set[Signal], tuple[Any, str, list[BaseRenderable] | None]]:
        def _eval() -> tuple[Any, str, list[BaseRenderable] | None]:
            cache_key = self._cache_key_fn() if self._cache_key_fn is not None else None
            if (
                self._cache_key_fn is not None
                and cache_key == self._current_cache_key
                and self._children
            ):
                return (cache_key, "current", None)
            if self._cache_key_fn is not None:
                cached = self._branch_cache.pop(cache_key, None)
                if cached is not None:
                    return (cache_key, "cached", cached)
            new_children = _normalize_render_result(self._render_fn())
            return (cache_key, "fresh", new_children)

        return _track_signals(_eval)

    def _stash_current_branch(self) -> None:
        if self._current_cache_key is None or not self._children:
            return
        self._branch_cache[self._current_cache_key] = _detach_children(self)
        _evict_lru_branches(self._branch_cache, self._max_cached_branches)

    def _restore_cached_children(
        self, cache_key: Any, cached_children: list[BaseRenderable]
    ) -> None:
        self._stash_current_branch()
        self._current_cache_key = cache_key
        for child in cached_children:
            self.add(child)
        self.mark_dirty()

    def _apply_children(self, new_children: list[BaseRenderable]) -> None:
        _apply_region_children(self, new_children)

    def _apply_region(
        self,
        cache_key: Any,
        mode: str,
        payload: list[BaseRenderable] | None,
    ) -> None:
        if mode == "current":
            return
        if mode == "cached":
            assert payload is not None
            self._restore_cached_children(cache_key, payload)
            return

        assert payload is not None
        if (
            self._cache_key_fn is not None
            and cache_key != self._current_cache_key
            and self._current_cache_key is not None
        ):
            self._stash_current_branch()
        self._current_cache_key = cache_key
        self._apply_children(payload)

    def _reactive_update(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            tracked, result = self._evaluate_region()
            cache_key, mode, payload = result
            self._apply_region(cache_key, mode, payload)
            self._subscribe_data(tracked)
            self.mark_dirty()
        finally:
            self._updating = False

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
        self._tracked_signals = frozenset()
        for cached in self._branch_cache.values():
            for child in cached:
                if not child._destroyed:
                    child.destroy()
        self._branch_cache.clear()
        super().destroy()


class MemoBlock(Dynamic):
    """Mounted subtree that only re-renders when its invalidation key changes.

    This is the ergonomic layer over ``Dynamic(cache_key=...)`` for subtrees
    whose structure is stable across most updates. Leaf updates inside the
    subtree should use reactive props/signals so the subtree can stay mounted.
    """

    __slots__ = ()

    def __init__(
        self,
        *,
        render: Callable[
            [], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...] | None
        ],
        invalidate_when: Callable[[], Any] | None = None,
        **kwargs,
    ):
        if invalidate_when is None:
            sentinel = object()

            def invalidate_when() -> object:
                return sentinel

        super().__init__(
            render=render,
            cache_key=invalidate_when,
            **kwargs,
        )


class Lazy(Renderable):
    """Deferred child creation — builds children only when first rendered.

    Use inside Show/Switch when child construction is expensive and
    should be deferred until the branch is actually active.

    Replaces the old Show(build=lambda: ...) pattern:
        Show(Lazy(lambda: expensive_tree()), when=cond)
    """

    __slots__ = ("_build_fn", "_built")

    def __init__(self, build_fn, **kwargs):
        super().__init__(**kwargs)
        self._build_fn = build_fn
        self._built = False

    def _pre_configure_yoga(self):
        if not self._built:
            self._built = True
            for child in _normalize_render_result(self._build_fn()):
                self.add(child)
        super()._pre_configure_yoga()


__all__ = [
    "Dynamic",
    "ErrorBoundary",
    "For",
    "Lazy",
    "Match",
    "MemoBlock",
    "Mount",
    "Portal",
    "Show",
    "Suspense",
    "Switch",
    "component",
]
