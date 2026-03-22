"""Port of upstream KeyHandler.stopPropagation.test.ts.

Upstream: packages/core/src/lib/KeyHandler.stopPropagation.test.ts
Tests ported: 11/11
"""

import pytest

from opentui.events import KeyEvent, PasteEvent
from opentui.input.key_handler import InternalKeyHandler


def create_key_handler(use_kitty_keyboard: bool = False) -> InternalKeyHandler:
    return InternalKeyHandler(use_kitty_keyboard)


class TestStopPropagation:
    """Maps to top-level test() calls in KeyHandler.stopPropagation.test.ts."""

    def test_stops_subsequent_global_handlers(self):
        """Maps to test("stopPropagation - stops subsequent global handlers")."""
        handler = create_key_handler()
        first_called = False
        second_called = False

        def h1(key):
            nonlocal first_called
            first_called = True
            key.stop_propagation()

        def h2(key):
            nonlocal second_called
            second_called = True

        handler.on("keypress", h1)
        handler.on("keypress", h2)
        handler.process_input("a")
        assert first_called is True
        assert second_called is False

    def test_stops_internal_handlers_from_running(self):
        """Maps to test("stopPropagation - stops internal handlers from running")."""
        handler = create_key_handler()
        global_called = False
        internal_called = False

        def gh(key):
            nonlocal global_called
            global_called = True
            key.stop_propagation()

        def ih(key):
            nonlocal internal_called
            internal_called = True

        handler.on("keypress", gh)
        handler.on_internal("keypress", ih)
        handler.process_input("a")
        assert global_called is True
        assert internal_called is False

    def test_internal_handler_can_stop_other_internal_handlers(self):
        """Maps to test("stopPropagation - internal handler can stop other internal handlers")."""
        handler = create_key_handler()
        i1_called = False
        i2_called = False

        def ih1(key):
            nonlocal i1_called
            i1_called = True
            key.stop_propagation()

        def ih2(key):
            nonlocal i2_called
            i2_called = True

        handler.on_internal("keypress", ih1)
        handler.on_internal("keypress", ih2)
        handler.process_input("a")
        assert i1_called is True
        assert i2_called is False

    def test_does_not_affect_prevent_default(self):
        """Maps to test("stopPropagation - does not affect preventDefault")."""
        handler = create_key_handler()
        call_order: list[str] = []

        def gh(key):
            call_order.append("global")
            key.prevent_default()
            # preventDefault does NOT stop propagation to other global handlers
            # but it does stop internal handlers

        def gh2(key):
            call_order.append("global2")
            key.stop_propagation()
            # stopPropagation stops all further handlers

        def ih(key):
            call_order.append("internal")

        handler.on("keypress", gh)
        handler.on("keypress", gh2)
        handler.on_internal("keypress", ih)
        handler.process_input("a")
        assert call_order == ["global", "global2"]

    def test_without_calling_it_all_handlers_run(self):
        """Maps to test("stopPropagation - without calling it, all handlers run")."""
        handler = create_key_handler()
        call_order: list[str] = []

        handler.on("keypress", lambda key: call_order.append("global1"))
        handler.on("keypress", lambda key: call_order.append("global2"))
        handler.on_internal("keypress", lambda key: call_order.append("internal1"))
        handler.on_internal("keypress", lambda key: call_order.append("internal2"))
        handler.process_input("a")
        assert "global1" in call_order
        assert "global2" in call_order
        assert "internal1" in call_order
        assert "internal2" in call_order

    def test_paste_events_support_stop_propagation(self):
        """Maps to test("stopPropagation - paste events support stopPropagation")."""
        handler = create_key_handler()
        first_called = False
        second_called = False

        def h1(event):
            nonlocal first_called
            first_called = True
            event.stop_propagation()

        def h2(event):
            nonlocal second_called
            second_called = True

        handler.on("paste", h1)
        handler.on("paste", h2)
        handler.process_paste("test paste")
        assert first_called is True
        assert second_called is False

    def test_works_with_keyrelease_events(self):
        """Maps to test("stopPropagation - works with keyrelease events")."""
        handler = create_key_handler(True)  # kitty keyboard for release events
        first_called = False
        second_called = False

        def h1(key):
            nonlocal first_called
            first_called = True
            key.stop_propagation()

        def h2(key):
            nonlocal second_called
            second_called = True

        handler.on("keyrelease", h1)
        handler.on("keyrelease", h2)
        # Kitty keyboard release event for 'a': \x1b[97;1:3u (codepoint 97, mod 1, event 3=release)
        handler.process_input("\x1b[97;1:3u")
        assert first_called is True
        assert second_called is False

    def test_error_in_handler_does_not_affect_propagation_stopped_state(self):
        """Maps to test("stopPropagation - error in handler does not affect propagation stopped state")."""
        handler = create_key_handler()
        second_called = False
        internal_called = False

        def bad_handler(key):
            key.stop_propagation()
            raise RuntimeError("Test error")

        def gh2(key):
            nonlocal second_called
            second_called = True

        def ih(key):
            nonlocal internal_called
            internal_called = True

        handler.on("keypress", bad_handler)
        handler.on("keypress", gh2)
        handler.on_internal("keypress", ih)
        # Should not raise
        handler.process_input("a")
        # stop_propagation was called before the error, so subsequent handlers should not run
        assert second_called is False
        assert internal_called is False

    def test_modal_scenario_esc_key_handled_by_modal_stops_at_modal(self):
        """Maps to test("stopPropagation - modal scenario: ESC key handled by modal, stops at modal")."""
        handler = create_key_handler()
        modal_handled = False
        app_handled = False

        def modal_handler(key):
            nonlocal modal_handled
            if key.key == "escape":
                modal_handled = True
                key.stop_propagation()

        def app_handler(key):
            nonlocal app_handled
            app_handled = True

        handler.on_internal("keypress", modal_handler)
        handler.on_internal("keypress", app_handler)
        handler.process_input("\x1b")  # ESC
        assert modal_handled is True
        assert app_handled is False

    def test_modal_scenario_global_modal_handler_prevents_app_handler(self):
        """Maps to test("stopPropagation - modal scenario: global modal handler prevents app handler")."""
        handler = create_key_handler()
        modal_called = False
        app_called = False

        def modal_global(key):
            nonlocal modal_called
            modal_called = True
            key.stop_propagation()

        def app_global(key):
            nonlocal app_called
            app_called = True

        handler.on("keypress", modal_global)
        handler.on("keypress", app_global)
        handler.process_input("a")
        assert modal_called is True
        assert app_called is False

    def test_event_flow_without_stop_propagation_shows_order(self):
        """Maps to test("stopPropagation - event flow without stopPropagation shows order")."""
        handler = create_key_handler()
        call_order: list[str] = []

        handler.on("keypress", lambda key: call_order.append("global1"))
        handler.on("keypress", lambda key: call_order.append("global2"))
        handler.on_internal("keypress", lambda key: call_order.append("internal1"))
        handler.on_internal("keypress", lambda key: call_order.append("internal2"))
        handler.process_input("b")
        # Global handlers run first (in registration order), then internal
        assert call_order[0] == "global1"
        assert call_order[1] == "global2"
        # Internal handlers run after globals (order within internals may vary since they're in a set)
        assert "internal1" in call_order[2:]
        assert "internal2" in call_order[2:]
