"""Public animation API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ._runtime import (
    AnimationItem,
    CallbackItem,
    TimelineItem,
    evaluate_item,
    evaluate_timeline_sync,
)


@dataclass
class JSAnimation:
    """Animation state passed to onUpdate callbacks."""

    targets: list[Any]
    delta_time: float
    progress: float
    current_time: float


_RESERVED_KEYS = frozenset(
    {
        "duration",
        "ease",
        "on_update",
        "on_complete",
        "on_start",
        "on_loop",
        "loop",
        "loop_delay",
        "alternate",
        "once",
    }
)


class Timeline:
    """Animation timeline with support for animations, callbacks, and sub-timelines."""

    def __init__(
        self,
        duration: float = 1000.0,
        loop: bool = False,
        autoplay: bool = True,
        on_complete: Callable[[], None] | None = None,
        on_pause: Callable[[], None] | None = None,
    ) -> None:
        self.items: list[AnimationItem | CallbackItem] = []
        self.sub_timelines: list[TimelineItem] = []
        self.current_time: float = 0.0
        self.is_playing: bool = False
        self.is_complete: bool = False
        self.duration: float = duration
        self.loop: bool = loop
        self.synced: bool = False
        self._autoplay = autoplay
        self._on_complete = on_complete
        self._on_pause = on_pause
        self._state_change_listeners: list[Callable[[Timeline], None]] = []
        self._ticking: bool = False
        self._pending_delta: float = 0.0

    def add_state_change_listener(self, listener: Callable[[Timeline], None]) -> None:
        """Register a listener for timeline state changes."""
        self._state_change_listeners.append(listener)

    def remove_state_change_listener(self, listener: Callable[[Timeline], None]) -> None:
        """Remove a state change listener."""
        self._state_change_listeners = [
            cb for cb in self._state_change_listeners if cb is not listener
        ]

    def _notify_state_change(self) -> None:
        for listener in self._state_change_listeners:
            listener(self)

    def add(
        self,
        target: Any,
        properties: dict[str, Any],
        start_time: float | str = 0,
    ) -> Timeline:
        """Add an animation to the timeline.

        Args:
            target: Object or list of objects to animate.
            properties: Dict of property end-values and animation options
                (duration, ease, on_update, on_complete, on_start, on_loop,
                 loop, loop_delay, alternate, once).
            start_time: When the animation starts (ms). Strings resolve to 0.

        Returns:
            self for chaining.
        """
        resolved_start_time = 0.0 if isinstance(start_time, str) else float(start_time)

        anim_properties: dict[str, float] = {}
        for key, val in properties.items():
            if key not in _RESERVED_KEYS and isinstance(val, int | float):
                anim_properties[key] = float(val)

        targets = target if isinstance(target, list) else [target]

        self.items.append(
            AnimationItem(
                start_time=resolved_start_time,
                target=targets,
                properties=anim_properties,
                initial_values=[],
                duration=properties.get("duration", 1000.0),
                ease=properties.get("ease", "linear"),
                loop=properties.get("loop", False),
                loop_delay=properties.get("loop_delay", 0.0),
                alternate=properties.get("alternate", False),
                on_update=properties.get("on_update"),
                on_complete=properties.get("on_complete"),
                on_start=properties.get("on_start"),
                on_loop=properties.get("on_loop"),
                completed=False,
                started=False,
                current_loop=0,
                once=properties.get("once", False),
            )
        )

        return self

    def once(self, target: Any, properties: dict[str, Any]) -> Timeline:
        """Add a one-shot animation at the current time.

        Once animations play once and are removed after completion.
        They are not re-executed when the timeline loops.

        Args:
            target: Object or list of objects to animate.
            properties: Animation properties (same as add()).

        Returns:
            self for chaining.
        """
        props = dict(properties)
        props["once"] = True
        self.add(target, props, self.current_time)
        return self

    def call(self, callback: Callable[[], None], start_time: float | str = 0) -> Timeline:
        """Add a callback to be executed at the given time.

        Args:
            callback: Function to call.
            start_time: When to call it (ms). Strings resolve to 0.

        Returns:
            self for chaining.
        """
        resolved = 0.0 if isinstance(start_time, str) else float(start_time)
        self.items.append(
            CallbackItem(
                start_time=resolved,
                callback=callback,
                executed=False,
            )
        )
        return self

    def sync(self, timeline: Timeline, start_time: float = 0) -> Timeline:
        """Sync a sub-timeline to this timeline.

        Args:
            timeline: The sub-timeline to sync.
            start_time: When to start the sub-timeline (ms).

        Returns:
            self for chaining.

        Raises:
            RuntimeError: If the timeline is already synced.
        """
        if timeline.synced:
            raise RuntimeError("Timeline already synced")
        self.sub_timelines.append(
            TimelineItem(
                start_time=start_time,
                timeline=timeline,
            )
        )
        timeline.synced = True
        return self

    def play(self) -> Timeline:
        """Start or resume playback.

        If the timeline is complete, this restarts it.

        Returns:
            self for chaining.
        """
        if self.is_complete:
            return self.restart()
        for sub in self.sub_timelines:
            if sub.timeline_started and sub.timeline is not None:
                sub.timeline.play()
        self.is_playing = True
        self._notify_state_change()
        return self

    def pause(self) -> Timeline:
        """Pause playback.

        Returns:
            self for chaining.
        """
        for sub in self.sub_timelines:
            if sub.timeline is not None:
                sub.timeline.pause()
        self.is_playing = False
        if self._on_pause is not None:
            self._on_pause()
        self._notify_state_change()
        return self

    def _reset_items(self) -> None:
        for item in self.items:
            if isinstance(item, CallbackItem):
                item.executed = False
            elif isinstance(item, AnimationItem):
                item.completed = False
                item.started = False
                item.current_loop = 0
        for sub in self.sub_timelines:
            sub.timeline_started = False
            if sub.timeline is not None:
                sub.timeline.restart()
                sub.timeline.pause()

    def restart(self) -> Timeline:
        """Restart the timeline from the beginning.

        Returns:
            self for chaining.
        """
        self.is_complete = False
        self.current_time = 0.0
        self.is_playing = True
        self._reset_items()
        self._notify_state_change()
        return self

    def update(self, delta_time: float) -> None:
        """Advance the timeline by delta_time milliseconds.

        This is the main tick method called by the engine each frame.
        """
        if self._ticking:
            # Prevent re-entrant tick calls; queue the delta for later
            self._pending_delta += delta_time
            return
        self._ticking = True
        try:
            self._do_update(delta_time)
            # Drain any queued delta from re-entrant calls
            while self._pending_delta > 0:
                queued = self._pending_delta
                self._pending_delta = 0.0
                self._do_update(queued)
        finally:
            self._ticking = False

    def _do_update(self, delta_time: float) -> None:
        """Internal update logic, separated to support re-entrancy guard."""
        # Evaluate sub-timelines (they run even when paused to handle sync start)
        for sub in self.sub_timelines:
            evaluate_timeline_sync(sub, self.current_time + delta_time, delta_time)

        if not self.is_playing:
            return

        self.current_time += delta_time

        for item in self.items:
            evaluate_item(item, JSAnimation, self.current_time, delta_time)

        self.items = [
            item
            for item in self.items
            if not (isinstance(item, AnimationItem) and item.once and item.completed)
        ]

        if self.loop and self.current_time >= self.duration:
            overshoot = self.current_time % self.duration

            self._reset_items()
            self.current_time = 0.0

            if overshoot > 0:
                self.update(overshoot)
        elif not self.loop and self.current_time >= self.duration:
            self.current_time = self.duration
            self.is_playing = False
            self.is_complete = True

            if self._on_complete is not None:
                self._on_complete()
            self._notify_state_change()

    @property
    def is_running(self) -> bool:
        return self.is_playing

    def stop(self) -> None:
        self.pause()

    @property
    def progress(self) -> float:
        """Current progress as a 0..1 fraction."""
        if self.duration <= 0:
            return 1.0
        return min(self.current_time / self.duration, 1.0)


class TimelineEngine:
    """Manages a set of timelines and drives their updates."""

    def __init__(self) -> None:
        self._timelines: set[Timeline] = set()

    def register(self, timeline: Timeline) -> None:
        if timeline not in self._timelines:
            self._timelines.add(timeline)

    def unregister(self, timeline: Timeline) -> None:
        self._timelines.discard(timeline)

    def clear(self) -> None:
        self._timelines.clear()

    def update(self, delta_time: float) -> None:
        """Update all registered (non-synced) timelines."""
        for timeline in list(self._timelines):
            if not timeline.synced:
                timeline.update(delta_time)


# Module-level engine singleton
engine = TimelineEngine()


__all__ = [
    "JSAnimation",
    "Timeline",
    "TimelineEngine",
    "create_timeline",
    "engine",
]


def create_timeline(
    duration: float = 1000.0,
    loop: bool = False,
    autoplay: bool = True,
    on_complete: Callable[[], None] | None = None,
    on_pause: Callable[[], None] | None = None,
) -> Timeline:
    """Registers the timeline with the global engine.

    Args:
        duration: Timeline duration in ms.
        loop: Whether the timeline loops.
        autoplay: Whether to auto-play (default True).
        on_complete: Called when the timeline completes (non-looping only).
        on_pause: Called when the timeline is paused.
    """
    timeline = Timeline(
        duration=duration,
        loop=loop,
        autoplay=autoplay,
        on_complete=on_complete,
        on_pause=on_pause,
    )
    if autoplay:
        timeline.play()

    engine.register(timeline)
    return timeline
