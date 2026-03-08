"""Tests for TUI main layout."""

from opentui.components import Box, Text

from opencode.tui.layout import (
    main_layout,
    toolbar,
    status_bar,
    sidebar,
    content_area,
)
from opencode.tui.themes import get_theme, init_theme, list_themes, ThemeColors


# --- Theme ---

class TestThemeSystem:
    def test_get_theme_returns_theme_colors(self):
        init_theme("opencode", "dark")
        t = get_theme()
        assert isinstance(t, ThemeColors)

    def test_has_required_color_tokens(self):
        t = get_theme()
        assert t.primary.startswith("#")
        assert t.background.startswith("#")
        assert t.text.startswith("#")
        assert t.border.startswith("#")

    def test_list_themes_returns_builtin(self):
        names = list_themes()
        assert "opencode" in names
        assert "dracula" in names
        assert len(names) >= 30


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

    def test_session_without_id_or_title(self):
        sessions = [{}]
        s = sidebar(sessions=sessions)
        children = s.get_children()
        texts = [getattr(c, "_content", "") for c in children if isinstance(c, Text)]
        assert "Untitled" in texts


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

    def test_branch_forwarded_to_status_bar(self):
        layout = main_layout(branch="main")
        # status_bar is the last child of the outer Box
        children = layout.get_children()
        sb = children[-1]
        sb_children = sb.get_children()
        texts = [getattr(c, "_content", "") for c in sb_children if isinstance(c, Text)]
        assert any("main" in t for t in texts)
