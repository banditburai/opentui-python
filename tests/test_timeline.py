"""Port of upstream Timeline.test.ts.

Upstream: packages/core/src/animation/Timeline.test.ts
Tests ported: 95/95
Note: upstream has 90 it() call sites, but testCases.forEach generates 6 easing tests from 1 it()
"""

import pytest

from opentui.animation import (
    JSAnimation,
    Timeline,
    TimelineEngine,
    create_timeline,
    engine,
)


@pytest.fixture(autouse=True)
def _clear_engine():
    """Clear the global engine before and after each test."""
    engine.clear()
    yield
    engine.clear()


class TestTimelineBasicAnimation:
    """Maps to describe("Timeline") > describe("Basic Animation")."""

    def test_should_animate_a_single_property(self):
        """Maps to it("should animate a single property")."""
        target = {"x": 0, "y": 0, "value": 0}
        update_callbacks: list[JSAnimation] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "on_update": lambda anim: update_callbacks.append(anim),
            },
        )

        timeline.play()

        engine.update(0)
        assert target["x"] == 0

        engine.update(500)
        assert target["x"] == 50

        engine.update(500)
        assert target["x"] == 100
        assert len(update_callbacks) > 0

    def test_should_animate_multiple_properties(self):
        """Maps to it("should animate multiple properties")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "y": 200,
                "duration": 1000,
            },
        )

        timeline.play()
        engine.update(500)

        assert target["x"] == 50
        assert target["y"] == 100

    def test_should_handle_easing_functions(self):
        """Maps to it("should handle easing functions")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "ease": "linear",
            },
        )

        timeline.play()
        engine.update(500)

        assert target["x"] == 50


class TestTimelineControl:
    """Maps to describe("Timeline") > describe("Timeline Control")."""

    def _setup(self):
        target = {"x": 0, "y": 0, "value": 0}
        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 1000})
        return target, timeline

    def test_should_start_paused_when_autoplay_is_false(self):
        """Maps to it("should start paused when autoplay is false")."""
        target, timeline = self._setup()
        engine.update(500)
        assert target["x"] == 0

    def test_should_animate_when_played(self):
        """Maps to it("should animate when played")."""
        target, timeline = self._setup()
        timeline.play()
        engine.update(500)
        assert target["x"] == 50

    def test_should_pause_animation(self):
        """Maps to it("should pause animation")."""
        target, timeline = self._setup()
        timeline.play()
        engine.update(250)
        assert target["x"] == 25

        timeline.pause()
        engine.update(250)
        assert target["x"] == 25

    def test_should_restart_animation(self):
        """Maps to it("should restart animation")."""
        target, timeline = self._setup()
        timeline.play()
        engine.update(500)
        assert target["x"] == 50

        timeline.restart()
        engine.update(250)
        assert target["x"] == 25

    def test_should_play_again_when_calling_play_on_a_finished_non_looping_timeline(self):
        """Maps to it("should play again when calling play() on a finished non-looping timeline")."""
        target, timeline = self._setup()
        timeline.play()

        engine.update(1000)
        assert target["x"] == 100
        assert timeline.is_playing is False

        timeline.play()
        assert timeline.is_playing is True

        engine.update(500)
        assert target["x"] == 50

        engine.update(500)
        assert target["x"] == 100
        assert timeline.is_playing is False

    def test_should_call_on_pause_callback_when_timeline_is_paused(self):
        """Maps to it("should call onPause callback when timeline is paused")."""
        target = {"x": 0, "y": 0, "value": 0}
        pause_call_count = [0]

        timeline = create_timeline(
            duration=1000,
            autoplay=False,
            on_pause=lambda: pause_call_count.__setitem__(0, pause_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 1000})

        timeline.play()
        engine.update(500)
        assert target["x"] == 50
        assert pause_call_count[0] == 0

        timeline.pause()
        assert pause_call_count[0] == 1
        assert timeline.is_playing is False

        timeline.pause()
        assert pause_call_count[0] == 2

        timeline.play()
        timeline.pause()
        assert pause_call_count[0] == 3

    def test_should_not_call_on_pause_callback_when_timeline_is_not_initialized_with_one(self):
        """Maps to it("should not call onPause callback when timeline is not initialized with one")."""
        target = {"x": 0, "y": 0, "value": 0}
        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 1000})

        timeline.play()
        timeline.pause()

        assert timeline.is_playing is False

    def test_should_not_call_on_pause_callback_when_timeline_completes_naturally(self):
        """Maps to it("should not call onPause callback when timeline completes naturally")."""
        target = {"x": 0, "y": 0, "value": 0}
        pause_call_count = [0]
        complete_call_count = [0]
        timeline = create_timeline(
            duration=1000,
            autoplay=False,
            on_pause=lambda: pause_call_count.__setitem__(0, pause_call_count[0] + 1),
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 500})

        timeline.play()
        engine.update(1000)

        assert timeline.is_playing is False
        assert pause_call_count[0] == 0
        assert complete_call_count[0] == 1


class TestTimelineLooping:
    """Maps to describe("Timeline") > describe("Looping")."""

    def test_should_loop_timeline_when_loop_is_true(self):
        """Maps to it("should loop timeline when loop is true")."""
        target = {"x": 0, "y": 0, "value": 0}
        timeline = create_timeline(duration=1000, loop=True, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 1000})

        timeline.play()

        engine.update(1000)
        assert target["x"] == 100

        engine.update(500)
        assert target["x"] == 50

    def test_should_not_loop_when_loop_is_false(self):
        """Maps to it("should not loop when loop is false")."""
        target = {"x": 0, "y": 0, "value": 0}
        timeline = create_timeline(duration=1000, loop=False, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 1000})

        timeline.play()

        engine.update(1000)
        assert target["x"] == 100
        assert timeline.is_playing is False

        engine.update(500)
        assert target["x"] == 100


