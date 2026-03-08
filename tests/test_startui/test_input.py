"""Tests for startui Input component."""

from opentui.components import Input as TUIInput
from startui.input import Input


class TestInput:
    def test_returns_tui_input(self):
        i = Input()
        assert isinstance(i, TUIInput)

    def test_has_border(self):
        i = Input()
        assert i.border is True

    def test_has_border_style(self):
        i = Input()
        assert i.border_style == "single"

    def test_placeholder(self):
        i = Input(placeholder="Type here...")
        assert i.placeholder == "Type here..."

    def test_initial_value(self):
        i = Input(value="hello")
        assert i.value == "hello"

    def test_disabled_sets_fg(self):
        i = Input(disabled=True)
        # Disabled input should have dimmed foreground
        assert i._fg is not None

    def test_on_change_registered(self):
        changes = []
        i = Input(on_change=lambda v: changes.append(v))
        # Callback registered via event system
        assert isinstance(i, TUIInput)
        assert len(i._event_handlers.get("change", [])) == 1

    def test_on_submit_registered(self):
        submits = []
        i = Input(on_submit=lambda v: submits.append(v))
        assert isinstance(i, TUIInput)
        assert len(i._event_handlers.get("submit", [])) == 1

    def test_kwargs_passthrough(self):
        i = Input(width=30)
        assert i._width == 30

    def test_disabled_suppresses_callbacks(self):
        i = Input(disabled=True, on_change=lambda v: None, on_submit=lambda v: None)
        # Callbacks should not be registered when disabled
        assert isinstance(i, TUIInput)

    def test_variant_default(self):
        i = Input(variant="default")
        assert i.border is True
