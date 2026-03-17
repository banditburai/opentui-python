"""Structural control flow — For, Show, Switch.

In-process equivalents of Datastar/idiomorph server-driven fragment patching
and structural control flow primitives for keyed lists and conditional rendering.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import layout as yoga_layout
from .base import BaseRenderable, Renderable

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..renderer import Buffer


# ---------------------------------------------------------------------------
# For — keyed list reconciliation
# ---------------------------------------------------------------------------


class For(Renderable):
    """Keyed list — only renders genuinely new items, preserves existing.

    The in-process equivalent of Datastar's server-driven SSE fragment
    patching: only genuinely new items trigger allocation. Existing items
    keep their identity, state, and yoga nodes.

    Usage:
        For(
            each=log_entries,        # Signal or callable returning list
            render=log_entry,        # fn(item) -> Renderable
            key_fn=lambda e: str(e["id"]),
            key="entry-list",
            flex_grow=1,
        )
    """

    __slots__ = ("_each_source", "_render_fn", "_key_fn")

    def __init__(self, *, each, render, key_fn, **kwargs):
        super().__init__(**kwargs)
        self._each_source = each
        self._render_fn = render
        self._key_fn = key_fn

    def _reconcile_children(self):
        """Reconcile children against current source data.

        Fast path: same keys in same order -> skip entirely (zero work).
        Otherwise: reuse existing children by key, only call render_fn
        for genuinely new items.
        """
        source = self._each_source
        raw: Any = source() if callable(source) else source
        items: list[Any] = list(raw)

        new_key_list = [self._key_fn(item) for item in items]
        # Generate stable fallback keys for items with key=None
        new_key_list = [
            k if k is not None else f"__for_index_{i}" for i, k in enumerate(new_key_list)
        ]
        old_key_list = [child.key for child in self._children]

        if new_key_list == old_key_list:
            _log.debug("For[%s] fast-path: %d keys unchanged", self.key, len(new_key_list))
            return  # Fast path: nothing changed

        old_by_key = {c.key: c for c in self._children if c.key is not None}
        new_keys = set(new_key_list)
        new_children = []
        reused = 0
        created = 0

        for idx, item in enumerate(items):
            k = self._key_fn(item)
            if k is None:
                k = f"__for_index_{idx}"
            existing = old_by_key.get(k)
            if existing is not None:
                new_children.append(existing)  # Reuse — zero allocation
                reused += 1
            else:
                child = self._render_fn(item)  # Only genuinely new items
                child.key = k
                new_children.append(child)
                created += 1

        # Collect removed children for destruction AFTER yoga sync.
        # destroy_recursively() sets _yoga_node=None which releases the
        # Python reference to the C++ yoga node — if the GC collects it
        # while still in the parent's yoga child list, remove_all_children
        # would dereference freed memory.
        removed = [
            child for child in self._children if child.key is not None and child.key not in new_keys
        ]

        self._children = new_children
        self._children_tuple = None
        for child in new_children:
            child._parent = self

        if self._yoga_node is not None:
            self._yoga_node.remove_all_children()
            for child in new_children:
                if child._yoga_node is not None:
                    owner = child._yoga_node.owner
                    if owner is not None:
                        owner.remove_child(child._yoga_node)
                    self._yoga_node.insert_child(child._yoga_node, self._yoga_node.child_count)

        # Now safe to destroy — yoga nodes are detached from parent.
        for child in removed:
            child._parent = None
            child.destroy_recursively()

        _log.debug(
            "For[%s] reconcile: reused=%d created=%d destroyed=%d total=%d",
            self.key,
            reused,
            created,
            len(removed),
            len(new_children),
        )

    def _configure_yoga_node(self, node: Any) -> None:
        """Ensure keyed children exist before layout/configuration."""
        self._reconcile_children()
        super()._configure_yoga_node(node)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return
        for child in self._children:
            if isinstance(child, Renderable):
                child.render(buffer, delta_time)


# ---------------------------------------------------------------------------
# Show — conditional rendering
# ---------------------------------------------------------------------------


class Show(Renderable):
    """Conditional rendering — shows children when condition is truthy.

    Evaluates `when()` eagerly in __init__. Calls `render()` when truthy,
    `fallback()` when falsy. When inactive with no fallback, yoga node gets
    Display.None_ for zero layout cost.

    Usage:
        Show(
            when=lambda: is_visible(),
            render=lambda: Box(Text("Content")),
            fallback=lambda: Text("Hidden"),
            key="content-show",
        )
    """

    __slots__ = ("_when", "_render_fn", "_fallback_fn", "_is_active")

    def __init__(
        self,
        *,
        when: Callable[[], Any],
        render: Callable[[], BaseRenderable | list[BaseRenderable]],
        fallback: Callable[[], BaseRenderable | list[BaseRenderable]] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._when = when
        self._render_fn = render
        self._fallback_fn = fallback
        self._is_active = False
        self._evaluate_and_populate()

    def _evaluate_and_populate(self):
        condition = self._when()
        active = bool(condition)
        has_fallback = self._fallback_fn is not None
        self._is_active = active or has_fallback

        if active:
            result = self._render_fn()
        elif self._fallback_fn is not None:
            result = self._fallback_fn()
        else:
            return  # No children, _is_active=False

        if isinstance(result, BaseRenderable):
            result = [result]
        elif result is None:
            return
        for child in result:
            self.add(child)

    def _configure_yoga_node(self, node: Any) -> None:
        super()._configure_yoga_node(node)
        if not self._is_active:
            yoga_layout.configure_node(node, display="none")
        else:
            yoga_layout.configure_node(node, display="flex")

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._is_active:
            return
        for child in self._children:
            if isinstance(child, Renderable):
                child.render(buffer, delta_time)


# ---------------------------------------------------------------------------
# Match + Switch — multi-branch conditional
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Match:
    """A branch condition for Switch. Not a Renderable — just configuration."""

    when: Callable[[], Any]
    render: Callable[[], BaseRenderable | list[BaseRenderable]]


class Switch(Renderable):
    """Multi-branch conditional rendering.

    Two modes:
    - Condition matching: pass Match objects as positional args
    - Value matching: pass on=callable, cases=dict

    Usage (condition matching):
        Switch(
            Match(when=lambda: score() >= 90, render=lambda: Text("A")),
            Match(when=lambda: score() >= 80, render=lambda: Text("B")),
            fallback=lambda: Text("F"),
            key="grade",
        )

    Usage (value matching):
        Switch(
            on=lambda: active_tab(),
            cases={
                0: counter_panel,
                1: log_panel,
            },
            key="tab-switch",
        )
    """

    __slots__ = ("_matches", "_on_fn", "_cases", "_fallback_fn", "_is_active")

    def __init__(
        self,
        *matches: Match,
        on: Callable[[], Any] | None = None,
        cases: dict[Any, Callable[[], BaseRenderable | list[BaseRenderable]]] | None = None,
        fallback: Callable[[], BaseRenderable | list[BaseRenderable]] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._matches = matches
        self._on_fn = on
        self._cases = cases or {}
        self._fallback_fn = fallback
        self._is_active = False
        self._evaluate_and_populate()

    def _evaluate_and_populate(self):
        render_fn = None

        if self._on_fn is not None:
            value = self._on_fn()
            render_fn = self._cases.get(value)
        else:
            for match in self._matches:
                if match.when():
                    render_fn = match.render
                    break

        if render_fn is None:
            render_fn = self._fallback_fn

        if render_fn is not None:
            self._is_active = True
            result = render_fn()
            if isinstance(result, BaseRenderable):
                result = [result]
            elif result is None:
                return
            for child in result:
                self.add(child)
        else:
            self._is_active = False

    def _configure_yoga_node(self, node: Any) -> None:
        super()._configure_yoga_node(node)
        if not self._is_active:
            yoga_layout.configure_node(node, display="none")
        else:
            yoga_layout.configure_node(node, display="flex")

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible or not self._is_active:
            return
        for child in self._children:
            if isinstance(child, Renderable):
                child.render(buffer, delta_time)


# ---------------------------------------------------------------------------
# Portal — mount children at a different tree location
# ---------------------------------------------------------------------------


class Portal(Renderable):
    """Render children at a different location in the component tree.

    The Portal marker itself is invisible (display=none). It creates a Box
    container at the mount point containing the actual children. This is
    useful for modals, overlays, toasts, and command palettes that need to
    escape their logical parent's layout constraints.

    Usage:
        Portal(
            Text("Modal content"),
            mount=overlay_box,     # or callable, or None for root
            ref=lambda c: ...,     # optional callback receiving container
            key="modal-portal",
        )
    """

    __slots__ = ("_mount_source", "_container", "_ref_fn", "_current_mount", "_content_children")

    def __init__(
        self,
        *children: BaseRenderable,
        mount: BaseRenderable | Callable[[], BaseRenderable] | None = None,
        ref: Callable[[BaseRenderable], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._mount_source = mount
        self._ref_fn = ref
        self._container: BaseRenderable | None = None
        self._current_mount: BaseRenderable | None = None
        self._content_children: list[BaseRenderable] = list(children)

    def _resolve_mount(self) -> BaseRenderable:
        if self._mount_source is None:
            from ..hooks import use_renderer

            try:
                return use_renderer().root
            except RuntimeError:
                raise RuntimeError(
                    "Portal with mount=None requires an active renderer. "
                    "Pass an explicit mount= target or ensure a renderer is running."
                ) from None
        if callable(self._mount_source):
            return self._mount_source()
        return self._mount_source

    def _ensure_container(self) -> None:
        from .box import Box

        mount = self._resolve_mount()

        # Mount point changed — remove from old mount
        if self._container is not None and self._current_mount is not mount:
            if self._current_mount is not None and not self._current_mount._destroyed:
                self._current_mount.remove(self._container)
            self._container.destroy_recursively()
            self._container = None

        if self._container is None:
            self._container = Box(key=f"portal-container-{self.key}" if self.key else None)
            self._container._host = self
            for child in self._content_children:
                self._container.add(child)
            mount.add(self._container)
            self._current_mount = mount
            if self._ref_fn is not None:
                self._ref_fn(self._container)

    def _configure_yoga_node(self, node: Any) -> None:
        self._ensure_container()
        super()._configure_yoga_node(node)
        yoga_layout.configure_node(node, display="none")

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """No-op — container is rendered by the mount point's tree traversal."""
        pass

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._container is not None:
            container = self._container
            mount = self._current_mount
            self._container = None
            self._current_mount = None
            if mount is not None and not mount._destroyed:
                mount.remove(container)
            if not container._destroyed:
                container.destroy_recursively()
        self._content_children.clear()
        super().destroy()


__all__ = ["For", "Match", "Portal", "Show", "Switch"]
