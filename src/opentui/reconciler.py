"""Key-based reconciliation for component trees.

Idiomorph-inspired approach: matches old and new children by (type, key)
tuple, patches matched nodes in-place, destroys unmatched old nodes,
and inserts unmatched new nodes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .components.base import BaseRenderable

log = logging.getLogger(__name__)


def _node_key(node: BaseRenderable) -> tuple[type, str | int | None]:
    """Return the reconciliation key for a node: (type, key)."""
    return (type(node), getattr(node, "key", None))


def reconcile(
    parent: BaseRenderable,
    old_children: list[BaseRenderable],
    new_children: list[BaseRenderable],
) -> None:
    """Reconcile old_children with new_children under parent.

    - Matched nodes (same type + key): patch props, keep identity
    - Unmatched old: destroy
    - Unmatched new: insert as-is
    """
    # Build index of old children by (type, key)
    old_by_key: dict[tuple[type, str | int | None], BaseRenderable] = {}
    old_unkeyed: list[BaseRenderable] = []

    for child in old_children:
        key = _node_key(child)
        if key[1] is not None:
            old_by_key[key] = child
        else:
            old_unkeyed.append(child)

    matched_old: set[int] = set()  # IDs of matched old nodes
    result: list[BaseRenderable] = []
    unkeyed_idx = 0

    for new_child in new_children:
        key = _node_key(new_child)
        matched = None

        if key[1] is not None and key in old_by_key:
            # Keyed match
            matched = old_by_key.pop(key)
        elif key[1] is None:
            # Try to match an unkeyed old node of the same type
            while unkeyed_idx < len(old_unkeyed):
                candidate = old_unkeyed[unkeyed_idx]
                unkeyed_idx += 1
                if type(candidate) is type(new_child):
                    matched = candidate
                    break

        if matched is not None:
            matched_old.add(id(matched))
            # Patch: copy props from new to old, keeping old identity
            _patch_node(matched, new_child)
            # Recurse into children
            if hasattr(new_child, "_children"):
                old_grandchildren = list(matched._children)
                new_grandchildren = list(new_child._children)
                matched._children.clear()
                reconcile(matched, old_grandchildren, new_grandchildren)
            matched._parent = parent
            result.append(matched)
        else:
            # New node — insert as-is
            new_child._parent = parent
            result.append(new_child)

    # Destroy unmatched old nodes
    for child in old_children:
        if id(child) not in matched_old:
            child._parent = None
            child.destroy_recursively()

    parent._children = result


def _patch_node(old: BaseRenderable, new: BaseRenderable) -> None:
    """Copy layout/style properties from new node to old node, preserving old identity."""
    # Patch common Renderable properties if both have them
    _patchable_attrs = (
        "_width",
        "_height",
        "_min_width",
        "_min_height",
        "_max_width",
        "_max_height",
        "_flex_grow",
        "_flex_shrink",
        "_flex_direction",
        "_flex_wrap",
        "_flex_basis",
        "_justify_content",
        "_align_items",
        "_align_self",
        "_gap",
        "_overflow",
        "_position",
        "_padding",
        "_padding_top",
        "_padding_right",
        "_padding_bottom",
        "_padding_left",
        "_margin",
        "_margin_top",
        "_margin_right",
        "_margin_bottom",
        "_margin_left",
        "_background_color",
        "_fg",
        "_border",
        "_border_style",
        "_border_color",
        "_title",
        "_title_alignment",
        "_visible",
        "_opacity",
        "_z_index",
    )
    for attr in _patchable_attrs:
        if hasattr(new, attr):
            try:
                setattr(old, attr, getattr(new, attr))
            except AttributeError:
                pass  # Slot may not exist on BaseRenderable
    old.mark_dirty()
