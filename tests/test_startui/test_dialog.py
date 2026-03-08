"""Tests for Dialog and AlertDialog components."""

from opentui.components import Box, Text
from startui.signals import Signal
from startui.dialog import (
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
                is_open=sig(),
            ),
            signal=sig,
        )
        assert isinstance(d, Box)

    def test_without_signal(self):
        d = Dialog(DialogContent(Text("Content")))
        assert isinstance(d, Box)


class TestDialogTrigger:
    def test_returns_box(self):
        sig = Signal("open", False)
        t = DialogTrigger("Open Dialog", signal=sig)
        assert isinstance(t, Box)
        assert t.on_mouse_down is not None

    def test_toggles_signal(self):
        sig = Signal("open", False)
        t = DialogTrigger("Open", signal=sig)
        t.on_mouse_down(None)
        assert sig() is True
        t.on_mouse_down(None)
        assert sig() is False

    def test_without_signal(self):
        t = DialogTrigger("Open")
        assert t.on_mouse_down is None


class TestDialogContent:
    def test_visible_when_open(self):
        c = DialogContent(Text("Body"), is_open=True)
        assert isinstance(c, Box)
        assert c._visible is True

    def test_hidden_when_closed(self):
        c = DialogContent(Text("Body"), is_open=False)
        assert c._visible is False

    def test_has_border(self):
        c = DialogContent(Text("Body"), is_open=True)
        assert c._border is True

    def test_kwargs_forwarded(self):
        c = DialogContent(Text("Body"), is_open=True, width=40)
        assert c._width == 40


class TestDialogSubcomponents:
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
