"""Port of upstream integration.test.ts.

Upstream: packages/core/src/testing/integration.test.ts
Tests ported: 11/11 (0 skipped)
"""

from opentui.testing import (
    SGRMouseButtons,
    SGRMouseParser,
    create_mock_mouse,
)


class TestMockMouseParserIntegration:
    """Maps to describe("mock-mouse + parser integration")."""

    def test_simple_click_is_correctly_parsed(self):
        """Maps to test("simple click is correctly parsed")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.click(10, 5)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) == 2
        assert events[0] == {
            "type": "down",
            "button": 0,
            "x": 10,
            "y": 5,
            "modifiers": {"shift": False, "alt": False, "ctrl": False},
            "scroll": None,
        }
        assert events[1] == {
            "type": "up",
            "button": 0,
            "x": 10,
            "y": 5,
            "modifiers": {"shift": False, "alt": False, "ctrl": False},
            "scroll": None,
        }

    def test_double_click_is_correctly_parsed(self):
        """Maps to test("double click is correctly parsed")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.double_click(10, 5)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) == 4
        for event in events:
            assert event["x"] == 10
            assert event["y"] == 5
            assert event["button"] == 0
        assert [e["type"] for e in events] == ["down", "up", "down", "up"]

    def test_press_down_and_release_separately_are_correctly_parsed(self):
        """Maps to test("pressDown and release separately are correctly parsed")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.press_down(10, 5, SGRMouseButtons.MIDDLE)
        mouse.release(10, 5, SGRMouseButtons.MIDDLE)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) == 2
        assert events[0] == {
            "type": "down",
            "button": 1,  # MIDDLE
            "x": 10,
            "y": 5,
            "modifiers": {"shift": False, "alt": False, "ctrl": False},
            "scroll": None,
        }
        assert events[1] == {
            "type": "up",
            "button": 1,
            "x": 10,
            "y": 5,
            "modifiers": {"shift": False, "alt": False, "ctrl": False},
            "scroll": None,
        }

    def test_different_buttons_work_correctly(self):
        """Maps to test("different buttons work correctly")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.click(10, 5, SGRMouseButtons.RIGHT)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) == 2
        for event in events:
            assert event["button"] == 2  # RIGHT
            assert event["x"] == 10
            assert event["y"] == 5

    def test_all_scroll_directions_are_correctly_parsed(self):
        """Maps to test("all scroll directions are correctly parsed")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()

        mouse.scroll(15, 8, "up")
        mouse.scroll(15, 8, "down")
        mouse.scroll(15, 8, "left")
        mouse.scroll(15, 8, "right")

        events = parser.parse_all(renderer.get_emitted_data())
        assert len(events) == 4

        expected_directions = ["up", "down", "left", "right"]
        # button & 3: up=64&3=0, down=65&3=1, left=66&3=2, right=67&3=3→0 (but actually 67&3=3)
        expected_buttons = [0, 1, 2, 3]
        for i, event in enumerate(events):
            assert event["type"] == "scroll"
            assert event["button"] == expected_buttons[i]
            assert event["x"] == 15
            assert event["y"] == 8
            assert event["scroll"] == {"direction": expected_directions[i], "delta": 1}

    def test_scroll_with_modifiers_is_correctly_parsed(self):
        """Maps to test("scroll with modifiers is correctly parsed")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.scroll(15, 8, "left", shift=True)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) == 1
        assert events[0] == {
            "type": "scroll",
            "button": 2,  # WHEEL_LEFT (66) & 3 = 2
            "x": 15,
            "y": 8,
            "modifiers": {"shift": True, "alt": False, "ctrl": False},
            "scroll": {"direction": "left", "delta": 1},
        }

    def test_drag_events_are_correctly_parsed(self):
        """Maps to test("drag events are correctly parsed")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.drag(5, 5, 15, 10)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) > 3
        assert events[0]["type"] == "down"
        assert events[0]["button"] == 0
        assert events[0]["x"] == 5
        assert events[0]["y"] == 5

        for i in range(1, len(events) - 1):
            assert events[i]["type"] == "drag"
            assert events[i]["button"] == 0

        last_event = events[-1]
        assert last_event["type"] == "up"
        assert last_event["x"] == 15
        assert last_event["y"] == 10

    def test_move_to_without_button_press_generates_move_events(self):
        """Maps to test("moveTo without button press generates move events")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.move_to(15, 8)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) == 1
        assert events[0] == {
            "type": "move",
            "button": 0,
            "x": 15,
            "y": 8,
            "modifiers": {"shift": False, "alt": False, "ctrl": False},
            "scroll": None,
        }

    def test_move_to_with_button_press_generates_drag_events(self):
        """Maps to test("moveTo with button press generates drag events")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.press_down(5, 5)
        mouse.move_to(15, 8)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) == 2
        assert events[0]["type"] == "down"
        assert events[1]["type"] == "drag"
        assert events[1]["x"] == 15
        assert events[1]["y"] == 8

    def test_all_modifier_combinations_work(self):
        """Maps to test("all modifier combinations work")."""
        modifier_combos = [
            {"shift": True},
            {"alt": True},
            {"ctrl": True},
            {"shift": True, "alt": True},
            {"shift": True, "ctrl": True},
            {"alt": True, "ctrl": True},
            {"shift": True, "alt": True, "ctrl": True},
        ]

        for modifiers in modifier_combos:
            mouse, renderer = create_mock_mouse()
            parser = SGRMouseParser()
            mouse.click(10, 5, SGRMouseButtons.LEFT, **modifiers)
            events = parser.parse_all(renderer.get_emitted_data())

            assert len(events) == 2
            expected_mods = {
                "shift": modifiers.get("shift", False),
                "alt": modifiers.get("alt", False),
                "ctrl": modifiers.get("ctrl", False),
            }
            for event in events:
                assert event["modifiers"] == expected_mods

    def test_drag_with_different_button_and_modifiers(self):
        """Maps to test("drag with different button and modifiers")."""
        mouse, renderer = create_mock_mouse()
        parser = SGRMouseParser()
        mouse.drag(5, 5, 15, 10, SGRMouseButtons.RIGHT, alt=True)
        events = parser.parse_all(renderer.get_emitted_data())

        assert len(events) > 3
        for event in events:
            assert event["button"] == 2  # RIGHT
            assert event["modifiers"]["alt"] is True
