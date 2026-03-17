"""Hooks for OpenTUI Python - matching @opentui/solid patterns."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .signals import Signal
from .structs import RGBA

if TYPE_CHECKING:
    from .events import KeyEvent, MouseEvent, PasteEvent
    from .renderer import CliRenderer


_current_renderer: CliRenderer | None = None
_keyboard_handlers: list[Callable[[KeyEvent], None]] = []
_mouse_handlers: list[Callable[[MouseEvent], None]] = []
_paste_handlers: list[Callable[[PasteEvent], None]] = []
_resize_handlers: list[Callable[[int, int], None]] = []
_selection_handlers: list[Callable[[Any], None]] = []
_focus_handlers: list[Callable[[str], None]] = []
_terminal_dimensions = Signal("terminal_dimensions", (80, 24))


def set_renderer(renderer: CliRenderer) -> None:
    """Set the current renderer (internal use)."""
    global _current_renderer
    _current_renderer = renderer
    _set_terminal_dimensions(renderer.width, renderer.height)


def get_renderer() -> CliRenderer | None:
    """Get the current renderer."""
    return _current_renderer


def get_keyboard_handlers() -> list[Callable[[KeyEvent], None]]:
    """Get all registered keyboard handlers."""
    return _keyboard_handlers.copy()


def clear_keyboard_handlers() -> None:
    """Clear all keyboard handlers."""
    _keyboard_handlers.clear()


def get_paste_handlers() -> list[Callable[[PasteEvent], None]]:
    """Get all registered paste handlers."""
    return _paste_handlers.copy()


def clear_paste_handlers() -> None:
    """Clear all paste handlers."""
    _paste_handlers.clear()


def get_resize_handlers() -> list[Callable[[int, int], None]]:
    """Get all registered resize handlers."""
    return _resize_handlers.copy()


def clear_resize_handlers() -> None:
    """Clear all resize handlers."""
    _resize_handlers.clear()


def _set_terminal_dimensions(width: int, height: int) -> None:
    """Update the shared terminal dimensions signal."""
    _terminal_dimensions.set((width, height))


def get_selection_handlers() -> list[Callable[[Any], None]]:
    """Get all registered selection handlers."""
    return _selection_handlers.copy()


def clear_selection_handlers() -> None:
    """Clear all selection handlers."""
    _selection_handlers.clear()


def get_focus_handlers() -> list[Callable[[str], None]]:
    """Get all registered focus handlers."""
    return _focus_handlers.copy()


def clear_focus_handlers() -> None:
    """Clear all focus handlers."""
    _focus_handlers.clear()


def register_focus_handler(handler: Callable[[str], None]) -> None:
    """Register a raw focus handler (not deduplicated, for testing)."""
    _focus_handlers.append(handler)


def unregister_focus_handler(handler: Callable[[str], None]) -> None:
    """Unregister a previously registered focus handler."""
    if handler in _focus_handlers:
        _focus_handlers.remove(handler)


def register_keyboard_handler(handler: Callable) -> None:
    """Register a raw keyboard handler (not deduplicated, for testing)."""
    _keyboard_handlers.append(handler)


def unregister_keyboard_handler(handler: Callable) -> None:
    """Unregister a previously registered keyboard handler."""
    if handler in _keyboard_handlers:
        _keyboard_handlers.remove(handler)


def register_paste_handler(handler: Callable[[PasteEvent], None]) -> None:
    """Register a paste handler (for components that need paste events)."""
    _paste_handlers.append(handler)


def unregister_paste_handler(handler: Callable[[PasteEvent], None]) -> None:
    """Unregister a previously registered paste handler."""
    if handler in _paste_handlers:
        _paste_handlers.remove(handler)


def use_focus(handler: Callable[[str], None]) -> None:
    """Subscribe to terminal focus/blur events.

    Args:
        handler: Called with ``"focus"`` or ``"blur"`` when the terminal
            window gains or loses focus.
    """
    if not any(h is handler for h in _focus_handlers):
        _focus_handlers.append(handler)


def use_renderer() -> CliRenderer:
    """Get the current renderer instance.

    Usage:
        renderer = use_renderer()
        renderer.set_title("My App")

    Raises:
        RuntimeError: If no renderer is available
    """
    renderer = get_renderer()
    if renderer is None:
        raise RuntimeError("No renderer available. Use render() to create one.")
    return renderer


def use_terminal_dimensions() -> tuple[int, int]:
    """Get current terminal dimensions.

    Returns:
        Tuple of (width, height) in terminal cells

    Usage:
        width, height = use_terminal_dimensions()
    """
    renderer = get_renderer()
    if renderer is not None:
        current = (renderer.width, renderer.height)
        if _terminal_dimensions() != current:
            _set_terminal_dimensions(*current)
    return _terminal_dimensions()


def use_on_resize(callback: Callable[[int, int], None]) -> CliRenderer:
    """Subscribe to terminal resize events.

    Args:
        callback: Called with (width, height) when terminal resizes

    Returns:
        The renderer for chaining

    Usage:
        def on_resize(width, height):
            print(f"Terminal resized to {width}x{height}")

        use_on_resize(on_resize)
    """
    renderer = use_renderer()
    if not any(handler is callback for handler in _resize_handlers):
        _resize_handlers.append(callback)
    return renderer


_keyboard_handler_refs: dict[int, Callable] = {}


def use_keyboard(
    handler: Callable[[KeyEvent], None],
    options: dict | None = None,
) -> None:
    """Subscribe to keyboard events.

    Args:
        handler: Called with KeyEvent when keys are pressed
        options: Optional settings like {"release": True} for key release events

    Usage:
        def on_key(event):
            if event.key == "escape":
                print("Escape pressed!")

        use_keyboard(on_key)

        # With release events
        use_keyboard(on_key, {"release": True})
    """
    # Remove the previous wrapper for this handler to prevent accumulation
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


_mouse_handler_refs: dict[int, Callable] = {}


def use_mouse(handler: Callable[[MouseEvent], None]) -> None:
    """Subscribe to mouse events (scroll, click, drag).

    Args:
        handler: Called with MouseEvent for mouse actions

    Usage:
        def on_mouse(event):
            if event.type == "scroll":
                print(f"Scroll: {event.scroll_delta}")

        use_mouse(on_mouse)
    """
    # Remove the previous handler to prevent accumulation
    handler_id = id(handler)
    prev = _mouse_handler_refs.pop(handler_id, None)
    if prev is not None and prev in _mouse_handlers:
        _mouse_handlers.remove(prev)

    _mouse_handlers.append(handler)
    _mouse_handler_refs[handler_id] = handler


def get_mouse_handlers() -> list[Callable[[MouseEvent], None]]:
    """Get all registered mouse handlers."""
    return _mouse_handlers.copy()


def clear_mouse_handlers() -> None:
    """Clear all mouse handlers."""
    _mouse_handlers.clear()


_paste_handler_refs: dict[int, Callable] = {}


def use_paste(callback: Callable[[PasteEvent], None]) -> None:
    """Subscribe to paste events.

    Args:
        callback: Called with a structured paste event

    Usage:
        def on_paste(event):
            print(f"Pasted: {event.text}")

        use_paste(on_paste)
    """
    # Remove the previous handler to prevent accumulation
    handler_id = id(callback)
    prev = _paste_handler_refs.pop(handler_id, None)
    if prev is not None and prev in _paste_handlers:
        _paste_handlers.remove(prev)

    _paste_handlers.append(callback)
    _paste_handler_refs[handler_id] = callback


_selection_handler_refs: dict[int, Callable] = {}


def use_selection_handler(callback: Callable[[Any], None]) -> None:
    """Subscribe to text selection events.

    Args:
        callback: Called with selection info

    Usage:
        def on_select(selection):
            print(f"Selected: {selection}")

        use_selection_handler(on_select)
    """
    # Remove the previous handler to prevent accumulation
    handler_id = id(callback)
    prev = _selection_handler_refs.pop(handler_id, None)
    if prev is not None and prev in _selection_handlers:
        _selection_handlers.remove(prev)

    _selection_handlers.append(callback)
    _selection_handler_refs[handler_id] = callback


def use_cursor(x: int, y: int) -> None:
    """Request the terminal cursor at screen position (x, y).

    Call this from a ``render_after`` callback where absolute coordinates
    are known.  The renderer positions the real terminal cursor after the
    frame buffer is flushed — the terminal emulator handles blinking
    natively, so there is zero rebuild overhead.
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
    """Create and manage a Timeline for animations.

    Args:
        options: Timeline options like {"duration": 1000, "autoplay": True}

    Returns:
        Timeline instance

    Usage:
        timeline = use_timeline({"duration": 1000, "autoplay": True})
        timeline.add(target, properties, start_time)
    """
    return Timeline(options or {})


