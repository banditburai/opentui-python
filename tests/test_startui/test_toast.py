"""Tests for Toast notification system."""

from opentui.components import Box, Text
from startui.toast import Toast, Toaster, use_toast


class TestToast:
    def test_returns_box(self):
        t = Toast("Hello", variant="default")
        assert isinstance(t, Box)

    def test_success_variant(self):
        t = Toast("Success!", variant="success")
        assert isinstance(t, Box)

    def test_error_variant(self):
        t = Toast("Error!", variant="error")
        assert isinstance(t, Box)

    def test_warning_variant(self):
        t = Toast("Warning!", variant="warning")
        assert isinstance(t, Box)

    def test_title_and_description(self):
        t = Toast("Title", description="Details here")
        assert isinstance(t, Box)


class TestToaster:
    def test_returns_box(self):
        state = use_toast()
        container = Toaster(state=state)
        assert isinstance(container, Box)

    def test_empty_state(self):
        state = use_toast()
        container = Toaster(state=state)
        assert len(container.get_children()) == 0

    def test_shows_toasts(self):
        state = use_toast()
        state["add"]("Hello")
        container = Toaster(state=state)
        assert len(container.get_children()) == 1

    def test_multiple_toasts(self):
        state = use_toast()
        state["add"]("First")
        state["add"]("Second")
        container = Toaster(state=state)
        assert len(container.get_children()) == 2

    def test_dismiss_toast(self):
        state = use_toast()
        toast_id = state["add"]("Dismissable")
        state["dismiss"](toast_id)
        container = Toaster(state=state)
        assert len(container.get_children()) == 0


class TestUseToast:
    def test_returns_dict(self):
        state = use_toast()
        assert isinstance(state, dict)
        assert "add" in state
        assert "dismiss" in state
        assert "toasts" in state

    def test_add_returns_id(self):
        state = use_toast()
        toast_id = state["add"]("Message")
        assert isinstance(toast_id, str)

    def test_add_with_variant(self):
        state = use_toast()
        toast_id = state["add"]("Error!", variant="error")
        toasts = state["toasts"]()
        assert len(toasts) == 1
        assert toasts[0]["variant"] == "error"

    def test_add_with_description(self):
        state = use_toast()
        state["add"]("Title", description="Body text")
        toasts = state["toasts"]()
        assert toasts[0]["description"] == "Body text"
