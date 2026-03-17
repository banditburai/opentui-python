"""Selection model.

Provides text selection with anchor/focus points, selected/touched renderable
tracking, and conversion between global and local selection coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .components.base import BaseRenderable


class SelectionAnchor:
    """Stores selection anchor relative to a renderable.

    The anchor tracks a position relative to the renderable's origin so that
    when the renderable moves (e.g. due to scroll), the anchor follows.
    """

    def __init__(self, renderable: BaseRenderable, absolute_x: int, absolute_y: int) -> None:
        self._renderable = renderable
        self._relative_x = absolute_x - renderable.x
        self._relative_y = absolute_y - renderable.y

    @property
    def x(self) -> int:
        return self._renderable.x + self._relative_x

    @property
    def y(self) -> int:
        return self._renderable.y + self._relative_y


class Selection:
    """Text selection model with anchor/focus points.

    The anchor is the point where the selection started, and the focus is
    where the selection currently extends to. The selection bounds are
    computed from the min/max of anchor and focus.
    """

    def __init__(
        self,
        anchor_renderable: Any,
        anchor: dict[str, int],
        focus: dict[str, int],
    ) -> None:
        self._anchor = SelectionAnchor(anchor_renderable, anchor["x"], anchor["y"])
        self._focus = {"x": focus["x"], "y": focus["y"]}
        self._selected_renderables: list[Any] = []
        self._touched_renderables: list[Any] = []
        self._is_active: bool = True
        self._is_dragging: bool = True
        self._is_start: bool = False

    @property
    def is_start(self) -> bool:
        return self._is_start

    @is_start.setter
    def is_start(self, value: bool) -> None:
        self._is_start = value

    @property
    def anchor(self) -> dict[str, int]:
        return {"x": self._anchor.x, "y": self._anchor.y}

    @property
    def focus(self) -> dict[str, int]:
        return dict(self._focus)

    @focus.setter
    def focus(self, value: dict[str, int]) -> None:
        self._focus = {"x": value["x"], "y": value["y"]}

    @property
    def is_active(self) -> bool:
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self._is_active = value

    @property
    def is_dragging(self) -> bool:
        return self._is_dragging

    @is_dragging.setter
    def is_dragging(self, value: bool) -> None:
        self._is_dragging = value

    @property
    def bounds(self) -> dict[str, int]:
        """Return the bounding rectangle of the selection.

        Selection bounds are inclusive of both anchor and focus.
        A selection from (0,0) to (0,0) covers 1 cell.
        """
        min_x = min(self._anchor.x, self._focus["x"])
        max_x = max(self._anchor.x, self._focus["x"])
        min_y = min(self._anchor.y, self._focus["y"])
        max_y = max(self._anchor.y, self._focus["y"])

        width = max_x - min_x + 1
        height = max_y - min_y + 1

        return {"x": min_x, "y": min_y, "width": width, "height": height}

    def update_selected_renderables(self, selected_renderables: list[Any]) -> None:
        self._selected_renderables = selected_renderables

    @property
    def selected_renderables(self) -> list[Any]:
        return self._selected_renderables

    def update_touched_renderables(self, touched_renderables: list[Any]) -> None:
        self._touched_renderables = touched_renderables

    @property
    def touched_renderables(self) -> list[Any]:
        return self._touched_renderables

    def get_selected_text(self) -> str:
        """Get the selected text from all selected renderables.

        Renderables are sorted in reading order (top-to-bottom, then
        left-to-right). Destroyed renderables are skipped.
        """
        sorted_renderables = sorted(
            self._selected_renderables,
            key=lambda r: (r.y, r.x),
        )
        texts = []
        for renderable in sorted_renderables:
            if getattr(renderable, "_destroyed", False) or getattr(
                renderable, "is_destroyed", False
            ):
                continue
            text = renderable.get_selected_text()
            if text:
                texts.append(text)
        return "\n".join(texts)


@dataclass
class LocalSelectionBounds:
    """Local selection bounds relative to a renderable."""

    anchor_x: int
    anchor_y: int
    focus_x: int
    focus_y: int
    is_active: bool


def convert_global_to_local_selection(
    global_selection: Selection | None,
    local_x: int,
    local_y: int,
) -> LocalSelectionBounds | None:
    """Convert global Selection to local coordinates.

    Returns None if the selection is not active.
    """
    if global_selection is None or not global_selection.is_active:
        return None

    anchor = global_selection.anchor
    focus = global_selection.focus

    return LocalSelectionBounds(
        anchor_x=anchor["x"] - local_x,
        anchor_y=anchor["y"] - local_y,
        focus_x=focus["x"] - local_x,
        focus_y=focus["y"] - local_y,
        is_active=True,
    )


__all__ = [
    "Selection",
    "SelectionAnchor",
    "LocalSelectionBounds",
    "convert_global_to_local_selection",
]
