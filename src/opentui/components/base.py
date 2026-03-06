"""Base renderable classes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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

    width: int | None = None
    height: int | None = None
    min_width: int | None = None
    min_height: int | None = None
    max_width: int | None = None
    max_height: int | None = None
    flex_grow: float = 0
    flex_shrink: float = 1
    flex_direction: str = "column"
    justify_content: str = "flex-start"
    align_items: str = "stretch"
    gap: int = 0
    padding: int = 0
    padding_top: int | None = None
    padding_right: int | None = None
    padding_bottom: int | None = None
    padding_left: int | None = None
    margin: int = 0
    margin_top: int | None = None
    margin_right: int | None = None
    margin_bottom: int | None = None
    margin_left: int | None = None


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
        return child._id

    def remove(self, child: BaseRenderable) -> None:
        """Remove a child renderable."""
        if child in self._children:
            self._children.remove(child)
            child._parent = None

    def insert_before(self, child: BaseRenderable, anchor: BaseRenderable) -> int:
        """Insert a child before an anchor."""
        if child._parent:
            child._parent.remove(child)
        child._parent = self
        idx = self._children.index(anchor)
        self._children.insert(idx, child)
        return child._id

    def get_children(self) -> list[BaseRenderable]:
        """Get all children."""
        return self._children.copy()

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
        for child in self._children[:]:
            child.destroy()
        self._children.clear()
        self._parent = None

    def destroy_recursively(self) -> None:
        """Destroy this renderable and all descendants."""
        self.destroy()


class Renderable(BaseRenderable):
    """Base renderable with layout and styling."""

    def __init__(
        self,
        *,
        # Layout
        width: int | None = None,
        height: int | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        flex_grow: float = 0,
        flex_shrink: float = 1,
        flex_direction: str = "column",
        justify_content: str = "flex-start",
        align_items: str = "stretch",
        gap: int = 0,
        # Spacing
        padding: int = 0,
        padding_top: int | None = None,
        padding_right: int | None = None,
        padding_bottom: int | None = None,
        padding_left: int | None = None,
        margin: int = 0,
        margin_top: int | None = None,
        margin_right: int | None = None,
        margin_bottom: int | None = None,
        margin_left: int | None = None,
        # Style
        background_color: s.RGBA | str | None = None,
        fg: s.RGBA | str | None = None,
        border: bool = False,
        border_style: str = "single",
        border_color: s.RGBA | str | None = None,
        title: str | None = None,
        title_alignment: str = "left",
        # Focus
        focused: bool = False,
        # Visibility
        visible: bool = True,
        opacity: float = 1.0,
        # Z-order
        z_index: int = 0,
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
        self._justify_content = justify_content
        self._align_items = align_items
        self._gap = gap

        # Spacing
        self._padding = padding
        self._padding_top = padding_top if padding_top is not None else padding
        self._padding_right = padding_right if padding_right is not None else padding
        self._padding_bottom = padding_bottom if padding_bottom is not None else padding
        self._padding_left = padding_left if padding_left is not None else padding

        self._margin = margin
        self._margin_top = margin_top if margin_top is not None else margin
        self._margin_right = margin_right if margin_right is not None else margin
        self._margin_bottom = margin_bottom if margin_bottom is not None else margin
        self._margin_left = margin_left if margin_left is not None else margin

        # Style
        self._background_color = self._parse_color(background_color)
        self._fg = self._parse_color(fg)
        self._border = border
        self._border_style = border_style
        self._border_color = self._parse_color(border_color)
        self._title = title
        self._title_alignment = title_alignment

        # Focus
        self._focusable = False
        self._focused = focused

        # Visibility
        self._visible = visible
        self._opacity = opacity

        # Z-order
        self._z_index = z_index

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
    def width(self) -> int | None:
        return self._width

    @property
    def height(self) -> int | None:
        return self._height

    # Layout properties
    @property
    def flex_grow(self) -> float:
        return self._flex_grow

    @property
    def flex_shrink(self) -> float:
        return self._flex_shrink

    @property
    def flex_direction(self) -> str:
        return self._flex_direction

    @property
    def justify_content(self) -> str:
        return self._justify_content

    @property
    def align_items(self) -> str:
        return self._align_items

    @property
    def gap(self) -> int:
        return self._gap

    # Style properties
    @property
    def background_color(self) -> s.RGBA | None:
        return self._background_color

    @property
    def fg(self) -> s.RGBA | None:
        return self._fg

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

    @property
    def opacity(self) -> float:
        return self._opacity

    def request_render(self) -> None:
        """Request a re-render."""
        # Would typically notify the renderer
        pass

    def _configure_yoga_node(self, node: Any) -> None:
        """Configure yoga node with this renderable's layout properties."""
        import yoga

        if self._width is not None:
            node.width = float(self._width)
        if self._height is not None:
            node.height = float(self._height)

        if self._min_width is not None:
            node.min_width = float(self._min_width)
        if self._min_height is not None:
            node.min_height = float(self._min_height)
        if self._max_width is not None:
            node.max_width = float(self._max_width)
        if self._max_height is not None:
            node.max_height = float(self._max_height)

        if self._flex_grow:
            node.flex_grow = self._flex_grow
        if self._flex_shrink != 1:
            node.flex_shrink = self._flex_shrink

        if self._flex_direction != "column":
            node.flex_direction = yoga_layout.FLEX_DIRECTION_MAP.get(
                self._flex_direction, yoga.FlexDirection.Column
            )

        if self._justify_content != "flex-start":
            node.justify_content = yoga_layout.JUSTIFY_MAP.get(
                self._justify_content, yoga.Justify.FlexStart
            )

        if self._align_items != "stretch":
            node.align_items = yoga_layout.ALIGN_MAP.get(self._align_items, yoga.Align.Stretch)

        if self._gap:
            node.set_gap(yoga.Gutter.All, float(self._gap))

        if (
            self._padding
            or self._padding_top
            or self._padding_right
            or self._padding_bottom
            or self._padding_left
        ):
            if self._padding:
                node.set_padding(yoga.Edge.All, float(self._padding))
            else:
                if self._padding_top:
                    node.set_padding(yoga.Edge.Top, float(self._padding_top))
                if self._padding_right:
                    node.set_padding(yoga.Edge.Right, float(self._padding_right))
                if self._padding_bottom:
                    node.set_padding(yoga.Edge.Bottom, float(self._padding_bottom))
                if self._padding_left:
                    node.set_padding(yoga.Edge.Left, float(self._padding_left))

        if (
            self._margin
            or self._margin_top
            or self._margin_right
            or self._margin_bottom
            or self._margin_left
        ):
            if self._margin:
                node.set_margin(yoga.Edge.All, float(self._margin))
            else:
                if self._margin_top:
                    node.set_margin(yoga.Edge.Top, float(self._margin_top))
                if self._margin_right:
                    node.set_margin(yoga.Edge.Right, float(self._margin_right))
                if self._margin_bottom:
                    node.set_margin(yoga.Edge.Bottom, float(self._margin_bottom))
                if self._margin_left:
                    node.set_margin(yoga.Edge.Left, float(self._margin_left))

    def update_layout(self, delta_time: float = 0) -> None:
        """Update layout (would integrate with layout engine)."""
        pass

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render this renderable to the buffer."""
        if not self._visible:
            return

        # Render children
        for child in self._children:
            if isinstance(child, Renderable):
                child.render(buffer, delta_time)

    def get_children_sorted_by_primary_axis(self) -> list[Renderable]:
        """Get children sorted for layout."""
        return [c for c in self._children if isinstance(c, Renderable)]


__all__ = [
    "BaseRenderable",
    "Renderable",
    "LayoutOptions",
    "StyleOptions",
]
