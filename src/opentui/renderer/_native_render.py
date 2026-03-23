"""Native C++ render acceleration mixin for CliRenderer.

Provides fast paths for common-tree rendering, hybrid rendering,
incremental dirty-subtree repainting, and layout-aware repaint plans.
"""

from __future__ import annotations

import logging
from typing import Any

from .buffer import Buffer
from .layout import supports_common_tree_strategy
from .native import (
    LayoutRepaintFact,
    _COMMON_RENDER_CACHE,
    _ensure_common_render_loaded,
    _has_instance_render_override,
)
from .repaint import node_bounds_rect
from .repaint_plan import (
    collect_dirty_common_roots,
    compute_layout_common_repaint_plan,
)

_log = logging.getLogger(__name__)


class _NativeRenderMixin:
    """C++ accelerated render paths for common and hybrid trees.

    Expects host class to provide: _root, _force_next_render, _post_process_fns,
    _common_tree_cache_root, _common_tree_cache_valid, _common_tree_cache_eligible,
    _clear_color, _tree_has_custom_update_layout, _pending_structural_clear_rects.
    """

    def _render_common_tree_fast(self, root, buffer: Buffer) -> bool:
        if not self._prepare_common_tree_render(root):
            return False

        return self._render_common_tree_unchecked_fast(root, buffer)

    def _render_common_tree_unchecked_fast(self, root, buffer: Buffer) -> bool:
        render_fn = _COMMON_RENDER_CACHE["render_fn"]
        offsets = _COMMON_RENDER_CACHE["offsets"]
        root_type = _COMMON_RENDER_CACHE["root_type"]
        box_type = _COMMON_RENDER_CACHE["box_type"]
        text_type = _COMMON_RENDER_CACHE["text_type"]
        portal_type = _COMMON_RENDER_CACHE["portal_type"]

        if None in (render_fn, offsets, root_type, box_type, text_type, portal_type):
            return False

        try:
            return bool(
                render_fn(buffer._ptr, root, root_type, box_type, text_type, portal_type, offsets)
            )
        except Exception:
            _log.debug("native common render path unavailable", exc_info=True)
            self._common_tree_cache_root = root
            self._common_tree_cache_valid = False
            self._common_tree_cache_eligible = False
            return False

    def _render_hybrid_tree_fast(self, root, buffer: Buffer, delta_time: float) -> bool:
        if _has_instance_render_override(root):
            return False

        c = _ensure_common_render_loaded(root)
        hybrid_fn, offsets = c["hybrid_fn"], c["offsets"]
        root_type, box_type, text_type, portal_type = (
            c["root_type"],
            c["box_type"],
            c["text_type"],
            c["portal_type"],
        )

        if None in (hybrid_fn, offsets, root_type, box_type, text_type, portal_type):
            return False

        def py_fallback(node):
            node.render(buffer, delta_time)

        try:
            return bool(
                hybrid_fn(
                    buffer._ptr,
                    root,
                    root_type,
                    box_type,
                    text_type,
                    portal_type,
                    offsets,
                    py_fallback,
                )
            )
        except Exception:
            _log.debug("hybrid render path failed", exc_info=True)
            return False

    def _prepare_common_tree_render(self, root) -> bool:
        if _has_instance_render_override(root):
            return False
        if not supports_common_tree_strategy(root):
            self._common_tree_cache_root = root
            self._common_tree_cache_valid = True
            self._common_tree_cache_eligible = False
            return False

        c = _ensure_common_render_loaded(root)
        validate_fn, render_fn, offsets = c["validate_fn"], c["render_fn"], c["offsets"]
        root_type, box_type, text_type, portal_type = (
            c["root_type"],
            c["box_type"],
            c["text_type"],
            c["portal_type"],
        )

        if None in (validate_fn, render_fn, offsets, root_type, box_type, text_type, portal_type):
            return False

        tree_dirty = bool(
            getattr(root, "_dirty", False)
            or getattr(root, "_subtree_dirty", False)
            or getattr(root, "_paint_subtree_dirty", False)
        )
        cache_stale = root is not self._common_tree_cache_root or not self._common_tree_cache_valid

        try:
            if tree_dirty or cache_stale:
                eligible = bool(
                    validate_fn(root, root_type, box_type, text_type, portal_type, offsets)
                )
                self._common_tree_cache_root = root
                self._common_tree_cache_valid = True
                self._common_tree_cache_eligible = eligible
                if not eligible:
                    return False
            elif not self._common_tree_cache_eligible:
                return False
            return True
        except Exception:
            _log.debug("native common render path unavailable", exc_info=True)
            self._common_tree_cache_root = root
            self._common_tree_cache_valid = False
            self._common_tree_cache_eligible = False
            return False

    def _can_reuse_current_buffer_frame(self) -> bool:
        root = self._root
        if root is None or self._force_next_render or self._post_process_fns:
            return False
        if (
            getattr(root, "_dirty", False)
            or getattr(root, "_subtree_dirty", False)
            or getattr(root, "_paint_subtree_dirty", False)
        ):
            return False
        return self._prepare_common_tree_render(root)

    def _can_incremental_common_tree_repaint(self) -> bool:
        root = self._root
        if root is None or self._force_next_render:
            return False
        if getattr(root, "_dirty", False) or getattr(root, "_subtree_dirty", False):
            return False
        if not getattr(root, "_paint_subtree_dirty", False):
            return False
        return self._prepare_common_tree_render(root)

    def _compute_layout_common_repaint_plan(
        self,
        layout_repaint_facts: list[LayoutRepaintFact],
    ) -> list[tuple[Any, tuple[int, int, int, int]]] | None:
        root = self._root
        if root is None:
            return None
        return compute_layout_common_repaint_plan(
            root,
            layout_repaint_facts,
            force_next_render=self._force_next_render,
            has_post_process_fns=bool(self._post_process_fns),
            tree_has_custom_update_layout=self._tree_has_custom_update_layout,
            pending_structural_clear_rects=self._pending_structural_clear_rects,
            prepare_common_tree_render_fn=self._prepare_common_tree_render,
        )

    def _render_common_plan_fast(
        self,
        plan: list[tuple[Any | None, tuple[int, int, int, int]]],
        buffer: Buffer,
        delta_time: float,
    ) -> None:
        for node, rect in plan:
            self._clear_common_repaint_rect(buffer, rect)
            if node is None:
                continue
            if not self._render_common_tree_unchecked_fast(node, buffer):
                node.render(buffer, delta_time)

    def _clear_common_repaint_rect(
        self,
        buffer: Buffer,
        rect: tuple[int, int, int, int],
    ) -> None:
        x, y, width, height = rect
        if width <= 0 or height <= 0:
            return
        buffer.fill_rect(x, y, width, height, self._clear_color)

    def _render_dirty_common_subtrees_fast(self, root, buffer: Buffer, delta_time: float) -> None:
        dirty_roots: list[Any] = []
        collect_dirty_common_roots(root, dirty_roots)
        self._render_common_plan_fast(
            [(node, node_bounds_rect(node)) for node in dirty_roots],
            buffer,
            delta_time,
        )
