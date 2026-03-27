"""Geometry helpers that plan incremental repaint regions after yoga layout."""

import contextlib
from typing import Any

from .native import (
    _NATIVE_LAYOUT_CACHE,
    _NOT_LOADED,
    LayoutRepaintFact,
    _load_native_layout_apply,
)


def apply_yoga_layout_native(
    root,
    *,
    origin_x: int = 0,
    origin_y: int = 0,
) -> list[LayoutRepaintFact]:
    fn = _NATIVE_LAYOUT_CACHE["fn"]
    offsets = _NATIVE_LAYOUT_CACHE["offsets"]

    if fn is _NOT_LOADED:
        _load_native_layout_apply(root)
        fn = _NATIVE_LAYOUT_CACHE["fn"]
        offsets = _NATIVE_LAYOUT_CACHE["offsets"]

    if fn is None or offsets is None:
        raise RuntimeError("yoga.apply_layout_tree is required")

    facts = list(fn(root, offsets, origin_x, origin_y))
    # The native walker cannot safely call _on_size_change via slot
    # offsets because RootRenderable (the root type used to discover
    # offsets) doesn't have this slot — reading at a Box-derived offset
    # on a RootRenderable would access out-of-bounds memory.  Fire the
    # callbacks from Python instead using the geometry-change facts.
    for fact in facts:
        node = fact[0]
        old_w, old_h, new_w, new_h = fact[6], fact[7], fact[10], fact[11]
        if old_w != new_w or old_h != new_h:
            cb = getattr(node, "_on_size_change", None)
            if cb is not None:
                with contextlib.suppress(Exception):
                    cb(new_w, new_h)
    return facts


def promote_layout_repaint_root_from_facts(
    fact: LayoutRepaintFact,
    facts_by_id: dict[int, LayoutRepaintFact],
    root_id: int,
    root,
) -> Any:
    current_fact = fact
    current_node = fact[0]
    parent_id = fact[1]
    while parent_id and parent_id != root_id and parent_id in facts_by_id:
        current_fact = facts_by_id[parent_id]
        current_node = current_fact[0]
        parent_id = current_fact[1]

    has_children = bool(current_fact[2])
    if parent_id == root_id and not has_children:
        return root
    if not has_children and parent_id and parent_id != root_id:
        parent = getattr(current_node, "_parent", None)
        if parent is not None:
            return parent
    return current_node


def dedupe_common_roots_from_facts(
    nodes: list[Any],
    facts_by_id: dict[int, LayoutRepaintFact],
    root_id: int,
) -> list[Any]:
    unique: dict[int, Any] = {}
    for node in nodes:
        unique.setdefault(id(node), node)
    kept: list[Any] = []
    unique_ids = set(unique)
    for node in unique.values():
        parent = getattr(node, "_parent", None)
        while parent is not None and id(parent) not in unique_ids and id(parent) != root_id:
            parent = getattr(parent, "_parent", None)
        if parent is None or id(parent) == root_id:
            kept.append(node)
    return kept


def dedupe_common_roots(nodes: list[Any], root) -> list[Any]:
    unique: dict[int, Any] = {}
    for node in nodes:
        unique.setdefault(id(node), node)
    kept: list[Any] = []
    unique_ids = set(unique)
    root_id = id(root)
    for node in unique.values():
        parent = getattr(node, "_parent", None)
        while parent is not None and id(parent) not in unique_ids and id(parent) != root_id:
            parent = getattr(parent, "_parent", None)
        if parent is None or id(parent) == root_id:
            kept.append(node)
    return kept


def layout_repaint_rect_from_fact(
    fact: LayoutRepaintFact | None,
) -> tuple[int, int, int, int]:
    if fact is None:
        return (0, 0, 0, 0)
    return union_rects(
        (fact[4], fact[5], fact[6], fact[7]),
        (fact[8], fact[9], fact[10], fact[11]),
    )


def node_bounds_rect(node) -> tuple[int, int, int, int]:
    return (
        int(getattr(node, "_x", 0) or 0),
        int(getattr(node, "_y", 0) or 0),
        int(getattr(node, "_layout_width", 0) or 0),
        int(getattr(node, "_layout_height", 0) or 0),
    )


def union_rects(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    x1, y1, w1, h1 = first
    x2, y2, w2, h2 = second
    if w1 <= 0 or h1 <= 0:
        return second
    if w2 <= 0 or h2 <= 0:
        return first
    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1 + w1, x2 + w2)
    bottom = max(y1 + h1, y2 + h2)
    return (left, top, right - left, bottom - top)