class TestTimelineIndividualAnimationLoops:
    """Maps to describe("Timeline") > describe("Individual Animation Loops")."""

    def test_should_loop_individual_animation_specified_number_of_times(self):
        """Maps to it("should loop individual animation specified number of times")."""
        target = {"x": 0, "y": 0, "value": 0}
        completion_count = [0]

        timeline = create_timeline(duration=5000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "loop": 3,
                "on_complete": lambda: completion_count.__setitem__(0, completion_count[0] + 1),
            },
        )

        timeline.play()

        engine.update(1000)
        assert target["x"] == 100
        assert completion_count[0] == 0

        engine.update(1000)
        assert target["x"] == 100
        assert completion_count[0] == 0

        engine.update(1000)
        assert target["x"] == 100
        assert completion_count[0] == 1

        engine.update(1000)
        assert target["x"] == 100
        assert completion_count[0] == 1

    def test_should_handle_loop_delay(self):
        """Maps to it("should handle loop delay")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=5000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "loop": 2,
                "loop_delay": 500,
            },
        )

        timeline.play()

        engine.update(1000)
        assert target["x"] == 100

        engine.update(250)
        assert target["x"] == 100

        engine.update(250)
        engine.update(500)
        assert target["x"] == 50


class TestTimelineAlternatingAnimations:
    """Maps to describe("Timeline") > describe("Alternating Animations")."""

    def test_should_alternate_direction_with_each_loop(self):
        """Maps to it("should alternate direction with each loop")."""
        target = {"x": 0, "y": 0, "value": 0}
        values: list[float] = []

        timeline = create_timeline(duration=5000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "loop": 3,
                "alternate": True,
                "on_update": lambda anim: values.append(anim.targets[0]["x"]),
            },
        )

        timeline.play()

        engine.update(500)
        assert target["x"] == 50
        engine.update(500)
        assert target["x"] == 100

        engine.update(500)
        assert target["x"] == 50
        engine.update(500)
        assert target["x"] == 0

        engine.update(500)
        assert target["x"] == 50
        engine.update(500)
        assert target["x"] == 100

    def test_should_handle_alternating_with_loop_delay(self):
        """Maps to it("should handle alternating with loop delay")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=5000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "loop": 2,
                "alternate": True,
                "loop_delay": 500,
            },
        )

        timeline.play()

        engine.update(1000)
        assert target["x"] == 100

        engine.update(500)
        assert target["x"] == 100

        engine.update(500)
        assert target["x"] == 50
        engine.update(500)
        assert target["x"] == 0

    def test_should_handle_alternating_animations_with_looping_parent_timeline(self):
        """Maps to it("should handle alternating animations with looping parent timeline")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=3000, loop=True, autoplay=False)

        animation_values: list[dict] = []
        main_timeline_loops = [0]

        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "loop": 2,
                "alternate": True,
                "on_update": lambda anim: animation_values.append(
                    {
                        "time": timeline.current_time,
                        "value": anim.targets[0]["x"],
                        "loop": main_timeline_loops[0],
                    }
                ),
            },
            500,
        )

        timeline.play()

        engine.update(500)
        first_loop_start_value = target["x"]
        engine.update(500)
        engine.update(500)
        engine.update(500)
        engine.update(500)
        engine.update(500)

        main_timeline_loops[0] += 1

        second_loop_time = timeline.current_time
        engine.update(500)
        second_loop_start_value = target["x"]

        assert second_loop_time == 0
        assert second_loop_start_value == first_loop_start_value


class TestTimelineSync:
    """Maps to describe("Timeline") > describe("Timeline Sync")."""

    def test_should_sync_sub_timelines_to_main_timeline(self):
        """Maps to it("should sync sub-timelines to main timeline")."""
        main_timeline = create_timeline(duration=3000, autoplay=False)
        sub_timeline = create_timeline(duration=1000, autoplay=False)

        sub_target = {"value": 0}
        sub_timeline.add(sub_target, {"value": 100, "duration": 1000})

        main_timeline.sync(sub_timeline, 1000)
        main_timeline.play()

        engine.update(500)
        assert sub_target["value"] == 0

        engine.update(500)
        assert sub_target["value"] == 0

        engine.update(500)
        assert sub_target["value"] == 50

        engine.update(500)
        assert sub_target["value"] == 100

        engine.update(500)
        assert sub_target["value"] == 100

    def test_should_restart_completed_sub_timelines_when_main_timeline_loops(self):
        """Maps to it("should restart completed sub-timelines when main timeline loops")."""
        main_timeline = create_timeline(duration=1000, loop=True, autoplay=False)
        sub_timeline = create_timeline(duration=300, autoplay=False)

        sub_target = {"value": 0}
        sub_complete_count = [0]

        sub_timeline.add(
            sub_target,
            {
                "value": 100,
                "duration": 300,
                "on_complete": lambda: sub_complete_count.__setitem__(0, sub_complete_count[0] + 1),
            },
        )

        main_timeline.sync(sub_timeline, 200)
        main_timeline.play()

        engine.update(200)
        assert sub_target["value"] == 0

        engine.update(150)
        assert sub_target["value"] == 50

        engine.update(150)
        assert sub_target["value"] == 100
        assert sub_complete_count[0] == 1
        assert sub_timeline.is_playing is False

        engine.update(500)

        assert main_timeline.current_time == 0
        assert sub_target["value"] == 100
        assert sub_timeline.is_playing is False

        engine.update(200)
        assert sub_timeline.is_playing is True

        engine.update(150)
        assert sub_target["value"] == 50

        engine.update(150)
        assert sub_target["value"] == 100
        assert sub_complete_count[0] == 2

    def test_should_preserve_initial_values_for_looping_sub_timeline_when_main_timeline_does_not_loop(
        self,
    ):
        """Maps to it("should preserve initial values for looping sub-timeline when main timeline does not loop")."""
        main_timeline = create_timeline(duration=5000, loop=False, autoplay=False)
        sub_timeline = create_timeline(duration=1000, loop=True, autoplay=False)

        sub_target = {"x": 10, "y": 20}
        captured_states: list[dict] = []
        sub_loop_count = [0]

        sub_target["x"] = 50
        sub_target["y"] = 80

        sub_timeline.add(
            sub_target,
            {
                "x": 200,
                "y": 300,
                "duration": 1000,
                "on_update": lambda anim: captured_states.append(
                    {
                        "x": anim.targets[0]["x"],
                        "y": anim.targets[0]["y"],
                        "time": main_timeline.current_time,
                        "loop": sub_loop_count[0],
                    }
                ),
                "on_complete": lambda: sub_loop_count.__setitem__(0, sub_loop_count[0] + 1),
            },
        )

        main_timeline.sync(sub_timeline, 1500)
        main_timeline.play()

        engine.update(1000)
        assert sub_target["x"] == 50
        assert sub_target["y"] == 80
        assert len(captured_states) == 0

        engine.update(750)
        assert len(captured_states) > 0

        first_loop_midpoint = next((s for s in captured_states if s["loop"] == 0), None)
        assert first_loop_midpoint is not None
        assert first_loop_midpoint["x"] > 50
        assert first_loop_midpoint["x"] < 200
        assert first_loop_midpoint["y"] > 80
        assert first_loop_midpoint["y"] < 300

        engine.update(750)
        assert sub_target["x"] == 200
        assert sub_target["y"] == 300
        assert sub_loop_count[0] == 1

        engine.update(500)

        second_loop_midpoint = next(
            (s for s in captured_states if s["loop"] == 1 and s["time"] >= 2500), None
        )
        assert second_loop_midpoint is not None
        assert second_loop_midpoint["x"] > 50
        assert second_loop_midpoint["x"] < 200
        assert second_loop_midpoint["y"] > 80
        assert second_loop_midpoint["y"] < 300

        engine.update(500)
        assert sub_target["x"] == 200
        assert sub_target["y"] == 300
        assert sub_loop_count[0] == 2

        engine.update(500)

        third_loop_midpoint = next(
            (s for s in captured_states if s["loop"] == 2 and s["time"] >= 3500), None
        )
        assert third_loop_midpoint is not None
        assert third_loop_midpoint["x"] > 50
        assert third_loop_midpoint["x"] < 200
        assert third_loop_midpoint["y"] > 80
        assert third_loop_midpoint["y"] < 300

        engine.update(1000)
        assert main_timeline.is_playing is False
        assert sub_loop_count[0] >= 2

    def test_should_pause_sub_timelines_when_main_timeline_is_paused(self):
        """Maps to it("should pause sub-timelines when main timeline is paused")."""
        main_timeline = create_timeline(duration=3000, autoplay=False)
        sub_timeline = create_timeline(duration=1000, autoplay=False)

        main_target = {"x": 0}
        sub_target = {"value": 0}

        main_timeline.add(main_target, {"x": 100, "duration": 2000})
        sub_timeline.add(sub_target, {"value": 50, "duration": 800})

        main_timeline.sync(sub_timeline, 500)
        main_timeline.play()

        engine.update(250)
        assert main_target["x"] == 12.5
        assert sub_target["value"] == 0
        assert main_timeline.is_playing is True
        assert sub_timeline.is_playing is False

        engine.update(500)
        assert main_target["x"] == 37.5
        assert sub_target["value"] == 15.625
        assert main_timeline.is_playing is True
        assert sub_timeline.is_playing is True

        main_timeline.pause()
        assert main_timeline.is_playing is False
        assert sub_timeline.is_playing is False

        engine.update(400)
        assert main_target["x"] == 37.5
        assert sub_target["value"] == 15.625
        assert sub_timeline.is_playing is False

        main_timeline.play()
        assert main_timeline.is_playing is True
        assert sub_timeline.is_playing is True

        engine.update(200)
        assert main_target["x"] == 47.5
        assert sub_target["value"] == 28.125
        assert sub_timeline.is_playing is True


class TestTimelineCallbacks:
    """Maps to describe("Timeline") > describe("Callbacks")."""

    def test_should_execute_call_callbacks_at_specified_times(self):
        """Maps to it("should execute call callbacks at specified times")."""
        call_times: list[int] = []

        timeline = create_timeline(duration=2000, autoplay=False)
        timeline.call(lambda: call_times.append(0), 0)
        timeline.call(lambda: call_times.append(1000), 1000)
        timeline.call(lambda: call_times.append(1500), 1500)

        timeline.play()

        engine.update(500)
        assert call_times == [0]

        engine.update(500)
        assert call_times == [0, 1000]

        engine.update(500)
        assert call_times == [0, 1000, 1500]

    def test_should_support_string_start_time_parameters(self):
        """Maps to it("should support string startTime parameters")."""
        target = {"x": 0, "y": 0, "value": 0}
        call_times: list[str] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.call(lambda: call_times.append("start"), "start")
        timeline.add(target, {"x": 100, "duration": 1000}, "start")

        timeline.play()
        engine.update(500)

        assert call_times == ["start"]
        assert target["x"] == 50

    def test_should_trigger_on_start_callback_correctly(self):
        """Maps to it("should trigger onStart callback correctly")."""
        target = {"x": 0, "y": 0, "value": 0}
        started = [False]

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "on_start": lambda: started.__setitem__(0, True),
            },
            200,
        )

        timeline.play()
        assert started[0] is False

        engine.update(100)
        assert started[0] is False
        assert target["x"] == 0

        engine.update(150)
        assert started[0] is True
        assert target["x"] == 10

    def test_should_trigger_on_loop_callback_correctly_for_individual_animation_loops(self):
        """Maps to it("should trigger onLoop callback correctly for individual animation loops")."""
        target = {"x": 0, "y": 0, "value": 0}
        loop_count = [0]
        complete_count = [0]

        timeline = create_timeline(duration=5000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "loop": 3,
                "loop_delay": 100,
                "on_loop": lambda: loop_count.__setitem__(0, loop_count[0] + 1),
                "on_complete": lambda: complete_count.__setitem__(0, complete_count[0] + 1),
            },
        )

        timeline.play()

        engine.update(500)
        assert target["x"] == 100
        assert loop_count[0] == 0
        engine.update(100)
        assert loop_count[0] == 1

        engine.update(500)
        assert target["x"] == 100
        assert loop_count[0] == 1
        engine.update(100)
        assert loop_count[0] == 2

        engine.update(500)
        assert target["x"] == 100
        assert loop_count[0] == 2
        assert complete_count[0] == 1


class TestTimelineComplexLoopingScenarios:
    """Maps to describe("Timeline") > describe("Complex Looping Scenarios")."""

    def test_should_correctly_reset_and_re_run_finite_looped_animation_when_parent_timeline_loops(
        self,
    ):
        """Maps to it("should correctly reset and re-run finite-looped animation when parent timeline loops")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=2000, loop=True, autoplay=False)

        anim_loop_count = [0]
        anim_complete_count = [0]
        anim_start_count = [0]

        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "loop": 2,
                "loop_delay": 100,
                "on_start": lambda: anim_start_count.__setitem__(0, anim_start_count[0] + 1),
                "on_loop": lambda: anim_loop_count.__setitem__(0, anim_loop_count[0] + 1),
                "on_complete": lambda: anim_complete_count.__setitem__(
                    0, anim_complete_count[0] + 1
                ),
            },
            500,
        )

        timeline.play()

        engine.update(500)
        assert anim_start_count[0] == 1
        engine.update(500)
        assert target["x"] == 100
        assert anim_loop_count[0] == 0
        engine.update(100)
        assert anim_loop_count[0] == 1

        engine.update(500)
        assert target["x"] == 100
        assert anim_loop_count[0] == 1
        assert anim_complete_count[0] == 1
        engine.update(100)
        assert anim_loop_count[0] == 1
        assert anim_complete_count[0] == 1

        engine.update(300)
        assert target["x"] == 100
        assert anim_complete_count[0] == 1

        assert timeline.current_time == 0

        engine.update(500)
        assert anim_start_count[0] == 2
        assert target["x"] == 0

        engine.update(500)
        assert target["x"] == 100
        assert anim_loop_count[0] == 1
        engine.update(100)
        assert anim_loop_count[0] == 2

        engine.update(500)
        assert target["x"] == 100
        assert anim_loop_count[0] == 2
        assert anim_complete_count[0] == 2


