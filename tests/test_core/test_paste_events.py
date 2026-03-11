"""Tests for structured paste event delivery."""

from opentui.events import AttachmentPayload, PasteEvent
from opentui.hooks import clear_paste_handlers, get_paste_handlers, use_paste
from opentui.input import InputHandler


def test_input_handler_emits_structured_paste_event():
    handler = InputHandler()
    seen = []
    handler.on_paste(lambda event: seen.append(event))

    handler._emit_paste("hello")

    assert len(seen) == 1
    assert isinstance(seen[0], PasteEvent)
    assert seen[0].text == "hello"
    assert seen[0].attachments == []


def test_use_paste_registers_structured_event_handler():
    clear_paste_handlers()
    seen = []

    use_paste(lambda event: seen.append(event))

    handlers = get_paste_handlers()
    handlers[0](PasteEvent(text="clip"))

    assert len(seen) == 1
    assert isinstance(seen[0], PasteEvent)
    assert seen[0].text == "clip"


def test_paste_event_can_carry_attachment_payload():
    event = PasteEvent(
        attachments=[
            AttachmentPayload(kind="file", path="/tmp/example.png", mime_type="image/png"),
        ]
    )

    assert event.text is None
    assert len(event.attachments) == 1
    assert event.attachments[0].path == "/tmp/example.png"
