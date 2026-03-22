"""Lazy-loaded native acceleration caches for yoga layout and common-tree rendering."""

from __future__ import annotations

import logging
from typing import Any

from ..components.base import Renderable

_log = logging.getLogger(__name__)

_CUSTOM_UPDATE_LAYOUT_CACHE: dict[type, bool] = {}

LayoutRepaintFact = tuple[Any, int, bool, bool, int, int, int, int, int, int, int, int]

# Lazy-loaded native layout apply entrypoint from yoga-python.
_NOT_LOADED = object()
_NATIVE_LAYOUT_CACHE: dict[str, Any] = {
    "fn": _NOT_LOADED,
    "offsets": None,
}
_COMMON_RENDER_CACHE: dict[str, Any] = {
    "validate_fn": _NOT_LOADED,
    "render_fn": _NOT_LOADED,
    "hybrid_fn": _NOT_LOADED,
    "offsets": None,
    "root_type": None,
    "box_type": None,
    "text_type": None,
    "portal_type": None,
}


def _load_native_layout_apply(root) -> None:

    _NATIVE_LAYOUT_CACHE["fn"] = None  # mark as loaded (no longer _NOT_LOADED)
    try:
        from ..ffi import get_native

        nb = get_native()
        discover = (
            getattr(getattr(nb, "native_signals", None), "discover_slot_offset", None)
            if nb
            else None
        )
        if discover is None:
            _log.debug("_load_native_layout_apply: opentui_bindings=%s, discover=%s", nb, discover)
            return
        import yoga

        fn = getattr(yoga, "apply_layout_tree", None)
        if fn is None:
            _log.debug("_load_native_layout_apply: yoga.apply_layout_tree not found")
            return
        tp = type(root)
        offsets = {
            "_x": discover(tp, "_x"),
            "_y": discover(tp, "_y"),
            "_layout_width": discover(tp, "_layout_width"),
            "_layout_height": discover(tp, "_layout_height"),
            "_dirty": discover(tp, "_dirty"),
            "_subtree_dirty": discover(tp, "_subtree_dirty"),
            "_children": discover(tp, "_children"),
            "_parent": discover(tp, "_parent"),
            "_yoga_node": discover(tp, "_yoga_node"),
            "_on_size_change": -1,
        }
        required_offsets = (
            "_x",
            "_y",
            "_layout_width",
            "_layout_height",
            "_dirty",
            "_subtree_dirty",
            "_children",
            "_parent",
            "_yoga_node",
        )
        missing = [name for name in required_offsets if offsets[name] < 0]
        if missing:
            _log.debug("_load_native_layout_apply: missing offsets for %s on %s", missing, tp)
            return
        _NATIVE_LAYOUT_CACHE["fn"] = fn
        _NATIVE_LAYOUT_CACHE["offsets"] = offsets
        _log.debug("_load_native_layout_apply: SUCCESS fn=%s", fn)
    except Exception:
        _log.debug("_load_native_layout_apply: exception", exc_info=True)