class TestTimelineTimingPrecisionAnimationStartTimeOvershoot:
    """Maps to describe("Timeline") > describe("Timing Precision") > describe("Animation Start Time Overshoot")."""

    def test_should_account_for_overshoot_when_animation_starts_late(self):
        """Maps to it("should account for overshoot when animation starts late")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=2000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "ease": "linear",
            },
            50,
        )

        timeline.play()

        engine.update(66)
        assert target["x"] == pytest.approx(1.6, abs=0.1)

    def test_should_handle_multiple_animations_with_different_start_time_overshoots(self):
        """Maps to it("should handle multiple animations with different start time overshoots")."""
        target1 = {"x": 0}
        target2 = {"y": 0}

        timeline = create_timeline(duration=3000, autoplay=False)
        timeline.add(target1, {"x": 100, "duration": 1000, "ease": "linear"}, 30)
        timeline.add(target2, {"y": 200, "duration": 1000, "ease": "linear"}, 80)

        timeline.play()
        engine.update(100)

        assert target1["x"] == pytest.approx(7, abs=0.1)
        assert target2["y"] == pytest.approx(4, abs=0.1)

    def test_should_handle_zero_duration_animations_with_overshoot(self):
        """Maps to it("should handle zero duration animations with overshoot")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 0}, 50)

        timeline.play()
        engine.update(66)

        assert target["x"] == 100


class TestTimelineTimingPrecisionLoopDelayPrecision:
    """Maps to describe("Timeline") > describe("Timing Precision") > describe("Loop Delay Precision")."""

    def test_should_account_for_overshoot_in_loop_delays(self):
        """Maps to it("should account for overshoot in loop delays")."""
        target = {"x": 0, "y": 0, "value": 0}
        values: list[float] = []

        timeline = create_timeline(duration=5000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "loop": 3,
                "loop_delay": 500,
                "ease": "linear",
                "on_update": lambda anim: values.append(anim.targets[0]["x"]),
            },
        )

        timeline.play()

        engine.update(1000)
        assert target["x"] == 100

        engine.update(516)
        assert target["x"] == pytest.approx(1.6, abs=0.1)

    def test_should_handle_multiple_loop_delay_overshoots(self):
        """Maps to it("should handle multiple loop delay overshoots")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=10000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "loop": 4,
                "loop_delay": 300,
                "ease": "linear",
            },
        )

        timeline.play()

        engine.update(1000)
        assert target["x"] == 100

        engine.update(333)
        assert target["x"] == pytest.approx(3.3, abs=0.1)

        engine.update(967)
        assert target["x"] == 100

        engine.update(350)
        assert target["x"] == pytest.approx(5, abs=0.1)

    def test_should_handle_alternating_animations_with_loop_delay_overshoot(self):
        """Maps to it("should handle alternating animations with loop delay overshoot")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=8000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "loop": 3,
                "alternate": True,
                "loop_delay": 400,
                "ease": "linear",
            },
        )

        timeline.play()

        engine.update(1000)
        assert target["x"] == 100

        engine.update(450)
        assert target["x"] == 95

        engine.update(950)
        assert target["x"] == 0

        engine.update(425)
        assert target["x"] == 2.5


class TestTimelineTimingPrecisionSyncedTimelinePrecision:
    """Maps to describe("Timeline") > describe("Timing Precision") > describe("Synced Timeline Precision")."""

    def test_should_account_for_overshoot_when_starting_synced_timelines(self):
        """Maps to it("should account for overshoot when starting synced timelines")."""
        main_timeline = create_timeline(duration=3000, autoplay=False)
        sub_timeline = create_timeline(duration=1000, autoplay=False)

        sub_target = {"value": 0}
        sub_timeline.add(sub_target, {"value": 100, "duration": 1000, "ease": "linear"})

        main_timeline.sync(sub_timeline, 500)
        main_timeline.play()

        engine.update(533)
        assert sub_target["value"] == pytest.approx(3.3, abs=0.1)

    def test_should_handle_multiple_synced_timelines_with_different_overshoot_amounts(self):
        """Maps to it("should handle multiple synced timelines with different overshoot amounts")."""
        main_timeline = create_timeline(duration=5000, autoplay=False)
        sub_timeline1 = create_timeline(duration=1000, autoplay=False)
        sub_timeline2 = create_timeline(duration=1500, autoplay=False)

        sub_target1 = {"value": 0}
        sub_target2 = {"value": 0}

        sub_timeline1.add(sub_target1, {"value": 100, "duration": 1000, "ease": "linear"})
        sub_timeline2.add(sub_target2, {"value": 200, "duration": 1500, "ease": "linear"})

        main_timeline.sync(sub_timeline1, 300)
        main_timeline.sync(sub_timeline2, 800)
        main_timeline.play()

        engine.update(850)

        assert sub_target1["value"] == pytest.approx(55, abs=1)
        assert sub_target2["value"] == pytest.approx(6.67, abs=0.1)


class TestTimelineTimingPrecisionComplexPrecisionScenarios:
    """Maps to describe("Timeline") > describe("Timing Precision") > describe("Complex Precision Scenarios")."""

    def test_should_handle_alternating_animation_with_main_timeline_loop_and_overshoot(self):
        """Maps to it("should handle alternating animation with main timeline loop and overshoot")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=3000, loop=True, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 800,
                "loop": 2,
                "alternate": True,
                "loop_delay": 200,
                "ease": "linear",
            },
            500,
        )

        timeline.play()

        engine.update(3100)

        assert target["x"] == 0

        engine.update(450)
        assert target["x"] == 6.25

        engine.update(750 + 250)
        assert target["x"] == 93.75

    def test_should_maintain_precision_across_multiple_frame_updates_at_30fps(self):
        """Maps to it("should maintain precision across multiple frame updates at 30fps")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=2000, autoplay=False)

        frame_time = 33.33
        values: list[float] = []

        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "ease": "linear",
                "on_update": lambda anim: values.append(anim.targets[0]["x"]),
            },
            50,
        )

        timeline.play()

        engine.update(frame_time)
        assert target["x"] == 0

        engine.update(frame_time)
        assert target["x"] == pytest.approx(1.67, abs=0.1)

        engine.update(frame_time)
        assert target["x"] == pytest.approx(5, abs=0.1)

        for _ in range(29):
            engine.update(frame_time)

        assert target["x"] == pytest.approx(100, abs=0.5)


