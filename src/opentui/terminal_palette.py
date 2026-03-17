"""Terminal palette detection via OSC 4/10-19 escape sequences.

Parses ANSI terminal palette responses to extract foreground, background,
cursor, and 256-colour palette values.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Hex = str | None  # "#rrggbb" or None
WriteFunction = Callable[[str], bool]


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# OSC 4 palette response: ESC ] 4 ; <index> ; rgb:RR/GG/BB  BEL|ST
#                       or ESC ] 4 ; <index> ; #RRGGBB       BEL|ST
OSC4_RESPONSE = re.compile(
    r"\x1b]4;(\d+);(?:(?:rgb:)([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)|#([0-9a-fA-F]{6}))(?:\x07|\x1b\\)"
)

# OSC special response: ESC ] <code> ; rgb:RR/GG/BB  BEL|ST
#                     or ESC ] <code> ; #RRGGBB       BEL|ST
OSC_SPECIAL_RESPONSE = re.compile(
    r"\x1b](\d+);(?:(?:rgb:)([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)|#([0-9a-fA-F]{6}))(?:\x07|\x1b\\)"
)


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------


def _scale_component(comp: str) -> str:
    """Scale a hex colour component of arbitrary width to 2 hex digits (0-255)."""
    val = int(comp, 16)
    max_in = (1 << (4 * len(comp))) - 1
    return format(round((val / max_in) * 255), "02x")


def _to_hex(
    r: str | None = None,
    g: str | None = None,
    b: str | None = None,
    hex6: str | None = None,
) -> str:
    """Convert regex-captured groups to a ``#rrggbb`` hex string."""
    if hex6:
        return f"#{hex6.lower()}"
    if r and g and b:
        return f"#{_scale_component(r)}{_scale_component(g)}{_scale_component(b)}"
    return "#000000"


# ---------------------------------------------------------------------------
# tmux passthrough helper
# ---------------------------------------------------------------------------


def _wrap_for_tmux(osc: str) -> str:
    """Wrap OSC sequence for tmux passthrough."""
    escaped = osc.replace("\x1b", "\x1b\x1b")
    return f"\x1bPtmux;{escaped}\x1b\\"


# ---------------------------------------------------------------------------
# Stream protocol  (what MockStream / real TTY must satisfy)
# ---------------------------------------------------------------------------


class ReadableStream(Protocol):
    """Protocol for something that looks like a readable TTY stream."""

    is_tty: bool

    def on_data(self, handler: Callable[[str], None]) -> None: ...

    def remove_listener(self, handler: Callable[[str], None]) -> None: ...


class WritableStream(Protocol):
    """Protocol for something that looks like a writable TTY stream."""

    is_tty: bool

    def write(self, data: str) -> bool: ...


# ---------------------------------------------------------------------------
# TerminalColors dataclass
# ---------------------------------------------------------------------------


@dataclass
class TerminalColors:
    """Result of a full palette detection."""

    palette: list[Hex] = field(default_factory=list)
    default_foreground: Hex = None
    default_background: Hex = None
    cursor_color: Hex = None
    mouse_foreground: Hex = None
    mouse_background: Hex = None
    tek_foreground: Hex = None
    tek_background: Hex = None
    highlight_background: Hex = None
    highlight_foreground: Hex = None


# ---------------------------------------------------------------------------
# GetPaletteOptions
# ---------------------------------------------------------------------------


@dataclass
class GetPaletteOptions:
    timeout: int = 5000  # milliseconds
    size: int = 16


# ---------------------------------------------------------------------------
# Parse helpers  (pure functions operating on string buffers)
# ---------------------------------------------------------------------------


def parse_osc4_responses(data: str) -> dict[int, str]:
    """Parse all OSC 4 colour responses from *data* and return {index: hex}."""
    results: dict[int, str] = {}
    for m in OSC4_RESPONSE.finditer(data):
        idx = int(m.group(1))
        results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))
    return results


