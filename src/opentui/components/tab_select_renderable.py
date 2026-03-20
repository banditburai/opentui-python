"""TabSelectRenderable - horizontal tab-style selection renderable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..events import KeyEvent
from ..keymapping import (
    DEFAULT_KEY_ALIASES,
    KeyAliasMap,
    KeyBinding,
    build_key_bindings_map,
    lookup_action,
    merge_key_aliases,
    merge_key_bindings,
)
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


@dataclass
class TabSelectOption:
    name: str
    description: str = ""
    value: Any = None


class TabSelectRenderableEvents:
    SELECTION_CHANGED = "selectionChanged"
    ITEM_SELECTED = "itemSelected"


_DEFAULT_TAB_SELECT_BINDINGS: list[KeyBinding] = [
    KeyBinding(name="left", action="move-left"),
    KeyBinding(name="[", action="move-left"),
    KeyBinding(name="right", action="move-right"),
    KeyBinding(name="]", action="move-right"),
    KeyBinding(name="return", action="select-current"),
    KeyBinding(name="linefeed", action="select-current"),
]


class TabSelectRenderable(Renderable):
    """Horizontal tab-style selection renderable.

    Usage:
        tab_select = TabSelectRenderable(
            options=[
                TabSelectOption("Tab 1", description="First tab"),
                TabSelectOption("Tab 2", description="Second tab"),
            ],
        )
        tab_select.focus()
        tab_select.handle_key(KeyEvent(key="right"))
        assert tab_select.get_selected_index() == 1
    """

    __slots__ = (
        "_options",
        "_selected_index",
        "_scroll_offset",
        "_tab_width",
        "_max_visible_tabs",
        "_show_scroll_arrows",
        "_show_description",
        "_show_underline",
        "_wrap_selection",
        "_key_bindings",
        "_key_alias_map",
        "_key_map",
        "_is_destroyed",
    )

    def __init__(
        self,
        *,
        options: list[TabSelectOption] | None = None,
        tab_width: int = 20,
        show_scroll_arrows: bool = True,
        show_description: bool = True,
        show_underline: bool = True,
        wrap_selection: bool = False,
        # Key bindings
        key_bindings: list[KeyBinding] | None = None,
        key_alias_map: KeyAliasMap | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._options: list[TabSelectOption] = list(options) if options else []
        self._selected_index: int = 0
        self._scroll_offset: int = 0
        self._tab_width = tab_width

        self._show_scroll_arrows = show_scroll_arrows
        self._show_description = show_description
        self._show_underline = show_underline
        self._wrap_selection = wrap_selection

        w = self._width if isinstance(self._width, int) else 80
        self._max_visible_tabs = max(1, w // self._tab_width)

        self._focusable = True

        self._key_alias_map = merge_key_aliases(DEFAULT_KEY_ALIASES, key_alias_map or {})
        self._key_bindings: list[KeyBinding] = list(key_bindings) if key_bindings else []
        merged = merge_key_bindings(_DEFAULT_TAB_SELECT_BINDINGS, self._key_bindings)
        self._key_map = build_key_bindings_map(merged, self._key_alias_map)

        self._is_destroyed = False

    @property
    def options(self) -> list[TabSelectOption]:
        return list(self._options)

    @options.setter
    def options(self, opts: list[TabSelectOption]) -> None:
        self._options = list(opts) if opts else []
        if self._options:
            self._selected_index = min(self._selected_index, len(self._options) - 1)
        else:
            self._selected_index = 0
        self._update_scroll_offset()
        self.mark_dirty()

    @property
    def wrap_selection(self) -> bool:
        return self._wrap_selection

    @wrap_selection.setter
    def wrap_selection(self, v: bool) -> None:
        self._wrap_selection = v

    @property
    def key_bindings(self) -> list[KeyBinding]:
        return list(self._key_bindings)

    @key_bindings.setter
    def key_bindings(self, bindings: list[KeyBinding]) -> None:
        self._key_bindings = list(bindings)
        merged = merge_key_bindings(_DEFAULT_TAB_SELECT_BINDINGS, self._key_bindings)
        self._key_map = build_key_bindings_map(merged, self._key_alias_map)

    @property
    def key_alias_map(self) -> KeyAliasMap:
        return dict(self._key_alias_map)

    @key_alias_map.setter
    def key_alias_map(self, aliases: KeyAliasMap) -> None:
        self._key_alias_map = merge_key_aliases(DEFAULT_KEY_ALIASES, aliases)
        merged = merge_key_bindings(_DEFAULT_TAB_SELECT_BINDINGS, self._key_bindings)
        self._key_map = build_key_bindings_map(merged, self._key_alias_map)

    def get_selected_index(self) -> int:
        return self._selected_index

    def get_selected_option(self) -> TabSelectOption | None:
        if not self._options or self._selected_index >= len(self._options):
            return None
        return self._options[self._selected_index]

    def set_selected_index(self, index: int) -> None:
        """Set selection programmatically. Ignores invalid indices."""
        if not self._options:
            return
        if index < 0 or index >= len(self._options):
            return
        self._selected_index = index
        self._update_scroll_offset()
        self.emit(TabSelectRenderableEvents.SELECTION_CHANGED, index, self._options[index])
        self.mark_paint_dirty()

    def move_left(self) -> None:
        """Move selection left by one. Respects wrap_selection."""
        if not self._options:
            return
        if self._selected_index > 0:
            self._selected_index -= 1
        elif self._wrap_selection:
            self._selected_index = len(self._options) - 1
        else:
            return

        self._update_scroll_offset()
        self.mark_paint_dirty()
        self.emit(
            TabSelectRenderableEvents.SELECTION_CHANGED,
            self._selected_index,
            self.get_selected_option(),
        )

    def move_right(self) -> None:
        """Move selection right by one. Respects wrap_selection."""
        if not self._options:
            return
        if self._selected_index < len(self._options) - 1:
            self._selected_index += 1
        elif self._wrap_selection:
            self._selected_index = 0
        else:
            return

        self._update_scroll_offset()
        self.mark_paint_dirty()
        self.emit(
            TabSelectRenderableEvents.SELECTION_CHANGED,
            self._selected_index,
            self.get_selected_option(),
        )

    def select_current(self) -> None:
        """Select the current item. Emits ITEM_SELECTED if an option exists."""
        if not self._options or self._selected_index >= len(self._options):
            return
        option = self._options[self._selected_index]
        self.emit(TabSelectRenderableEvents.ITEM_SELECTED, self._selected_index, option)

    def _update_scroll_offset(self) -> None:
        half_visible = self._max_visible_tabs // 2
        new_offset = max(
            0,
            min(
                self._selected_index - half_visible,
                len(self._options) - self._max_visible_tabs,
            ),
        )
        if new_offset != self._scroll_offset:
            self._scroll_offset = new_offset
            self.mark_paint_dirty()

    def handle_key(self, event: KeyEvent) -> bool:
        if event.default_prevented:
            return False

        action = self._lookup_action(event)
        if action:
            return self._dispatch_action(action)

        return False

    def _lookup_action(self, event: KeyEvent) -> str | None:
        return lookup_action(
            event.key,
            event.ctrl,
            event.shift,
            event.alt,
            event.meta,
            self._key_map,
            self._key_alias_map,
        )

    def _dispatch_action(self, action: str) -> bool:
        if action == "move-left":
            self.move_left()
            return True
        if action == "move-right":
            self.move_right()
            return True
        if action == "select-current":
            self.select_current()
            return True
        return False

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

    def destroy(self) -> None:
        self._is_destroyed = True
        super().destroy()


__all__ = [
    "TabSelectOption",
    "TabSelectRenderable",
    "TabSelectRenderableEvents",
]
