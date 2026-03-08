"""Tests for AsyncBridge thread-safe async↔sync communication."""

import asyncio
import time

import pytest

from opencode.tui.bridge import AsyncBridge


class TestAsyncBridge:
    def test_schedule_and_drain(self):
        bridge = AsyncBridge()
        results = []
        bridge.schedule_update(lambda: results.append(1))
        bridge.schedule_update(lambda: results.append(2))
        count = bridge.drain_updates()
        assert results == [1, 2]
        assert count == 2

    def test_drain_empty(self):
        bridge = AsyncBridge()
        assert bridge.drain_updates() == 0

    def test_start_and_stop(self):
        bridge = AsyncBridge()
        bridge.start()
        assert bridge._loop is not None
        assert bridge._thread is not None
        assert bridge._thread.is_alive()
        bridge.stop()
        assert bridge._loop is None

    def test_submit_coroutine(self):
        bridge = AsyncBridge()
        bridge.start()

        async def add(a, b):
            return a + b

        try:
            future = bridge.submit(add(2, 3))
            result = future.result(timeout=2)
            assert result == 5
        finally:
            bridge.stop()

    def test_submit_raises_when_not_started(self):
        bridge = AsyncBridge()
        async def noop():
            pass
        with pytest.raises(RuntimeError, match="not started"):
            bridge.submit(noop())

    def test_schedule_update_from_async(self):
        bridge = AsyncBridge()
        bridge.start()
        results = []

        async def work():
            bridge.schedule_update(lambda: results.append("from_async"))

        try:
            future = bridge.submit(work())
            future.result(timeout=2)
            bridge.drain_updates()
            assert results == ["from_async"]
        finally:
            bridge.stop()

    def test_drain_handles_errors(self):
        """Errors in one update don't prevent subsequent updates from running."""
        bridge = AsyncBridge()
        results = []

        def bad():
            raise ValueError("boom")

        bridge.schedule_update(bad)
        bridge.schedule_update(lambda: results.append("ok"))
        bridge.drain_updates()
        assert results == ["ok"]

    def test_start_idempotent(self):
        bridge = AsyncBridge()
        bridge.start()
        thread1 = bridge._thread
        bridge.start()  # Should be no-op
        assert bridge._thread is thread1
        bridge.stop()

    def test_stop_idempotent(self):
        bridge = AsyncBridge()
        bridge.stop()  # Should not raise
        bridge.start()
        bridge.stop()
        bridge.stop()  # Should not raise

    def test_frame_callback_drains(self):
        bridge = AsyncBridge()
        results = []
        bridge.schedule_update(lambda: results.append("drained"))
        bridge._drain_frame(0.016)
        assert results == ["drained"]

    def test_concurrent_schedule_and_drain(self):
        """10 threads scheduling 100 updates each → 1000 total drained."""
        import threading

        bridge = AsyncBridge()
        counter = {"n": 0}
        lock = threading.Lock()

        def schedule_batch():
            for _ in range(100):
                def inc():
                    with lock:
                        counter["n"] += 1
                bridge.schedule_update(inc)

        threads = [threading.Thread(target=schedule_batch) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total = bridge.drain_updates()
        assert total == 1000
        assert counter["n"] == 1000
