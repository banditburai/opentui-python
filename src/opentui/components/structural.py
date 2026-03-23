"""Structural components - Portal, ErrorBoundary, Suspense, Match.

These are structural primitives that provide mounting, error handling,
and async loading boundary semantics. They are separated from the
reactive control flow primitives (For, Show, Switch, Dynamic) for
module organisation but are re-exported from ``control_flow`` for
backward compatibility.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .. import layout as yoga_layout
from ..signals import Signal
from .base import BaseRenderable, Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer

_log = logging.getLogger(__name__)


def _subtree_contains_portal(node: BaseRenderable) -> bool:
    """Check if a node's subtree contains a Portal.

    Only detects Portals present at construction time. Portals added
    dynamically (e.g. inside @component children that build lazily)
    are not caught by this check.
    """
    if isinstance(node, Portal):
        return True
    return any(_subtree_contains_portal(child) for child in node._children)


class Match:
    """A branch condition for Switch. Not a Renderable; just configuration.

    Usage (positional children):
        Match(Text("Home"), when=tab == "home")

    Usage (render= for deferred/factory creation):
        Match(when=is_visible, render=lambda: Portal(...))
    """

    __slots__ = ("when", "_render_fn")

    def __init__(self, *children, when=None, render=None):
        if when is None:
            raise ValueError("Match requires a when= condition")
        if children and render is not None:
            raise ValueError("Match accepts positional children OR render=, not both")
        self.when = when
        if children:
            for c in children:
                if isinstance(c, BaseRenderable) and _subtree_contains_portal(c):
                    raise ValueError(
                        "Match does not support Portal as a positional child. "
                        "Use render=lambda: Portal(...) instead."
                    )
            _pre = list(children)
            self._render_fn = lambda: _pre
        elif render is not None:
            self._render_fn = render
        else:
            raise ValueError("Match requires children or render=")

    @property
    def render(self):
        return self._render_fn


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

    @staticmethod
    def _clear_subtree_dirty_flags(node: BaseRenderable) -> None:
        node._subtree_dirty = False
        for child in node._children:
            Portal._clear_subtree_dirty_flags(child)

    @staticmethod
    def _content_extent(child: BaseRenderable, size_attr: str, layout_attr: str) -> int:
        value = getattr(child, size_attr, None)
        if isinstance(value, int | float):
            return int(value)
        return int(getattr(child, layout_attr, 0) or 0)

    @classmethod
    def _measure_container_bounds(cls, children: list[BaseRenderable]) -> tuple[int, int]:
        max_right = 0
        max_bottom = 0
        for child in children:
            left = getattr(child, "_pos_left", None)
            top = getattr(child, "_pos_top", None)
            x = int(left) if isinstance(left, int | float) else int(getattr(child, "_x", 0) or 0)
            y = int(top) if isinstance(top, int | float) else int(getattr(child, "_y", 0) or 0)
            width = cls._content_extent(child, "_width", "_layout_width")
            height = cls._content_extent(child, "_height", "_layout_height")
            max_right = max(max_right, x + max(0, width))
            max_bottom = max(max_bottom, y + max(0, height))
        return max_right, max_bottom

    def _ensure_container(self) -> None:
        from .box import Box

        mount = self._resolve_mount()

        if self._container is not None and self._current_mount is not mount:
            if self._current_mount is not None and not self._current_mount._destroyed:
                self._current_mount.remove(self._container)
            self._container.destroy_recursively()
            self._container = None

        if self._container is None:
            self._container = Box(
                key=f"portal-container-{self.key}" if self.key else None,
                position="absolute",
                left=0,
                top=0,
            )
            self._container._host = self
            self._container.contains_point = lambda x, y: True
            self._container.add_children(self._content_children)
            mount.add(self._container)
            self._current_mount = mount
            if self._ref_fn is not None:
                self._ref_fn(self._container)
            container_changed = True
        else:
            container_changed = False

        bounds_width, bounds_height = self._measure_container_bounds(self._content_children)
        if bounds_width > 0 and self._container.width != bounds_width:
            self._container.width = bounds_width
            container_changed = True
        if bounds_height > 0 and self._container.height != bounds_height:
            self._container.height = bounds_height
            container_changed = True
        if container_changed:
            self._container._configure_yoga_properties()
            self._clear_subtree_dirty_flags(self._container)

    def _pre_configure_yoga(self) -> None:
        self._ensure_container()

    def _post_configure_yoga(self, node: Any) -> None:
        yoga_layout.configure_node(node, display="none")

    def participates_in_parent_yoga(self) -> bool:
        return False

    def affects_parent_paint(self) -> bool:
        return False

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
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


class ErrorBoundary(Renderable):
    """Catches exceptions during child construction and renders a fallback.

    Wraps child construction in try/except. On error, swaps children for
    the fallback. Fallback receives (error, reset_fn). Calling reset_fn
    retries the original render.

    Usage:
        ErrorBoundary(
            render=lambda: SomeComponent(),
            fallback=lambda err, reset: Box(
                Text(f"Error: {err}"),
                Text("Click to retry", on_mouse_down=lambda _: reset()),
            ),
        )
    """

    __slots__ = ("_render_fn", "_fallback_fn", "_error", "_has_error")

    def __init__(
        self,
        *,
        render: Callable[[], BaseRenderable | list[BaseRenderable]],
        fallback: Callable[[Exception, Callable], BaseRenderable | list[BaseRenderable]],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._render_fn = render
        self._fallback_fn = fallback
        self._error: Exception | None = None
        self._has_error = False
        self._try_render()

    def _try_render(self) -> None:
        from ._control_flow_region import normalize_render_result

        try:
            children = normalize_render_result(self._render_fn())
            self._has_error = False
            self._error = None
            for child in children:
                self.add(child)
        except Exception as e:
            self._error = e
            self._has_error = True
            self._show_fallback(e)

    def _show_fallback(self, error: Exception) -> None:
        from ._control_flow_region import normalize_render_result

        for c in list(self._children):
            self.remove(c)
            c.destroy_recursively()
        try:
            for c in normalize_render_result(self._fallback_fn(error, self._reset)):
                self.add(c)
        except Exception:
            pass  # Keep boundary alive but empty if fallback itself crashes
        self.mark_dirty()

    def _reset(self) -> None:
        for c in list(self._children):
            self.remove(c)
            c.destroy_recursively()
        self._try_render()
        self.mark_dirty()


_suspense_stack: list[list[Signal]] = []


def _register_suspense_resource(loading_signal: Signal) -> None:
    if _suspense_stack:
        _suspense_stack[-1].append(loading_signal)


class Suspense(Renderable):
    """Show fallback while nested resources are loading.

    Mirrors SolidJS ``<Suspense>``. Tracks resource loading signals
    registered during child construction and shows ``fallback`` until
    all resources have resolved.

    Usage::

        resource = create_resource(fetch_data)

        Suspense(
            fallback=lambda: Text("Loading..."),
            children=[
                Text(lambda: f"Data: {resource.data()}")
            ],
        )
    """

    __slots__ = ("_fallback_fn", "_child_nodes", "_pending_signals", "_show_fallback", "_unsub")

    def __init__(
        self,
        *,
        fallback: Callable[[], Any] | BaseRenderable | None = None,
        children: list | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)

        self._fallback_fn = fallback
        self._pending_signals: list[Signal] = []
        self._show_fallback = False
        self._unsub: Callable[[], None] | None = None

        # Push suspense context so create_resource can register
        _suspense_stack.append(self._pending_signals)
        try:
            self._child_nodes: list[BaseRenderable] = []
            if children:
                for child in children:
                    if child is not None:
                        self._child_nodes.append(child)
        finally:
            _suspense_stack.pop()

        if self._pending_signals:
            signals = list(self._pending_signals)

            def _any_loading() -> bool:
                return any(sig() for sig in signals)

            self._show_fallback = _any_loading()

            def _on_loading_change(_: Any) -> None:
                self._show_fallback = _any_loading()
                self._update_children()

            unsubs: list[Callable[[], None]] = []
            for sig in signals:
                unsubs.append(sig.subscribe(_on_loading_change))

            def _cleanup() -> None:
                for u in unsubs:
                    u()

            self._unsub = _cleanup
        else:
            self._show_fallback = False

        self._update_children()

    def _update_children(self) -> None:
        from ._control_flow_region import normalize_render_result

        child_node_ids = {id(n) for n in self._child_nodes}
        for c in list(self._children):
            self.remove(c)
            if id(c) not in child_node_ids and not c._destroyed:
                c.destroy_recursively()

        if self._show_fallback:
            if self._fallback_fn is not None:
                if callable(self._fallback_fn) and not isinstance(
                    self._fallback_fn, BaseRenderable
                ):
                    fb = self._fallback_fn()
                else:
                    fb = self._fallback_fn
                if fb is not None:
                    for c in normalize_render_result(fb):
                        self.add(c)
        else:
            for child in self._child_nodes:
                self.add(child)

        self.mark_dirty()

    def destroy(self) -> None:
        if self._destroyed:
            return
        if self._unsub:
            self._unsub()
            self._unsub = None
        current = {id(c) for c in self._children}
        for child in self._child_nodes:
            if id(child) not in current and not child._destroyed:
                child.destroy_recursively()
        self._child_nodes.clear()
        super().destroy()


__all__ = [
    "ErrorBoundary",
    "Match",
    "Portal",
    "Suspense",
]
