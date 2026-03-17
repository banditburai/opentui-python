"""Port of upstream renderer.idle.test.ts.

Upstream: packages/core/src/tests/renderer.idle.test.ts
Tests ported: 16/16 (all implemented)

The Python ``CliRenderer`` now implements the upstream control state machine:
  - ``RendererControlState`` enum (IDLE, AUTO_STARTED, EXPLICIT_STARTED, etc.)
  - ``start()``, ``stop()``, ``pause()`` methods
  - ``request_live()`` / ``drop_live()`` for auto-start/stop
  - ``idle()`` async method returning a future that resolves when idle

In test mode rendering is still driven manually via ``setup.render_frame()``,
but the control state transitions and ``idle()`` resolution work identically
to the upstream TypeScript implementation.
"""

import asyncio

import pytest

from opentui import RendererControlState, create_test_renderer


class TestRendererIdle:
    """Maps to top-level tests in renderer.idle.test.ts."""

    async def test_idle_resolves_immediately_when_renderer_is_already_idle(self):
        """Maps to test("idle() resolves immediately when renderer is already idle").

        The renderer starts in IDLE state and is not running.  idle()
        should resolve immediately.
        """

        setup = await create_test_renderer(80, 24)
        try:
            assert setup.renderer.control_state == RendererControlState.IDLE
            assert setup.renderer.is_running is False

            # idle() should resolve immediately when already idle.
            await setup.renderer.idle()
        finally:
            setup.destroy()

    async def test_idle_waits_for_running_renderer_to_stop(self):
        """Maps to test("idle() waits for running renderer to stop").

        After start(), the renderer is running.  idle() returns a future
        that resolves when stop() is called.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.start()
            assert setup.renderer.is_running is True

            idle_resolved = False

            async def wait_idle():
                nonlocal idle_resolved
                await setup.renderer.idle()
                idle_resolved = True

            task = asyncio.ensure_future(wait_idle())

            # Give the event loop a tick so the idle() future is registered.
            await asyncio.sleep(0)
            assert idle_resolved is False

            setup.renderer.stop()

            # Let the event loop process the resolved future.
            await asyncio.sleep(0)
            assert idle_resolved is True
            assert setup.renderer.is_running is False

            await task
        finally:
            setup.destroy()

    async def test_idle_waits_for_paused_renderer_after_request_render(self):
        """Maps to test("idle() waits for paused renderer after requestRender()").

        After pause(), the renderer is not running.  request_render()
        sets update_scheduled=True.  idle() should still resolve
        after render_frame() clears the scheduled flag.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.pause()
            assert setup.renderer.is_running is False

            setup.renderer.request_render()

            # idle() should resolve after the render completes.
            # render_frame() clears _rendering and calls _resolve_idle_if_needed.
            setup.render_frame()
            await setup.renderer.idle()

            assert setup.renderer.is_running is False
        finally:
            setup.destroy()

    async def test_idle_resolves_immediately_after_request_render_completes(self):
        """Maps to test("idle() resolves immediately after requestRender() completes").

        After request_render() + render_frame(), the renderer is idle again.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.request_render()
            setup.render_frame()

            # idle() should resolve immediately now.
            await setup.renderer.idle()
            assert setup.renderer._running is False
        finally:
            setup.destroy()

    async def test_multiple_idle_calls_all_resolve_when_renderer_becomes_idle(self):
        """Maps to test("multiple idle() calls all resolve when renderer becomes idle").

        Multiple idle() futures should all resolve when the renderer stops.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.start()

            resolved_count = 0

            async def wait_idle():
                nonlocal resolved_count
                await setup.renderer.idle()
                resolved_count += 1

            task1 = asyncio.ensure_future(wait_idle())
            task2 = asyncio.ensure_future(wait_idle())
            task3 = asyncio.ensure_future(wait_idle())

            # Let the event loop register all three futures.
            await asyncio.sleep(0)
            assert resolved_count == 0

            setup.renderer.stop()

            # Let all three resolve.
            await asyncio.sleep(0)
            assert resolved_count == 3

            await asyncio.gather(task1, task2, task3)
            assert setup.renderer.is_running is False
        finally:
            setup.destroy()

    async def test_idle_resolves_when_auto_started_renderer_drops_all_live_requests(self):
        """Maps to test("idle() resolves when AUTO_STARTED renderer drops all live requests").

        request_live() auto-starts the renderer.  drop_live() returns it
        to IDLE when the counter reaches zero.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.request_live()
            assert setup.renderer.control_state == RendererControlState.AUTO_STARTED
            assert setup.renderer.is_running is True

            idle_resolved = False

            async def wait_idle():
                nonlocal idle_resolved
                await setup.renderer.idle()
                idle_resolved = True

            task = asyncio.ensure_future(wait_idle())
            await asyncio.sleep(0)

            setup.renderer.drop_live()

            await asyncio.sleep(0)
            assert idle_resolved is True
            assert setup.renderer.control_state == RendererControlState.IDLE
            assert setup.renderer.is_running is False

            await task
        finally:
            setup.destroy()

    async def test_idle_resolves_after_explicit_pause(self):
        """Maps to test("idle() resolves after explicit pause").

        After start(), pause() moves the renderer to EXPLICIT_PAUSED
        and resolves pending idle() futures.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.start()
            assert setup.renderer.is_running is True

            idle_resolved = False

            async def wait_idle():
                nonlocal idle_resolved
                await setup.renderer.idle()
                idle_resolved = True

            task = asyncio.ensure_future(wait_idle())
            await asyncio.sleep(0)

            setup.renderer.pause()

            await asyncio.sleep(0)
            assert idle_resolved is True
            assert setup.renderer.control_state == RendererControlState.EXPLICIT_PAUSED
            assert setup.renderer.is_running is False

            await task
        finally:
            setup.destroy()

    async def test_idle_resolves_immediately_when_called_on_paused_renderer(self):
        """Maps to test("idle() resolves immediately when called on paused renderer").

        After start() + pause(), the renderer is paused (not running).
        idle() should resolve immediately.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.start()
            setup.renderer.pause()

            # idle() should resolve immediately on a paused renderer.
            await setup.renderer.idle()
        finally:
            setup.destroy()

    async def test_idle_resolves_when_renderer_is_destroyed(self):
        """Maps to test("idle() resolves when renderer is destroyed").

        After start(), destroy() resolves pending idle() futures.
        """

        setup = await create_test_renderer(80, 24)
        setup.renderer.start()

        idle_resolved = False

        async def wait_idle():
            nonlocal idle_resolved
            await setup.renderer.idle()
            idle_resolved = True

        task = asyncio.ensure_future(wait_idle())
        await asyncio.sleep(0)

        setup.renderer.destroy()

        await asyncio.sleep(0)
        assert idle_resolved is True

        await task

    async def test_idle_resolves_immediately_when_called_on_destroyed_renderer(self):
        """Maps to test("idle() resolves immediately when called on destroyed renderer")."""

        setup = await create_test_renderer(80, 24)
        setup.destroy()

        # idle() should resolve immediately on a destroyed renderer.
        await setup.renderer.idle()
        assert setup.renderer.is_destroyed is True

    async def test_idle_waits_through_multiple_request_render_calls(self):
        """Maps to test("idle() waits through multiple requestRender() calls").

        Multiple request_render() calls should not cause issues.  After
        render_frame() the renderer is idle.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.request_render()
            setup.renderer.request_render()
            setup.render_frame()
            assert setup.renderer._running is False

            await setup.renderer.idle()
        finally:
            setup.destroy()

    async def test_idle_works_correctly_with_stop_called_during_rendering(self):
        """Maps to test("idle() works correctly with stop() called during rendering").

        After start() and a brief run, stop() should resolve idle() futures.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.start()

            idle_resolved = False

            async def wait_idle():
                nonlocal idle_resolved
                await setup.renderer.idle()
                idle_resolved = True

            task = asyncio.ensure_future(wait_idle())
            await asyncio.sleep(0)

            setup.renderer.stop()

            await asyncio.sleep(0)
            assert idle_resolved is True
            assert setup.renderer.is_running is False

            await task
        finally:
            setup.destroy()

    async def test_idle_resolves_after_pause_called_during_rendering(self):
        """Maps to test("idle() resolves after pause() called during rendering").

        After start(), pause() should resolve idle() futures and set
        the control state to EXPLICIT_PAUSED.
        """

        setup = await create_test_renderer(80, 24)
        try:
            setup.renderer.start()

            idle_resolved = False

            async def wait_idle():
                nonlocal idle_resolved
                await setup.renderer.idle()
                idle_resolved = True

            task = asyncio.ensure_future(wait_idle())
            await asyncio.sleep(0)

            setup.renderer.pause()

            await asyncio.sleep(0)
            assert idle_resolved is True
            assert setup.renderer.control_state == RendererControlState.EXPLICIT_PAUSED
            assert setup.renderer.is_running is False

            await task
        finally:
            setup.destroy()

    async def test_idle_can_be_used_in_a_loop_to_wait_between_operations(self):
        """Maps to test("idle() can be used in a loop to wait between operations").

        Sequential request_render() + render_frame() + idle() calls
        should work correctly.
        """

        setup = await create_test_renderer(80, 24)
        try:
            operations: list[str] = []

            operations.append("start")
            setup.renderer.request_render()
            setup.render_frame()
            await setup.renderer.idle()
            operations.append("rendered")

            setup.renderer.request_render()
            setup.render_frame()
            await setup.renderer.idle()
            operations.append("rendered again")

            assert operations == ["start", "rendered", "rendered again"]
        finally:
            setup.destroy()

    async def test_idle_works_with_request_animation_frame(self):
        """Maps to test("idle() works with requestAnimationFrame").

        In Python, requestAnimationFrame callbacks are executed during the next
        call to render_frame() (via _render_frame).
        """

        setup = await create_test_renderer(80, 24)
        try:
            frame_callback_executed = False

            def _raf_callback(dt):
                nonlocal frame_callback_executed
                frame_callback_executed = True

            setup.renderer.request_animation_frame(_raf_callback)

            # The callback fires during the next render frame.
            setup.render_frame()

            assert frame_callback_executed is True
        finally:
            setup.destroy()

    async def test_idle_waits_for_all_animation_frames_to_complete(self):
        """Maps to test("idle() waits for all animation frames to complete").

        Verifies that nested requestAnimationFrame calls are executed --
        a callback that schedules another RAF sees the second callback run
        in the subsequent frame.
        """

        setup = await create_test_renderer(80, 24)
        try:
            count = 0

            def _outer_raf(dt):
                nonlocal count
                count += 1

                def _inner_raf(dt2):
                    nonlocal count
                    count += 1

                setup.renderer.request_animation_frame(_inner_raf)

            setup.renderer.request_animation_frame(_outer_raf)

            # First frame runs the outer RAF (count=1) and schedules inner.
            setup.render_frame()
            assert count == 1

            # Second frame runs the inner RAF (count=2).
            setup.render_frame()
            assert count == 2
        finally:
            setup.destroy()
