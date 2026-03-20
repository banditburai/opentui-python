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
from typing import TYPE_CHECKING, Any

from .. import layout as yoga_layout
from ..signals import Signal, _tracking_context
from .base import BaseRenderable, Renderable
from .structural import (
    ErrorBoundary,
    Match,
    Portal,
    Suspense,
    _register_suspense_resource,
    _suspense_stack,
)
from .template import (
    MountedTemplate,
    Template,
    TemplateBinding,
    TemplateRefs,
    bind,
    reactive,
    template,
    template_component,
)

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..renderer import Buffer


def _subscribe_signals(
    tracked: set[Signal],
    callback: Callable[[], None],
) -> Callable[[], None] | None:
    """Subscribe *callback* to each signal in *tracked*.

    Returns a cleanup callable that unsubscribes all, or ``None`` if
    *tracked* is empty.  This is the single implementation of the
    subscribe-lifecycle pattern used by For, Show, Switch, Dynamic,
    and MountedTemplate.
    """
    if not tracked:
        return None
    cleanups = [sig.subscribe(lambda _, cb=callback: cb()) for sig in tracked]

    def cleanup() -> None:
        for unsub in cleanups:
            unsub()

    return cleanup


def _normalize_render_result(
    result: BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...] | None,
):
    if result is None:
        return []
    if isinstance(result, BaseRenderable):
        return [result]
    return list(result)


def _detach_children(parent: BaseRenderable) -> list[BaseRenderable]:
    detached = list(parent._children)
    for child in detached:
        if child._yoga_node is not None and parent._yoga_node is not None:
            parent._yoga_node.remove_child(child._yoga_node)
        child._parent = None
    parent._children.clear()
    parent._children_tuple = None
    return detached


def _subtree_contains_portal(node: BaseRenderable) -> bool:
    from .structural import Portal

    if isinstance(node, Portal):
        return True
    return any(_subtree_contains_portal(child) for child in node._children)


def _split_cacheable_branch_children(
    children: list[BaseRenderable],
) -> tuple[list[BaseRenderable], list[BaseRenderable]]:
    reusable: list[BaseRenderable] = []
    disposable: list[BaseRenderable] = []
    for child in children:
        if _subtree_contains_portal(child):
            disposable.append(child)
        else:
            reusable.append(child)
    return reusable, disposable


def _evict_lru_branches(cache: dict[Any, list[BaseRenderable]], max_size: int) -> None:
    while len(cache) > max_size:
        oldest_key = next(iter(cache))
        evicted = cache.pop(oldest_key)
        for child in evicted:
            if not child._destroyed:
                child.destroy_recursively()


def _normalize_inserted_children(
    result: BaseRenderable | list[Any] | tuple[Any, ...] | str | Any | None,
) -> tuple[str, str | BaseRenderable | list[BaseRenderable]]:
    if result is None:
        return "children", []
    if isinstance(result, BaseRenderable):
        return "single_node", result
    if isinstance(result, list | tuple):
        children: list[BaseRenderable] = []
        for item in result:
            mode, payload = _normalize_inserted_children(item)
            if mode == "text":
                from .text import Text

                children.append(Text(payload))
            elif mode == "single_node":
                children.append(payload)
            else:
                children.extend(payload)
        return "children", children
    return "text", str(result)


def _apply_region_children(
    parent: BaseRenderable,
    new_children: list[BaseRenderable],
) -> None:
    from ..reconciler import _reconcile_matched_child, reconcile

    old_children = list(parent._children)
    if (
        len(old_children) == 1
        and len(new_children) == 1
        and type(old_children[0]) is type(new_children[0])
        and old_children[0].key == new_children[0].key
    ):
        if _can_fast_patch_plain_text(old_children[0], new_children[0]):
            _fast_patch_plain_text(old_children[0], new_children[0])
            parent._children = [old_children[0]]
            parent._children_tuple = None
            parent.mark_dirty()
            return
        if _can_fast_patch_plain_box(old_children[0], new_children[0]):
            _fast_patch_plain_box(parent, old_children[0], new_children[0])
            parent._children = [old_children[0]]
            parent._children_tuple = None
            parent.mark_dirty()
            return
        parent._children = [_reconcile_matched_child(parent, old_children[0], new_children[0])]
        parent._children_tuple = None
        parent.mark_dirty()
        return

    reconcile(parent, old_children, new_children)


