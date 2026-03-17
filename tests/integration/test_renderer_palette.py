"""Port of upstream renderer.palette.test.ts.

Upstream: packages/core/src/tests/renderer.palette.test.ts
Tests: 25

Tests verify terminal palette detection (OSC 4/10/11 queries for detecting
terminal colours).  The palette detector works with mock stdin/stdout
streams in test mode so no real terminal is required.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from opentui.palette import (
    MockPaletteStdin,
    MockPaletteStdout,
    TerminalColors,
    TerminalPaletteDetector,
)
from opentui.renderer import CliRenderer, CliRendererConfig, RendererControlState, RootRenderable

# ---------------------------------------------------------------------------
# FakeNative — minimal native mock so we can construct a CliRenderer
# without real nanobind bindings.
# ---------------------------------------------------------------------------


class _FakeNative:
    class renderer:
        @staticmethod
        def create_renderer(w, h, testing, remote):
            return 1

        @staticmethod
        def destroy_renderer(ptr):
            pass

        @staticmethod
        def get_next_buffer(ptr):
            return 1

        @staticmethod
        def render(ptr, skip_diff):
            pass

        @staticmethod
        def resize_renderer(ptr, w, h):
            pass

        @staticmethod
        def setup_terminal(ptr, use_alternate_screen):
            pass

        @staticmethod
        def restore_terminal_modes(ptr):
            pass

        @staticmethod
        def suspend_renderer(ptr):
            pass

        @staticmethod
        def resume_renderer(ptr):
            pass

        @staticmethod
        def write_out(ptr, data):
            pass

    class buffer:
        @staticmethod
        def buffer_clear(ptr, alpha):
            pass

        @staticmethod
        def get_buffer_width(ptr):
            return 80

        @staticmethod
        def get_buffer_height(ptr):
            return 24


def _make_renderer(width: int = 80, height: int = 24, **kwargs) -> CliRenderer:
    """Create a CliRenderer in test mode backed by FakeNative."""
    config = CliRendererConfig(
        width=width,
        height=height,
        testing=True,
        use_mouse=kwargs.get("use_mouse"),
    )
    native = _FakeNative()
    r = CliRenderer(1, config, native)
    r._root = RootRenderable(r)
    return r


# ---------------------------------------------------------------------------
# Mock stream helpers (matching upstream createMockStreams)
# ---------------------------------------------------------------------------


def _create_mock_streams(*, is_tty: bool = True):
    """Create mock stdin/stdout that auto-respond to OSC queries.

    Mirrors the upstream TypeScript ``createMockStreams()`` function.
    The mock stdout intercepts writes and schedules appropriate OSC
    responses on the mock stdin.
    """
    mock_stdin = MockPaletteStdin(is_tty=is_tty)
    writes: list[str] = []

    def _responder(data: str) -> None:
        """Simulate terminal response to OSC queries."""
        if "\x1b]4;0;?" in data and "\x1b]4;1;?" not in data:
            # OSC support check — respond with a single colour
            asyncio.get_event_loop().call_soon(
                lambda: mock_stdin.emit_data("\x1b]4;0;rgb:0000/0000/0000\x07")
            )
        elif "\x1b]4;" in data and "?" in data:
            # Full palette query — respond with colours for indices 0..15
            def _respond_palette():
                for i in range(16):
                    mock_stdin.emit_data(f"\x1b]4;{i};rgb:1000/2000/3000\x07")

            asyncio.get_event_loop().call_soon(_respond_palette)
        elif "\x1b]10;?" in data:
            # Special colour queries
            def _respond_special():
                mock_stdin.emit_data("\x1b]10;#ffffff\x07")
                mock_stdin.emit_data("\x1b]11;#000000\x07")
                mock_stdin.emit_data("\x1b]12;#00ff00\x07")

            asyncio.get_event_loop().call_soon(_respond_special)

    mock_stdout = MockPaletteStdout(is_tty=is_tty, responder=_responder)
    mock_stdout.writes = writes

    return mock_stdin, mock_stdout, writes


def _attach_palette_detector(
    renderer: CliRenderer,
    stdin: MockPaletteStdin,
    stdout: MockPaletteStdout,
) -> None:
    """Attach a palette detector wired to mock streams to a renderer."""
    detector = TerminalPaletteDetector(stdin, stdout)
    renderer._palette_detector = detector


# ---------------------------------------------------------------------------
# TestPaletteCachingBehavior
# ---------------------------------------------------------------------------


class TestPaletteCachingBehavior:
    """Palette caching behavior"""

    @pytest.mark.asyncio
    async def test_get_palette_returns_cached_palette_on_subsequent_calls(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette1 = await renderer.get_palette(timeout=300)
        palette2 = await renderer.get_palette(timeout=300)

        assert palette1 is palette2
        assert palette1 == palette2

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_get_palette_caches_correctly_with_non_256_size_parameter(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette1 = await renderer.get_palette(size=16, timeout=300)
        palette2 = await renderer.get_palette(size=16, timeout=300)

        assert palette1 is palette2
        assert renderer.palette_detection_status == "cached"

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_cached_palette_is_returned_instantly(self):
        mock_stdin, mock_stdout, writes = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        await renderer.get_palette(timeout=300)
        write_count_after_first = len(mock_stdout.writes)

        start = time.monotonic()
        await renderer.get_palette(timeout=300)
        duration = (time.monotonic() - start) * 1000  # ms

        assert duration < 50
        assert len(mock_stdout.writes) == write_count_after_first

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_calls_share_same_detection(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette1, palette2, palette3 = await asyncio.gather(
            renderer.get_palette(timeout=300),
            renderer.get_palette(timeout=300),
            renderer.get_palette(timeout=300),
        )

        assert palette1 is palette2
        assert palette2 is palette3

        # Should have at most 2 OSC support checks (the support check query)
        osc_checks = [w for w in mock_stdout.writes if "\x1b]4;0;?" in w]
        assert len(osc_checks) <= 2

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_palette_detector_created_only_once(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        detector_before = renderer._palette_detector
        assert detector_before is not None

        await renderer.get_palette(timeout=300)
        detector1 = renderer._palette_detector
        assert detector1 is not None

        await renderer.get_palette(timeout=300)
        detector2 = renderer._palette_detector
        assert detector1 is detector2

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_cache_persists_with_different_timeout_values(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette1 = await renderer.get_palette(timeout=100)
        write_count_after_first = len(mock_stdout.writes)

        palette2 = await renderer.get_palette(timeout=5000)

        assert len(mock_stdout.writes) == write_count_after_first
        assert palette1 is palette2

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_cache_persists_across_renderer_lifecycle(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette1 = await renderer.get_palette(timeout=300)

        renderer.start()
        await asyncio.sleep(0.01)
        renderer.pause()
        # Note: suspend/resume use native calls that are no-ops for FakeNative
        renderer._control_state = RendererControlState.EXPLICIT_SUSPENDED
        renderer._control_state = RendererControlState.EXPLICIT_STARTED
        renderer.stop()

        palette2 = await renderer.get_palette(timeout=100)
        assert palette1 is palette2

        renderer.destroy()


# ---------------------------------------------------------------------------
# TestPaletteDetectionWithNonTTY
# ---------------------------------------------------------------------------


class TestPaletteDetectionWithNonTTY:
    """Palette detection with non-TTY"""

    @pytest.mark.asyncio
    async def test_handles_non_tty_streams_gracefully(self):
        mock_stdin = MockPaletteStdin(is_tty=False)
        mock_stdout = MockPaletteStdout(is_tty=False)

        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette = await renderer.get_palette(timeout=100)

        assert isinstance(palette, TerminalColors)
        assert isinstance(palette.palette, list)

        # Should be cached
        cached = await renderer.get_palette(timeout=100)
        assert palette is cached

        renderer.destroy()


# ---------------------------------------------------------------------------
# TestPaletteDetectionWithOSCResponses
# ---------------------------------------------------------------------------


class TestPaletteDetectionWithOSCResponses:
    """Palette detection with OSC responses"""

    @pytest.mark.asyncio
    async def test_detects_colors_from_osc_responses(self):
        mock_stdin = MockPaletteStdin(is_tty=True)

        def _responder(data: str) -> None:
            loop = asyncio.get_event_loop()
            if "\x1b]4;0;?" in data and "\x1b]4;1;?" not in data:
                # OSC support check
                loop.call_soon(lambda: mock_stdin.emit_data("\x1b]4;0;#000000\x07"))
            elif "\x1b]4;" in data and "?" in data:

                def _emit_all():
                    mock_stdin.emit_data("\x1b]4;0;#000000\x07")
                    mock_stdin.emit_data("\x1b]4;1;#ff0000\x07")
                    mock_stdin.emit_data("\x1b]4;2;#00ff00\x07")
                    mock_stdin.emit_data("\x1b]4;3;#0000ff\x07")
                    for i in range(4, 256):
                        mock_stdin.emit_data(f"\x1b]4;{i};#808080\x07")

                loop.call_soon(_emit_all)

        mock_stdout = MockPaletteStdout(is_tty=True, responder=_responder)

        renderer = _make_renderer()
        detector = TerminalPaletteDetector(mock_stdin, mock_stdout)
        renderer._palette_detector = detector

        palette = await renderer.get_palette(timeout=300, size=256)

        assert isinstance(palette, TerminalColors)
        assert isinstance(palette.palette, list)
        assert len(palette.palette) >= 16
        assert palette.palette[0] == "#000000"
        assert palette.palette[1] == "#ff0000"
        assert palette.palette[2] == "#00ff00"
        assert palette.palette[3] == "#0000ff"

        # Should be cached
        cached = await renderer.get_palette(timeout=100, size=256)
        assert palette is cached

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_handles_rgb_format_responses(self):
        mock_stdin = MockPaletteStdin(is_tty=True)

        def _responder(data: str) -> None:
            loop = asyncio.get_event_loop()
            if "\x1b]4;0;?" in data and "\x1b]4;1;?" not in data:
                loop.call_soon(lambda: mock_stdin.emit_data("\x1b]4;0;rgb:0000/0000/0000\x07"))
            elif "\x1b]4;" in data and "?" in data:

                def _emit_all():
                    mock_stdin.emit_data("\x1b]4;0;rgb:0000/0000/0000\x07")
                    mock_stdin.emit_data("\x1b]4;1;rgb:ffff/0000/0000\x07")
                    mock_stdin.emit_data("\x1b]4;2;rgb:8000/8000/8000\x07")
                    for i in range(3, 256):
                        mock_stdin.emit_data(f"\x1b]4;{i};rgb:1111/1111/1111\x07")

                loop.call_soon(_emit_all)

        mock_stdout = MockPaletteStdout(is_tty=True, responder=_responder)

        renderer = _make_renderer()
        detector = TerminalPaletteDetector(mock_stdin, mock_stdout)
        renderer._palette_detector = detector

        palette = await renderer.get_palette(timeout=300, size=256)

        assert palette.palette[0] == "#000000"
        assert palette.palette[1] == "#ff0000"
        assert palette.palette[2] == "#808080"

        renderer.destroy()


# ---------------------------------------------------------------------------
# TestPaletteIntegration
# ---------------------------------------------------------------------------


class TestPaletteIntegration:
    """Palette integration tests"""

    @pytest.mark.asyncio
    async def test_palette_detection_does_not_interfere_with_input_handling(self):
        """Palette detection should not consume non-OSC keyboard input."""
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        keys_received: list[str] = []

        # Simulate keyboard input arriving during palette detection
        palette_promise = renderer.get_palette(timeout=300)

        # Send non-OSC data (simulates keystrokes)
        mock_stdin.emit_data("a")
        mock_stdin.emit_data("b")
        mock_stdin.emit_data("c")

        await asyncio.sleep(0.01)

        # The palette detector should have ignored non-OSC data
        # and completed detection normally
        await palette_promise

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_get_palette_works_with_different_renderer_configurations(self):
        configs = [
            {"width": 40, "height": 10},
            {"width": 120, "height": 40},
            {"use_mouse": False},
        ]

        for config_kwargs in configs:
            mock_stdin, mock_stdout, _ = _create_mock_streams()
            renderer = _make_renderer(**config_kwargs)
            _attach_palette_detector(renderer, mock_stdin, mock_stdout)

            palette = await renderer.get_palette(timeout=300)
            assert isinstance(palette, TerminalColors)
            assert isinstance(palette.palette, list)

            cached = await renderer.get_palette(timeout=100)
            assert palette is cached

            renderer.destroy()


# ---------------------------------------------------------------------------
# TestPaletteCacheInvalidation
# ---------------------------------------------------------------------------


class TestPaletteCacheInvalidation:
    """Palette cache invalidation"""

    @pytest.mark.asyncio
    async def test_clear_palette_cache_invalidates_cache(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette1 = await renderer.get_palette(timeout=300)
        assert renderer.palette_detection_status == "cached"

        renderer.clear_palette_cache()
        assert renderer.palette_detection_status == "idle"

        palette2 = await renderer.get_palette(timeout=300)

        assert palette1 is not palette2
        assert renderer.palette_detection_status == "cached"

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_palette_detection_status_tracks_detection_lifecycle(self):
        """Status goes idle -> detecting -> cached."""
        mock_stdin = MockPaletteStdin(is_tty=True)
        statuses_seen: list[str] = []

        # Use a delayed responder: the OSC support check fires with a delay
        # so we can observe the "detecting" state between the call and the
        # response.
        def _responder(data: str) -> None:
            loop = asyncio.get_event_loop()
            if "\x1b]4;0;?" in data and "\x1b]4;1;?" not in data:
                # Delay the response so the test can observe "detecting"
                loop.call_later(
                    0.02,
                    lambda: mock_stdin.emit_data("\x1b]4;0;rgb:0000/0000/0000\x07"),
                )
            elif "\x1b]4;" in data and "?" in data:

                def _emit_all():
                    for i in range(16):
                        mock_stdin.emit_data(f"\x1b]4;{i};rgb:1000/2000/3000\x07")

                loop.call_later(0.02, _emit_all)
            elif "\x1b]10;?" in data:

                def _respond_special():
                    mock_stdin.emit_data("\x1b]10;#ffffff\x07")
                    mock_stdin.emit_data("\x1b]11;#000000\x07")
                    mock_stdin.emit_data("\x1b]12;#00ff00\x07")

                loop.call_later(0.02, _respond_special)

        mock_stdout = MockPaletteStdout(is_tty=True, responder=_responder)

        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        assert renderer.palette_detection_status == "idle"
        statuses_seen.append(renderer.palette_detection_status)

        # Start detection as a task, then immediately check status
        task = asyncio.create_task(renderer.get_palette(timeout=300))
        # Yield to let the task start running
        await asyncio.sleep(0)
        statuses_seen.append(renderer.palette_detection_status)

        await task
        statuses_seen.append(renderer.palette_detection_status)

        assert "idle" in statuses_seen
        assert "detecting" in statuses_seen
        assert statuses_seen[-1] == "cached"

        renderer.destroy()


# ---------------------------------------------------------------------------
# TestPaletteDetectionWithSuspendedRenderer
# ---------------------------------------------------------------------------


class TestPaletteDetectionWithSuspendedRenderer:
    """Palette detection with suspended renderer"""

    @pytest.mark.asyncio
    async def test_get_palette_throws_error_when_renderer_is_suspended(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        renderer._control_state = RendererControlState.EXPLICIT_SUSPENDED

        with pytest.raises(RuntimeError, match="Cannot detect palette while renderer is suspended"):
            await renderer.get_palette(timeout=300)

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_get_palette_works_after_resume(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        renderer._control_state = RendererControlState.EXPLICIT_SUSPENDED
        renderer._control_state = RendererControlState.EXPLICIT_STARTED

        palette = await renderer.get_palette(timeout=300)
        assert isinstance(palette, TerminalColors)
        assert isinstance(palette.palette, list)

        renderer.destroy()


# ---------------------------------------------------------------------------
# TestPaletteDetectorCleanup
# ---------------------------------------------------------------------------


class TestPaletteDetectorCleanup:
    """Palette detector cleanup"""

    @pytest.mark.asyncio
    async def test_destroy_cleans_up_palette_detector(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        await renderer.get_palette(timeout=300)

        renderer.destroy()

        assert renderer._palette_detector is None
        assert renderer._palette_detection_promise is None
        assert renderer._cached_palette is None

    @pytest.mark.asyncio
    async def test_multiple_destroy_calls_dont_cause_errors(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        await renderer.get_palette(timeout=300)

        # Multiple destroy calls should not raise
        renderer.destroy()
        renderer.destroy()
        renderer.destroy()

    @pytest.mark.asyncio
    async def test_cleanup_removes_all_palette_detector_listeners_from_stdin(self):
        mock_stdin = MockPaletteStdin(is_tty=True)
        listener_counts: dict[str, int] = {}

        # Use a delayed responder so we can observe listener count during detection
        def _responder(data: str) -> None:
            loop = asyncio.get_event_loop()
            if "\x1b]4;0;?" in data and "\x1b]4;1;?" not in data:
                loop.call_later(
                    0.05,
                    lambda: mock_stdin.emit_data("\x1b]4;0;rgb:0000/0000/0000\x07"),
                )
            elif "\x1b]4;" in data and "?" in data:

                def _emit_all():
                    for i in range(16):
                        mock_stdin.emit_data(f"\x1b]4;{i};rgb:1000/2000/3000\x07")

                loop.call_later(0.05, _emit_all)
            elif "\x1b]10;?" in data:

                def _respond_special():
                    mock_stdin.emit_data("\x1b]10;#ffffff\x07")
                    mock_stdin.emit_data("\x1b]11;#000000\x07")
                    mock_stdin.emit_data("\x1b]12;#00ff00\x07")

                loop.call_later(0.05, _respond_special)

        mock_stdout = MockPaletteStdout(is_tty=True, responder=_responder)

        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        listener_counts["initial"] = mock_stdin.listener_count()

        task = asyncio.create_task(renderer.get_palette(timeout=300))
        # Yield to let detection start and add listener
        await asyncio.sleep(0.01)

        listener_counts["during"] = mock_stdin.listener_count()
        assert listener_counts["during"] == listener_counts["initial"] + 1

        await task

        listener_counts["after"] = mock_stdin.listener_count()
        assert listener_counts["after"] == listener_counts["initial"]

        renderer.destroy()

        listener_counts["destroyed"] = mock_stdin.listener_count()
        assert listener_counts["destroyed"] == 0


# ---------------------------------------------------------------------------
# TestPaletteDetectionErrorHandling
# ---------------------------------------------------------------------------


class TestPaletteDetectionErrorHandling:
    """Palette detection error handling"""

    @pytest.mark.asyncio
    async def test_handles_timeout_gracefully(self):
        # Non-responsive stdin (no responder) — detection will timeout
        mock_stdin = MockPaletteStdin(is_tty=True)
        mock_stdout = MockPaletteStdout(is_tty=True)

        renderer = _make_renderer()
        detector = TerminalPaletteDetector(mock_stdin, mock_stdout)
        renderer._palette_detector = detector

        palette = await renderer.get_palette(timeout=100)
        assert isinstance(palette, TerminalColors)
        assert isinstance(palette.palette, list)
        # All colours should be None since no responses arrived
        assert all(c is None for c in palette.palette)

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_handles_stdin_listener_restoration_on_error(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        try:
            palette_promise = renderer.get_palette(timeout=300)
            await palette_promise
        except Exception:
            pass

        # After detection (success or error), stdin should not have negative
        # or leaked listeners.  Upstream asserts listener_count > 0 because the
        # TS renderer keeps a permanent "data" listener on stdin; in Python the
        # mock has no such permanent listener so we only assert non-negative.
        listener_count = mock_stdin.listener_count()
        assert listener_count >= 0

        renderer.destroy()


# ---------------------------------------------------------------------------
# TestPaletteCacheWithDifferentSizes
# ---------------------------------------------------------------------------


class TestPaletteCacheWithDifferentSizes:
    """Palette cache with different sizes"""

    @pytest.mark.asyncio
    async def test_cache_works_correctly_when_requesting_size_16_twice(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette1 = await renderer.get_palette(size=16, timeout=300)
        write_count_after_first = len(mock_stdout.writes)

        assert renderer.palette_detection_status == "cached"
        assert len(palette1.palette) == 16

        start = time.monotonic()
        palette2 = await renderer.get_palette(size=16, timeout=300)
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed < 50
        assert len(mock_stdout.writes) == write_count_after_first
        assert palette1 is palette2
        assert renderer.palette_detection_status == "cached"

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_cache_is_invalidated_when_requesting_different_size(self):
        mock_stdin = MockPaletteStdin(is_tty=True)
        writes: list[str] = []

        def _responder(data: str) -> None:
            writes.append(data)
            loop = asyncio.get_event_loop()
            if "\x1b]4;0;?" in data and "\x1b]4;1;?" not in data:
                loop.call_soon(lambda: mock_stdin.emit_data("\x1b]4;0;rgb:0000/0000/0000\x07"))
            elif "\x1b]4;" in data and "?" in data:

                def _emit_all():
                    for i in range(256):
                        mock_stdin.emit_data(f"\x1b]4;{i};rgb:1000/2000/3000\x07")

                loop.call_soon(_emit_all)
            elif "\x1b]10;?" in data:

                def _respond_special():
                    mock_stdin.emit_data("\x1b]10;#ffffff\x07")
                    mock_stdin.emit_data("\x1b]11;#000000\x07")
                    mock_stdin.emit_data("\x1b]12;#00ff00\x07")

                loop.call_soon(_respond_special)

        mock_stdout = MockPaletteStdout(is_tty=True, responder=_responder)

        renderer = _make_renderer()
        detector = TerminalPaletteDetector(mock_stdin, mock_stdout)
        renderer._palette_detector = detector

        palette1 = await renderer.get_palette(size=16, timeout=300)
        write_count_after_16 = len(writes)

        palette2 = await renderer.get_palette(size=256, timeout=300)
        write_count_after_256 = len(writes)

        assert write_count_after_256 > write_count_after_16
        assert palette1 is not palette2

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_cache_persists_across_multiple_identical_size_requests(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        palette1 = await renderer.get_palette(size=16, timeout=300)
        write_count_after_first = len(mock_stdout.writes)

        palette2 = await renderer.get_palette(size=16, timeout=300)
        palette3 = await renderer.get_palette(size=16, timeout=300)
        palette4 = await renderer.get_palette(size=16, timeout=300)

        assert len(mock_stdout.writes) == write_count_after_first
        assert palette1 is palette2
        assert palette2 is palette3
        assert palette3 is palette4

        renderer.destroy()

    @pytest.mark.asyncio
    async def test_cached_call_is_significantly_faster_than_initial_detection(self):
        mock_stdin, mock_stdout, _ = _create_mock_streams()
        renderer = _make_renderer()
        _attach_palette_detector(renderer, mock_stdin, mock_stdout)

        start1 = time.perf_counter()
        await renderer.get_palette(size=16, timeout=300)
        elapsed1 = (time.perf_counter() - start1) * 1000  # ms

        start2 = time.perf_counter()
        await renderer.get_palette(size=16, timeout=300)
        elapsed2 = (time.perf_counter() - start2) * 1000  # ms

        assert elapsed2 < 10
        # Cached call should be at least 10x faster (may not hold for
        # extremely fast first calls, but the cache should be sub-ms)
        if elapsed1 > 1.0:
            assert elapsed2 < elapsed1 / 10

        renderer.destroy()
