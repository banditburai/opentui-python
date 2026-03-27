"""Port of upstream renderer.focus-restore.test.ts.

Upstream: packages/core/src/tests/renderer.focus-restore.test.ts
Tests ported: 11/11 (1 skipped — requires renderer.on("focus"/"blur") event
               emitter which is not in the Python testing infrastructure)

The upstream tests use ``renderer.stdin.emit("data", ...)`` to feed raw
escape sequences through the full input parser pipeline.  In Python these
are fed via ``setup.stdin.emit("data", ...)`` which drives the same
``TestInputHandler`` that ``run()`` would use.

Focus-in:  ``\\x1b[I``
Focus-out: ``\\x1b[O``

The ``_should_restore_modes`` / ``_restore_terminal_modes`` logic mirrors
upstream ``renderer.ts`` and is wired into ``TestSetup._ensure_stdin_input``.
In testing mode ``_restore_terminal_modes`` is a no-op (it would need a live
terminal), so we spy on it with ``unittest.mock.patch.object`` to count calls.
"""

import pytest
from unittest.mock import patch

from opentui import create_test_renderer


# Focus-in and focus-out escape sequences (CSI I / CSI O).
FOCUS_IN = "\x1b[I"
FOCUS_OUT = "\x1b[O"


class TestFocusRestoreTerminalModeReEnableOnFocusIn:
    """Maps to describe("focus restore - terminal mode re-enable on focus-in")."""

    async def test_restore_terminal_modes_is_not_called_on_focus_in_without_prior_blur(self):
        """Maps to test("restoreTerminalModes is NOT called on focus-in without prior blur")."""

        setup = await create_test_renderer(80, 24)
        try:
            with patch.object(setup.renderer, "_restore_terminal_modes") as mock_restore:
                # Trigger stdin input setup.
                _ = setup.stdin

                # Send focus-in without a preceding blur.
                setup.stdin.emit("data", FOCUS_IN)

                assert mock_restore.call_count == 0
        finally:
            setup.destroy()

    async def test_restore_terminal_modes_is_called_once_after_blur_then_focus_in(self):
        """Maps to test("restoreTerminalModes is called once after blur then focus-in")."""

        setup = await create_test_renderer(80, 24)
        try:
            with patch.object(setup.renderer, "_restore_terminal_modes") as mock_restore:
                _ = setup.stdin

                setup.stdin.emit("data", FOCUS_OUT)
                setup.stdin.emit("data", FOCUS_IN)

                assert mock_restore.call_count == 1
        finally:
            setup.destroy()

    async def test_restore_terminal_modes_is_not_called_on_blur_event(self):
        """Maps to test("restoreTerminalModes is NOT called on blur event")."""

        setup = await create_test_renderer(80, 24)
        try:
            with patch.object(setup.renderer, "_restore_terminal_modes") as mock_restore:
                _ = setup.stdin

                setup.stdin.emit("data", FOCUS_OUT)

                assert mock_restore.call_count == 0
        finally:
            setup.destroy()

    async def test_restore_terminal_modes_is_called_before_focus_event_is_emitted_after_blur(self):
        """Maps to test("restoreTerminalModes is called before focus event is emitted after blur").

        Verifies ordering: _restore_terminal_modes() must be called BEFORE any
        registered focus handlers fire on the focus-in event.
        """

        setup = await create_test_renderer(80, 24)
        try:
            call_order: list[str] = []

            # Patch _restore_terminal_modes to record its call position.
            original_restore = setup.renderer._restore_terminal_modes

            def _tracked_restore():
                call_order.append("restoreTerminalModes")
                original_restore()

            setup.renderer._restore_terminal_modes = _tracked_restore

            # Register a focus handler (via stdin's on_focus which is wired in _ensure_stdin_input).
            # We attach it as a hooks focus handler that records the "focus-event" call.
            from opentui import hooks

            def _focus_hook(focus_type: str) -> None:
                if focus_type == "focus":
                    call_order.append("focus-event")

            hooks.register_focus_handler(_focus_hook)
            try:
                _ = setup.stdin

                setup.stdin.emit("data", FOCUS_OUT)
                setup.stdin.emit("data", FOCUS_IN)

                # restoreTerminalModes should have been called before the focus event.
                assert call_order == ["restoreTerminalModes", "focus-event"]
            finally:
                hooks.unregister_focus_handler(_focus_hook)
        finally:
            setup.destroy()

    async def test_repeated_focus_in_events_only_restore_once_per_blur_cycle(self):
        """Maps to test("repeated focus-in events only restore once per blur cycle")."""

        setup = await create_test_renderer(80, 24)
        try:
            with patch.object(setup.renderer, "_restore_terminal_modes") as mock_restore:
                _ = setup.stdin

                setup.stdin.emit("data", FOCUS_OUT)

                # Multiple focus-in events should only trigger one restore per blur cycle.
                setup.stdin.emit("data", FOCUS_IN)
                setup.stdin.emit("data", FOCUS_IN)
                setup.stdin.emit("data", FOCUS_IN)

                assert mock_restore.call_count == 1
        finally:
            setup.destroy()

    async def test_multiple_blur_focus_cycles_each_trigger_one_restore(self):
        """Maps to test("multiple blur/focus cycles each trigger one restore")."""

        setup = await create_test_renderer(80, 24)
        try:
            with patch.object(setup.renderer, "_restore_terminal_modes") as mock_restore:
                _ = setup.stdin

                # First cycle.
                setup.stdin.emit("data", FOCUS_OUT)
                setup.stdin.emit("data", FOCUS_IN)

                # Second cycle.
                setup.stdin.emit("data", FOCUS_OUT)
                setup.stdin.emit("data", FOCUS_IN)

                assert mock_restore.call_count == 2
        finally:
            setup.destroy()

    async def test_focus_in_emits_focus_event_on_the_renderer(self):
        """Maps to test("focus-in emits focus event on the renderer").

        Upstream checks renderer.on("focus") / renderer.on("blur") event emitter.
        CliRenderer exposes .on("focus", handler) and .on("blur", handler) which
        fire when stdin delivers CSI I (focus-in) or CSI O (focus-out) sequences.
        """

        setup = await create_test_renderer(80, 24)
        try:
            events: list[str] = []

            setup.renderer.on("focus", lambda: events.append("focus"))
            setup.renderer.on("blur", lambda: events.append("blur"))

            _ = setup.stdin

            setup.stdin.emit("data", FOCUS_IN)
            setup.stdin.emit("data", FOCUS_OUT)

            assert events == ["focus", "blur"]
        finally:
            setup.destroy()

    async def test_focus_events_do_not_trigger_keypress_events(self):
        """Maps to test("focus events do not trigger keypress events")."""

        setup = await create_test_renderer(80, 24)
        try:
            keypresses: list = []

            from opentui import hooks

            def _key_handler(event) -> None:
                keypresses.append(event)

            hooks.register_keyboard_handler(_key_handler)
            try:
                _ = setup.stdin

                setup.stdin.emit("data", FOCUS_IN)
                setup.stdin.emit("data", FOCUS_OUT)

                assert len(keypresses) == 0
            finally:
                hooks.unregister_keyboard_handler(_key_handler)
        finally:
            setup.destroy()

    async def test_mouse_events_work_after_focus_restore_cycle(self):
        """Maps to test("mouse events work after focus restore cycle")."""

        setup = await create_test_renderer(80, 24, use_mouse=True)
        try:
            from opentui.components.box import Box
            from opentui.events import MouseEvent, MouseButton

            mouse_event_count = 0

            target = Box(
                width=setup.renderer.width,
                height=setup.renderer.height,
                position="absolute",
                left=0,
                top=0,
            )

            def _on_mouse_down(event):
                nonlocal mouse_event_count
                mouse_event_count += 1

            target._on_mouse_down = _on_mouse_down
            setup.renderer.root.add(target)
            setup.render_frame()

            # Verify mouse works initially.
            event = MouseEvent(type="down", x=5, y=5, button=MouseButton.LEFT)
            setup.renderer._dispatch_mouse_event(event)
            assert mouse_event_count > 0

            count_before = mouse_event_count

            # Simulate focus loss and regain via stdin.
            _ = setup.stdin
            with patch.object(setup.renderer, "_restore_terminal_modes"):
                setup.stdin.emit("data", FOCUS_OUT)
                setup.stdin.emit("data", FOCUS_IN)

            # Mouse should still work after the focus restore cycle.
            event2 = MouseEvent(type="down", x=5, y=5, button=MouseButton.LEFT)
            setup.renderer._dispatch_mouse_event(event2)
            assert mouse_event_count > count_before
        finally:
            setup.destroy()

    async def test_keyboard_input_works_after_focus_restore_cycle(self):
        """Maps to test("keyboard input works after focus restore cycle")."""

        setup = await create_test_renderer(80, 24)
        try:
            key_event_count = 0

            from opentui import hooks

            def _key_handler(event) -> None:
                nonlocal key_event_count
                key_event_count += 1

            hooks.register_keyboard_handler(_key_handler)
            try:
                # Verify keyboard works initially.
                setup.mock_input.press_key("a")
                assert key_event_count > 0

                count_before = key_event_count

                # Simulate focus loss and regain.
                _ = setup.stdin
                with patch.object(setup.renderer, "_restore_terminal_modes"):
                    setup.stdin.emit("data", FOCUS_OUT)
                    setup.stdin.emit("data", FOCUS_IN)

                # Keyboard should still work after the focus restore cycle.
                setup.mock_input.press_key("b")
                assert key_event_count > count_before
            finally:
                hooks.unregister_keyboard_handler(_key_handler)
        finally:
            setup.destroy()

    async def test_rapid_focus_toggle_does_not_cause_issues(self):
        """Maps to test("rapid focus toggle does not cause issues")."""

        setup = await create_test_renderer(80, 24)
        try:
            with patch.object(setup.renderer, "_restore_terminal_modes") as mock_restore:
                _ = setup.stdin

                # Simulate 10 rapid blur/focus cycles.
                for _ in range(10):
                    setup.stdin.emit("data", FOCUS_OUT)
                    setup.stdin.emit("data", FOCUS_IN)

                assert mock_restore.call_count == 10
        finally:
            setup.destroy()
