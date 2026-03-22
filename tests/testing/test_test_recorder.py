"""Tests for TestRecorder — ported from testing/test-recorder.test.ts (26 tests).

Upstream: reference/opentui/packages/core/src/testing/test-recorder.test.ts
"""

from __future__ import annotations

import asyncio

import pytest

from opentui import create_test_renderer
from opentui.components.text_renderable import TextRenderable
from opentui.testing.capture import TestRecorder


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def setup(event_loop):
    s = event_loop.run_until_complete(create_test_renderer(width=80, height=24))
    yield s
    s.destroy()


class TestRecorderTests:
    """TestRecorder — 26 tests."""

    def test_should_initialize_with_empty_frames(self, setup):
        recorder = TestRecorder(setup.renderer)
        assert recorder.recorded_frames == []
        assert recorder.is_recording is False

    def test_should_start_recording(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()
        assert recorder.is_recording is True
        recorder.stop()

    def test_should_stop_recording(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()
        assert recorder.is_recording is True
        recorder.stop()
        assert recorder.is_recording is False

    def test_should_record_frames_during_rendering(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Hello World")
        setup.renderer.root.add(text)
        setup.render_frame()

        assert len(recorder.recorded_frames) == 1

        setup.render_frame()
        assert len(recorder.recorded_frames) == 2

        recorder.stop()

    def test_should_capture_frame_content_correctly(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Test Content")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 1
        assert "Test Content" in frames[0].frame

        recorder.stop()

    def test_should_include_frame_metadata(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Frame Metadata")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 1
        assert frames[0].timestamp >= 0
        assert frames[0].frame_number == 0

        recorder.stop()

    def test_should_increment_frame_numbers(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Multiple Frames")
        setup.renderer.root.add(text)
        setup.render_frame()

        setup.render_frame()
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 3
        assert frames[0].frame_number == 0
        assert frames[1].frame_number == 1
        assert frames[2].frame_number == 2

        recorder.stop()

    def test_should_capture_changing_content_across_frames(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Initial")
        setup.renderer.root.add(text)
        setup.render_frame()

        text.content = "Changed"
        setup.render_frame()
        recorder.stop()

        frame1 = recorder.recorded_frames[0].frame
        frame2 = recorder.recorded_frames[1].frame

        assert "Initial" in frame1
        assert "Changed" in frame2
        assert frame1 != frame2

    def test_should_not_record_when_not_started(self, setup):
        recorder = TestRecorder(setup.renderer)
        text = TextRenderable(content="Not Recording")
        setup.renderer.root.add(text)
        setup.render_frame()

        assert len(recorder.recorded_frames) == 0

    def test_should_not_record_after_stopped(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Stopped")
        setup.renderer.root.add(text)
        setup.render_frame()

        assert len(recorder.recorded_frames) == 1

        recorder.stop()
        setup.render_frame()
        assert len(recorder.recorded_frames) == 1

    def test_should_clear_recorded_frames(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Clear Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        setup.render_frame()

        assert len(recorder.recorded_frames) == 2
        recorder.clear()
        assert len(recorder.recorded_frames) == 0

        recorder.stop()

    def test_should_handle_multiple_rec_stop_cycles(self, setup):
        recorder = TestRecorder(setup.renderer)
        text = TextRenderable(content="Cycle Test")

        recorder.rec()
        setup.renderer.root.add(text)
        setup.render_frame()
        recorder.stop()
        assert len(recorder.recorded_frames) == 1

        recorder.clear()
        recorder.rec()
        setup.render_frame()
        setup.render_frame()
        recorder.stop()
        assert len(recorder.recorded_frames) == 2

    def test_should_not_duplicate_frames_when_rec_called_multiple_times(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()
        recorder.rec()

        text = TextRenderable(content="Duplicate Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        recorder.stop()

        assert len(recorder.recorded_frames) == 1

    def test_should_restore_original_render_after_stop(self, setup):
        recorder = TestRecorder(setup.renderer)
        text = TextRenderable(content="Restore Test")

        recorder.rec()
        setup.renderer.root.add(text)
        setup.render_frame()
        recorder.stop()

        recorder.clear()
        setup.render_frame()
        assert len(recorder.recorded_frames) == 0

        recorder.rec()
        setup.render_frame()
        recorder.stop()
        assert len(recorder.recorded_frames) == 1

    def test_should_capture_timestamps_in_increasing_order(self, setup):
        time_val = 0

        def now():
            return time_val

        recorder = TestRecorder(setup.renderer, options={"now": now})
        recorder.rec()

        setup.render_frame()
        time_val = 10
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 2
        assert frames[1].timestamp > frames[0].timestamp
        assert frames[1].timestamp - frames[0].timestamp == 10

        recorder.stop()

    def test_should_return_a_copy_of_recorded_frames(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Copy Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames1 = recorder.recorded_frames
        frames2 = recorder.recorded_frames

        assert frames1 == frames2
        assert frames1 is not frames2

        recorder.stop()

    def test_should_handle_empty_renders(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()
        setup.render_frame()

        assert len(recorder.recorded_frames) == 1
        assert recorder.recorded_frames[0].frame is not None

        recorder.stop()

    def test_should_capture_complex_content(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text1 = TextRenderable(content="Line 1")
        text2 = TextRenderable(content="Line 2")
        setup.renderer.root.add(text1)
        setup.renderer.root.add(text2)
        setup.render_frame()

        frame = recorder.recorded_frames[0].frame
        assert "Line 1" in frame
        assert "Line 2" in frame

        recorder.stop()

    def test_should_handle_rapid_render_calls(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="Rapid Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        for _ in range(4):
            setup.render_frame()

        assert len(recorder.recorded_frames) == 5

        recorder.stop()

    def test_should_optionally_record_fg_buffer(self, setup):
        recorder = TestRecorder(setup.renderer, options={"record_buffers": {"fg": True}})
        recorder.rec()

        text = TextRenderable(content="Buffer Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 1
        assert frames[0].buffers is not None
        assert frames[0].buffers.fg is not None
        assert isinstance(frames[0].buffers.fg, list)
        assert frames[0].buffers.bg is None
        assert frames[0].buffers.attributes is None

        recorder.stop()

    def test_should_optionally_record_bg_buffer(self, setup):
        recorder = TestRecorder(setup.renderer, options={"record_buffers": {"bg": True}})
        recorder.rec()

        text = TextRenderable(content="Buffer Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 1
        assert frames[0].buffers is not None
        assert frames[0].buffers.bg is not None
        assert isinstance(frames[0].buffers.bg, list)
        assert frames[0].buffers.fg is None
        assert frames[0].buffers.attributes is None

        recorder.stop()

    def test_should_optionally_record_attributes_buffer(self, setup):
        recorder = TestRecorder(setup.renderer, options={"record_buffers": {"attributes": True}})
        recorder.rec()

        text = TextRenderable(content="Buffer Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 1
        assert frames[0].buffers is not None
        assert frames[0].buffers.attributes is not None
        assert isinstance(frames[0].buffers.attributes, list)
        assert frames[0].buffers.fg is None
        assert frames[0].buffers.bg is None

        recorder.stop()

    def test_should_record_multiple_buffers_when_requested(self, setup):
        recorder = TestRecorder(
            setup.renderer,
            options={
                "record_buffers": {"fg": True, "bg": True, "attributes": True},
            },
        )
        recorder.rec()

        text = TextRenderable(content="Buffer Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 1
        assert frames[0].buffers is not None
        assert frames[0].buffers.fg is not None
        assert frames[0].buffers.bg is not None
        assert frames[0].buffers.attributes is not None

        recorder.stop()

    def test_should_not_record_buffers_when_not_requested(self, setup):
        recorder = TestRecorder(setup.renderer)
        recorder.rec()

        text = TextRenderable(content="No Buffer Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 1
        assert frames[0].buffers is None

        recorder.stop()

    def test_should_record_independent_buffer_copies(self, setup):
        recorder = TestRecorder(setup.renderer, options={"record_buffers": {"fg": True}})
        recorder.rec()

        text = TextRenderable(content="Copy Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 2

        frame1_fg = frames[0].buffers.fg
        frame2_fg = frames[1].buffers.fg

        assert frame1_fg is not None
        assert frame2_fg is not None
        assert frame1_fg is not frame2_fg

        recorder.stop()

    def test_should_have_correct_buffer_sizes(self, setup):
        recorder = TestRecorder(
            setup.renderer,
            options={
                "record_buffers": {"fg": True, "bg": True, "attributes": True},
            },
        )
        recorder.rec()

        text = TextRenderable(content="Size Test")
        setup.renderer.root.add(text)
        setup.render_frame()

        frames = recorder.recorded_frames
        assert len(frames) == 1

        expected_size = setup.renderer.width * setup.renderer.height
        assert len(frames[0].buffers.fg) == expected_size * 4
        assert len(frames[0].buffers.bg) == expected_size * 4
        assert len(frames[0].buffers.attributes) == expected_size

        recorder.stop()
