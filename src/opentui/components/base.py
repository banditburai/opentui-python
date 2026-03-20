"""Base renderable classes."""

from __future__ import annotations

import contextlib
import itertools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

import yoga

from .. import layout as yoga_layout
from .. import structs as s
from ..enums import RenderStrategy
from ..signals import _HAS_NATIVE, Signal, _ComputedSignal, _tracking_context

log = logging.getLogger(__name__)

# Pointer identity with C++-interned strings enables O(1) comparison in yoga.
import sys as _sys

_COLUMN = _sys.intern("column")
_NOWRAP = _sys.intern("nowrap")
_FLEX_START = _sys.intern("flex-start")
_STRETCH = _sys.intern("stretch")
_VISIBLE = _sys.intern("visible")
_RELATIVE = _sys.intern("relative")
_SINGLE = _sys.intern("single")
_LEFT = _sys.intern("left")

# Default values for "simple text" fast-path detection.
# If all these attrs remain at their defaults after __init__, the reconciler
# can use the cheap dict-only patch path instead of full slot scanning.
_SIMPLE_DEFAULTS: dict[str, object] = {
    "_min_width": None,
    "_min_height": None,
    "_max_width": None,
    "_max_height": None,
    "_flex_grow": 0,
    "_flex_shrink": 1,
    "_flex_direction": _COLUMN,
    "_flex_wrap": _NOWRAP,
    "_flex_basis": None,
    "_justify_content": _FLEX_START,
    "_align_items": _STRETCH,
    "_align_self": None,
    "_gap": 0,
    "_row_gap": None,
    "_column_gap": None,
    "_overflow": _VISIBLE,
    "_position": _RELATIVE,
    "_padding": 0,
    "_padding_top": 0,
    "_padding_right": 0,
    "_padding_bottom": 0,
    "_padding_left": 0,
    "_margin": 0,
    "_margin_top": 0,
    "_margin_right": 0,
    "_margin_bottom": 0,
    "_margin_left": 0,
    "_background_color": None,
    "_fg": None,
    "_border": False,
    "_border_style": _SINGLE,
    "_border_color": None,
    "_title": None,
    "_title_alignment": _LEFT,
    "_border_top": True,
    "_border_right": True,
    "_border_bottom": True,
    "_border_left": True,
    "_border_chars": None,
    "_focusable": False,
    "_focused": False,
    "_focused_border_color": None,
    "_opacity": 1.0,
    "_z_index": 0,
    "_pos_top": None,
    "_pos_right": None,
    "_pos_bottom": None,
    "_pos_left": None,
    "_translate_x": 0,
    "_translate_y": 0,
    "_render_before": None,
    "_render_after": None,
    "_on_size_change": None,
    "_on_lifecycle_pass": None,
    "_on_mouse_down": None,
    "_on_mouse_up": None,
    "_on_mouse_move": None,
    "_on_mouse_drag": None,
    "_on_mouse_drag_end": None,
    "_on_mouse_drop": None,
    "_on_mouse_over": None,
    "_on_mouse_out": None,
    "_on_mouse_scroll": None,
    "_on_key_down": None,
    "_on_paste": None,
    "_live": False,
    "_live_count": 0,
    "_handle_paste": None,
    "_selectable": False,
    "_children_tuple": None,
    "_width": None,
    "_height": None,
    "_visible": True,
}

# Optional C++ native prop binding support (lazy-loaded to avoid import order issues)
_NATIVE_CACHE: dict[str, Any] = {
    "create_prop_binding": None,
    "yoga_configurator": None,
    "yoga_configurator_loaded": False,
    "configure_node_fast": None,
    "configure_node_fast_loaded": False,
}


def _get_yoga_configurator() -> Any:
    """Lazy import of the native YogaConfigurator."""
    if _NATIVE_CACHE["yoga_configurator_loaded"]:
        return _NATIVE_CACHE["yoga_configurator"]
    _NATIVE_CACHE["yoga_configurator_loaded"] = True
    if not _HAS_NATIVE:
        return None
    import sys

    nb = sys.modules.get("opentui_bindings")
    if nb is not None:
        try:
            _NATIVE_CACHE["yoga_configurator"] = nb.yoga_configure.YogaConfigurator()
            return _NATIVE_CACHE["yoga_configurator"]
        except AttributeError:
            pass
    return None


def _get_create_prop_binding() -> Any:
    """Lazy import of the native create_prop_binding function."""
    create_prop_binding = _NATIVE_CACHE["create_prop_binding"]
    if create_prop_binding is not None:
        return create_prop_binding
    if not _HAS_NATIVE:
        return None
    import sys

    nb = sys.modules.get("opentui_bindings")
    if nb is not None:
        try:
            _NATIVE_CACHE["create_prop_binding"] = nb.native_signals.create_prop_binding
            return _NATIVE_CACHE["create_prop_binding"]
        except AttributeError:
            pass
    return None


def _get_configure_node_fast() -> Any:
    """Lazy resolve of yoga.configure_node_fast without a module-global write in hot code."""
    if _NATIVE_CACHE["configure_node_fast_loaded"]:
        return _NATIVE_CACHE["configure_node_fast"]
    configure_node_fast = getattr(yoga, "configure_node_fast", None)
    _NATIVE_CACHE["configure_node_fast"] = configure_node_fast
    _NATIVE_CACHE["configure_node_fast_loaded"] = True
    return configure_node_fast


if TYPE_CHECKING:
    from ..renderer import Buffer


_SENTINEL = object()
_UNSET_FLEX_SHRINK = object()


class _PropBinding(NamedTuple):
    """A reactive prop binding: source, cleanup, and unsub-only callables."""

    source: object
    cleanup: Callable
    unsub_only: Callable


_renderable_id_counter = itertools.count(1)


def _next_id() -> int:
    return next(_renderable_id_counter)


