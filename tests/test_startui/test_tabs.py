"""Tests for Tabs with context injection."""

from opentui.components import Box, Text
from startui.signals import Signal
from startui.tabs import Tabs, TabsContent, TabsTrigger


class TestTabs:
    def test_returns_box(self):
        t = Tabs(
            TabsTrigger("Tab1", value="a"),
            value="a",
        )
        assert isinstance(t, Box)

    def test_renders_triggers(self):
        t = Tabs(
            TabsTrigger("Tab1", value="a"),
            TabsTrigger("Tab2", value="b"),
            value="a",
        )
        children = t.get_children()
        assert len(children) == 2

    def test_with_signal(self):
        sig = Signal("tab", "a")
        t = Tabs(
            TabsTrigger("Tab1", value="a"),
            TabsTrigger("Tab2", value="b"),
            signal=sig,
        )
        assert isinstance(t, Box)


class TestTabsTrigger:
    def test_returns_callable(self):
        trigger = TabsTrigger("Tab1", value="a")
        assert callable(trigger)

    def test_renders_to_box(self):
        trigger = TabsTrigger("Tab1", value="a")
        sig = Signal("tab", "a")
        result = trigger(tabs_state=sig, variant="default")
        assert isinstance(result, Box)

    def test_active_trigger(self):
        trigger = TabsTrigger("Tab1", value="a")
        sig = Signal("tab", "a")
        result = trigger(tabs_state=sig, variant="default")
        # Active trigger should have click handler
        assert result.on_mouse_down is not None

    def test_inactive_trigger(self):
        trigger = TabsTrigger("Tab1", value="a")
        sig = Signal("tab", "b")
        result = trigger(tabs_state=sig, variant="default")
        assert isinstance(result, Box)


class TestTabsContent:
    def test_returns_callable(self):
        content = TabsContent(Text("Content"), value="a")
        assert callable(content)

    def test_active_content_visible(self):
        content = TabsContent(Text("Content"), value="a")
        sig = Signal("tab", "a")
        result = content(tabs_state=sig)
        children = result.get_children()
        assert len(children) == 1

    def test_inactive_content_hidden(self):
        content = TabsContent(Text("Content"), value="a")
        sig = Signal("tab", "b")
        result = content(tabs_state=sig)
        assert result._visible is False


class TestTabsIntegration:
    def test_full_tabs(self):
        sig = Signal("tab", "chat")
        t = Tabs(
            TabsTrigger("Chat", value="chat"),
            TabsTrigger("Editor", value="editor"),
            TabsContent(Text("Chat content"), value="chat"),
            TabsContent(Text("Editor content"), value="editor"),
            signal=sig,
        )
        assert isinstance(t, Box)
        children = t.get_children()
        assert len(children) == 4
