"""Tests for the SQLite data layer."""

from datetime import datetime

import pytest
from opencode.db.store import Store
from opencode.db.models import Session, Message, FileChange


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


class TestSessions:
    def test_create_and_get(self, store):
        session = Session(id="s1", title="Test", model="gpt-4")
        store.create_session(session)
        result = store.get_session("s1")
        assert result is not None
        assert result.id == "s1"
        assert result.title == "Test"
        assert result.model == "gpt-4"

    def test_get_nonexistent(self, store):
        assert store.get_session("nope") is None

    def test_list_sessions(self, store):
        store.create_session(Session(id="s1", title="First"))
        store.create_session(Session(id="s2", title="Second"))
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_update_session(self, store):
        store.create_session(Session(id="s1", title="Old"))
        store.update_session("s1", title="New")
        result = store.get_session("s1")
        assert result.title == "New"

    def test_update_session_rejects_bad_columns(self, store):
        store.create_session(Session(id="s1"))
        with pytest.raises(ValueError, match="Invalid column"):
            store.update_session("s1", evil="DROP TABLE sessions")

    def test_delete_session(self, store):
        store.create_session(Session(id="s1"))
        store.delete_session("s1")
        assert store.get_session("s1") is None

    def test_datetime_roundtrip(self, store):
        ts = datetime(2025, 6, 15, 12, 30, 0)
        store.create_session(Session(id="s1", created_at=ts, updated_at=ts))
        result = store.get_session("s1")
        assert isinstance(result.created_at, datetime)
        assert result.created_at == ts


class TestMessages:
    def test_create_and_get(self, store):
        store.create_session(Session(id="s1"))
        msg = Message(id="m1", session_id="s1", role="user", content="Hello")
        store.create_message(msg)
        messages = store.get_messages("s1")
        assert len(messages) == 1
        assert messages[0].content == "Hello"
        assert messages[0].role == "user"

    def test_multiple_messages(self, store):
        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="user", content="Hi"))
        store.create_message(Message(id="m2", session_id="s1", role="assistant", content="Hello"))
        messages = store.get_messages("s1")
        assert len(messages) == 2

    def test_delete_message(self, store):
        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="user"))
        store.delete_message("m1")
        assert store.get_messages("s1") == []

    def test_delete_message_cleans_file_changes(self, store):
        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="assistant"))
        store.create_file_change(FileChange(
            id="f1", session_id="s1", message_id="m1", path="x.py",
        ))
        store.delete_message("m1")
        assert store.get_file_changes("s1") == []

    def test_empty_session_has_no_messages(self, store):
        store.create_session(Session(id="s1"))
        assert store.get_messages("s1") == []


class TestFileChanges:
    def test_create_and_get(self, store):
        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="assistant"))
        change = FileChange(
            id="f1", session_id="s1", message_id="m1",
            path="src/main.py", action="create", diff="+hello",
        )
        store.create_file_change(change)
        changes = store.get_file_changes("s1")
        assert len(changes) == 1
        assert changes[0].path == "src/main.py"
        assert changes[0].action == "create"

    def test_cascade_delete(self, store):
        store.create_session(Session(id="s1"))
        store.create_message(Message(id="m1", session_id="s1", role="user"))
        store.create_file_change(FileChange(
            id="f1", session_id="s1", message_id="m1", path="x.py",
        ))
        store.delete_session("s1")
        assert store.get_file_changes("s1") == []
        assert store.get_messages("s1") == []


class TestStoreLifecycle:
    def test_in_memory(self):
        store = Store(":memory:")
        store.create_session(Session(id="s1"))
        assert store.get_session("s1") is not None
        store.close()

    def test_context_manager(self):
        with Store(":memory:") as store:
            store.create_session(Session(id="s1"))
            assert store.get_session("s1") is not None
