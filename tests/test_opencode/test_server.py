"""Tests for the SSE server endpoints — both legacy and new modular routes."""

import json

import pytest

from opencode.bus import Event, EventBus
from opencode.db.store import Store
from opencode.tui.themes import init_theme

pytest.importorskip("starlette")
pytest.importorskip("starhtml")
pytest.importorskip("httpx")

from starlette.testclient import TestClient  # noqa: E402

from opencode.ai.tools import ToolRegistry  # noqa: E402
from opencode.tui.bridge import AsyncBridge  # noqa: E402
from opencode.tui.state import AppState  # noqa: E402


class MockProvider:
    model = "test-model"

    async def stream(self, messages, *, tools=None, **kwargs):
        from opencode.ai.stream import StreamChunk

        yield StreamChunk(content="hi", finish_reason="stop")


@pytest.fixture(autouse=True)
def _theme():
    init_theme("opencode", "dark")


@pytest.fixture
def app():
    """Create a test Starlette app."""
    store = Store(":memory:")
    bus = EventBus()
    bridge = AsyncBridge()
    provider = MockProvider()
    tool_registry = ToolRegistry()

    state = AppState(
        store=store,
        provider=provider,
        tool_registry=tool_registry,
        bridge=bridge,
        bus=bus,
    )

    from opencode.server.app import create_app

    return create_app(bus, state), state


# ---------------------------------------------------------------------------
# Legacy compat routes
# ---------------------------------------------------------------------------


