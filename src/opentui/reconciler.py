"""Key-based reconciliation for component trees.

Idiomorph-inspired approach: matches old and new children by (type, key)
tuple, patches matched nodes in-place, destroys unmatched old nodes,
and inserts unmatched new nodes.
"""

from __future__ import annotations

import types
from collections import defaultdict, deque
from typing import TYPE_CHECKING

from .components.base import _SIMPLE_DEFAULTS
from .components.control_flow import For, Portal
from .components.scrollbox import ScrollBox

if TYPE_CHECKING:
    from .components.base import BaseRenderable

_SENTINEL = object()

_NOT_LOADED = object()
_native_patch_fn = _NOT_LOADED

# Lazy-cached Text type for _patch_text_fast_path (avoids per-call import)
_Text_type: type | None = None


def _load_native_patch() -> None:
    global _native_patch_fn
    _native_patch_fn = None
    try:
        from . import ffi

        mod = getattr(ffi.get_native(), "reconciler_patch", None)
        if mod is None:
            return
        init_fn = getattr(mod, "init_skip_attrs", None)
        patch_fn = getattr(mod, "patch_node_fast", None)
        if init_fn is None or patch_fn is None:
            return
        init_fn(list(_SKIP_ATTRS), types.MethodType)
        _native_patch_fn = patch_fn
    except Exception:
        pass


# Attributes that must NOT be copied during patching — these are either
# identity / tree-structure fields managed by the reconciler itself, or
# computed values that the layout engine will overwrite each frame.
_SKIP_ATTRS: frozenset[str] = frozenset(
    {
        # Identity & tree structure (managed by reconciler)
        "_id",
        "_num",
        "key",
        "_parent",
        "_children",
        # Internal state (preserved from old node)
        "_event_handlers",
        "_cleanups",
        "_dirty",
        "_subtree_dirty",
        "_destroyed",
        # Layout engine state (recomputed by yoga each frame)
        "_yoga_node",
        "_x",
        "_y",
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
        # Portal runtime state (preserved from old node).
        # Note: _mount_source and _ref_fn are intentionally NOT skipped —
        # they should update on reconciliation so Portal picks up new mount
        # targets and ref callbacks from the latest render output.
        "_container",
        "_scroll_content",
        "_current_mount",
        "_host",
        "_content_children",
        # Reactive subscription state (Show/Switch/For fine-grained reactivity)
        "_prop_bindings",
        "_condition_cleanup",
        "_data_cleanup",
        "_current_branch",
        "_current_branch_key",
        "_is_active",
        # Reentrancy guards (Show/Switch/For reactive updates)
        "_updating",
        "_reconciling",
        "_computing",
        # Branch cache (Show/Switch) + For item cache
        "_render_cache",
        "_fallback_cache",
        "_branch_cache",
        "_last_items",
        # ErrorBoundary internal state
        "_error",
        "_has_error",
    }
)

_slots_cache: dict[type, tuple[str, ...]] = {}
_dict_presence_cache: dict[type, bool] = {}

_SIMPLE_TEXT_SLOT_DEFAULTS: tuple[tuple[str, object], ...] = tuple(_SIMPLE_DEFAULTS.items())
_SIMPLE_TEXT_DICT_ATTRS: tuple[str, ...] = (
    "_content",
    "_bold",
    "_italic",
    "_underline",
    "_strikethrough",
    "_selection_start",
    "_selection_end",
    "_selection_bg",
    "_wrap_mode",
    "_text_modifiers",
)


def _patchable_slots(cls: type) -> tuple[str, ...]:
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


def _has_instance_dict(cls: type) -> bool:
    cached = _dict_presence_cache.get(cls)
    if cached is not None:
        return cached
    result = any("__dict__" in klass.__dict__ for klass in cls.__mro__)
    _dict_presence_cache[cls] = result
    return result


def _node_key(node: BaseRenderable) -> tuple[type, str | int | None]:
    return (type(node), node.key)


def _init_nested_fors(node: BaseRenderable) -> None:
    """Recursively find For/Portal nodes in a new subtree and initialize them.

    For nodes are lazy — __init__ does not call _reconcile_children().
    Portal nodes need _ensure_container() called to create their container.
    When a new subtree is inserted (e.g. Box → ScrollBox → For), the
    reconciler only sees the top-level Box.  This function walks the
    subtree to initialize any For/Portal nodes at any depth.
    """
    if isinstance(node, For):
        node._reconcile_children()
    elif isinstance(node, Portal):
        node._ensure_container()
        if node._container is not None:
            for child in node._container._children:
                _init_nested_fors(child)
        return  # Portal's own _children stays empty; don't recurse into it
    for child in node._children:
        _init_nested_fors(child)