def parse_osc_special_responses(data: str) -> dict[int, str]:
    """Parse all OSC special colour responses from *data* and return {code: hex}."""
    results: dict[int, str] = {}
    for m in OSC_SPECIAL_RESPONSE.finditer(data):
        idx = int(m.group(1))
        results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))
    return results


def has_osc4_response(data: str) -> bool:
    """Return ``True`` if *data* contains at least one valid OSC 4 response."""
    return bool(OSC4_RESPONSE.search(data))


# ---------------------------------------------------------------------------
# TerminalPalette
# ---------------------------------------------------------------------------


class TerminalPalette:
    """Detects terminal colour palette by querying OSC 4 / 10-19 sequences.

    This is an event-driven parser.  Call ``feed()`` to push data from stdin
    into the internal buffer, and call the various ``detect_*`` /
    ``query_*`` methods to retrieve results.

    For async usage the class also exposes the higher-level ``detect()``
    and ``detect_osc_support()`` coroutine-like methods that accept a
    *feeder* callback for injecting data over time.

    Parameters
    ----------
    stdin : ReadableStream
        Readable stream (or mock) from which terminal responses arrive.
    stdout : WritableStream
        Writable stream (or mock) to which queries are written.
    write_fn : WriteFunction | None
        Optional custom write function.  When ``None``, ``stdout.write`` is
        used.
    is_legacy_tmux : bool
        When ``True``, all OSC output is wrapped in DCS tmux passthrough.
    """

    def __init__(
        self,
        stdin: ReadableStream,
        stdout: WritableStream,
        write_fn: WriteFunction | None = None,
        is_legacy_tmux: bool = False,
    ) -> None:
        self._stdin = stdin
        self._stdout = stdout
        self._write_fn: WriteFunction = write_fn or stdout.write
        self._in_legacy_tmux = is_legacy_tmux
        self._active_listeners: list[Callable[[str], None]] = []

    # -- internal helpers ---------------------------------------------------

    def _write_osc(self, osc: str) -> bool:
        data = _wrap_for_tmux(osc) if self._in_legacy_tmux else osc
        return self._write_fn(data)

    def cleanup(self) -> None:
        """Remove all active listeners."""
        for handler in list(self._active_listeners):
            self._stdin.remove_listener(handler)
        self._active_listeners.clear()

    # -- OSC support detection (synchronous, callback-driven) ---------------

    def detect_osc_support(self, timeout_ms: int = 300) -> _OSCSupportDetection:
        """Start OSC support detection.

        Returns an ``_OSCSupportDetection`` object that can be resolved by
        feeding data via the stdin mock.  Call ``.result`` after data has
        been fed to check the outcome, or use it in the two-phase detect
        flow.
        """
        if not self._stdout.is_tty or not self._stdin.is_tty:
            return _OSCSupportDetection(result=False)

        det = _OSCSupportDetection()

        def on_data(chunk: str) -> None:
            det._buffer += chunk
            if OSC4_RESPONSE.search(det._buffer):
                det._result = True
                det._done = True

        self._stdin.on_data(on_data)
        self._active_listeners.append(on_data)
        det._handler = on_data
        det._palette = self

        self._write_osc("\x1b]4;0;?\x07")

        return det

    # -- palette query (synchronous, callback-driven) -----------------------

    def query_palette(self, indices: list[int], timeout_ms: int = 1200) -> _PaletteQuery:
        """Start a palette query for the given colour *indices*.

        Returns a ``_PaletteQuery`` object whose ``.results`` dict is
        populated as data arrives from stdin.
        """
        results: dict[int, Hex] = dict.fromkeys(indices)

        if not self._stdout.is_tty or not self._stdin.is_tty:
            return _PaletteQuery(results=results, done=True)

        q = _PaletteQuery(results=results)

        def on_data(chunk: str) -> None:
            q._buffer += chunk

            for m in OSC4_RESPONSE.finditer(q._buffer):
                idx = int(m.group(1))
                if idx in results:
                    results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))

            # Trim buffer if too large
            if len(q._buffer) > 8192:
                q._buffer = q._buffer[-4096:]

            done_count = sum(1 for v in results.values() if v is not None)
            if done_count == len(results):
                q._done = True

        self._stdin.on_data(on_data)
        self._active_listeners.append(on_data)
        q._handler = on_data
        q._palette = self

        query = "".join(f"\x1b]4;{i};?\x07" for i in indices)
        self._write_osc(query)

        return q

    # -- special colours query (synchronous, callback-driven) ---------------

    def query_special_colors(self, timeout_ms: int = 1200) -> _SpecialColorsQuery:
        """Start a special-colours query (OSC 10-19).

        Returns a ``_SpecialColorsQuery`` object whose ``.results`` dict
        is populated as data arrives from stdin.
        """
        results: dict[int, Hex] = {
            10: None,
            11: None,
            12: None,
            13: None,
            14: None,
            15: None,
            16: None,
            17: None,
            19: None,
        }

        if not self._stdout.is_tty or not self._stdin.is_tty:
            return _SpecialColorsQuery(results=results, done=True)

        q = _SpecialColorsQuery(results=results)

        def on_data(chunk: str) -> None:
            q._buffer += chunk

            for m in OSC_SPECIAL_RESPONSE.finditer(q._buffer):
                idx = int(m.group(1))
                if idx in results:
                    results[idx] = _to_hex(m.group(2), m.group(3), m.group(4), m.group(5))

            if len(q._buffer) > 8192:
                q._buffer = q._buffer[-4096:]

            done_count = sum(1 for v in results.values() if v is not None)
            if done_count == len(results):
                q._done = True

        self._stdin.on_data(on_data)
        self._active_listeners.append(on_data)
        q._handler = on_data
        q._palette = self

        self._write_osc(
            "\x1b]10;?\x07"
            "\x1b]11;?\x07"
            "\x1b]12;?\x07"
            "\x1b]13;?\x07"
            "\x1b]14;?\x07"
            "\x1b]15;?\x07"
            "\x1b]16;?\x07"
            "\x1b]17;?\x07"
            "\x1b]19;?\x07"
        )

        return q

    # -- full detection (two-phase) -----------------------------------------

    def detect(self, options: GetPaletteOptions | dict | None = None) -> _FullDetection:
        """Start a full palette detection.

        Phase 1: OSC support probe (``detect_osc_support``).
        Phase 2: If supported, palette + special colours queries run
                 concurrently on the same stdin data stream.

        Returns a ``_FullDetection`` state machine.
        """
        if isinstance(options, dict):
            opts = GetPaletteOptions(**options)
        elif options is None:
            opts = GetPaletteOptions()
        else:
            opts = options

        return _FullDetection(self, opts)


