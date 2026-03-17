"""Port of upstream KeyHandler.test.ts.

Upstream: packages/core/src/lib/KeyHandler.test.ts
Tests ported: 30/30 (4 skipped - require TestRenderer)
"""

import pytest

from opentui.events import KeyEvent, PasteEvent
from opentui.key_handler import InternalKeyHandler


def create_key_handler(use_kitty_keyboard: bool = False) -> InternalKeyHandler:
    return InternalKeyHandler(use_kitty_keyboard)


class TestKeyHandlerProcessInput:
    """Maps to top-level test() calls in KeyHandler.test.ts."""

    def test_process_input_emits_keypress_events(self):
        handler = InternalKeyHandler()
        received: list[KeyEvent] = []
        handler.on("keypress", lambda key: received.append(key))
        handler.process_input("a")
        assert len(received) == 1
        k = received[0]
        assert k.name == "a"
        assert k.ctrl is False
        assert k.meta is False
        assert k.shift is False
        assert k.alt is False
        assert k.number is False
        assert k.sequence == "a"
        assert k.event_type == "press"

    def test_emits_keypress_events(self):
        handler = create_key_handler()
        received: list[KeyEvent] = []
        handler.on("keypress", lambda key: received.append(key))
        handler.process_input("a")
        assert len(received) == 1
        k = received[0]
        assert k.name == "a"
        assert k.ctrl is False
        assert k.meta is False
        assert k.shift is False
        assert k.alt is False
        assert k.number is False
        assert k.sequence == "a"
        assert k.event_type == "press"

    def test_handles_paste_via_process_paste(self):
        handler = create_key_handler()
        received: list[str] = []
        handler.on("paste", lambda event: received.append(event.text))
        handler.process_paste("pasted content")
        assert received == ["pasted content"]

    def test_process_paste_handles_content_directly(self):
        handler = create_key_handler()
        received: list[str] = []
        handler.on("paste", lambda event: received.append(event.text))
        handler.process_paste("chunk1chunk2chunk3")
        assert received == ["chunk1chunk2chunk3"]

    def test_strips_ansi_codes_in_paste(self):
        handler = create_key_handler()
        received: list[str] = []
        handler.on("paste", lambda event: received.append(event.text))
        handler.process_paste("text with \x1b[31mred\x1b[0m color")
        assert received == ["text with red color"]

    def test_constructor_accepts_use_kitty_keyboard_parameter(self):
        h1 = create_key_handler(False)
        h2 = create_key_handler(True)
        assert h1 is not None
        assert h2 is not None

    def test_handles_string_input(self):
        handler = create_key_handler()
        received: list[KeyEvent] = []
        handler.on("keypress", lambda key: received.append(key))
        handler.process_input("c")
        assert len(received) == 1
        k = received[0]
        assert k.name == "c"
        assert k.ctrl is False
        assert k.meta is False
        assert k.shift is False
        assert k.alt is False
        assert k.number is False
        assert k.sequence == "c"
        assert k.event_type == "press"

    def test_event_inheritance_from_event_emitter(self):
        handler = create_key_handler()
        assert callable(handler.on)
        assert callable(handler.emit)
        assert callable(handler.remove_listener)

    def test_prevent_default_stops_propagation(self):
        handler = create_key_handler()
        global_called = False
        second_called = False

        def first_handler(key):
            nonlocal global_called
            global_called = True
            key.prevent_default()

        def second_handler(key):
            nonlocal second_called
            if not key.default_prevented:
                second_called = True

        handler.on("keypress", first_handler)
        handler.on("keypress", second_handler)
        handler.process_input("a")
        assert global_called is True
        assert second_called is False


