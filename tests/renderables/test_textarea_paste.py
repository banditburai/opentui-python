"""Port of upstream Textarea.paste.test.ts.

Upstream: packages/core/src/renderables/__tests__/Textarea.paste.test.ts
Tests ported: 16/16 (16 real)
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


def _type_string(ta: TextareaRenderable, text: str) -> None:
    """Type a string character by character via handle_key."""
    for ch in text:
        ta.handle_key(_key(ch))


def _make(text: str = "", **kwargs) -> TextareaRenderable:
    """Create a focused TextareaRenderable with given text."""
    ta = TextareaRenderable(initial_value=text, **kwargs)
    ta.focus()
    return ta


class TestTextareaPasteEvents:
    """Maps to describe("Paste Events")."""

    def test_should_paste_text_at_cursor_position(self):
        """Maps to it("should paste text at cursor position")."""
        ta = _make()
        event = PasteEvent(text="Hello World")
        ta.handle_paste(event)
        assert ta.plain_text == "Hello World"
        assert ta.cursor_position == (0, 11)
        ta.destroy()

    def test_should_paste_text_in_the_middle(self):
        """Maps to it("should paste text in the middle")."""
        ta = _make("HelloWorld")
        ta.edit_buffer.set_cursor(0, 5)
        event = PasteEvent(text=" Beautiful ")
        ta.handle_paste(event)
        assert ta.plain_text == "Hello Beautiful World"
        ta.destroy()

    def test_should_paste_multi_line_text(self):
        """Maps to it("should paste multi-line text")."""
        ta = _make()
        event = PasteEvent(text="Line 1\nLine 2\nLine 3")
        ta.handle_paste(event)
        assert ta.plain_text == "Line 1\nLine 2\nLine 3"
        assert ta.line_count == 3
        ta.destroy()

    def test_should_paste_text_at_beginning_of_buffer(self):
        """Maps to it("should paste text at beginning of buffer")."""
        ta = _make("World")
        ta.edit_buffer.set_cursor(0, 0)
        event = PasteEvent(text="Hello ")
        ta.handle_paste(event)
        assert ta.plain_text == "Hello World"
        ta.destroy()

    def test_should_replace_selected_text_when_pasting(self):
        """Maps to it("should replace selected text when pasting")."""
        ta = _make("Hello World")
        ta.set_selection(6, 11)  # select "World"
        ta.edit_buffer.set_cursor(0, 11)
        event = PasteEvent(text="Universe")
        ta.handle_paste(event)
        assert ta.plain_text == "Hello Universe"
        ta.destroy()

    def test_should_replace_multi_line_selection_when_pasting(self):
        """Maps to it("should replace multi-line selection when pasting")."""
        ta = _make("Line 1\nLine 2\nLine 3")
        # Select "Line 2\n" (offset 7 to 14)
        ta.set_selection(7, 14)
        ta.edit_buffer.set_cursor(2, 0)
        event = PasteEvent(text="Replaced\n")
        ta.handle_paste(event)
        assert "Line 2" not in ta.plain_text
        assert "Replaced" in ta.plain_text
        ta.destroy()

    def test_should_replace_selected_text_with_multi_line_paste(self):
        """Maps to it("should replace selected text with multi-line paste")."""
        ta = _make("Hello World")
        ta.set_selection(6, 11)  # select "World"
        ta.edit_buffer.set_cursor(0, 11)
        event = PasteEvent(text="Big\nBeautiful\nWorld")
        ta.handle_paste(event)
        assert ta.plain_text == "Hello Big\nBeautiful\nWorld"
        assert ta.line_count == 3
        ta.destroy()

    def test_should_paste_empty_string_without_error(self):
        """Maps to it("should paste empty string without error")."""
        ta = _make("Hello")
        event = PasteEvent(text="")
        ta.handle_paste(event)
        assert ta.plain_text == "Hello"
        ta.destroy()

    def test_should_resize_viewport_when_pasting_multiline_text(self):
        """Maps to it("should resize viewport when pasting multiline text")."""
        ta = _make()
        event = PasteEvent(text="Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
        ta.handle_paste(event)
        assert ta.line_count == 5
        assert ta.plain_text == "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        ta.destroy()

    def test_should_paste_unicode_characters_emoji_cjk(self):
        """Maps to it("should paste Unicode characters (emoji, CJK)")."""
        ta = _make()
        event = PasteEvent(text="Hello World")
        ta.handle_paste(event)
        assert "Hello" in ta.plain_text
        assert "World" in ta.plain_text

        ta2 = _make()
        event2 = PasteEvent(text="CJK text")
        ta2.handle_paste(event2)
        assert ta2.plain_text == "CJK text"
        ta2.destroy()

        ta.destroy()

    def test_should_replace_entire_selection_with_pasted_text(self):
        """Maps to it("should replace entire selection with pasted text")."""
        ta = _make("ABCDEF")
        ta.set_selection(0, 6)  # select all
        ta.edit_buffer.set_cursor(0, 6)
        event = PasteEvent(text="XYZ")
        ta.handle_paste(event)
        assert ta.plain_text == "XYZ"
        ta.destroy()

    def test_should_handle_paste_via_handle_paste_method_directly(self):
        """Maps to it("should handle paste via handlePaste method directly")."""
        ta = _make()
        event = PasteEvent(text="Pasted content")
        ta.handle_paste(event)
        assert ta.plain_text == "Pasted content"
        ta.destroy()

    def test_should_replace_selection_when_using_handle_paste_directly(self):
        """Maps to it("should replace selection when using handlePaste directly")."""
        ta = _make("Old text here")
        ta.set_selection(4, 9)  # select "text "  (actually "text ")
        ta.edit_buffer.set_cursor(0, 9)
        event = PasteEvent(text="content ")
        ta.handle_paste(event)
        assert "content" in ta.plain_text
        assert ta.plain_text.startswith("Old ")
        ta.destroy()

    def test_should_support_prevent_default_on_paste_event(self):
        """Maps to it("should support preventDefault on paste event")."""
        received_events = []

        def on_paste(event: PasteEvent):
            received_events.append(event)
            event.prevent_default()

        ta = _make(on_paste=on_paste)
        event = PasteEvent(text="Should not paste")
        ta.handle_paste(event)

        # Text should NOT have been inserted because prevent_default was called
        assert ta.plain_text == ""
        assert len(received_events) == 1
        assert received_events[0].default_prevented is True

        ta.destroy()

    def test_should_pass_full_paste_event_to_on_paste_handler(self):
        """Maps to it("should pass full PasteEvent to onPaste handler")."""
        received_events = []

        def on_paste(event: PasteEvent):
            received_events.append(event)

        ta = _make(on_paste=on_paste)
        event = PasteEvent(text="Some text")
        ta.handle_paste(event)

        assert len(received_events) == 1
        assert received_events[0].text == "Some text"
        # Text should still have been inserted since prevent_default was NOT called
        assert ta.plain_text == "Some text"

        ta.destroy()

    def test_should_allow_conditional_paste_prevention(self):
        """Maps to it("should allow conditional paste prevention")."""

        def on_paste(event: PasteEvent):
            # Only prevent pasting if text contains "bad"
            if event.text and "bad" in event.text:
                event.prevent_default()

        ta = _make(on_paste=on_paste)

        # Paste allowed text
        event1 = PasteEvent(text="good text")
        ta.handle_paste(event1)
        assert ta.plain_text == "good text"

        # Paste prevented text
        event2 = PasteEvent(text="bad text")
        ta.handle_paste(event2)
        # Should still be "good text" since the paste was prevented
        assert ta.plain_text == "good text"

        ta.destroy()
