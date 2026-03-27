"""Testing utilities — buffer capture, diff, and frame recording."""

import ctypes
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

DiffType = Literal["line_count", "text", "width"]


class DiffResult:
    def __init__(
        self,
        type: DiffType,
        message: str,
        line: int | None = None,
        expected: str | None = None,
        actual: str | None = None,
    ):
        self.type = type
        self.message = message
        self.line = line
        self.expected = expected
        self.actual = actual


class BufferDiff:
    """Utility for comparing buffer outputs between implementations."""

    def __init__(self, expected: list[dict], actual: list[dict]):
        self.expected = expected
        self.actual = actual
        self.differences: list[DiffResult] = []

    def compare(self) -> list[DiffResult]:
        """Compare expected and actual buffers."""
        self.differences = []

        if len(self.expected) != len(self.actual):
            self.differences.append(
                DiffResult(
                    type="line_count",
                    message=f"Line count mismatch: expected {len(self.expected)}, got {len(self.actual)}",
                )
            )
            return self.differences

        for y, (exp_line, act_line) in enumerate(zip(self.expected, self.actual, strict=False)):
            exp_text = exp_line.get("text", "")
            act_text = act_line.get("text", "")

            if exp_text != act_text:
                self.differences.append(
                    DiffResult(
                        type="text",
                        message=f"Line {y} text mismatch",
                        line=y,
                        expected=exp_text,
                        actual=act_text,
                    )
                )

            exp_width = exp_line.get("width", len(exp_text))
            act_width = act_line.get("width", len(act_text))

            if exp_width != act_width:
                self.differences.append(
                    DiffResult(
                        type="width",
                        message=f"Line {y} width mismatch: expected {exp_width}, got {act_width}",
                        line=y,
                        expected=str(exp_width),
                        actual=str(act_width),
                    )
                )

        return self.differences

    def has_differences(self) -> bool:
        """Check if there are any differences."""
        return bool(self.differences)

    def summary(self) -> str:
        """Get a summary of differences."""
        if not self.differences:
            return "No differences found"

        lines = [f"Found {len(self.differences)} difference(s):"]
        for diff in self.differences:
            lines.append(f"  - {diff.message}")
        return "\n".join(lines)


def assert_buffer_equal(expected: list[dict], actual: list[dict]) -> None:
    """Assert that two buffers are equal, raise on difference."""
    diff = BufferDiff(expected, actual)
    differences = diff.compare()

    if differences:
        raise AssertionError(diff.summary())


@dataclass
class RecordedBuffers:
    """Buffer data captured from a single frame."""

    fg: list[float] | None = None
    bg: list[float] | None = None
    attributes: list[int] | None = None


@dataclass
class RecordedFrame:
    """A single captured frame from the TestRecorder."""

    frame: str
    timestamp: float
    frame_number: int
    buffers: RecordedBuffers | None = None


class TestRecorder:
    """Records frames from a renderer by hooking into the render pipeline."""

    __test__ = False  # Not a pytest test class

    def __init__(self, renderer: Any, options: dict | None = None) -> None:
        self._renderer = renderer
        self._frames: list[RecordedFrame] = []
        self._recording = False
        self._frame_number = 0
        self._start_time: float = 0
        self._original_render_frame: Any = None
        opts = options or {}
        self._record_buffers: dict = opts.get("record_buffers", {})
        self._now: Callable[[], float] = opts.get("now", lambda: time.monotonic() * 1000)

    def rec(self) -> None:
        """Start recording frames."""
        if self._recording:
            return

        self._recording = True
        self._frames = []
        self._frame_number = 0
        self._start_time = self._now()

        original = self._renderer._render_frame
        self._original_render_frame = original

        def hooked_render_frame(dt: float) -> None:
            original(dt)
            if self._recording:
                self._capture_frame()

        self._renderer._render_frame = hooked_render_frame

    def stop(self) -> None:
        """Stop recording and restore original render method."""
        if not self._recording:
            return

        self._recording = False

        if self._original_render_frame is not None:
            self._renderer._render_frame = self._original_render_frame
            self._original_render_frame = None

    @property
    def recorded_frames(self) -> list[RecordedFrame]:
        """Return a copy of the recorded frames list."""
        return list(self._frames)

    @property
    def is_recording(self) -> bool:
        return self._recording

    def clear(self) -> None:
        """Clear all recorded frames."""
        self._frames = []
        self._frame_number = 0

    def _capture_frame(self) -> None:
        """Capture the current frame from the renderer's buffer."""
        buffer = self._renderer.get_current_buffer()
        frame_text = buffer.get_plain_text()

        recorded = RecordedFrame(
            frame=frame_text,
            timestamp=self._now() - self._start_time,
            frame_number=self._frame_number,
        )
        self._frame_number += 1

        if (
            self._record_buffers.get("fg")
            or self._record_buffers.get("bg")
            or self._record_buffers.get("attributes")
        ):
            w = buffer.width
            h = buffer.height
            size = w * h
            buffers = RecordedBuffers()

            if self._record_buffers.get("fg"):
                fg_ptr = buffer._native.buffer_get_fg_ptr(buffer._ptr)
                arr = (ctypes.c_float * (size * 4)).from_address(fg_ptr)
                buffers.fg = list(arr)

            if self._record_buffers.get("bg"):
                bg_ptr = buffer._native.buffer_get_bg_ptr(buffer._ptr)
                arr = (ctypes.c_float * (size * 4)).from_address(bg_ptr)
                buffers.bg = list(arr)

            if self._record_buffers.get("attributes"):
                attr_ptr = buffer._native.buffer_get_attributes_ptr(buffer._ptr)
                arr = (ctypes.c_uint32 * size).from_address(attr_ptr)
                buffers.attributes = list(arr)

            recorded.buffers = buffers

        self._frames.append(recorded)


