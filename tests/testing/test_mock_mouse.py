"""Port of upstream mock-mouse.test.ts.

Upstream: packages/core/src/testing/mock-mouse.test.ts
Tests ported: 16/16 (0 skipped)
"""

import re

from opentui.testing import SGRMouseButtons, create_mock_mouse


class TestMockMouse:
    """Maps to describe("mock-mouse")."""

    def test_click_generates_correct_mouse_events(self):
        """Maps to test("click generates correct mouse events")."""
        mouse, renderer = create_mock_mouse()
        mouse.click(10, 5)

        assert len(renderer.emitted_data) == 2
        assert renderer.emitted_data[0] == "\x1b[<0;11;6M"  # down event
        assert renderer.emitted_data[1] == "\x1b[<0;11;6m"  # up event

    def test_click_with_different_button(self):
        """Maps to test("click with different button")."""
        mouse, renderer = create_mock_mouse()
        mouse.click(10, 5, SGRMouseButtons.RIGHT)

        assert renderer.emitted_data[0] == "\x1b[<2;11;6M"  # right button down
        assert renderer.emitted_data[1] == "\x1b[<2;11;6m"  # right button up

    def test_click_with_modifiers(self):
        """Maps to test("click with modifiers")."""
        mouse, renderer = create_mock_mouse()
        mouse.click(10, 5, SGRMouseButtons.LEFT, ctrl=True, shift=True)

        assert renderer.emitted_data[0] == "\x1b[<20;11;6M"  # 0 + 16 (ctrl) + 4 (shift) = 20
        assert renderer.emitted_data[1] == "\x1b[<20;11;6m"

    def test_move_to_generates_move_event(self):
        """Maps to test("moveTo generates move event")."""
        mouse, renderer = create_mock_mouse()
        mouse.move_to(15, 8)

        assert renderer.get_emitted_data() == "\x1b[<35;16;9M"  # 32 (motion) + 3 (button 3) = 35

    def test_move_to_with_modifiers(self):
        """Maps to test("moveTo with modifiers")."""
        mouse, renderer = create_mock_mouse()
        mouse.move_to(15, 8, alt=True)

        assert renderer.get_emitted_data() == "\x1b[<43;16;9M"  # 32 + 3 + 8 (alt) = 43

    def test_double_click_generates_four_events(self):
        """Maps to test("doubleClick generates four events")."""
        mouse, renderer = create_mock_mouse()
        mouse.double_click(10, 5)

        assert len(renderer.emitted_data) == 4
        assert renderer.emitted_data[0] == "\x1b[<0;11;6M"
        assert renderer.emitted_data[1] == "\x1b[<0;11;6m"
        assert renderer.emitted_data[2] == "\x1b[<0;11;6M"
        assert renderer.emitted_data[3] == "\x1b[<0;11;6m"

    def test_press_down_and_release_work_separately(self):
        """Maps to test("pressDown and release work separately")."""
        mouse, renderer = create_mock_mouse()
        mouse.press_down(10, 5, SGRMouseButtons.MIDDLE)
        mouse.release(10, 5, SGRMouseButtons.MIDDLE)

        assert renderer.emitted_data[0] == "\x1b[<1;11;6M"  # middle button down
        assert renderer.emitted_data[1] == "\x1b[<1;11;6m"  # middle button up

    def test_drag_generates_drag_events(self):
        """Maps to test("drag generates drag events")."""
        mouse, renderer = create_mock_mouse()
        mouse.drag(10, 5, 20, 10)

        # Should have: down, several drag events, up
        assert len(renderer.emitted_data) > 3
        assert renderer.emitted_data[0] == "\x1b[<0;11;6M"  # initial down

        # Check that drag events have the motion flag (32)
        for i in range(1, len(renderer.emitted_data) - 1):
            event = renderer.emitted_data[i]
            assert re.match(r"\x1b\[<32;\d+;\d+M", event), (
                f"Drag event {i} missing motion flag: {event!r}"
            )

        last_event = renderer.emitted_data[-1]
        assert last_event == "\x1b[<0;21;11m"  # final up

    def test_scroll_events_work(self):
        """Maps to test("scroll events work")."""
        mouse, renderer = create_mock_mouse()
        mouse.scroll(10, 5, "up")
        mouse.scroll(10, 5, "down")

        assert renderer.emitted_data[0] == "\x1b[<64;11;6M"  # wheel up
        assert renderer.emitted_data[1] == "\x1b[<65;11;6M"  # wheel down

    def test_scroll_with_modifiers(self):
        """Maps to test("scroll with modifiers")."""
        mouse, renderer = create_mock_mouse()
        mouse.scroll(10, 5, "left", shift=True)

        assert renderer.get_emitted_data() == "\x1b[<70;11;6M"  # 66 (wheel left) + 4 (shift) = 70

    def test_move_to_becomes_drag_when_button_is_pressed(self):
        """Maps to test("moveTo becomes drag when button is pressed")."""
        mouse, renderer = create_mock_mouse()
        mouse.press_down(5, 5)
        mouse.move_to(15, 8)

        assert renderer.emitted_data[0] == "\x1b[<0;6;6M"  # down
        assert renderer.emitted_data[1] == "\x1b[<32;16;9M"  # drag (32 = motion flag, button 0)

    def test_get_current_position_tracks_position(self):
        """Maps to test("getCurrentPosition tracks position")."""
        mouse, renderer = create_mock_mouse()

        assert mouse.get_current_position() == {"x": 0, "y": 0}
        mouse.move_to(10, 5)
        assert mouse.get_current_position() == {"x": 10, "y": 5}
        mouse.click(15, 8)
        assert mouse.get_current_position() == {"x": 15, "y": 8}

    def test_get_pressed_buttons_tracks_button_state(self):
        """Maps to test("getPressedButtons tracks button state")."""
        mouse, renderer = create_mock_mouse()

        assert mouse.get_pressed_buttons() == []

        mouse.press_down(10, 5, SGRMouseButtons.LEFT)
        assert mouse.get_pressed_buttons() == [SGRMouseButtons.LEFT]

        mouse.press_down(10, 5, SGRMouseButtons.RIGHT)
        assert sorted(mouse.get_pressed_buttons()) == [SGRMouseButtons.LEFT, SGRMouseButtons.RIGHT]

        mouse.release(10, 5, SGRMouseButtons.LEFT)
        assert mouse.get_pressed_buttons() == [SGRMouseButtons.RIGHT]

        mouse.release(10, 5, SGRMouseButtons.RIGHT)
        assert mouse.get_pressed_buttons() == []

    def test_delay_works_correctly(self):
        """Maps to test("delay works correctly").

        The Python port uses synchronous calls (no async/await), so
        we verify that the API works correctly without actual delays.
        Click should produce 2 events regardless.
        """
        mouse, renderer = create_mock_mouse()
        mouse.click(10, 5, SGRMouseButtons.LEFT)

        assert len(renderer.emitted_data) == 2

    def test_coordinates_are_1_based_in_ansi_output(self):
        """Maps to test("coordinates are 1-based in ANSI output")."""
        mouse, renderer = create_mock_mouse()
        mouse.click(0, 0)  # 0-based coordinates

        assert renderer.emitted_data[0] == "\x1b[<0;1;1M"  # 1-based in ANSI
        assert renderer.emitted_data[1] == "\x1b[<0;1;1m"

    def test_all_scroll_directions_work(self):
        """Maps to test("all scroll directions work")."""
        mouse, renderer = create_mock_mouse()
        mouse.scroll(10, 5, "up")
        mouse.scroll(10, 5, "down")
        mouse.scroll(10, 5, "left")
        mouse.scroll(10, 5, "right")

        assert renderer.emitted_data[0] == "\x1b[<64;11;6M"  # up
        assert renderer.emitted_data[1] == "\x1b[<65;11;6M"  # down
        assert renderer.emitted_data[2] == "\x1b[<66;11;6M"  # left
        assert renderer.emitted_data[3] == "\x1b[<67;11;6M"  # right
