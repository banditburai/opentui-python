"""Shared base renderable tree and lifecycle primitives."""

from __future__ import annotations

import contextlib
import itertools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, NamedTuple

import yoga

from .. import diagnostics as _diag
from .. import layout as yoga_layout
from .._signal_types import _HAS_NATIVE
from ..enums import RenderStrategy

if TYPE_CHECKING:
    from ..renderer import Buffer


class LayoutRect(NamedTuple):
    """Computed layout rectangle for a renderable."""

    x: int
    y: int
    width: int
    height: int
    padding_left: int = 0
    padding_right: int = 0
    padding_top: int = 0
    padding_bottom: int = 0

    @property
    def content_x(self) -> int:
        return self.x + self.padding_left

    @property
    def content_y(self) -> int:
        return self.y + self.padding_top

    @property
    def content_width(self) -> int:
        return max(0, self.width - self.padding_left - self.padding_right)

    @property
    def content_height(self) -> int:
        return max(0, self.height - self.padding_top - self.padding_bottom)


_NATIVE_CACHE: dict[str, Any] = {
    "create_prop_binding": None,
    "yoga_configurator": None,
    "yoga_configurator_loaded": False,
    "configure_node_fast": None,
    "configure_node_fast_loaded": False,
}


def _get_yoga_configurator() -> Any:
    if _NATIVE_CACHE["yoga_configurator_loaded"]:
        return _NATIVE_CACHE["yoga_configurator"]
    _NATIVE_CACHE["yoga_configurator_loaded"] = True
    if not _HAS_NATIVE:
        return None
    from .. import ffi

    nb = ffi.get_native()
    if nb is not None:
        try:
            _NATIVE_CACHE["yoga_configurator"] = nb.yoga_configure.YogaConfigurator()
            return _NATIVE_CACHE["yoga_configurator"]
        except AttributeError:
            pass
    return None


def _get_create_prop_binding() -> Any:
    create_prop_binding = _NATIVE_CACHE["create_prop_binding"]
    if create_prop_binding is not None:
        return create_prop_binding
    if not _HAS_NATIVE:
        return None
    from .. import ffi

    nb = ffi.get_native()
    if nb is not None:
        try:
            _NATIVE_CACHE["create_prop_binding"] = nb.native_signals.create_prop_binding
            return _NATIVE_CACHE["create_prop_binding"]
        except AttributeError:
            pass
    return None


def _get_configure_node_fast() -> Any:
    if _NATIVE_CACHE["configure_node_fast_loaded"]:
        return _NATIVE_CACHE["configure_node_fast"]
    configure_node_fast = getattr(yoga, "configure_node_fast", None)
    _NATIVE_CACHE["configure_node_fast"] = configure_node_fast
    _NATIVE_CACHE["configure_node_fast_loaded"] = True
    return configure_node_fast


class _PropBinding(NamedTuple):
    source: object
    cleanup: Callable
    unsub_only: Callable


_renderable_id_counter = itertools.count(1)


def _next_id() -> int:
    return next(_renderable_id_counter)


def _sync_yoga_children(
    parent_yoga_node: Any,
    children: list[BaseRenderable],
    *,
    filter_participates: bool = False,
) -> None:
    """Collect yoga nodes from *children* and set them on *parent_yoga_node*."""
    yoga_children = []
    for child in children:
        if child._yoga_node is not None:
            if filter_participates and not child.participates_in_parent_yoga():
                continue
            yoga_owner = child._yoga_node.owner
            if yoga_owner is not None and yoga_owner is not parent_yoga_node:
                yoga_owner.remove_child(child._yoga_node)
            yoga_children.append(child._yoga_node)
    parent_yoga_node.set_children(yoga_children)


