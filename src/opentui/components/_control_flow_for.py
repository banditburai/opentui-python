from __future__ import annotations

import logging
from typing import Any

from .base import BaseRenderable


def _attach_yoga_child(parent_yoga: Any, child: BaseRenderable, index: int) -> None:
    if child._yoga_node is not None:
        owner = child._yoga_node.owner
        if owner is not None:
            owner.remove_child(child._yoga_node)
        parent_yoga.insert_child(child._yoga_node, index)


def _mark_children_changed(node: Any) -> None:
    node._children_tuple = None
    node.mark_dirty()
    if node._parent is not None:
        node._parent.mark_dirty()


def patch_for_item(node: Any, child: BaseRenderable, item: Any) -> None:
    from ..reconciler import _patch_node, reconcile

    new_child = node._render_fn(item)
    new_child.key = child.key
    _patch_node(child, new_child)
    old_grandchildren = list(child._children)
    new_grandchildren = list(new_child._children)
    if old_grandchildren or new_grandchildren:
        child._children.clear()
        child._children_tuple = None
        reconcile(child, old_grandchildren, new_grandchildren)


def patch_existing_for_children(
    node: Any,
    children: list[BaseRenderable],
    items: list[Any],
) -> int:
    prev = node._last_items
    patched = 0
    for idx, (child, item) in enumerate(zip(children, items, strict=True)):
        if prev is not None and idx < len(prev) and item is prev[idx]:
            continue
        patch_for_item(node, child, item)
        patched += 1
    return patched


def _for_patch_in_place(
    node: Any, new_key_list: list, items: list, log: logging.Logger,
) -> bool:
    """Fast path: keys match exactly — patch existing children in place."""
    old_key_list = [child.key for child in node._children]
    if new_key_list != old_key_list:
        return False
    patched = patch_existing_for_children(node, node._children, items)
    node._last_items = items
    log.debug("For[%s] fast-path: %d/%d keys patched", node.key, patched, len(new_key_list))
    return True


def _for_append(
    node: Any, new_key_list: list, old_key_list: list, items: list, log: logging.Logger,
) -> bool:
    """Fast path: new items appended to end."""
    if len(new_key_list) <= len(old_key_list):
        return False
    if new_key_list[: len(old_key_list)] != old_key_list:
        return False

    patched = patch_existing_for_children(node, node._children, items[: len(old_key_list)])
    created = 0

    for idx in range(len(old_key_list), len(items)):
        item = items[idx]
        child = node._render_fn(item)
        child.key = new_key_list[idx]
        child._parent = node
        node._children.append(child)
        created += 1
        if node._yoga_node is not None:
            _attach_yoga_child(node._yoga_node, child, node._yoga_node.child_count)

    if created:
        _mark_children_changed(node)

    node._last_items = items
    log.debug(
        "For[%s] append fast-path: patched=%d created=%d total=%d",
        node.key, patched, created, len(node._children),
    )
    return True


def _for_truncate(
    node: Any, new_key_list: list, old_key_list: list, items: list, log: logging.Logger,
) -> bool:
    """Fast path: items removed from end."""
    if len(new_key_list) >= len(old_key_list):
        return False
    if old_key_list[: len(new_key_list)] != new_key_list:
        return False

    patched = patch_existing_for_children(node, node._children[: len(new_key_list)], items)
    destroyed = 0

    removed_children = node._children[len(new_key_list) :]
    if removed_children:
        node._children = node._children[: len(new_key_list)]
        _mark_children_changed(node)
        if node._yoga_node is not None:
            for child in removed_children:
                if child._yoga_node is not None:
                    node._yoga_node.remove_child(child._yoga_node)
        for child in removed_children:
            child._parent = None
            child.destroy()
            destroyed += 1

    node._last_items = items
    log.debug(
        "For[%s] truncate fast-path: patched=%d destroyed=%d total=%d",
        node.key, patched, destroyed, len(node._children),
    )
    return True


def _for_prepend(
    node: Any, new_key_list: list, old_key_list: list, items: list, log: logging.Logger,
) -> bool:
    """Fast path: items prepended to beginning."""
    if len(new_key_list) <= len(old_key_list):
        return False
    if new_key_list[len(new_key_list) - len(old_key_list) :] != old_key_list:
        return False

    prepended = len(new_key_list) - len(old_key_list)
    patched = patch_existing_for_children(node, node._children, items[prepended:])
    created = 0

    prepended_children: list[BaseRenderable] = []
    for idx in range(prepended):
        item = items[idx]
        child = node._render_fn(item)
        child.key = new_key_list[idx]
        child._parent = node
        prepended_children.append(child)
        created += 1

    if prepended_children:
        node._children = prepended_children + node._children
        _mark_children_changed(node)
        if node._yoga_node is not None:
            for idx, child in enumerate(prepended_children):
                _attach_yoga_child(node._yoga_node, child, idx)

    node._last_items = items
    log.debug(
        "For[%s] prepend fast-path: patched=%d created=%d total=%d",
        node.key, patched, created, len(node._children),
    )
    return True


def _for_full_reconcile(
    node: Any, new_key_list: list, items: list, log: logging.Logger,
) -> None:
    """General reconciliation: arbitrary reorder, add, remove."""
    old_by_key = {c.key: c for c in node._children if c.key is not None}
    new_keys = set(new_key_list)
    new_children = []
    reused = 0
    created = 0

    for idx, item in enumerate(items):
        k = node._key_fn(item)
        if k is None:
            k = f"__for_index_{idx}"
        existing = old_by_key.get(k)
        if existing is not None:
            patch_for_item(node, existing, item)
            new_children.append(existing)
            reused += 1
        else:
            child = node._render_fn(item)
            child.key = k
            new_children.append(child)
            created += 1

    removed = [child for child in node._children if child.key is not None and child.key not in new_keys]

    node._children = new_children
    _mark_children_changed(node)
    for child in new_children:
        child._parent = node

    if node._yoga_node is not None:
        node._yoga_node.remove_all_children()
        for child in new_children:
            _attach_yoga_child(node._yoga_node, child, node._yoga_node.child_count)

    for child in removed:
        child._parent = None
        child.destroy()

    node._last_items = items
    log.debug(
        "For[%s] reconcile: reused=%d created=%d destroyed=%d total=%d",
        node.key, reused, created, len(removed), len(new_children),
    )


def reconcile_for_children(node: Any, diag: Any, log: logging.Logger) -> None:
    source = node._each_source
    raw: Any = source() if callable(source) else source
    items: list[Any] = list(raw)

    if diag._enabled & diag.VISIBILITY:
        diag.log_for_reconcile(node, len(node._children), len(items))

    new_key_list = [node._key_fn(item) for item in items]
    new_key_list = [k if k is not None else f"__for_index_{i}" for i, k in enumerate(new_key_list)]
    old_key_list = [child.key for child in node._children]

    if _for_patch_in_place(node, new_key_list, items, log):
        return
    if _for_append(node, new_key_list, old_key_list, items, log):
        return
    if _for_truncate(node, new_key_list, old_key_list, items, log):
        return
    if _for_prepend(node, new_key_list, old_key_list, items, log):
        return
    _for_full_reconcile(node, new_key_list, items, log)


__all__ = ["reconcile_for_children"]