class TestTimelineEdgeCases:
    """Maps to describe("Timeline") > describe("Edge Cases")."""

    def test_should_handle_zero_duration(self):
        """Maps to it("should handle zero duration")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 0})

        timeline.play()
        engine.update(1)

        assert target["x"] == 100

    def test_should_handle_negative_delta_time_gracefully(self):
        """Maps to it("should handle negative deltaTime gracefully")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 1000})

        timeline.play()
        engine.update(-100)

        assert target["x"] == 0

    def test_should_handle_very_large_delta_time(self):
        """Maps to it("should handle very large deltaTime")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 1000})

        timeline.play()
        engine.update(10000)

        assert target["x"] == 100


class TestTimelineNewEasingFunctionTests:
    """Maps to describe("Timeline") > describe("New Easing Function Tests")."""

    @pytest.mark.parametrize(
        "ease_name,mid_value",
        [
            ("inCirc", 0.13397459621556135),
            ("outCirc", 0.8660254037844386),
            ("inOutCirc", 0.5),
            ("inBack", -0.0876975),
            ("outBack", 1.0876975),
            ("inOutBack", 0.5),
        ],
    )
    def test_should_animate_correctly_with_easing(self, ease_name, mid_value):
        """Maps to it("should animate correctly with <ease_name> easing")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(target, {"x": 100, "duration": 1000, "ease": ease_name})
        timeline.play()

        engine.update(0)
        assert target["x"] == pytest.approx(0, abs=1e-5)

        engine.update(500)
        if ease_name in ("inBack",) or ease_name in ("outBack",):
            assert target["x"] == pytest.approx(100 * mid_value, abs=1e-5)
        elif ease_name in ("inOutCirc", "inOutBack"):
            assert target["x"] == pytest.approx(50, abs=1e-5)
        else:
            assert target["x"] == pytest.approx(100 * mid_value, abs=1e-5)

        engine.update(500)
        assert target["x"] == pytest.approx(100, abs=1e-5)


class TestTimelineDeltaTimeInOnUpdateCallbacks:
    """Maps to describe("Timeline") > describe("DeltaTime in onUpdate Callbacks")."""

    def test_should_provide_correct_delta_time_to_on_update_callbacks(self):
        """Maps to it("should provide correct deltaTime to onUpdate callbacks")."""
        target = {"x": 0, "y": 0, "value": 0}
        delta_times_received: list[float] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "on_update": lambda anim: delta_times_received.append(anim.delta_time),
            },
        )

        timeline.play()

        engine.update(16)
        assert delta_times_received[0] == 16

        engine.update(33)
        assert delta_times_received[1] == 33

        engine.update(50)
        assert delta_times_received[2] == 50

    def test_should_support_throttling_patterns_like_the_vignette_example(self):
        """Maps to it("should support throttling patterns like the vignette example")."""
        target = {"x": 0, "y": 0, "value": 0, "strength": 0}

        vignette_time = [0.0]
        vignette_update_count = [0]
        vignette_strength_values: list[float] = []

        timeline = create_timeline(duration=2000, autoplay=False)
        timeline.add(
            target,
            {
                "strength": 1.0,
                "duration": 1000,
                "on_update": lambda values: _vignette_throttle(
                    values, vignette_time, vignette_update_count, vignette_strength_values
                ),
            },
        )

        timeline.play()

        for _ in range(10):
            engine.update(16.67)

        assert vignette_update_count[0] > 0
        assert vignette_update_count[0] < 10
        assert len(vignette_strength_values) == vignette_update_count[0]

    def test_should_provide_delta_time_across_multiple_animation_loops(self):
        """Maps to it("should provide deltaTime across multiple animation loops")."""
        target = {"x": 0, "y": 0, "value": 0}
        delta_times_received: list[float] = []

        timeline = create_timeline(duration=5000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "loop": 3,
                "loop_delay": 100,
                "on_update": lambda anim: delta_times_received.append(anim.delta_time),
            },
        )

        timeline.play()

        engine.update(25)
        engine.update(30)
        engine.update(445)
        engine.update(35)
        engine.update(65)
        engine.update(40)

        assert delta_times_received == [25, 30, 445, 35, 65, 40]

    def test_should_provide_delta_time_to_synced_sub_timeline_animations(self):
        """Maps to it("should provide deltaTime to synced sub-timeline animations")."""
        target = {"x": 0, "y": 0, "value": 0}
        main_delta_times: list[float] = []
        sub_delta_times: list[float] = []

        sub_target = {"value": 0}

        main_timeline = create_timeline(duration=2000, autoplay=False)
        sub_timeline = create_timeline(duration=500, autoplay=False)

        main_timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "on_update": lambda anim: main_delta_times.append(anim.delta_time),
            },
        )

        sub_timeline.add(
            sub_target,
            {
                "value": 50,
                "duration": 500,
                "on_update": lambda anim: sub_delta_times.append(anim.delta_time),
            },
        )

        main_timeline.sync(sub_timeline, 300)
        main_timeline.play()

        engine.update(200)
        assert main_delta_times == [200]
        assert sub_delta_times == []

        engine.update(150)
        assert main_delta_times == [200, 150]
        assert sub_delta_times == [50]

        engine.update(100)
        assert main_delta_times == [200, 150, 100]
        assert sub_delta_times == [50, 100]

    def test_should_handle_delta_time_correctly_when_animation_starts_mid_frame(self):
        """Maps to it("should handle deltaTime correctly when animation starts mid-frame")."""
        target = {"x": 0, "y": 0, "value": 0}
        delta_times_received: list[float] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "on_update": lambda anim: delta_times_received.append(anim.delta_time),
            },
            250,
        )

        timeline.play()

        engine.update(200)
        assert delta_times_received == []

        engine.update(100)
        assert delta_times_received == [100]

        engine.update(150)
        assert delta_times_received == [100, 150]

    def test_should_provide_correct_delta_time_for_zero_duration_animations(self):
        """Maps to it("should provide correct deltaTime for zero duration animations")."""
        target = {"x": 0, "y": 0, "value": 0}
        delta_times_received: list[float] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 0,
                "on_update": lambda anim: delta_times_received.append(anim.delta_time),
            },
        )

        timeline.play()

        engine.update(50)
        assert delta_times_received == [50]
        assert target["x"] == 100

        engine.update(25)
        assert delta_times_received == [50]

    def test_should_provide_consistent_delta_time_during_alternating_animations(self):
        """Maps to it("should provide consistent deltaTime during alternating animations")."""
        target = {"x": 0, "y": 0, "value": 0}
        delta_times_received: list[float] = []
        progress_values: list[float] = []

        timeline = create_timeline(duration=3000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "loop": 2,
                "alternate": True,
                "on_update": lambda anim: (
                    delta_times_received.append(anim.delta_time),
                    progress_values.append(anim.progress),
                ),
            },
        )

        timeline.play()

        engine.update(250)
        engine.update(250)

        engine.update(125)
        engine.update(375)

        assert delta_times_received == [250, 250, 125, 375]

        assert progress_values[0] == 0.5
        assert progress_values[1] == 1
        assert progress_values[2] == 0.25
        assert progress_values[3] == 1