def _replace_region_children(
    parent: BaseRenderable,
    new_children: list[BaseRenderable],
) -> None:
    from ..reconciler import _init_nested_fors

    old_children = list(parent._children)
    parent._children = list(new_children)
    parent._children_tuple = None
    parent.mark_dirty()

    for child in new_children:
        child._parent = parent
        _init_nested_fors(child)

    if parent._yoga_node is not None:
        yoga_children = []
        for child in new_children:
            if child._yoga_node is not None:
                yoga_owner = child._yoga_node.owner
                if yoga_owner is not None and yoga_owner is not parent._yoga_node:
                    yoga_owner.remove_child(child._yoga_node)
                yoga_children.append(child._yoga_node)
        parent._yoga_node.set_children(yoga_children)

    for child in old_children:
        child._parent = None
        child.destroy_recursively()


def _can_fast_patch_plain_text(old: BaseRenderable, new: BaseRenderable) -> bool:
    from .text import Text

    if not isinstance(old, Text) or not isinstance(new, Text):
        return False
    if old.key != new.key:
        return False
    if old._children or new._children:
        return False
    if old._text_modifiers or new._text_modifiers:
        return False
    return not (old._prop_bindings or new._prop_bindings)


def _fast_patch_plain_text(old: BaseRenderable, new: BaseRenderable) -> None:
    from .text import Text

    assert isinstance(old, Text)
    assert isinstance(new, Text)

    paint_changed = False
    layout_changed = False
    style_attrs = (
        "_fg",
        "_background_color",
        "_bold",
        "_italic",
        "_underline",
        "_strikethrough",
        "_selection_start",
        "_selection_end",
        "_selection_bg",
        "_opacity",
        "_z_index",
    )
    layout_attrs = ("_wrap_mode", "_visible")
    for attr in style_attrs:
        old_val = object.__getattribute__(old, attr)
        new_val = object.__getattribute__(new, attr)
        if old_val is not new_val and old_val != new_val:
            object.__setattr__(old, attr, new_val)
            paint_changed = True

    for attr in layout_attrs:
        old_val = object.__getattribute__(old, attr)
        new_val = object.__getattribute__(new, attr)
        if old_val is not new_val and old_val != new_val:
            object.__setattr__(old, attr, new_val)
            layout_changed = True
            # _visible bypass: propagate live_count if node has live=True
            if attr == "_visible" and getattr(old, "_live", False):
                old._propagate_live_count(1 if new_val else -1)

    if old._content != new._content:
        old.content = new._content
        layout_changed = True

    if layout_changed:
        old.mark_dirty()
    elif paint_changed:
        old.mark_paint_dirty()


def _can_fast_patch_plain_box(old: BaseRenderable, new: BaseRenderable) -> bool:
    from .box import Box

    if type(old) is not Box or type(new) is not Box:
        return False
    if old.key != new.key:
        return False
    return not (old._prop_bindings or new._prop_bindings)


def _fast_patch_plain_box(parent: BaseRenderable, old: BaseRenderable, new: BaseRenderable) -> None:
    from ..reconciler import _patchable_slots

    changed = False
    for attr in _patchable_slots(type(old)):
        old_val = object.__getattribute__(old, attr)
        new_val = object.__getattribute__(new, attr)
        if old_val is new_val or old_val == new_val:
            continue
        object.__setattr__(old, attr, new_val)
        changed = True

    _apply_region_children(old, list(new._children))
    old._parent = parent
    if changed:
        old.mark_dirty()


