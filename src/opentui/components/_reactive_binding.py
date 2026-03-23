"""Reactive property binding mixin for Renderable.

Handles binding attributes to Signals, ComputedSignals, and callables
so that UI props update automatically when reactive sources change.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

from .._signal_types import Signal, _ComputedSignal
from .._signals_runtime import _tracking_context
from ._renderable_base import _get_create_prop_binding, _PropBinding
from ._renderable_constants import _SIMPLE_DEFAULTS

_log = logging.getLogger(__name__)

_SENTINEL = object()


class _ReactiveBindingMixin:
    """Reactive property binding lifecycle for Renderable nodes.

    Expects host class to provide: _prop_bindings, _cleanups, _yoga_node,
    _live, _is_simple, _LAYOUT_PROPS, mark_dirty, mark_paint_dirty,
    _propagate_live_count.
    """

    def _set_or_bind(self, attr: str, value: object, *, transform: Callable | None = None) -> None:
        """If value is a Signal, ComputedSignal, or callable (not str/type):
        wraps with optional transform and creates a reactive binding.
        Otherwise: applies transform (if any) and sets directly.
        """
        if isinstance(value, Signal | _ComputedSignal):
            source = value.map(transform) if transform else value
            self._bind_reactive_prop(attr, source)
            self._is_simple = False
        elif callable(value) and not isinstance(value, str | type):
            if transform:
                raw_fn = value
                source = lambda: transform(raw_fn())  # noqa: E731
            else:
                source = value
            self._bind_reactive_prop(attr, source)
            self._is_simple = False
        else:
            resolved = transform(value) if transform and value is not None else value
            setattr(self, attr, resolved)
            # Track whether this attr diverges from the "simple text" defaults
            if (
                self._is_simple
                and attr in _SIMPLE_DEFAULTS
                and resolved is not _SIMPLE_DEFAULTS[attr]
                and resolved != _SIMPLE_DEFAULTS[attr]
            ):
                self._is_simple = False

    def _make_on_change(self, attr: str, yogadirty: bool) -> Callable[[object], None]:
        """Auto-selects dirty level: layout props use mark_dirty() (triggers yoga),
        visual-only props use mark_paint_dirty() (skips yoga). _visible is
        special-cased because it needs _propagate_live_count side effects.
        """
        propagate_live = attr == "_visible"

        if yogadirty or propagate_live:

            def on_change(new_value: object) -> None:
                old = getattr(self, attr, _SENTINEL)
                if old is new_value or old == new_value:
                    return
                setattr(self, attr, new_value)
                self.mark_dirty()
                if yogadirty and self._yoga_node is not None:
                    try:
                        self._yoga_node.mark_dirty()
                    except RuntimeError as e:
                        if "leaf" not in str(e) and "measure" not in str(e):
                            raise
                if propagate_live and self._live:
                    self._propagate_live_count(1 if new_value else -1)
        else:

            def on_change(new_value: object) -> None:
                old = getattr(self, attr, _SENTINEL)
                if old is new_value or old == new_value:
                    return
                setattr(self, attr, new_value)
                self.mark_paint_dirty()

        return on_change

    def _make_on_change_callable(
        self, attr: str, yogadirty: bool, fn: Callable[[], object]
    ) -> Callable[[object], None]:
        """Single-dep callable fast path: subscribes directly to the dep
        signal, skipping the ComputedSignal intermediary.  Wraps _make_on_change
        with fn() re-evaluation and tracking suppression.
        """
        updater = self._make_on_change(attr, yogadirty)

        def on_change(_: object) -> None:
            token = _tracking_context.set(None)
            try:
                new_value = fn()
            finally:
                _tracking_context.reset(token)
            updater(new_value)

        return on_change

    def _bind_reactive_prop(self, attr: str, source: object) -> bool:
        """Bind an attribute to a reactive source (Signal, ComputedSignal, or callable).

        Sets the initial value and subscribes so future changes update the attr,
        mark the node dirty, and (for layout props) mark the yoga node dirty.
        Returns True if binding was created, False if source is not reactive.
        """
        self._unbind_reactive_prop(attr)

        yogadirty = attr in self._LAYOUT_PROPS

        if isinstance(source, Signal | _ComputedSignal):
            # Subscribable source — read initial value without polluting tracking context
            token = _tracking_context.set(None)
            try:
                initial = source()
            finally:
                _tracking_context.reset(token)
            setattr(self, attr, initial)

            # Fast path: C++ NativePropBinding for direct Signals (no transform).
            # The native C++ path writes directly to __slots__, bypassing
            # property setters.  For _visible, a post_write_callback handles
            # the _propagate_live_count side effect that the property setter
            # would normally perform.
            native = getattr(source, "_native", None)
            cpb = _get_create_prop_binding() if native is not None else None
            if native is not None and cpb is not None:
                try:
                    # Build post-write callback for _visible to maintain live_count.
                    # Also propagates _subtree_dirty (mark_dirty) since _visible
                    # is not in _LAYOUT_PROPS but still needs layout-level dirtying.
                    pwc = None
                    if attr == "_visible":

                        def _visible_post_write(old_val: object, new_val: object) -> None:
                            self.mark_dirty()
                            if self._live:
                                self._propagate_live_count(1 if new_val else -1)

                        pwc = _visible_post_write

                    binding = cpb(
                        self,
                        attr,
                        yoga_dirty=yogadirty,
                        post_write_callback=pwc,
                    )
                    native.add_prop_binding(binding)
                    slot_offset = binding.slot_offset

                    def native_cleanup() -> None:
                        native.remove_prop_binding(self, slot_offset)

                    if self._prop_bindings is None:
                        self._prop_bindings = {}
                    self._prop_bindings[attr] = _PropBinding(source, native_cleanup, native_cleanup)
                    self._cleanups[id(native_cleanup)] = native_cleanup
                    return True
                except (ValueError, RuntimeError):
                    pass

            # Slow path: Python callback subscription
            on_change = self._make_on_change(attr, yogadirty)
            unsub = source.subscribe(on_change)
            is_inline_computed = isinstance(source, _ComputedSignal)

            def cleanup() -> None:
                unsub()
                if is_inline_computed:
                    source.dispose()

            def unsub_only() -> None:
                unsub()

            if self._prop_bindings is None:
                self._prop_bindings = {}
            self._prop_bindings[attr] = _PropBinding(source, cleanup, unsub_only)
            self._cleanups[id(cleanup)] = cleanup
            return True

        elif callable(source) and not isinstance(source, type):
            tracked: set[Signal] = set()
            token = _tracking_context.set(tracked)
            try:
                source()  # Discover deps (value discarded)
            except Exception:
                _log.warning("Reactive prop callable raised during dep discovery for %r", attr)
                return False
            finally:
                _tracking_context.reset(token)

            if len(tracked) == 1:
                # Fast path: single dep — subscribe directly, skip ComputedSignal
                dep = next(iter(tracked))
                token2 = _tracking_context.set(None)
                try:
                    initial = source()
                finally:
                    _tracking_context.reset(token2)
                setattr(self, attr, initial)

                on_change = self._make_on_change_callable(attr, yogadirty, source)
                unsub = dep.subscribe(on_change)

                def cleanup_single() -> None:
                    unsub()

                if self._prop_bindings is None:
                    self._prop_bindings = {}
                self._prop_bindings[attr] = _PropBinding(source, cleanup_single, cleanup_single)
                self._cleanups[id(cleanup_single)] = cleanup_single
                return True

            # Multi-dep or zero-dep — use ComputedSignal for auto-tracking
            token2 = _tracking_context.set(None)
            try:
                computed_sig = _ComputedSignal(source)
                initial = computed_sig()
            finally:
                _tracking_context.reset(token2)
            setattr(self, attr, initial)

            on_change = self._make_on_change(attr, yogadirty)
            unsub_c = computed_sig.subscribe(on_change)

            def cleanup_c() -> None:
                unsub_c()
                computed_sig.dispose()

            if self._prop_bindings is None:
                self._prop_bindings = {}
            self._prop_bindings[attr] = _PropBinding(source, cleanup_c, cleanup_c)
            self._cleanups[id(cleanup_c)] = cleanup_c
            return True

        return False

    def _unbind_reactive_prop(self, attr: str) -> None:
        if self._prop_bindings is None:
            return
        binding = self._prop_bindings.pop(attr, None)
        if binding is None:
            return
        with contextlib.suppress(Exception):
            binding.cleanup()
        self._cleanups.pop(id(binding.cleanup), None)
        if not self._prop_bindings:
            self._prop_bindings = None

    def _unbind_all_reactive_props(self) -> None:
        if self._prop_bindings is None:
            return
        for _attr, binding in list(self._prop_bindings.items()):
            with contextlib.suppress(Exception):
                binding.cleanup()
            self._cleanups.pop(id(binding.cleanup), None)
        self._prop_bindings = None
