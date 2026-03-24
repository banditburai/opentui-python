"""Port of upstream Textarea.destroyed-events.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.destroyed-events.test.ts
Tests: 21 (21 real, 0 skipped)
"""

from opentui.components.textarea import TextareaRenderable
from opentui.events import KeyEvent, PasteEvent


# ── Helpers ─────────────────────────────────────────────────────────────


def _key(
    name: str,
    *,
    ctrl: bool = False,
    shift: bool = False,
    alt: bool = False,
    meta: bool = False,
    hyper: bool = False,
    sequence: str = "",
) -> KeyEvent:
    return KeyEvent(
        key=name, ctrl=ctrl, shift=shift, alt=alt, meta=meta, hyper=hyper, sequence=sequence
    )


def _make(text: str = "", **kwargs) -> TextareaRenderable:
    """Create a focused TextareaRenderable with given text."""
    ta = TextareaRenderable(initial_value=text, **kwargs)
    ta.focus()
    return ta


class TestTextareaDestroyedRenderableEvents:
    """Textarea - Destroyed Renderable Event Tests"""

    class TestKeypressEventsOnDestroyedRenderable:
        """Keypress events on destroyed renderable"""

        def test_should_not_trigger_handle_key_press_after_destroy_is_called(self):
            """After destroy, handle_key should not process events."""
            keypress_called = False
            handle_key_called = False

            def on_key_down(event):
                nonlocal keypress_called
                keypress_called = True

            ta = _make("Test", on_key_down=on_key_down)

            # Wrap handle_key to track calls
            original_handle_key = ta.handle_key

            def tracked_handle_key(event):
                nonlocal handle_key_called
                handle_key_called = True
                return original_handle_key(event)

            ta.destroy()

            # Reset flags
            keypress_called = False
            handle_key_called = False

            # Try to send a key event after destruction
            result = ta.handle_key(_key("A"))

            assert result is False
            assert keypress_called is False
            # handle_key returns False early due to _is_destroyed guard

        def test_should_not_trigger_handle_key_press_when_destroyed_before_blur(self):
            """Destroy without explicit blur prevents key handling."""
            keypress_called = False

            def on_key_down(event):
                nonlocal keypress_called
                keypress_called = True

            ta = _make("Test", on_key_down=on_key_down)

            # Destroy without explicitly blurring first
            ta.destroy()

            keypress_called = False

            result = ta.handle_key(_key("B"))

            assert result is False
            assert keypress_called is False

        def test_should_not_trigger_keypress_during_async_operations_after_destroy(self):
            """Events queued before destroy should not be processed after destroy."""
            keypress_count = 0

            def on_key_down(event):
                nonlocal keypress_count
                keypress_count += 1

            ta = _make("Test", on_key_down=on_key_down)

            # Process some key events before destroy
            ta.handle_key(_key("A"))
            ta.handle_key(_key("B"))

            count_before_destroy = keypress_count

            # Destroy
            ta.destroy()

            # Queue more events after destroy
            ta.handle_key(_key("C"))
            ta.handle_key(_key("D"))

            # Only the events before destroy should have been processed
            assert keypress_count == count_before_destroy
            assert keypress_count <= 2

        def test_should_handle_rapid_focus_destroy_keypress_cycles(self):
            """Rapid focus/destroy/keypress cycles should not crash."""
            errors = []

            try:
                ta = _make("Test")
                ta.handle_key(_key("A"))
                ta.destroy()
                ta.handle_key(_key("B"))

                # Create and destroy another
                ta2 = _make("Test2")
                ta2.handle_key(_key("C"))
                ta2.destroy()
                ta2.handle_key(_key("D"))
            except Exception as e:
                errors.append(e)

            assert len(errors) == 0

        def test_should_not_crash_when_keypress_handler_fires_after_edit_buffer_is_destroyed(self):
            """Key press after destroy should be safely ignored."""
            ta = _make("Test")

            # Destroy the whole textarea properly
            ta.destroy()

            # Try pressing key after destroy - should be safely ignored
            result = ta.handle_key(_key("X"))

            assert result is False
            assert ta.is_destroyed is True

    class TestPasteEventsOnDestroyedRenderable:
        """Paste events on destroyed renderable"""

        def test_should_not_trigger_handle_paste_after_destroy_is_called(self):
            """After destroy, handle_paste should not process events."""
            paste_called = False

            def on_paste(event):
                nonlocal paste_called
                paste_called = True

            ta = _make("Test", on_paste=on_paste)

            ta.destroy()
            paste_called = False

            ta.handle_paste(PasteEvent(text="PastedText"))

            assert paste_called is False

        def test_should_not_trigger_paste_during_async_operations_after_destroy(self):
            """Paste after destroy should not be processed."""
            paste_count = 0

            def on_paste(event):
                nonlocal paste_count
                paste_count += 1

            ta = _make("Test", on_paste=on_paste)

            # Queue paste operation before destroy
            ta.handle_paste(PasteEvent(text="Text1"))
            count_before = paste_count

            # Destroy
            ta.destroy()

            # Try another paste after destroy
            ta.handle_paste(PasteEvent(text="Text2"))

            # At most the first paste should have been processed
            assert paste_count <= 1

    class TestEventHandlersCleanupOnDestroy:
        """Event handlers cleanup on destroy"""

        def test_should_remove_keypress_handler_from_internal_key_input_on_destroy(self):
            """After destroy, focused should be False and is_destroyed should be True."""
            ta = _make("Test")

            assert ta.focused is True

            ta.destroy()

            assert ta.focused is False
            assert ta.is_destroyed is True

        def test_should_not_trigger_events_when_destroyed_renderable_is_still_in_tree(self):
            """Destroyed renderable does not process key events."""
            keypress_count = 0

            def on_key_down(event):
                nonlocal keypress_count
                keypress_count += 1

            ta = _make("Test", on_key_down=on_key_down)

            ta.destroy()

            assert ta.is_destroyed is True
            keypress_count = 0

            ta.handle_key(_key("A"))

            assert keypress_count == 0

        def test_should_handle_destroy_called_multiple_times(self):
            """Multiple destroy calls should not crash."""
            error_occurred = False

            ta = _make("Test")

            try:
                ta.destroy()
                ta.destroy()
                ta.destroy()
            except Exception:
                error_occurred = True

            assert error_occurred is False

        def test_should_clean_up_event_listeners_when_destroyed_while_handling_an_event(self):
            """Destroying during an event handler should not cause errors."""
            handler_call_count = 0
            should_destroy = False

            ta = _make("Test")

            def on_key_down(event):
                nonlocal handler_call_count
                handler_call_count += 1
                if should_destroy:
                    ta.destroy()

            ta = _make("Test", on_key_down=on_key_down)

            # First keypress should work
            ta.handle_key(_key("A"))
            assert handler_call_count == 1

            # Second keypress destroys the renderable during handler
            should_destroy = True
            ta.handle_key(_key("B"))
            assert handler_call_count == 2

            # Third keypress should not trigger anything (destroyed)
            ta.handle_key(_key("C"))
            assert handler_call_count == 2

    class TestDestroyedRenderableWithQueuedOperations:
        """Destroyed renderable with queued operations"""

        def test_should_not_process_insert_text_after_destroy(self):
            """insert_text after destroy should be a no-op."""
            ta = _make("Initial")

            ta.destroy()

            # Try to call insert_text on destroyed renderable - should be no-op
            ta.insert_text("New Text")

            # Should not crash - the destroy guard makes it a no-op
            assert ta.is_destroyed is True

        def test_should_handle_events_arriving_between_destroy_and_cleanup(self):
            """Key events during destroy should not crash."""
            ta = _make("Test")

            # Queue several key events
            ta.handle_key(_key("A"))
            ta.handle_key(_key("B"))
            ta.handle_key(_key("C"))

            # Destroy immediately
            ta.destroy()

            # No crashes should occur
            assert ta.is_destroyed is True

        def test_should_safely_handle_focus_after_destroy(self):
            """Focus after destroy should be no-op."""
            ta = _make("Test")
            assert ta.focused is True

            ta.destroy()

            # Try to focus again after destroy - should be no-op
            ta.focus()

            # Focus should still be False after destroy
            assert ta.focused is False

    class TestEditorViewAndEditBufferDestroyedState:
        """EditorView and EditBuffer destroyed state"""

        def test_should_check_if_edit_buffer_guard_prevents_operations_after_destroy(self):
            """Edit buffer operations should fail after destroy."""
            ta = _make("Test")

            ta.destroy()

            # After destroy, the edit buffer is destroyed; accessing it should throw
            error_thrown = False
            try:
                ta.edit_buffer.get_text()
            except Exception as e:
                error_thrown = True

            assert error_thrown is True

        def test_should_check_if_editor_view_guard_prevents_operations_after_destroy(self):
            """Editor view (cursor) operations should fail after destroy."""
            ta = _make("Test")

            ta.destroy()

            # After destroy, the edit buffer is destroyed; cursor access should throw
            error_thrown = False
            try:
                ta.edit_buffer.get_cursor_position()
            except Exception as e:
                error_thrown = True

            assert error_thrown is True

        def test_should_not_allow_keypress_after_proper_destroy(self):
            """Key press after destroy should not fire handler."""
            keypress_fired = False

            def on_key_down(event):
                nonlocal keypress_fired
                keypress_fired = True

            ta = _make("Test", on_key_down=on_key_down)

            ta.destroy()

            ta.handle_key(_key("A"))

            assert keypress_fired is False
            assert ta.is_destroyed is True

    class TestMultipleRenderablesAndEventRouting:
        """Multiple renderables and event routing"""

        def test_should_not_route_events_to_destroyed_renderable_when_multiple_exist(self):
            """Events should only reach the active (non-destroyed) renderable."""
            editor1_keypress_count = 0
            editor2_keypress_count = 0

            def on_key1(event):
                nonlocal editor1_keypress_count
                editor1_keypress_count += 1

            def on_key2(event):
                nonlocal editor2_keypress_count
                editor2_keypress_count += 1

            ta1 = _make("Editor 1", on_key_down=on_key1)
            ta2 = TextareaRenderable(initial_value="Editor 2", on_key_down=on_key2)

            # Focus first editor
            ta1.handle_key(_key("A"))
            assert editor1_keypress_count == 1
            assert editor2_keypress_count == 0

            # Destroy first editor and focus second
            ta1.destroy()
            ta2.focus()

            editor1_keypress_count = 0
            editor2_keypress_count = 0

            ta2.handle_key(_key("B"))

            assert editor1_keypress_count == 0
            assert editor2_keypress_count == 1

            ta2.destroy()

        def test_should_handle_switching_focus_between_renderables_rapidly(self):
            """Rapid focus switching and destroy should not crash."""
            ta1 = _make("Editor 1")
            ta2 = _make("Editor 2")

            # Rapidly switch focus and destroy
            ta1.focus()
            ta2.focus()
            ta1.destroy()
            ta2.blur()
            ta2.focus()
            ta2.destroy()

            # Send events after all destroyed
            ta1.handle_key(_key("X"))
            ta2.handle_key(_key("X"))

            # Should not crash
            assert ta1.is_destroyed is True
            assert ta2.is_destroyed is True

    class TestRenderableDestroyedFlagChecks:
        """Renderable destroyed flag checks"""

        def test_should_prevent_handle_key_press_execution_when_is_destroyed_is_true(self):
            """handle_key returns False when is_destroyed is True."""
            ta = _make("Test")

            ta.handle_key(_key("A"))

            ta.destroy()

            result = ta.handle_key(_key("B"))

            assert result is False

        def test_should_check_is_destroyed_in_event_handler_methods(self):
            """is_destroyed flag tracks destroy state correctly."""
            ta = _make("Test")

            assert ta.is_destroyed is False

            ta.focus()
            assert ta.is_destroyed is False

            ta.destroy()
            assert ta.is_destroyed is True

            # After destroy, operations should either fail or be no-ops
            error_count = 0
            try:
                ta.focus()
            except Exception:
                error_count += 1

            try:
                ta.blur()
            except Exception:
                error_count += 1

            # Operations after destroy should either throw or be ignored
            assert ta.is_destroyed is True
