"""opencode.fs — File system operations and git integration."""

from .git import GitOps
from .watcher import FileWatcher

__all__ = ["GitOps", "FileWatcher"]
