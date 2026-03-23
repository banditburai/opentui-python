"""Scroll acceleration strategies for ScrollBox."""

from __future__ import annotations

import math
import time
from collections import deque


class LinearScrollAccel:
    def tick(self, _now_ms: float | None = None) -> float:
        return 1.0

    def reset(self) -> None:
        return None


class MacOSScrollAccel:
    """macOS-inspired scroll acceleration."""

    _HISTORY_SIZE = 3
    _STREAK_TIMEOUT = 150
    _MIN_TICK_INTERVAL = 6
    _REFERENCE_INTERVAL = 100

    def __init__(self, *, amplitude: float = 0.8, tau: float = 3.0, max_multiplier: float = 6.0):
        self._amplitude = amplitude
        self._tau = tau
        self._max_multiplier = max_multiplier
        self._last_tick_ms = 0.0
        self._history: deque[float] = deque(maxlen=self._HISTORY_SIZE)

    def tick(self, now_ms: float | None = None) -> float:
        if now_ms is None:
            now_ms = time.monotonic() * 1000.0

        dt = (now_ms - self._last_tick_ms) if self._last_tick_ms else float("inf")
        if dt == float("inf") or dt > self._STREAK_TIMEOUT:
            self._last_tick_ms = now_ms
            self._history.clear()
            return 1.0

        if dt < self._MIN_TICK_INTERVAL:
            return 1.0

        self._last_tick_ms = now_ms
        self._history.append(dt)

        avg_interval = sum(self._history) / len(self._history)
        velocity = self._REFERENCE_INTERVAL / avg_interval
        x = velocity / self._tau
        multiplier = 1.0 + self._amplitude * (math.exp(x) - 1.0)
        return min(multiplier, self._max_multiplier)

    def reset(self) -> None:
        self._last_tick_ms = 0.0
        self._history.clear()


__all__ = ["LinearScrollAccel", "MacOSScrollAccel"]
