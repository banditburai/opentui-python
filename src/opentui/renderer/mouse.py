"""Mixin that adds mouse dispatch, hit testing, hover, and selection to CliRenderer."""

from __future__ import annotations

import logging
from typing import Any

from ._mouse_hit_testing import (
    dispatch_mouse_to_tree,
    do_auto_focus,
    find_deepest_hit,
    find_focusable_ancestor,
    hit_test,
    recheck_hover_state,
    update_hover_state,
)
from ._mouse_selection import (
    clear_selection,
    finish_selection,
    get_selection,
    handle_selection_mouse,
    has_selection,
    request_selection_update,
    start_selection,
    update_selection,
)

_log = logging.getLogger(__name__)

_MOUSE_HANDLER_MAP = {
    "down": "_on_mouse_down",
    "up": "_on_mouse_up",
    "move": "_on_mouse_move",
    "drag": "_on_mouse_drag",
    "scroll": "_on_mouse_scroll",
}
class MouseHandlingMixin:
    """Mixin providing mouse dispatch, hit testing, hover, and selection."""

    # -- Tree queries ----------------------------------------------------------

    def _tree_has_mouse_handlers(self, renderable) -> bool:
        if renderable is None:
            return False

        try:
            for attr in (
                "_on_mouse_down",
                "_on_mouse_up",
                "_on_mouse_move",
                "_on_mouse_drag",
                "_on_mouse_scroll",
            ):
                if getattr(renderable, attr, None) is not None:
                    return True
        except AttributeError:
            pass

        try:
            return any(self._tree_has_mouse_handlers(child) for child in renderable.get_children())
        except AttributeError:
            return False

    def _tree_has_scroll_targets(self, renderable) -> bool:
        if renderable is None:
            return False
        if getattr(renderable, "_is_scroll_target", False):
            return True
        try:
            return any(self._tree_has_scroll_targets(child) for child in renderable.get_children())
        except AttributeError:
            return False

    # -- Mouse dispatch --------------------------------------------------------

    def _handle_selection_mouse(self, event, hit_renderable, is_ctrl: bool, button: int) -> bool:
        return handle_selection_mouse(self, event, hit_renderable, is_ctrl, button)

    def _handle_capture_mouse(self, event, captured) -> bool:
        """Route mouse events to the captured element.

        Returns True if the event was fully handled (caller should return early).
        """
        # Route drag/move events directly to captured element (skip tree walk).
        if captured is not None and event.type not in ("up", "down"):
            handler = getattr(captured, "_on_mouse_drag", None)
            if handler is not None:
                event.target = captured
                handler(event)
                _log.debug("mouse capture→drag handler fired on %s", type(captured).__name__)
            else:
                _log.debug(
                    "mouse capture active but no _on_mouse_drag on %s", type(captured).__name__
                )
            return True

        # On mouse-up: send drag-end + up to captured element, then release.
        if captured is not None and event.type == "up":
            drag_end_handler = getattr(captured, "_on_mouse_drag_end", None)
            if drag_end_handler is not None:
                event.target = captured
                drag_end_handler(event)
            up_handler = getattr(captured, "_on_mouse_up", None)
            if up_handler is not None:
                event.target = captured
                up_handler(event)
            self._captured_renderable = None
            _log.debug("mouse capture released on up")
            return True

        return False

    def _dispatch_mouse_event(self, event) -> None:
        if self._root is None:
            return

        if self._split_height > 0:
            if event.y < self._render_offset:
                return
            event.y -= self._render_offset

        self._latest_pointer["x"] = event.x
        self._latest_pointer["y"] = event.y
        self._has_pointer = True
        self._last_pointer_modifiers = {
            "shift": getattr(event, "shift", False),
            "alt": getattr(event, "alt", False),
            "ctrl": getattr(event, "ctrl", False),
        }

        if self._use_console and self._console.visible:
            cb = self._console.bounds
            if (
                cb.x <= event.x < cb.x + cb.width
                and cb.y <= event.y < cb.y + cb.height
                and self._console.handle_mouse(event)
            ):
                return

        if event.type == "scroll":
            self._dispatch_scroll_event(event)
            return

        captured = self._captured_renderable

        if event.type in ("down", "drag", "up"):
            _log.debug(
                "mouse dispatch type=%s x=%s y=%s button=%s captured=%s",
                event.type,
                event.x,
                event.y,
                getattr(event, "button", None),
                type(captured).__name__ if captured is not None else None,
            )

        hit_renderable = self._find_deepest_hit(self._root, event.x, event.y)
        is_ctrl = getattr(event, "ctrl", False)
        button = getattr(event, "button", 0)

        # Selection-related branches (start, drag-update, up-finish, ctrl-extend).
        if self._handle_selection_mouse(event, hit_renderable, is_ctrl, button):
            return

        # Captured element routing (drag/move forwarding, up release).
        if self._handle_capture_mouse(event, captured):
            return

        # Track drag state so that auto-focus is suppressed during drag operations.
        if event.type == "down":
            self._is_dragging = False
        elif event.type == "drag":
            self._is_dragging = True
        elif event.type == "up":
            self._is_dragging = False

        self._dispatch_mouse_to_tree(self._root, event)

        target = getattr(event, "target", None)
        _log.debug(
            "mouse tree dispatch result type=%s target=%s has_drag=%s",
            event.type,
            type(target).__name__ if target is not None else None,
            getattr(target, "_on_mouse_drag", None) is not None if target else False,
        )

        # Hover tracking: fire _on_mouse_out / _on_mouse_over when the
        # element under the pointer changes.
        if event.type in ("move", "drag"):
            update_hover_state(self, event.x, event.y)

        # Auto-focus on left-button mousedown
        if (
            event.type == "down"
            and getattr(event, "button", 0) == 0  # left button only
            and not event.default_prevented
            and self._auto_focus
        ):
            hit = target
            if hit is None:
                hit = self._find_deepest_hit(self._root, event.x, event.y)
            focusable = self._find_focusable_ancestor(hit)
            if focusable is not None:
                self._do_auto_focus(focusable)

        # After dispatching a drag event, capture the target element so
        # subsequent drags bypass the tree walk.
        if event.type == "drag" and target is not None:
            self._captured_renderable = target
            _log.debug("mouse captured %s on drag", type(target).__name__)
        elif event.type == "down" and target is not None:
            handler = getattr(target, "_on_mouse_drag", None)
            if handler is not None:
                self._captured_renderable = target
                _log.debug("mouse captured %s on down (has drag handler)", type(target).__name__)

        # If down event and not prevented, clear any existing selection.
        if (
            event.type == "down"
            and not event.default_prevented
            and self._current_selection is not None
        ):
            self.clear_selection()

    def _dispatch_scroll_event(self, event) -> None:
        if self._root is None:
            return

        self._dispatch_mouse_to_tree(self._root, event)

        if event.propagation_stopped:
            return

        # Fall back to the focused renderable when nothing handled it.
        if self._focused_renderable is not None:
            focused = self._focused_renderable
            if not getattr(focused, "_destroyed", False):
                scroll_handler = getattr(focused, "_on_mouse_scroll", None)
                handle_scroll = getattr(focused, "handle_scroll_event", None)
                if scroll_handler is not None:
                    event.target = focused
                    scroll_handler(event)
                elif handle_scroll is not None:
                    event.target = focused
                    handle_scroll(event)

    # -- Selection API ---------------------------------------------------------

    @property
    def has_selection(self) -> bool:
        return has_selection(self)

    def get_selection(self):
        return get_selection(self)

    def start_selection(self, renderable, x: int, y: int) -> None:
        start_selection(self, renderable, x, y)

    def update_selection(
        self, current_renderable, x: int, y: int, *, finish_dragging: bool = False
    ) -> None:
        update_selection(
            self,
            current_renderable,
            x,
            y,
            finish_dragging=finish_dragging,
        )

    def clear_selection(self) -> None:
        clear_selection(self)

    def _finish_selection(self) -> None:
        finish_selection(self)

    def _is_within_container(self, renderable, container) -> bool:
        from ._mouse_selection import is_within_container

        return is_within_container(renderable, container)

    def _notify_selectables_of_selection_change(self) -> None:
        from ._mouse_selection import notify_selectables_of_selection_change

        notify_selectables_of_selection_change(self)

    def _walk_selectable_renderables(
        self,
        container,
        selection_bounds: dict,
        selected_renderables: list,
        touched_renderables: list,
        scroll_adjust_x: int = 0,
        scroll_adjust_y: int = 0,
    ) -> None:
        from ._mouse_selection import walk_selectable_renderables

        walk_selectable_renderables(
            self,
            container,
            selection_bounds,
            selected_renderables,
            touched_renderables,
            scroll_adjust_x,
            scroll_adjust_y,
        )

    def request_selection_update(self) -> None:
        request_selection_update(self)

    # -- Hit testing & hover ---------------------------------------------------

    @staticmethod
    def _iter_children_front_to_back(children) -> list:
        from ._mouse_hit_testing import iter_children_front_to_back

        return iter_children_front_to_back(children)

    def _recheck_hover_state(self) -> None:
        recheck_hover_state(self)

    def _find_deepest_hit(
        self,
        renderable,
        x: int,
        y: int,
        scroll_adjust_x: int = 0,
        scroll_adjust_y: int = 0,
    ) -> Any:
        return find_deepest_hit(self, renderable, x, y, scroll_adjust_x, scroll_adjust_y)

    def hit_test(self, x: int, y: int) -> int:
        return hit_test(self, x, y)

    def _find_focusable_ancestor(self, renderable) -> Any:
        return find_focusable_ancestor(renderable)

    def _do_auto_focus(self, renderable) -> None:
        do_auto_focus(self, renderable)

    def _dispatch_mouse_to_tree(
        self, renderable, event, scroll_adjust_x: int = 0, scroll_adjust_y: int = 0
    ) -> None:
        dispatch_mouse_to_tree(
            self,
            renderable,
            event,
            _MOUSE_HANDLER_MAP,
            scroll_adjust_x,
            scroll_adjust_y,
        )
