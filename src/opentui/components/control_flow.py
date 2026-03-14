"""Structural control flow — For, Show, Switch.

In-process equivalents of Datastar/idiomorph server-driven fragment patching
and Solid.js structural control flow primitives.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

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
        raw = source() if callable(source) else source
        items: list[Any] = list(raw)

        new_key_list = [self._key_fn(item) for item in items]
        old_key_list = [child.key for child in self._children]

        if new_key_list == old_key_list:
            _log.debug("For[%s] fast-path: %d keys unchanged", self.key, len(new_key_list))
            return  # Fast path: nothing changed

        old_by_key = {c.key: c for c in self._children if c.key is not None}
        new_keys = set(new_key_list)
        new_children = []
        reused = 0
        created = 0

        for item in items:
            k = self._key_fn(item)
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
            child for child in self._children
            if child.key is not None and child.key not in new_keys
        ]

        self._children = new_children
        for child in new_children:
            child._parent = self

        # Sync yoga tree BEFORE destroying removed nodes.
        if self._yoga_node is not None:
            self._yoga_node.remove_all_children()
            for child in new_children:
                if child._yoga_node is not None:
                    owner = child._yoga_node.owner
                    if owner is not None:
                        owner.remove_child(child._yoga_node)
                    self._yoga_node.insert_child(
                        child._yoga_node, self._yoga_node.child_count
                    )

        # Now safe to destroy — yoga nodes are detached from parent.
        for child in removed:
            child._parent = None
            child.destroy_recursively()

        _log.debug(
            "For[%s] reconcile: reused=%d created=%d destroyed=%d total=%d",
            self.key, reused, created, len(removed), len(new_children),
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
        """Evaluate condition and add the appropriate children."""
        condition = self._when()
        self._is_active = bool(condition) or self._fallback_fn is not None

        if condition:
            result = self._render_fn()
        elif self._fallback_fn is not None:
            result = self._fallback_fn()
        else:
            return  # No children, _is_active=False

        # Normalize to list and add
        if isinstance(result, BaseRenderable):
            result = [result]
        elif result is None:
            return
        for child in result:
            self.add(child)

    def _configure_yoga_node(self, node: Any) -> None:
        """Toggle Display between Flex and None_ based on active state."""
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
        """Find first matching branch and add its children."""
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


__all__ = ["For", "Match", "Show", "Switch"]
