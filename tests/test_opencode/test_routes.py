"""Tests for route system, home screen, and tips."""

from __future__ import annotations

from opentui.components import Box

from opencode.tui.components.home import LOGO, home_screen
from opencode.tui.routes import Route, get_route, navigate_to_home, navigate_to_session, set_route
from opencode.tui.themes import init_theme
from opencode.tui.tips import TIPS, format_tip, random_tip


class TestRoutes:
    def setup_method(self):
        set_route(Route.HOME)

    def test_initial_route_is_home(self):
        assert get_route() == Route.HOME

    def test_navigate_to_session(self):
        navigate_to_session()
        assert get_route() == Route.SESSION

    def test_navigate_to_home(self):
        set_route(Route.SESSION)
        navigate_to_home()
        assert get_route() == Route.HOME

    def test_set_route(self):
        set_route(Route.SESSION)
        assert get_route() == Route.SESSION
        set_route(Route.HOME)
        assert get_route() == Route.HOME


class TestTips:
    def test_tips_list_not_empty(self):
        assert len(TIPS) >= 30

    def test_random_tip(self):
        tip = random_tip()
        assert isinstance(tip, str)
        assert len(tip) > 0

    def test_format_tip_plain(self):
        segments = format_tip("Hello world")
        assert segments == [("Hello world", False)]

    def test_format_tip_highlighted(self):
        segments = format_tip("Press {Ctrl+K} to open")
        assert len(segments) == 3
        assert segments[0] == ("Press ", False)
        assert segments[1] == ("Ctrl+K", True)
        assert segments[2] == (" to open", False)

    def test_format_tip_multiple_highlights(self):
        segments = format_tip("{A} and {B}")
        highlighted = [s for s, h in segments if h]
        assert "A" in highlighted
        assert "B" in highlighted


class TestHomeScreen:
    def setup_method(self):
        init_theme("opencode", "dark")

    def test_renders_box(self):
        h = home_screen()
        assert isinstance(h, Box)

    def test_with_mcp_servers(self):
        servers = [
            {"name": "filesystem", "status": "connected"},
            {"name": "database", "status": "disconnected"},
        ]
        h = home_screen(mcp_servers=servers)
        assert isinstance(h, Box)

    def test_without_mcp(self):
        h = home_screen(mcp_servers=None)
        assert isinstance(h, Box)

    def test_logo_is_multiline(self):
        assert "\n" in LOGO
