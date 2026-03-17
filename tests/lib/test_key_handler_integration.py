"""Port of upstream KeyHandler.integration.test.ts.

Upstream: packages/core/src/lib/KeyHandler.integration.test.ts
Tests ported: 7/7
"""

import pytest

from opentui.key_handler import InternalKeyHandler, KeyEvent


def _create_handler() -> InternalKeyHandler:
    return InternalKeyHandler()


class TestKeyHandlerIntegration:
    """Maps to top-level test() calls in KeyHandler.integration.test.ts."""

    def test_modal_esc_handler_prevents_subsequent_handlers(self):
        """Maps to test("Integration - Modal ESC handler prevents subsequent handlers")."""
        handler = _create_handler()

        modal_open = True
        modal_handled_esc = False
        background_handled_esc = False

        def modal_handler(key: KeyEvent) -> None:
            nonlocal modal_open, modal_handled_esc
            if key.key == "escape" and modal_open:
                modal_handled_esc = True
                modal_open = False
                key.stop_propagation()

        def background_handler(key: KeyEvent) -> None:
            nonlocal background_handled_esc
            if key.key == "escape":
                background_handled_esc = True

        handler.on("keypress", modal_handler)
        handler.on("keypress", background_handler)

        handler.process_input("\x1b")

        assert modal_open is False
        assert modal_handled_esc is True
        assert background_handled_esc is False  # Modal stopped propagation

    def test_focused_input_field_handles_key_stops_parent_handlers(self):
        """Maps to test("Integration - Focused input field handles key, stops parent handlers")."""
        handler = _create_handler()

        input_value: list[str] = []
        parent_handled_key = False

        def parent_handler(key: KeyEvent) -> None:
            nonlocal parent_handled_key
            if not key.propagation_stopped:
                parent_handled_key = True

        def input_handler(key: KeyEvent) -> None:
            if key.key in ("a", "b", "c"):
                input_value.append(key.key)
                key.stop_propagation()

        handler.on("keypress", parent_handler)
        handler.on_internal("keypress", input_handler)

        handler.process_input("a")
        handler.process_input("b")
        handler.process_input("c")

        assert input_value == ["a", "b", "c"]
        assert parent_handled_key is True  # Parent ran first (global priority)

    def test_dialog_system_with_priority_innermost_modal_wins(self):
        """Maps to test("Integration - Dialog system with priority: innermost modal wins")."""
        handler = _create_handler()

        outer_modal_closed = False
        inner_modal_closed = False
        close_log: list[str] = []

        def outer_handler(key: KeyEvent) -> None:
            nonlocal outer_modal_closed
            if key.key == "escape" and not key.propagation_stopped:
                close_log.append("outer")
                outer_modal_closed = True
                key.stop_propagation()

        def inner_handler(key: KeyEvent) -> None:
            nonlocal inner_modal_closed
            if key.key == "escape":
                close_log.append("inner")
                inner_modal_closed = True
                key.stop_propagation()

        # Register outer first, then reorder so inner is first
        handler.on("keypress", outer_handler)
        handler.remove_listener("keypress", outer_handler)
        handler.on("keypress", inner_handler)
        handler.on("keypress", outer_handler)

        handler.process_input("\x1b")

        assert close_log == ["inner"]
        assert inner_modal_closed is True
        assert outer_modal_closed is False  # Inner stopped propagation

    def test_keyboard_shortcut_system_with_priorities(self):
        """Maps to test("Integration - Keyboard shortcut system with priorities")."""
        handler = _create_handler()

        actions: list[str] = []

        def global_shortcuts(key: KeyEvent) -> None:
            if key.ctrl and key.key == "s":
                actions.append("save")
            if key.ctrl and key.key == "o":
                actions.append("open")

        editor_focused = True

        def editor_handler(key: KeyEvent) -> None:
            if editor_focused and key.ctrl and key.key == "s":
                actions.append("save-document")
                key.stop_propagation()

        handler.on("keypress", global_shortcuts)
        handler.on_internal("keypress", editor_handler)

        handler.process_input("\x13")  # Ctrl+S

        assert actions == ["save", "save-document"]

    def test_prevent_default_vs_stop_propagation_behavior(self):
        """Maps to test("Integration - preventDefault vs stopPropagation behavior")."""
        handler = _create_handler()

        log: list[str] = []

        def handler1(key: KeyEvent) -> None:
            if key.key == "a":
                log.append("handler1-saw-a")
                key.prevent_default()

        def handler2(key: KeyEvent) -> None:
            if key.key == "a":
                log.append("handler2-saw-a")
                if key.default_prevented:
                    log.append("handler2-saw-prevented")

        def handler3(key: KeyEvent) -> None:
            if key.key == "a":
                log.append("handler3-internal-saw-a")

        handler.on("keypress", handler1)
        handler.on("keypress", handler2)
        handler.on_internal("keypress", handler3)

        handler.process_input("a")

        assert log == [
            "handler1-saw-a",
            "handler2-saw-a",
            "handler2-saw-prevented",
            # handler3 doesn't run because preventDefault stops internal handlers
        ]

        # Now test with stopPropagation
        log.clear()
        handler.remove_all_listeners("keypress")
        # Also clear internal handlers
        handler._renderable_handlers.pop("keypress", None)

        def handler_b1(key: KeyEvent) -> None:
            if key.key == "b":
                log.append("handler1-saw-b")
                key.stop_propagation()

        def handler_b2(key: KeyEvent) -> None:
            if key.key == "b":
                log.append("handler2-saw-b")

        handler.on("keypress", handler_b1)
        handler.on("keypress", handler_b2)

        handler.process_input("b")

        assert log == [
            "handler1-saw-b",
            # handler2 doesn't run because stopPropagation stops all subsequent
        ]

    def test_form_submission_with_enter_key(self):
        """Maps to test("Integration - Form submission with Enter key")."""
        handler = _create_handler()

        form_submitted = False
        input_value = ""

        def form_handler(key: KeyEvent) -> None:
            nonlocal form_submitted
            if key.key == "return" and not key.propagation_stopped:
                form_submitted = True

        def input_handler(key: KeyEvent) -> None:
            nonlocal input_value
            if key.key == "return":
                input_value += "\n"
                key.stop_propagation()

        handler.on("keypress", form_handler)
        handler.on_internal("keypress", input_handler)

        handler.process_input("\r")

        assert input_value == "\n"
        assert form_submitted is True  # Global handler ran first

    def test_event_bubbling_with_multiple_nested_components(self):
        """Maps to test("Integration - Event bubbling with multiple nested components")."""
        handler = _create_handler()

        event_log: list[dict] = []

        def root_handler(key: KeyEvent) -> None:
            event_log.append({"component": "root", "stopped": key.propagation_stopped})

        def child_handler(key: KeyEvent) -> None:
            event_log.append({"component": "child", "stopped": key.propagation_stopped})
            if key.key == " ":
                key.stop_propagation()

        def sibling_handler(key: KeyEvent) -> None:
            event_log.append({"component": "sibling", "stopped": key.propagation_stopped})

        handler.on("keypress", root_handler)
        handler.on_internal("keypress", child_handler)
        handler.on_internal("keypress", sibling_handler)

        handler.process_input(" ")  # Space key

        assert event_log == [
            {"component": "root", "stopped": False},
            {"component": "child", "stopped": False},
            # sibling doesn't run because child stopped propagation
        ]
        assert len(event_log) == 2
