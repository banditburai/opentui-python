"""Debug/diagnostic helpers and layout cache invalidation for the renderer."""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


def invalidate_layout_hook_cache(renderer: Any) -> None:
    renderer._tree_has_custom_update_layout = None
    renderer._tree_custom_update_layout_count = None


def adjust_layout_hook_cache_for_subtree(
    renderer: Any,
    renderable: Any,
    delta: int,
    *,
    count_tree_custom_update_layout: Any,
) -> None:
    if renderer._tree_custom_update_layout_count is None:
        return
    subtree_count = count_tree_custom_update_layout(renderable)
    renderer._tree_custom_update_layout_count = max(
        0,
        renderer._tree_custom_update_layout_count + (subtree_count * delta),
    )
    renderer._tree_has_custom_update_layout = renderer._tree_custom_update_layout_count > 0


def debug_dump_tree(renderer: Any, node: Any, depth: int = 0, max_depth: int = 8) -> None:
    if depth > max_depth:
        _log.warning("%s  ... (max depth)", "  " * depth)
        return
    indent = "  " * depth
    name = type(node).__name__
    lw = getattr(node, "_layout_width", "?")
    lh = getattr(node, "_layout_height", "?")
    x = getattr(node, "_x", "?")
    y = getattr(node, "_y", "?")
    fg = getattr(node, "_flex_grow", "?")
    vis = getattr(node, "_visible", "?")
    key = getattr(node, "_key", None)
    nkids = len(getattr(node, "_children", []))
    yoga_info = ""
    yoga_node = getattr(node, "_yoga_node", None)
    if yoga_node:
        yoga_info = f" yoga={yoga_node.layout_width}x{yoga_node.layout_height}"
    key_str = f" key={key}" if key else ""
    content = ""
    c = getattr(node, "_content", None)
    if c is not None:
        content = f' "{c[:30]}"' if c else ""
    _log.debug(
        "%s%s: %sx%s @(%s,%s) fg=%s vis=%s kids=%d%s%s%s",
        indent,
        name,
        lw,
        lh,
        x,
        y,
        fg,
        vis,
        nkids,
        yoga_info,
        key_str,
        content,
    )
    for child in getattr(node, "_children", []):
        debug_dump_tree(renderer, child, depth + 1, max_depth)


__all__ = [
    "adjust_layout_hook_cache_for_subtree",
    "debug_dump_tree",
    "invalidate_layout_hook_cache",
]
