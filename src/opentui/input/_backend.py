"""TerminalBackend protocol and platform factory."""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable


@runtime_checkable
class TerminalBackend(Protocol):
    """Abstract interface for low-level terminal I/O.

    Primitives:
    - start()/stop() — enter/exit raw mode
    - has_data(timeout) — check if input bytes are available
    - read_byte() — read one byte (returns int 0-255)
    - unread(byte) — push a byte back to the front of the read buffer
    """

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def has_data(self, timeout: float = 0) -> bool: ...
    def read_byte(self) -> int: ...
    def unread(self, byte: int) -> None: ...


def create_backend() -> TerminalBackend:
    """Create a platform-appropriate terminal backend."""
    if sys.platform == "win32":
        from ._backend_windows import WindowsBackend

        return WindowsBackend()
    from ._backend_unix import UnixBackend

    return UnixBackend()