@dataclass
class LayoutOptions:
    width: int | str | None = None
    height: int | str | None = None
    min_width: int | str | None = None
    min_height: int | str | None = None
    max_width: int | str | None = None
    max_height: int | str | None = None
    flex_grow: float = 0
    flex_shrink: float = 1
    flex_direction: str = "column"
    flex_wrap: str = "nowrap"
    flex_basis: float | str | None = None
    justify_content: str = "flex-start"
    align_items: str = "stretch"
    align_self: str | None = None
    gap: int = 0
    overflow: str = "visible"
    position: str = "relative"
    padding: int = 0
    padding_top: int | None = None
    padding_right: int | None = None
    padding_bottom: int | None = None
    padding_left: int | None = None
    padding_x: int | None = None
    padding_y: int | None = None
    margin: int = 0
    margin_top: int | None = None
    margin_right: int | None = None
    margin_bottom: int | None = None
    margin_left: int | None = None
    margin_x: int | None = None
    margin_y: int | None = None
    opacity: float = 1.0
    z_index: int = 0
    top: float | str | None = None
    right: float | str | None = None
    bottom: float | str | None = None
    left: float | str | None = None
    translate_x: float = 0
    translate_y: float = 0


@dataclass
class StyleOptions:
    background_color: s.RGBA | None = None
    fg: s.RGBA | None = None
    border: bool = False
    border_style: str = "single"
    border_color: s.RGBA | None = None
    title: str | None = None
    title_alignment: str = "left"


def is_renderable(obj: Any) -> bool:
    return isinstance(obj, BaseRenderable)


def _clamp_opacity(v: float) -> float:
    return max(0.0, min(1.0, v))


_parse_color_static = s.parse_color_opt


_DIRTY_NONE = 0
_DIRTY_LAYOUT = 1
_DIRTY_PAINT = 2
_DIRTY_HIT_PAINT = 3

_MOUSE_TRACKING_CACHE_SLOTS = frozenset(
    {
        "_visible",
        "_on_mouse_down",
        "_on_mouse_up",
        "_on_mouse_move",
        "_on_mouse_drag",
        "_on_mouse_drag_end",
        "_on_mouse_drop",
        "_on_mouse_over",
        "_on_mouse_out",
        "_on_mouse_scroll",
    }
)


class _Prop:
    """Descriptor for slot access with optional transform and dirty marking.

    Replaces three former descriptors (_SlotProperty, _DirtySlotProperty,
    _TransformDirtySlotProperty) with a single unified class.
    """

    __slots__ = ("_slot", "_transform", "_dirty")

    def __init__(
        self,
        slot: str,
        transform: Callable | None = None,
        *,
        paint_only: bool = False,
        hit_paint: bool = False,
        dirty: bool = True,
    ):
        self._slot = slot
        self._transform = transform
        if not dirty:
            self._dirty = _DIRTY_NONE
        elif hit_paint:
            self._dirty = _DIRTY_HIT_PAINT
        elif paint_only:
            self._dirty = _DIRTY_PAINT
        else:
            self._dirty = _DIRTY_LAYOUT

    def __get__(self, obj, objtype=None):
        return getattr(obj, self._slot) if obj is not None else self

    def __set__(self, obj, value):
        if self._transform is not None:
            value = self._transform(value)
        setattr(obj, self._slot, value)
        if self._slot in _MOUSE_TRACKING_CACHE_SLOTS:
            obj._invalidate_mouse_tracking_cache()
        d = self._dirty
        if d == _DIRTY_LAYOUT:
            obj.mark_dirty()
        elif d == _DIRTY_HIT_PAINT:
            obj.mark_hit_paint_dirty()
        elif d == _DIRTY_PAINT:
            obj.mark_paint_dirty()


