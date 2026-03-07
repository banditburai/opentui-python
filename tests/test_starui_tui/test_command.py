"""Tests for Command palette components."""

from opentui.components import Box, Text
from starui_tui.signals import Signal
from starui_tui.command import Command, CommandInput, CommandList, CommandItem, CommandGroup


class TestCommand:
    def test_returns_box(self):
        c = Command(
            CommandInput(placeholder="Search..."),
            CommandList(
                CommandItem("Open file", value="open"),
                CommandItem("Save", value="save"),
            ),
        )
        assert isinstance(c, Box)


class TestCommandInput:
    def test_returns_box(self):
        ci = CommandInput(placeholder="Type a command...")
        assert isinstance(ci, Box)


class TestCommandList:
    def test_returns_box(self):
        cl = CommandList(
            CommandItem("Item 1", value="1"),
            CommandItem("Item 2", value="2"),
        )
        assert isinstance(cl, Box)

    def test_children_count(self):
        cl = CommandList(
            CommandItem("Item 1", value="1"),
            CommandItem("Item 2", value="2"),
        )
        children = cl.get_children()
        assert len(children) == 2


class TestCommandItem:
    def test_returns_box(self):
        item = CommandItem("Open file", value="open")
        assert isinstance(item, Box)

    def test_with_callback(self):
        selected = []
        item = CommandItem("Open", value="open", on_select=lambda v: selected.append(v))
        item.on_mouse_down(None)
        assert selected == ["open"]

    def test_with_shortcut(self):
        item = CommandItem("Save", value="save", shortcut="Ctrl+S")
        assert isinstance(item, Box)
        children = item.get_children()
        # label + shortcut
        assert len(children) == 2


class TestCommandGroup:
    def test_returns_box(self):
        g = CommandGroup(
            "Files",
            CommandItem("Open", value="open"),
            CommandItem("Save", value="save"),
        )
        assert isinstance(g, Box)

    def test_has_heading(self):
        g = CommandGroup(
            "Files",
            CommandItem("Open", value="open"),
        )
        children = g.get_children()
        # heading + items
        assert len(children) == 2
