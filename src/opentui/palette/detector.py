"""Terminal palette detection via OSC 4/10/11 queries.

Queries the terminal for its colour palette (indexed colours 0-255) and
special colours (foreground,
background, cursor, etc.) using Operating System Command escape sequences.

In **test mode** the caller supplies mock stdin/stdout objects so that no
real terminal is required.
"""

import asyncio
import re
from typing import Any, Protocol, runtime_checkable

from .common import (
    OSC4_RE as _OSC4_RE,
)
from .common import (
    OSC_SPECIAL_RE as _OSC_SPECIAL_RE,
)
from .common import (
    TerminalColors,
    _to_hex,
)


@runtime_checkable
class MockStdin(Protocol):
    """Protocol for mock stdin streams used in palette detection tests."""

    is_tty: bool

    def add_data_listener(self, listener: Any) -> None: ...
    def remove_data_listener(self, listener: Any) -> None: ...
    def listener_count(self) -> int: ...


@runtime_checkable
class MockStdout(Protocol):
    """Protocol for mock stdout streams used in palette detection tests."""

    is_tty: bool

    def write(self, data: str) -> bool: ...


class TerminalPalette:
    """Detects the terminal's colour palette via OSC escape sequences.

    In production, *stdin*/*stdout* are real TTY streams.  In test mode,
    callers supply mock objects implementing the ``MockStdin``/``MockStdout``
    protocols.
    """

    def __init__(
        self,
        stdin: Any,
        stdout: Any,
        write_fn: Any | None = None,
    ) -> None:
        self._stdin = stdin
        self._stdout = stdout
        self._write_fn = write_fn or stdout.write
        self._active_listeners: list[Any] = []
        self._active_handles: list[asyncio.TimerHandle | asyncio.Task] = []

    def _write_osc(self, osc: str) -> None:
        self._write_fn(osc)

    def _add_stdin_listener(self, listener: Any) -> None:
        """Add a data listener to stdin (supports both mock and real)."""
        self._active_listeners.append(listener)
        stdin = self._stdin
        if hasattr(stdin, "add_data_listener"):
            stdin.add_data_listener(listener)
        elif hasattr(stdin, "on"):
            stdin.on("data", listener)

    def _remove_stdin_listener(self, listener: Any) -> None:
        """Remove a data listener from stdin."""
        if listener in self._active_listeners:
            self._active_listeners.remove(listener)
        stdin = self._stdin
        if hasattr(stdin, "remove_data_listener"):
            stdin.remove_data_listener(listener)
        elif hasattr(stdin, "removeListener"):
            stdin.removeListener("data", listener)

    def cleanup(self) -> None:
        """Remove all active listeners and cancel timers."""
        for listener in list(self._active_listeners):
            self._remove_stdin_listener(listener)
        self._active_listeners.clear()

    def _is_tty(self) -> bool:
        """Check if both stdout and stdin are TTYs."""
        is_out = getattr(self._stdout, "is_tty", getattr(self._stdout, "isTTY", False))
        is_in = getattr(self._stdin, "is_tty", getattr(self._stdin, "isTTY", False))
        return bool(is_out and is_in)

    async def detect_osc_support(self, timeout_ms: float = 300) -> bool:
        """Send ``OSC 4;0;?`` and wait for a response.

        Returns True if the terminal responds, False on timeout.
        """
        if not self._is_tty():
            return False

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        buf = ""

        def on_data(chunk: Any) -> None:
            nonlocal buf
            buf += str(chunk) if not isinstance(chunk, str) else chunk
            if _OSC4_RE.search(buf):
                if not future.done():
                    future.set_result(True)
                self._remove_stdin_listener(on_data)

        self._add_stdin_listener(on_data)
        self._write_osc("\x1b]4;0;?\x07")

        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000.0)
        except (TimeoutError, asyncio.CancelledError):
            return False
        finally:
            self._remove_stdin_listener(on_data)

    async def _query_colors(
        self,
        indices: list[int],
        regex: re.Pattern,
        query_fmt: str,
        timeout_ms: float = 1200,
    ) -> dict[int, str | None]:
        """Query colours via OSC sequences.

        Args:
            indices: Colour indices to query.
            regex: Compiled pattern matching terminal responses.
            query_fmt: Format string for query (e.g. ``"\\x1b]4;{i};?\\x07"``).
            timeout_ms: Timeout in milliseconds.
        """
        results: dict[int, str | None] = dict.fromkeys(indices)
        if not self._is_tty():
            return results

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[int, str | None]] = loop.create_future()
        buf = ""
        idle_handle: asyncio.TimerHandle | None = None

        def _resolve() -> None:
            nonlocal idle_handle
            if idle_handle is not None:
                idle_handle.cancel()
                idle_handle = None
            self._remove_stdin_listener(on_data)
            if not future.done():
                future.set_result(results)

        def on_data(chunk: Any) -> None:
            nonlocal buf, idle_handle
            buf += str(chunk) if not isinstance(chunk, str) else chunk
            matched = False

            for m in regex.finditer(buf):
                idx = int(m.group(1))
                if idx in results:
                    results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))
                    matched = True

            if len(buf) > 8192:
                buf = buf[-4096:]

            if all(v is not None for v in results.values()):
                _resolve()
                return

            if not matched:
                return

            if idle_handle is not None:
                idle_handle.cancel()
            idle_handle = loop.call_later(0.15, _resolve)

        self._add_stdin_listener(on_data)
        self._write_osc("".join(query_fmt.format(i=i) for i in indices))

        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000.0)
        except (TimeoutError, asyncio.CancelledError):
            return results
        finally:
            if idle_handle is not None:
                idle_handle.cancel()
            self._remove_stdin_listener(on_data)

    async def _query_palette(
        self,
        indices: list[int],
        timeout_ms: float = 1200,
    ) -> dict[int, str | None]:
        """Query indexed colours via OSC 4."""
        return await self._query_colors(indices, _OSC4_RE, "\x1b]4;{i};?\x07", timeout_ms)

    async def _query_special_colors(self, timeout_ms: float = 1200) -> dict[int, str | None]:
        """Query special colours via OSC 10-19."""
        return await self._query_colors(
            [10, 11, 12, 13, 14, 15, 16, 17, 19],
            _OSC_SPECIAL_RE,
            "\x1b]{i};?\x07",
            timeout_ms,
        )

    async def detect(
        self,
        timeout: float = 5000,
        size: int = 16,
    ) -> TerminalColors:
        """Detect the terminal's colour palette and special colours.

        Args:
            timeout: Timeout in milliseconds for the detection.
            size: Number of indexed colours to query (default 16, max 256).

        Returns:
            A ``TerminalColors`` object.
        """
        supported = await self.detect_osc_support()

        if not supported:
            return TerminalColors(
                palette=[None] * size,
            )

        indices = list(range(size))
        palette_results, special_colors = await asyncio.gather(
            self._query_palette(indices, timeout),
            self._query_special_colors(timeout),
        )

        palette_list: list[str | None] = [palette_results.get(i) for i in range(size)]

        return TerminalColors(
            palette=palette_list,
            default_foreground=special_colors.get(10),
            default_background=special_colors.get(11),
            cursor_color=special_colors.get(12),
            mouse_foreground=special_colors.get(13),
            mouse_background=special_colors.get(14),
            tek_foreground=special_colors.get(15),
            tek_background=special_colors.get(16),
            highlight_background=special_colors.get(17),
            highlight_foreground=special_colors.get(19),
        )


