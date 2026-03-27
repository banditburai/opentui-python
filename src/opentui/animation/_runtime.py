from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .easing import EASING_FUNCTIONS, _linear

if TYPE_CHECKING:
    from .timeline import JSAnimation, Timeline


@dataclass
class AnimationItem:
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
class CallbackItem:
    start_time: float = 0.0
    callback: Callable[[], None] | None = None
    executed: bool = False


@dataclass
class TimelineItem:
    start_time: float = 0.0
    timeline: Timeline | None = None
    timeline_started: bool = False


def capture_initial_values(item: AnimationItem) -> None:
    if not item.properties or item.initial_values:
        return

    initial_values: list[dict[str, float]] = []
    for target in item.target:
        target_initial: dict[str, float] = {}
        for key in item.properties:
            val = getattr(target, key, None) if not isinstance(target, dict) else target.get(key)
            if isinstance(val, int | float):
                target_initial[key] = float(val)
        initial_values.append(target_initial)
    item.initial_values = initial_values


def apply_animation_at_progress(
    item: AnimationItem,
    animation_type: type[JSAnimation],
    progress: float,
    reversed_: bool,
    timeline_time: float,
    delta_time: float = 0.0,
) -> None:
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
        item.on_update(
            animation_type(
                targets=item.target,
                progress=eased_progress,
                current_time=timeline_time,
                delta_time=delta_time,
            )
        )


def evaluate_animation(
    item: AnimationItem,
    animation_type: type[JSAnimation],
    timeline_time: float,
    delta_time: float = 0.0,
) -> None:
    if timeline_time < item.start_time:
        return

    animation_time = timeline_time - item.start_time
    duration = item.duration or 0.0

    if timeline_time >= item.start_time and not item.started:
        capture_initial_values(item)
        if item.on_start is not None:
            item.on_start()
        item.started = True

    if duration <= 0:
        if not item.completed:
            apply_animation_at_progress(item, animation_type, 1.0, False, timeline_time, delta_time)
            if item.on_complete is not None:
                item.on_complete()
            item.completed = True
        return

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

    if item.on_loop is not None and current_cycle > item.current_loop and current_cycle < max_loops:
        item.on_loop()
    item.current_loop = current_cycle

    if (
        item.on_complete is not None
        and not item.completed
        and current_cycle == max_loops - 1
        and time_in_cycle >= duration
    ):
        final_loop_reversed = item.alternate and (current_cycle % 2 == 1)
        apply_animation_at_progress(
            item, animation_type, 1.0, final_loop_reversed, timeline_time, delta_time
        )
        item.on_complete()
        item.completed = True
        return

    if current_cycle >= max_loops:
        if not item.completed:
            final_reversed = item.alternate and ((max_loops - 1) % 2 == 1)
            apply_animation_at_progress(
                item, animation_type, 1.0, final_reversed, timeline_time, delta_time
            )
            if item.on_complete is not None:
                item.on_complete()
            item.completed = True
        return

    if time_in_cycle == 0 and animation_time > 0 and current_cycle < max_loops:
        current_cycle -= 1
        time_in_cycle = cycle_time

    if time_in_cycle >= duration:
        is_reversed = item.alternate and (current_cycle % 2 == 1)
        apply_animation_at_progress(
            item, animation_type, 1.0, is_reversed, timeline_time, delta_time
        )
        return

    progress = time_in_cycle / duration
    is_reversed = item.alternate and (current_cycle % 2 == 1)
    apply_animation_at_progress(
        item, animation_type, progress, is_reversed, timeline_time, delta_time
    )


def evaluate_callback(item: CallbackItem, timeline_time: float) -> None:
    if not item.executed and timeline_time >= item.start_time and item.callback is not None:
        item.callback()
        item.executed = True


def evaluate_timeline_sync(
    item: TimelineItem, timeline_time: float, delta_time: float = 0.0
) -> None:
    if item.timeline is None or timeline_time < item.start_time:
        return

    if not item.timeline_started:
        item.timeline_started = True
        item.timeline.play()
        overshoot = timeline_time - item.start_time
        item.timeline.update(overshoot)
        return

    item.timeline.update(delta_time)


def evaluate_item(
    item: AnimationItem | CallbackItem,
    animation_type: type[JSAnimation],
    timeline_time: float,
    delta_time: float = 0.0,
) -> None:
    if isinstance(item, AnimationItem):
        evaluate_animation(item, animation_type, timeline_time, delta_time)
    elif isinstance(item, CallbackItem):
        evaluate_callback(item, timeline_time)


__all__ = [
    "AnimationItem",
    "CallbackItem",
    "TimelineItem",
    "evaluate_item",
    "evaluate_timeline_sync",
]
