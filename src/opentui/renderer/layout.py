"""Dirty-flag tree walks that feed the yoga layout pass."""

from __future__ import annotations

from typing import Any

from .native import _CUSTOM_UPDATE_LAYOUT_CACHE, _DEFAULT_UPDATE_LAYOUT_FN


def collect_top_dirty_layout_nodes(root) -> list[Any]:
    found: list[Any] = []

    def walk(node) -> None:
        if getattr(node, "_dirty", False):
            found.append(node)
            return
        for child in getattr(node, "_children", ()):
            if getattr(child, "_subtree_dirty", False):
                walk(child)

    walk(root)
    return found


def collect_local_layout_subtree(
    root,
) -> tuple[Any, float, float, int, int] | None:
    dirty_nodes = collect_top_dirty_layout_nodes(root)
    if not dirty_nodes:
        return None

    parents = {getattr(node, "_parent", None) for node in dirty_nodes}
    if len(parents) != 1:
        return None

    parent = next(iter(parents))
    if parent is None or parent is root:
        return None
    if getattr(parent, "_dirty", False):
        return None
    if not hasattr(parent, "_layout_width") or not hasattr(parent, "_layout_height"):
        return None

    subtree = parent
    avail_width = float(int(getattr(subtree, "_layout_width", 0) or 0))
    avail_height = float(int(getattr(subtree, "_layout_height", 0) or 0))
    if avail_width <= 0 or avail_height <= 0:
        return None

    origin_parent = getattr(subtree, "_parent", None)
    origin_x = int(getattr(origin_parent, "_x", 0) or 0) if origin_parent is not None else 0
    origin_y = int(getattr(origin_parent, "_y", 0) or 0) if origin_parent is not None else 0
    return (subtree, avail_width, avail_height, origin_x, origin_y)


def clear_handled_layout_dirty_ancestors(node) -> None:
    current = node
    while current is not None:
        if getattr(current, "_subtree_dirty", False):
            current._subtree_dirty = False
        current = getattr(current, "_parent", None)


def clear_all_dirty(renderable) -> None:
    if (
        not getattr(renderable, "_dirty", False)
        and not getattr(renderable, "_subtree_dirty", False)
        and not getattr(renderable, "_paint_subtree_dirty", False)
        and not getattr(renderable, "_hit_paint_dirty", False)
    ):
        return
    renderable._dirty = False
    renderable._subtree_dirty = False
    renderable._paint_subtree_dirty = False
    renderable._hit_paint_dirty = False
    for child in renderable._children:
        if (
            getattr(child, "_dirty", False)
            or getattr(child, "_subtree_dirty", False)
            or getattr(child, "_paint_subtree_dirty", False)
            or getattr(child, "_hit_paint_dirty", False)
        ):
            clear_all_dirty(child)


def has_custom_update_layout(renderable) -> bool:
    cls = type(renderable)
    cached = _CUSTOM_UPDATE_LAYOUT_CACHE.get(cls)
    if cached is not None:
        return cached
    update_layout = getattr(cls, "update_layout", None)
    result = update_layout is not None and update_layout is not _DEFAULT_UPDATE_LAYOUT_FN
    _CUSTOM_UPDATE_LAYOUT_CACHE[cls] = result
    return result


def count_tree_custom_update_layout(renderable) -> int:
    count = 1 if has_custom_update_layout(renderable) else 0
    for child in getattr(renderable, "_children", ()):
        count += count_tree_custom_update_layout(child)
    return count


def supports_common_tree_strategy(renderable) -> bool:
    """Intentionally shallow gate — the native validator already walks the full tree;
    doing another full Python traversal here doubles the hot path cost for large
    common trees.
    """
    # Lazy imports to avoid circular dependency (RootRenderable lives in renderer.py)
    from ..enums import RenderStrategy
    from .core import RootRenderable

    if isinstance(renderable, RootRenderable):
        for child in getattr(renderable, "_children", ()):
            strategy = getattr(child, "get_render_strategy", None)
            if strategy is None:
                continue
            child_strategy = child.get_render_strategy()
            if child_strategy in (RenderStrategy.RETAINED_LAYER, RenderStrategy.HEAVY_WIDGET):
                return False
        return True

    strategy = getattr(renderable, "get_render_strategy", None)
    if strategy is None:
        return True
    node_strategy = renderable.get_render_strategy()
    if node_strategy in (RenderStrategy.RETAINED_LAYER, RenderStrategy.HEAVY_WIDGET):
        return False
    return not (
        node_strategy is RenderStrategy.PYTHON_FALLBACK and getattr(renderable, "_children", None)
    )
