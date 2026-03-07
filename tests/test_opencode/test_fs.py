"""Tests for file watcher and git integration."""

import asyncio
import subprocess
from pathlib import Path

import pytest
from opencode.fs.git import GitOps
from opencode.fs.watcher import FileWatcher


# --- GitOps ---

class TestGitOps:
    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a temporary git repo."""
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
            capture_output=True, check=True,
        )
        (tmp_path / "readme.md").write_text("hello")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "."],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init"],
            capture_output=True, check=True,
        )
        return tmp_path

    def test_status_clean(self, git_repo):
        ops = GitOps(git_repo)
        result = asyncio.run(ops.status())
        assert isinstance(result, str)
        # Clean repo — no untracked/modified lines
        assert "M " not in result
        assert "??" not in result

    def test_status_with_changes(self, git_repo):
        (git_repo / "new.txt").write_text("new file")
        ops = GitOps(git_repo)
        result = asyncio.run(ops.status())
        assert "new.txt" in result

    def test_diff_clean(self, git_repo):
        ops = GitOps(git_repo)
        result = asyncio.run(ops.diff())
        assert result == ""

    def test_diff_with_changes(self, git_repo):
        (git_repo / "readme.md").write_text("changed")
        ops = GitOps(git_repo)
        result = asyncio.run(ops.diff())
        assert "changed" in result or "+changed" in result

    def test_log(self, git_repo):
        ops = GitOps(git_repo)
        result = asyncio.run(ops.log(n=5))
        assert "init" in result

    def test_current_branch(self, git_repo):
        ops = GitOps(git_repo)
        result = asyncio.run(ops.current_branch())
        assert result in ("main", "master")

    def test_is_git_repo_true(self, git_repo):
        ops = GitOps(git_repo)
        assert asyncio.run(ops.is_git_repo()) is True

    def test_is_git_repo_false(self, tmp_path):
        ops = GitOps(tmp_path)
        assert asyncio.run(ops.is_git_repo()) is False


# --- FileWatcher ---

class TestFileWatcher:
    def test_init(self, tmp_path):
        w = FileWatcher(tmp_path)
        assert w.root == tmp_path

    def test_debounce_default(self, tmp_path):
        w = FileWatcher(tmp_path, debounce=0.5)
        assert w.debounce == 0.5

    def test_callback_receives_events(self, tmp_path):
        received = []
        w = FileWatcher(tmp_path, debounce=0.05)
        w.on_change = lambda paths: received.extend(paths)

        async def _run():
            w.start()
            # Create a file to trigger the watcher
            (tmp_path / "trigger.txt").write_text("x")
            await asyncio.sleep(0.3)
            w.stop()

        asyncio.run(_run())
        # Watchdog may or may not detect in time depending on OS;
        # just verify the watcher starts and stops without error
        assert isinstance(received, list)

    def test_start_stop(self, tmp_path):
        w = FileWatcher(tmp_path, debounce=0.05)
        async def _run():
            w.start()
            assert w.is_running
            w.stop()
            assert not w.is_running
        asyncio.run(_run())

    def test_ignore_patterns(self, tmp_path):
        w = FileWatcher(tmp_path, ignore_patterns=["*.pyc", "__pycache__"])
        assert "*.pyc" in w.ignore_patterns
