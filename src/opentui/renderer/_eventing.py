"""Event listener registry and callback management for the renderer."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any


def register_event_listener(renderer: Any, event: str, handler: Callable) -> Callable[[], None]:
    listeners = renderer._event_listeners.setdefault(event, [])
    listeners.append(handler)

    def _unsub() -> None:
        with contextlib.suppress(ValueError):
            listeners.remove(handler)

    return _unsub


def emit_renderer_event(renderer: Any, event: str, *args: Any) -> None:
    for handler in list(renderer._event_listeners.get(event, [])):
        with contextlib.suppress(Exception):
            handler(*args)


def invalidate_handler_cache(renderer: Any) -> None:
    renderer._handlers_dirty = True
    renderer._mouse_tracking_dirty = True


def collect_event_forwarding(renderer: Any) -> dict[str, list[Callable]]:
    if not renderer._handlers_dirty:
        return renderer._cached_handlers

    handlers: dict[str, list[Callable]] = {"key": [], "mouse": [], "paste": []}
    if renderer._root:
        _collect_handlers(renderer._root, handlers)

    renderer._cached_handlers = handlers
    renderer._handlers_dirty = False
    return handlers


def add_post_process_fn(renderer: Any, fn: Callable) -> None:
    renderer._post_process_fns.append(fn)


def remove_post_process_fn(renderer: Any, fn: Callable) -> None:
    with contextlib.suppress(ValueError):
        renderer._post_process_fns.remove(fn)


def set_frame_callback(renderer: Any, callback: Callable) -> None:
    renderer._frame_callbacks.append(callback)


def remove_frame_callback(renderer: Any, callback: Callable) -> None:
    with contextlib.suppress(ValueError):
        renderer._frame_callbacks.remove(callback)


def request_animation_frame(renderer: Any, callback: Callable) -> int:
    handle = renderer._next_animation_id
    renderer._next_animation_id += 1
    renderer._animation_frame_callbacks[handle] = callback
    return handle


def cancel_animation_frame(renderer: Any, handle: int) -> None:
    renderer._animation_frame_callbacks.pop(handle, None)


def _collect_handlers(renderable: Any, handlers: dict[str, list[Callable]]) -> None:
    with contextlib.suppress(AttributeError):
        handlers["key"].append(renderable._key_handler)

    try:
        handler = renderable._on_key_down
        if handler is not None:
            handlers["key"].append(handler)
    except AttributeError:
        pass

    try:
        handler = renderable._on_paste
        if handler is not None:
            handlers["paste"].append(handler)
    except AttributeError:
        pass

    try:
        for child in renderable.get_children():
            _collect_handlers(child, handlers)
    except AttributeError:
        pass
