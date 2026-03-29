"""Unix terminal backend using termios/tty/select."""

from __future__ import annotations

import atexit
import contextlib
import os
import select
import sys
import termios
import tty


class UnixBackend:
    """Terminal backend for Unix systems (macOS, Linux)."""

    def __init__(self) -> None:
        self._fd: int = -1
        self._old_settings: list | None = None
        self._pushback: list[int] = []
        self._atexit_registered = False

    @property
    def fd(self) -> int:
        """Raw file descriptor for stdin (implementation-specific)."""
        return self._fd

    def start(self) -> None:
        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        # Disable ISIG so Ctrl+C delivers \x03 byte to stdin instead of
        # raising SIGINT.  Disable IEXTEN so VDISCARD (Ctrl+O on macOS)
        # and VLNEXT (Ctrl+V) aren't consumed by the line discipline.
        new_settings = termios.tcgetattr(self._fd)
        new_settings[0] &= ~termios.ICRNL  # iflag: don't translate CR->NL
        new_settings[3] &= ~(termios.ISIG | termios.IEXTEN)  # lflags
        termios.tcsetattr(self._fd, termios.TCSANOW, new_settings)
        if not self._atexit_registered:
            atexit.register(self._atexit_restore)
            self._atexit_registered = True

    def _atexit_restore(self) -> None:
        with contextlib.suppress(Exception):
            if self._old_settings is not None:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
                self._old_settings = None

    def stop(self) -> None:
        if self._old_settings is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            self._old_settings = None

    def has_data(self, timeout: float = 0) -> bool:
        if self._pushback:
            return True
        return bool(select.select([self._fd], [], [], timeout)[0])

    def read_byte(self) -> int:
        if self._pushback:
            return self._pushback.pop(0)
        data = os.read(self._fd, 1)
        if not data:
            return -1
        return data[0]

    def unread(self, byte: int) -> None:
        """Push a byte back to the front of the read buffer."""
        self._pushback.insert(0, byte)