class _ReactiveRegion(Renderable):
    """Shared mounted-region lifecycle for fine-grained child updates."""

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

    def _collect_tracked_result(self) -> tuple[set[Signal], Any]:
        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            result = self._render_fn()
        finally:
            _tracking_context.reset(token)
        return tracked, result

    def _evaluate_region(self) -> tuple[set[Signal], Any]:
        return self._collect_tracked_result()

    def _setup_reactive_region(self) -> None:
        tracked, result = self._evaluate_region()
        self._apply_evaluated_region(result)
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

    def _apply_evaluated_region(self, result: Any) -> None:
        raise NotImplementedError

    def _reactive_update(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            tracked, result = self._evaluate_region()
            self._apply_evaluated_region(result)
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
        super().destroy()


class Inserted(_ReactiveRegion):
    """Mounted child expression with a scalar Text fast path.

    This is the closer Python analogue to Solid's child insertion logic:
    scalar expressions update a persistent Text child directly, while
    renderable expressions reconcile mounted children in place.
    """

    __slots__ = ()

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

    def _apply_evaluated_region(self, result: Any) -> None:
        mode, payload = _normalize_inserted_children(result)
        self._apply_region(mode, payload)


class For(Renderable):
    """Keyed list - only renders genuinely new items, preserves existing.

    Auto-tracks signals read by ``each`` and reactively reconciles
    children when those signals change, without requiring a full tree
    rebuild.  Existing items keep their identity, state, and yoga nodes.

    Usage:
        For(
            each=log_entries,        # Signal or callable returning list
            render=log_entry,        # fn(item) -> Renderable
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

    def __init__(self, *, each, render, key_fn=None, **kwargs):
        super().__init__(**kwargs)
        self._each_source = each
        self._render_fn = render
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
        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            source = self._each_source
            source() if callable(source) else source
        finally:
            _tracking_context.reset(token)

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
            tracked: set[Signal] = set()
            token = _tracking_context.set(tracked)
            try:
                source = self._each_source
                source() if callable(source) else source
            finally:
                _tracking_context.reset(token)

            self._reconcile_children()
            self._subscribe_data(tracked)
            self.mark_dirty()
        finally:
            self._reconciling = False

    def _patch_item(self, child: BaseRenderable, item: Any) -> None:
        from ..reconciler import _patch_node, reconcile

        new_child = self._render_fn(item)
        new_child.key = child.key
        _patch_node(child, new_child)
        old_grandchildren = list(child._children)
        new_grandchildren = list(new_child._children)
        if old_grandchildren or new_grandchildren:
            child._children.clear()
            child._children_tuple = None
            reconcile(child, old_grandchildren, new_grandchildren)

    def _patch_existing(self, children: list[BaseRenderable], items: list[Any]) -> int:
        prev = self._last_items
        patched = 0
        for idx, (child, item) in enumerate(zip(children, items, strict=True)):
            if prev is not None and idx < len(prev) and item is prev[idx]:
                continue
            self._patch_item(child, item)
            patched += 1
        return patched

    def _reconcile_children(self):
        """Reconcile children against current source data.

        For reused items (same key), re-renders and patches props via
        _patch_node + recursive reconcile so data changes propagate.
        Fast path: identical keys in same order with identity-based item
        skip (items that are the same object are not re-rendered).
        """
        source = self._each_source
        raw: Any = source() if callable(source) else source
        items: list[Any] = list(raw)

        new_key_list = [self._key_fn(item) for item in items]
        # Generate stable fallback keys for items with key=None
        new_key_list = [
            k if k is not None else f"__for_index_{i}" for i, k in enumerate(new_key_list)
        ]
        old_key_list = [child.key for child in self._children]

        if new_key_list == old_key_list:
            patched = self._patch_existing(self._children, items)
            self._last_items = items
            _log.debug(
                "For[%s] fast-path: %d/%d keys patched", self.key, patched, len(new_key_list)
            )
            return

        if (
            len(new_key_list) > len(old_key_list)
            and new_key_list[: len(old_key_list)] == old_key_list
        ):
            # Pure append: preserve existing order/identity, patch only any
            # changed prefix items, and mount only the new tail nodes.
            patched = self._patch_existing(self._children, items[: len(old_key_list)])
            created = 0

            for idx in range(len(old_key_list), len(items)):
                item = items[idx]
                child = self._render_fn(item)
                child.key = new_key_list[idx]
                child._parent = self
                self._children.append(child)
                created += 1
                if self._yoga_node is not None and child._yoga_node is not None:
                    owner = child._yoga_node.owner
                    if owner is not None:
                        owner.remove_child(child._yoga_node)
                    self._yoga_node.insert_child(child._yoga_node, self._yoga_node.child_count)

            if created:
                self._children_tuple = None
                self.mark_dirty()
                if self._parent is not None:
                    self._parent.mark_dirty()

            self._last_items = items
            _log.debug(
                "For[%s] append fast-path: patched=%d created=%d total=%d",
                self.key,
                patched,
                created,
                len(self._children),
            )
            return

        if (
            len(new_key_list) < len(old_key_list)
            and old_key_list[: len(new_key_list)] == new_key_list
        ):
            # Pure truncate: preserve the shared prefix, patch only any
            # changed prefix items, and destroy only the removed tail nodes.
            patched = self._patch_existing(self._children[: len(new_key_list)], items)
            destroyed = 0

            removed_children = self._children[len(new_key_list) :]
            if removed_children:
                self._children = self._children[: len(new_key_list)]
                self._children_tuple = None
                self.mark_dirty()
                if self._parent is not None:
                    self._parent.mark_dirty()
                if self._yoga_node is not None:
                    for child in removed_children:
                        if child._yoga_node is not None:
                            self._yoga_node.remove_child(child._yoga_node)
                for child in removed_children:
                    child._parent = None
                    child.destroy_recursively()
                    destroyed += 1

            self._last_items = items
            _log.debug(
                "For[%s] truncate fast-path: patched=%d destroyed=%d total=%d",
                self.key,
                patched,
                destroyed,
                len(self._children),
            )
            return

        if (
            len(new_key_list) > len(old_key_list)
            and new_key_list[len(new_key_list) - len(old_key_list) :] == old_key_list
        ):
            # Pure prepend: preserve the shared suffix, patch only any
            # changed reused items, and mount only the new head nodes.
            prepended = len(new_key_list) - len(old_key_list)
            patched = self._patch_existing(self._children, items[prepended:])
            created = 0

            prepended_children: list[BaseRenderable] = []
            for idx in range(prepended):
                item = items[idx]
                child = self._render_fn(item)
                child.key = new_key_list[idx]
                child._parent = self
                prepended_children.append(child)
                created += 1

            if prepended_children:
                self._children = prepended_children + self._children
                self._children_tuple = None
                self.mark_dirty()
                if self._parent is not None:
                    self._parent.mark_dirty()
                if self._yoga_node is not None:
                    for idx, child in enumerate(prepended_children):
                        if child._yoga_node is not None:
                            owner = child._yoga_node.owner
                            if owner is not None:
                                owner.remove_child(child._yoga_node)
                            self._yoga_node.insert_child(child._yoga_node, idx)

            self._last_items = items
            _log.debug(
                "For[%s] prepend fast-path: patched=%d created=%d total=%d",
                self.key,
                patched,
                created,
                len(self._children),
            )
            return

        old_by_key = {c.key: c for c in self._children if c.key is not None}
        new_keys = set(new_key_list)
        new_children = []
        reused = 0
        created = 0

        for idx, item in enumerate(items):
            k = self._key_fn(item)
            if k is None:
                k = f"__for_index_{idx}"
            existing = old_by_key.get(k)
            if existing is not None:
                self._patch_item(existing, item)
                new_children.append(existing)
                reused += 1
            else:
                child = self._render_fn(item)  # Only genuinely new items
                child.key = k
                new_children.append(child)
                created += 1

        # Collect removed children for destruction AFTER yoga sync.
        # destroy_recursively() sets _yoga_node=None which releases the
        # Python reference to the C++ yoga node - if the GC collects it
        # while still in the parent's yoga child list, remove_all_children
        # would dereference freed memory.
        removed = [
            child for child in self._children if child.key is not None and child.key not in new_keys
        ]

        self._children = new_children
        self._children_tuple = None
        self.mark_dirty()
        if self._parent is not None:
            self._parent.mark_dirty()
        for child in new_children:
            child._parent = self

        if self._yoga_node is not None:
            self._yoga_node.remove_all_children()
            for child in new_children:
                if child._yoga_node is not None:
                    owner = child._yoga_node.owner
                    if owner is not None:
                        owner.remove_child(child._yoga_node)
                    self._yoga_node.insert_child(child._yoga_node, self._yoga_node.child_count)

        # Now safe to destroy - yoga nodes are detached from parent.
        for child in removed:
            child._parent = None
            child.destroy_recursively()

        self._last_items = items
        _log.debug(
            "For[%s] reconcile: reused=%d created=%d destroyed=%d total=%d",
            self.key,
            reused,
            created,
            len(removed),
            len(new_children),
        )

    def _pre_configure_yoga(self) -> None:
        self._reconcile_children()

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._data_cleanup:
            self._data_cleanup()
            self._data_cleanup = None
        super().destroy()


class Show(Renderable):
    """Conditional rendering - shows children when condition is truthy.

    Auto-tracks signals read by ``when()`` and reactively swaps children
    when the condition changes, without requiring a full tree rebuild.

    Caches inactive branches so toggling reattaches existing nodes instead
    of destroying and recreating them (~100x faster for non-trivial subtrees).

    Usage:
        Show(
            when=lambda: is_visible(),
            render=lambda: Box(Text("Content")),
            fallback=lambda: Text("Hidden"),
            key="content-show",
        )
    """

    __slots__ = (
        "_when",
        "_render_fn",
        "_fallback_fn",
        "_is_active",
        "_current_branch",
        "_condition_cleanup",
        "_updating",
        "_render_cache",
        "_fallback_cache",
        "_cached_display",
    )

    def __init__(
        self,
        *,
        when: Callable[[], Any],
        render: Callable[[], BaseRenderable | list[BaseRenderable]],
        fallback: Callable[[], BaseRenderable | list[BaseRenderable]] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._when = when
        self._render_fn = render
        self._fallback_fn = fallback
        self._is_active = False
        self._current_branch: str = "none"
        self._condition_cleanup: Callable[[], None] | None = None
        self._updating = False
        self._render_cache: list[BaseRenderable] | None = None
        self._fallback_cache: list[BaseRenderable] | None = None
        self._cached_display: str | None = None
        self._setup_reactive_condition()

    def _setup_reactive_condition(self) -> None:
        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            condition = self._when()
        finally:
            _tracking_context.reset(token)

        self._apply_condition(condition)
        self._subscribe_condition(tracked)

    def _subscribe_condition(self, tracked: set[Signal]) -> None:
        if self._condition_cleanup:
            self._condition_cleanup()
            self._condition_cleanup = None

        self._condition_cleanup = _subscribe_signals(tracked, self._reactive_update)

    def _apply_condition(self, condition: Any) -> None:
        active = bool(condition)
        new_branch = (
            "render" if active else ("fallback" if self._fallback_fn is not None else "none")
        )
        if new_branch == self._current_branch:
            return

        disposed_children: list[BaseRenderable] = []
        if self._children:
            reusable, disposed_children = _split_cacheable_branch_children(list(self._children))
            if self._current_branch == "render":
                self._render_cache = reusable or None
            elif self._current_branch == "fallback":
                self._fallback_cache = reusable or None
        _detach_children(self)
        for child in disposed_children:
            child.destroy_recursively()

        self._current_branch = new_branch
        self._is_active = new_branch != "none"

        cache = self._render_cache if new_branch == "render" else self._fallback_cache
        if cache is not None:
            if new_branch == "render":
                self._render_cache = None
            else:
                self._fallback_cache = None
            for child in cache:
                self.add(child)
            return

        if new_branch == "render":
            render_fn = self._render_fn
        elif new_branch == "fallback" and self._fallback_fn is not None:
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
            tracked: set[Signal] = set()
            token = _tracking_context.set(tracked)
            try:
                condition = self._when()
            finally:
                _tracking_context.reset(token)

            self._apply_condition(condition)
            self._subscribe_condition(tracked)
            self.mark_dirty()
        finally:
            self._updating = False

    def _post_configure_yoga(self, node: Any) -> None:
        display = "flex" if self._is_active else "none"
        if display != self._cached_display:
            self._cached_display = display
            yoga_layout.configure_node(node, display=display)

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
                        child.destroy_recursively()
        self._render_cache = None
        self._fallback_cache = None
        super().destroy()


class Dynamic(_ReactiveRegion):
    """Mounted reactive region that reconciles only its own children.

    The render callable is tracked independently from the parent component
    body. Signal changes read inside ``render`` update this region in place
    instead of forcing a full component rebuild.
    """

    __slots__ = (
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
        self._cache_key_fn = cache_key
        self._current_cache_key: Any = None
        self._branch_cache: dict[Any, list[BaseRenderable]] = {}
        self._max_cached_branches = max_cached_branches
        super().__init__(render=render, **kwargs)

    def _evaluate_region(self) -> tuple[set[Signal], tuple[Any, str, list[BaseRenderable] | None]]:
        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            cache_key = self._cache_key_fn() if self._cache_key_fn is not None else None
            if (
                self._cache_key_fn is not None
                and cache_key == self._current_cache_key
                and self._children
            ):
                return tracked, (cache_key, "current", None)

            if self._cache_key_fn is not None:
                cached = self._branch_cache.pop(cache_key, None)
                if cached is not None:
                    return tracked, (cache_key, "cached", cached)

            new_children = _normalize_render_result(self._render_fn())
        finally:
            _tracking_context.reset(token)

        return tracked, (cache_key, "fresh", new_children)

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

    def _apply_evaluated_region(self, result: tuple[Any, str, list[BaseRenderable] | None]) -> None:
        cache_key, mode, payload = result
        self._apply_region(cache_key, mode, payload)

    def destroy(self) -> None:
        if self._destroyed:
            return
        for cached in self._branch_cache.values():
            for child in cached:
                if not child._destroyed:
                    child.destroy_recursively()
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


class Switch(Renderable):
    """Multi-branch conditional rendering with reactive subscription.

    Auto-tracks signals read by ``on()`` or ``Match.when()`` and reactively
    swaps children when the active branch changes, without requiring a full
    tree rebuild.

    Two modes:
    - Condition matching: pass Match objects as positional args
    - Value matching: pass on=callable, cases=dict

    Usage (condition matching):
        Switch(
            Match(when=lambda: score() >= 90, render=lambda: Text("A")),
            Match(when=lambda: score() >= 80, render=lambda: Text("B")),
            fallback=lambda: Text("F"),
            key="grade",
        )

    Usage (value matching):
        Switch(
            on=lambda: active_tab(),
            cases={
                0: counter_panel,
                1: log_panel,
            },
            key="tab-switch",
        )
    """

    __slots__ = (
        "_matches",
        "_on_fn",
        "_cases",
        "_fallback_fn",
        "_is_active",
        "_current_branch_key",
        "_condition_cleanup",
        "_updating",
        "_branch_cache",
        "_max_cached_branches",
        "_cached_display",
    )

    def __init__(
        self,
        *matches: Match,
        on: Callable[[], Any] | None = None,
        cases: dict[Any, Callable[[], BaseRenderable | list[BaseRenderable]]] | None = None,
        fallback: Callable[[], BaseRenderable | list[BaseRenderable]] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._matches = matches
        self._on_fn = on
        self._cases = cases or {}
        self._fallback_fn = fallback
        self._is_active = False
        self._current_branch_key: tuple[Any, ...] = ("none",)
        self._condition_cleanup: Callable[[], None] | None = None
        self._updating = False
        self._branch_cache: dict[tuple[Any, ...], list[BaseRenderable]] = {}
        self._max_cached_branches: int = 4
        self._cached_display: str | None = None
        self._setup_reactive_condition()

    def _setup_reactive_condition(self) -> None:
        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            render_fn, branch_key = self._resolve_branch()
        finally:
            _tracking_context.reset(token)

        self._apply_branch(render_fn, branch_key)
        self._subscribe_condition(tracked)

    def _subscribe_condition(self, tracked: set[Signal]) -> None:
        if self._condition_cleanup:
            self._condition_cleanup()
            self._condition_cleanup = None

        self._condition_cleanup = _subscribe_signals(tracked, self._reactive_update)

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
            return self._fallback_fn, ("fallback",)

        return None, ("none",)

    def _apply_branch(self, render_fn: Callable | None, branch_key: tuple[Any, ...]) -> None:
        if branch_key == self._current_branch_key:
            return

        disposed_children: list[BaseRenderable] = []
        if self._children and self._current_branch_key != ("none",):
            reusable, disposed_children = _split_cacheable_branch_children(list(self._children))
            if reusable:
                self._branch_cache[self._current_branch_key] = reusable
                _evict_lru_branches(self._branch_cache, self._max_cached_branches)
        _detach_children(self)
        for child in disposed_children:
            child.destroy_recursively()

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
            tracked: set[Signal] = set()
            token = _tracking_context.set(tracked)
            try:
                render_fn, branch_key = self._resolve_branch()
            finally:
                _tracking_context.reset(token)

            self._apply_branch(render_fn, branch_key)
            self._subscribe_condition(tracked)
            self.mark_dirty()
        finally:
            self._updating = False

    def _post_configure_yoga(self, node: Any) -> None:
        display = "flex" if self._is_active else "none"
        if display != self._cached_display:
            self._cached_display = display
            yoga_layout.configure_node(node, display=display)

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
                    child.destroy_recursively()
        self._branch_cache.clear()
        super().destroy()


__all__ = [
    "Dynamic",
    "ErrorBoundary",
    "For",
    "Inserted",
    "Match",
    "MemoBlock",
    "MountedTemplate",
    "Portal",
    "Show",
    "Suspense",
    "Switch",
    "Template",
    "TemplateBinding",
    "_register_suspense_resource",
    "bind",
    "reactive",
    "template",
    "template_component",
]
