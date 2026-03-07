"""Tests for the TUI input area component."""

from opentui.components import Box, Text
from opentui.events import KeyEvent

from opencode.tui.components.input import (
    InputState,
    input_area,
)


# --- InputState ---


class TestInputState:
    def test_initial_empty(self):
        state = InputState()
        assert state.text == ""
        assert state.history == []
        assert state.history_index == -1

    def test_set_text(self):
        state = InputState()
        state.text = "hello"
        assert state.text == "hello"

    def test_submit_clears_and_returns(self):
        state = InputState()
        state.text = "send this"
        result = state.submit()
        assert result == "send this"
        assert state.text == ""

    def test_submit_adds_to_history(self):
        state = InputState()
        state.text = "first"
        state.submit()
        state.text = "second"
        state.submit()
        assert state.history == ["first", "second"]

    def test_submit_empty_returns_empty(self):
        state = InputState()
        result = state.submit()
        assert result == ""
        assert state.history == []  # empty strings not added

    def test_history_up(self):
        state = InputState()
        state.text = "one"
        state.submit()
        state.text = "two"
        state.submit()
        # Navigate up through history
        state.history_up()
        assert state.text == "two"
        state.history_up()
        assert state.text == "one"

    def test_history_up_at_top_stays(self):
        state = InputState()
        state.text = "only"
        state.submit()
        state.history_up()
        assert state.text == "only"
        state.history_up()  # already at top
        assert state.text == "only"

    def test_history_down(self):
        state = InputState()
        state.text = "one"
        state.submit()
        state.text = "two"
        state.submit()
        state.history_up()
        state.history_up()
        assert state.text == "one"
        state.history_down()
        assert state.text == "two"

    def test_history_down_past_end_clears(self):
        state = InputState()
        state.text = "cmd"
        state.submit()
        state.history_up()
        assert state.text == "cmd"
        state.history_down()
        assert state.text == ""

    def test_handle_key_enter_submits(self):
        state = InputState()
        state.text = "hello"
        submitted = []
        state.on_submit = submitted.append
        event = KeyEvent(key="return")
        state.handle_key(event)
        assert submitted == ["hello"]
        assert state.text == ""

    def test_handle_key_shift_enter_inserts_newline(self):
        state = InputState()
        state.text = "line1"
        event = KeyEvent(key="return", shift=True)
        state.handle_key(event)
        assert state.text == "line1\n"

    def test_handle_key_up_navigates_history(self):
        state = InputState()
        state.text = "prev"
        state.submit()
        event = KeyEvent(key="up")
        state.handle_key(event)
        assert state.text == "prev"

    def test_handle_key_down_navigates_history(self):
        state = InputState()
        state.text = "prev"
        state.submit()
        state.history_up()
        event = KeyEvent(key="down")
        state.handle_key(event)
        assert state.text == ""

    def test_handle_key_regular_char(self):
        state = InputState()
        event = KeyEvent(key="a")
        state.handle_key(event)
        assert state.text == "a"

    def test_handle_key_backspace(self):
        state = InputState()
        state.text = "ab"
        event = KeyEvent(key="backspace")
        state.handle_key(event)
        assert state.text == "a"

    def test_handle_key_ctrl_c_clears(self):
        state = InputState()
        state.text = "something"
        event = KeyEvent(key="c", ctrl=True)
        state.handle_key(event)
        assert state.text == ""


# --- input_area rendering ---


class TestInputArea:
    def test_returns_box(self):
        state = InputState()
        widget = input_area(state=state)
        assert isinstance(widget, Box)

    def test_shows_placeholder_when_empty(self):
        state = InputState()
        widget = input_area(state=state, placeholder="Type here...")
        all_text = _collect_text(widget)
        assert any("Type here..." in t for t in all_text)

    def test_shows_text_when_filled(self):
        state = InputState()
        state.text = "my message"
        widget = input_area(state=state, placeholder="Type here...")
        all_text = _collect_text(widget)
        assert any("my message" in t for t in all_text)
        # Placeholder should NOT appear when there's text
        assert not any("Type here..." in t for t in all_text)

    def test_multiline_text(self):
        state = InputState()
        state.text = "line1\nline2"
        widget = input_area(state=state)
        all_text = _collect_text(widget)
        assert any("line1" in t for t in all_text)
        assert any("line2" in t for t in all_text)

    def test_accepts_kwargs(self):
        state = InputState()
        widget = input_area(state=state, padding_left=2)
        assert isinstance(widget, Box)


# --- Helpers ---


def _collect_text(node, depth=0):
    """Recursively collect all text content from a component tree."""
    if depth > 10:
        return []
    texts = []
    if isinstance(node, Text):
        texts.append(getattr(node, "_content", ""))
    if hasattr(node, "get_children"):
        for child in node.get_children():
            texts.extend(_collect_text(child, depth + 1))
    return texts