class TestTimelineOnUpdateCallbackFrequencyAndCorrectness:
    """Maps to describe("Timeline") > describe("onUpdate Callback Frequency and Correctness")."""

    def test_should_provide_correct_progress_values_in_on_update_callbacks(self):
        """Maps to it("should provide correct progress values in onUpdate callbacks")."""
        target = {"x": 0, "y": 0, "value": 0}
        progress_values: list[float] = []
        target_values: list[float] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "ease": "linear",
                "on_update": lambda anim: (
                    progress_values.append(anim.progress),
                    target_values.append(anim.targets[0]["x"]),
                ),
            },
        )

        timeline.play()

        engine.update(0)
        engine.update(250)
        engine.update(250)
        engine.update(250)
        engine.update(250)

        assert progress_values == [0, 0.25, 0.5, 0.75, 1]
        assert target_values == [0, 25, 50, 75, 100]

    def test_should_call_on_update_for_each_animation_in_a_looping_scenario_without_duplicates(
        self,
    ):
        """Maps to it("should call onUpdate for each animation in a looping scenario without duplicates")."""
        target = {"x": 0, "y": 0, "value": 0}
        update_count = [0]
        progress_history: list[float] = []

        timeline = create_timeline(duration=3000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "loop": 3,
                "on_update": lambda anim: (
                    update_count.__setitem__(0, update_count[0] + 1),
                    progress_history.append(anim.progress),
                ),
            },
        )

        timeline.play()

        engine.update(250)
        engine.update(250)

        engine.update(250)
        engine.update(250)

        engine.update(250)
        engine.update(250)

        assert update_count[0] == 6
        assert progress_history == [0.5, 1, 0.5, 1, 0.5, 1]

    def test_should_call_on_update_correctly_for_alternating_animations(self):
        """Maps to it("should call onUpdate correctly for alternating animations")."""
        target = {"x": 0, "y": 0, "value": 0}
        update_count = [0]
        target_value_history: list[float] = []
        progress_history: list[float] = []

        timeline = create_timeline(duration=3000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "loop": 3,
                "alternate": True,
                "on_update": lambda anim: (
                    update_count.__setitem__(0, update_count[0] + 1),
                    target_value_history.append(anim.targets[0]["x"]),
                    progress_history.append(anim.progress),
                ),
            },
        )

        timeline.play()

        engine.update(250)
        engine.update(250)

        engine.update(250)
        engine.update(250)

        engine.update(250)
        engine.update(250)

        assert update_count[0] == 6
        assert target_value_history == [50, 100, 50, 0, 50, 100]
        assert progress_history == [0.5, 1, 0.5, 1, 0.5, 1]

    def test_should_provide_correct_delta_time_and_timing_information_in_on_update(self):
        """Maps to it("should provide correct deltaTime and timing information in onUpdate")."""
        target = {"x": 0, "y": 0, "value": 0}
        delta_time_history: list[float] = []
        current_time_history: list[float] = []

        timeline = create_timeline(duration=2000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 1000,
                "on_update": lambda anim: (
                    delta_time_history.append(anim.delta_time),
                    current_time_history.append(anim.current_time),
                ),
            },
            300,
        )

        timeline.play()

        engine.update(200)
        assert delta_time_history == []

        engine.update(150)
        engine.update(200)
        engine.update(300)
        engine.update(450)

        assert delta_time_history == [150, 200, 300, 450]
        assert current_time_history == [350, 550, 850, 1300]

    def test_should_not_call_on_update_multiple_times_for_zero_duration_animations(self):
        """Maps to it("should not call onUpdate multiple times for zero duration animations")."""
        target = {"x": 0, "y": 0, "value": 0}
        update_count = [0]
        received_values: list[JSAnimation] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 0,
                "on_update": lambda anim: (
                    update_count.__setitem__(0, update_count[0] + 1),
                    received_values.append(anim),
                ),
            },
        )

        timeline.play()

        engine.update(50)
        engine.update(100)
        engine.update(200)

        assert update_count[0] == 1
        assert received_values[0].progress == 1
        assert received_values[0].targets[0]["x"] == 100

    def test_should_not_call_on_update_after_animation_completes(self):
        """Maps to it("should not call onUpdate after animation completes")."""
        target = {"x": 0, "y": 0, "value": 0}
        update_call_count = [0]
        complete_call_count = [0]
        update_times: list[float] = []

        timeline = create_timeline(duration=2000, autoplay=False)
        timeline.add(
            target,
            {
                "x": 100,
                "duration": 500,
                "on_update": lambda anim: (
                    update_call_count.__setitem__(0, update_call_count[0] + 1),
                    update_times.append(timeline.current_time),
                ),
                "on_complete": lambda: complete_call_count.__setitem__(
                    0, complete_call_count[0] + 1
                ),
            },
        )

        timeline.play()

        engine.update(250)
        assert update_call_count[0] == 1
        assert complete_call_count[0] == 0
        assert target["x"] == 50

        engine.update(250)
        assert update_call_count[0] == 2
        assert complete_call_count[0] == 1
        assert target["x"] == 100

        engine.update(300)
        engine.update(400)
        engine.update(500)

        assert update_call_count[0] == 2
        assert complete_call_count[0] == 1
        assert target["x"] == 100

        assert update_times == [250, 500]

    def test_should_call_on_update_for_multiple_targets_on_same_animation_correctly(self):
        """Maps to it("should call onUpdate for multiple targets on same animation correctly")."""
        target1 = {"x": 0, "y": 0}
        target2 = {"x": 0, "y": 0}
        update_count = [0]
        all_targets_history: list[list[dict]] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            [target1, target2],
            {
                "x": 100,
                "y": 200,
                "duration": 1000,
                "on_update": lambda anim: (
                    update_count.__setitem__(0, update_count[0] + 1),
                    all_targets_history.append([{"x": t["x"], "y": t["y"]} for t in anim.targets]),
                ),
            },
        )

        timeline.play()

        engine.update(500)
        engine.update(500)

        assert update_count[0] == 2

        assert all_targets_history[0] == [
            {"x": 50, "y": 100},
            {"x": 50, "y": 100},
        ]

        assert all_targets_history[1] == [
            {"x": 100, "y": 200},
            {"x": 100, "y": 200},
        ]


class TestTimelineTargetValuePersistenceBug:
    """Maps to describe("Timeline") > describe("Target Value Persistence Bug")."""

    def test_should_not_reset_target_values_to_initial_values_when_animation_hasnt_started(self):
        """Maps to it("should not reset target values to initial values when animation hasnt started")."""
        test_target = {"x": 50, "strength": 1.5}

        test_target["x"] = 75
        test_target["strength"] = 2.0

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            test_target,
            {
                "x": 100,
                "duration": 300,
            },
            500,
        )

        timeline.play()

        engine.update(100)

        assert test_target["x"] == 75
        assert test_target["strength"] == 2.0

        engine.update(200)
        assert test_target["x"] == 75
        assert test_target["strength"] == 2.0

        engine.update(300)
        assert test_target["x"] == pytest.approx(83.33, abs=0.01)
        assert test_target["strength"] == 2.0

    def test_should_not_reset_target_values_to_initial_values_after_on_update(self):
        """Maps to it("should not reset target values to initial values after onUpdate")."""
        test_target = {"x": 0, "y": 50}
        on_update_call_count = [0]
        captured_values: list[dict] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            test_target,
            {
                "x": 100,
                "duration": 500,
                "on_update": lambda anim: (
                    on_update_call_count.__setitem__(0, on_update_call_count[0] + 1),
                    captured_values.append({"x": test_target["x"], "y": test_target["y"]}),
                ),
            },
        )

        timeline.play()

        engine.update(250)
        assert on_update_call_count[0] == 1
        assert test_target["x"] == 50
        assert test_target["y"] == 50

        engine.update(250)
        assert on_update_call_count[0] == 2
        assert test_target["x"] == 100
        assert test_target["y"] == 50

        engine.update(100)
        engine.update(100)
        engine.update(100)

        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert on_update_call_count[0] == 2

        assert captured_values[0] == {"x": 50, "y": 50}
        assert captured_values[1] == {"x": 100, "y": 50}

    def test_should_preserve_final_values_across_timeline_loops(self):
        """Maps to it("should preserve final values across timeline loops")."""
        test_target = {"value": 0}
        update_call_count = [0]

        timeline = create_timeline(duration=1000, loop=True, autoplay=False)
        timeline.add(
            test_target,
            {
                "value": 100,
                "duration": 600,
                "on_update": lambda _: update_call_count.__setitem__(0, update_call_count[0] + 1),
            },
        )

        timeline.play()

        engine.update(600)
        assert test_target["value"] == 100
        assert update_call_count[0] == 1

        engine.update(400)

        assert test_target["value"] == 100
        assert update_call_count[0] == 1

        engine.update(300)
        assert test_target["value"] == 50
        assert update_call_count[0] == 2

    def test_should_preserve_original_initial_values_across_timeline_loops(self):
        """Maps to it("should preserve original initial values across timeline loops")."""
        test_target = {"value": 0}
        update_call_count = [0]

        timeline = create_timeline(duration=1000, loop=True, autoplay=False)
        timeline.add(
            test_target,
            {
                "value": 100,
                "duration": 600,
                "on_update": lambda _: update_call_count.__setitem__(0, update_call_count[0] + 1),
            },
        )

        timeline.play()

        engine.update(600)
        assert test_target["value"] == 100
        assert update_call_count[0] == 1

        engine.update(400)

        assert test_target["value"] == 100
        assert update_call_count[0] == 1

        engine.update(300)
        assert test_target["value"] == 50
        assert update_call_count[0] == 2