@dataclass
class CapturedSpan:
    """A contiguous run of cells with the same styling."""

    text: str
    width: int
    fg: Any  # RGBA
    bg: Any  # RGBA
    attributes: int


@dataclass
class CapturedLine:
    """A single line of captured spans."""

    spans: list[CapturedSpan] = field(default_factory=list)


@dataclass
class CapturedFrame:
    """Full frame capture with styled spans."""

    cols: int
    rows: int
    lines: list[CapturedLine]
    cursor: tuple[int, int]


def capture_spans(renderer: Any) -> CapturedFrame:
    """Read the current buffer and group cells into styled spans.

    Iterates over every cell in the buffer, reading fg color, bg color,
    attributes, and character. Adjacent cells with matching style are
    grouped into a single :class:`CapturedSpan`.

    Args:
        renderer: A CliRenderer instance.

    Returns:
        A :class:`CapturedFrame` with cols, rows, lines (list of CapturedLine),
        and cursor position.
    """
    from .. import structs as s

    buffer = renderer.get_current_buffer()
    w = buffer.width
    h = buffer.height

    # Get raw text for character data
    try:
        raw: bytes = buffer._native.buffer_write_resolved_chars(buffer._ptr, True)
        text = raw.decode("utf-8", errors="replace") if raw else ""
    except Exception:
        text = ""

    text_lines = text.split("\n")

    fg_ptr = buffer._native.buffer_get_fg_ptr(buffer._ptr)
    bg_ptr = buffer._native.buffer_get_bg_ptr(buffer._ptr)
    attr_ptr = buffer._native.buffer_get_attributes_ptr(buffer._ptr)

    lines: list[CapturedLine] = []

    for y in range(h):
        line_text = text_lines[y] if y < len(text_lines) else ""
        spans: list[CapturedSpan] = []
        current_text = ""
        current_width = 0
        current_fg: s.RGBA | None = None
        current_bg: s.RGBA | None = None
        current_attr: int | None = None

        for x in range(w):
            # Read fg color
            fg_offset = (y * w + x) * 4
            fg_arr = (ctypes.c_float * 4).from_address(
                fg_ptr + fg_offset * ctypes.sizeof(ctypes.c_float)
            )
            fg = s.RGBA(fg_arr[0], fg_arr[1], fg_arr[2], fg_arr[3])

            # Read bg color
            bg_arr = (ctypes.c_float * 4).from_address(
                bg_ptr + fg_offset * ctypes.sizeof(ctypes.c_float)
            )
            bg = s.RGBA(bg_arr[0], bg_arr[1], bg_arr[2], bg_arr[3])

            # Read attributes
            attr_offset = y * w + x
            a_arr = (ctypes.c_uint32 * 1).from_address(
                attr_ptr + attr_offset * ctypes.sizeof(ctypes.c_uint32)
            )
            attr = a_arr[0]

            ch = line_text[x] if x < len(line_text) else " "

            # Check if this cell continues the current span
            if (
                current_fg is not None
                and fg == current_fg
                and bg == current_bg
                and attr == current_attr
            ):
                current_text += ch
                current_width += 1
            else:
                # Flush current span
                if current_fg is not None:
                    spans.append(
                        CapturedSpan(
                            text=current_text,
                            width=current_width,
                            fg=current_fg,
                            bg=current_bg,
                            attributes=current_attr,  # type: ignore[arg-type]
                        )
                    )
                current_text = ch
                current_width = 1
                current_fg = fg
                current_bg = bg
                current_attr = attr

        # Flush last span
        if current_fg is not None:
            spans.append(
                CapturedSpan(
                    text=current_text,
                    width=current_width,
                    fg=current_fg,
                    bg=current_bg,
                    attributes=current_attr,  # type: ignore[arg-type]
                )
            )

        lines.append(CapturedLine(spans=spans))

    cursor_x = getattr(renderer, "_cursor_x", 0)
    cursor_y = getattr(renderer, "_cursor_y", 0)

    return CapturedFrame(cols=w, rows=h, lines=lines, cursor=(cursor_x, cursor_y))