class MockPaletteStdin:
    """Mock stdin for palette detection tests.

    Supports the listener-based protocol that ``TerminalPalette``
    uses.  Test code calls ``emit_data(data)`` to simulate terminal
    responses.
    """

    def __init__(self, *, is_tty: bool = True) -> None:
        self.is_tty = is_tty
        self.isTTY = is_tty  # API compatibility
        self._listeners: list[Any] = []

    def add_data_listener(self, listener: Any) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_data_listener(self, listener: Any) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def listener_count(self) -> int:
        return len(self._listeners)

    def emit_data(self, data: str) -> None:
        """Simulate data arriving on stdin."""
        for listener in list(self._listeners):
            listener(data)


class MockPaletteStdout:
    """Mock stdout for palette detection tests.

    Records all writes so tests can assert on OSC queries that were sent.
    Optionally calls a *responder* callback when data is written, allowing
    the test to simulate terminal responses to specific queries.
    """

    def __init__(
        self,
        *,
        is_tty: bool = True,
        responder: Any | None = None,
    ) -> None:
        self.is_tty = is_tty
        self.isTTY = is_tty  # API compatibility
        self.writes: list[str] = []
        self._responder = responder

    def write(self, data: str) -> bool:
        self.writes.append(data)
        if self._responder is not None:
            self._responder(data)
        return True


__all__ = [
    "TerminalColors",
    "TerminalPalette",
    "MockPaletteStdin",
    "MockPaletteStdout",
]
