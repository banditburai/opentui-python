"""In-memory test backend — no OS pipes, no platform-specific code."""

from __future__ import annotations


class BufferBackend:
    """Pure-Python in-memory backend for testing.

    Replaces the pipe-based TestInputHandler approach — eliminates
    cross-platform pipe/select issues entirely.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def has_data(self, timeout: float = 0) -> bool:
        return len(self._buf) > 0

    def read_byte(self) -> int:
        return self._buf.pop(0)

    def feed(self, data: bytes | str) -> None:
        """Add data to the read buffer."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._buf.extend(data)

    def unread(self, byte: int) -> None:
        """Push a byte back to the front of the buffer (for peek/unget)."""
        self._buf.insert(0, byte)