class Animation:
    """Single animation definition."""

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
        """Get the interpolated value at given elapsed time."""
        local_time = elapsed - self.start_time
        if local_time < 0:
            return self.start_value
        if local_time >= self.duration:
            return self.end_value

        progress = local_time / self.duration

        if self.easing == "ease-in":
            progress = progress * progress
        elif self.easing == "ease-out":
            progress = 1 - (1 - progress) * (1 - progress)
        elif self.easing == "ease-in-out":
            if progress < 0.5:
                progress = 2 * progress * progress
            else:
                progress = 1 - (-2 * progress + 2) * (-2 * progress + 2) / 2

        return self.start_value + (self.end_value - self.start_value) * progress


class Timeline:
    """Animation timeline for smooth animations.

    This is a simplified version - full implementation would integrate
    with the render loop for smooth animations.
    """

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
        """Add an animation to the timeline.

        Args:
            target: Object to animate
            properties: Property names and target values ({"prop": end_value})
            start_time: Start time offset in ms
            duration: Animation duration in ms
            easing: Easing function ("linear", "ease-in", "ease-out", "ease-in-out")
        """
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
        """Update all animations.

        Args:
            elapsed: Elapsed time in ms since timeline started
        """
        for anim in self._animations:
            value = anim.get_value(elapsed)
            setattr(anim.target, anim.property_name, value)

    def play(self) -> None:
        """Start playing the timeline."""
        self._running = True

    def pause(self) -> None:
        """Pause the timeline."""
        self._running = False

    def restart(self) -> None:
        """Restart the timeline from the beginning."""
        self._start_time = None
        self._running = True

    def stop(self) -> None:
        """Stop the timeline."""
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
