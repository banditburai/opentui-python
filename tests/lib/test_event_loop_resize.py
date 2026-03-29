"""Tests for EventLoop resize polling fallback (non-SIGWINCH platforms)."""

import os
import signal
import shutil
from unittest.mock import patch

import pytest


class TestResizePollingFallback:
    """Verify that EventLoop polls terminal size when SIGWINCH is unavailable."""

    def test_resize_handler_called_on_size_change(self):
        """When SIGWINCH is missing, EventLoop detects size changes via polling."""
        from opentui.input.event_loop import EventLoop

        loop = EventLoop(target_fps=60.0)

        resize_called = []

        def track_resize():
            resize_called.append(True)

        loop._handle_resize = track_resize

        # Simulate: no SIGWINCH, terminal size changes between frames
        sizes = [
            os.terminal_size((80, 24)),
            os.terminal_size((120, 40)),
            os.terminal_size((120, 40)),
        ]
        frame_count = [0]

        def fake_get_terminal_size(*args, **kwargs):
            return sizes[min(frame_count[0], len(sizes) - 1)]

        def fake_poll():
            frame_count[0] += 1
            if frame_count[0] >= 3:
                loop._running = False
            return False

        # Remove SIGWINCH from signal module temporarily to simulate Windows
        orig_sigwinch = getattr(signal, "SIGWINCH", None)
        try:
            if hasattr(signal, "SIGWINCH"):
                delattr(signal, "SIGWINCH")

            with (
                patch.object(shutil, "get_terminal_size", side_effect=fake_get_terminal_size),
                patch.object(loop._input_handler, "start"),
                patch.object(loop._input_handler, "stop"),
                patch.object(loop._input_handler, "poll", side_effect=fake_poll),
            ):
                loop.run()
        finally:
            # Restore SIGWINCH
            if orig_sigwinch is not None:
                signal.SIGWINCH = orig_sigwinch

        # Resize should have been called when size changed from 80x24 to 120x40
        assert len(resize_called) >= 1
