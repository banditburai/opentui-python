"""Windows terminal backend using Console API via ctypes.

Requires Windows 10 1809+ for ENABLE_VIRTUAL_TERMINAL_INPUT.
"""

from __future__ import annotations

import atexit
import contextlib
import ctypes
import ctypes.wintypes

# Console mode flags
ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11

WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
INFINITE = 0xFFFFFFFF


def _get_kernel32():  # type: ignore[no-untyped-def]
    """Lazy accessor for kernel32 — avoids crash if imported on non-Windows."""
    return ctypes.windll.kernel32  # type: ignore[attr-defined]


class WindowsBackend:
    """Terminal backend for Windows using Console API + VT input mode."""

    def __init__(self) -> None:
        self._kernel32 = _get_kernel32()
        self._stdin_handle = self._kernel32.GetStdHandle(STD_INPUT_HANDLE)
        self._stdout_handle = self._kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        self._orig_stdin_mode = ctypes.wintypes.DWORD(0)
        self._orig_stdout_mode = ctypes.wintypes.DWORD(0)
        self._pushback: list[int] = []
        self._atexit_registered = False

    def start(self) -> None:
        # Save original modes
        self._kernel32.GetConsoleMode(self._stdin_handle, ctypes.byref(self._orig_stdin_mode))
        self._kernel32.GetConsoleMode(self._stdout_handle, ctypes.byref(self._orig_stdout_mode))

        # Configure stdin: disable line/echo/processed input, enable VT input
        new_stdin_mode = (
            self._orig_stdin_mode.value
            & ~ENABLE_LINE_INPUT
            & ~ENABLE_ECHO_INPUT
            & ~ENABLE_PROCESSED_INPUT
        ) | ENABLE_VIRTUAL_TERMINAL_INPUT
        self._kernel32.SetConsoleMode(self._stdin_handle, new_stdin_mode)

        # Configure stdout: enable VT processing for ANSI output
        new_stdout_mode = self._orig_stdout_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        self._kernel32.SetConsoleMode(self._stdout_handle, new_stdout_mode)

        if not self._atexit_registered:
            atexit.register(self._atexit_restore)
            self._atexit_registered = True

    def _atexit_restore(self) -> None:
        with contextlib.suppress(Exception):
            self._kernel32.SetConsoleMode(self._stdin_handle, self._orig_stdin_mode.value)
            self._kernel32.SetConsoleMode(self._stdout_handle, self._orig_stdout_mode.value)

    def stop(self) -> None:
        self._kernel32.SetConsoleMode(self._stdin_handle, self._orig_stdin_mode.value)
        self._kernel32.SetConsoleMode(self._stdout_handle, self._orig_stdout_mode.value)

    def has_data(self, timeout: float = 0) -> bool:
        if self._pushback:
            return True
        timeout_ms = int(timeout * 1000) if timeout > 0 else 0
        result = self._kernel32.WaitForSingleObject(self._stdin_handle, timeout_ms)
        return result == WAIT_OBJECT_0

    def read_byte(self) -> int:
        if self._pushback:
            return self._pushback.pop(0)
        # In VT input mode, ReadFile delivers UTF-8 VT sequences
        buf = ctypes.create_string_buffer(1)
        bytes_read = ctypes.wintypes.DWORD(0)
        ok = self._kernel32.ReadFile(self._stdin_handle, buf, 1, ctypes.byref(bytes_read), None)
        if not ok or bytes_read.value == 0:
            return -1
        return buf.raw[0]

    def unread(self, byte: int) -> None:
        """Push a byte back to the front of the read buffer."""
        self._pushback.insert(0, byte)
