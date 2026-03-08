"""Tests for the StarHTML web frontend components and pages."""

from __future__ import annotations

import pytest

pytest.importorskip("starhtml")

from starhtml import Div, Html  # noqa: E402

from opencode.tui.themes import init_theme  # noqa: E402


@pytest.fixture(autouse=True)
def _theme():
    init_theme("opencode", "dark")


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


class TestSignals:
    def test_app_signals(self):
        from opencode.web.signals import app_signals

        sigs = app_signals()
        assert "prompt" in sigs
        assert "status" in sigs
        assert "model" in sigs
        assert "session_id" in sigs
        assert "streaming" in sigs
        assert "sidebar_open" in sigs
        assert "theme" in sigs
        assert len(sigs) >= 8


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


class TestToolbarComponent:
    def test_renders(self):
        from opencode.web.components.toolbar import toolbar_html

        result = toolbar_html()
        assert result is not None
        assert "OpenCode" in str(result)

    def test_custom_title(self):
        from opencode.web.components.toolbar import toolbar_html

        result = toolbar_html(title="My App")
        assert result is not None
        assert "My App" in str(result)


class TestSidebarComponent:
    def test_renders_empty(self):
        from opencode.web.components.sidebar import sidebar_html

        result = sidebar_html()
        assert result is not None
        assert "Sessions" in str(result)

    def test_renders_with_sessions(self):
        from opencode.web.components.sidebar import sidebar_html

        sessions = [
            {"id": "s1", "title": "First"},
            {"id": "s2", "title": "Second"},
        ]
        result = sidebar_html(sessions=sessions, active_id="s1")
        rendered = str(result)
        assert "First" in rendered
        assert "Second" in rendered

    def test_session_item(self):
        from opencode.web.components.sidebar import session_item_html

        result = session_item_html(session_id="s1", title="Test", active=True)
        assert result is not None
        assert "Test" in str(result)


class TestMessageComponent:
    def test_user_message(self):
        from opencode.web.components.message import message_html

        result = message_html(role="user", content="Hello")
        rendered = str(result)
        assert "Hello" in rendered
        assert "User" in rendered

    def test_assistant_message(self):
        from opencode.web.components.message import message_html

        result = message_html(role="assistant", content="Hi!", model="gpt-4")
        rendered = str(result)
        assert "Hi!" in rendered
        assert "gpt-4" in rendered

    def test_with_tool_calls(self):
        from opencode.web.components.message import message_html

        result = message_html(
            role="assistant",
            content="Here are the files:",
            tool_calls=[{"function": {"name": "bash", "arguments": '{"command": "ls"}'}}],
        )
        rendered = str(result)
        assert "bash" in rendered

    def test_tool_result(self):
        from opencode.web.components.message import tool_result_html

        result = tool_result_html(tool_name="bash", content="file1\nfile2")
        rendered = str(result)
        assert "bash" in rendered
        assert "file1" in rendered


class TestPromptComponent:
    def test_renders(self):
        from opencode.web.components.prompt import prompt_html

        result = prompt_html()
        assert result is not None

    def test_custom_placeholder(self):
        from opencode.web.components.prompt import prompt_html

        result = prompt_html(placeholder="Ask anything...")
        assert "Ask anything" in str(result)


class TestDialogComponents:
    def test_command_palette(self):
        from opencode.web.components.dialogs import command_palette_html

        result = command_palette_html(commands=[
            {"name": "New Session", "keybinding": "Ctrl+N"},
        ])
        rendered = str(result)
        assert "New Session" in rendered

    def test_command_palette_empty(self):
        from opencode.web.components.dialogs import command_palette_html

        result = command_palette_html()
        assert result is not None

    def test_theme_picker(self):
        from opencode.web.components.dialogs import theme_picker_html

        result = theme_picker_html(themes=["opencode", "dracula"], active="opencode")
        rendered = str(result)
        assert "opencode" in rendered
        assert "dracula" in rendered


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


class TestLayoutPage:
    def test_base_layout(self):
        from opencode.web.pages.layout import base_layout

        result = base_layout(Div("Content"))
        assert result is not None

    def test_custom_title(self):
        from opencode.web.pages.layout import base_layout

        result = base_layout(Div("Content"), title="Custom")
        assert result is not None


class TestHomePage:
    def test_renders(self):
        from opencode.web.pages.home import home_page

        result = home_page()
        assert result is not None


class TestSessionPage:
    def test_empty(self):
        from opencode.web.pages.session import session_page

        result = session_page()
        assert result is not None

    def test_with_messages(self):
        from opencode.web.pages.session import session_page

        msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = session_page(messages=msgs)
        assert result is not None


# ---------------------------------------------------------------------------
# Web app creation
# ---------------------------------------------------------------------------


class TestWebApp:
    def test_create_web_app(self):
        from opencode.ai.tools import ToolRegistry
        from opencode.bus import EventBus
        from opencode.db.store import Store
        from opencode.tui.bridge import AsyncBridge
        from opencode.tui.state import AppState
        from opencode.web.app import create_web_app

        class MockProvider:
            model = "test-model"

            async def stream(self, messages, *, tools=None, **kwargs):
                from opencode.ai.stream import StreamChunk
                yield StreamChunk(content="hi", finish_reason="stop")

        store = Store(":memory:")
        bus = EventBus()
        bridge = AsyncBridge()

        state = AppState(
            store=store,
            provider=MockProvider(),
            tool_registry=ToolRegistry(),
            bridge=bridge,
            bus=bus,
        )

        app = create_web_app(bus, state)
        assert app is not None


# ---------------------------------------------------------------------------
# Package imports
# ---------------------------------------------------------------------------


class TestWebPackage:
    def test_imports(self):
        from opencode.web import create_web_app
        from opencode.web.signals import app_signals
        from opencode.web.components import (
            command_palette_html,
            message_html,
            prompt_html,
            sidebar_html,
            toolbar_html,
            theme_picker_html,
        )
        from opencode.web.pages import base_layout, home_page, session_page

        assert create_web_app is not None
        assert app_signals is not None
