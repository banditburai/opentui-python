"""Tests for TUI main layout."""

from opentui.components import Box, Text

from opencode.tui.layout import (
    main_layout,
    toolbar,
    status_bar,
    sidebar,
    content_area,
)
from opencode.tui.theme import APP_THEME


# --- Theme ---

class TestAppTheme:
    def test_has_required_keys(self):
        assert "bg" in APP_THEME
        assert "fg" in APP_THEME
        assert "toolbar" in APP_THEME
        assert "status_bar" in APP_THEME
        assert "sidebar" in APP_THEME

    def test_toolbar_has_colors(self):
        assert "bg" in APP_THEME["toolbar"]
        assert "fg" in APP_THEME["toolbar"]

    def test_status_bar_has_colors(self):
        assert "bg" in APP_THEME["status_bar"]
        assert "fg" in APP_THEME["status_bar"]


# --- Layout components ---

class TestToolbar:
    def test_returns_box(self):
        t = toolbar(title="OpenCode")
        assert isinstance(t, Box)

    def test_contains_title(self):
        t = toolbar(title="MyApp")
        children = t.get_children()
        assert any(
            isinstance(c, Text) and "MyApp" in getattr(c, "_content", "")
            for c in children
        )

    def test_default_title(self):
        t = toolbar()
        assert isinstance(t, Box)


class TestStatusBar:
    def test_returns_box(self):
        s = status_bar()
        assert isinstance(s, Box)

    def test_with_model(self):
        s = status_bar(model="gpt-4")
        children = s.get_children()
        texts = [getattr(c, "_content", "") for c in children if isinstance(c, Text)]
        assert any("gpt-4" in t for t in texts)


class TestSidebar:
    def test_returns_box(self):
        s = sidebar()
        assert isinstance(s, Box)

    def test_with_sessions(self):
        sessions = [{"id": "s1", "title": "First"}, {"id": "s2", "title": "Second"}]
        s = sidebar(sessions=sessions)
        assert isinstance(s, Box)


class TestContentArea:
    def test_returns_box(self):
        c = content_area()
        assert isinstance(c, Box)


class TestMainLayout:
    def test_returns_box(self):
        layout = main_layout()
        assert isinstance(layout, Box)

    def test_has_children(self):
        layout = main_layout()
        children = layout.get_children()
        assert len(children) >= 3  # toolbar, content, status bar

    def test_accepts_title(self):
        layout = main_layout(title="Test")
        assert isinstance(layout, Box)
