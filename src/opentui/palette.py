"""Terminal palette detection via OSC 4/10/11 queries.

Queries the terminal for its colour palette (indexed colours 0-255) and
special colours (foreground,
background, cursor, etc.) using Operating System Command escape sequences.

In **test mode** the caller supplies mock stdin/stdout objects so that no
real terminal is required.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# OSC response regexes — match both BEL (\x07) and ST (\x1b\\) terminators
# ---------------------------------------------------------------------------

# OSC 4 response: \x1b]4;<index>;rgb:RRRR/GGGG/BBBB\x07  OR  \x1b]4;<index>;#RRGGBB\x07
_OSC4_RE = re.compile(
    r"\x1b\]4;(\d+);"
    r"(?:(?:rgb:)([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)"
    r"|#([0-9a-fA-F]{6}))"
    r"(?:\x07|\x1b\\)"
)

# OSC 10-19 special colour response
_OSC_SPECIAL_RE = re.compile(
    r"\x1b\](\d+);"
    r"(?:(?:rgb:)([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)"
    r"|#([0-9a-fA-F]{6}))"
    r"(?:\x07|\x1b\\)"
)


# ---------------------------------------------------------------------------
# Colour conversion helpers
# ---------------------------------------------------------------------------


def _scale_component(comp: str) -> str:
    """Scale a hex component of arbitrary width to 2-digit hex (0-255)."""
    val = int(comp, 16)
    max_in = (1 << (4 * len(comp))) - 1
    scaled = round((val / max_in) * 255)
    return f"{scaled:02x}"


def _to_hex(
    r: str | None = None,
    g: str | None = None,
    b: str | None = None,
    hex6: str | None = None,
) -> str:
    """Convert parsed OSC colour components to a ``#rrggbb`` string."""
    if hex6:
        return f"#{hex6.lower()}"
    if r and g and b:
        return f"#{_scale_component(r)}{_scale_component(g)}{_scale_component(b)}"
    return "#000000"


# ---------------------------------------------------------------------------
# TerminalColors dataclass
# ---------------------------------------------------------------------------


@dataclass
class TerminalColors:
    """Result of a palette detection query."""

    palette: list[str | None] = field(default_factory=list)
    default_foreground: str | None = None
    default_background: str | None = None
    cursor_color: str | None = None
    mouse_foreground: str | None = None
    mouse_background: str | None = None
    tek_foreground: str | None = None
    tek_background: str | None = None
    highlight_background: str | None = None
    highlight_foreground: str | None = None


# ---------------------------------------------------------------------------
# Mock stream protocol for test mode
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TerminalPaletteDetector
# ---------------------------------------------------------------------------


class TerminalPaletteDetector:
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

    # -- write helper -------------------------------------------------------

    def _write_osc(self, osc: str) -> None:
        self._write_fn(osc)

    # -- listener management ------------------------------------------------

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

    # -- detection methods --------------------------------------------------

    async def detect_osc_support(self, timeout_ms: float = 300) -> bool:
        """Send ``OSC 4;0;?`` and wait for a response.

        Returns True if the terminal responds, False on timeout.
        """
        stdout = self._stdout
        stdin = self._stdin

        is_tty_out = getattr(stdout, "is_tty", getattr(stdout, "isTTY", False))
        is_tty_in = getattr(stdin, "is_tty", getattr(stdin, "isTTY", False))

        if not is_tty_out or not is_tty_in:
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

    async def _query_palette(
        self,
        indices: list[int],
        timeout_ms: float = 1200,
    ) -> dict[int, str | None]:
        """Query indexed colours via OSC 4."""
        stdout = self._stdout
        stdin = self._stdin

        results: dict[int, str | None] = dict.fromkeys(indices)

        is_tty_out = getattr(stdout, "is_tty", getattr(stdout, "isTTY", False))
        is_tty_in = getattr(stdin, "is_tty", getattr(stdin, "isTTY", False))

        if not is_tty_out or not is_tty_in:
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

            for m in _OSC4_RE.finditer(buf):
                idx = int(m.group(1))
                if idx in results:
                    results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))

            # Trim buffer to prevent unbounded growth
            if len(buf) > 8192:
                buf = buf[-4096:]

            # Check if all indices resolved
            done_count = sum(1 for v in results.values() if v is not None)
            if done_count == len(results):
                _resolve()
                return

            # Reset idle timer on each data arrival
            if idle_handle is not None:
                idle_handle.cancel()
            idle_handle = loop.call_later(0.15, _resolve)

        self._add_stdin_listener(on_data)

        # Send queries
        queries = "".join(f"\x1b]4;{i};?\x07" for i in indices)
        self._write_osc(queries)

        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000.0)
        except (TimeoutError, asyncio.CancelledError):
            return results
        finally:
            if idle_handle is not None:
                idle_handle.cancel()
            self._remove_stdin_listener(on_data)

    async def _query_special_colors(
        self,
        timeout_ms: float = 1200,
    ) -> dict[int, str | None]:
        """Query special colours via OSC 10-19."""
        stdout = self._stdout
        stdin = self._stdin

        special_indices = [10, 11, 12, 13, 14, 15, 16, 17, 19]
        results: dict[int, str | None] = dict.fromkeys(special_indices)

        is_tty_out = getattr(stdout, "is_tty", getattr(stdout, "isTTY", False))
        is_tty_in = getattr(stdin, "is_tty", getattr(stdin, "isTTY", False))

        if not is_tty_out or not is_tty_in:
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
            updated = False

            for m in _OSC_SPECIAL_RE.finditer(buf):
                idx = int(m.group(1))
                if idx in results:
                    results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))
                    updated = True

            if len(buf) > 8192:
                buf = buf[-4096:]

            done_count = sum(1 for v in results.values() if v is not None)
            if done_count == len(results):
                _resolve()
                return

            if not updated:
                return

            if idle_handle is not None:
                idle_handle.cancel()
            idle_handle = loop.call_later(0.15, _resolve)

        self._add_stdin_listener(on_data)

        queries = "".join(f"\x1b]{i};?\x07" for i in special_indices)
        self._write_osc(queries)

        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000.0)
        except (TimeoutError, asyncio.CancelledError):
            return results
        finally:
            if idle_handle is not None:
                idle_handle.cancel()
            self._remove_stdin_listener(on_data)

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


# ---------------------------------------------------------------------------
# Mock streams for testing
# ---------------------------------------------------------------------------


class MockPaletteStdin:
    """Mock stdin for palette detection tests.

    Supports the listener-based protocol that ``TerminalPaletteDetector``
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
    "TerminalPaletteDetector",
    "MockPaletteStdin",
    "MockPaletteStdout",
]