def _can_patch_positionally(
    old_children: list[BaseRenderable],
    new_children: list[BaseRenderable],
) -> bool:
    """Return True when children can be matched pairwise in place.

    This is the common rebuild case for stable trees: same arity, same types,
    and same keys in the same order. In that case we can skip key maps and
    avoid rebuilding the parent's yoga child list.
    """
    if len(old_children) != len(new_children):
        return False
    return all(
        type(old_child) is type(new_child) and old_child.key == new_child.key
        for old_child, new_child in zip(old_children, new_children, strict=True)
    )


def _reconcile_matched_child(
    parent: BaseRenderable,
    matched: BaseRenderable,
    new_child: BaseRenderable,
) -> BaseRenderable:
    _patch_node(matched, new_child)

    # Clean up reactive subscriptions on the discarded new node.
    # The old node keeps its own subscriptions (in _SKIP_ATTRS);
    # the new node's subscriptions were created in __init__ and
    # would otherwise be orphaned, leaking into Signal._subscribers.
    for cleanup_attr in ("_condition_cleanup", "_data_cleanup"):
        _cleanup_fn = getattr(new_child, cleanup_attr, None)
        if _cleanup_fn is not None:
            _cleanup_fn()
            object.__setattr__(new_child, cleanup_attr, None)
    # Generic reactive prop bindings — source-identity optimization
    new_prop_bindings = getattr(new_child, "_prop_bindings", None)
    old_prop_bindings = getattr(matched, "_prop_bindings", None)

    if new_prop_bindings:
        for _attr, _new_binding in list(new_prop_bindings.items()):
            _old_binding = old_prop_bindings.get(_attr) if old_prop_bindings else None
            if _old_binding and _old_binding.source is _new_binding.source:
                # Same source object — keep old subscription, unsub new only
                # (must NOT dispose shared source via full cleanup)
                _new_binding.unsub_only()
            else:
                # Different source — unsub new's callback (without disposing
                # the source), then re-bind on old with the still-alive source.
                _new_binding.unsub_only()
                if _old_binding:
                    matched._unbind_reactive_prop(_attr)
                matched._bind_reactive_prop(_attr, _new_binding.source)
            # Remove cleanup from new node's _cleanups to prevent leak
            new_child._cleanups.pop(id(_new_binding.cleanup), None)
        new_child._prop_bindings = None

        # Clean up old bindings for attrs not in new (reactive→static)
        if old_prop_bindings:
            for _attr in list(old_prop_bindings):
                if _attr not in new_prop_bindings:
                    matched._unbind_reactive_prop(_attr)
    elif old_prop_bindings:
        # All reactive→static: clean up everything
        matched._unbind_all_reactive_props()

    if isinstance(matched, For):
        matched._reconcile_children()
    elif isinstance(matched, ScrollBox):
        assert isinstance(new_child, ScrollBox)
        matched._copy_content_layout_from(new_child)
        old_content = list(matched._scroll_content._children)
        new_content = list(new_child._scroll_content._children)
        reconcile(matched._scroll_content, old_content, new_content)
    elif isinstance(matched, Portal):
        assert isinstance(new_child, Portal)
        if matched._container is not None:
            old_content = list(matched._container._children)
            new_content = list(new_child._content_children)
            reconcile(matched._container, old_content, new_content)
        else:
            # Container not yet created — update content children for next _ensure_container
            matched._content_children = list(new_child._content_children)
    else:
        old_grandchildren = list(matched._children)
        new_grandchildren = list(new_child._children)
        reconcile(matched, old_grandchildren, new_grandchildren)

    matched._parent = parent
    return matched


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
    if _can_patch_positionally(old_children, new_children):
        result = [
            _reconcile_matched_child(parent, matched, new_child)
            for matched, new_child in zip(old_children, new_children, strict=True)
        ]
        parent._children = result
        parent._children_tuple = None
        parent._subtree_dirty = True
        return

    old_by_key: dict[tuple[type, str | int | None], BaseRenderable] = {}
    old_unkeyed_by_type: defaultdict[type, deque[BaseRenderable]] = defaultdict(deque)

    for child in old_children:
        key = _node_key(child)
        if key[1] is not None:
            old_by_key[key] = child
        else:
            old_unkeyed_by_type[type(child)].append(child)

    matched_old: set[int] = set()
    result: list[BaseRenderable] = []

    for new_child in new_children:
        key = _node_key(new_child)
        matched = None

        if key[1] is not None and key in old_by_key:
            matched = old_by_key.pop(key)
        elif key[1] is None:
            new_type = type(new_child)
            if new_type in old_unkeyed_by_type and old_unkeyed_by_type[new_type]:
                matched = old_unkeyed_by_type[new_type].popleft()

        if matched is not None:
            matched_old.add(id(matched))
            result.append(_reconcile_matched_child(parent, matched, new_child))
        else:
            new_child._parent = parent
            # Recursively init any For nodes in the new subtree.
            # For nodes are lazy (no _reconcile_children in __init__)
            # so we must build their children when first mounted.
            _init_nested_fors(new_child)
            result.append(new_child)

    parent._children = result
    parent._children_tuple = None
    parent._subtree_dirty = True

    # Sync yoga tree BEFORE destroying unmatched old nodes.
    #
    # This ordering is critical: destroy_recursively() sets _yoga_node=None
    # on destroyed nodes, which releases the Python reference to the C++
    # yoga node.  If the GC collects that node while it's still in the
    # parent's yoga child list, remove_all_children() would dereference
    # freed memory.  By syncing first, we detach all old yoga children
    # from the parent (via remove_all_children) while they're still alive,
    # making the subsequent destroy safe.
    yoga_structure_changed = len(result) != len(old_children) or any(
        child is not old_child for child, old_child in zip(result, old_children, strict=True)
    )

    if parent._yoga_node is not None and yoga_structure_changed:
        yoga_children = []
        for child in result:
            if child._yoga_node is not None:
                yoga_owner = child._yoga_node.owner
                if yoga_owner is not None and yoga_owner is not parent._yoga_node:
                    yoga_owner.remove_child(child._yoga_node)
                yoga_children.append(child._yoga_node)
        parent._yoga_node.set_children(yoga_children)

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
    if _patch_text_fast_path(old, new):
        return

    if _native_patch_fn is _NOT_LOADED:
        _load_native_patch()

    if _native_patch_fn is not None:
        changed, needs_dict = _native_patch_fn(old, new)
        if needs_dict:
            _patch_dict_attrs(old, new, changed)
        elif changed:
            old.mark_dirty()
        return

    get = object.__getattribute__
    set_attr = object.__setattr__

    changed = False
    for attr in _patchable_slots(type(new)):
        new_val = _rebind_bound_method(get(new, attr), old, new)
        if not _same_value(get(old, attr), new_val):
            set_attr(old, attr, new_val)
            changed = True

    if _has_instance_dict(type(new)):
        _patch_dict_attrs(old, new, changed)
    elif changed:
        old.mark_dirty()