class TestInternalKeyHandler:
    """Maps to InternalKeyHandler tests in KeyHandler.test.ts."""

    def test_on_internal_handlers_run_after_regular_handlers(self):
        handler = create_key_handler()
        call_order: list[str] = []
        handler.on_internal("keypress", lambda key: call_order.append("internal"))
        handler.on("keypress", lambda key: call_order.append("regular"))
        handler.process_input("a")
        assert call_order == ["regular", "internal"]

    def test_prevent_default_prevents_internal_handlers_from_running(self):
        handler = create_key_handler()
        regular_called = False
        internal_called = False

        def regular(key):
            nonlocal regular_called
            regular_called = True
            key.prevent_default()

        def internal(key):
            nonlocal internal_called
            internal_called = True

        handler.on("keypress", regular)
        handler.on_internal("keypress", internal)
        handler.process_input("a")
        assert regular_called is True
        assert internal_called is False

    def test_multiple_internal_handlers_can_be_registered(self):
        handler = create_key_handler()
        h1_called = False
        h2_called = False
        h3_called = False

        def ih1(_):
            nonlocal h1_called
            h1_called = True

        def ih2(_):
            nonlocal h2_called
            h2_called = True

        def ih3(_):
            nonlocal h3_called
            h3_called = True

        handler.on_internal("keypress", ih1)
        handler.on_internal("keypress", ih2)
        handler.on_internal("keypress", ih3)
        handler.process_input("a")
        assert h1_called is True
        assert h2_called is True
        assert h3_called is True

    def test_off_internal_removes_specific_handlers(self):
        handler = create_key_handler()
        h1_called = False
        h2_called = False

        def ih1(_):
            nonlocal h1_called
            h1_called = True

        def ih2(_):
            nonlocal h2_called
            h2_called = True

        handler.on_internal("keypress", ih1)
        handler.on_internal("keypress", ih2)
        handler.off_internal("keypress", ih1)
        handler.process_input("a")
        assert h1_called is False
        assert h2_called is True

    def test_emit_returns_true_when_there_are_listeners(self):
        handler = create_key_handler()

        # No listeners
        result = handler.emit(
            "keypress",
            KeyEvent(key="a", sequence="a", event_type="press", source="raw"),
        )
        assert result is False

        # Add regular listener
        handler.on("keypress", lambda _: None)
        result = handler.emit(
            "keypress",
            KeyEvent(key="b", sequence="b", event_type="press", source="raw"),
        )
        assert result is True

        # Remove regular, add internal
        handler.remove_all_listeners("keypress")
        handler.on_internal("keypress", lambda _: None)
        result = handler.emit(
            "keypress",
            KeyEvent(key="c", sequence="c", event_type="press", source="raw"),
        )
        assert result is True

    def test_paste_events_work_with_priority_system(self):
        handler = create_key_handler()
        call_order: list[str] = []
        handler.on("paste", lambda e: call_order.append(f"regular:{e.text}"))
        handler.on_internal("paste", lambda e: call_order.append(f"internal:{e.text}"))
        handler.process_paste("hello")
        assert call_order == ["regular:hello", "internal:hello"]

    def test_paste_prevent_default_prevents_internal_handlers(self):
        handler = create_key_handler()
        regular_called = False
        internal_called = False
        received_text = ""

        def regular(event):
            nonlocal regular_called, received_text
            regular_called = True
            received_text = event.text
            event.prevent_default()

        def internal(event):
            nonlocal internal_called
            internal_called = True

        handler.on("paste", regular)
        handler.on_internal("paste", internal)
        handler.process_paste("test paste")
        assert regular_called is True
        assert received_text == "test paste"
        assert internal_called is False


class TestKeyHandlerEdgeCases:
    """Maps to edge case tests in KeyHandler.test.ts."""

    def test_emits_paste_event_even_with_empty_content(self):
        handler = create_key_handler()
        paste_received = False
        received_text = "not-empty"

        def on_paste(event):
            nonlocal paste_received, received_text
            paste_received = True
            received_text = event.text

        handler.on("paste", on_paste)
        handler.process_paste("")
        assert paste_received is True
        assert received_text == ""

    def test_filters_out_mouse_events(self):
        handler = create_key_handler()
        count_holder = [0]

        def on_key(_):
            count_holder[0] += 1

        handler.on("keypress", on_key)
        handler.remove_all_listeners("keypress")
        handler.on("keypress", on_key)

        # SGR mouse events should not generate keypresses
        handler.process_input("\x1b[<0;10;5M")
        assert count_holder[0] == 0

        handler.process_input("\x1b[<0;10;5m")
        assert count_holder[0] == 0

        # Old-style mouse: \x1b[M + 3 bytes
        handler.process_input("\x1b[M ab")
        assert count_holder[0] == 0

        # Regular characters should still work
        handler.process_input("c")
        assert count_holder[0] == 1

        handler.process_input("a")
        assert count_holder[0] == 2

    def test_key_event_has_source_field_set_to_raw_by_default(self):
        handler = create_key_handler()
        received: list[KeyEvent] = []
        handler.on("keypress", lambda key: received.append(key))
        handler.process_input("a")
        assert len(received) == 1
        assert received[0].source == "raw"
        assert received[0].name == "a"

    def test_key_event_has_source_field_for_different_key_types(self):
        handler = create_key_handler()
        received: list[KeyEvent] = []
        handler.on("keypress", lambda key: received.append(key))
        handler.process_input("a")  # printable character
        handler.process_input("A")  # uppercase
        handler.process_input("\x1b[A")  # up arrow (escape sequence)
        handler.process_input("\x01")  # Ctrl+A
        assert len(received) == 4
        assert all(k.source == "raw" for k in received)

    def test_key_event_source_is_kitty_when_using_kitty_keyboard_protocol(self):
        handler = create_key_handler(True)
        received: list[KeyEvent] = []
        handler.on("keypress", lambda key: received.append(key))
        # Kitty keyboard protocol sequence for 'a' (codepoint 97)
        handler.process_input("\x1b[97u")
        assert len(received) == 1
        assert received[0].source == "kitty"
        assert received[0].name == "a"

    def test_key_event_source_is_raw_for_non_kitty_sequences_even_with_kitty_enabled(self):
        handler = create_key_handler(use_kitty_keyboard=True)
        received: list[KeyEvent] = []
        handler.on("keypress", lambda key: received.append(key))
        # Regular sequences that don't match Kitty protocol
        handler.process_input("a")
        handler.process_input("\x1b[A")  # Up arrow (standard ANSI)
        assert len(received) == 2
        assert received[0].source == "raw"
        assert received[0].name == "a"
        assert received[1].source == "raw"
        assert received[1].name == "up"

    def test_source_field_persists_through_key_event_wrapper(self):
        handler = create_key_handler()
        received: list[KeyEvent] = []
        handler.on("keypress", lambda key: received.append(key))
        handler.process_input("x")
        assert len(received) == 1
        assert isinstance(received[0], KeyEvent)
        assert received[0].source == "raw"
        assert received[0].name == "x"