def _load_common_render(root) -> None:
    _COMMON_RENDER_CACHE["validate_fn"] = None
    _COMMON_RENDER_CACHE["render_fn"] = None
    _COMMON_RENDER_CACHE["hybrid_fn"] = None
    try:
        from ..ffi import get_native

        nb = get_native()
        discover = nb.native_signals.discover_slot_offset if nb else None
        validate_fn = nb.common_render.validate_common_tree if nb else None
        render_fn = nb.common_render.render_common_tree_unchecked if nb else None
        hybrid_fn = getattr(nb.common_render, "render_hybrid_tree", None) if nb else None
        if discover is None or validate_fn is None or render_fn is None:
            return

        from ..components.box import Box
        from ..components.control_flow import Portal
        from ..components.text import Text

        root_type = type(root)
        offsets = {
            "_visible": discover(Text, "_visible"),
            "_children": discover(Text, "_children"),
            "_x": discover(Text, "_x"),
            "_y": discover(Text, "_y"),
            "_layout_width": discover(Text, "_layout_width"),
            "_layout_height": discover(Text, "_layout_height"),
            "_padding_left": discover(Text, "_padding_left"),
            "_padding_right": discover(Text, "_padding_right"),
            "_padding_top": discover(Text, "_padding_top"),
            "_content": discover(Text, "_content"),
            "_fg": discover(Text, "_fg"),
            "_background_color": discover(Text, "_background_color"),
            "_wrap_mode": discover(Text, "_wrap_mode"),
            "_selection_start": discover(Text, "_selection_start"),
            "_selection_end": discover(Text, "_selection_end"),
            "_bold": discover(Text, "_bold"),
            "_italic": discover(Text, "_italic"),
            "_underline": discover(Text, "_underline"),
            "_strikethrough": discover(Text, "_strikethrough"),
            "_border": discover(Box, "_border"),
            "_border_style": discover(Box, "_border_style"),
            "_border_color": discover(Box, "_border_color"),
            "_title": discover(Box, "_title"),
            "_title_alignment": discover(Box, "_title_alignment"),
            "_border_top": discover(Box, "_border_top"),
            "_border_right": discover(Box, "_border_right"),
            "_border_bottom": discover(Box, "_border_bottom"),
            "_border_left": discover(Box, "_border_left"),
            "_focused": discover(Box, "_focused"),
            "_overflow": discover(Box, "_overflow"),
            "_render_before": discover(Box, "_render_before"),
            "_render_after": discover(Box, "_render_after"),
        }
        required = (
            "_visible",
            "_children",
            "_x",
            "_y",
            "_layout_width",
            "_layout_height",
            "_padding_left",
            "_padding_right",
            "_padding_top",
            "_content",
            "_wrap_mode",
            "_selection_start",
            "_selection_end",
            "_bold",
            "_italic",
            "_underline",
            "_strikethrough",
            "_border",
            "_border_style",
            "_border_color",
            "_title",
            "_title_alignment",
            "_border_top",
            "_border_right",
            "_border_bottom",
            "_border_left",
            "_focused",
            "_overflow",
            "_render_before",
            "_render_after",
        )
        if any(offsets[name] < 0 for name in required):
            return
        _COMMON_RENDER_CACHE["validate_fn"] = validate_fn
        _COMMON_RENDER_CACHE["render_fn"] = render_fn
        _COMMON_RENDER_CACHE["hybrid_fn"] = hybrid_fn
        _COMMON_RENDER_CACHE["offsets"] = offsets
        _COMMON_RENDER_CACHE["root_type"] = root_type
        _COMMON_RENDER_CACHE["box_type"] = Box
        _COMMON_RENDER_CACHE["text_type"] = Text
        _COMMON_RENDER_CACHE["portal_type"] = Portal
    except Exception:
        pass


def _ensure_common_render_loaded(root) -> dict[str, Any]:
    c = _COMMON_RENDER_CACHE
    if c["validate_fn"] is _NOT_LOADED:
        _load_common_render(root)
    return c


def _has_instance_render_override(node) -> bool:
    if node is None or not hasattr(node, "__dict__"):
        return False
    return "render" in node.__dict__


# Cursor style DECSCUSR codes (hoisted from set_cursor_style to avoid per-call dict allocation)
_CURSOR_STYLE_MAP = {
    "block": 1,
    "underline": 3,
    "bar": 5,
    "steady_block": 2,
    "steady_underline": 4,
    "steady_bar": 6,
}

# Steady (non-blinking) DECSCUSR codes — used by software blink in _apply_cursor.
# Maps base style names ("block", "bar", "underline") to their steady variants
# so the terminal shows a static shape while our timer handles the blink.
_CURSOR_STYLE_MAP_STEADY = {
    "block": 2,
    "underline": 4,
    "bar": 6,
    "steady_block": 2,
    "steady_underline": 4,
    "steady_bar": 6,
}

_DEFAULT_UPDATE_LAYOUT_FN = Renderable.update_layout