class TestLegacyEndpoints:
    def test_list_sessions_empty(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_session(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.post("/sessions")
        assert resp.status_code == 200
        assert "id" in resp.json()

    def test_list_sessions_after_create(self, app):
        application, state = app
        client = TestClient(application)
        client.post("/sessions")
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_session_messages_empty(self, app):
        application, state = app
        client = TestClient(application)
        create_resp = client.post("/sessions")
        session_id = create_resp.json()["id"]
        resp = client.get(f"/sessions/{session_id}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_post_message_requires_text(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.post("/messages", json={"text": ""})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# New session routes
# ---------------------------------------------------------------------------


class TestSessionRoutes:
    def test_list_sessions(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/session")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_and_get_session(self, app):
        application, state = app
        client = TestClient(application)

        create = client.post("/session")
        assert create.status_code == 200
        session_id = create.json()["id"]

        get = client.get(f"/session/{session_id}")
        assert get.status_code == 200
        assert get.json()["id"] == session_id

    def test_update_session(self, app):
        application, state = app
        client = TestClient(application)

        create = client.post("/session")
        session_id = create.json()["id"]

        resp = client.patch(f"/session/{session_id}", json={"title": "New Title"})
        assert resp.status_code == 200

    def test_delete_session(self, app):
        application, state = app
        client = TestClient(application)

        create = client.post("/session")
        session_id = create.json()["id"]

        delete = client.delete(f"/session/{session_id}")
        assert delete.status_code == 200

    def test_get_nonexistent_session(self, app):
        application, state = app
        client = TestClient(application)

        resp = client.get("/session/nonexistent")
        assert resp.status_code == 404

    def test_session_messages(self, app):
        application, state = app
        client = TestClient(application)

        create = client.post("/session")
        session_id = create.json()["id"]

        resp = client.get(f"/session/{session_id}/message")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_abort_session(self, app):
        application, state = app
        client = TestClient(application)

        create = client.post("/session")
        session_id = create.json()["id"]

        resp = client.post(f"/session/{session_id}/abort")
        assert resp.status_code == 200

    def test_session_diff(self, app):
        application, state = app
        client = TestClient(application)

        create = client.post("/session")
        session_id = create.json()["id"]

        resp = client.get(f"/session/{session_id}/diff")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Global routes
# ---------------------------------------------------------------------------


class TestGlobalRoutes:
    def test_health(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/global/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_global_config(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/global/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "model" in data
        assert "theme" in data

    def test_global_dispose(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.post("/global/dispose")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Config routes
# ---------------------------------------------------------------------------


class TestConfigRoutes:
    def test_get_config(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "theme" in data

    def test_get_providers_config(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/config/providers")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Provider routes
# ---------------------------------------------------------------------------


class TestProviderRoutes:
    def test_list_providers(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/provider")
        assert resp.status_code == 200
        providers = resp.json()
        assert len(providers) >= 4
        assert any(p["id"] == "anthropic" for p in providers)

    def test_provider_auth(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/provider/auth")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# MCP routes
# ---------------------------------------------------------------------------


class TestMcpRoutes:
    def test_get_mcp_status(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/mcp")
        assert resp.status_code == 200

    def test_connect_mcp_not_implemented(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.post("/mcp/connect", json={"name": "test-server"})
        assert resp.status_code == 501
        assert "not yet implemented" in resp.json()["error"]

    def test_disconnect_mcp_not_implemented(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.post("/mcp/disconnect", json={"name": "test-server"})
        assert resp.status_code == 501
        assert "not yet implemented" in resp.json()["error"]

    def test_connect_always_501(self, app):
        """MCP connect returns 501 regardless of body content."""
        application, state = app
        client = TestClient(application)
        resp = client.post("/mcp/connect", json={})
        assert resp.status_code == 501


# ---------------------------------------------------------------------------
# Permission routes
# ---------------------------------------------------------------------------


class TestPermissionRoutes:
    def test_list_permissions(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/permission")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_respond_not_found(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.post("/permission/nonexistent/reply", json={"approved": True})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Question routes
# ---------------------------------------------------------------------------


class TestQuestionRoutes:
    def test_list_questions(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/question")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_reply_not_found(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.post("/question/nonexistent/reply", json={"answer": "yes"})
        assert resp.status_code == 404

    def test_reject_not_found(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.post("/question/nonexistent/reject")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# System routes
# ---------------------------------------------------------------------------


class TestSystemRoutes:
    def test_get_paths(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/path")
        assert resp.status_code == 200
        data = resp.json()
        assert "cwd" in data
        assert "home" in data

    def test_get_vcs(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/vcs")
        assert resp.status_code == 200
        data = resp.json()
        assert "type" in data

    def test_list_commands(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/command")
        assert resp.status_code == 200
        commands = resp.json()
        assert len(commands) >= 10

    def test_list_agents(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/agent")
        assert resp.status_code == 200
        agents = resp.json()
        assert len(agents) >= 4

    def test_list_tools(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/tool")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# File routes
# ---------------------------------------------------------------------------


class TestFileRoutes:
    def test_list_dir(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/file", params={"path": "."})
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data

    def test_read_file(self, app):
        application, state = app
        client = TestClient(application)

        # Read a file known to exist within the project directory
        resp = client.get("/file/content", params={"path": "pyproject.toml"})
        assert resp.status_code == 200
        assert "opencode" in resp.json()["content"].lower()

    def test_read_file_not_found(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/file/content", params={"path": "nonexistent_file_xyz.txt"})
        assert resp.status_code == 404

    def test_read_file_requires_path(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/file/content")
        assert resp.status_code == 400

    def test_find_files(self, app):
        application, state = app
        client = TestClient(application)

        # Search within the project directory
        resp = client.get("/find/file", params={"pattern": "**/*.py", "directory": "src"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_find_text(self, app):
        application, state = app
        client = TestClient(application)

        # Search for text in the project src directory
        resp = client.get("/find", params={"pattern": "def ", "directory": "src"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_find_text_requires_pattern(self, app):
        application, state = app
        client = TestClient(application)
        resp = client.get("/find")
        assert resp.status_code == 400

    def test_path_traversal_blocked(self, app):
        """Paths outside the project directory should return 403."""
        application, state = app
        client = TestClient(application)
        resp = client.get("/file/content", params={"path": "/etc/passwd"})
        assert resp.status_code == 403
