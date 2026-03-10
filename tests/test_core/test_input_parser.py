"""Tests for terminal input sequence parsing."""

from opentui.events import MouseButton
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
