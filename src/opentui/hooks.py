"""Hooks for OpenTUI — keyboard, focus, mouse, and lifecycle handlers."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .signals import Signal, on_cleanup
from .structs import RGBA

if TYPE_CHECKING:
    from .events import KeyEvent, MouseEvent, PasteEvent
    from .renderer import CliRenderer


_current_renderer: CliRenderer | None = None
_pending_mount_fns: list[Callable[[], None]] = []
_keyboard_handlers: list[Callable[[KeyEvent], None]] = []
_mouse_handlers: list[Callable[[MouseEvent], None]] = []
_paste_handlers: list[Callable[[PasteEvent], None]] = []
_resize_handlers: list[Callable[[int, int], None]] = []
_selection_handlers: list[Callable[[Any], None]] = []
_focus_handlers: list[Callable[[str], None]] = []
_terminal_dimensions = Signal((80, 24), name="terminal_dimensions")


def set_renderer(renderer: CliRenderer) -> None:
    global _current_renderer
    _current_renderer = renderer
    _set_terminal_dimensions(renderer.width, renderer.height)


def get_renderer() -> CliRenderer | None:
    return _current_renderer


def get_keyboard_handlers() -> list[Callable[[KeyEvent], None]]:
    return _keyboard_handlers.copy()


def clear_keyboard_handlers() -> None:
    _keyboard_handlers.clear()


def get_paste_handlers() -> list[Callable[[PasteEvent], None]]:
    return _paste_handlers.copy()


def clear_paste_handlers() -> None:
    _paste_handlers.clear()


def get_resize_handlers() -> list[Callable[[int, int], None]]:
    return _resize_handlers.copy()


def clear_resize_handlers() -> None:
    _resize_handlers.clear()


def _set_terminal_dimensions(width: int, height: int) -> None:
    _terminal_dimensions.set((width, height))


def get_selection_handlers() -> list[Callable[[Any], None]]:
    return _selection_handlers.copy()


def clear_selection_handlers() -> None:
    _selection_handlers.clear()


def get_focus_handlers() -> list[Callable[[str], None]]:
    return _focus_handlers.copy()


def clear_focus_handlers() -> None:
    _focus_handlers.clear()


def register_focus_handler(handler: Callable[[str], None]) -> None:
    _focus_handlers.append(handler)


def unregister_focus_handler(handler: Callable[[str], None]) -> None:
    with contextlib.suppress(ValueError):
        _focus_handlers.remove(handler)


def register_keyboard_handler(handler: Callable) -> None:
    _keyboard_handlers.append(handler)


def unregister_keyboard_handler(handler: Callable) -> None:
    with contextlib.suppress(ValueError):
        _keyboard_handlers.remove(handler)


def register_paste_handler(handler: Callable[[PasteEvent], None]) -> None:
    _paste_handlers.append(handler)


def unregister_paste_handler(handler: Callable[[PasteEvent], None]) -> None:
    with contextlib.suppress(ValueError):
        _paste_handlers.remove(handler)


def _use_identity_handler(
    handler: Callable,
    handler_list: list,
) -> Callable[[], None]:
    """Register *handler* with identity-dedup and on_cleanup auto-removal."""
    if not any(h is handler for h in handler_list):
        handler_list.append(handler)

    def _cleanup() -> None:
        with contextlib.suppress(ValueError):
            handler_list.remove(handler)

    on_cleanup(_cleanup)
    return _cleanup


def _use_deduped_handler(
    handler: Callable,
    handler_list: list,
    refs: dict[int, Callable],
) -> Callable[[], None]:
    handler_id = id(handler)
    prev = refs.pop(handler_id, None)
    if prev is not None and prev in handler_list:
        handler_list.remove(prev)

    handler_list.append(handler)
    refs[handler_id] = handler

    def _cleanup() -> None:
        w = refs.pop(handler_id, None)
        if w is not None and w in handler_list:
            handler_list.remove(w)

    on_cleanup(_cleanup)
    return _cleanup


def use_focus(handler: Callable[[str], None]) -> Callable[[], None]:
    return _use_identity_handler(handler, _focus_handlers)


def use_renderer() -> CliRenderer:
    renderer = get_renderer()
    if renderer is None:
        raise RuntimeError("No renderer available. Use render() to create one.")
    return renderer


def use_terminal_dimensions() -> tuple[int, int]:
    renderer = get_renderer()
    if renderer is not None:
        current = (renderer.width, renderer.height)
        if _terminal_dimensions() != current:
            _set_terminal_dimensions(*current)
    return _terminal_dimensions()


def use_on_resize(callback: Callable[[int, int], None]) -> CliRenderer:
    renderer = use_renderer()
    _use_identity_handler(callback, _resize_handlers)
    return renderer


_keyboard_handler_refs: dict[int, Callable] = {}


def use_keyboard(
    handler: Callable[[KeyEvent], None],
    options: dict | None = None,
) -> Callable[[], None]:
    handler_id = id(handler)
    prev = _keyboard_handler_refs.pop(handler_id, None)
    if prev is not None and prev in _keyboard_handlers:
        _keyboard_handlers.remove(prev)

    if options and options.get("release"):

        def wrapper(event: KeyEvent) -> None:
            handler(event)

        wrapper._original_handler = handler  # type: ignore[attr-defined]
        wrapper._receive_release = True  # type: ignore[attr-defined]
        _keyboard_handlers.append(wrapper)
        _keyboard_handler_refs[handler_id] = wrapper
    else:

        def press_only_wrapper(event: KeyEvent) -> None:
            if not hasattr(event, "event_type") or event.event_type == "press":
                handler(event)

        press_only_wrapper._original_handler = handler  # type: ignore[attr-defined]
        press_only_wrapper._receive_release = False  # type: ignore[attr-defined]
        _keyboard_handlers.append(press_only_wrapper)
        _keyboard_handler_refs[handler_id] = press_only_wrapper

    def _cleanup() -> None:
        w = _keyboard_handler_refs.pop(handler_id, None)
        if w is not None and w in _keyboard_handlers:
            _keyboard_handlers.remove(w)

    on_cleanup(_cleanup)
    return _cleanup


_mouse_handler_refs: dict[int, Callable] = {}


def use_mouse(handler: Callable[[MouseEvent], None]) -> Callable[[], None]:
    return _use_deduped_handler(handler, _mouse_handlers, _mouse_handler_refs)


def get_mouse_handlers() -> list[Callable[[MouseEvent], None]]:
    return _mouse_handlers.copy()


def clear_mouse_handlers() -> None:
    _mouse_handlers.clear()


_paste_handler_refs: dict[int, Callable] = {}


def use_paste(callback: Callable[[PasteEvent], None]) -> Callable[[], None]:
    return _use_deduped_handler(callback, _paste_handlers, _paste_handler_refs)


_selection_handler_refs: dict[int, Callable] = {}


def use_selection_handler(callback: Callable[[Any], None]) -> Callable[[], None]:
    return _use_deduped_handler(callback, _selection_handlers, _selection_handler_refs)


def on_mount(fn: Callable[[], None]) -> None:
    """Register a callback to run after the component is first mounted.

    Mirrors SolidJS ``onMount``. The callback runs once after the first
    layout pass that includes the component. Call from within a component
    body (i.e., during tree construction).

    Usage::

        def MyComponent():
            on_mount(lambda: print("mounted!"))
            return Text("hello")
    """
    _pending_mount_fns.append(fn)


def flush_mount_callbacks() -> None:
    if _pending_mount_fns:
        fns = _pending_mount_fns[:]
        _pending_mount_fns.clear()
        for fn in fns:
            fn()


def use_cursor(x: int, y: int) -> None:
    """Request the terminal cursor at screen position (x, y).

    Call this from a ``render_after`` callback where absolute coordinates
    are known.  The renderer positions the real terminal cursor after the
    frame buffer is flushed — the terminal emulator handles blinking
    natively, so there is zero overhead.
    """
    renderer = get_renderer()
    if renderer is not None:
        renderer.request_cursor(x, y)


def use_cursor_style(style: str = "block", color: str | RGBA | None = None) -> None:
    """Request a cursor style (and optional color) for this frame.

    Call alongside ``use_cursor`` from a ``render_after`` callback.
    If no position is requested this frame, the style is silently ignored.

    *style*: ``"block"``, ``"underline"``, ``"bar"`` (blinking variants),
    or ``"steady_block"``, ``"steady_underline"``, ``"steady_bar"``.

    *color*: Optional hex color string (e.g. ``"#ff0000"``) or RGBA.
    Pass ``None`` to use the terminal default.
    """
    renderer = get_renderer()
    if renderer is not None:
        color_str = color.to_hex() if isinstance(color, RGBA) else color
        renderer.request_cursor_style(style, color_str)


def use_timeline(options: dict | None = None) -> Timeline:
    return Timeline(options or {})


class Animation:
    def __init__(
        self,
        target: Any,
        property_name: str,
        start_value: float,
        end_value: float,
        duration: float,
        easing: str = "linear",
        start_time: float = 0,
    ):
        self.target = target
        self.property_name = property_name
        self.start_value = start_value
        self.end_value = end_value
        self.duration = duration
        self.easing = easing
        self.start_time = start_time
        self._current_value = start_value

    def get_value(self, elapsed: float) -> float:
        local_time = elapsed - self.start_time
        if local_time < 0:
            return self.start_value
        if local_time >= self.duration:
            return self.end_value

        progress = local_time / self.duration

        if self.easing == "ease-in":
            progress = progress**2
        elif self.easing == "ease-out":
            progress = 1 - (1 - progress) ** 2
        elif self.easing == "ease-in-out":
            if progress < 0.5:
                progress = 2 * progress * progress
            else:
                progress = 1 - (-2 * progress + 2) ** 2 / 2

        return self.start_value + (self.end_value - self.start_value) * progress


class Timeline:
    def __init__(self, options: dict):
        self._duration = options.get("duration", 1000)
        self._loop = options.get("loop", False)
        self._autoplay = options.get("autoplay", True)
        self._on_complete = options.get("on_complete")
        self._running = False
        self._animations: list[Animation] = []
        self._start_time: float | None = None

    def add(
        self,
        target: Any,
        properties: dict,
        start_time: float = 0,
        duration: float | None = None,
        easing: str = "linear",
    ) -> None:
        anim_duration = duration or (self._duration / len(properties)) if properties else 200

        for prop_name, end_value in properties.items():
            start_value = getattr(target, prop_name, 0)
            anim = Animation(
                target=target,
                property_name=prop_name,
                start_value=start_value,
                end_value=end_value,
                duration=anim_duration,
                easing=easing,
                start_time=start_time,
            )
            self._animations.append(anim)

    def update(self, elapsed: float) -> None:
        for anim in self._animations:
            value = anim.get_value(elapsed)
            setattr(anim.target, anim.property_name, value)

    def play(self) -> None:
        self._running = True

    def pause(self) -> None:
        self._running = False

    def restart(self) -> None:
        self._start_time = None
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


__all__ = [
    "use_renderer",
    "use_terminal_dimensions",
    "use_on_resize",
    "use_keyboard",
    "use_mouse",
    "use_paste",
    "use_cursor",
    "use_cursor_style",
    "use_selection_handler",
    "use_timeline",
    "on_mount",
    "flush_mount_callbacks",
    "Timeline",
    "Animation",
    "get_keyboard_handlers",
    "clear_keyboard_handlers",
    "get_mouse_handlers",
    "clear_mouse_handlers",
    "get_paste_handlers",
    "clear_paste_handlers",
    "get_resize_handlers",
    "clear_resize_handlers",
    "get_selection_handlers",
    "clear_selection_handlers",
    "get_focus_handlers",
    "clear_focus_handlers",
    "use_focus",
    "register_focus_handler",
    "unregister_focus_handler",
    "register_keyboard_handler",
    "unregister_keyboard_handler",
    "register_paste_handler",
    "unregister_paste_handler",
]
