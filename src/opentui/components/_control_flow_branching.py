from collections.abc import Callable
from typing import Any

from .. import diagnostics as _diag
from .. import layout as yoga_layout
from .._signal_types import Signal, _ComputedSignal
from ..renderer.buffer import Buffer
from ._control_flow_region import detach_children as _detach_children
from ._control_flow_region import evict_lru_branches as _evict_lru_branches
from ._control_flow_region import normalize_render_result as _normalize_render_result
from ._control_flow_region import (
    split_cacheable_branch_children as _split_cacheable_branch_children,
)
from ._control_flow_region import subscribe_signals as _subscribe_signals
from ._control_flow_region import track_signals as _track_signals
from .base import BaseRenderable, Renderable
from .structural import Match, _subtree_contains_portal

_BRANCH_NONE = "none"
_BRANCH_RENDER = "render"
_BRANCH_FALLBACK = "fallback"


class Show(Renderable):
    __slots__ = (
        "_when",
        "_render_fn",
        "_fallback_fn",
        "_current_branch",
        "_render_cache",
        "_fallback_cache",
        "_is_active",
        "_condition_cleanup",
        "_updating",
    )

    def __init__(
        self,
        *children: BaseRenderable,
        when: Signal | _ComputedSignal | Callable[[], Any],
        render: Callable[[], BaseRenderable | list[BaseRenderable]] | None = None,
        fallback: BaseRenderable
        | Callable[[], BaseRenderable | list[BaseRenderable]]
        | None = None,
        **kwargs,
    ):
        has_children = bool(children)
        has_render = render is not None
        if has_children and has_render:
            raise ValueError("Show accepts positional children OR render=, not both")
        if not has_children and not has_render:
            raise ValueError("Show requires children or render=")

        super().__init__(**kwargs)
        self._when = when
        self._is_active = False
        self._condition_cleanup: Callable[[], None] | None = None
        self._updating = False

        if has_children:
            for child in children:
                if isinstance(child, BaseRenderable) and _subtree_contains_portal(child):
                    raise ValueError(
                        "Show does not support Portal as a positional child "
                        "(Portals are destroyed on hide and cannot be cached). "
                        "Use render=lambda: Portal(...) instead."
                    )
            prepared_children = list(children)
            self._render_fn = lambda: prepared_children
        else:
            self._render_fn = render  # type: ignore[assignment]

        if isinstance(fallback, BaseRenderable):
            fallback_node = fallback
            self._fallback_fn = lambda: fallback_node
        else:
            self._fallback_fn = fallback

        self._current_branch: str = _BRANCH_NONE
        self._render_cache: list[BaseRenderable] | None = None
        self._fallback_cache: list[BaseRenderable] | None = None
        self._setup_reactive_condition()

    def _setup_reactive_condition(self) -> None:
        when = self._when
        if isinstance(when, Signal | _ComputedSignal):
            condition = when.peek() if isinstance(when, Signal) else when()
            self._apply_condition(condition)
            self._subscribe_condition({when})  # type: ignore[arg-type]
            return
        tracked, condition = _track_signals(when)
        self._apply_condition(condition)
        self._subscribe_condition(tracked)

    def _apply_condition(self, condition: Any) -> None:
        active = bool(condition)
        new_branch = (
            _BRANCH_RENDER
            if active
            else (_BRANCH_FALLBACK if self._fallback_fn is not None else _BRANCH_NONE)
        )
        if new_branch == self._current_branch:
            return

        if _diag._enabled & _diag.VISIBILITY:
            cache = self._render_cache if new_branch == _BRANCH_RENDER else self._fallback_cache
            _diag.log_show_branch(self, active, self._current_branch, new_branch, cache is not None)

        disposed_children: list[BaseRenderable] = []
        if self._children:
            reusable, disposed_children = _split_cacheable_branch_children(list(self._children))
            if self._current_branch == _BRANCH_RENDER:
                self._render_cache = reusable or None
            elif self._current_branch == _BRANCH_FALLBACK:
                self._fallback_cache = reusable or None
        _detach_children(self)
        for child in disposed_children:
            child.destroy()

        self._current_branch = new_branch
        self._is_active = new_branch != _BRANCH_NONE

        cache = self._render_cache if new_branch == _BRANCH_RENDER else self._fallback_cache
        if cache is not None:
            if new_branch == _BRANCH_RENDER:
                self._render_cache = None
            else:
                self._fallback_cache = None
            for child in cache:
                self.add(child)
            return

        if new_branch == _BRANCH_RENDER:
            render_fn = self._render_fn
        elif new_branch == _BRANCH_FALLBACK and self._fallback_fn is not None:
            render_fn = self._fallback_fn
        else:
            return
        for child in _normalize_render_result(render_fn()):
            self.add(child)

    def _reactive_update(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            when = self._when
            if isinstance(when, Signal | _ComputedSignal):
                condition = when.peek() if isinstance(when, Signal) else when()
                self._apply_condition(condition)
            else:
                tracked, condition = _track_signals(when)
                self._apply_condition(condition)
                self._subscribe_condition(tracked)
            self.mark_dirty()
        finally:
            self._updating = False

    def _subscribe_condition(self, tracked: set[Signal]) -> None:
        if self._condition_cleanup:
            self._condition_cleanup()
            self._condition_cleanup = None
        self._condition_cleanup = _subscribe_signals(tracked, self._reactive_update)

    def _post_configure_yoga(self, node: Any) -> None:
        if not self._is_active:
            if self._flex_grow:
                yoga_layout.configure_node(node, flex_grow=0)
        elif self._flex_grow:
            yoga_layout.configure_node(node, flex_grow=self._flex_grow)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._is_active:
            return
        for child in self._children:
            child.render(buffer, delta_time)

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._condition_cleanup:
            self._condition_cleanup()
            self._condition_cleanup = None
        for cache in (self._render_cache, self._fallback_cache):
            if cache is not None:
                for child in cache:
                    if not child._destroyed:
                        child.destroy()
        self._render_cache = None
        self._fallback_cache = None
        super().destroy()


class Switch(Renderable):
    __slots__ = (
        "_matches",
        "_on_fn",
        "_cases",
        "_fallback_fn",
        "_current_branch_key",
        "_branch_cache",
        "_max_cached_branches",
        "_is_active",
        "_condition_cleanup",
        "_updating",
    )

    def __init__(
        self,
        *matches: Match,
        on: Signal | _ComputedSignal | Callable[[], Any] | None = None,
        cases: dict[Any, BaseRenderable | list | tuple | Callable] | None = None,
        fallback: BaseRenderable
        | Callable[[], BaseRenderable | list[BaseRenderable]]
        | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._matches = matches
        self._on_fn = on
        self._is_active = False
        self._condition_cleanup: Callable[[], None] | None = None
        self._updating = False
        self._current_branch_key: tuple[Any, ...] = (_BRANCH_NONE,)
        self._branch_cache: dict[tuple[Any, ...], list[BaseRenderable]] = {}
        self._max_cached_branches = 4

        if isinstance(fallback, BaseRenderable):
            fallback_node = fallback
            self._fallback_fn = lambda: fallback_node
        else:
            self._fallback_fn = fallback

        if cases is not None:
            self._cases = {}
            for key, value in cases.items():
                if isinstance(value, BaseRenderable):
                    node = value

                    def _singleton_factory(_node=node, _key=key):
                        if _node._destroyed:
                            raise RuntimeError(
                                f"Switch case {_key!r}: node was destroyed by LRU cache eviction. "
                                "Use a callable factory (e.g. cases={{key: lambda: Text(...)}}) "
                                "for branches that may be evicted and re-created."
                            )
                        return _node

                    self._cases[key] = _singleton_factory
                elif isinstance(value, list | tuple):
                    nodes = list(value)
                    self._cases[key] = lambda _nodes=nodes: _nodes
                else:
                    self._cases[key] = value
        else:
            self._cases = {}

        self._setup_reactive_condition()

    def _setup_reactive_condition(self) -> None:
        on = self._on_fn
        if on is not None and isinstance(on, Signal | _ComputedSignal):
            render_fn, branch_key = self._resolve_branch_peek(on)
            self._apply_branch(render_fn, branch_key)
            self._subscribe_condition({on})  # type: ignore[arg-type]
            return
        tracked, (render_fn, branch_key) = _track_signals(self._resolve_branch)
        self._apply_branch(render_fn, branch_key)
        self._subscribe_condition(tracked)

    def _resolve_branch_peek(
        self, on: Signal | _ComputedSignal
    ) -> tuple[Callable | None, tuple[Any, ...]]:
        value = on.peek() if isinstance(on, Signal) else on()
        render_fn = self._cases.get(value)
        if render_fn is not None:
            return render_fn, ("value", value)
        if self._fallback_fn is not None:
            return self._fallback_fn, (_BRANCH_FALLBACK,)
        return None, (_BRANCH_NONE,)

    def _resolve_branch(self) -> tuple[Callable | None, tuple[Any, ...]]:
        if self._on_fn is not None:
            value = self._on_fn()
            render_fn = self._cases.get(value)
            if render_fn is not None:
                return render_fn, ("value", value)
        else:
            for idx, match in enumerate(self._matches):
                if match.when():
                    return match.render, ("match", idx)

        if self._fallback_fn is not None:
            return self._fallback_fn, (_BRANCH_FALLBACK,)

        return None, (_BRANCH_NONE,)

    def _apply_branch(self, render_fn: Callable | None, branch_key: tuple[Any, ...]) -> None:
        if branch_key == self._current_branch_key:
            return

        if _diag._enabled & _diag.VISIBILITY:
            cached = branch_key in self._branch_cache
            _diag.log_switch_branch(self, branch_key, self._current_branch_key, cached)

        disposed_children: list[BaseRenderable] = []
        if self._children and self._current_branch_key != (_BRANCH_NONE,):
            reusable, disposed_children = _split_cacheable_branch_children(list(self._children))
            if reusable:
                self._branch_cache[self._current_branch_key] = reusable
                _evict_lru_branches(self._branch_cache, self._max_cached_branches)
        _detach_children(self)
        for child in disposed_children:
            child.destroy()

        self._current_branch_key = branch_key
        self._is_active = render_fn is not None

        if render_fn is None:
            return

        cached = self._branch_cache.pop(branch_key, None)
        if cached is not None:
            for child in cached:
                self.add(child)
            return

        for child in _normalize_render_result(render_fn()):
            self.add(child)

    def _reactive_update(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            on = self._on_fn
            if on is not None and isinstance(on, Signal | _ComputedSignal):
                render_fn, branch_key = self._resolve_branch_peek(on)
                self._apply_branch(render_fn, branch_key)
            else:
                tracked, (render_fn, branch_key) = _track_signals(self._resolve_branch)
                self._apply_branch(render_fn, branch_key)
                self._subscribe_condition(tracked)
            self.mark_dirty()
        finally:
            self._updating = False

    def _subscribe_condition(self, tracked: set[Signal]) -> None:
        if self._condition_cleanup:
            self._condition_cleanup()
            self._condition_cleanup = None
        self._condition_cleanup = _subscribe_signals(tracked, self._reactive_update)

    def _post_configure_yoga(self, node: Any) -> None:
        if not self._is_active:
            if self._flex_grow:
                yoga_layout.configure_node(node, flex_grow=0)
        elif self._flex_grow:
            yoga_layout.configure_node(node, flex_grow=self._flex_grow)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._is_active:
            return
        for child in self._children:
            child.render(buffer, delta_time)

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._condition_cleanup:
            self._condition_cleanup()
            self._condition_cleanup = None
        for cached in self._branch_cache.values():
            for child in cached:
                if not child._destroyed:
                    child.destroy()
        self._branch_cache.clear()
        super().destroy()


__all__ = ["Show", "Switch"]
