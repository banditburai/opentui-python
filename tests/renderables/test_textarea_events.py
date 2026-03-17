"""Port of upstream Textarea.events.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.events.test.ts
Tests: 29 (29 real, 0 skipped)
"""

from opentui.components.textarea_renderable import TextareaRenderable
from opentui.events import KeyEvent, PasteEvent
from opentui.keymapping import KeyBinding


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


def _type_string(ta: TextareaRenderable, text: str) -> None:
    """Type a string character by character via handle_key."""
    for ch in text:
        ta.handle_key(_key(ch))


def _make(text: str = "", **kwargs) -> TextareaRenderable:
    """Create a focused TextareaRenderable with given text."""
    ta = TextareaRenderable(initial_value=text, **kwargs)
    ta.focus()
    return ta


class TestTextareaEventHandlers:
    """Textarea - Event Handlers Tests"""

    class TestChangeEventsOnCursorChange:
        """Change Events - onCursorChange"""

        def test_should_fire_on_cursor_change_when_cursor_moves(self):
            """Cursor change fires when cursor moves via move_cursor_right/move_cursor_down."""
            cursor_change_count = 0
            last_cursor_event = None

            def on_cursor(pos):
                nonlocal cursor_change_count, last_cursor_event
                cursor_change_count += 1
                last_cursor_event = pos

            ta = _make("Line 1\nLine 2\nLine 3", on_cursor_change=on_cursor)
            initial_count = cursor_change_count

            ta.move_cursor_right()

            assert cursor_change_count > initial_count
            assert last_cursor_event is not None
            assert last_cursor_event[0] == 0  # line
            assert last_cursor_event[1] == 1  # col

            prev_count = cursor_change_count
            ta.move_cursor_down()

            assert cursor_change_count >= prev_count
            assert last_cursor_event is not None
            assert last_cursor_event[0] >= 0
            ta.destroy()

        def test_should_fire_on_cursor_change_when_typing_moves_cursor(self):
            """Cursor change fires when typing a character."""
            cursor_change_count = 0
            last_cursor_event = None

            def on_cursor(pos):
                nonlocal cursor_change_count, last_cursor_event
                cursor_change_count += 1
                last_cursor_event = pos

            ta = _make("", on_cursor_change=on_cursor)
            initial_count = cursor_change_count

            ta.handle_key(_key("H"))

            assert cursor_change_count > initial_count
            assert last_cursor_event is not None
            assert last_cursor_event[0] == 0  # line
            assert last_cursor_event[1] == 1  # col
            ta.destroy()

        def test_should_fire_on_cursor_change_when_pressing_arrow_keys(self):
            """Cursor change fires on arrow key presses."""
            cursor_event_count = 0
            last_cursor_event = None

            def on_cursor(pos):
                nonlocal cursor_event_count, last_cursor_event
                cursor_event_count += 1
                last_cursor_event = pos

            ta = _make("ABC\nDEF", on_cursor_change=on_cursor)
            initial_count = cursor_event_count

            ta.handle_key(_key("right"))

            assert cursor_event_count > initial_count
            assert last_cursor_event is not None
            assert last_cursor_event[1] == 1  # visual_column

            before_down = cursor_event_count
            ta.handle_key(_key("down"))

            assert cursor_event_count >= before_down
            assert last_cursor_event is not None
            ta.destroy()

        def test_should_fire_on_cursor_change_when_using_goto_line(self):
            """Cursor change fires when using goto_line."""
            cursor_change_count = 0
            last_cursor_event = None

            def on_cursor(pos):
                nonlocal cursor_change_count, last_cursor_event
                cursor_change_count += 1
                last_cursor_event = pos

            ta = _make("Line 0\nLine 1\nLine 2", on_cursor_change=on_cursor)
            initial_count = cursor_change_count

            ta.goto_line(2)

            assert cursor_change_count > initial_count
            assert last_cursor_event is not None
            assert last_cursor_event[0] == 2  # line
            assert last_cursor_event[1] == 0  # col
            ta.destroy()

        def test_should_fire_on_cursor_change_after_undo(self):
            """Cursor change fires after undo."""
            cursor_change_count = 0

            def on_cursor(pos):
                nonlocal cursor_change_count
                cursor_change_count += 1

            ta = _make("", on_cursor_change=on_cursor)

            ta.handle_key(_key("H"))
            ta.handle_key(_key("i"))

            before_undo = cursor_change_count

            ta.undo()

            assert cursor_change_count > before_undo
            ta.destroy()

        def test_should_update_event_handler_when_set_dynamically(self):
            """Dynamic handler update via on_cursor_change property setter."""
            first_handler_called = False
            second_handler_called = False

            def first_handler(pos):
                nonlocal first_handler_called
                first_handler_called = True

            def second_handler(pos):
                nonlocal second_handler_called
                second_handler_called = True

            ta = _make("Test", on_cursor_change=first_handler)

            ta.move_cursor_right()
            assert first_handler_called is True

            ta.on_cursor_change = second_handler

            ta.move_cursor_right()
            assert second_handler_called is True
            ta.destroy()

        def test_should_not_fire_when_handler_is_undefined(self):
            """No crash when handler is None; cursor still moves."""
            ta = _make("Test", on_cursor_change=None)

            ta.move_cursor_right()
            assert ta.cursor_position == (0, 1)
            ta.destroy()

    class TestChangeEventsOnContentChange:
        """Change Events - onContentChange"""

        def test_should_fire_on_content_change_when_typing(self):
            """Content change fires when typing."""
            content_change_count = 0

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("", on_content_change=on_content)
            initial_count = content_change_count

            ta.handle_key(_key("H"))

            assert content_change_count > initial_count
            assert ta.plain_text == "H"
            ta.destroy()

        def test_should_fire_on_content_change_when_deleting(self):
            """Content change fires when deleting (backspace)."""
            content_change_count = 0

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("Hello", on_content_change=on_content)
            # Move cursor to end
            ta.goto_line(9999)
            # Move to end of line
            ta.goto_line_end()
            initial_count = content_change_count

            ta.handle_key(_key("backspace"))

            assert content_change_count > initial_count
            assert ta.plain_text == "Hell"
            ta.destroy()

        def test_should_fire_on_content_change_when_inserting_newline(self):
            """Content change fires when inserting newline."""
            content_change_count = 0

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("Test", on_content_change=on_content)
            # Move cursor to end
            ta.goto_line(9999)
            ta.goto_line_end()
            initial_count = content_change_count

            ta.handle_key(_key("return"))

            assert content_change_count > initial_count
            assert ta.plain_text == "Test\n"
            ta.destroy()

        def test_should_fire_on_content_change_when_pasting(self):
            """Content change fires on paste."""
            content_change_count = 0

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("Hello", on_content_change=on_content)
            # Move cursor to end
            ta.goto_line(9999)
            ta.goto_line_end()
            initial_count = content_change_count

            event = PasteEvent(text=" World")
            ta.handle_paste(event)

            assert content_change_count > initial_count
            assert ta.plain_text == "Hello World"
            ta.destroy()

        def test_should_fire_on_content_change_after_undo(self):
            """Content change fires after undo."""
            content_change_count = 0

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("", on_content_change=on_content)

            ta.handle_key(_key("T"))
            ta.handle_key(_key("e"))

            before_undo = content_change_count

            ta.undo()

            assert content_change_count >= before_undo
            assert ta.plain_text == "T"
            ta.destroy()

        def test_should_fire_on_content_change_after_redo(self):
            """Content change fires after redo."""
            content_change_count = 0

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("", on_content_change=on_content)

            ta.handle_key(_key("X"))
            ta.undo()

            before_redo = content_change_count

            ta.redo()

            assert content_change_count >= before_redo
            assert ta.plain_text == "X"
            ta.destroy()

        def test_should_fire_on_content_change_when_setting_value_programmatically(self):
            """Content change fires when set_text is called."""
            content_change_count = 0

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("Initial", on_content_change=on_content)
            initial_count = content_change_count

            ta.set_text("Updated")

            assert content_change_count > initial_count
            assert ta.plain_text == "Updated"
            ta.destroy()

        def test_should_fire_on_content_change_when_deleting_selection(self):
            """Content change fires when deleting a selection."""
            content_change_count = 0

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("Hello World", on_content_change=on_content)

            # Select first 5 characters via shift+right
            for _ in range(5):
                ta.handle_key(_key("right", shift=True))

            before_delete = content_change_count

            ta.handle_key(_key("backspace"))

            assert content_change_count > before_delete
            assert ta.plain_text == " World"
            ta.destroy()

        def test_should_update_event_handler_when_set_dynamically(self):
            """Dynamic handler update via on_content_change property setter."""
            first_handler_called = False
            second_handler_called = False

            def first_handler(text):
                nonlocal first_handler_called
                first_handler_called = True

            def second_handler(text):
                nonlocal second_handler_called
                second_handler_called = True

            ta = _make("", on_content_change=first_handler)

            ta.handle_key(_key("A"))
            assert first_handler_called is True

            ta.on_content_change = second_handler

            ta.handle_key(_key("B"))
            assert second_handler_called is True
            ta.destroy()

        def test_should_not_fire_when_handler_is_undefined(self):
            """No crash when handler is None; text still changes."""
            ta = _make("", on_content_change=None)

            ta.handle_key(_key("X"))
            assert ta.plain_text == "X"
            ta.destroy()

        def test_should_fire_exactly_once_when_setting_via_setter_and_pressing_a_key(self):
            """Content change fires exactly once when set via setter then key pressed."""
            content_change_count = 0

            ta = _make("")

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta.on_content_change = on_content

            ta.handle_key(_key("X"))

            assert content_change_count == 1
            assert ta.plain_text == "X"
            ta.destroy()

    class TestChangeEventsOnSubmit:
        """Change Events - onSubmit"""

        def test_should_fire_on_submit_with_default_keybinding_meta_enter(self):
            """Submit fires on Meta+Enter (alt+return in terminal convention)."""
            submit_count = 0

            def on_submit(text):
                nonlocal submit_count
                submit_count += 1

            ta = _make("Test content", on_submit=on_submit)
            initial_count = submit_count

            # Meta+Enter -> alt+return in terminal convention
            ta.handle_key(_key("return", alt=True))

            assert submit_count == initial_count + 1
            assert ta.plain_text == "Test content"
            ta.destroy()

        def test_should_fire_on_submit_with_alternative_keybinding_meta_return(self):
            """Submit fires on Meta+Return (alt+return in terminal convention)."""
            submit_count = 0

            def on_submit(text):
                nonlocal submit_count
                submit_count += 1

            ta = _make("Test", on_submit=on_submit)

            ta.handle_key(_key("return", alt=True))

            assert submit_count == 1
            ta.destroy()

        def test_should_not_insert_newline_when_submitting(self):
            """Submit does not insert a newline."""
            submit_count = 0

            def on_submit(text):
                nonlocal submit_count
                submit_count += 1

            ta = _make("Test", on_submit=on_submit)
            ta.goto_line(9999)
            ta.goto_line_end()

            ta.handle_key(_key("return", alt=True))

            assert submit_count == 1
            assert ta.plain_text == "Test"
            ta.destroy()

        def test_should_update_handler_via_setter(self):
            """Handler can be updated via on_submit property setter."""
            first_handler_called = False
            second_handler_called = False

            def first_handler(text):
                nonlocal first_handler_called
                first_handler_called = True

            def second_handler(text):
                nonlocal second_handler_called
                second_handler_called = True

            ta = _make("", on_submit=first_handler)

            ta.handle_key(_key("return", alt=True))
            assert first_handler_called is True

            ta.on_submit = second_handler

            ta.handle_key(_key("return", alt=True))
            assert second_handler_called is True
            ta.destroy()

        def test_should_not_fire_when_handler_is_undefined(self):
            """No crash when on_submit is None."""
            ta = _make("Test", on_submit=None)

            ta.handle_key(_key("return", alt=True))
            assert ta.plain_text == "Test"
            ta.destroy()

        def test_should_support_custom_keybinding_for_submit(self):
            """Custom keybinding ctrl+s triggers submit."""
            submit_count = 0

            def on_submit(text):
                nonlocal submit_count
                submit_count += 1

            ta = _make(
                "Test",
                key_bindings=[KeyBinding(name="s", action="submit", ctrl=True)],
                on_submit=on_submit,
            )

            ta.handle_key(_key("s", ctrl=True))

            assert submit_count == 1
            ta.destroy()

        def test_should_get_current_handler_via_getter(self):
            """on_submit property getter returns the current handler."""

            def handler(text):
                pass

            ta = _make("", on_submit=handler)

            assert ta.on_submit is handler
            ta.destroy()

        def test_should_allow_removing_handler_by_setting_to_undefined(self):
            """Setting on_submit to None removes the handler."""
            submit_count = 0

            def on_submit(text):
                nonlocal submit_count
                submit_count += 1

            ta = _make("", on_submit=on_submit)

            ta.handle_key(_key("return", alt=True))
            assert submit_count == 1

            ta.on_submit = None

            ta.handle_key(_key("return", alt=True))
            assert submit_count == 1  # Should not increment
            ta.destroy()

    class TestCombinedCursorAndContentEvents:
        """Combined cursor and content events"""

        def test_should_fire_both_on_cursor_change_and_on_content_change_when_typing(self):
            """Typing fires both cursor and content change events."""
            cursor_change_count = 0
            content_change_count = 0

            def on_cursor(pos):
                nonlocal cursor_change_count
                cursor_change_count += 1

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("", on_cursor_change=on_cursor, on_content_change=on_content)
            initial_cursor = cursor_change_count
            initial_content = content_change_count

            ta.handle_key(_key("H"))

            assert cursor_change_count > initial_cursor
            assert content_change_count > initial_content
            ta.destroy()

        def test_should_fire_on_cursor_change_but_not_on_content_change_when_only_moving_cursor(
            self,
        ):
            """Moving cursor fires cursor change but not content change."""
            cursor_change_count = 0
            content_change_count = 0

            def on_cursor(pos):
                nonlocal cursor_change_count
                cursor_change_count += 1

            def on_content(text):
                nonlocal content_change_count
                content_change_count += 1

            ta = _make("Test", on_cursor_change=on_cursor, on_content_change=on_content)
            initial_cursor = cursor_change_count
            initial_content = content_change_count

            ta.move_cursor_right()

            assert cursor_change_count > initial_cursor
            assert content_change_count == initial_content  # Should not change
            ta.destroy()

        def test_should_track_events_through_complex_editing_sequence(self):
            """Complex editing sequence fires appropriate events."""
            events = []

            def on_cursor(pos):
                events.append("cursor")

            def on_content(text):
                events.append("content")

            ta = _make("", on_cursor_change=on_cursor, on_content_change=on_content)
            events.clear()  # Clear initial events

            # Type "Hello"
            ta.handle_key(_key("H"))
            ta.handle_key(_key("e"))
            ta.handle_key(_key("l"))
            ta.handle_key(_key("l"))
            ta.handle_key(_key("o"))

            # Move cursor
            ta.move_cursor_left()
            ta.move_cursor_left()

            # Backspace
            ta.handle_key(_key("backspace"))

            cursor_events = [e for e in events if e == "cursor"]
            content_events = [e for e in events if e == "content"]

            assert len(cursor_events) > 0
            assert len(content_events) > 0
            ta.destroy()
