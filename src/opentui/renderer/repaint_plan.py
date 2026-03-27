"""Repaint plan computation — decides which subtrees to re-render after layout."""

from typing import Any

from .layout import supports_common_tree_strategy
from .native import LayoutRepaintFact, _has_instance_render_override
from .repaint import (
    dedupe_common_roots,
    dedupe_common_roots_from_facts,
    layout_repaint_rect_from_fact,
    node_bounds_rect,
    promote_layout_repaint_root_from_facts,
)


def compute_layout_common_repaint_plan(
    root,
    layout_repaint_facts: list[LayoutRepaintFact],
    *,
    force_next_render: bool,
    has_post_process_fns: bool,
    tree_has_custom_update_layout: bool | None,
    pending_structural_clear_rects: list[tuple[int, int, int, int]],
    prepare_common_tree_render_fn,
) -> list[tuple[Any, tuple[int, int, int, int]]] | None:
    """Top-level entry point: decide whether a layout-driven incremental repaint
    plan can be used and, if so, compute it.

    Returns a list of ``(node_or_None, rect)`` pairs, or *None* when a full
    repaint is required.

    Parameters mirror the renderer state that the original method accessed via
    ``self._*`` attributes:

    * *root* -- the root renderable (already known non-None by the caller).
    * *layout_repaint_facts* -- facts produced by ``apply_yoga_layout_native``.
    * *force_next_render* -- ``renderer._force_next_render``.
    * *has_post_process_fns* -- ``bool(renderer._post_process_fns)``.
    * *tree_has_custom_update_layout* -- ``renderer._tree_has_custom_update_layout``.
    * *pending_structural_clear_rects* -- ``renderer._pending_structural_clear_rects``.
    * *prepare_common_tree_render_fn* -- bound ``renderer._prepare_common_tree_render``.
    """
    if (
        force_next_render
        or has_post_process_fns
        or tree_has_custom_update_layout
        or not layout_repaint_facts
    ):
        return None
    if not prepare_common_tree_render_fn(root):
        return None

    return _compute_from_facts(root, layout_repaint_facts, pending_structural_clear_rects)


def _compute_from_facts(
    root,
    facts: list[LayoutRepaintFact],
    pending_structural_clear_rects: list[tuple[int, int, int, int]],
) -> list[tuple[Any | None, tuple[int, int, int, int]]] | None:
    """Dispatch to the small-list or large-list strategy."""
    if len(facts) <= 8:
        return _compute_small_facts(root, facts, pending_structural_clear_rects)

    root_id = id(root)
    facts_by_id: dict[int, LayoutRepaintFact] = {id(fact[0]): fact for fact in facts}
    if root_id in facts_by_id:
        return _compute_structural_plan(root, facts_by_id[root_id], pending_structural_clear_rects)

    promoted: list[Any] = []
    for fact in facts_by_id.values():
        promoted_node = promote_layout_repaint_root_from_facts(fact, facts_by_id, root_id, root)
        if promoted_node is root:
            return None
        promoted.append(promoted_node)

    roots = dedupe_common_roots_from_facts(promoted, facts_by_id, root_id)
    if not roots:
        return None

    fact_by_node = {fact[0]: fact for fact in facts}
    return [
        (
            node,
            layout_repaint_rect_from_fact(fact_by_node.get(node))
            if node in fact_by_node
            else node_bounds_rect(node),
        )
        for node in roots
    ]


def _compute_small_facts(
    root,
    facts: list[LayoutRepaintFact],
    pending_structural_clear_rects: list[tuple[int, int, int, int]],
) -> list[tuple[Any | None, tuple[int, int, int, int]]] | None:
    """Optimised path for <= 8 layout-repaint facts (avoids dict overhead)."""
    root_id = id(root)
    node_ids = [id(fact[0]) for fact in facts]

    for idx, node_id in enumerate(node_ids):
        if node_id == root_id:
            return _compute_structural_plan(root, facts[idx], pending_structural_clear_rects)

    promoted: list[Any] = []
    for fact in facts:
        current_fact = fact
        current_node = fact[0]
        parent_id = fact[1]
        while parent_id and parent_id != root_id:
            parent_fact = None
            for idx, node_id in enumerate(node_ids):
                if node_id == parent_id:
                    parent_fact = facts[idx]
                    break
            if parent_fact is None:
                break
            current_fact = parent_fact
            current_node = current_fact[0]
            parent_id = current_fact[1]

        has_children = bool(current_fact[2])
        if parent_id == root_id and not has_children:
            return None
        if not has_children and parent_id and parent_id != root_id:
            parent = getattr(current_node, "_parent", None)
            if parent is not None:
                current_node = parent
        promoted.append(current_node)

    roots = dedupe_common_roots(promoted, root)
    if not roots:
        return None

    plan: list[tuple[Any | None, tuple[int, int, int, int]]] = []
    for node in roots:
        node_fact = None
        for fact in facts:
            if fact[0] is node:
                node_fact = fact
                break
        rect = (
            layout_repaint_rect_from_fact(node_fact)
            if node_fact is not None
            else node_bounds_rect(node)
        )
        plan.append((node, rect))
    return plan


def _compute_structural_plan(
    root,
    root_fact: LayoutRepaintFact,
    pending_structural_clear_rects: list[tuple[int, int, int, int]],
) -> list[tuple[Any | None, tuple[int, int, int, int]]] | None:
    """Handle the case where the root itself appears in the layout facts."""
    if root_fact[4:8] != root_fact[8:12]:
        return None

    plan: list[tuple[Any | None, tuple[int, int, int, int]]] = [
        (None, rect) for rect in pending_structural_clear_rects
    ]
    dirty_roots: list[Any] = []
    collect_structural_common_roots(root, dirty_roots)
    for node in dedupe_common_roots(dirty_roots, root):
        plan.append((node, node_bounds_rect(node)))
    return plan or None


def collect_structural_common_roots(node, out: list[Any]) -> None:
    """Walk the tree collecting dirty subtree roots eligible for common-tree render."""
    for child in getattr(node, "_children", ()):
        if getattr(child, "_destroyed", False):
            continue
        if not (
            getattr(child, "_dirty", False)
            or getattr(child, "_subtree_dirty", False)
            or getattr(child, "_paint_subtree_dirty", False)
        ):
            continue
        if supports_common_tree_strategy(child) and not _has_instance_render_override(child):
            out.append(child)
            continue
        collect_structural_common_roots(child, out)


def collect_dirty_common_roots(node, out: list[Any]) -> None:
    """Walk the tree collecting paint-dirty subtree roots for incremental repaint."""
    if getattr(node, "_dirty", False):
        out.append(node)
        return
    for child in getattr(node, "_children", ()):
        if getattr(child, "_dirty", False) or getattr(child, "_paint_subtree_dirty", False):
            collect_dirty_common_roots(child, out)
