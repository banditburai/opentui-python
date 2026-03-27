"""Mouse selection bookkeeping and overlay rendering helpers."""

import contextlib
import time
from typing import Any

from ..events import MouseEvent
from ._mouse_hit_testing import accumulate_scroll_offsets, find_deepest_hit
from .buffer import Buffer

_DOUBLE_CLICK_THRESHOLD = 0.4  # seconds


def handle_selection_mouse(
    renderer: Any,
    event,
    hit_renderable,
    is_ctrl: bool,
    button: int,
) -> bool:
    # --- Extend selection via right-click (button 2) ---
    # Right-click is the primary extend mechanism because terminals pass it
    # through in mouse tracking mode — unlike shift+click / alt+click which
    # most terminals intercept for their own text selection.
    if event.type == "down" and button == 2 and not is_ctrl:
        if renderer._current_selection is not None:
            update_selection(renderer, hit_renderable, event.x, event.y)
            renderer._current_selection.is_dragging = True
            return True
        # No active selection — create one from last left-click pos to here
        last_pos = getattr(renderer, "_last_click_pos", None)
        last_rend = getattr(renderer, "_last_click_renderable", None)
        if last_pos is not None and last_rend is not None:
            start_selection(renderer, last_rend, last_pos[0], last_pos[1])
            update_selection(renderer, hit_renderable, event.x, event.y)
            renderer._current_selection.is_dragging = True
            return True

    if (
        event.type == "down"
        and button == 0
        and not (
            renderer._current_selection is not None and renderer._current_selection.is_dragging
        )
        and not is_ctrl
    ):
        # Extend selection: shift+click OR alt/option+click.
        # These work as secondary mechanisms for terminals that pass modifier
        # bits through — but most terminals intercept them, so right-click
        # (above) is the primary extend mechanism.
        is_shift = getattr(event, "shift", False)
        is_alt = getattr(event, "alt", False)
        is_extend = is_shift or is_alt
        if is_extend:
            if renderer._current_selection is not None:
                # Extend: keep anchor, move focus to shift-click point
                update_selection(renderer, hit_renderable, event.x, event.y)
                renderer._current_selection.is_dragging = True
                return True
            # No selection yet — create one from last click pos to here
            last_pos = getattr(renderer, "_last_click_pos", None)
            last_rend = getattr(renderer, "_last_click_renderable", None)
            if last_pos is not None and last_rend is not None:
                start_selection(renderer, last_rend, last_pos[0], last_pos[1])
                if renderer._current_selection is None:
                    return False
                update_selection(renderer, hit_renderable, event.x, event.y)
                renderer._current_selection.is_dragging = True
                return True

        # Double-click detection
        now = time.monotonic()
        last_time = getattr(renderer, "_last_click_time", 0.0)
        last_pos = getattr(renderer, "_last_click_pos", (0, 0))
        is_double = (
            now - last_time < _DOUBLE_CLICK_THRESHOLD
            and abs(event.x - last_pos[0]) <= 1
            and abs(event.y - last_pos[1]) <= 1
        )
        renderer._last_click_time = now
        renderer._last_click_pos = (event.x, event.y)
        renderer._last_click_renderable = hit_renderable

        if (
            is_double
            and hit_renderable is not None
            and _try_word_select(renderer, hit_renderable, event.x, event.y)
        ):
            return True

        if hit_renderable is not None and not getattr(hit_renderable, "_destroyed", False):
            is_selectable = getattr(hit_renderable, "selectable", False)
            has_drag_handler = getattr(hit_renderable, "_on_mouse_drag", None) is not None
            should_start = getattr(hit_renderable, "should_start_selection", None)
            should_start_result = (
                should_start(event.x, event.y) if should_start is not None else None
            )
            if should_start is not None and not should_start_result:
                pass
            elif is_selectable or not has_drag_handler:
                renderer._pending_selection_start = {
                    "x": event.x,
                    "y": event.y,
                    "renderable": hit_renderable,
                }
        return False

    if (
        event.type == "drag"
        and renderer._pending_selection_start is not None
        and (renderer._current_selection is None or not renderer._current_selection.is_dragging)
    ):
        pending = renderer._pending_selection_start
        renderer._pending_selection_start = None
        start_selection(renderer, pending["renderable"], pending["x"], pending["y"])

    if (
        event.type == "drag"
        and renderer._current_selection is not None
        and renderer._current_selection.is_dragging
    ):
        update_selection(renderer, hit_renderable, event.x, event.y)

        if hit_renderable is not None:
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
        return True

    if event.type == "up" and renderer._pending_selection_start is not None:
        renderer._pending_selection_start = None

    if (
        event.type == "up"
        and renderer._current_selection is not None
        and renderer._current_selection.is_dragging
    ):
        if hit_renderable is not None:
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
        finish_selection(renderer)
        return True

    if event.type == "down" and button == 0 and renderer._current_selection is not None and is_ctrl:
        renderer._current_selection.is_dragging = True
        update_selection(renderer, hit_renderable, event.x, event.y)
        return True

    return False


