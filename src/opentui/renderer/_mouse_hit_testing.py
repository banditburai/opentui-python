"""Mouse hit-testing, hover, and tree-dispatch helpers."""

import contextlib
from typing import Any

from ..events import MouseEvent


def accumulate_scroll_offsets(renderable, sx: int, sy: int) -> tuple[int, int]:
    if getattr(renderable, "_scroll_y", False):
        fn = getattr(renderable, "_scroll_offset_y_fn", None)
        sy += int(fn()) if fn else int(getattr(renderable, "_scroll_offset_y", 0))
    if getattr(renderable, "_scroll_x", False):
        sx += int(getattr(renderable, "_scroll_offset_x", 0))
    return sx, sy


def iter_children_front_to_back(children) -> list:
    indexed = list(enumerate(children))
    indexed.sort(
        key=lambda pair: (getattr(pair[1], "_z_index", 0), pair[0]),
        reverse=True,
    )
    return [child for _, child in indexed]


def update_hover_state(renderer: Any, x: int, y: int) -> None:
    hit = find_deepest_hit(renderer, renderer._root, x, y)
    last_over = renderer._last_over_renderable

    if hit is last_over:
        return

    if last_over is not None and not getattr(last_over, "_destroyed", False):
        out_handler = getattr(last_over, "_on_mouse_out", None)
        if out_handler is not None:
            out_ev = MouseEvent(
                type="out",
                x=x,
                y=y,
                button=0,
                shift=renderer._last_pointer_modifiers.get("shift", False),
                alt=renderer._last_pointer_modifiers.get("alt", False),
                ctrl=renderer._last_pointer_modifiers.get("ctrl", False),
            )
            out_ev.target = last_over
            out_handler(out_ev)

    renderer._last_over_renderable = hit

    if hit is not None:
        over_handler = getattr(hit, "_on_mouse_over", None)
        if over_handler is not None:
            over_ev = MouseEvent(
                type="over",
                x=x,
                y=y,
                button=0,
                shift=renderer._last_pointer_modifiers.get("shift", False),
                alt=renderer._last_pointer_modifiers.get("alt", False),
                ctrl=renderer._last_pointer_modifiers.get("ctrl", False),
            )
            over_ev.target = hit
            over_handler(over_ev)


def recheck_hover_state(renderer: Any) -> None:
    if renderer.is_destroyed or not renderer._has_pointer:
        return
    if renderer._captured_renderable is not None:
        return

    update_hover_state(
        renderer,
        renderer._latest_pointer["x"],
        renderer._latest_pointer["y"],
    )


def find_deepest_hit(
    renderer: Any,
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

    child_sx, child_sy = accumulate_scroll_offsets(renderable, scroll_adjust_x, scroll_adjust_y)

    try:
        children = list(renderable.get_children())
    except AttributeError:
        children = []

    for child in iter_children_front_to_back(children):
        hit = find_deepest_hit(renderer, child, x, y, child_sx, child_sy)
        if hit is not None:
            return hit

    if inside:
        return renderable
    return None


def hit_test(renderer: Any, x: int, y: int) -> int:
    hit = find_deepest_hit(renderer, renderer._root, x, y)
    if hit is None or hit is renderer._root:
        return 0
    return hit._num


def find_focusable_ancestor(renderable) -> Any:
    node = renderable
    while node is not None:
        if getattr(node, "_focusable", False):
            return node
        node = getattr(node, "_parent", None)
    return None


def do_auto_focus(renderer: Any, renderable) -> None:
    if renderer._focused_renderable is renderable:
        return
    if renderer._focused_renderable is not None:
        with contextlib.suppress(Exception):
            renderer._focused_renderable.blur()
    renderer._focused_renderable = renderable
    with contextlib.suppress(Exception):
        renderable.focus()


def dispatch_mouse_to_tree(
    renderer: Any,
    renderable,
    event,
    handler_map: dict[str, str],
    scroll_adjust_x: int = 0,
    scroll_adjust_y: int = 0,
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

    child_scroll_x, child_scroll_y = accumulate_scroll_offsets(
        renderable, scroll_adjust_x, scroll_adjust_y
    )

    for child in iter_children_front_to_back(children):
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
        dispatch_mouse_to_tree(
            renderer,
            child,
            event,
            handler_map,
            child_scroll_x,
            child_scroll_y,
        )
        if event.propagation_stopped:
            return
        break

    if not inside:
        return

    attr = handler_map.get(event.type)
    if not attr:
        return

    handler = getattr(renderable, attr, None)
    if handler is not None:
        event.target = renderable
        handler(event)


__all__ = [
    "accumulate_scroll_offsets",
    "dispatch_mouse_to_tree",
    "do_auto_focus",
    "find_deepest_hit",
    "find_focusable_ancestor",
    "hit_test",
    "iter_children_front_to_back",
    "recheck_hover_state",
    "update_hover_state",
]
