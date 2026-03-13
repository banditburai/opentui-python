"""Key-based reconciliation for component trees.

Idiomorph-inspired approach: matches old and new children by (type, key)
tuple, patches matched nodes in-place, destroys unmatched old nodes,
and inserts unmatched new nodes.
"""

from __future__ import annotations

import logging
import types
from typing import TYPE_CHECKING

from .components.control_flow import For

if TYPE_CHECKING:
    from .components.base import BaseRenderable

log = logging.getLogger(__name__)

_SENTINEL = object()

# Attributes that must NOT be copied during patching — these are either
# identity / tree-structure fields managed by the reconciler itself, or
# computed values that the layout engine will overwrite each frame.
_SKIP_ATTRS: frozenset[str] = frozenset({
    # Identity & tree structure (managed by reconciler)
    "_id",
    "key",
    "_parent",
    "_children",
    # Internal state (preserved from old node)
    "_event_handlers",
    "_cleanups",
    "_dirty",
    # Layout engine state (recomputed by yoga each frame)
    "_yoga_node",
    "_x",
    "_y",
    "_layout_x",
    "_layout_y",
    "_layout_width",
    "_layout_height",
    # Image render state (preserved from old node)
    "_graphics_id",
    "_last_draw_signature",
    "_was_suppressed",
    # Scroll position (render-time state, not a tree property)
    "_scroll_offset_y",
    "_scroll_offset_x",
    "_scroll_accumulator_x",
    "_scroll_accumulator_y",
    "_scroll_width",
    "_scroll_height",
    "_viewport_width",
    "_viewport_height",
    "_has_manual_scroll",
    "_is_applying_sticky_scroll",
    "_sticky_scroll_top",
    "_sticky_scroll_bottom",
    "_sticky_scroll_left",
    "_sticky_scroll_right",
    "_scroll_acceleration",
    # desired_scroll_y tracking (preserved from old node)
    "_last_applied_desired_y",
})

# Cache: type → tuple of patchable slot names
_slots_cache: dict[type, tuple[str, ...]] = {}


def _patchable_slots(cls: type) -> tuple[str, ...]:
    """Collect all __slots__ from the MRO, minus the skip set.  Cached per type."""
    cached = _slots_cache.get(cls)
    if cached is not None:
        return cached
    slots: list[str] = []
    seen: set[str] = set()
    for klass in cls.__mro__:
        for slot in getattr(klass, "__slots__", ()):
            if slot not in seen and slot not in _SKIP_ATTRS:
                seen.add(slot)
                slots.append(slot)
    result = tuple(slots)
    _slots_cache[cls] = result
    return result


def _node_key(node: BaseRenderable) -> tuple[type, str | int | None]:
    """Return the reconciliation key for a node: (type, key)."""
    return (type(node), getattr(node, "key", None))


def _init_nested_fors(node: BaseRenderable) -> None:
    """Recursively find For nodes in a new subtree and build their children.

    For nodes are lazy — __init__ does not call _reconcile_children().
    When a new subtree is inserted (e.g. Box → ScrollBox → For), the
    reconciler only sees the top-level Box.  This function walks the
    subtree to initialize any For nodes at any depth.
    """
    if isinstance(node, For):
        node._reconcile_children()
    for child in node._children:
        _init_nested_fors(child)


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

            # For component: self-managed idiomorph reconciliation
            if isinstance(matched, For):
                matched._reconcile_children()
            elif hasattr(new_child, "_children"):
                # Normal recursive reconciliation
                old_grandchildren = list(matched._children)
                new_grandchildren = list(new_child._children)
                matched._children.clear()
                reconcile(matched, old_grandchildren, new_grandchildren)

            matched._parent = parent
            result.append(matched)
        else:
            # New node — insert as-is
            new_child._parent = parent
            # Recursively init any For nodes in the new subtree.
            # For nodes are lazy (no _reconcile_children in __init__)
            # so we must build their children when first mounted.
            _init_nested_fors(new_child)
            result.append(new_child)

    parent._children = result

    # Sync yoga tree BEFORE destroying unmatched old nodes.
    #
    # This ordering is critical: destroy_recursively() sets _yoga_node=None
    # on destroyed nodes, which releases the Python reference to the C++
    # yoga node.  If the GC collects that node while it's still in the
    # parent's yoga child list, remove_all_children() would dereference
    # freed memory.  By syncing first, we detach all old yoga children
    # from the parent (via remove_all_children) while they're still alive,
    # making the subsequent destroy safe.
    if parent._yoga_node is not None:
        parent._yoga_node.remove_all_children()
        for child in result:
            if child._yoga_node is not None:
                yoga_owner = child._yoga_node.owner
                if yoga_owner is not None:
                    yoga_owner.remove_child(child._yoga_node)
                parent._yoga_node.insert_child(child._yoga_node, parent._yoga_node.child_count)

    # Now safe to destroy unmatched old nodes — their yoga nodes are no
    # longer referenced by the parent's yoga tree.
    for child in old_children:
        if id(child) not in matched_old:
            child._parent = None
            child.destroy_recursively()


def _patch_node(old: BaseRenderable, new: BaseRenderable) -> None:
    """Copy all properties from new node to old node, preserving old identity.

    Uses a blacklist approach: every attribute is copied EXCEPT
    structural / computed ones in _SKIP_ATTRS.  This means new component
    attributes are automatically supported without updating the reconciler.

    Handles both __slots__-based attrs (from base classes) and __dict__-based
    attrs (from subclasses that don't define __slots__).
    """
    # 1. Patch slot-based attributes (from BaseRenderable / Renderable)
    changed = False
    for attr in _patchable_slots(type(new)):
        try:
            new_val = _rebind_bound_method(getattr(new, attr), old, new)
            if new_val is not getattr(old, attr, _SENTINEL):
                setattr(old, attr, new_val)
                changed = True
        except AttributeError:
            pass  # Slot exists on new's class but not old's

    # 2. Patch __dict__-based attributes (from subclasses like Text, Code, etc.)
    new_dict = getattr(new, "__dict__", None)
    if new_dict:
        for attr, value in new_dict.items():
            if attr not in _SKIP_ATTRS:
                try:
                    new_val = _rebind_bound_method(value, old, new)
                    if new_val is not getattr(old, attr, _SENTINEL):
                        setattr(old, attr, new_val)
                        changed = True
                except AttributeError:
                    pass

    if changed:
        old.mark_dirty()


def _rebind_bound_method(value: object, old: BaseRenderable, new: BaseRenderable) -> object:
    """Retarget bound methods copied from *new* so they execute on *old*.

    Event handlers like ``_on_mouse_scroll = self._handle_mouse_scroll`` are
    stored as bound methods on the renderable instance. During reconciliation
    we preserve the old mounted node but patch in new attributes. If we copy
    the bound method object verbatim, it stays bound to the transient *new*
    instance, which has no live layout. Rebind those methods to *old*.
    """
    if isinstance(value, types.MethodType) and value.__self__ is new:
        return value.__func__.__get__(old, type(old))
    return value