def _total_scroll_offset(renderable: Any) -> tuple[int, int]:
    """Walk up the parent chain to accumulate scroll offsets."""
    sx, sy = 0, 0
    parent = getattr(renderable, "_parent", None)
    while parent is not None:
        sx, sy = accumulate_scroll_offsets(parent, sx, sy)
        parent = getattr(parent, "_parent", None)
    return sx, sy


def _try_word_select(renderer: Any, renderable: Any, x: int, y: int) -> bool:
    """Attempt word-selection on a TextRenderable at the given screen position.

    Returns True if a word was selected, False otherwise.
    """
    from ..components.textarea.textarea_text_utils import char_class, offset_to_line_col

    coord_fn = getattr(renderable, "coord_to_offset", None)
    if coord_fn is None:
        return False
    text = getattr(renderable, "plain_text", None)
    if not text:
        return False

    # Account for scroll offsets: screen coords → layout coords
    scroll_x, scroll_y = _total_scroll_offset(renderable)
    local_x = x + scroll_x - getattr(renderable, "_x", 0)
    local_y = y + scroll_y - getattr(renderable, "_y", 0)
    offset = coord_fn(local_x, local_y)

    if offset < 0 or offset >= len(text):
        return False
    if char_class(text[offset]) == 0:  # whitespace
        return False

    # Find word boundaries using char_class
    cls = char_class(text[offset])
    word_start = offset
    while word_start > 0 and char_class(text[word_start - 1]) == cls:
        word_start -= 1
    word_end = offset
    while word_end < len(text) - 1 and char_class(text[word_end + 1]) == cls:
        word_end += 1
    # word_end is inclusive — the last character of the word

    # Convert offsets back to screen coordinates (layout → screen)
    start_line, start_col = offset_to_line_col(text, word_start)
    end_line, end_col = offset_to_line_col(text, word_end + 1)

    rx = getattr(renderable, "_x", 0)
    ry = getattr(renderable, "_y", 0)
    start_sx = rx + start_col - scroll_x
    start_sy = ry + start_line - scroll_y
    end_sx = rx + end_col - scroll_x
    end_sy = ry + end_line - scroll_y

    start_selection(renderer, renderable, start_sx, start_sy)
    update_selection(renderer, renderable, end_sx, end_sy, finish_dragging=True)
    return True


def has_selection(renderer: Any) -> bool:
    return renderer._current_selection is not None


def get_selection(renderer: Any):
    return renderer._current_selection


def start_selection(renderer: Any, renderable, x: int, y: int) -> None:
    if getattr(renderable, "_destroyed", False):
        return

    clear_selection(renderer)

    from ..selection import Selection

    parent = getattr(renderable, "_parent", None)
    container = parent if parent is not None else renderer._root
    renderer._selection_containers.append(container)
    renderer._current_selection = Selection(renderable, {"x": x, "y": y}, {"x": x, "y": y})
    renderer._current_selection.is_start = True

    notify_selectables_of_selection_change(renderer)