# ---------------------------------------------------------------------------
# Detection state-machine objects
# ---------------------------------------------------------------------------


class _OSCSupportDetection:
    """Tracks the state of an OSC support probe."""

    def __init__(self, *, result: bool | None = None) -> None:
        self._buffer: str = ""
        self._result: bool | None = result
        self._done: bool = result is not None
        self._handler: Callable[[str], None] | None = None
        self._palette: TerminalPalette | None = None

    @property
    def result(self) -> bool | None:
        return self._result

    @property
    def done(self) -> bool:
        return self._done

    def finish(self, default: bool = False) -> bool:
        """Finalise and detach the listener.  Returns the detected value."""
        if self._handler and self._palette:
            self._palette._stdin.remove_listener(self._handler)
            if self._handler in self._palette._active_listeners:
                self._palette._active_listeners.remove(self._handler)
        return self._result if self._result is not None else default


class _PaletteQuery:
    """Tracks the state of a palette colour query."""

    def __init__(self, results: dict[int, Hex], *, done: bool = False) -> None:
        self.results = results
        self._buffer: str = ""
        self._done: bool = done
        self._handler: Callable[[str], None] | None = None
        self._palette: TerminalPalette | None = None

    @property
    def done(self) -> bool:
        return self._done

    def finish(self) -> dict[int, Hex]:
        if self._handler and self._palette:
            self._palette._stdin.remove_listener(self._handler)
            if self._handler in self._palette._active_listeners:
                self._palette._active_listeners.remove(self._handler)
        return self.results