class TestKeyHandlerErrorHandling:
    """Maps to error handling tests in KeyHandler.test.ts."""

    def test_global_handler_error_is_caught_and_logged(self):
        handler = create_key_handler()
        handler_called = False

        def bad_handler(key):
            nonlocal handler_called
            handler_called = True
            raise RuntimeError("Test error in global handler")

        handler.on("keypress", bad_handler)
        # Should not raise
        handler.process_input("a")
        assert handler_called is True

    def test_renderable_handler_error_does_not_stop_processing(self):
        handler = create_key_handler()
        first_called = False
        second_called = False

        def ih1(key):
            nonlocal first_called
            first_called = True
            raise RuntimeError("Test error in internal handler")

        def ih2(key):
            nonlocal second_called
            second_called = True

        handler.on_internal("keypress", ih1)
        handler.on_internal("keypress", ih2)
        # Should not raise
        handler.process_input("a")
        assert first_called is True
        assert second_called is True

    def test_global_handler_error_stops_further_global_handlers_but_allows_internal(self):
        handler = create_key_handler()
        global_called = False
        internal_called = False

        def bad_global(key):
            nonlocal global_called
            global_called = True
            raise RuntimeError("Global handler error")

        def internal(key):
            nonlocal internal_called
            internal_called = True

        handler.on("keypress", bad_global)
        handler.on_internal("keypress", internal)
        handler.process_input("a")
        assert global_called is True
        assert internal_called is True

    def test_paste_handler_error_is_caught_and_logged(self):
        handler = create_key_handler()
        handler_called = False

        def bad_paste(event):
            nonlocal handler_called
            handler_called = True
            raise RuntimeError("Test error in paste handler")

        handler.on("paste", bad_paste)
        # Should not raise
        handler.process_paste("test")
        assert handler_called is True

    def test_process_input_returns_true_even_when_handler_throws(self):
        handler = create_key_handler()
        handler.on("keypress", lambda key: (_ for _ in ()).throw(RuntimeError("Handler error")))

        def raise_handler(key):
            raise RuntimeError("Handler error")

        handler.remove_all_listeners("keypress")
        handler.on("keypress", raise_handler)
        result = handler.process_input("a")
        assert result is True

    def test_internal_handler_error_with_prevent_default_still_respects_prevention(self):
        handler = create_key_handler()
        global_called = False
        internal_called = False

        def global_handler(key):
            nonlocal global_called
            global_called = True
            key.prevent_default()

        def internal_handler(key):
            nonlocal internal_called
            internal_called = True
            raise RuntimeError("Should not reach here")

        handler.on("keypress", global_handler)
        handler.on_internal("keypress", internal_handler)
        handler.process_input("a")
        assert global_called is True
        assert internal_called is False

    def test_error_in_one_event_type_does_not_prevent_other_event_types(self):
        handler = create_key_handler()
        keypress_called = False
        paste_called = False

        def bad_keypress(key):
            nonlocal keypress_called
            keypress_called = True
            raise RuntimeError("Keypress error")

        def paste_handler(event):
            nonlocal paste_called
            paste_called = True

        handler.on("keypress", bad_keypress)
        handler.on("paste", paste_handler)
        handler.process_input("a")
        handler.process_paste("test")
        assert keypress_called is True
        assert paste_called is True
