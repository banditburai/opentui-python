"""Template system - Mount, @component.

Provides the template-based rendering primitives that mount a stable
subtree once and update it reactively in place.  ``@component`` is the
primary public entry point for named components; ``Mount`` is the
inline primitive for reactive regions.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from .._signal_types import Signal
from .._signals_runtime import _tracking_context
from ._control_flow_region import subscribe_signals
from ._control_flow_region import normalize_render_result
from .base import BaseRenderable, Renderable
from .structural import Portal

_TEMPLATE_UNSET = object()
_TEMPLATE_NO_KEY = object()


def _collect_template_refs(
    nodes: list[BaseRenderable],
    refs: dict[str, BaseRenderable] | None = None,
) -> dict[str, BaseRenderable]:
    if refs is None:
        refs = {}
    for node in nodes:
        refs[node.id] = node
        child_nodes = (
            list(node._content_children) if isinstance(node, Portal) else list(node._children)
        )
        _collect_template_refs(child_nodes, refs)
    return refs


class Mount(Renderable):
    """Mount a build function as a reactive subtree.

    The inline primitive for reactive regions.  ``build()`` creates the
    subtree once; signals read during build are auto-tracked and trigger
    rebuilds when they change.

    For named, reusable components with props, use ``@component`` instead.
    """

    __slots__ = (
        "_build_fn",
        "_update_fn",
        "_invalidate_when",
        "_auto_invalidate",
        "_auto_tracked_deps",
        "_data_cleanup",
        "_tracked_signals",
        "_updating",
        "_current_key",
        "_refs",
        "_update_arity",
    )

    def __init__(
        self,
        build: Callable[[], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]],
        *,
        update: Callable[..., None] | None = None,
        invalidate_when: Callable[[], Any] | None = None,
        auto_invalidate: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if invalidate_when is not None:
            auto_invalidate = False
        self._build_fn = build
        self._update_fn = update
        self._invalidate_when = invalidate_when
        self._auto_invalidate = auto_invalidate
        self._auto_tracked_deps: tuple[Signal, ...] = ()
        self._data_cleanup: Callable[[], None] | None = None
        self._tracked_signals: frozenset[Signal] = frozenset()
        self._updating = False
        self._current_key: Any = _TEMPLATE_UNSET
        self._refs: dict[str, BaseRenderable] = {}
        self._update_arity = self._resolve_update_arity(update)
        self._setup_template()

    def _template_target_from_children(
        self, children: list[BaseRenderable]
    ) -> BaseRenderable | list[BaseRenderable]:
        return children[0] if len(children) == 1 else children

    @staticmethod
    def _resolve_update_arity(update: Callable[..., None] | None) -> int:
        if update is None:
            return 0
        try:
            params = inspect.signature(update).parameters.values()
        except (TypeError, ValueError):
            return 1
        positional = [
            p
            for p in params
            if p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        return 2 if len(positional) >= 2 else 1

    def _rebuild_refs(self, children: list[BaseRenderable]) -> None:
        self._refs = dict(_collect_template_refs(children))

    def _run_update(self, update_target: BaseRenderable | list[BaseRenderable]) -> None:
        if self._update_fn is None:
            return
        if self._update_arity >= 2:
            self._update_fn(update_target, self._refs)
        else:
            self._update_fn(update_target)

    def _subscribe_data(self, tracked: set[Signal]) -> None:
        next_tracked = frozenset(tracked)
        if next_tracked == self._tracked_signals:
            return

        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
            self._tracked_signals = frozenset()

        self._data_cleanup = subscribe_signals(tracked, self._reactive_update)
        self._tracked_signals = next_tracked

    def _evaluate_template(
        self,
    ) -> tuple[set[Signal], Any, list[BaseRenderable] | None, bool]:
        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            # Compute the invalidation key
            if self._auto_invalidate:
                next_key = self._compute_auto_key()
            elif self._invalidate_when is not None:
                next_key = self._invalidate_when()
            else:
                next_key = _TEMPLATE_NO_KEY

            rebuilt_children: list[BaseRenderable] | None = None
            force_replace = False
            needs_build = (
                self._current_key is _TEMPLATE_UNSET
                or next_key != self._current_key
                or not self._children
            )
            if needs_build:
                if self._auto_invalidate:
                    # Run build under a separate tracking pass to capture deps
                    build_tracked: set[Signal] = set()
                    build_token = _tracking_context.set(build_tracked)
                    try:
                        rebuilt_children = normalize_render_result(self._build_fn())
                    finally:
                        _tracking_context.reset(build_token)
                    tracked.update(build_tracked)
                    self._auto_tracked_deps = tuple(build_tracked)
                    # Recompute key from newly discovered deps
                    next_key = self._snapshot_auto_key()
                else:
                    rebuilt_children = normalize_render_result(self._build_fn())

                force_replace = (
                    self._current_key is not _TEMPLATE_UNSET and next_key != self._current_key
                )
                self._rebuild_refs(rebuilt_children)
                update_target = self._template_target_from_children(rebuilt_children)
            else:
                update_target = self._template_target_from_children(list(self._children))

            self._run_update(update_target)
        finally:
            _tracking_context.reset(token)

        return tracked, next_key, rebuilt_children, force_replace

    def _compute_auto_key(self) -> tuple | object:
        """Read previously-tracked deps to form the invalidation key."""
        if not self._auto_tracked_deps:
            return _TEMPLATE_NO_KEY
        return tuple(dep.peek() for dep in self._auto_tracked_deps)

    _snapshot_auto_key = _compute_auto_key

    def _setup_template(self) -> None:
        from ._control_flow_region import apply_region_children

        tracked, next_key, rebuilt_children, _force_replace = self._evaluate_template()
        if rebuilt_children is not None:
            apply_region_children(self, rebuilt_children)
        self._current_key = next_key
        self._subscribe_data(tracked)

    def _reactive_update(self) -> None:
        from ._control_flow_region import apply_region_children, replace_region_children

        if self._updating:
            return
        self._updating = True
        try:
            tracked, next_key, rebuilt_children, force_replace = self._evaluate_template()
            if rebuilt_children is not None:
                if force_replace:
                    replace_region_children(self, rebuilt_children)
                else:
                    apply_region_children(self, rebuilt_children)
            self._current_key = next_key
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
        self._refs = {}
        super().destroy()


def component(
    fn: Callable[..., BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]]
    | None = None,
    *,
    invalidate_when: Callable[..., Any] | None = None,
    **decorator_kwargs,
):
    """Decorator for reactive components.

    The decorated function, when called, returns a ``Mount`` that rebuilds
    when any signal read in the component body changes.  Prop-level lambdas
    and Signals are handled by fine-grained bindings without triggering a
    full rebuild.

    Kwargs matching the function's own parameters are forwarded to the
    function; remaining kwargs (layout, key, etc.) go to the Mount.

    Usage::

        @component
        def Counter():
            count = Signal(0, name="count")
            return Box(
                Text(lambda: f"Count: {count()}"),
            )

        Counter()                    # returns Mount
        Counter(flex_grow=1)         # layout kwargs pass through

        # Component params are separated automatically
        @component
        def UserCard(user):
            return Box(Text(lambda: user.name()))

        UserCard(some_user, flex_grow=1)

        # Works naturally with Show/Switch
        Show(Counter(), when=is_visible)
        Switch(on=active_tab, cases={0: Counter, 1: LogPanel})
    """

    def decorate(
        component_fn: Callable[
            ..., BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]
        ],
    ):
        try:
            fn_params = set(inspect.signature(component_fn).parameters)
        except (TypeError, ValueError):
            fn_params = set()

        def wrapped(*args: Any, **kwargs: Any) -> Mount:
            fn_kwargs: dict[str, Any] = {}
            mt_kwargs: dict[str, Any] = {}
            for k, v in kwargs.items():
                if k in fn_params:
                    fn_kwargs[k] = v
                else:
                    mt_kwargs[k] = v

            def build():
                return component_fn(*args, **fn_kwargs)

            invalidate = None
            if invalidate_when is not None:
                invalidate = lambda: invalidate_when(*args, **fn_kwargs)  # noqa: E731

            merged = {**decorator_kwargs, **mt_kwargs}
            return Mount(build, invalidate_when=invalidate, **merged)

        wrapped.__name__ = getattr(component_fn, "__name__", "component")
        wrapped.__doc__ = component_fn.__doc__
        wrapped.__qualname__ = getattr(component_fn, "__qualname__", wrapped.__name__)
        wrapped.__opentui_component__ = True
        return wrapped

    if fn is not None:
        return decorate(fn)
    return decorate


__all__ = [
    "Mount",
    "component",
]
