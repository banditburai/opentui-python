"""Base renderable classes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .. import layout as yoga_layout
from .. import structs as s

if TYPE_CHECKING:
    from ..renderer import Buffer


# Unique ID counter for renderables
_renderable_id = 0


def _next_id() -> int:
    global _renderable_id
    _renderable_id += 1
    return _renderable_id


@dataclass
class LayoutOptions:
    """Layout options for renderables."""

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
    """Style options for renderables."""

    background_color: s.RGBA | None = None
    fg: s.RGBA | None = None
    border: bool = False
    border_style: str = "single"
    border_color: s.RGBA | None = None
    title: str | None = None
    title_alignment: str = "left"


class BaseRenderable:
    """Base class for all renderables."""

    __slots__ = (
        "_id",
        "_parent",
        "_children",
        "_event_handlers",
        "_yoga_node",
        "_x",
        "_y",
        "_width",
        "_height",
        "_layout_x",
        "_layout_y",
        "_layout_width",
        "_layout_height",
        "_dirty",
    )

    def __init__(self):
        self._id = _next_id()
        self._parent: BaseRenderable | None = None
        self._children: list[BaseRenderable] = []
        self._event_handlers: dict[str, list[Callable]] = {}
        self._yoga_node: Any = None
        self._x: int = 0
        self._y: int = 0
        self._width: int | None = None
        self._height: int | None = None
        self._layout_x: float = 0
        self._layout_y: float = 0
        self._layout_width: float = 0
        self._layout_height: float = 0
        self._dirty: bool = True

    @property
    def x(self) -> int:
        return self._x

    @property
    def y(self) -> int:
        return self._y

    @property
    def width(self) -> int | None:
        return self._width

    @property
    def height(self) -> int | None:
        return self._height

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        """Mark this renderable as needing re-render."""
        self._dirty = True

    def mark_clean(self) -> None:
        """Mark this renderable as clean."""
        self._dirty = False

    def request_render(self) -> None:
        """Propagate dirty flag up the tree."""
        self._dirty = True
        if self._parent is not None:
            self._parent.request_render()

    def _ensure_yoga_node(self) -> Any:
        """Ensure this renderable has a yoga node."""
        if self._yoga_node is None:
            self._yoga_node = yoga_layout.create_node()
        return self._yoga_node

    def _build_yoga_tree(self) -> Any:
        """Build yoga tree from this renderable and children."""
        node = self._ensure_yoga_node()
        self._configure_yoga_node(node)

        for child in self._children:
            if hasattr(child, "_build_yoga_tree"):
                child_node = child._build_yoga_tree()
                if child_node is not None:
                    node.insert_child(child_node, node.child_count)

        return node

    def _configure_yoga_node(self, node: Any) -> None:
        """Configure yoga node with this renderable's layout properties."""
        pass

    def _apply_yoga_layout(self) -> None:
        """Apply computed yoga layout to this renderable."""
        if self._yoga_node is None:
            return

        layout = yoga_layout.get_layout(self._yoga_node)
        self._x = int(layout["x"])
        self._y = int(layout["y"])
        self._width = int(layout["width"])
        self._height = int(layout["height"])

    def _sync_yoga_layout_to_children(self) -> None:
        """Sync yoga layout to children."""
        for child in self._children:
            if hasattr(child, "_apply_yoga_layout"):
                child._apply_yoga_layout()

        for child in self._children:
            if hasattr(child, "_sync_yoga_layout_to_children"):
                child._sync_yoga_layout_to_children()

    @property
    def id(self) -> int:
        return self._id

    def add(self, child: BaseRenderable, index: int | None = None) -> int:
        """Add a child renderable."""
        if child._parent:
            child._parent.remove(child)
        child._parent = self
        if index is not None:
            self._children.insert(index, child)
        else:
            self._children.append(child)
        self.mark_dirty()
        return child._id

    def remove(self, child: BaseRenderable) -> None:
        """Remove a child renderable."""
        if child in self._children:
            self._children.remove(child)
            child._parent = None
            self.mark_dirty()

    def insert_before(self, child: BaseRenderable, anchor: BaseRenderable) -> int:
        """Insert a child before an anchor."""
        if child._parent:
            child._parent.remove(child)
        child._parent = self
        idx = self._children.index(anchor)
        self._children.insert(idx, child)
        self.mark_dirty()
        return child._id

    def get_children(self) -> tuple[BaseRenderable, ...]:
        """Get all children as an immutable tuple."""
        return tuple(self._children)

    def get_children_count(self) -> int:
        """Get the number of children."""
        return len(self._children)

    def get_renderable(self, id: str) -> BaseRenderable | None:
        """Get a renderable by ID."""
        if str(self._id) == id:
            return self
        for child in self._children:
            found = child.get_renderable(id)
            if found:
                return found
        return None

    def find_descendant_by_id(self, id: str) -> BaseRenderable | None:
        """Find a descendant by ID."""
        return self.get_renderable(id)

    def on(self, event: str, handler: Callable) -> None:
        """Register an event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable | None = None) -> None:
        """Remove an event handler."""
        if event not in self._event_handlers:
            return
        if handler is None:
            self._event_handlers[event] = []
        else:
            self._event_handlers[event] = [h for h in self._event_handlers[event] if h != handler]

    def emit(self, event: str, *args, **kwargs) -> None:
        """Emit an event to handlers."""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            handler(*args, **kwargs)

    def destroy(self) -> None:
        """Destroy this renderable."""
        if self._parent is not None:
            self._parent.remove(self)
        for child in self._children[:]:
            child.destroy()
        self._children.clear()
        self._event_handlers.clear()
        self._yoga_node = None
        self._parent = None

    def destroy_recursively(self) -> None:
        """Destroy this renderable and all descendants."""
        self.destroy()


class Renderable(BaseRenderable):
    """Base renderable with layout and styling."""

    __slots__ = (
        # Layout
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
        "_overflow",
        "_position",
        # Spacing
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
        # Style
        "_background_color",
        "_fg",
        "_border",
        "_border_style",
        "_border_color",
        "_title",
        "_title_alignment",
        # Border sides
        "_border_top",
        "_border_right",
        "_border_bottom",
        "_border_left",
        "_border_chars",
        # Focus
        "_focusable",
        "_focused",
        # Visibility
        "_visible",
        "_opacity",
        # Z-order
        "_z_index",
        # Position edges
        "_pos_top",
        "_pos_right",
        "_pos_bottom",
        "_pos_left",
        # Transform
        "_translate_x",
        "_translate_y",
        # Lifecycle hooks
        "_render_before",
        "_render_after",
        "_on_size_change",
        "_on_lifecycle_pass",
        # Mouse event handlers
        "_on_mouse_down",
        "_on_mouse_up",
        "_on_mouse_move",
        "_on_mouse_drag",
        "_on_mouse_drag_end",
        "_on_mouse_drop",
        "_on_mouse_over",
        "_on_mouse_out",
        "_on_mouse_scroll",
        # Keyboard
        "_on_key_down",
        "_on_paste",
        # Live tracking
        "_live",
    )

    def __init__(
        self,
        *,
        # Layout
        width: int | str | None = None,
        height: int | str | None = None,
        min_width: int | str | None = None,
        min_height: int | str | None = None,
        max_width: int | str | None = None,
        max_height: int | str | None = None,
        flex_grow: float = 0,
        flex_shrink: float = 1,
        flex_direction: str = "column",
        flex_wrap: str = "nowrap",
        flex_basis: float | str | None = None,
        justify_content: str = "flex-start",
        align_items: str = "stretch",
        align_self: str | None = None,
        gap: int = 0,
        overflow: str = "visible",
        position: str = "relative",
        # Spacing
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
        # Style
        background_color: s.RGBA | str | None = None,
        fg: s.RGBA | str | None = None,
        border: bool = False,
        border_style: str = "single",
        border_color: s.RGBA | str | None = None,
        title: str | None = None,
        title_alignment: str = "left",
        # Border sides
        border_top: bool = True,
        border_right: bool = True,
        border_bottom: bool = True,
        border_left: bool = True,
        border_chars: dict | None = None,
        # Focus
        focused: bool = False,
        # Visibility
        visible: bool = True,
        opacity: float = 1.0,
        # Z-order
        z_index: int = 0,
        # Position edges
        top: float | str | None = None,
        right: float | str | None = None,
        bottom: float | str | None = None,
        left: float | str | None = None,
        # Transform
        translate_x: float = 0,
        translate_y: float = 0,
    ):
        super().__init__()

        # Layout
        self._x = 0
        self._y = 0
        self._width = width
        self._height = height
        self._min_width = min_width
        self._min_height = min_height
        self._max_width = max_width
        self._max_height = max_height
        self._flex_grow = flex_grow
        self._flex_shrink = flex_shrink
        self._flex_direction = flex_direction
        self._flex_wrap = flex_wrap
        self._flex_basis = flex_basis
        self._justify_content = justify_content
        self._align_items = align_items
        self._align_self = align_self
        self._gap = gap
        self._overflow = overflow
        self._position = position

        # Spacing — resolve shorthand x/y
        self._padding = padding
        self._padding_top = padding_top if padding_top is not None else (padding_y if padding_y is not None else padding)
        self._padding_right = padding_right if padding_right is not None else (padding_x if padding_x is not None else padding)
        self._padding_bottom = padding_bottom if padding_bottom is not None else (padding_y if padding_y is not None else padding)
        self._padding_left = padding_left if padding_left is not None else (padding_x if padding_x is not None else padding)

        self._margin = margin
        self._margin_top = margin_top if margin_top is not None else (margin_y if margin_y is not None else margin)
        self._margin_right = margin_right if margin_right is not None else (margin_x if margin_x is not None else margin)
        self._margin_bottom = margin_bottom if margin_bottom is not None else (margin_y if margin_y is not None else margin)
        self._margin_left = margin_left if margin_left is not None else (margin_x if margin_x is not None else margin)

        # Style
        self._background_color = self._parse_color(background_color)
        self._fg = self._parse_color(fg)
        self._border = border
        self._border_style = border_style
        self._border_color = self._parse_color(border_color)
        self._title = title
        self._title_alignment = title_alignment

        # Border sides
        self._border_top = border_top
        self._border_right = border_right
        self._border_bottom = border_bottom
        self._border_left = border_left
        self._border_chars = border_chars

        # Focus
        self._focusable = False
        self._focused = focused

        # Visibility
        self._visible = visible
        self._opacity = opacity

        # Z-order
        self._z_index = z_index

        # Position edges
        self._pos_top = top
        self._pos_right = right
        self._pos_bottom = bottom
        self._pos_left = left

        # Transform
        self._translate_x = translate_x
        self._translate_y = translate_y

        # Lifecycle hooks
        self._render_before: Callable | None = None
        self._render_after: Callable | None = None
        self._on_size_change: Callable | None = None
        self._on_lifecycle_pass: Callable | None = None

        # Per-renderable mouse event handlers
        self._on_mouse_down: Callable | None = None
        self._on_mouse_up: Callable | None = None
        self._on_mouse_move: Callable | None = None
        self._on_mouse_drag: Callable | None = None
        self._on_mouse_drag_end: Callable | None = None
        self._on_mouse_drop: Callable | None = None
        self._on_mouse_over: Callable | None = None
        self._on_mouse_out: Callable | None = None
        self._on_mouse_scroll: Callable | None = None

        # Keyboard/paste
        self._on_key_down: Callable | None = None
        self._on_paste: Callable | None = None

        # Live tracking
        self._live = False

    @staticmethod
    def _parse_color(color: s.RGBA | str | None) -> s.RGBA | None:
        """Parse a color string or RGBA to RGBA."""
        if color is None:
            return None
        if isinstance(color, s.RGBA):
            return color
        if isinstance(color, str):
            return s.RGBA.from_hex(color)
        return None

    # Position properties
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
        self.mark_dirty()

    @property
    def height(self) -> int | str | None:
        return self._height

    @height.setter
    def height(self, value: int | str | None) -> None:
        self._height = value
        self.mark_dirty()

    # Layout properties
    @property
    def flex_grow(self) -> float:
        return self._flex_grow

    @flex_grow.setter
    def flex_grow(self, value: float) -> None:
        self._flex_grow = value
        self.mark_dirty()

    @property
    def flex_shrink(self) -> float:
        return self._flex_shrink

    @flex_shrink.setter
    def flex_shrink(self, value: float) -> None:
        self._flex_shrink = value
        self.mark_dirty()

    @property
    def flex_direction(self) -> str:
        return self._flex_direction

    @flex_direction.setter
    def flex_direction(self, value: str) -> None:
        self._flex_direction = value
        self.mark_dirty()

    @property
    def flex_wrap(self) -> str:
        return self._flex_wrap

    @flex_wrap.setter
    def flex_wrap(self, value: str) -> None:
        self._flex_wrap = value
        self.mark_dirty()

    @property
    def flex_basis(self) -> float | str | None:
        return self._flex_basis

    @flex_basis.setter
    def flex_basis(self, value: float | str | None) -> None:
        self._flex_basis = value
        self.mark_dirty()

    @property
    def justify_content(self) -> str:
        return self._justify_content

    @justify_content.setter
    def justify_content(self, value: str) -> None:
        self._justify_content = value
        self.mark_dirty()

    @property
    def align_items(self) -> str:
        return self._align_items

    @align_items.setter
    def align_items(self, value: str) -> None:
        self._align_items = value
        self.mark_dirty()

    @property
    def align_self(self) -> str | None:
        return self._align_self

    @align_self.setter
    def align_self(self, value: str | None) -> None:
        self._align_self = value
        self.mark_dirty()

    @property
    def gap(self) -> int:
        return self._gap

    @gap.setter
    def gap(self, value: int) -> None:
        self._gap = value
        self.mark_dirty()

    @property
    def overflow(self) -> str:
        return self._overflow

    @overflow.setter
    def overflow(self, value: str) -> None:
        self._overflow = value
        self.mark_dirty()

    @property
    def position(self) -> str:
        return self._position

    @position.setter
    def position(self, value: str) -> None:
        self._position = value
        self.mark_dirty()

    # Style properties
    @property
    def background_color(self) -> s.RGBA | None:
        return self._background_color

    @background_color.setter
    def background_color(self, value: s.RGBA | str | None) -> None:
        self._background_color = self._parse_color(value)
        self.mark_dirty()

    @property
    def fg(self) -> s.RGBA | None:
        return self._fg

    @fg.setter
    def fg(self, value: s.RGBA | str | None) -> None:
        self._fg = self._parse_color(value)
        self.mark_dirty()

    @property
    def border(self) -> bool:
        return self._border

    @property
    def border_style(self) -> str:
        return self._border_style

    @property
    def border_color(self) -> s.RGBA | None:
        return self._border_color

    @property
    def title(self) -> str | None:
        return self._title

    @title.setter
    def title(self, value: str | None) -> None:
        self._title = value
        self.mark_dirty()

    # Focus properties
    @property
    def focusable(self) -> bool:
        return self._focusable

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = value

    def focus(self) -> None:
        """Focus this renderable."""
        self._focused = True

    def blur(self) -> None:
        """Unfocus this renderable."""
        self._focused = False

    # Visibility properties
    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value
        self.mark_dirty()

    @property
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        self._opacity = value
        self.mark_dirty()

    @property
    def z_index(self) -> int:
        return self._z_index

    @z_index.setter
    def z_index(self, value: int) -> None:
        self._z_index = value
        self.mark_dirty()

    # Position edges
    @property
    def pos_top(self) -> float | str | None:
        return self._pos_top

    @pos_top.setter
    def pos_top(self, value: float | str | None) -> None:
        self._pos_top = value
        self.mark_dirty()

    @property
    def pos_right(self) -> float | str | None:
        return self._pos_right

    @pos_right.setter
    def pos_right(self, value: float | str | None) -> None:
        self._pos_right = value
        self.mark_dirty()

    @property
    def pos_bottom(self) -> float | str | None:
        return self._pos_bottom

    @pos_bottom.setter
    def pos_bottom(self, value: float | str | None) -> None:
        self._pos_bottom = value
        self.mark_dirty()

    @property
    def pos_left(self) -> float | str | None:
        return self._pos_left

    @pos_left.setter
    def pos_left(self, value: float | str | None) -> None:
        self._pos_left = value
        self.mark_dirty()

    # Transform
    @property
    def translate_x(self) -> float:
        return self._translate_x

    @translate_x.setter
    def translate_x(self, value: float) -> None:
        self._translate_x = value
        self.mark_dirty()

    @property
    def translate_y(self) -> float:
        return self._translate_y

    @translate_y.setter
    def translate_y(self, value: float) -> None:
        self._translate_y = value
        self.mark_dirty()

    # Live property
    @property
    def live(self) -> bool:
        return self._live

    @live.setter
    def live(self, value: bool) -> None:
        self._live = value

    # Lifecycle hooks
    @property
    def render_before(self) -> Callable | None:
        return self._render_before

    @render_before.setter
    def render_before(self, value: Callable | None) -> None:
        self._render_before = value

    @property
    def render_after(self) -> Callable | None:
        return self._render_after

    @render_after.setter
    def render_after(self, value: Callable | None) -> None:
        self._render_after = value

    @property
    def on_size_change(self) -> Callable | None:
        return self._on_size_change

    @on_size_change.setter
    def on_size_change(self, value: Callable | None) -> None:
        self._on_size_change = value

    # Mouse event handler properties
    @property
    def on_mouse_down(self) -> Callable | None:
        return self._on_mouse_down

    @on_mouse_down.setter
    def on_mouse_down(self, value: Callable | None) -> None:
        self._on_mouse_down = value

    @property
    def on_mouse_up(self) -> Callable | None:
        return self._on_mouse_up

    @on_mouse_up.setter
    def on_mouse_up(self, value: Callable | None) -> None:
        self._on_mouse_up = value

    @property
    def on_mouse_move(self) -> Callable | None:
        return self._on_mouse_move

    @on_mouse_move.setter
    def on_mouse_move(self, value: Callable | None) -> None:
        self._on_mouse_move = value

    @property
    def on_mouse_drag(self) -> Callable | None:
        return self._on_mouse_drag

    @on_mouse_drag.setter
    def on_mouse_drag(self, value: Callable | None) -> None:
        self._on_mouse_drag = value

    @property
    def on_mouse_drag_end(self) -> Callable | None:
        return self._on_mouse_drag_end

    @on_mouse_drag_end.setter
    def on_mouse_drag_end(self, value: Callable | None) -> None:
        self._on_mouse_drag_end = value

    @property
    def on_mouse_drop(self) -> Callable | None:
        return self._on_mouse_drop

    @on_mouse_drop.setter
    def on_mouse_drop(self, value: Callable | None) -> None:
        self._on_mouse_drop = value

    @property
    def on_mouse_over(self) -> Callable | None:
        return self._on_mouse_over

    @on_mouse_over.setter
    def on_mouse_over(self, value: Callable | None) -> None:
        self._on_mouse_over = value

    @property
    def on_mouse_out(self) -> Callable | None:
        return self._on_mouse_out

    @on_mouse_out.setter
    def on_mouse_out(self, value: Callable | None) -> None:
        self._on_mouse_out = value

    @property
    def on_mouse_scroll(self) -> Callable | None:
        return self._on_mouse_scroll

    @on_mouse_scroll.setter
    def on_mouse_scroll(self, value: Callable | None) -> None:
        self._on_mouse_scroll = value

    @property
    def on_key_down(self) -> Callable | None:
        return self._on_key_down

    @on_key_down.setter
    def on_key_down(self, value: Callable | None) -> None:
        self._on_key_down = value

    @property
    def on_paste(self) -> Callable | None:
        return self._on_paste

    @on_paste.setter
    def on_paste(self, value: Callable | None) -> None:
        self._on_paste = value

    def _configure_yoga_node(self, node: Any) -> None:
        """Configure yoga node with this renderable's layout properties."""
        yoga_layout.configure_node(
            node,
            width=self._width,
            height=self._height,
            min_width=self._min_width,
            min_height=self._min_height,
            max_width=self._max_width,
            max_height=self._max_height,
            flex_grow=self._flex_grow if self._flex_grow else None,
            flex_shrink=self._flex_shrink if self._flex_shrink != 1 else None,
            flex_basis=self._flex_basis,
            flex_direction=self._flex_direction if self._flex_direction != "column" else None,
            flex_wrap=self._flex_wrap if self._flex_wrap != "nowrap" else None,
            justify_content=self._justify_content if self._justify_content != "flex-start" else None,
            align_items=self._align_items if self._align_items != "stretch" else None,
            align_self=self._align_self,
            gap=float(self._gap) if self._gap else None,
            overflow=self._overflow if self._overflow != "visible" else None,
            position_type=self._position if self._position != "relative" else None,
            padding=float(self._padding) if self._padding else None,
            padding_top=float(self._padding_top) if self._padding_top and not self._padding else None,
            padding_right=float(self._padding_right) if self._padding_right and not self._padding else None,
            padding_bottom=float(self._padding_bottom) if self._padding_bottom and not self._padding else None,
            padding_left=float(self._padding_left) if self._padding_left and not self._padding else None,
            margin=float(self._margin) if self._margin else None,
            margin_top=float(self._margin_top) if self._margin_top and not self._margin else None,
            margin_right=float(self._margin_right) if self._margin_right and not self._margin else None,
            margin_bottom=float(self._margin_bottom) if self._margin_bottom and not self._margin else None,
            margin_left=float(self._margin_left) if self._margin_left and not self._margin else None,
            top=self._pos_top,
            right=self._pos_right,
            bottom=self._pos_bottom,
            left=self._pos_left,
        )

    def _apply_yoga_layout(self) -> None:
        """Apply computed yoga layout to this renderable."""
        if self._yoga_node is None:
            return

        layout = yoga_layout.get_layout(self._yoga_node)
        old_w = self._width
        old_h = self._height
        self._x = int(layout["x"])
        self._y = int(layout["y"])
        self._width = int(layout["width"])
        self._height = int(layout["height"])

        if self._on_size_change and (old_w != self._width or old_h != self._height):
            self._on_size_change(self._width, self._height)

    def update_layout(self, delta_time: float = 0) -> None:
        """Update layout (would integrate with layout engine)."""
        pass

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render this renderable to the buffer."""
        if not self._visible:
            return

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        # Render children
        for child in self._children:
            if isinstance(child, Renderable):
                child.render(buffer, delta_time)

        if self._render_after:
            self._render_after(buffer, delta_time, self)

    def get_children_sorted_by_primary_axis(self) -> list[Renderable]:
        """Get children sorted for layout."""
        return [c for c in self._children if isinstance(c, Renderable)]


__all__ = [
    "BaseRenderable",
    "Renderable",
    "LayoutOptions",
    "StyleOptions",
]