def _patch_dict_attrs(old: BaseRenderable, new: BaseRenderable, changed: bool) -> None:
    get = object.__getattribute__
    set_attr = object.__setattr__
    new_dict = get(new, "__dict__")
    old_dict = get(old, "__dict__")
    for attr, value in new_dict.items():
        if attr not in _SKIP_ATTRS:
            new_val = _rebind_bound_method(value, old, new)
            if not _same_value(old_dict.get(attr, _SENTINEL), new_val):
                set_attr(old, attr, new_val)
                changed = True

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


def _same_value(old_value: object, new_value: object) -> bool:
    if old_value is new_value:
        return True
    if old_value is _SENTINEL or new_value is _SENTINEL:
        return False
    try:
        return bool(old_value == new_value)
    except Exception:
        return False


def _patch_text_fast_path(old: BaseRenderable, new: BaseRenderable) -> bool:
    global _Text_type
    if _Text_type is None:
        from .components.text import Text

        _Text_type = Text
    Text = _Text_type

    if type(old) is not Text or type(new) is not Text:
        return False
    if old._children or new._children:
        return False
    if not (_is_simple_text_shape(old) and _is_simple_text_shape(new)):
        return False

    changed = False

    for attr in _SIMPLE_TEXT_DICT_ATTRS:
        new_val = object.__getattribute__(new, attr)
        old_val = object.__getattribute__(old, attr)
        if not _same_value(old_val, new_val):
            object.__setattr__(old, attr, new_val)
            changed = True

    if changed:
        old.mark_dirty()
    return True


def _is_simple_text_shape(node: object) -> bool:
    # Fast path: _is_simple flag is maintained by _set_or_bind during __init__
    try:
        return node._is_simple  # type: ignore[union-attr]
    except AttributeError:
        pass
    get = object.__getattribute__
    for attr, default in _SIMPLE_TEXT_SLOT_DEFAULTS:
        if not _same_value(get(node, attr), default):
            return False
    return True