class _SpecialColorsQuery:
    """Tracks the state of a special-colours query."""

    def __init__(self, results: dict[int, Hex], *, done: bool = False) -> None:
        self.results = results
        self._buffer: str = ""
        self._done: bool = done
        self._handler: Callable[[str], None] | None = None
        self._palette: TerminalPalette | None = None

    @property
    def done(self) -> bool:
        return self._done

    def finish(self) -> dict[int, Hex]:
        if self._handler and self._palette:
            self._palette._stdin.remove_listener(self._handler)
            if self._handler in self._palette._active_listeners:
                self._palette._active_listeners.remove(self._handler)
        return self.results


class _FullDetection:
    """Two-phase detection state machine.

    Usage (synchronous test flow)::

        det = palette.detect({"size": 256, "timeout": 2000})

        # Phase 1: Feed OSC support response
        stdin.emit("\\x1b]4;0;#000000\\x07")

        # Advance to phase 2
        det.advance()

        # Phase 2: Feed palette + special colour responses
        for i in range(256):
            stdin.emit(f"\\x1b]4;{i};#000000\\x07")
        stdin.emit("\\x1b]10;#aabbcc\\x07")

        # Retrieve result
        result = det.finish()
    """

    def __init__(self, tp: TerminalPalette, opts: GetPaletteOptions) -> None:
        self._tp = tp
        self._opts = opts
        self._osc_det: _OSCSupportDetection | None = None
        self._palette_q: _PaletteQuery | None = None
        self._special_q: _SpecialColorsQuery | None = None
        self._phase: int = 0  # 0 = not started, 1 = probing, 2 = querying
        self._result: TerminalColors | None = None

        # Immediately start phase 1
        self._start_phase1()

    def _start_phase1(self) -> None:
        self._osc_det = self._tp.detect_osc_support(300)
        self._phase = 1

        # If the non-TTY path short-circuited, produce the null result now
        if self._osc_det.done and not self._osc_det.result:
            self._result = TerminalColors(
                palette=[None] * self._opts.size,
            )

    def advance(self) -> None:
        """Transition from phase 1 to phase 2 if OSC was supported.

        This should be called after feeding the OSC support probe response.
        """
        if self._phase != 1:
            return

        supported = self._osc_det.finish(default=False) if self._osc_det else False

        if not supported:
            self._result = TerminalColors(
                palette=[None] * self._opts.size,
            )
            self._phase = 3
            return

        self._phase = 2
        indices = list(range(self._opts.size))
        self._palette_q = self._tp.query_palette(indices, self._opts.timeout)
        self._special_q = self._tp.query_special_colors(self._opts.timeout)

    def finish(self) -> TerminalColors:
        """Finalise detection and return the ``TerminalColors`` result.

        If still in phase 1, automatically advances.
        """
        if self._result is not None:
            return self._result

        if self._phase == 1:
            self.advance()

        if self._result is not None:
            return self._result

        palette_results = self._palette_q.finish() if self._palette_q else {}
        special_colors = self._special_q.finish() if self._special_q else {}

        return TerminalColors(
            palette=[palette_results.get(i) for i in range(self._opts.size)],
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
# Factory
# ---------------------------------------------------------------------------


def create_terminal_palette(
    stdin: ReadableStream,
    stdout: WritableStream,
    write_fn: WriteFunction | None = None,
    is_legacy_tmux: bool = False,
) -> TerminalPalette:
    return TerminalPalette(stdin, stdout, write_fn, is_legacy_tmux)
