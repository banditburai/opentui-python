"""File watcher with debouncing."""

from __future__ import annotations

import fnmatch
import os
import threading
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
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot: dict[str, float] = {}

    @property
    def is_running(self) -> bool:
        return self._thread is not None and not self._stop_event.is_set()

    def start(self) -> None:
        """Start watching for changes."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._snapshot = self._scan()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _should_ignore(self, name: str) -> bool:
        """Check if a filename matches any ignore pattern."""
        for pat in self.ignore_patterns:
            if fnmatch.fnmatch(name, pat):
                return True
        return False

    def _scan(self) -> dict[str, float]:
        """Recursively scan directory and return {path: mtime} dict."""
        result: dict[str, float] = {}
        try:
            for dirpath, dirnames, filenames in os.walk(self.root):
                # Filter ignored directories in-place to prevent descent
                dirnames[:] = [d for d in dirnames if not self._should_ignore(d)]
                for name in filenames:
                    if self._should_ignore(name):
                        continue
                    full = os.path.join(dirpath, name)
                    try:
                        result[full] = os.stat(full).st_mtime
                    except OSError:
                        pass
        except OSError:
            pass
        return result

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while not self._stop_event.wait(timeout=self.debounce):
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

            callback = self.on_change
            if changed and callback is not None:
                callback(changed)