class TestTimelineMultipleAnimationsOnSameObject:
    """Maps to describe("Timeline") > describe("Multiple Animations on Same Object")."""

    def test_should_handle_multiple_animations_on_the_same_object(self):
        """Maps to it("should handle multiple animations on the same object")."""
        test_target = {"x": 0}

        timeline = create_timeline(duration=5000, autoplay=False)
        timeline.add(test_target, {"x": 100, "duration": 100}, 0)
        timeline.add(test_target, {"x": 50, "duration": 100}, 200)

        timeline.play()

        assert test_target["x"] == 0

        engine.update(50)
        assert test_target["x"] == 50

        engine.update(50)
        assert test_target["x"] == 100

        engine.update(50)
        assert test_target["x"] == 100

        engine.update(100)
        assert test_target["x"] == 75

        engine.update(50)
        assert test_target["x"] == 50

    def test_should_handle_multiple_sequential_animations_on_the_same_object(self):
        """Maps to it("should handle multiple sequential animations on the same object")."""
        test_target = {"x": 0, "y": 0, "z": 0}
        animation_states: list[dict] = []

        timeline = create_timeline(duration=5000, autoplay=False)

        timeline.add(
            test_target,
            {
                "x": 100,
                "duration": 1000,
                "on_update": lambda _: animation_states.append(
                    {
                        "time": timeline.current_time,
                        "x": test_target["x"],
                        "y": test_target["y"],
                        "z": test_target["z"],
                    }
                ),
            },
            0,
        )

        timeline.add(
            test_target,
            {
                "y": 50,
                "duration": 500,
                "on_update": lambda _: animation_states.append(
                    {
                        "time": timeline.current_time,
                        "x": test_target["x"],
                        "y": test_target["y"],
                        "z": test_target["z"],
                    }
                ),
            },
            1500,
        )

        timeline.add(
            test_target,
            {
                "z": 200,
                "duration": 1000,
                "on_update": lambda _: animation_states.append(
                    {
                        "time": timeline.current_time,
                        "x": test_target["x"],
                        "y": test_target["y"],
                        "z": test_target["z"],
                    }
                ),
            },
            3000,
        )

        timeline.play()

        engine.update(0)
        assert test_target["x"] == 0
        assert test_target["y"] == 0
        assert test_target["z"] == 0

        engine.update(500)
        assert test_target["x"] == 50
        assert test_target["y"] == 0
        assert test_target["z"] == 0

        engine.update(500)
        assert test_target["x"] == 100
        assert test_target["y"] == 0
        assert test_target["z"] == 0

        engine.update(250)
        assert test_target["x"] == 100
        assert test_target["y"] == 0
        assert test_target["z"] == 0

        engine.update(250)
        assert test_target["x"] == 100
        assert test_target["y"] == 0
        assert test_target["z"] == 0

        engine.update(250)
        assert test_target["x"] == 100
        assert test_target["y"] == 25
        assert test_target["z"] == 0

        engine.update(250)
        engine.update(500)
        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert test_target["z"] == 0

        engine.update(500)
        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert test_target["z"] == 0

        engine.update(500)
        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert test_target["z"] == 100

        engine.update(500)
        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert test_target["z"] == 200

        engine.update(1000)
        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert test_target["z"] == 200

        assert len(animation_states) > 0

        engine.update(1000)
        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert test_target["z"] == 200

    def test_should_handle_overlapping_animations_on_different_properties(self):
        """Maps to it("should handle overlapping animations on different properties")."""
        test_target = {"x": 0, "y": 0, "scale": 1}

        timeline = create_timeline(duration=3000, autoplay=False)
        timeline.add(test_target, {"x": 100, "duration": 1000}, 0)
        timeline.add(test_target, {"y": 50, "duration": 1000}, 500)
        timeline.add(test_target, {"scale": 2, "duration": 1000}, 800)

        timeline.play()

        engine.update(600)
        assert test_target["x"] == 60
        assert test_target["y"] == 5
        assert test_target["scale"] == 1

        engine.update(400)
        assert test_target["x"] == 100
        assert test_target["y"] == 25
        assert test_target["scale"] == pytest.approx(1.2)

        engine.update(600)
        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert test_target["scale"] == pytest.approx(1.8)

        engine.update(400)
        assert test_target["x"] == 100
        assert test_target["y"] == 50
        assert test_target["scale"] == 2

    def test_should_handle_multiple_animations_with_different_easing_functions(self):
        """Maps to it("should handle multiple animations with different easing functions")."""
        test_target = {"a": 0, "b": 0, "c": 0}

        timeline = create_timeline(duration=3000, autoplay=False)
        timeline.add(test_target, {"a": 100, "duration": 1000, "ease": "linear"}, 0)
        timeline.add(test_target, {"b": 100, "duration": 1000, "ease": "inQuad"}, 500)
        timeline.add(test_target, {"c": 100, "duration": 1000, "ease": "inExpo"}, 1000)

        timeline.play()

        engine.update(500)
        assert test_target["a"] == 50
        assert test_target["b"] == 0
        assert test_target["c"] == 0

        engine.update(500)
        assert test_target["a"] == 100
        assert test_target["b"] == 25
        assert test_target["c"] == 0

        engine.update(500)
        assert test_target["a"] == 100
        assert test_target["b"] == 100
        assert test_target["c"] > 0
        assert test_target["c"] < 50

        engine.update(500)
        assert test_target["a"] == 100
        assert test_target["b"] == 100
        assert test_target["c"] == 100


class TestTimelineJSAnimationTargetsArrayHandling:
    """Maps to describe("Timeline") > describe("JSAnimation targets Array Handling")."""

    def test_should_provide_single_target_as_targets_0_in_on_update_callback(self):
        """Maps to it("should provide single target as targets[0] in onUpdate callback")."""
        brightness_effect = {"brightness": 0.5}
        captured_targets: list[list] = []
        captured_values: list[float] = []

        timeline = create_timeline(duration=2000, autoplay=False)
        timeline.add(
            brightness_effect,
            {
                "brightness": 1.0,
                "ease": "linear",
                "duration": 1000,
                "on_update": lambda values: (
                    captured_targets.append(list(values.targets)),
                    captured_values.append(values.targets[0]["brightness"]),
                ),
            },
        )

        timeline.play()

        engine.update(250)
        assert captured_values[0] == 0.625
        assert len(captured_targets[0]) == 1
        assert captured_targets[0][0]["brightness"] == 0.625

        engine.update(250)
        assert captured_values[1] == 0.75
        assert captured_targets[1][0]["brightness"] == 0.75

        engine.update(500)
        assert captured_values[2] == 1.0
        assert captured_targets[2][0]["brightness"] == 1.0

        assert brightness_effect["brightness"] == 1.0

    def test_should_provide_multiple_targets_correctly_in_targets_array(self):
        """Maps to it("should provide multiple targets correctly in targets array")."""
        effect1 = {"intensity": 0.0}
        effect2 = {"intensity": 0.0}
        captured_targets: list[list] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            [effect1, effect2],
            {
                "intensity": 2.0,
                "ease": "linear",
                "duration": 500,
                "on_update": lambda values: captured_targets.append(list(values.targets)),
            },
        )

        timeline.play()

        engine.update(250)
        assert len(captured_targets[0]) == 2
        assert captured_targets[0][0]["intensity"] == 1.0
        assert captured_targets[0][1]["intensity"] == 1.0

        engine.update(250)
        assert len(captured_targets[1]) == 2
        assert captured_targets[1][0]["intensity"] == 2.0
        assert captured_targets[1][1]["intensity"] == 2.0

        assert effect1["intensity"] == 2.0
        assert effect2["intensity"] == 2.0

    def test_should_provide_targets_with_complex_object_properties(self):
        """Maps to it("should provide targets with complex object properties")."""
        post_process_effect = {
            "brightness": 0.8,
            "contrast": 1.0,
            "saturation": 0.9,
            "vignette": {"strength": 0.2},
        }

        logged_values: list[dict] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            post_process_effect,
            {
                "brightness": 1.2,
                "contrast": 1.5,
                "saturation": 1.1,
                "ease": "outExpo",
                "duration": 500,
                "on_update": lambda values: logged_values.append(
                    {
                        "brightness": values.targets[0]["brightness"],
                        "contrast": values.targets[0]["contrast"],
                        "saturation": values.targets[0]["saturation"],
                    }
                ),
            },
        )

        timeline.play()

        engine.update(100)
        engine.update(200)
        engine.update(200)

        assert len(logged_values) == 3

        assert logged_values[0]["brightness"] > 1.0
        assert logged_values[0]["contrast"] > 1.2
        assert logged_values[0]["saturation"] > 1.0

        assert logged_values[2]["brightness"] == 1.2
        assert logged_values[2]["contrast"] == 1.5
        assert logged_values[2]["saturation"] == 1.1

        assert post_process_effect["vignette"]["strength"] == 0.2

        assert post_process_effect["brightness"] == 1.2
        assert post_process_effect["contrast"] == 1.5
        assert post_process_effect["saturation"] == 1.1

    def test_should_maintain_targets_array_consistency_with_different_animation_properties(self):
        """Maps to it("should maintain targets array consistency with different animation properties")."""
        multi_prop_target = {"x": 0, "y": 0, "z": 0, "scale": 1, "rotation": 0}
        all_captured_states: list[dict] = []

        timeline = create_timeline(duration=2000, autoplay=False)
        timeline.add(
            multi_prop_target,
            {
                "x": 100,
                "scale": 2,
                "rotation": 360,
                "ease": "linear",
                "duration": 1000,
                "on_update": lambda values: all_captured_states.append(dict(values.targets[0])),
            },
        )

        timeline.play()

        engine.update(500)
        engine.update(500)

        assert len(all_captured_states) == 2

        assert all_captured_states[0]["x"] == 50
        assert all_captured_states[0]["scale"] == 1.5
        assert all_captured_states[0]["rotation"] == 180
        assert all_captured_states[0]["y"] == 0
        assert all_captured_states[0]["z"] == 0

        assert all_captured_states[1]["x"] == 100
        assert all_captured_states[1]["scale"] == 2
        assert all_captured_states[1]["rotation"] == 360
        assert all_captured_states[1]["y"] == 0
        assert all_captured_states[1]["z"] == 0

        assert multi_prop_target["x"] == 100
        assert multi_prop_target["scale"] == 2
        assert multi_prop_target["rotation"] == 360
        assert multi_prop_target["y"] == 0
        assert multi_prop_target["z"] == 0

    def test_should_handle_class_instances_with_getter_setter_properties(self):
        """Maps to it("should handle class instances with getter/setter properties")."""

        class TestEffect:
            def __init__(self):
                self._brightness = 1.0
                self._contrast = 1.0

            @property
            def brightness(self):
                return self._brightness

            @brightness.setter
            def brightness(self, value):
                self._brightness = value

            @property
            def contrast(self):
                return self._contrast

            @contrast.setter
            def contrast(self, value):
                self._contrast = value

        effect_instance = TestEffect()
        captured_values: list[dict] = []

        timeline = create_timeline(duration=1000, autoplay=False)
        timeline.add(
            effect_instance,
            {
                "brightness": 2.0,
                "contrast": 1.5,
                "ease": "linear",
                "duration": 500,
                "on_update": lambda values: captured_values.append(
                    {
                        "brightness": values.targets[0].brightness,
                        "contrast": values.targets[0].contrast,
                    }
                ),
            },
        )

        timeline.play()

        engine.update(250)
        engine.update(250)

        assert len(captured_values) == 2

        assert captured_values[0]["brightness"] == 1.5
        assert captured_values[0]["contrast"] == 1.25

        assert captured_values[1]["brightness"] == 2.0
        assert captured_values[1]["contrast"] == 1.5

        assert effect_instance.brightness == 2.0
        assert effect_instance.contrast == 1.5


