"""Structural control flow - For, Show, Switch.

Fine-grained reactive control flow primitives that subscribe to their
signal dependencies and update their children reactively, without
requiring a full tree rebuild.  Follows Solid.js semantics: each
primitive auto-tracks the signals it reads and re-evaluates only when
those specific signals change.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import layout as yoga_layout
from .. import structs as s
from ..signals import Signal, _tracking_context, is_reactive
from .base import BaseRenderable, Renderable

_log = logging.getLogger(__name__)
_TEMPLATE_UNSET = object()
_TEMPLATE_NO_KEY = object()

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


class TemplateRefs(dict[str, BaseRenderable]):
    """Stable id->node mapping for MountedTemplate updates."""

    def require(self, id: str) -> BaseRenderable:
        node = self.get(id)
        if node is None:
            raise KeyError(f"Template ref not found: {id}")
        return node


@dataclass(frozen=True, slots=True)
class TemplateBinding:
    """Marker for declarative template lowering.

    Most callers should use :func:`reactive` rather than construct this directly.
    """

    source: object
    __opentui_template_binding__: bool = True


def reactive(source: object) -> TemplateBinding:
    """Mark a prop/text value for mounted-template lowering.

    ``source`` may be a plain value, ``Signal``, computed, or a zero-argument
    callable. Small lambdas are fine for local leaf expressions; named
    functions are preferred when the logic is reused or non-trivial.

    There are two reactive mechanisms for updating props:

    1. **Direct Signal/callable binding** (no ``reactive()`` needed):
       Pass a ``Signal`` or callable directly to a prop on any component.
       The prop will auto-subscribe and update without rebuilding::

           count = Signal(0)
           Text(content=count)               # Signal bound directly
           Text(fg=lambda: "red" if x() else "blue")  # callable auto-wrapped

    2. **Template lowering** (use ``reactive()``):
       Inside ``@template_component``, wrap values with ``reactive()`` so the
       template compiler can track which props are reactive and set up
       fine-grained subscriptions on the mounted instance::

           @template_component
           def Counter():
               count = Signal(0)
               return Text(reactive(lambda: f"Count: {count()}"), id="label")

    Use ``reactive()`` inside ``@template_component`` bodies. Outside templates,
    pass Signals or callables directly to props — they are auto-detected.

    Examples:
        Text(reactive(lambda: f"Count: {count()}"), id="count")

        def panel_title() -> str:
            return f"Count: {count()}"

        Text(reactive(panel_title), id="count")
    """
    return TemplateBinding(source=source)


def bind(source: object) -> TemplateBinding:
    """Deprecated: use ``reactive()`` instead."""
    import warnings

    warnings.warn(
        "bind() is deprecated, use reactive() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return reactive(source)


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


class MountedTemplate(Renderable):
    """Mount a stable subtree once, then update it reactively in place.

    This is the explicit architectural escape hatch for structurally stable
    dynamic regions. ``build()`` creates the mounted subtree once.
    ``update()`` reads signals and mutates the mounted subtree directly.
    ``invalidate_when`` is optional and rebuilds the subtree only when its
    structural key changes.

    Use named ``build`` / ``update`` functions for anything non-trivial.
    """

    __slots__ = (
        "_build_fn",
        "_update_fn",
        "_invalidate_when",
        "_data_cleanup",
        "_tracked_signals",
        "_updating",
        "_current_key",
        "_refs",
        "_update_arity",
    )

    def __init__(
        self,
        *,
        build: Callable[[], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]],
        update: Callable[..., None] | None = None,
        invalidate_when: Callable[[], Any] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._build_fn = build
        self._update_fn = update
        self._invalidate_when = invalidate_when
        self._data_cleanup: Callable[[], None] | None = None
        self._tracked_signals: frozenset[Signal] = frozenset()
        self._updating = False
        self._current_key: Any = _TEMPLATE_UNSET
        self._refs: TemplateRefs = TemplateRefs()
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
        self._refs = TemplateRefs(_collect_template_refs(children))

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

        self._data_cleanup = _subscribe_signals(tracked, self._reactive_update)
        self._tracked_signals = next_tracked

    def _evaluate_template(
        self,
    ) -> tuple[set[Signal], Any, list[BaseRenderable] | None, bool]:
        tracked: set[Signal] = set()
        token = _tracking_context.set(tracked)
        try:
            next_key = (
                self._invalidate_when() if self._invalidate_when is not None else _TEMPLATE_NO_KEY
            )
            rebuilt_children: list[BaseRenderable] | None = None
            force_replace = False
            if (
                self._current_key is _TEMPLATE_UNSET
                or next_key != self._current_key
                or not self._children
            ):
                rebuilt_children = _normalize_render_result(self._build_fn())
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

    def _setup_template(self) -> None:
        tracked, next_key, rebuilt_children, _force_replace = self._evaluate_template()
        if rebuilt_children is not None:
            _apply_region_children(self, rebuilt_children)
        self._current_key = next_key
        self._subscribe_data(tracked)

    def _reactive_update(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            tracked, next_key, rebuilt_children, force_replace = self._evaluate_template()
            if rebuilt_children is not None:
                if force_replace:
                    _replace_region_children(self, rebuilt_children)
                else:
                    _apply_region_children(self, rebuilt_children)
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
        self._refs = TemplateRefs()
        super().destroy()


def _read_template_binding_value(source: object) -> object:
    if is_reactive(source):
        return source()
    return source


def _iter_template_attrs(node: BaseRenderable) -> list[str]:
    attrs: list[str] = []
    seen: set[str] = set()
    for cls in type(node).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for attr in slots:
            if attr not in seen:
                seen.add(attr)
                attrs.append(attr)
    if hasattr(node, "__dict__"):
        for attr in node.__dict__:
            if attr not in seen:
                attrs.append(attr)
    return attrs


def _extract_template_bindings(
    nodes: list[BaseRenderable],
    bindings: dict[str, object] | None = None,
) -> dict[str, object]:
    if bindings is None:
        bindings = {}
    for node in nodes:
        for attr in _iter_template_attrs(node):
            try:
                value = object.__getattribute__(node, attr)
            except AttributeError:
                continue
            if not getattr(value, "__opentui_template_binding__", False):
                continue
            public_attr = attr[1:] if attr.startswith("_") else attr
            bindings[f"{node.id}.{public_attr}"] = value.source
            _set_template_attr(node, public_attr, _read_template_binding_value(value.source))
        child_nodes = (
            list(node._content_children) if isinstance(node, Portal) else list(node._children)
        )
        _extract_template_bindings(child_nodes, bindings)
    return bindings


def _resolve_template_target(
    mounted: BaseRenderable | list[BaseRenderable],
    refs: TemplateRefs,
    path: str,
) -> tuple[BaseRenderable, str]:
    node_id, sep, attr = path.rpartition(".")
    if not sep or not node_id or not attr:
        raise ValueError(f"Template binding must be '<id>.<attr>' or '@root.<attr>', got {path!r}")
    if node_id == "@root":
        if not isinstance(mounted, BaseRenderable):
            raise ValueError("@root bindings require a single mounted root node")
        return mounted, attr
    return refs.require(node_id), attr


def _set_template_attr(target: BaseRenderable, attr: str, value: object) -> None:
    descriptor = getattr(type(target), attr, None)
    if isinstance(descriptor, property) and descriptor.fset is not None:
        setattr(target, attr, value)
        return

    private_attr = f"_{attr}"
    try:
        old = object.__getattribute__(target, private_attr)
    except AttributeError:
        setattr(target, attr, value)
        return

    new_value = value
    if attr in {"fg", "background_color", "border_color", "focused_border_color", "selection_bg"}:
        new_value = target._parse_color(value) if value is not None else None
    elif attr == "border_style":
        new_value = s.parse_border_style(value)

    if old is new_value or old == new_value:
        return

    object.__setattr__(target, private_attr, new_value)
    if isinstance(target, Renderable) and private_attr in target._LAYOUT_PROPS:
        target.mark_dirty()
        if target._yoga_node is not None:
            try:
                target._yoga_node.mark_dirty()
            except RuntimeError as e:
                if "leaf" not in str(e) and "measure" not in str(e):
                    raise
    else:
        target.mark_paint_dirty()


class Template(MountedTemplate):
    """Declarative mounted template with id-based reactive bindings.

    Usage:
        Template(
            build=lambda: Box(
                Text("", id="count"),
                Text("", id="double"),
                id="panel",
            ),
            bindings={
                "count.content": lambda: f"Count: {count()}",
                "double.content": lambda: f"Double: {count() * 2}",
                "panel.border": lambda: bool(count() % 2),
            },
        )

    Named functions are equally supported and are preferred when the template
    is shared or the binding logic is more than a small local expression.
    """

    __slots__ = ()

    def __init__(
        self,
        *,
        build: Callable[[], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]],
        bindings: dict[str, object],
        invalidate_when: Callable[[], Any] | None = None,
        **kwargs,
    ):
        def update(mounted: BaseRenderable | list[BaseRenderable], refs: TemplateRefs) -> None:
            for path, source in bindings.items():
                target, attr = _resolve_template_target(mounted, refs, path)
                _set_template_attr(target, attr, _read_template_binding_value(source))

        super().__init__(
            build=build,
            update=update,
            invalidate_when=invalidate_when,
            **kwargs,
        )


def template(
    build: Callable[[], BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]],
    *,
    invalidate_when: Callable[[], Any] | None = None,
    **kwargs,
) -> MountedTemplate:
    """Lower a bound build tree onto MountedTemplate automatically.

    Build functions can use ``reactive(...)`` for prop/text values and this helper
    will extract those bindings into the mounted-template fast path.

    This is the most Pythonic high-level entry point for stable regions:
    write a normal build function, mark changing leaf values with ``reactive(...)``,
    and optionally provide ``invalidate_when`` for real structural changes.

    Example:
        def build_panel():
            return Box(
                Text(reactive(panel_title), id="title"),
                Text(reactive(panel_subtitle), id="subtitle"),
                id="panel",
                border=reactive(is_selected),
            )

        panel = template(build_panel, invalidate_when=current_mode)
    """

    extracted_bindings: dict[str, object] = {}

    def build_with_lowering():
        nonlocal extracted_bindings
        built = _normalize_render_result(build())
        extracted_bindings = _extract_template_bindings(built)
        if len(built) == 1:
            return built[0]
        return built

    def update(mounted: BaseRenderable | list[BaseRenderable], refs: TemplateRefs) -> None:
        for path, source in extracted_bindings.items():
            target, attr = _resolve_template_target(mounted, refs, path)
            _set_template_attr(target, attr, _read_template_binding_value(source))

    return MountedTemplate(
        build=build_with_lowering,
        update=update,
        invalidate_when=invalidate_when,
        **kwargs,
    )


def template_component(
    fn: Callable[..., BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]]
    | None = None,
    *,
    invalidate_when: Callable[..., Any] | None = None,
    **template_kwargs,
):
    """Decorate a component function so it renders through ``template(...)``.

    This is the preferred migration path for stable components:
    keep authoring a normal component function, use ``reactive(...)`` for changing
    leaf values, and opt the component into mounted-template execution.

    Example:
        @template_component
        def StatusPanel():
            return Box(
                Text(reactive(panel_title), id="title"),
                Text(reactive(panel_subtitle), id="subtitle"),
                id="panel",
                border=reactive(is_selected),
            )

        @template_component(invalidate_when=lambda mode: mode())
        def ModePanel(mode):
            return Box(Text(reactive(lambda: mode())), id=f"mode-{mode()}")
    """

    def decorate(
        component_fn: Callable[
            ..., BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...]
        ],
    ):
        def wrapped(*args, **kwargs):
            def build():
                return component_fn(*args, **kwargs)

            invalidate = None
            if invalidate_when is not None:
                invalidate = lambda: invalidate_when(*args, **kwargs)  # noqa: E731

            return template(
                build,
                invalidate_when=invalidate,
                **template_kwargs,
            )

        wrapped.__name__ = getattr(component_fn, "__name__", "template_component")
        wrapped.__doc__ = component_fn.__doc__
        wrapped.__qualname__ = getattr(component_fn, "__qualname__", wrapped.__name__)
        wrapped.__opentui_template_component__ = True
        return wrapped

    if fn is not None:
        return decorate(fn)
    return decorate


@dataclass(frozen=True, slots=True)
class Match:
    """A branch condition for Switch. Not a Renderable; just configuration."""

    when: Callable[[], Any]
    render: Callable[[], BaseRenderable | list[BaseRenderable]]


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


class Portal(Renderable):
    """Render children at a different location in the component tree.

    The Portal marker itself is invisible (display=none). It creates a Box
    container at the mount point containing the actual children. This is
    useful for modals, overlays, toasts, and command palettes that need to
    escape their logical parent's layout constraints.

    Usage:
        Portal(
            Text("Modal content"),
            mount=overlay_box,     # or callable, or None for root
            ref=lambda c: ...,     # optional callback receiving container
            key="modal-portal",
        )
    """

    __slots__ = ("_mount_source", "_container", "_ref_fn", "_current_mount", "_content_children")

    def __init__(
        self,
        *children: BaseRenderable,
        mount: BaseRenderable | Callable[[], BaseRenderable] | None = None,
        ref: Callable[[BaseRenderable], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._mount_source = mount
        self._ref_fn = ref
        self._container: BaseRenderable | None = None
        self._current_mount: BaseRenderable | None = None
        self._content_children: list[BaseRenderable] = list(children)

    def _resolve_mount(self) -> BaseRenderable:
        if self._mount_source is None:
            from ..hooks import use_renderer

            try:
                return use_renderer().root
            except RuntimeError:
                raise RuntimeError(
                    "Portal with mount=None requires an active renderer. "
                    "Pass an explicit mount= target or ensure a renderer is running."
                ) from None
        if callable(self._mount_source):
            return self._mount_source()
        return self._mount_source

    @staticmethod
    def _clear_subtree_dirty_flags(node: BaseRenderable) -> None:
        node._subtree_dirty = False
        for child in node._children:
            Portal._clear_subtree_dirty_flags(child)

    @staticmethod
    def _content_extent(child: BaseRenderable, size_attr: str, layout_attr: str) -> int:
        value = getattr(child, size_attr, None)
        if isinstance(value, int | float):
            return int(value)
        return int(getattr(child, layout_attr, 0) or 0)

    @classmethod
    def _measure_container_bounds(cls, children: list[BaseRenderable]) -> tuple[int, int]:
        max_right = 0
        max_bottom = 0
        for child in children:
            left = getattr(child, "_pos_left", None)
            top = getattr(child, "_pos_top", None)
            x = int(left) if isinstance(left, int | float) else int(getattr(child, "_x", 0) or 0)
            y = int(top) if isinstance(top, int | float) else int(getattr(child, "_y", 0) or 0)
            width = cls._content_extent(child, "_width", "_layout_width")
            height = cls._content_extent(child, "_height", "_layout_height")
            max_right = max(max_right, x + max(0, width))
            max_bottom = max(max_bottom, y + max(0, height))
        return max_right, max_bottom

    def _ensure_container(self) -> None:
        from .box import Box

        mount = self._resolve_mount()

        if self._container is not None and self._current_mount is not mount:
            if self._current_mount is not None and not self._current_mount._destroyed:
                self._current_mount.remove(self._container)
            self._container.destroy_recursively()
            self._container = None

        if self._container is None:
            self._container = Box(
                key=f"portal-container-{self.key}" if self.key else None,
                position="absolute",
                left=0,
                top=0,
            )
            self._container._host = self
            self._container.contains_point = lambda x, y: True
            self._container.add_children(self._content_children)
            mount.add(self._container)
            self._current_mount = mount
            if self._ref_fn is not None:
                self._ref_fn(self._container)
            container_changed = True
        else:
            container_changed = False

        bounds_width, bounds_height = self._measure_container_bounds(self._content_children)
        if bounds_width > 0 and self._container.width != bounds_width:
            self._container.width = bounds_width
            container_changed = True
        if bounds_height > 0 and self._container.height != bounds_height:
            self._container.height = bounds_height
            container_changed = True
        if container_changed:
            self._container._configure_yoga_properties()
            self._clear_subtree_dirty_flags(self._container)

    def _pre_configure_yoga(self) -> None:
        self._ensure_container()

    def _post_configure_yoga(self, node: Any) -> None:
        yoga_layout.configure_node(node, display="none")

    def participates_in_parent_yoga(self) -> bool:
        return False

    def affects_parent_paint(self) -> bool:
        return False

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        pass

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._container is not None:
            container = self._container
            mount = self._current_mount
            self._container = None
            self._current_mount = None
            if mount is not None and not mount._destroyed:
                mount.remove(container)
            if not container._destroyed:
                container.destroy_recursively()
        self._content_children.clear()
        super().destroy()


class ErrorBoundary(Renderable):
    """Catches exceptions during child construction and renders a fallback.

    Wraps child construction in try/except. On error, swaps children for
    the fallback. Fallback receives (error, reset_fn). Calling reset_fn
    retries the original render.

    Usage:
        ErrorBoundary(
            render=lambda: SomeComponent(),
            fallback=lambda err, reset: Box(
                Text(f"Error: {err}"),
                Text("Click to retry", on_mouse_down=lambda _: reset()),
            ),
        )
    """

    __slots__ = ("_render_fn", "_fallback_fn", "_error", "_has_error")

    def __init__(
        self,
        *,
        render: Callable[[], BaseRenderable | list[BaseRenderable]],
        fallback: Callable[[Exception, Callable], BaseRenderable | list[BaseRenderable]],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._render_fn = render
        self._fallback_fn = fallback
        self._error: Exception | None = None
        self._has_error = False
        self._try_render()

    def _try_render(self) -> None:
        try:
            children = _normalize_render_result(self._render_fn())
            self._has_error = False
            self._error = None
            for child in children:
                self.add(child)
        except Exception as e:
            self._error = e
            self._has_error = True
            self._show_fallback(e)

    def _show_fallback(self, error: Exception) -> None:
        for c in list(self._children):
            self.remove(c)
            c.destroy_recursively()
        try:
            for c in _normalize_render_result(self._fallback_fn(error, self._reset)):
                self.add(c)
        except Exception:
            pass  # Keep boundary alive but empty if fallback itself crashes
        self.mark_dirty()

    def _reset(self) -> None:
        for c in list(self._children):
            self.remove(c)
            c.destroy_recursively()
        self._try_render()
        self.mark_dirty()


_suspense_stack: list[list[Signal]] = []


def _register_suspense_resource(loading_signal: Signal) -> None:
    if _suspense_stack:
        _suspense_stack[-1].append(loading_signal)


class Suspense(Renderable):
    """Show fallback while nested resources are loading.

    Mirrors SolidJS ``<Suspense>``. Tracks resource loading signals
    registered during child construction and shows ``fallback`` until
    all resources have resolved.

    Usage::

        resource = create_resource(fetch_data)

        Suspense(
            fallback=lambda: Text("Loading..."),
            children=[
                Text(lambda: f"Data: {resource.data()}")
            ],
        )
    """

    __slots__ = ("_fallback_fn", "_child_nodes", "_pending_signals", "_show_fallback", "_unsub")

    def __init__(
        self,
        *,
        fallback: Callable[[], Any] | BaseRenderable | None = None,
        children: list | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)

        self._fallback_fn = fallback
        self._pending_signals: list[Signal] = []
        self._show_fallback = False
        self._unsub: Callable[[], None] | None = None

        # Push suspense context so create_resource can register
        _suspense_stack.append(self._pending_signals)
        try:
            self._child_nodes: list[BaseRenderable] = []
            if children:
                for child in children:
                    if child is not None:
                        self._child_nodes.append(child)
        finally:
            _suspense_stack.pop()

        if self._pending_signals:
            signals = list(self._pending_signals)

            def _any_loading() -> bool:
                return any(sig() for sig in signals)

            self._show_fallback = _any_loading()

            def _on_loading_change(_: Any) -> None:
                self._show_fallback = _any_loading()
                self._update_children()

            unsubs: list[Callable[[], None]] = []
            for sig in signals:
                unsubs.append(sig.subscribe(_on_loading_change))

            def _cleanup() -> None:
                for u in unsubs:
                    u()

            self._unsub = _cleanup
        else:
            self._show_fallback = False

        self._update_children()

    def _update_children(self) -> None:
        child_node_ids = {id(n) for n in self._child_nodes}
        for c in list(self._children):
            self.remove(c)
            if id(c) not in child_node_ids and not c._destroyed:
                c.destroy_recursively()

        if self._show_fallback:
            if self._fallback_fn is not None:
                if callable(self._fallback_fn) and not isinstance(
                    self._fallback_fn, BaseRenderable
                ):
                    fb = self._fallback_fn()
                else:
                    fb = self._fallback_fn
                if fb is not None:
                    for c in _normalize_render_result(fb):
                        self.add(c)
        else:
            for child in self._child_nodes:
                self.add(child)

        self.mark_dirty()

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._unsub:
            self._unsub()
            self._unsub = None
        current = {id(c) for c in self._children}
        for child in self._child_nodes:
            if id(child) not in current and not child._destroyed:
                child.destroy_recursively()
        self._child_nodes.clear()
        super().destroy()


__all__ = [
    "Dynamic",
    "ErrorBoundary",
    "For",
    "Match",
    "MemoBlock",
    "MountedTemplate",
    "Portal",
    "Show",
    "Suspense",
    "Switch",
    "Template",
    "TemplateBinding",
    "bind",
    "reactive",
    "template",
    "template_component",
]