class BaseRenderable:
    renderables_by_number: dict[int, BaseRenderable] = {}

    __slots__ = (
        "_num",
        "_id",
        "_parent",
        "_children",
        "_children_tuple",
        "_event_handlers",
        "_cleanups",
        "_yoga_node",
        "_x",
        "_y",
        "_width",
        "_height",
        "_layout_width",
        "_layout_height",
        "_dirty",
        "_subtree_dirty",
        "_paint_subtree_dirty",
        "_hit_paint_dirty",
        "_destroyed",
        "_visible",
        "_host",
        "key",
    )

    def __init__(self, *, key: str | int | None = None, id: str | None = None):
        self._num = _next_id()
        self._id: str = id if id is not None else f"renderable-{self._num}"
        BaseRenderable.renderables_by_number[self._num] = self
        self.key = key
        self._parent: BaseRenderable | None = None
        self._children: list[BaseRenderable] = []
        self._children_tuple: tuple[BaseRenderable, ...] | None = None
        self._event_handlers: dict[str, list[Callable]] = {}
        self._cleanups: dict[int, Callable] = {}
        self._yoga_node: Any = yoga_layout.create_node()
        self._x = 0
        self._y = 0
        self._width: int | str | None = None
        self._height: int | str | None = None
        self._layout_width = 0
        self._layout_height = 0
        self._dirty = True
        self._subtree_dirty = True
        self._paint_subtree_dirty = True
        self._hit_paint_dirty = False
        self._destroyed = False
        self._visible = True
        self._host: BaseRenderable | None = None

    @property
    def x(self) -> int:
        return self._x

    @property
    def y(self) -> int:
        return self._y

    @property
    def width(self) -> int | str | None:
        return self._width

    @property
    def height(self) -> int | str | None:
        return self._height

    @property
    def layout_width(self) -> int:
        return self._layout_width

    @property
    def layout_height(self) -> int:
        return self._layout_height

    @property
    def layout_rect(self) -> LayoutRect:
        return LayoutRect(self._x, self._y, self._layout_width, self._layout_height)

    @property
    def parent(self) -> BaseRenderable | None:
        return self._parent

    @property
    def children(self) -> tuple[BaseRenderable, ...]:
        return self.get_children()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        pass

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        if _diag._enabled & _diag.DIRTY:
            _diag.log_dirty(self, "layout")
        self._dirty = True
        node = self
        while node is not None and not node._subtree_dirty:
            node._subtree_dirty = True
            node = node._parent

    def mark_paint_dirty(self) -> None:
        if _diag._enabled & _diag.DIRTY:
            _diag.log_dirty(self, "paint")
        self._dirty = True
        node = self
        while node is not None and not node._paint_subtree_dirty:
            node._paint_subtree_dirty = True
            node = node._parent

    def mark_hit_paint_dirty(self) -> None:
        self.mark_paint_dirty()
        node = self
        while node is not None and not node._hit_paint_dirty:
            node._hit_paint_dirty = True
            node = node._parent

    def _get_renderer(self) -> Any | None:
        node: BaseRenderable | None = self
        while node is not None and node._parent is not None:
            node = node._parent
        return getattr(node, "_renderer", None) if node is not None else None

    def _queue_structural_clear_rect(self, rect: tuple[int, int, int, int]) -> None:
        x, y, width, height = rect
        if width <= 0 or height <= 0:
            return
        if (renderer := self._get_renderer()) is not None:
            renderer.queue_structural_clear_rect((x, y, width, height))

    def _invalidate_renderer_structure_caches(self) -> None:
        if (renderer := self._get_renderer()) is not None:
            renderer.invalidate_handler_cache()

    def _invalidate_mouse_tracking_cache(self) -> None:
        if (renderer := self._get_renderer()) is not None:
            renderer._mouse_tracking_dirty = True

    def _adjust_renderer_layout_hook_cache(self, delta: int) -> None:
        if (renderer := self._get_renderer()) is not None:
            renderer.adjust_layout_hook_cache_for_subtree(self, delta)

    def _sync_yoga_display(self) -> None:
        if self._yoga_node is None:
            return
        self._yoga_node.display = yoga.Display.Flex if self._visible else yoga.Display.None_

    def _configure_yoga_properties(self) -> None:
        configurator = _get_yoga_configurator()
        if configurator is not None:
            try:
                configurator.configure_tree(self)
            except TypeError:
                configurator.configure_tree(self, yoga.configure_node_fast)
            return
        if not self._subtree_dirty:
            return
        pre = type(self)._pre_configure_yoga
        if pre is not BaseRenderable._pre_configure_yoga:
            pre(self)
        self._configure_yoga_node(self._yoga_node)
        post = type(self)._post_configure_yoga
        if post is not BaseRenderable._post_configure_yoga:
            post(self, self._yoga_node)
        for child in self._children:
            child._configure_yoga_properties()

    def _pre_configure_yoga(self) -> None:
        """Called before yoga configure."""

    def _post_configure_yoga(self, node: Any) -> None:
        """Called after yoga configure."""

    def _configure_yoga_node(self, node: Any) -> None:
        pass

    def _apply_yoga_layout(self) -> None:
        node = self._yoga_node
        if node is None:
            return
        self._x = int(node.layout_left)
        self._y = int(node.layout_top)
        self._layout_width = int(node.layout_width)
        self._layout_height = int(node.layout_height)

    @property
    def num(self) -> int:
        return self._num

    @property
    def id(self) -> str:
        return self._id

    @id.setter
    def id(self, value: str) -> None:
        self._id = value

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        old = self._visible
        self._visible = value
        if _diag._enabled & _diag.VISIBILITY and old != value:
            _diag.log_visibility_change(self, old, value)
        self._sync_yoga_display()
        self.mark_dirty()

    @property
    def is_destroyed(self) -> bool:
        return self._destroyed

    def participates_in_parent_yoga(self) -> bool:
        return True

    def affects_parent_paint(self) -> bool:
        return True

    def add(self, child: BaseRenderable | None, index: int | None = None) -> int:
        if child is None:
            return -1
        if child._destroyed or child._yoga_node is None:
            return -1
        if child._parent:
            child._parent.remove(child)
        child._parent = self
        include_in_yoga = child.participates_in_parent_yoga()
        if index is not None:
            if index < 0:
                index = max(0, len(self._children) + index)
            index = min(index, len(self._children))
            self._children.insert(index, child)
            if include_in_yoga:
                yoga_index = sum(
                    1 for sibling in self._children[:index] if sibling.participates_in_parent_yoga()
                )
                self._yoga_node.insert_child(child._yoga_node, yoga_index)
        else:
            index = len(self._children)
            self._children.append(child)
            if include_in_yoga:
                self._yoga_node.insert_child(child._yoga_node, self._yoga_node.child_count)
        self._children_tuple = None
        self._invalidate_renderer_structure_caches()
        child._adjust_renderer_layout_hook_cache(1)
        if include_in_yoga:
            self.mark_dirty()
        else:
            pre = type(child)._pre_configure_yoga
            if pre is not BaseRenderable._pre_configure_yoga:
                pre(child)
            if child.affects_parent_paint():
                self.mark_hit_paint_dirty()
        return index

    def add_children(self, children: list[BaseRenderable]) -> None:
        if not children:
            return
        any_yoga = False
        for child in children:
            if child is None or child._destroyed or child._yoga_node is None:
                continue
            if child._parent:
                child._parent.remove(child)
            child._parent = self
            self._children.append(child)
            include_in_yoga = child.participates_in_parent_yoga()
            any_yoga = any_yoga or include_in_yoga
            if not include_in_yoga:
                pre = type(child)._pre_configure_yoga
                if pre is not BaseRenderable._pre_configure_yoga:
                    pre(child)
        self._children_tuple = None
        self._invalidate_renderer_structure_caches()
        for child in children:
            if child is not None:
                child._adjust_renderer_layout_hook_cache(1)
        if self._yoga_node is not None:
            _sync_yoga_children(self._yoga_node, self._children, filter_participates=True)
        if any_yoga:
            self.mark_dirty()
        elif any(child.affects_parent_paint() for child in children if child is not None):
            self.mark_hit_paint_dirty()

    def remove(self, child: BaseRenderable) -> None:
        if child in self._children:
            clear_rect = (child._x, child._y, child._layout_width, child._layout_height)
            self._children.remove(child)
            self._children_tuple = None
            self._invalidate_renderer_structure_caches()
            child._adjust_renderer_layout_hook_cache(-1)
            include_in_yoga = child.participates_in_parent_yoga()
            if include_in_yoga and child._yoga_node.owner is self._yoga_node:
                self._yoga_node.remove_child(child._yoga_node)
            child._parent = None
            if include_in_yoga:
                self._queue_structural_clear_rect(clear_rect)
                self.mark_dirty()
            elif child.affects_parent_paint():
                self._queue_structural_clear_rect(clear_rect)
                self.mark_hit_paint_dirty()

    def insert_before(self, child: BaseRenderable | None, anchor: BaseRenderable | None) -> int:
        if child is None:
            return -1
        if anchor is None:
            return self.add(child)
        if child is anchor:
            if child not in self._children:
                return self.add(child)
            return self._children.index(child)
        if anchor not in self._children:
            return -1
        if child._parent:
            child._parent.remove(child)
        child._parent = self
        idx = self._children.index(anchor)
        self._children.insert(idx, child)
        self._children_tuple = None
        self._invalidate_renderer_structure_caches()
        child._adjust_renderer_layout_hook_cache(1)
        include_in_yoga = child.participates_in_parent_yoga()
        if include_in_yoga:
            yoga_index = sum(
                1 for sibling in self._children[:idx] if sibling.participates_in_parent_yoga()
            )
            self._yoga_node.insert_child(child._yoga_node, yoga_index)
        if include_in_yoga:
            self.mark_dirty()
        else:
            pre = type(child)._pre_configure_yoga
            if pre is not BaseRenderable._pre_configure_yoga:
                pre(child)
            if child.affects_parent_paint():
                self.mark_hit_paint_dirty()
        return idx

    def get_children(self) -> tuple[BaseRenderable, ...]:
        if self._children_tuple is None:
            self._children_tuple = tuple(self._children)
        return self._children_tuple

    def get_children_count(self) -> int:
        return len(self._children)

    def contains_point(self, x: int, y: int) -> bool:
        w, h = self._layout_width, self._layout_height
        return w > 0 and h > 0 and self._x <= x < self._x + w and self._y <= y < self._y + h

    def get_renderable(self, id: str) -> BaseRenderable | None:
        for child in self._children:
            if child._id == id:
                return child
        return None

    def find_descendant_by_id(self, id: str) -> BaseRenderable | None:
        for child in self._children:
            if child._id == id:
                return child
            found = child.find_descendant_by_id(id)
            if found is not None:
                return found
        return None

    def on(self, event: str, handler: Callable) -> None:
        self._event_handlers.setdefault(event, []).append(handler)

    def off(self, event: str, handler: Callable | None = None) -> None:
        if event not in self._event_handlers:
            return
        if handler is None:
            self._event_handlers[event] = []
        else:
            self._event_handlers[event] = [h for h in self._event_handlers[event] if h != handler]

    def emit(self, event: str, *args, **kwargs) -> None:
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            handler(*args, **kwargs)

    def on_cleanup(self, fn: Callable) -> None:
        self._cleanups[id(fn)] = fn

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        BaseRenderable.renderables_by_number.pop(self._num, None)
        for fn in self._cleanups.values():
            with contextlib.suppress(Exception):
                fn()
        self._cleanups.clear()
        if self._parent is not None:
            self._parent.remove(self)
        for child in self._children[:]:
            child.destroy()
        self._children.clear()
        self._children_tuple = None
        self._event_handlers.clear()
        if self._yoga_node is not None:
            configurator = _get_yoga_configurator()
            if configurator is not None:
                with contextlib.suppress(AttributeError):
                    configurator.clear_cache(self._yoga_node)
        self._yoga_node = None
        self._parent = None

    def destroy_recursively(self) -> None:
        self.destroy()

    def get_render_strategy(self) -> RenderStrategy:
        return RenderStrategy.PYTHON_FALLBACK


def is_renderable(obj: Any) -> bool:
    return isinstance(obj, BaseRenderable)


__all__ = [
    "BaseRenderable",
    "LayoutRect",
    "_PropBinding",
    "_get_configure_node_fast",
    "_get_create_prop_binding",
    "_get_yoga_configurator",
    "_sync_yoga_children",
    "is_renderable",
]
