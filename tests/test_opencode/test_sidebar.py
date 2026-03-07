"""Tests for the session management sidebar component."""

from datetime import datetime

from opentui.components import Box, Text

from opencode.tui.components.sidebar import (
    SessionItem,
    session_list,
    sidebar_panel,
)


# --- SessionItem ---


class TestSessionItem:
    def test_fields(self):
        item = SessionItem(id="s1", title="First", updated_at=datetime.now())
        assert item.id == "s1"
        assert item.title == "First"

    def test_default_title(self):
        item = SessionItem(id="s2", title="", updated_at=datetime.now())
        assert item.title == ""


# --- session_list ---


class TestSessionList:
    def test_returns_box(self):
        items = [SessionItem(id="s1", title="One", updated_at=datetime.now())]
        sl = session_list(sessions=items)
        assert isinstance(sl, Box)

    def test_shows_session_titles(self):
        items = [
            SessionItem(id="s1", title="Chat A", updated_at=datetime.now()),
            SessionItem(id="s2", title="Chat B", updated_at=datetime.now()),
        ]
        sl = session_list(sessions=items)
        all_text = _collect_text(sl)
        assert any("Chat A" in t for t in all_text)
        assert any("Chat B" in t for t in all_text)

    def test_highlights_active(self):
        items = [
            SessionItem(id="s1", title="A", updated_at=datetime.now()),
            SessionItem(id="s2", title="B", updated_at=datetime.now()),
        ]
        sl = session_list(sessions=items, active_id="s2")
        assert isinstance(sl, Box)

    def test_empty_list(self):
        sl = session_list(sessions=[])
        assert isinstance(sl, Box)
        all_text = _collect_text(sl)
        assert any("no sessions" in t.lower() for t in all_text)

    def test_session_with_empty_title_shows_untitled(self):
        items = [SessionItem(id="s1", title="", updated_at=datetime.now())]
        sl = session_list(sessions=items)
        all_text = _collect_text(sl)
        assert any("Untitled" in t for t in all_text)

    def test_long_title_truncated(self):
        long = "A" * 100
        items = [SessionItem(id="s1", title=long, updated_at=datetime.now())]
        sl = session_list(sessions=items)
        all_text = _collect_text(sl)
        # Default sidebar width is 30, minus 2 padding = 28 max chars
        assert all(len(t) <= 28 for t in all_text if "A" in t)


# --- sidebar_panel ---


class TestSidebarPanel:
    def test_returns_box(self):
        panel = sidebar_panel(sessions=[])
        assert isinstance(panel, Box)

    def test_has_header(self):
        panel = sidebar_panel(sessions=[])
        all_text = _collect_text(panel)
        assert any("session" in t.lower() for t in all_text)

    def test_with_sessions(self):
        items = [SessionItem(id="s1", title="First", updated_at=datetime.now())]
        panel = sidebar_panel(sessions=items)
        all_text = _collect_text(panel)
        assert any("First" in t for t in all_text)

    def test_with_active_session(self):
        items = [
            SessionItem(id="s1", title="A", updated_at=datetime.now()),
            SessionItem(id="s2", title="B", updated_at=datetime.now()),
        ]
        panel = sidebar_panel(sessions=items, active_id="s1")
        assert isinstance(panel, Box)

    def test_accepts_kwargs(self):
        panel = sidebar_panel(sessions=[], width=40)
        assert isinstance(panel, Box)


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
