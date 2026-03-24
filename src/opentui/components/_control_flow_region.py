from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .._signal_types import Signal
from .._signals_runtime import _tracking_context
from ._renderable_base import _sync_yoga_children
from .base import BaseRenderable
from .structural import _subtree_contains_portal


def normalize_render_result(
    result: BaseRenderable | list[BaseRenderable] | tuple[BaseRenderable, ...] | None,
) -> list[BaseRenderable]:
    if result is None:
        return []
    if isinstance(result, BaseRenderable):
        return [result]
    return list(result)


def detach_children(parent: BaseRenderable) -> list[BaseRenderable]:
    detached = list(parent._children)
    for child in detached:
        if child._yoga_node is not None and parent._yoga_node is not None:
            parent._yoga_node.remove_child(child._yoga_node)
        child._parent = None
    parent._children.clear()
    parent._children_tuple = None
    return detached


def split_cacheable_branch_children(
    children: list[BaseRenderable],
) -> tuple[list[BaseRenderable], list[BaseRenderable]]:
    reusable, disposable = [], []
    for child in children:
        (disposable if _subtree_contains_portal(child) else reusable).append(child)
    return reusable, disposable


def evict_lru_branches(cache: dict[Any, list[BaseRenderable]], max_size: int) -> None:
    while len(cache) > max_size:
        oldest_key = next(iter(cache))
        evicted = cache.pop(oldest_key)
        for child in evicted:
            if not child._destroyed:
                child.destroy()


def normalize_inserted_children(
    result: BaseRenderable | list[Any] | tuple[Any, ...] | str | Any | None,
) -> tuple[str, str | BaseRenderable | list[BaseRenderable]]:
    if result is None:
        return "children", []
    if isinstance(result, BaseRenderable):
        return "single_node", result
    if isinstance(result, list | tuple):
        children: list[BaseRenderable] = []
        for item in result:
            mode, payload = normalize_inserted_children(item)
            if mode == "text":
                from .text import Text

                children.append(Text(payload))
            elif mode == "single_node":
                children.append(payload)
            else:
                children.extend(payload)
        return "children", children
    return "text", str(result)


def apply_region_children(
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
        if can_fast_patch_plain_text(old_children[0], new_children[0]):
            fast_patch_plain_text(old_children[0], new_children[0])
            parent._children = [old_children[0]]
            parent._children_tuple = None
            parent.mark_dirty()
            return
        if can_fast_patch_plain_box(old_children[0], new_children[0]):
            fast_patch_plain_box(parent, old_children[0], new_children[0])
            parent._children = [old_children[0]]
            parent._children_tuple = None
            parent.mark_dirty()
            return
        parent._children = [_reconcile_matched_child(parent, old_children[0], new_children[0])]
        parent._children_tuple = None
        parent.mark_dirty()
        return

    reconcile(parent, old_children, new_children)


def replace_region_children(
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
        _sync_yoga_children(parent._yoga_node, new_children)

    for child in old_children:
        child._parent = None
        child.destroy()


def can_fast_patch_plain_text(old: BaseRenderable, new: BaseRenderable) -> bool:
    from .text import Text

    return (
        isinstance(old, Text)
        and isinstance(new, Text)
        and old.key == new.key
        and not old._children
        and not new._children
        and not old._text_modifiers
        and not new._text_modifiers
        and not old._prop_bindings
        and not new._prop_bindings
    )


def fast_patch_plain_text(old: BaseRenderable, new: BaseRenderable) -> None:
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
            if attr == "_visible" and getattr(old, "_live", False):
                old._propagate_live_count(1 if new_val else -1)

    if old._content != new._content:
        old.content = new._content
        layout_changed = True

    if layout_changed:
        old.mark_dirty()
    elif paint_changed:
        old.mark_paint_dirty()


def can_fast_patch_plain_box(old: BaseRenderable, new: BaseRenderable) -> bool:
    from .box import Box

    return (
        type(old) is Box
        and type(new) is Box
        and old.key == new.key
        and not (old._prop_bindings or new._prop_bindings)
    )


def fast_patch_plain_box(parent: BaseRenderable, old: BaseRenderable, new: BaseRenderable) -> None:
    from ..reconciler import _patchable_slots

    changed = False
    for attr in _patchable_slots(type(old)):
        old_val = object.__getattribute__(old, attr)
        new_val = object.__getattribute__(new, attr)
        if old_val is new_val or old_val == new_val:
            continue
        object.__setattr__(old, attr, new_val)
        changed = True

    apply_region_children(old, list(new._children))
    old._parent = parent
    if changed:
        old.mark_dirty()


def track_signals(fn: Callable[[], Any]) -> tuple[set[Signal], Any]:
    tracked: set[Signal] = set()
    token = _tracking_context.set(tracked)
    try:
        result = fn()
    finally:
        _tracking_context.reset(token)
    return tracked, result


def subscribe_signals(
    tracked: set[Signal],
    callback: Callable[[], None],
) -> Callable[[], None] | None:
    if not tracked:
        return None
    unsubs = [sig.subscribe(lambda _, cb=callback: cb()) for sig in tracked]

    def cleanup() -> None:
        for unsub in unsubs:
            unsub()

    return cleanup


__all__ = [
    "apply_region_children",
    "detach_children",
    "evict_lru_branches",
    "normalize_inserted_children",
    "normalize_render_result",
    "replace_region_children",
    "split_cacheable_branch_children",
    "subscribe_signals",
    "track_signals",
]
