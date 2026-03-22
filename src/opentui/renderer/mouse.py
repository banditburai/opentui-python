"""Mixin that adds mouse dispatch, hit testing, hover, and selection to CliRenderer."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

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

        # 1. left-button down: start selection if target is selectable
        if (
            event.type == "down"
            and button == 0  # left button only
            and not (self._current_selection is not None and self._current_selection.is_dragging)
            and not is_ctrl
        ):
            can_start = bool(
                hit_renderable is not None
                and getattr(hit_renderable, "selectable", False)
                and not getattr(hit_renderable, "_destroyed", False)
                and hit_renderable.should_start_selection(event.x, event.y)
            )
            if can_start:
                self.start_selection(hit_renderable, event.x, event.y)
                self._dispatch_mouse_to_tree(self._root, event)
                return

        # 2. drag while selection isDragging: update selection focus
        if (
            event.type == "drag"
            and self._current_selection is not None
            and self._current_selection.is_dragging
        ):
            self.update_selection(hit_renderable, event.x, event.y)

            if hit_renderable is not None:
                from ..events import MouseEvent

                drag_ev = MouseEvent(
                    type="drag",
                    x=event.x,
                    y=event.y,
                    button=button,
                    is_dragging=True,
                    shift=getattr(event, "shift", False),
                    ctrl=is_ctrl,
                    alt=getattr(event, "alt", False),
                )
                drag_ev.target = hit_renderable
                handler = getattr(hit_renderable, "_on_mouse_drag", None)
                if handler is not None:
                    handler(drag_ev)
            return

        # 3. up while selection isDragging: dispatch up with isDragging, then finish
        if (
            event.type == "up"
            and self._current_selection is not None
            and self._current_selection.is_dragging
        ):
            if hit_renderable is not None:
                from ..events import MouseEvent

                up_ev = MouseEvent(
                    type="up",
                    x=event.x,
                    y=event.y,
                    button=button,
                    is_dragging=True,
                    shift=getattr(event, "shift", False),
                    ctrl=is_ctrl,
                    alt=getattr(event, "alt", False),
                )
                up_ev.target = hit_renderable
                handler = getattr(hit_renderable, "_on_mouse_up", None)
                if handler is not None:
                    handler(up_ev)
            self._finish_selection()
            return

        # 4. ctrl+click with existing selection: extend selection
        if event.type == "down" and button == 0 and self._current_selection is not None and is_ctrl:
            self._current_selection.is_dragging = True
            self.update_selection(hit_renderable, event.x, event.y)
            return

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
            return

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
            hit = self._find_deepest_hit(self._root, event.x, event.y)
            last_over = self._last_over_renderable
            if hit is not last_over:
                if last_over is not None and not getattr(last_over, "_destroyed", False):
                    out_handler = getattr(last_over, "_on_mouse_out", None)
                    if out_handler is not None:
                        from ..events import MouseEvent

                        out_ev = MouseEvent(type="out", x=event.x, y=event.y)
                        out_ev.target = last_over
                        out_handler(out_ev)
                self._last_over_renderable = hit
                if hit is not None:
                    over_handler = getattr(hit, "_on_mouse_over", None)
                    if over_handler is not None:
                        from ..events import MouseEvent

                        over_ev = MouseEvent(type="over", x=event.x, y=event.y)
                        over_ev.target = hit
                        over_handler(over_ev)

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
        return self._current_selection is not None

    def get_selection(self):
        return self._current_selection

    def start_selection(self, renderable, x: int, y: int) -> None:
        if not getattr(renderable, "selectable", False):
            return

        self.clear_selection()

        from ..selection import Selection

        parent = getattr(renderable, "_parent", None)
        self._selection_containers.append(parent if parent is not None else self._root)
        self._current_selection = Selection(renderable, {"x": x, "y": y}, {"x": x, "y": y})
        self._current_selection.is_start = True

        self._notify_selectables_of_selection_change()

    def update_selection(
        self, current_renderable, x: int, y: int, *, finish_dragging: bool = False
    ) -> None:
        if self._current_selection is None:
            return

        self._current_selection.is_start = False
        self._current_selection.focus = {"x": x, "y": y}

        if finish_dragging:
            self._current_selection.is_dragging = False

        if self._selection_containers:
            current_container = self._selection_containers[-1]

            if current_renderable is None or not self._is_within_container(
                current_renderable, current_container
            ):
                parent_container = getattr(current_container, "_parent", None)
                if parent_container is None:
                    parent_container = self._root
                self._selection_containers.append(parent_container)
            elif current_renderable is not None and len(self._selection_containers) > 1:
                container_index = -1
                try:
                    container_index = self._selection_containers.index(current_renderable)
                except ValueError:
                    parent = getattr(current_renderable, "_parent", None)
                    if parent is None:
                        parent = self._root
                    with contextlib.suppress(ValueError):
                        container_index = self._selection_containers.index(parent)

                if container_index != -1 and container_index < len(self._selection_containers) - 1:
                    self._selection_containers = self._selection_containers[: container_index + 1]

        self._notify_selectables_of_selection_change()

    def clear_selection(self) -> None:
        if self._current_selection is not None:
            for renderable in self._current_selection.touched_renderables:
                if getattr(renderable, "selectable", False) and not getattr(
                    renderable, "_destroyed", False
                ):
                    renderable.on_selection_changed(None)
            self._current_selection = None
        self._selection_containers = []

    def _finish_selection(self) -> None:
        if self._current_selection is not None:
            self._current_selection.is_dragging = False
            self._notify_selectables_of_selection_change()

    def _is_within_container(self, renderable, container) -> bool:
        current = renderable
        while current is not None:
            if current is container:
                return True
            current = getattr(current, "_parent", None)
        return False

    def _notify_selectables_of_selection_change(self) -> None:
        selected_renderables: list = []
        touched_renderables: list = []
        current_container = (
            self._selection_containers[-1] if self._selection_containers else self._root
        )

        if self._current_selection is not None and current_container is not None:
            self._walk_selectable_renderables(
                current_container,
                self._current_selection.bounds,
                selected_renderables,
                touched_renderables,
            )

            for renderable in self._current_selection.touched_renderables:
                if renderable not in touched_renderables and not getattr(
                    renderable, "_destroyed", False
                ):
                    renderable.on_selection_changed(None)

            self._current_selection.update_selected_renderables(selected_renderables)
            self._current_selection.update_touched_renderables(touched_renderables)

    def _walk_selectable_renderables(
        self,
        container,
        selection_bounds: dict,
        selected_renderables: list,
        touched_renderables: list,
    ) -> None:
        try:
            children = list(container.get_children())
        except AttributeError:
            return

        for child in children:
            cx = getattr(child, "_x", 0)
            cy = getattr(child, "_y", 0)
            cw = int(getattr(child, "_layout_width", 0) or 0)
            ch = int(getattr(child, "_layout_height", 0) or 0)

            sx = selection_bounds["x"]
            sy = selection_bounds["y"]
            sw = selection_bounds["width"]
            sh = selection_bounds["height"]

            if cx + cw <= sx or cx >= sx + sw or cy + ch <= sy or cy >= sy + sh:
                gcc = getattr(child, "get_children_count", None)
                if gcc is not None and gcc() > 0:
                    self._walk_selectable_renderables(
                        child, selection_bounds, selected_renderables, touched_renderables
                    )
                continue

            if getattr(child, "selectable", False):
                has_sel = child.on_selection_changed(self._current_selection)
                if has_sel:
                    selected_renderables.append(child)
                touched_renderables.append(child)

            gcc = getattr(child, "get_children_count", None)
            if gcc is not None and gcc() > 0:
                self._walk_selectable_renderables(
                    child, selection_bounds, selected_renderables, touched_renderables
                )

    def request_selection_update(self) -> None:
        if self._current_selection is not None and self._current_selection.is_dragging:
            px = self._latest_pointer["x"]
            py = self._latest_pointer["y"]
            hit = self._find_deepest_hit(self._root, px, py)
            self.update_selection(hit, px, py)

    # -- Hit testing & hover ---------------------------------------------------

    @staticmethod
    def _iter_children_front_to_back(children) -> list:
        indexed = list(enumerate(children))
        indexed.sort(
            key=lambda pair: (getattr(pair[1], "_z_index", 0), pair[0]),
            reverse=True,
        )
        return [child for _, child in indexed]

    def _recheck_hover_state(self) -> None:
        if self.is_destroyed or not self._has_pointer:
            return
        if self._captured_renderable is not None:
            return

        px = self._latest_pointer["x"]
        py = self._latest_pointer["y"]
        hit = self._find_deepest_hit(self._root, px, py)
        last_over = self._last_over_renderable

        if hit is last_over:
            return

        from ..events import MouseEvent

        if last_over is not None and not getattr(last_over, "_destroyed", False):
            out_handler = getattr(last_over, "_on_mouse_out", None)
            if out_handler is not None:
                out_ev = MouseEvent(
                    type="out",
                    x=px,
                    y=py,
                    button=0,
                    shift=self._last_pointer_modifiers.get("shift", False),
                    alt=self._last_pointer_modifiers.get("alt", False),
                    ctrl=self._last_pointer_modifiers.get("ctrl", False),
                )
                out_ev.target = last_over
                out_handler(out_ev)

        self._last_over_renderable = hit

        if hit is not None:
            over_handler = getattr(hit, "_on_mouse_over", None)
            if over_handler is not None:
                over_ev = MouseEvent(
                    type="over",
                    x=px,
                    y=py,
                    button=0,
                    shift=self._last_pointer_modifiers.get("shift", False),
                    alt=self._last_pointer_modifiers.get("alt", False),
                    ctrl=self._last_pointer_modifiers.get("ctrl", False),
                )
                over_ev.target = hit
                over_handler(over_ev)

    def _find_deepest_hit(
        self,
        renderable,
        x: int,
        y: int,
        scroll_adjust_x: int = 0,
        scroll_adjust_y: int = 0,
    ) -> Any:
        if renderable is None:
            return None

        check_x = x + scroll_adjust_x
        check_y = y + scroll_adjust_y

        contains_point = getattr(renderable, "contains_point", None)
        inside = True if contains_point is None else contains_point(check_x, check_y)
        host = getattr(renderable, "_host", None)

        if not inside and host is None:
            return None

        overflow = getattr(renderable, "_overflow", "visible")
        if overflow == "hidden":
            rx = getattr(renderable, "_x", 0)
            ry = getattr(renderable, "_y", 0)
            rw = int(getattr(renderable, "_layout_width", 0) or 0)
            rh = int(getattr(renderable, "_layout_height", 0) or 0)
            if not (rx <= x < rx + rw and ry <= y < ry + rh):
                return None

        child_sx = scroll_adjust_x
        child_sy = scroll_adjust_y
        if getattr(renderable, "_scroll_y", False):
            fn = getattr(renderable, "_scroll_offset_y_fn", None)
            child_sy += int(fn()) if fn else int(getattr(renderable, "_scroll_offset_y", 0))
        if getattr(renderable, "_scroll_x", False):
            child_sx += int(getattr(renderable, "_scroll_offset_x", 0))

        try:
            children = list(renderable.get_children())
        except AttributeError:
            children = []

        for child in self._iter_children_front_to_back(children):
            hit = self._find_deepest_hit(child, x, y, child_sx, child_sy)
            if hit is not None:
                return hit

        if inside:
            return renderable
        return None

    def hit_test(self, x: int, y: int) -> int:
        hit = self._find_deepest_hit(self._root, x, y)
        if hit is None or hit is self._root:
            return 0
        return hit._num

    def _find_focusable_ancestor(self, renderable) -> Any:
        node = renderable
        while node is not None:
            if getattr(node, "_focusable", False):
                return node
            node = getattr(node, "_parent", None)
        return None

    def _do_auto_focus(self, renderable) -> None:
        if self._focused_renderable is renderable:
            return
        if self._focused_renderable is not None:
            with contextlib.suppress(Exception):
                self._focused_renderable.blur()
        self._focused_renderable = renderable
        with contextlib.suppress(Exception):
            renderable.focus()

    def _find_scroll_target(
        self, renderable, x: int, y: int, scroll_adjust_x: int = 0, scroll_adjust_y: int = 0
    ):
        try:
            children = list(renderable.get_children())
        except AttributeError:
            children = []

        child_sx = scroll_adjust_x
        child_sy = scroll_adjust_y
        if getattr(renderable, "_scroll_y", False):
            fn = getattr(renderable, "_scroll_offset_y_fn", None)
            child_sy += int(fn()) if fn else int(getattr(renderable, "_scroll_offset_y", 0))
        if getattr(renderable, "_scroll_x", False):
            child_sx += int(getattr(renderable, "_scroll_offset_x", 0))

        for child in reversed(children):
            found = self._find_scroll_target(child, x, y, child_sx, child_sy)
            if found is not None:
                return found

        check_x = x + scroll_adjust_x
        check_y = y + scroll_adjust_y
        contains_point = getattr(renderable, "contains_point", None)
        inside = True if contains_point is None else contains_point(check_x, check_y)

        if inside and getattr(renderable, "_is_scroll_target", False):
            return renderable
        return None

    def _dispatch_mouse_to_tree(
        self, renderable, event, scroll_adjust_x: int = 0, scroll_adjust_y: int = 0
    ) -> None:
        if event.propagation_stopped:
            return

        check_x = event.x + scroll_adjust_x
        check_y = event.y + scroll_adjust_y

        contains_point = getattr(renderable, "contains_point", None)
        inside = True if contains_point is None else contains_point(check_x, check_y)

        try:
            children = list(renderable.get_children())
        except AttributeError:
            children = []

        child_scroll_x = scroll_adjust_x
        child_scroll_y = scroll_adjust_y
        if getattr(renderable, "_scroll_y", False):
            fn = getattr(renderable, "_scroll_offset_y_fn", None)
            child_scroll_y += int(fn()) if fn else int(getattr(renderable, "_scroll_offset_y", 0))
        if getattr(renderable, "_scroll_x", False):
            child_scroll_x += int(getattr(renderable, "_scroll_offset_x", 0))

        for child in self._iter_children_front_to_back(children):
            child_check_x = event.x + child_scroll_x
            child_check_y = event.y + child_scroll_y
            child_contains = getattr(child, "contains_point", None)
            child_host = getattr(child, "_host", None)
            if (
                child_contains is not None
                and not child_contains(child_check_x, child_check_y)
                and child_host is None
            ):
                continue
            self._dispatch_mouse_to_tree(child, event, child_scroll_x, child_scroll_y)
            if event.propagation_stopped:
                return
            break

        if not inside:
            return

        attr = _MOUSE_HANDLER_MAP.get(event.type)
        if not attr:
            return

        handler = getattr(renderable, attr, None)
        if handler is not None:
            event.target = renderable
            handler(event)
