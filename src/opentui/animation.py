"""Animation engine for OpenTUI Python.

Animation timeline system for OpenTUI. Provides Timeline-based animations
with easing, looping, alternating, sub-timeline synchronization, and
callback support.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal


def _linear(t: float) -> float:
    return t


def _in_quad(t: float) -> float:
    return t * t


def _out_quad(t: float) -> float:
    return t * (2 - t)


def _in_out_quad(t: float) -> float:
    return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t


def _in_expo(t: float) -> float:
    return 0.0 if t == 0 else math.pow(2, 10 * (t - 1))


def _out_expo(t: float) -> float:
    return 1.0 if t == 1 else 1 - math.pow(2, -10 * t)


def _in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * t) - 1) / 2


def _out_bounce(t: float) -> float:
    n1 = 7.5625
    d1 = 2.75
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


def _out_elastic(t: float) -> float:
    c4 = (2 * math.pi) / 3
    if t == 0:
        return 0.0
    if t == 1:
        return 1.0
    return math.pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def _in_bounce(t: float) -> float:
    return 1 - _out_bounce(1 - t)


def _in_circ(t: float) -> float:
    return 1 - math.sqrt(1 - t * t)


def _out_circ(t: float) -> float:
    return math.sqrt(1 - (t - 1) ** 2)


def _in_out_circ(t: float) -> float:
    t2 = t * 2
    if t2 < 1:
        return -0.5 * (math.sqrt(1 - t2 * t2) - 1)
    t2 -= 2
    return 0.5 * (math.sqrt(1 - t2 * t2) + 1)


def _in_back(t: float, s: float = 1.70158) -> float:
    return t * t * ((s + 1) * t - s)


def _out_back(t: float, s: float = 1.70158) -> float:
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def _in_out_back(t: float, s: float = 1.70158) -> float:
    s *= 1.525
    t2 = t * 2
    if t2 < 1:
        return 0.5 * (t2 * t2 * ((s + 1) * t2 - s))
    t2 -= 2
    return 0.5 * (t2 * t2 * ((s + 1) * t2 + s) + 2)


EasingName = Literal[
    "linear",
    "inQuad",
    "outQuad",
    "inOutQuad",
    "inExpo",
    "outExpo",
    "inOutSine",
    "outBounce",
    "outElastic",
    "inBounce",
    "inCirc",
    "outCirc",
    "inOutCirc",
    "inBack",
    "outBack",
    "inOutBack",
]

EASING_FUNCTIONS: dict[str, Callable[..., float]] = {
    "linear": _linear,
    "inQuad": _in_quad,
    "outQuad": _out_quad,
    "inOutQuad": _in_out_quad,
    "inExpo": _in_expo,
    "outExpo": _out_expo,
    "inOutSine": _in_out_sine,
    "outBounce": _out_bounce,
    "outElastic": _out_elastic,
    "inBounce": _in_bounce,
    "inCirc": _in_circ,
    "outCirc": _out_circ,
    "inOutCirc": _in_out_circ,
    "inBack": _in_back,
    "outBack": _out_back,
    "inOutBack": _in_out_back,
}


@dataclass
class JSAnimation:
    """Animation state passed to onUpdate callbacks."""

    targets: list[Any]
    delta_time: float
    progress: float
    current_time: float


# Reserved keys that are not animation properties
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


@dataclass
class _AnimationItem:
    """An animation item on the timeline."""

    type: str = "animation"
    start_time: float = 0.0
    target: list[Any] = field(default_factory=list)
    properties: dict[str, float] | None = None
    initial_values: list[dict[str, float]] = field(default_factory=list)
    duration: float = 1000.0
    ease: str = "linear"
    loop: bool | int = False
    loop_delay: float = 0.0
    alternate: bool = False
    on_update: Callable[[JSAnimation], None] | None = None
    on_complete: Callable[[], None] | None = None
    on_start: Callable[[], None] | None = None
    on_loop: Callable[[], None] | None = None
    completed: bool = False
    started: bool = False
    current_loop: int = 0
    once: bool = False


@dataclass
class _CallbackItem:
    """A callback item on the timeline."""

    type: str = "callback"
    start_time: float = 0.0
    callback: Callable[[], None] | None = None
    executed: bool = False


@dataclass
class _TimelineItem:
    """A sub-timeline sync item."""

    type: str = "timeline"
    start_time: float = 0.0
    timeline: Timeline | None = None
    timeline_started: bool = False


def _capture_initial_values(item: _AnimationItem) -> None:
    """Capture current property values from targets as initial values."""
    if not item.properties:
        return
    if not item.initial_values:
        initial_values: list[dict[str, float]] = []
        for target in item.target:
            target_initial: dict[str, float] = {}
            for key in item.properties:
                val = (
                    getattr(target, key, None) if not isinstance(target, dict) else target.get(key)
                )
                if isinstance(val, int | float):
                    target_initial[key] = float(val)
            initial_values.append(target_initial)
        item.initial_values = initial_values


def _apply_animation_at_progress(
    item: _AnimationItem,
    progress: float,
    reversed_: bool,
    timeline_time: float,
    delta_time: float = 0.0,
) -> None:
    """Apply interpolated property values to targets."""
    if not item.properties or not item.initial_values:
        return

    easing_fn = EASING_FUNCTIONS.get(item.ease, _linear)
    clamped = max(0.0, min(1.0, progress))
    eased_progress = easing_fn(clamped)
    final_progress = 1.0 - eased_progress if reversed_ else eased_progress

    for i, target in enumerate(item.target):
        if i >= len(item.initial_values):
            continue
        target_initial = item.initial_values[i]

        for key, end_value in item.properties.items():
            start_value = target_initial.get(key, 0.0)
            new_value = start_value + (end_value - start_value) * final_progress
            if isinstance(target, dict):
                target[key] = new_value
            else:
                setattr(target, key, new_value)

    if item.on_update is not None:
        anim = JSAnimation(
            targets=item.target,
            progress=eased_progress,
            current_time=timeline_time,
            delta_time=delta_time,
        )
        item.on_update(anim)


def _evaluate_animation(
    item: _AnimationItem, timeline_time: float, delta_time: float = 0.0
) -> None:
    """Evaluate an animation item at the given timeline time."""
    if timeline_time < item.start_time:
        return

    animation_time = timeline_time - item.start_time
    duration = item.duration or 0.0

    if timeline_time >= item.start_time and not item.started:
        _capture_initial_values(item)
        if item.on_start is not None:
            item.on_start()
        item.started = True

    if duration <= 0:
        if not item.completed:
            _apply_animation_at_progress(item, 1.0, False, timeline_time, delta_time)
            if item.on_complete is not None:
                item.on_complete()
            item.completed = True
        return

    # Unified looping logic
    loop = item.loop
    if loop is True:
        max_loops = float("inf")
    elif not loop or loop == 1:
        max_loops = 1
    elif isinstance(loop, int):
        max_loops = loop
    else:
        max_loops = float("inf")

    loop_delay = item.loop_delay or 0.0
    cycle_time = duration + loop_delay
    current_cycle = int(animation_time // cycle_time)
    time_in_cycle = animation_time % cycle_time

    # Trigger on_loop if a loop cycle (not the final one) completes
    if (
        item.on_loop is not None
        and item.current_loop is not None
        and current_cycle > item.current_loop
        and current_cycle < max_loops
    ):
        item.on_loop()
    item.current_loop = current_cycle

    # Check if the animation part of the *final loop* has just completed
    if (
        item.on_complete is not None
        and not item.completed
        and current_cycle == max_loops - 1
        and time_in_cycle >= duration
    ):
        final_loop_reversed = item.alternate and (current_cycle % 2 == 1)
        _apply_animation_at_progress(item, 1.0, final_loop_reversed, timeline_time, delta_time)
        item.on_complete()
        item.completed = True
        return

    if current_cycle >= max_loops:
        if not item.completed:
            final_reversed = item.alternate and ((max_loops - 1) % 2 == 1)
            _apply_animation_at_progress(item, 1.0, final_reversed, timeline_time, delta_time)
            if item.on_complete is not None:
                item.on_complete()
            item.completed = True
        return

    if time_in_cycle == 0 and animation_time > 0 and current_cycle < max_loops:
        current_cycle = current_cycle - 1
        time_in_cycle = cycle_time

    if time_in_cycle >= duration:
        is_reversed = item.alternate and (current_cycle % 2 == 1)
        _apply_animation_at_progress(item, 1.0, is_reversed, timeline_time, delta_time)
        return

    progress = time_in_cycle / duration
    is_reversed = item.alternate and (current_cycle % 2 == 1)
    _apply_animation_at_progress(item, progress, is_reversed, timeline_time, delta_time)


def _evaluate_callback(item: _CallbackItem, timeline_time: float) -> None:
    """Evaluate a callback item at the given timeline time."""
    if not item.executed and timeline_time >= item.start_time and item.callback is not None:
        item.callback()
        item.executed = True


def _evaluate_timeline_sync(
    item: _TimelineItem, timeline_time: float, delta_time: float = 0.0
) -> None:
    """Evaluate a synced sub-timeline item."""
    if item.timeline is None:
        return
    if timeline_time < item.start_time:
        return

    if not item.timeline_started:
        item.timeline_started = True
        item.timeline.play()

        overshoot = timeline_time - item.start_time
        item.timeline.update(overshoot)
        return

    item.timeline.update(delta_time)


def _evaluate_item(
    item: _AnimationItem | _CallbackItem, timeline_time: float, delta_time: float = 0.0
) -> None:
    """Evaluate a timeline item (animation or callback)."""
    if item.type == "animation":
        _evaluate_animation(item, timeline_time, delta_time)  # type: ignore[arg-type]
    elif item.type == "callback":
        _evaluate_callback(item, timeline_time)  # type: ignore[arg-type]


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
        self.items: list[_AnimationItem | _CallbackItem] = []
        self.sub_timelines: list[_TimelineItem] = []
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
            _AnimationItem(
                type="animation",
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
            _CallbackItem(
                type="callback",
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
            _TimelineItem(
                type="timeline",
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
            if item.type == "callback":
                cb: _CallbackItem = item  # type: ignore[assignment]
                cb.executed = False
            elif item.type == "animation":
                anim: _AnimationItem = item  # type: ignore[assignment]
                anim.completed = False
                anim.started = False
                anim.current_loop = 0
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
            _evaluate_timeline_sync(sub, self.current_time + delta_time, delta_time)

        if not self.is_playing:
            return

        self.current_time += delta_time

        for item in self.items:
            _evaluate_item(item, self.current_time, delta_time)

        self.items = [
            item
            for item in self.items
            if not (
                item.type == "animation"
                and getattr(item, "once", False)
                and getattr(item, "completed", False)
            )
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
        """Whether the timeline is currently playing.

        Alias for ``is_playing``, kept for API compatibility with
        ``use_timeline()`` consumers.
        """
        return self.is_playing

    def stop(self) -> None:
        """Stop playback (alias for ``pause()``).

        Provided for API compatibility with the simplified Timeline
        that was previously defined in ``hooks.py``.
        """
        self.pause()

    @property
    def progress(self) -> float:
        """Current progress as a 0..1 fraction."""
        if self.duration <= 0:
            return 1.0
        return min(self.current_time / self.duration, 1.0)


# Backward-compatible alias — the hooks.py simplified ``Animation`` class
# was exported publicly.  ``JSAnimation`` is the closest equivalent in the
# full animation engine.
Animation = JSAnimation


class TimelineEngine:
    """Manages a set of timelines and drives their updates."""

    def __init__(self) -> None:
        self._timelines: set[Timeline] = set()
        self._is_live: bool = False
        self.defaults = {"frame_rate": 60}

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
