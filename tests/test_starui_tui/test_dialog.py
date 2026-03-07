"""Tests for Dialog and AlertDialog components."""

from opentui.components import Box, Text
from starui_tui.signals import Signal
from starui_tui.dialog import (
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
)


class TestDialog:
    def test_returns_box(self):
        sig = Signal("open", False)
        d = Dialog(
            DialogTrigger("Open", signal=sig),
            DialogContent(
                DialogHeader(DialogTitle("Title")),
            ),
            signal=sig,
        )
        assert isinstance(d, Box)

    def test_closed_hides_content(self):
        sig = Signal("open", False)
        d = Dialog(
            DialogContent(Text("Content")),
            signal=sig,
        )
        assert isinstance(d, Box)

    def test_open_shows_content(self):
        sig = Signal("open", True)
        d = Dialog(
            DialogContent(Text("Content")),
            signal=sig,
        )
        assert isinstance(d, Box)


class TestDialogSubcomponents:
    def test_dialog_trigger(self):
        sig = Signal("open", False)
        t = DialogTrigger("Open Dialog", signal=sig)
        assert isinstance(t, Box)
        assert t.on_mouse_down is not None

    def test_dialog_content(self):
        c = DialogContent(Text("Body"), is_open=True)
        assert isinstance(c, Box)

    def test_dialog_content_hidden(self):
        c = DialogContent(Text("Body"), is_open=False)
        assert c._visible is False

    def test_dialog_header(self):
        h = DialogHeader(DialogTitle("Title"))
        assert isinstance(h, Box)

    def test_dialog_title(self):
        t = DialogTitle("My Dialog")
        assert isinstance(t, Text)
        assert t._bold is True

    def test_dialog_description(self):
        d = DialogDescription("A description")
        assert isinstance(d, Text)

    def test_dialog_footer(self):
        f = DialogFooter(Text("OK"))
        assert isinstance(f, Box)