def update_selection(
    renderer: Any,
    current_renderable,
    x: int,
    y: int,
    *,
    finish_dragging: bool = False,
) -> None:
    if renderer._current_selection is None:
        return

    renderer._current_selection.is_start = False
    renderer._current_selection.focus = {"x": x, "y": y}

    if finish_dragging:
        renderer._current_selection.is_dragging = False

    if renderer._selection_containers:
        current_container = renderer._selection_containers[-1]

        if current_renderable is None or not is_within_container(
            current_renderable, current_container
        ):
            parent_container = getattr(current_container, "_parent", None)
            if parent_container is None:
                parent_container = renderer._root
            renderer._selection_containers.append(parent_container)
        elif current_renderable is not None and len(renderer._selection_containers) > 1:
            container_index = -1
            try:
                container_index = renderer._selection_containers.index(current_renderable)
            except ValueError:
                parent = getattr(current_renderable, "_parent", None)
                if parent is None:
                    parent = renderer._root
                with contextlib.suppress(ValueError):
                    container_index = renderer._selection_containers.index(parent)

            if container_index != -1 and container_index < len(renderer._selection_containers) - 1:
                renderer._selection_containers = renderer._selection_containers[
                    : container_index + 1
                ]

    notify_selectables_of_selection_change(renderer)


def clear_selection(renderer: Any) -> None:
    if renderer._current_selection is not None:
        for renderable in renderer._current_selection.touched_renderables:
            if getattr(renderable, "selectable", False) and not getattr(
                renderable, "_destroyed", False
            ):
                renderable.on_selection_changed(None)
        renderer._current_selection = None
    renderer._selection_containers = []


def finish_selection(renderer: Any) -> None:
    if renderer._current_selection is not None:
        renderer._current_selection.is_dragging = False
        notify_selectables_of_selection_change(renderer)


def is_within_container(renderable, container) -> bool:
    current = renderable
    while current is not None:
        if current is container:
            return True
        current = getattr(current, "_parent", None)
    return False


def notify_selectables_of_selection_change(renderer: Any) -> None:
    selected_renderables: list = []
    touched_renderables: list = []
    current_container = (
        renderer._selection_containers[-1] if renderer._selection_containers else renderer._root
    )

    if renderer._current_selection is not None and current_container is not None:
        init_sx, init_sy = 0, 0
        ancestor = getattr(current_container, "_parent", None)
        while ancestor is not None:
            init_sx, init_sy = accumulate_scroll_offsets(ancestor, init_sx, init_sy)
            ancestor = getattr(ancestor, "_parent", None)

        bounds = renderer._current_selection.bounds

        walk_selectable_renderables(
            renderer,
            current_container,
            bounds,
            selected_renderables,
            touched_renderables,
            init_sx,
            init_sy,
        )

        for renderable in renderer._current_selection.touched_renderables:
            if renderable not in touched_renderables and not getattr(
                renderable, "_destroyed", False
            ):
                renderable.on_selection_changed(None)

        renderer._current_selection.update_selected_renderables(selected_renderables)
        renderer._current_selection.update_touched_renderables(touched_renderables)


