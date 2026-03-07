"""File watcher with debouncing."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable


class FileWatcher:
    """Polls for file system changes with debouncing.

    Usage:
        w = FileWatcher("/path/to/dir", debounce=0.3)
        w.on_change = lambda paths: print("Changed:", paths)
        w.start()
        ...
        w.stop()
    """

    def __init__(
        self,
        root: str | Path,
        *,
        debounce: float = 0.3,
        ignore_patterns: list[str] | None = None,
    ) -> None:
        self.root = Path(root)
        self.debounce = debounce
        self.ignore_patterns = ignore_patterns or []
        self.on_change: Callable[[list[str]], None] | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._snapshot: dict[str, float] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start watching for changes."""
        if self._running:
            return
        self._running = True
        self._snapshot = self._scan()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _should_ignore(self, name: str) -> bool:
        """Check if a filename matches any ignore pattern."""
        import fnmatch
        for pat in self.ignore_patterns:
            if fnmatch.fnmatch(name, pat):
                return True
        return False

    def _scan(self) -> dict[str, float]:
        """Scan directory and return {path: mtime} dict."""
        result: dict[str, float] = {}
        try:
            for entry in os.scandir(self.root):
                if self._should_ignore(entry.name):
                    continue
                try:
                    result[entry.path] = entry.stat().st_mtime
                except OSError:
                    pass
        except OSError:
            pass
        return result

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            time.sleep(self.debounce)
            new_snapshot = self._scan()
            changed: list[str] = []

            # Detect new or modified files
            for path, mtime in new_snapshot.items():
                old_mtime = self._snapshot.get(path)
                if old_mtime is None or mtime > old_mtime:
                    changed.append(path)

            # Detect deleted files
            for path in self._snapshot:
                if path not in new_snapshot:
                    changed.append(path)

            self._snapshot = new_snapshot

            if changed and self.on_change is not None:
                self.on_change(changed)