class TestTimelineScene00ReproductionBug:
    """Maps to describe("Timeline") > describe("Scene00 Reproduction Bug")."""

    def test_should_execute_callbacks_at_position_0_again_when_timeline_loops(self):
        """Maps to it("should execute callbacks at position 0 again when timeline loops")."""
        callback_execution_count = [0]
        reset_value = {"x": 0}

        timeline = create_timeline(duration=1000, loop=True, autoplay=False)

        timeline.call(
            lambda: (
                callback_execution_count.__setitem__(0, callback_execution_count[0] + 1),
                reset_value.__setitem__("x", 0),
            ),
            0,
        )

        timeline.add(reset_value, {"x": 100, "duration": 500}, 200)

        timeline.play()

        engine.update(0)
        assert callback_execution_count[0] == 1
        assert reset_value["x"] == 0

        engine.update(200)
        assert reset_value["x"] == 0

        engine.update(250)
        assert reset_value["x"] == 50

        engine.update(575)
        assert timeline.current_time == 25

        assert callback_execution_count[0] == 2
        assert reset_value["x"] == 0

        engine.update(175)
        assert reset_value["x"] == 0

        engine.update(250)
        assert reset_value["x"] == 50


class TestTimelineTopLevel:
    """Maps to top-level it() calls directly under describe("Timeline")."""

    def test_should_execute_callbacks_at_position_0_again_when_timeline_loops_top_level(self):
        """Maps to it("should execute callbacks at position 0 again when timeline loops") (top-level)."""
        callback_execution_count = [0]
        reset_value = {"x": 0}

        timeline = create_timeline(duration=1000, loop=True, autoplay=False)

        timeline.call(
            lambda: (
                callback_execution_count.__setitem__(0, callback_execution_count[0] + 1),
                reset_value.__setitem__("x", 0),
            ),
            0,
        )

        timeline.add(reset_value, {"x": 100, "duration": 500}, 200)

        timeline.play()

        engine.update(0)
        assert callback_execution_count[0] == 1
        assert reset_value["x"] == 0

        engine.update(200)
        assert reset_value["x"] == 0

        engine.update(250)
        assert reset_value["x"] == 50

        engine.update(575)
        assert timeline.current_time == 25

        assert callback_execution_count[0] == 2
        assert reset_value["x"] == 0

        engine.update(175)
        assert reset_value["x"] == 0

        engine.update(250)
        assert reset_value["x"] == 50

    def test_should_execute_callbacks_at_position_0_again_when_nested_sub_timeline_loops(self):
        """Maps to it("should execute callbacks at position 0 again when nested sub-timeline loops")."""
        main_timeline = create_timeline(duration=3000, loop=False, autoplay=False)
        sub_timeline = create_timeline(duration=1000, loop=True, autoplay=False)

        callback_execution_count = [0]
        reset_value = {"x": 0}

        sub_timeline.call(
            lambda: (
                callback_execution_count.__setitem__(0, callback_execution_count[0] + 1),
                reset_value.__setitem__("x", 0),
            ),
            0,
        )

        sub_timeline.add(reset_value, {"x": 100, "duration": 500}, 200)

        main_timeline.sync(sub_timeline, 500)
        main_timeline.play()

        engine.update(400)
        assert callback_execution_count[0] == 0
        assert reset_value["x"] == 0

        engine.update(100)
        assert callback_execution_count[0] == 1
        assert reset_value["x"] == 0

        engine.update(200)
        assert reset_value["x"] == 0

        engine.update(250)
        assert reset_value["x"] == 50

        engine.update(550)
        engine.update(25)

        assert callback_execution_count[0] == 2
        assert reset_value["x"] == 0

        engine.update(200)
        assert reset_value["x"] == 5

        engine.update(225)
        assert reset_value["x"] == 50

    def test_should_restart_animations_at_position_0_again_when_nested_sub_timeline_loops(self):
        """Maps to it("should restart animations at position 0 again when nested sub-timeline loops")."""
        main_timeline = create_timeline(duration=3000, loop=False, autoplay=False)
        sub_timeline = create_timeline(duration=1000, loop=True, autoplay=False)

        animation_target = {"value": 0}
        animation_start_count = [0]

        sub_timeline.add(
            animation_target,
            {
                "value": 100,
                "duration": 500,
                "on_start": lambda: animation_start_count.__setitem__(
                    0, animation_start_count[0] + 1
                ),
            },
            0,
        )

        main_timeline.sync(sub_timeline, 500)
        main_timeline.play()

        engine.update(400)
        assert animation_start_count[0] == 0
        assert animation_target["value"] == 0

        engine.update(100)
        assert animation_start_count[0] == 1
        assert animation_target["value"] == 0

        engine.update(250)
        assert animation_target["value"] == 50

        engine.update(250)
        assert animation_target["value"] == 100

        engine.update(500)
        engine.update(25)

        assert animation_start_count[0] == 2
        assert animation_target["value"] == 5

        engine.update(225)
        assert animation_target["value"] == 50

        engine.update(250)
        assert animation_target["value"] == 100