def walk_selectable_renderables(
    renderer: Any,
    container,
    selection_bounds: dict,
    selected_renderables: list,
    touched_renderables: list,
    scroll_adjust_x: int = 0,
    scroll_adjust_y: int = 0,
) -> None:
    try:
        children = list(container.get_children())
    except AttributeError:
        return

    child_sx, child_sy = accumulate_scroll_offsets(container, scroll_adjust_x, scroll_adjust_y)

    for child in children:
        cx = getattr(child, "_x", 0) - child_sx
        cy = getattr(child, "_y", 0) - child_sy
        cw = int(getattr(child, "_layout_width", 0) or 0)
        ch = int(getattr(child, "_layout_height", 0) or 0)

        sx = selection_bounds["x"]
        sy = selection_bounds["y"]
        sw = selection_bounds["width"]
        sh = selection_bounds["height"]

        overlaps = not (cx + cw <= sx or cx >= sx + sw or cy + ch <= sy or cy >= sy + sh)
        is_selectable = getattr(child, "selectable", False)

        if not overlaps:
            gcc = getattr(child, "get_children_count", None)
            if gcc is not None and gcc() > 0:
                walk_selectable_renderables(
                    renderer,
                    child,
                    selection_bounds,
                    selected_renderables,
                    touched_renderables,
                    child_sx,
                    child_sy,
                )
            continue

        if is_selectable:
            has_sel = child.on_selection_changed(renderer._current_selection)
            if has_sel:
                selected_renderables.append(child)
            touched_renderables.append(child)

        gcc = getattr(child, "get_children_count", None)
        if gcc is not None and gcc() > 0:
            walk_selectable_renderables(
                renderer,
                child,
                selection_bounds,
                selected_renderables,
                touched_renderables,
                child_sx,
                child_sy,
            )


def request_selection_update(renderer: Any) -> None:
    if renderer._current_selection is not None and renderer._current_selection.is_dragging:
        px = renderer._latest_pointer["x"]
        py = renderer._latest_pointer["y"]
        hit = find_deepest_hit(renderer, renderer._root, px, py)
        update_selection(renderer, hit, px, py)


def apply_selection_overlay(renderer: Any, buffer: Buffer, selection_bg: Any) -> None:
    sel = renderer._current_selection
    if sel is None:
        return
    if not sel.is_active:
        return

    anchor = sel.anchor
    focus = sel.focus
    if (anchor["y"], anchor["x"]) <= (focus["y"], focus["x"]):
        start_x, start_y = anchor["x"], anchor["y"]
        end_x, end_y = focus["x"], focus["y"]
    else:
        start_x, start_y = focus["x"], focus["y"]
        end_x, end_y = anchor["x"], anchor["y"]

    w = buffer.width
    h = buffer.height
    skip_rects: list[tuple[int, int, int, int]] = []
    for renderable in sel.touched_renderables:
        if not getattr(renderable, "_destroyed", False):
            rsx, rsy = _total_scroll_offset(renderable)
            skip_rects.append(
                (
                    getattr(renderable, "_x", 0) - rsx,
                    getattr(renderable, "_y", 0) - rsy,
                    int(getattr(renderable, "_layout_width", 0) or 0),
                    int(getattr(renderable, "_layout_height", 0) or 0),
                )
            )

    total_cells = 0
    for row in range(max(0, start_y), min(end_y + 1, h)):
        if row == start_y and row == end_y:
            col_start = max(0, start_x)
            col_end = min(end_x + 1, w)
        elif row == start_y:
            col_start = max(0, start_x)
            col_end = w
        elif row == end_y:
            col_start = 0
            col_end = min(end_x + 1, w)
        else:
            col_start = 0
            col_end = w

        segments = [(col_start, col_end)]
        for sx, sy, sw, sh in skip_rects:
            if row < sy or row >= sy + sh:
                continue
            new_segments = []
            for seg_start, seg_end in segments:
                if seg_start >= sx + sw or seg_end <= sx:
                    new_segments.append((seg_start, seg_end))
                else:
                    if seg_start < sx:
                        new_segments.append((seg_start, sx))
                    if seg_end > sx + sw:
                        new_segments.append((sx + sw, seg_end))
            segments = new_segments

        for seg_start, seg_end in segments:
            rect_w = seg_end - seg_start
            if rect_w > 0:
                buffer.fill_rect(seg_start, row, rect_w, 1, selection_bg)
                total_cells += rect_w


__all__ = [
    "apply_selection_overlay",
    "clear_selection",
    "finish_selection",
    "get_selection",
    "handle_selection_mouse",
    "has_selection",
    "notify_selectables_of_selection_change",
    "request_selection_update",
    "start_selection",
    "update_selection",
]