class BaseRenderable:
    """Base class for all renderables."""

    # Global registry mapping renderable num to instance (OpenTUI core pattern).
    # Entries are removed in destroy() — size is bounded by live renderables.
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
        self._x: int = 0
        self._y: int = 0
        self._width: int | str | None = None
        self._height: int | str | None = None
        self._layout_width: int = 0
        self._layout_height: int = 0
        self._dirty: bool = True
        self._subtree_dirty: bool = True
        self._paint_subtree_dirty: bool = True
        self._hit_paint_dirty: bool = False
        self._destroyed: bool = False
        self._visible: bool = True
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
        """Computed layout width (set by yoga after layout pass)."""
        return self._layout_width

    @property
    def layout_height(self) -> int:
        """Computed layout height (set by yoga after layout pass)."""
        return self._layout_height

    @property
    def parent(self) -> BaseRenderable | None:
        return self._parent

    @property
    def children(self) -> tuple[BaseRenderable, ...]:
        """Read-only view of this renderable's children."""
        return self.get_children()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        """Mark this renderable as needing re-render and layout recalculation.

        Sets ``_dirty`` on this node and propagates ``_subtree_dirty`` up the
        parent chain (stopping at the first already-dirty ancestor for O(1)
        amortised cost).  Use this for changes that affect layout (size, flex,
        padding, visibility, etc.).
        """
        self._dirty = True
        node = self
        while node is not None and not node._subtree_dirty:
            node._subtree_dirty = True
            node = node._parent

    def mark_paint_dirty(self) -> None:
        """Mark this renderable as needing repaint without forcing layout work.

        Propagates ``_paint_subtree_dirty`` up the parent chain independently
        of ``_subtree_dirty``.  When only paint properties change (colors,
        opacity, text content), this lets the renderer skip the expensive yoga
        layout pass and repaint only the affected subtrees — saving 80-90% of
        frame time for visual-only updates.
        """
        self._dirty = True
        node = self
        while node is not None and not node._paint_subtree_dirty:
            node._paint_subtree_dirty = True
            node = node._parent

    def mark_hit_paint_dirty(self) -> None:
        """Mark that hit-test geometry changed without layout recalculation.

        Used for paint-only changes that affect which element is under the
        pointer: scroll offsets (shifts children) and z-index (changes
        stacking order).  Propagates ``_hit_paint_dirty`` so the renderer
        rechecks hover state.  Pure visual changes (colors, text content)
        use ``mark_paint_dirty`` alone and skip the expensive hover walk.
        """
        self.mark_paint_dirty()
        node = self
        while node is not None and not node._hit_paint_dirty:
            node._hit_paint_dirty = True
            node = node._parent

    def _queue_structural_clear_rect(self, rect: tuple[int, int, int, int]) -> None:
        x, y, width, height = rect
        if width <= 0 or height <= 0:
            return
        node: BaseRenderable | None = self
        while node is not None and node._parent is not None:
            node = node._parent
        renderer = getattr(node, "_renderer", None) if node is not None else None
        if renderer is not None:
            renderer.queue_structural_clear_rect((x, y, width, height))

    def _invalidate_renderer_structure_caches(self) -> None:
        node: BaseRenderable | None = self
        while node is not None and node._parent is not None:
            node = node._parent
        renderer = getattr(node, "_renderer", None) if node is not None else None
        if renderer is not None:
            renderer.invalidate_handler_cache()

    def _invalidate_mouse_tracking_cache(self) -> None:
        node: BaseRenderable | None = self
        while node is not None and node._parent is not None:
            node = node._parent
        renderer = getattr(node, "_renderer", None) if node is not None else None
        if renderer is not None:
            renderer._mouse_tracking_dirty = True

    def _adjust_renderer_layout_hook_cache(self, delta: int) -> None:
        node: BaseRenderable | None = self
        while node is not None and node._parent is not None:
            node = node._parent
        renderer = getattr(node, "_renderer", None) if node is not None else None
        if renderer is not None:
            renderer.adjust_layout_hook_cache_for_subtree(self, delta)

    def _sync_yoga_display(self) -> None:
        if self._yoga_node is None:
            return
        self._yoga_node.display = yoga.Display.Flex if self._visible else yoga.Display.None_

    def _configure_yoga_properties(self) -> None:
        """Configure yoga properties on this node and all descendants.

        Unlike the old _build_yoga_tree, this does NOT rebuild yoga children —
        children are managed incrementally by add/remove and the reconciler.
        Skips clean subtrees via _subtree_dirty for O(changed) traversal.

        When a C++ YogaConfigurator is available, the tree walk is done in C++
        with direct __slots__ reads and direct yoga C API calls.
        """
        configurator = _get_yoga_configurator()
        if configurator is not None:
            try:
                configurator.configure_tree(self)
            except TypeError:
                # Fallback: old API with configure_node_fast argument
                configurator.configure_tree(self, yoga.configure_node_fast)
            return
        # Python fallback
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
        """Called before yoga configure. Override for pre-setup (e.g. For reconciliation)."""

    def _post_configure_yoga(self, node: Any) -> None:
        """Called after yoga configure. Override for post-adjust (e.g. Show display toggle)."""

    def _configure_yoga_node(self, node: Any) -> None:
        pass

    def _apply_yoga_layout(self) -> None:
        """Apply computed yoga layout to this renderable.

        Reads directly from yoga node attributes (avoiding dict allocation).
        Writes positions to _x/_y (later converted to absolute screen
        coordinates by _apply_yoga_layout_recursive) and computed
        dimensions to _layout_width/_layout_height.  The original
        _width/_height are left untouched so _configure_yoga_node always
        sees the developer-specified values (None for flex, 30 for fixed).
        """
        node = self._yoga_node
        if node is None:
            return
        self._x = int(node.layout_left)
        self._y = int(node.layout_top)
        self._layout_width = int(node.layout_width)
        self._layout_height = int(node.layout_height)

    @property
    def num(self) -> int:
        """Unique integer identifier for this renderable."""
        return self._num

    @property
    def id(self) -> str:
        """String identifier (default ``renderable-<num>``, or custom)."""
        return self._id

    @id.setter
    def id(self, value: str) -> None:
        self._id = value

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value
        self._sync_yoga_display()
        self.mark_dirty()

    @property
    def is_destroyed(self) -> bool:
        return self._destroyed

    def participates_in_parent_yoga(self) -> bool:
        """Return True when this node should be inserted into its parent's Yoga tree."""
        return True

    def affects_parent_paint(self) -> bool:
        """Return True when attach/remove should invalidate the logical parent's paint path."""
        return True

    def add(self, child: BaseRenderable | None, index: int | None = None) -> int:
        """Add a child renderable.  Returns the child's index, or -1 if destroyed."""
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
        """Add multiple children in a single batch.

        More efficient than calling add() in a loop: yoga's
        markDirtyAndPropagate() fires once instead of N times.
        """
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
            yoga_children = []
            for child in self._children:
                if child._yoga_node is not None and child.participates_in_parent_yoga():
                    yoga_owner = child._yoga_node.owner
                    if yoga_owner is not None and yoga_owner is not self._yoga_node:
                        yoga_owner.remove_child(child._yoga_node)
                    yoga_children.append(child._yoga_node)
            self._yoga_node.set_children(yoga_children)
        if any_yoga:
            self.mark_dirty()
        elif any(child.affects_parent_paint() for child in children if child is not None):
            self.mark_hit_paint_dirty()

    def remove(self, child: BaseRenderable) -> None:
        if child in self._children:
            clear_rect = (
                int(getattr(child, "_x", 0) or 0),
                int(getattr(child, "_y", 0) or 0),
                int(getattr(child, "_layout_width", 0) or 0),
                int(getattr(child, "_layout_height", 0) or 0),
            )
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
        """Insert a child before an anchor.  Returns the insertion index."""
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
        """Get all children as an immutable tuple."""
        if self._children_tuple is None:
            self._children_tuple = tuple(self._children)
        return self._children_tuple

    def get_children_count(self) -> int:
        return len(self._children)

    def contains_point(self, x: int, y: int) -> bool:
        """Return True when *(x, y)* falls within this renderable's layout bounds."""
        width = int(self._layout_width or 0)
        height = int(self._layout_height or 0)
        if width <= 0 or height <= 0:
            return False
        return self._x <= x < self._x + width and self._y <= y < self._y + height

    def get_renderable(self, id: str) -> BaseRenderable | None:
        """Find a child (direct only) by string ID."""
        for child in self._children:
            if child._id == id:
                return child
        return None

    def find_descendant_by_id(self, id: str) -> BaseRenderable | None:
        """Recursively find a descendant by string ID."""
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
        """Register a cleanup function to run when this renderable is destroyed."""
        self._cleanups[id(fn)] = fn

    def destroy(self) -> None:
        """Destroy this renderable, running cleanups first."""
        if self._destroyed:
            return
        self._destroyed = True
        # Remove from global lookup (matches OpenTUI core behavior).
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


