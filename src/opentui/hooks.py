"""Hooks for OpenTUI Python - matching @opentui/solid patterns."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .events import KeyEvent
    from .renderer import CliRenderer


# Global renderer context
_current_renderer: CliRenderer | None = None
_keyboard_handlers: list[Callable[[KeyEvent], None]] = []


def set_renderer(renderer: CliRenderer) -> None:
    """Set the current renderer (internal use)."""
    global _current_renderer
    _current_renderer = renderer


def get_renderer() -> CliRenderer | None:
    """Get the current renderer."""
    return _current_renderer


def get_keyboard_handlers() -> list[Callable[[KeyEvent], None]]:
    """Get all registered keyboard handlers."""
    return _keyboard_handlers.copy()


def clear_keyboard_handlers() -> None:
    """Clear all keyboard handlers."""
    _keyboard_handlers.clear()


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
    renderer = use_renderer()
    return renderer.width, renderer.height


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
    # In full implementation, this would register with the event system
    return renderer


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
    if options and options.get("release"):
        # Wrap handler to also receive release events
        def wrapper(event: KeyEvent) -> None:
            handler(event)

        wrapper._original_handler = handler  # type: ignore[attr-defined]
        wrapper._receive_release = True  # type: ignore[attr-defined]
        _keyboard_handlers.append(wrapper)
    else:
        # Wrap handler to filter out release events
        def press_only_wrapper(event: KeyEvent) -> None:
            if not hasattr(event, "event_type") or event.event_type == "press":
                handler(event)

        press_only_wrapper._original_handler = handler  # type: ignore[attr-defined]
        press_only_wrapper._receive_release = False  # type: ignore[attr-defined]
        _keyboard_handlers.append(press_only_wrapper)


def use_paste(callback: Callable[[str], None]) -> None:
    """Subscribe to paste events.

    Args:
        callback: Called with pasted text

    Usage:
        def on_paste(text):
            print(f"Pasted: {text}")

        use_paste(on_paste)
    """
    # In full implementation: use_renderer() to register paste handler


def use_selection_handler(callback: Callable[[Any], None]) -> None:
    """Subscribe to text selection events.

    Args:
        callback: Called with selection info

    Usage:
        def on_select(selection):
            print(f"Selected: {selection}")

        use_selection_handler(on_select)
    """
    # In full implementation: use_renderer() to register selection handler


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
    "use_paste",
    "use_selection_handler",
    "use_timeline",
    "Timeline",
    "Animation",
]