class TestTimelineOnComplete:
    """Maps to describe("Timeline") > describe("Timeline onComplete Callback")."""

    def test_should_call_on_complete_when_timeline_finishes_non_looping(self):
        """Maps to it("should call onComplete when timeline finishes (non-looping)")."""
        target = {"x": 0, "y": 0, "value": 0}
        complete_call_count = [0]

        timeline = create_timeline(
            duration=1000,
            loop=False,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 500})
        timeline.play()

        engine.update(500)
        assert complete_call_count[0] == 0
        assert timeline.is_playing is True

        engine.update(500)
        assert complete_call_count[0] == 1
        assert timeline.is_playing is False

        engine.update(1000)
        assert complete_call_count[0] == 1

    def test_should_not_call_on_complete_for_looping_timelines(self):
        """Maps to it("should not call onComplete for looping timelines")."""
        target = {"x": 0, "y": 0, "value": 0}
        complete_call_count = [0]

        timeline = create_timeline(
            duration=1000,
            loop=True,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 500})
        timeline.play()

        engine.update(1000)
        assert complete_call_count[0] == 0
        assert timeline.is_playing is True

        engine.update(1000)
        assert complete_call_count[0] == 0
        assert timeline.is_playing is True

        engine.update(2000)
        assert complete_call_count[0] == 0
        assert timeline.is_playing is True

    def test_should_call_on_complete_again_when_timeline_is_restarted_and_completes(self):
        """Maps to it("should call onComplete again when timeline is restarted and completes")."""
        target = {"x": 0, "y": 0, "value": 0}
        complete_call_count = [0]

        timeline = create_timeline(
            duration=1000,
            loop=False,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 800})
        timeline.play()

        engine.update(1000)
        assert complete_call_count[0] == 1
        assert timeline.is_playing is False

        timeline.restart()
        assert timeline.is_playing is True

        engine.update(1000)
        assert complete_call_count[0] == 2
        assert timeline.is_playing is False

    def test_should_not_call_on_complete_when_timeline_is_paused_before_completion(self):
        """Maps to it("should not call onComplete when timeline is paused before completion")."""
        target = {"x": 0, "y": 0, "value": 0}
        complete_call_count = [0]

        timeline = create_timeline(
            duration=1000,
            loop=False,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 800})
        timeline.play()

        engine.update(500)
        assert complete_call_count[0] == 0
        assert timeline.is_playing is True

        timeline.pause()
        engine.update(1000)
        assert complete_call_count[0] == 0
        assert timeline.is_playing is False

    def test_should_call_on_complete_when_playing_again_after_pause_reaches_completion(self):
        """Maps to it("should call onComplete when playing again after pause reaches completion")."""
        target = {"x": 0, "y": 0, "value": 0}
        complete_call_count = [0]

        timeline = create_timeline(
            duration=1000,
            loop=False,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 800})
        timeline.play()

        engine.update(500)
        timeline.pause()
        engine.update(1000)
        assert complete_call_count[0] == 0

        timeline.play()
        engine.update(500)
        assert complete_call_count[0] == 1
        assert timeline.is_playing is False

    def test_should_call_on_complete_with_correct_timing_when_timeline_has_overshoot(self):
        """Maps to it("should call onComplete with correct timing when timeline has overshoot")."""
        complete_call_count = [0]

        timeline = create_timeline(
            duration=1000,
            loop=False,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        target = {"x": 0, "y": 0, "value": 0}
        timeline.add(target, {"x": 100, "duration": 800})
        timeline.play()

        engine.update(1200)
        assert complete_call_count[0] == 1
        assert timeline.is_playing is False

    def test_should_work_correctly_with_synced_sub_timelines(self):
        """Maps to it("should work correctly with synced sub-timelines")."""
        target = {"x": 0, "y": 0, "value": 0}
        main_complete_count = [0]
        sub_complete_count = [0]

        main_timeline = create_timeline(
            duration=2000,
            loop=False,
            autoplay=False,
            on_complete=lambda: main_complete_count.__setitem__(0, main_complete_count[0] + 1),
        )

        sub_timeline = create_timeline(
            duration=1000,
            loop=False,
            autoplay=False,
            on_complete=lambda: sub_complete_count.__setitem__(0, sub_complete_count[0] + 1),
        )

        sub_target = {"value": 0}
        sub_timeline.add(sub_target, {"value": 100, "duration": 800})
        main_timeline.add(target, {"x": 50, "duration": 1500})

        main_timeline.sync(sub_timeline, 500)
        main_timeline.play()

        engine.update(1300)
        assert sub_complete_count[0] == 0
        assert main_complete_count[0] == 0
        assert main_timeline.is_playing is True

        engine.update(700)
        assert sub_complete_count[0] == 1
        assert main_complete_count[0] == 1
        assert main_timeline.is_playing is False

    def test_should_handle_on_complete_with_timeline_that_has_only_callbacks(self):
        """Maps to it("should handle onComplete with timeline that has only callbacks")."""
        complete_call_count = [0]
        callback_executed = [False]

        timeline = create_timeline(
            duration=500,
            loop=False,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )

        timeline.call(lambda: callback_executed.__setitem__(0, True), 200)
        timeline.play()

        engine.update(300)
        assert callback_executed[0] is True
        assert complete_call_count[0] == 0
        assert timeline.is_playing is True

        engine.update(200)
        assert complete_call_count[0] == 1
        assert timeline.is_playing is False

    def test_should_handle_on_complete_when_timeline_duration_is_shorter_than_animations(self):
        """Maps to it("should handle onComplete when timeline duration is shorter than animations")."""
        target = {"x": 0, "y": 0, "value": 0}
        complete_call_count = [0]

        timeline = create_timeline(
            duration=800,
            loop=False,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 1000})
        timeline.play()

        engine.update(800)
        assert complete_call_count[0] == 1
        assert timeline.is_playing is False
        assert target["x"] == 80

    def test_should_not_call_on_complete_multiple_times_on_same_completion(self):
        """Maps to it("should not call onComplete multiple times on same completion")."""
        target = {"x": 0, "y": 0, "value": 0}
        complete_call_count = [0]

        timeline = create_timeline(
            duration=500,
            loop=False,
            autoplay=False,
            on_complete=lambda: complete_call_count.__setitem__(0, complete_call_count[0] + 1),
        )
        timeline.add(target, {"x": 100, "duration": 300})
        timeline.play()

        engine.update(500)
        assert complete_call_count[0] == 1

        engine.update(100)
        engine.update(200)
        engine.update(500)
        assert complete_call_count[0] == 1


class TestTimelineOnceMethod:
    """Maps to describe("Timeline") > describe("Once Method")."""

    def test_should_execute_once_animation_immediately(self):
        """Maps to it("should execute once animation immediately")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=2000, autoplay=False)

        timeline.play()
        engine.update(500)

        assert target["x"] == 0
        assert len(timeline.items) == 0

        timeline.once(target, {"x": 100, "duration": 500})

        assert len(timeline.items) == 1
        assert target["x"] == 0

        engine.update(250)
        assert target["x"] == 50
        assert len(timeline.items) == 1

        engine.update(250)
        assert target["x"] == 100
        assert len(timeline.items) == 0

    def test_should_remove_once_animation_after_completion(self):
        """Maps to it("should remove once animation after completion")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=2000, autoplay=False)
        timeline.add(target, {"y": 50, "duration": 1000})
        timeline.play()

        engine.update(300)
        assert len(timeline.items) == 1

        timeline.once(target, {"x": 100, "duration": 200})
        assert len(timeline.items) == 2

        engine.update(200)
        assert target["x"] == 100
        assert target["y"] == 25
        assert len(timeline.items) == 1

        engine.update(500)
        assert target["y"] == 50
        assert len(timeline.items) == 1

        engine.update(200)
        assert target["y"] == 50
        assert len(timeline.items) == 1

    def test_should_not_re_execute_once_animation_when_timeline_loops(self):
        """Maps to it("should not re-execute once animation when timeline loops")."""
        target = {"x": 0, "y": 0, "value": 0}
        once_start_count = [0]
        once_complete_count = [0]

        timeline = create_timeline(duration=1000, loop=True, autoplay=False)

        timeline.play()
        engine.update(200)

        timeline.once(
            target,
            {
                "x": 100,
                "duration": 300,
                "on_start": lambda: once_start_count.__setitem__(0, once_start_count[0] + 1),
                "on_complete": lambda: once_complete_count.__setitem__(
                    0, once_complete_count[0] + 1
                ),
            },
        )

        assert len(timeline.items) == 1

        engine.update(300)
        assert target["x"] == 100
        assert once_start_count[0] == 1
        assert once_complete_count[0] == 1
        assert len(timeline.items) == 0

        engine.update(500)
        assert timeline.current_time == 0
        assert target["x"] == 100
        assert once_start_count[0] == 1
        assert once_complete_count[0] == 1
        assert len(timeline.items) == 0

    def test_should_handle_multiple_once_animations(self):
        """Maps to it("should handle multiple once animations")."""
        timeline = create_timeline(duration=2000, autoplay=False)

        timeline.play()
        engine.update(100)

        target1 = {"value": 0}
        target2 = {"value": 0}

        timeline.once(target1, {"value": 50, "duration": 200})
        timeline.once(target2, {"value": 100, "duration": 300})

        assert len(timeline.items) == 2

        engine.update(200)
        assert target1["value"] == 50
        assert target2["value"] == pytest.approx(66.67, abs=0.1)
        assert len(timeline.items) == 1

        engine.update(100)
        assert target1["value"] == 50
        assert target2["value"] == 100
        assert len(timeline.items) == 0

    def test_should_handle_once_animations_with_different_easing_functions(self):
        """Maps to it("should handle once animations with different easing functions")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)

        timeline.play()
        engine.update(200)

        timeline.once(target, {"x": 100, "duration": 400, "ease": "linear"})

        engine.update(200)
        assert target["x"] == 50

        engine.update(200)
        assert target["x"] == 100
        assert len(timeline.items) == 0

    def test_should_trigger_on_update_callbacks_for_once_animations(self):
        """Maps to it("should trigger onUpdate callbacks for once animations")."""
        target = {"x": 0, "y": 0, "value": 0}
        update_count = [0]
        progress_values: list[float] = []

        timeline = create_timeline(duration=1000, autoplay=False)

        timeline.play()
        engine.update(100)

        timeline.once(
            target,
            {
                "x": 100,
                "duration": 400,
                "on_update": lambda anim: (
                    update_count.__setitem__(0, update_count[0] + 1),
                    progress_values.append(anim.progress),
                ),
            },
        )

        engine.update(200)
        assert update_count[0] == 1
        assert progress_values[0] == 0.5

        engine.update(200)
        assert update_count[0] == 2
        assert progress_values[1] == 1
        assert len(timeline.items) == 0

    def test_should_handle_zero_duration_once_animations(self):
        """Maps to it("should handle zero duration once animations")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)

        timeline.play()
        engine.update(200)

        timeline.once(target, {"x": 100, "duration": 0})

        assert len(timeline.items) == 1

        engine.update(1)
        assert target["x"] == 100
        assert len(timeline.items) == 0

    def test_should_handle_once_animations_added_while_timeline_is_paused(self):
        """Maps to it("should handle once animations added while timeline is paused")."""
        target = {"x": 0, "y": 0, "value": 0}

        timeline = create_timeline(duration=1000, autoplay=False)

        timeline.play()
        engine.update(300)
        timeline.pause()

        timeline.once(target, {"x": 100, "duration": 200})

        assert len(timeline.items) == 1
        assert target["x"] == 0

        engine.update(100)
        assert target["x"] == 0
        assert len(timeline.items) == 1

        timeline.play()
        engine.update(100)
        assert target["x"] == 50

        engine.update(100)
        assert target["x"] == 100
        assert len(timeline.items) == 0


# ---------------------------------------------------------------------------
# Helper for throttle test
# ---------------------------------------------------------------------------


def _vignette_throttle(values, vignette_time, vignette_update_count, vignette_strength_values):
    vignette_time[0] += values.delta_time
    if vignette_time[0] > 66:
        vignette_strength_values.append(values.targets[0]["strength"])
        vignette_update_count[0] += 1
        vignette_time[0] = 0