class Renderable(BaseRenderable):
    """Base renderable with layout and styling."""

    __slots__ = (
        "_min_width",
        "_min_height",
        "_max_width",
        "_max_height",
        "_flex_grow",
        "_flex_shrink",
        "_flex_direction",
        "_flex_wrap",
        "_flex_basis",
        "_justify_content",
        "_align_items",
        "_align_self",
        "_gap",
        "_row_gap",
        "_column_gap",
        "_overflow",
        "_position",
        "_padding",
        "_padding_top",
        "_padding_right",
        "_padding_bottom",
        "_padding_left",
        "_margin",
        "_margin_top",
        "_margin_right",
        "_margin_bottom",
        "_margin_left",
        "_background_color",
        "_fg",
        "_border",
        "_border_style",
        "_border_color",
        "_title",
        "_title_alignment",
        "_border_top",
        "_border_right",
        "_border_bottom",
        "_border_left",
        "_border_chars",
        "_focusable",
        "_focused",
        "_focused_border_color",
        "_opacity",
        "_z_index",
        "_pos_top",
        "_pos_right",
        "_pos_bottom",
        "_pos_left",
        "_translate_x",
        "_translate_y",
        "_render_before",
        "_render_after",
        "_on_size_change",
        "_on_mouse_down",
        "_on_mouse_up",
        "_on_mouse_move",
        "_on_mouse_drag",
        "_on_mouse_drag_end",
        "_on_mouse_drop",
        "_on_mouse_over",
        "_on_mouse_out",
        "_on_mouse_scroll",
        "_on_key_down",
        "_on_paste",
        "_live",
        "_live_count",
        "_handle_paste",
        "_selectable",
        "_on_lifecycle_pass",
        "_row_gap",
        "_column_gap",
        "_prop_bindings",
        "_yoga_config_cache",
        # Fast-path flag: True while all layout/style slots are at defaults
        "_is_simple",
    )

    _LAYOUT_PROPS: frozenset[str] = frozenset(
        {
            "_content",
            "_wrap_mode",
            "_width",
            "_height",
            "_min_width",
            "_min_height",
            "_max_width",
            "_max_height",
            "_flex_grow",
            "_flex_shrink",
            "_flex_direction",
            "_flex_wrap",
            "_flex_basis",
            "_justify_content",
            "_align_items",
            "_align_self",
            "_gap",
            "_row_gap",
            "_column_gap",
            "_padding",
            "_padding_top",
            "_padding_right",
            "_padding_bottom",
            "_padding_left",
            "_margin",
            "_margin_top",
            "_margin_right",
            "_margin_bottom",
            "_margin_left",
            "_overflow",
            "_position",
            "_pos_top",
            "_pos_right",
            "_pos_bottom",
            "_pos_left",
            # Border affects yoga via effective padding (base.py _configure_yoga_node)
            "_border",
            "_border_top",
            "_border_right",
            "_border_bottom",
            "_border_left",
        }
    )

    def __init__(
        self,
        *,
        key: str | int | None = None,
        id: str | None = None,
        width: int | str | None = None,
        height: int | str | None = None,
        min_width: int | str | None = None,
        min_height: int | str | None = None,
        max_width: int | str | None = None,
        max_height: int | str | None = None,
        flex_grow: float = 0,
        flex_shrink: float | object = _UNSET_FLEX_SHRINK,
        flex_direction: str = _COLUMN,
        flex_wrap: str = _NOWRAP,
        flex_basis: float | str | None = None,
        justify_content: str = _FLEX_START,
        align_items: str = _STRETCH,
        align_self: str | None = None,
        gap: int = 0,
        row_gap: float | None = None,
        column_gap: float | None = None,
        overflow: str = _VISIBLE,
        position: str = _RELATIVE,
        padding: int = 0,
        padding_top: int | None = None,
        padding_right: int | None = None,
        padding_bottom: int | None = None,
        padding_left: int | None = None,
        padding_x: int | None = None,
        padding_y: int | None = None,
        margin: int = 0,
        margin_top: int | None = None,
        margin_right: int | None = None,
        margin_bottom: int | None = None,
        margin_left: int | None = None,
        margin_x: int | None = None,
        margin_y: int | None = None,
        background_color: s.RGBA | str | None = None,
        fg: s.RGBA | str | None = None,
        border: bool = False,
        border_style: str = _SINGLE,
        border_color: s.RGBA | str | None = None,
        title: str | None = None,
        title_alignment: str = _LEFT,
        border_top: bool = True,
        border_right: bool = True,
        border_bottom: bool = True,
        border_left: bool = True,
        border_chars: dict | None = None,
        focusable: bool = False,
        focused: bool = False,
        focused_border_color: s.RGBA | str | None = None,
        visible: bool = True,
        opacity: float = 1.0,
        z_index: int = 0,
        top: float | str | None = None,
        right: float | str | None = None,
        bottom: float | str | None = None,
        left: float | str | None = None,
        translate_x: float = 0,
        translate_y: float = 0,
        live: bool = False,
        on_mouse_down: Callable | None = None,
        on_mouse_up: Callable | None = None,
        on_mouse_move: Callable | None = None,
        on_mouse_drag: Callable | None = None,
        on_mouse_drag_end: Callable | None = None,
        on_mouse_drop: Callable | None = None,
        on_mouse_over: Callable | None = None,
        on_mouse_out: Callable | None = None,
        on_mouse_scroll: Callable | None = None,
        on_key_down: Callable | None = None,
        on_paste: Callable | None = None,
        on_size_change: Callable | None = None,
    ):
        super().__init__(key=key, id=id)

        # Must exist before _set_or_bind calls
        self._prop_bindings: dict[str, _PropBinding] | None = None
        self._yoga_config_cache: tuple | None = None
        # Fast-path flag for reconciler text patching
        self._is_simple: bool = True

        if isinstance(width, int | float) and width < 0:
            raise ValueError(f"width must be non-negative, got {width}")
        if isinstance(height, int | float) and height < 0:
            raise ValueError(f"height must be non-negative, got {height}")

        # Initialize None-default slots eagerly so skipped _set_or_bind calls
        # don't leave slots as unset descriptors (which raise AttributeError).
        self._min_width: int | str | None = None
        self._min_height: int | str | None = None
        self._max_width: int | str | None = None
        self._max_height: int | str | None = None
        self._flex_basis: float | str | None = None
        self._align_self: str | None = None
        self._row_gap: float | None = None
        self._column_gap: float | None = None
        self._background_color: s.RGBA | None = None
        self._fg: s.RGBA | None = None
        self._border_color: s.RGBA | None = None
        self._title: str | None = None
        self._border_chars: dict | None = None
        self._focused_border_color: s.RGBA | None = None
        self._pos_top: float | str | None = None
        self._pos_right: float | str | None = None
        self._pos_bottom: float | str | None = None
        self._pos_left: float | str | None = None
        explicit_numeric_size = isinstance(width, int | float) or isinstance(height, int | float)
        resolved_flex_shrink = (
            (0 if explicit_numeric_size else 1)
            if flex_shrink is _UNSET_FLEX_SHRINK
            else flex_shrink
        )
        if width is not None:
            self._set_or_bind("_width", width)
        if height is not None:
            self._set_or_bind("_height", height)
        if min_width is not None:
            self._set_or_bind("_min_width", min_width)
        if min_height is not None:
            self._set_or_bind("_min_height", min_height)
        if max_width is not None:
            self._set_or_bind("_max_width", max_width)
        if max_height is not None:
            self._set_or_bind("_max_height", max_height)
        self._set_or_bind("_flex_grow", flex_grow)
        self._set_or_bind("_flex_shrink", resolved_flex_shrink)
        self._set_or_bind("_flex_direction", flex_direction)
        self._set_or_bind("_flex_wrap", flex_wrap)
        if flex_basis is not None:
            self._set_or_bind("_flex_basis", flex_basis)
        self._set_or_bind("_justify_content", justify_content)
        self._set_or_bind("_align_items", align_items)
        if align_self is not None:
            self._set_or_bind("_align_self", align_self)
        self._set_or_bind("_gap", gap)
        if row_gap is not None:
            self._set_or_bind("_row_gap", row_gap)
        if column_gap is not None:
            self._set_or_bind("_column_gap", column_gap)
        self._set_or_bind("_overflow", overflow)
        self._set_or_bind("_position", position)

        self._padding = padding
        for attr, specific, axis in (
            ("_padding_top", padding_top, padding_y),
            ("_padding_right", padding_right, padding_x),
            ("_padding_bottom", padding_bottom, padding_y),
            ("_padding_left", padding_left, padding_x),
        ):
            self._set_or_bind(
                attr, specific if specific is not None else (axis if axis is not None else padding)
            )

        self._margin = margin
        for attr, specific, axis in (
            ("_margin_top", margin_top, margin_y),
            ("_margin_right", margin_right, margin_x),
            ("_margin_bottom", margin_bottom, margin_y),
            ("_margin_left", margin_left, margin_x),
        ):
            self._set_or_bind(
                attr, specific if specific is not None else (axis if axis is not None else margin)
            )

        if background_color is not None:
            self._set_or_bind("_background_color", background_color, transform=self._parse_color)
        if fg is not None:
            self._set_or_bind("_fg", fg, transform=self._parse_color)
        self._set_or_bind("_border", border)
        self._set_or_bind("_border_style", border_style, transform=s.parse_border_style)
        if border_color is not None:
            self._set_or_bind("_border_color", border_color, transform=self._parse_color)
        if title is not None:
            self._set_or_bind("_title", title)
        self._set_or_bind("_title_alignment", title_alignment)

        self._set_or_bind("_border_top", border_top)
        self._set_or_bind("_border_right", border_right)
        self._set_or_bind("_border_bottom", border_bottom)
        self._set_or_bind("_border_left", border_left)
        if border_chars is not None:
            self._set_or_bind("_border_chars", border_chars)

        self._set_or_bind("_focusable", focusable)
        self._set_or_bind("_focused", focused)
        if focused_border_color is not None:
            self._set_or_bind(
                "_focused_border_color", focused_border_color, transform=self._parse_color
            )

        if self._focused_border_color and not self._border:
            self._border = True

        self._set_or_bind("_visible", visible)
        self._sync_yoga_display()
        self._set_or_bind("_opacity", opacity, transform=_clamp_opacity)

        self._set_or_bind("_z_index", z_index)

        if top is not None:
            self._set_or_bind("_pos_top", top)
        if right is not None:
            self._set_or_bind("_pos_right", right)
        if bottom is not None:
            self._set_or_bind("_pos_bottom", bottom)
        if left is not None:
            self._set_or_bind("_pos_left", left)

        self._set_or_bind("_translate_x", translate_x)
        self._set_or_bind("_translate_y", translate_y)

        self._render_before: Callable | None = None
        self._render_after: Callable | None = None
        self._on_size_change: Callable | None = on_size_change

        self._on_mouse_down: Callable | None = on_mouse_down
        self._on_mouse_up: Callable | None = on_mouse_up
        self._on_mouse_move: Callable | None = on_mouse_move
        self._on_mouse_drag: Callable | None = on_mouse_drag
        self._on_mouse_drag_end: Callable | None = on_mouse_drag_end
        self._on_mouse_drop: Callable | None = on_mouse_drop
        self._on_mouse_over: Callable | None = on_mouse_over
        self._on_mouse_out: Callable | None = on_mouse_out
        self._on_mouse_scroll: Callable | None = on_mouse_scroll

        self._on_key_down: Callable | None = on_key_down
        self._on_paste: Callable | None = on_paste

        self._live = live
        self._live_count = 1 if live and self._visible else 0

        self._handle_paste: Callable | None = None
        self._on_lifecycle_pass: Callable | None = None

        self._selectable: bool = False

    _parse_color = staticmethod(_parse_color_static)

    @property
    def x(self) -> int:
        return self._x

    @property
    def y(self) -> int:
        return self._y

    @property
    def width(self) -> int | str | None:
        return self._width

    @width.setter
    def width(self, value: int | str | None) -> None:
        self._width = value
        if isinstance(value, int | float) and self._flex_shrink == 1:
            self._flex_shrink = 0
        self.mark_dirty()

    @property
    def height(self) -> int | str | None:
        return self._height

    @height.setter
    def height(self, value: int | str | None) -> None:
        self._height = value
        if isinstance(value, int | float) and self._flex_shrink == 1:
            self._flex_shrink = 0
        self.mark_dirty()

    min_width = _Prop("_min_width")

    min_height = _Prop("_min_height")

    max_width = _Prop("_max_width")

    max_height = _Prop("_max_height")

    flex_grow = _Prop("_flex_grow")

    flex_shrink = _Prop("_flex_shrink")

    flex_direction = _Prop("_flex_direction")

    flex_wrap = _Prop("_flex_wrap")

    flex_basis = _Prop("_flex_basis")

    justify_content = _Prop("_justify_content")

    align_items = _Prop("_align_items")

    align_self = _Prop("_align_self")

    gap = _Prop("_gap")

    row_gap = _Prop("_row_gap")

    column_gap = _Prop("_column_gap")

    @property
    def padding(self) -> int:
        return self._padding

    @padding.setter
    def padding(self, value: int) -> None:
        self._padding = value
        self._padding_top = value
        self._padding_right = value
        self._padding_bottom = value
        self._padding_left = value
        self.mark_dirty()

    padding_top = _Prop("_padding_top")

    padding_right = _Prop("_padding_right")

    padding_bottom = _Prop("_padding_bottom")

    padding_left = _Prop("_padding_left")

    overflow = _Prop("_overflow")

    position = _Prop("_position")

    background_color = _Prop("_background_color", _parse_color_static, paint_only=True)

    fg = _Prop("_fg", _parse_color_static, paint_only=True)

    @property
    def border(self) -> bool:
        return self._border

    border_style = _Prop("_border_style", s.parse_border_style, paint_only=True)

    border_color = _Prop("_border_color", _parse_color_static, paint_only=True)

    title = _Prop("_title", paint_only=True)

    @property
    def focusable(self) -> bool:
        return self._focusable

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        if self._focused == value:
            return
        self._focused = value
        self.mark_paint_dirty()

    def focus(self) -> None:
        self.focused = True

    def blur(self) -> None:
        self.focused = False

    opacity = _Prop("_opacity", _clamp_opacity, paint_only=True)

    z_index = _Prop("_z_index", hit_paint=True)

    pos_top = _Prop("_pos_top")

    pos_right = _Prop("_pos_right")

    pos_bottom = _Prop("_pos_bottom")

    pos_left = _Prop("_pos_left")

    translate_x = _Prop("_translate_x")

    translate_y = _Prop("_translate_y")

    @property
    def display(self) -> str:
        """Yoga display mode: ``"flex"`` when visible, ``"none"`` when hidden."""
        return "flex" if self._visible else "none"

    @display.setter
    def display(self, value: str) -> None:
        """Set display mode. ``"none"`` hides, anything else shows."""
        self.visible = value != "none"

    @BaseRenderable.visible.setter
    def visible(self, value: bool) -> None:
        old = self._visible
        if old == value:
            return
        self._visible = value
        self._invalidate_mouse_tracking_cache()
        self._sync_yoga_display()
        self.mark_dirty()
        if self._live:
            self._propagate_live_count(1 if value else -1)

    @property
    def live(self) -> bool:
        return self._live

    @live.setter
    def live(self, value: bool) -> None:
        if self._live == value:
            return
        self._live = value
        if self._visible:
            delta = 1 if value else -1
            self._propagate_live_count(delta)

    @property
    def live_count(self) -> int:
        """Number of live descendants (including self) for live-mode scheduling."""
        return self._live_count

    def _propagate_live_count(self, delta: int) -> None:
        self._live_count += delta
        if self._parent is not None and isinstance(self._parent, Renderable):
            self._parent._propagate_live_count(delta)

    def _set_or_bind(self, attr: str, value: object, *, transform: Callable | None = None) -> None:
        """Set an attribute statically or bind it to a reactive source.

        If value is a Signal, ComputedSignal, or callable (not str/type):
        wraps with optional transform and creates a reactive binding.
        Otherwise: applies transform (if any) and sets directly.
        """
        if getattr(value, "__opentui_template_binding__", False):
            setattr(self, attr, value)
            return
        if isinstance(value, Signal | _ComputedSignal):
            source = value.map(transform) if transform else value
            self._bind_reactive_prop(attr, source)
            self._is_simple = False
        elif callable(value) and not isinstance(value, str | type):
            if transform:
                raw_fn = value
                source = lambda: transform(raw_fn())  # noqa: E731
            else:
                source = value
            self._bind_reactive_prop(attr, source)
            self._is_simple = False
        else:
            resolved = transform(value) if transform and value is not None else value
            setattr(self, attr, resolved)
            # Track whether this attr diverges from the "simple text" defaults
            if (
                self._is_simple
                and attr in _SIMPLE_DEFAULTS
                and resolved is not _SIMPLE_DEFAULTS[attr]
                and resolved != _SIMPLE_DEFAULTS[attr]
            ):
                self._is_simple = False

    def _make_on_change(self, attr: str, yogadirty: bool) -> Callable[[object], None]:
        """Create a reactive prop change callback for the given attribute.

        Auto-selects dirty level: layout props use mark_dirty() (triggers yoga),
        visual-only props use mark_paint_dirty() (skips yoga). _visible is
        special-cased because it needs _propagate_live_count side effects.
        """
        propagate_live = attr == "_visible"

        if yogadirty or propagate_live:

            def on_change(new_value: object) -> None:
                old = getattr(self, attr, _SENTINEL)
                if old is new_value or old == new_value:
                    return
                setattr(self, attr, new_value)
                self.mark_dirty()
                if yogadirty and self._yoga_node is not None:
                    try:
                        self._yoga_node.mark_dirty()
                    except RuntimeError as e:
                        if "leaf" not in str(e) and "measure" not in str(e):
                            raise
                if propagate_live and self._live:
                    self._propagate_live_count(1 if new_value else -1)
        else:

            def on_change(new_value: object) -> None:
                old = getattr(self, attr, _SENTINEL)
                if old is new_value or old == new_value:
                    return
                setattr(self, attr, new_value)
                self.mark_paint_dirty()

        return on_change

    def _make_on_change_callable(
        self, attr: str, yogadirty: bool, fn: Callable[[], object]
    ) -> Callable[[object], None]:
        """Create a reactive prop callback that re-evaluates a callable on change.

        Used for single-dep callable fast path — subscribes directly to the dep
        signal, skipping the ComputedSignal intermediary.
        """
        if yogadirty:

            def on_change(_: object) -> None:
                token = _tracking_context.set(None)
                try:
                    new_value = fn()
                finally:
                    _tracking_context.reset(token)
                old = getattr(self, attr, _SENTINEL)
                if old is new_value or old == new_value:
                    return
                setattr(self, attr, new_value)
                self.mark_dirty()
                if self._yoga_node is not None:
                    try:
                        self._yoga_node.mark_dirty()
                    except RuntimeError as e:
                        if "leaf" not in str(e) and "measure" not in str(e):
                            raise
        else:

            def on_change(_: object) -> None:
                token = _tracking_context.set(None)
                try:
                    new_value = fn()
                finally:
                    _tracking_context.reset(token)
                old = getattr(self, attr, _SENTINEL)
                if old is new_value or old == new_value:
                    return
                setattr(self, attr, new_value)
                self.mark_paint_dirty()

        return on_change

    def _bind_reactive_prop(self, attr: str, source: object) -> bool:
        """Bind an attribute to a reactive source (Signal, ComputedSignal, or callable).

        Sets the initial value and subscribes so future changes update the attr,
        mark the node dirty, and (for layout props) mark the yoga node dirty.
        Returns True if binding was created, False if source is not reactive.
        """
        self._unbind_reactive_prop(attr)

        yogadirty = attr in self._LAYOUT_PROPS

        if isinstance(source, Signal | _ComputedSignal):
            # Subscribable source — read initial value without polluting tracking context
            token = _tracking_context.set(None)
            try:
                initial = source()
            finally:
                _tracking_context.reset(token)
            setattr(self, attr, initial)

            # Fast path: C++ NativePropBinding for direct Signals (no transform).
            # The native C++ path writes directly to __slots__, bypassing
            # property setters.  For _visible, a post_write_callback handles
            # the _propagate_live_count side effect that the property setter
            # would normally perform.
            native = getattr(source, "_native", None)
            cpb = _get_create_prop_binding() if native is not None else None
            if native is not None and cpb is not None:
                try:
                    # Build post-write callback for _visible to maintain live_count.
                    # Also propagates _subtree_dirty (mark_dirty) since _visible
                    # is not in _LAYOUT_PROPS but still needs layout-level dirtying.
                    pwc = None
                    if attr == "_visible":

                        def _visible_post_write(old_val: object, new_val: object) -> None:
                            self.mark_dirty()
                            if self._live:
                                self._propagate_live_count(1 if new_val else -1)

                        pwc = _visible_post_write

                    binding = cpb(
                        self,
                        attr,
                        yoga_dirty=yogadirty,
                        post_write_callback=pwc,
                    )
                    native.add_prop_binding(binding)
                    slot_offset = binding.slot_offset

                    def native_cleanup() -> None:
                        native.remove_prop_binding(self, slot_offset)

                    if self._prop_bindings is None:
                        self._prop_bindings = {}
                    self._prop_bindings[attr] = _PropBinding(source, native_cleanup, native_cleanup)
                    self._cleanups[id(native_cleanup)] = native_cleanup
                    return True
                except (ValueError, RuntimeError):
                    pass

            # Slow path: Python callback subscription
            on_change = self._make_on_change(attr, yogadirty)
            unsub = source.subscribe(on_change)
            is_inline_computed = isinstance(source, _ComputedSignal)

            def cleanup() -> None:
                unsub()
                if is_inline_computed:
                    source.dispose()

            def unsub_only() -> None:
                unsub()

            if self._prop_bindings is None:
                self._prop_bindings = {}
            self._prop_bindings[attr] = _PropBinding(source, cleanup, unsub_only)
            self._cleanups[id(cleanup)] = cleanup
            return True

        elif callable(source) and not isinstance(source, type):
            tracked: set[Signal] = set()
            token = _tracking_context.set(tracked)
            try:
                source()  # Discover deps (value discarded)
            except Exception:
                log.warning("Reactive prop callable raised during dep discovery for %r", attr)
                return False
            finally:
                _tracking_context.reset(token)

            if len(tracked) == 1:
                # Fast path: single dep — subscribe directly, skip ComputedSignal
                dep = next(iter(tracked))
                token2 = _tracking_context.set(None)
                try:
                    initial = source()
                finally:
                    _tracking_context.reset(token2)
                setattr(self, attr, initial)

                on_change = self._make_on_change_callable(attr, yogadirty, source)
                unsub = dep.subscribe(on_change)

                def cleanup_single() -> None:
                    unsub()

                if self._prop_bindings is None:
                    self._prop_bindings = {}
                self._prop_bindings[attr] = _PropBinding(source, cleanup_single, cleanup_single)
                self._cleanups[id(cleanup_single)] = cleanup_single
                return True

            # Multi-dep or zero-dep — use ComputedSignal for auto-tracking
            token2 = _tracking_context.set(None)
            try:
                computed_sig = _ComputedSignal(source)
                initial = computed_sig()
            finally:
                _tracking_context.reset(token2)
            setattr(self, attr, initial)

            on_change = self._make_on_change(attr, yogadirty)
            unsub_c = computed_sig.subscribe(on_change)

            def cleanup_c() -> None:
                unsub_c()
                computed_sig.dispose()

            if self._prop_bindings is None:
                self._prop_bindings = {}
            self._prop_bindings[attr] = _PropBinding(source, cleanup_c, cleanup_c)
            self._cleanups[id(cleanup_c)] = cleanup_c
            return True

        return False

    def _unbind_reactive_prop(self, attr: str) -> None:
        if self._prop_bindings is None:
            return
        binding = self._prop_bindings.pop(attr, None)
        if binding is None:
            return
        with contextlib.suppress(Exception):
            binding.cleanup()
        self._cleanups.pop(id(binding.cleanup), None)
        if not self._prop_bindings:
            self._prop_bindings = None

    def _unbind_all_reactive_props(self) -> None:
        if self._prop_bindings is None:
            return
        for _attr, binding in list(self._prop_bindings.items()):
            with contextlib.suppress(Exception):
                binding.cleanup()
            self._cleanups.pop(id(binding.cleanup), None)
        self._prop_bindings = None

    render_before = _Prop("_render_before", dirty=False)
    render_after = _Prop("_render_after", dirty=False)
    on_size_change = _Prop("_on_size_change", dirty=False)

    on_mouse_down = _Prop("_on_mouse_down", dirty=False)
    on_mouse_up = _Prop("_on_mouse_up", dirty=False)
    on_mouse_move = _Prop("_on_mouse_move", dirty=False)
    on_mouse_drag = _Prop("_on_mouse_drag", dirty=False)
    on_mouse_drag_end = _Prop("_on_mouse_drag_end", dirty=False)
    on_mouse_drop = _Prop("_on_mouse_drop", dirty=False)
    on_mouse_over = _Prop("_on_mouse_over", dirty=False)
    on_mouse_out = _Prop("_on_mouse_out", dirty=False)
    on_mouse_scroll = _Prop("_on_mouse_scroll", dirty=False)
    on_key_down = _Prop("_on_key_down", dirty=False)
    on_paste = _Prop("_on_paste", dirty=False)
    handle_paste = _Prop("_handle_paste", dirty=False)

    selectable = _Prop("_selectable", dirty=False)

    on_lifecycle_pass = _Prop("_on_lifecycle_pass", dirty=False)

    def handle_key_press(self, key: Any) -> bool:
        """Handle a key press after the user-facing on_key_down listener.

        Called only if on_key_down did not call prevent_default().
        Override in subclasses to provide component-specific key handling.
        Returns True if the key was handled.
        """
        return False

    def should_start_selection(self, x: int, y: int) -> bool:
        """Return True if this renderable should start a selection at (x, y).

        Default returns False. Override in subclasses that support selection.
        """
        return False

    def has_selection(self) -> bool:
        """Return True if this renderable has an active selection.

        Default returns False. Override in subclasses that support selection.
        """
        return False

    def on_selection_changed(self, selection: Any) -> bool:
        """Called when the global selection changes.

        Override this method to provide custom selection handling.
        Returns True if this renderable has a selection after the change.
        """
        return False

    def get_selected_text(self) -> str:
        """Return the selected text in this renderable.

        Default returns empty string. Override in subclasses.
        """
        return ""

    def dispatch_paste(self, event: Any) -> None:
        """Two-phase paste dispatch matching OpenTUI core Renderable.

        Phase 1: call ``on_paste`` (the user-facing listener).
        Phase 2: if ``event.default_prevented`` is *not* set,
                 call ``handle_paste`` (the component-internal handler).
        """
        if self._on_paste is not None:
            self._on_paste(event)
        if self._destroyed:
            return
        prevented = getattr(event, "default_prevented", False)
        if not prevented and self._handle_paste is not None:
            self._handle_paste(event)

    def _configure_yoga_node(self, node: Any) -> None:
        # Border adds to effective padding for yoga layout purposes
        bt = 1 if self._border and self._border_top else 0
        br = 1 if self._border and self._border_right else 0
        bb = 1 if self._border and self._border_bottom else 0
        bl = 1 if self._border and self._border_left else 0

        # Fast exit: if this node's own props haven't changed (not _dirty)
        # and we have a cached config, skip tuple construction entirely.
        # This node is only being traversed because a descendant is dirty.
        if not self._dirty and self._yoga_config_cache is not None:
            return

        # Config cache: skip redundant configure_node() calls (~2,000ns each)
        # when this node is traversed only because a descendant is dirty.
        config = (
            self._width,
            self._height,
            self._min_width,
            self._min_height,
            self._max_width,
            self._max_height,
            self._flex_grow,
            self._flex_shrink,
            self._flex_basis,
            self._flex_direction,
            self._flex_wrap,
            self._justify_content,
            self._align_items,
            self._align_self,
            self._gap,
            self._row_gap,
            self._column_gap,
            self._overflow,
            self._position,
            self._padding_top + bt,
            self._padding_right + br,
            self._padding_bottom + bb,
            self._padding_left + bl,
            self._margin,
            self._margin_top,
            self._margin_right,
            self._margin_bottom,
            self._margin_left,
            self._pos_top,
            self._pos_right,
            self._pos_bottom,
            self._pos_left,
        )
        if self._yoga_config_cache == config:
            return
        self._yoga_config_cache = config

        configure_node_fast = _get_configure_node_fast()
        common_kwargs = {
            "width": self._width,
            "height": self._height,
            "min_width": self._min_width,
            "min_height": self._min_height,
            "max_width": self._max_width,
            "max_height": self._max_height,
            "flex_grow": float(self._flex_grow) if self._flex_grow else None,
            "flex_shrink": float(self._flex_shrink),
            "flex_basis": self._flex_basis,
            "flex_direction": self._flex_direction if self._flex_direction is not _COLUMN else None,
            "flex_wrap": self._flex_wrap if self._flex_wrap is not _NOWRAP else None,
            "justify_content": self._justify_content
            if self._justify_content is not _FLEX_START
            else None,
            "align_items": self._align_items if self._align_items is not _STRETCH else None,
            "align_self": self._align_self,
            "gap": float(self._gap) if self._gap else None,
            "overflow": self._overflow if self._overflow is not _VISIBLE else None,
            "position_type": self._position if self._position is not _RELATIVE else None,
            "padding_top": float(self._padding_top + bt),
            "padding_right": float(self._padding_right + br),
            "padding_bottom": float(self._padding_bottom + bb),
            "padding_left": float(self._padding_left + bl),
            "margin": float(self._margin) if self._margin else None,
            "margin_top": float(self._margin_top) if self._margin_top is not None else None,
            "margin_right": float(self._margin_right) if self._margin_right is not None else None,
            "margin_bottom": float(self._margin_bottom)
            if self._margin_bottom is not None
            else None,
            "margin_left": float(self._margin_left) if self._margin_left is not None else None,
        }
        if callable(configure_node_fast):
            configure_node_fast(
                node,
                **common_kwargs,
                pos_top=self._pos_top,
                pos_right=self._pos_right,
                pos_bottom=self._pos_bottom,
                pos_left=self._pos_left,
            )
        else:
            yoga_layout.configure_node(
                node,
                **common_kwargs,
                row_gap=float(self._row_gap) if self._row_gap else None,
                column_gap=float(self._column_gap) if self._column_gap else None,
                top=self._pos_top,
                right=self._pos_right,
                bottom=self._pos_bottom,
                left=self._pos_left,
                display="flex" if self._visible else "none",
            )
        # row_gap/column_gap: configure_node_fast only supports "gap" (all),
        # so apply axis-specific gaps directly on the yoga node.
        if self._row_gap is not None:
            node.set_gap(yoga.Gutter.Row, float(self._row_gap))
        if self._column_gap is not None:
            node.set_gap(yoga.Gutter.Column, float(self._column_gap))

    def _apply_yoga_layout(self) -> None:
        node = self._yoga_node
        if node is None:
            return
        old_w = self._layout_width
        old_h = self._layout_height
        self._x, self._y, self._layout_width, self._layout_height = yoga.get_layout_batch(node)

        if self._on_size_change and (old_w != self._layout_width or old_h != self._layout_height):
            self._on_size_change(self._layout_width, self._layout_height)

    def update_layout(self, delta_time: float = 0) -> None:
        pass

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        for child in self._children:
            child.render(buffer, delta_time)

        if self._render_after:
            self._render_after(buffer, delta_time, self)


__all__ = [
    "BaseRenderable",
    "Renderable",
    "LayoutOptions",
    "StyleOptions",
]
