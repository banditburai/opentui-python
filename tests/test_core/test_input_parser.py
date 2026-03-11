"""Tests for terminal input sequence parsing."""

from unittest.mock import patch

from opentui.events import MouseButton, PasteEvent
from opentui.input import InputHandler


def test_rxvt_mouse_wheel_up_emits_scroll_event():
    handler = InputHandler()
    seen = []
    handler.on_mouse(lambda event: seen.append(event))

    handled = handler._handle_rxvt_mouse("64;63;15M")

    assert handled is True
    assert len(seen) == 1
    event = seen[0]
    assert event.type == "scroll"
    assert event.button == MouseButton.WHEEL_UP
    assert event.scroll_direction == "up"
    assert event.scroll_delta == -1
    assert event.x == 62
    assert event.y == 14


def test_rxvt_mouse_wheel_down_emits_scroll_event():
    handler = InputHandler()
    seen = []
    handler.on_mouse(lambda event: seen.append(event))

    handled = handler._handle_rxvt_mouse("65;63;15M")

    assert handled is True
    assert len(seen) == 1
    event = seen[0]
    assert event.type == "scroll"
    assert event.button == MouseButton.WHEEL_DOWN
    assert event.scroll_direction == "down"
    assert event.scroll_delta == 1
    assert event.x == 62
    assert event.y == 14


def test_rxvt_mouse_wheel_left_emits_horizontal_scroll_event():
    handler = InputHandler()
    seen = []
    handler.on_mouse(lambda event: seen.append(event))

    handled = handler._handle_rxvt_mouse("66;63;15M")

    assert handled is True
    assert len(seen) == 1
    event = seen[0]
    assert event.type == "scroll"
    assert event.button == MouseButton.WHEEL_LEFT
    assert event.scroll_direction == "left"
    assert event.scroll_delta == -1
    assert event.x == 62
    assert event.y == 14


def test_rxvt_mouse_wheel_right_emits_horizontal_scroll_event():
    handler = InputHandler()
    seen = []
    handler.on_mouse(lambda event: seen.append(event))

    handled = handler._handle_rxvt_mouse("67;63;15M")

    assert handled is True
    assert len(seen) == 1
    event = seen[0]
    assert event.type == "scroll"
    assert event.button == MouseButton.WHEEL_RIGHT
    assert event.scroll_direction == "right"
    assert event.scroll_delta == 1
    assert event.x == 62
    assert event.y == 14


def test_modify_other_keys_shift_enter_emits_shifted_return():
    handler = InputHandler()
    seen = []
    handler.on_key(lambda event: seen.append(event))

    handled = handler._dispatch_csi_sequence("27;2;13~")

    assert handled is True
    assert len(seen) == 1
    event = seen[0]
    assert event.key == "return"
    assert event.shift is True
    assert event.ctrl is False
    assert event.alt is False
    assert event.code == "\x1b[27;2;13~"


def test_kitty_keyboard_shift_enter_emits_shifted_return():
    handler = InputHandler()
    seen = []
    handler.on_key(lambda event: seen.append(event))

    handled = handler._dispatch_csi_sequence("13;2u")

    assert handled is True
    assert len(seen) == 1
    event = seen[0]
    assert event.key == "return"
    assert event.shift is True
    assert event.ctrl is False
    assert event.alt is False
    assert event.event_type == "press"
    assert event.code == "\x1b[13;2u"


def test_poll_treats_linefeed_as_shift_enter():
    handler = InputHandler()
    handler._running = True
    handler._fd = 0
    seen = []
    handler.on_key(lambda event: seen.append(event))

    with (
        patch("opentui.input.select.select", return_value=([0], [], [])),
        patch.object(handler, "_read_char", return_value="\n"),
    ):
        handled = handler.poll()

    assert handled is True
    assert len(seen) == 1
    event = seen[0]
    assert event.key == "return"
    assert event.shift is True
    assert event.code == "\n"


def test_bracketed_paste_emits_single_paste_event():
    handler = InputHandler()
    seen: list[PasteEvent] = []
    handler.on_paste(lambda event: seen.append(event))

    handled = handler._dispatch_csi_sequence("200~")
    for ch in "hello\nworld":
        handler._consume_bracketed_paste_char(ch)

    assert handled is True
    assert seen == []

    for ch in "\x1b[201~":
        handler._consume_bracketed_paste_char(ch)

    assert len(seen) == 1
    assert seen[0].text == "hello\nworld"


def test_escape_apc_sequence_is_consumed_silently():
    handler = InputHandler()
    seen = []
    handler.on_key(lambda event: seen.append(event))
    handler._fd = 0

    chars = iter(["_", "G", "i", "=", "1", ";", "O", "K", "\x1b", "\\"])

    def fake_read_char():
        return next(chars)

    with patch("opentui.input.select.select", return_value=([0], [], [])):
        with patch.object(handler, "_read_char", side_effect=fake_read_char):
            handled = handler._handle_escape()

    assert handled is True
    assert seen == []
