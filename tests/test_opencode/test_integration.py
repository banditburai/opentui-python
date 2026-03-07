"""Integration / smoke tests — wiring all OpenCode modules together."""

import uuid

from opentui.components import Box, Text

from opencode.config import AppConfig, load_config
from opencode.db.models import Session, Message
from opencode.db.store import Store
from opencode.tui.layout import main_layout
from opencode.tui.components.chat import chat_panel
from opencode.tui.components.input import InputState
from opencode.tui.components.sidebar import SessionItem, sidebar_panel
from opencode.tui.components.editor import code_viewer
from opencode.tui.components.diff import diff_viewer, parse_unified_diff
from opencode.tui.keybindings import default_keybindings


# --- Smoke: modules import and compose ---


class TestSmoke:
    def test_all_modules_import(self):
        """All OpenCode modules can be imported without error."""
        import opencode.config
        import opencode.db.store
        import opencode.db.models
        import opencode.tui.layout
        import opencode.tui.theme
        import opencode.tui.keybindings
        import opencode.tui.components.chat
        import opencode.tui.components.input
        import opencode.tui.components.sidebar
        import opencode.tui.components.editor
        import opencode.tui.components.diff

    def test_full_layout_renders(self):
        """main_layout composes all pieces without error."""
        layout = main_layout(title="OpenCode", model="gpt-4o", branch="main")
        assert isinstance(layout, Box)

    def test_config_defaults(self, tmp_path):
        """Config loads with defaults when no file exists."""
        cfg = load_config(config_dir=tmp_path)
        assert isinstance(cfg, AppConfig)
        assert cfg.model == "gpt-4o"

    def test_keybindings_loaded(self):
        """Default keybindings are registered."""
        reg = default_keybindings()
        assert len(reg.list()) >= 5


# --- Integration: session lifecycle ---


class TestSessionLifecycle:
    def test_create_and_list_session(self, tmp_path):
        """Create a session, verify it appears in store and sidebar."""
        db_path = tmp_path / "test.db"
        store = Store(str(db_path))
        # Store auto-initializes schema in __init__

        session = Session(
            id=str(uuid.uuid4()),
            title="Test Chat",
            model="gpt-4o",
        )
        store.create_session(session)
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].title == "Test Chat"

        # Render sidebar with live data
        items = [
            SessionItem(id=s.id, title=s.title, updated_at=s.updated_at)
            for s in sessions
        ]
        panel = sidebar_panel(sessions=items, active_id=session.id)
        assert isinstance(panel, Box)

        store.close()

    def test_create_session_add_messages_render_chat(self, tmp_path):
        """Full flow: create session, add messages, render chat panel."""
        db_path = tmp_path / "test.db"
        store = Store(str(db_path))
        # Store auto-initializes schema in __init__

        session_id = str(uuid.uuid4())
        store.create_session(Session(id=session_id, title="Chat"))

        # Add messages
        store.create_message(Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content="Hello, how are you?",
        ))
        store.create_message(Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content="I'm doing well! How can I help?",
        ))

        # Fetch and render
        messages = store.get_messages(session_id)
        assert len(messages) == 2

        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]
        panel = chat_panel(messages=msg_dicts)
        assert isinstance(panel, Box)
        children = panel.get_children()
        assert len(children) == 2

        store.close()

    def test_delete_session_cascade(self, tmp_path):
        """Deleting a session removes its messages."""
        db_path = tmp_path / "test.db"
        store = Store(str(db_path))
        # Store auto-initializes schema in __init__

        session_id = str(uuid.uuid4())
        store.create_session(Session(id=session_id, title="Temp"))
        store.create_message(Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content="test",
        ))
        store.delete_session(session_id)

        assert store.list_sessions() == []
        assert store.get_messages(session_id) == []

        store.close()


# --- Integration: input → chat flow ---


class TestInputChatFlow:
    def test_submit_and_render(self):
        """Simulate user typing, submitting, and seeing result in chat."""
        state = InputState()
        state.text = "What is 2+2?"

        # Submit
        submitted_text = state.submit()
        assert submitted_text == "What is 2+2?"
        assert state.text == ""

        # Build chat messages
        messages = [
            {"role": "user", "content": submitted_text},
            {"role": "assistant", "content": "4"},
        ]
        panel = chat_panel(messages=messages)
        assert isinstance(panel, Box)

    def test_streaming_render(self):
        """Streaming message shows cursor."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi th"},
        ]
        panel = chat_panel(messages=messages, streaming=True)
        all_text = _collect_text(panel)
        assert any("\u2588" in t for t in all_text)


# --- Integration: code viewer + diff ---


class TestCodeViewerIntegration:
    def test_code_viewer_renders(self):
        source = "def hello():\n    print('hi')\n"
        cv = code_viewer(source=source, filename="hello.py")
        assert isinstance(cv, Box)

    def test_diff_roundtrip(self):
        raw = """\
--- a/f.py
+++ b/f.py
@@ -1,3 +1,3 @@
 same
-old
+new
 same
"""
        lines = parse_unified_diff(raw)
        dv = diff_viewer(lines=lines, filename="f.py")
        assert isinstance(dv, Box)
        all_text = _collect_text(dv)
        assert any("f.py" in t for t in all_text)


# --- Helpers ---


def _collect_text(node, depth=0):
    if depth > 10:
        return []
    texts = []
    if isinstance(node, Text):
        texts.append(getattr(node, "_content", ""))
    if hasattr(node, "get_children"):
        for child in node.get_children():
            texts.extend(_collect_text(child, depth + 1))
    return texts
