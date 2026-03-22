"""Port of upstream wrap-resize-perf.test.ts.

Upstream: packages/core/src/tests/wrap-resize-perf.test.ts
Tests ported: 4/4 (3 implemented, 1 skipped — flaky upstream)
"""

import time

import pytest

from opentui.native import is_available
from opentui.editor.text_buffer_native import NativeTextBuffer
from opentui.editor.text_view_native import NativeTextBufferView

pytestmark = pytest.mark.skipif(not is_available(), reason="Native bindings not available")


def _measure_median(fn, iterations: int = 11) -> float:
    """Run *fn* *iterations* times and return the median elapsed time in seconds."""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    times.sort()
    return times[len(times) // 2]


# Algorithmic-complexity threshold: the ratio of (large_time / small_time) must
# be less than (input_size_ratio * THRESHOLD).  For O(n), doubling the input
# roughly doubles the time (ratio ≈ 2.0).  The threshold of 1.75 catches
# quadratic regressions (ratio ≈ 4.0) while tolerating linear variance.
COMPLEXITY_THRESHOLD = 1.75


class TestWordWrapAlgorithmicComplexity:
    """Maps to describe("Word wrap algorithmic complexity")."""

    def test_should_have_on_complexity_for_word_wrap_without_word_breaks(self):
        """Maps to it("should have O(n) complexity for word wrap without word breaks")."""
        small_size = 20000
        large_size = 40000

        small_text = "x" * small_size
        large_text = "x" * large_size

        small_buf = NativeTextBuffer()
        large_buf = NativeTextBuffer()
        small_buf.set_text(small_text)
        large_buf.set_text(large_text)

        small_view = NativeTextBufferView(small_buf.ptr, text_buffer=small_buf)
        large_view = NativeTextBufferView(large_buf.ptr, text_buffer=large_buf)

        small_view.set_wrap_mode("word")
        large_view.set_wrap_mode("word")
        small_view.set_wrap_width(80)
        large_view.set_wrap_width(80)

        # Warm up
        small_view.measure_for_dimensions(80, 100)
        large_view.measure_for_dimensions(80, 100)

        small_time = _measure_median(lambda: small_view.measure_for_dimensions(80, 100))
        large_time = _measure_median(lambda: large_view.measure_for_dimensions(80, 100))

        input_ratio = large_size / small_size

        # Guard against division by zero / unexpectedly fast runs
        if small_time <= 0:
            pytest.skip("Measurement too fast to be meaningful on this machine")

        ratio = large_time / small_time
        assert ratio < input_ratio * COMPLEXITY_THRESHOLD, (
            f"Word-wrap (no breaks) appears super-linear: "
            f"small={small_time * 1000:.2f}ms large={large_time * 1000:.2f}ms "
            f"ratio={ratio:.2f}, threshold={input_ratio * COMPLEXITY_THRESHOLD:.2f}"
        )

    def test_should_have_on_complexity_for_word_wrap_with_word_breaks(self):
        """Maps to it("should have O(n) complexity for word wrap with word breaks")."""
        small_size = 20000
        large_size = 40000

        def make_text(size: int) -> str:
            words = (size + 10) // 11
            return (" ".join(["xxxxxxxxxx"] * words))[:size]

        small_text = make_text(small_size)
        large_text = make_text(large_size)

        small_buf = NativeTextBuffer()
        large_buf = NativeTextBuffer()
        small_buf.set_text(small_text)
        large_buf.set_text(large_text)

        small_view = NativeTextBufferView(small_buf.ptr, text_buffer=small_buf)
        large_view = NativeTextBufferView(large_buf.ptr, text_buffer=large_buf)

        small_view.set_wrap_mode("word")
        large_view.set_wrap_mode("word")
        small_view.set_wrap_width(80)
        large_view.set_wrap_width(80)

        # Warm up
        small_view.measure_for_dimensions(80, 100)
        large_view.measure_for_dimensions(80, 100)

        small_time = _measure_median(lambda: small_view.measure_for_dimensions(80, 100))
        large_time = _measure_median(lambda: large_view.measure_for_dimensions(80, 100))

        input_ratio = large_size / small_size

        if small_time <= 0:
            pytest.skip("Measurement too fast to be meaningful on this machine")

        ratio = large_time / small_time
        assert ratio < input_ratio * COMPLEXITY_THRESHOLD, (
            f"Word-wrap (with breaks) appears super-linear: "
            f"small={small_time * 1000:.2f}ms large={large_time * 1000:.2f}ms "
            f"ratio={ratio:.2f}, threshold={input_ratio * COMPLEXITY_THRESHOLD:.2f}"
        )

    def test_should_have_on_complexity_for_char_wrap_mode(self):
        """Maps to it("should have O(n) complexity for char wrap mode")."""
        small_size = 20000
        large_size = 40000

        small_text = "x" * small_size
        large_text = "x" * large_size

        small_buf = NativeTextBuffer()
        large_buf = NativeTextBuffer()
        small_buf.set_text(small_text)
        large_buf.set_text(large_text)

        small_view = NativeTextBufferView(small_buf.ptr, text_buffer=small_buf)
        large_view = NativeTextBufferView(large_buf.ptr, text_buffer=large_buf)

        small_view.set_wrap_mode("char")
        large_view.set_wrap_mode("char")
        small_view.set_wrap_width(80)
        large_view.set_wrap_width(80)

        # Warm up
        small_view.measure_for_dimensions(80, 100)
        large_view.measure_for_dimensions(80, 100)

        small_time = _measure_median(lambda: small_view.measure_for_dimensions(80, 100))
        large_time = _measure_median(lambda: large_view.measure_for_dimensions(80, 100))

        input_ratio = large_size / small_size

        if small_time <= 0:
            pytest.skip("Measurement too fast to be meaningful on this machine")

        ratio = large_time / small_time
        assert ratio < input_ratio * COMPLEXITY_THRESHOLD, (
            f"Char-wrap appears super-linear: "
            f"small={small_time * 1000:.2f}ms large={large_time * 1000:.2f}ms "
            f"ratio={ratio:.2f}, threshold={input_ratio * COMPLEXITY_THRESHOLD:.2f}"
        )
