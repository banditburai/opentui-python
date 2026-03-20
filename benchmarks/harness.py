"""Shared benchmark harness for OpenTUI Python.

Consolidates duplicated infrastructure across bench_*.py files:
  - BenchResult dataclass with from_samples() classmethod
  - ResultRegistry for collecting results during a run
  - bench() / bench_frame_buckets() / collect_frame_medians() runners
  - Baseline save/load/compare with colored terminal output
"""

from __future__ import annotations

import gc
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# All 16 frame timing bucket names from renderer.py FrameTimingBuckets
FRAME_BUCKETS = (
    "signal_handling_ns",
    "layout_ns",
    "configure_yoga_ns",
    "compute_yoga_ns",
    "apply_layout_ns",
    "update_layout_hooks_ns",
    "mount_callbacks_ns",
    "buffer_prepare_ns",
    "buffer_lookup_ns",
    "repaint_plan_ns",
    "buffer_replay_ns",
    "render_tree_ns",
    "flush_ns",
    "post_render_ns",
    "frame_finish_ns",
    "total_ns",
)

_BASELINES_DIR = Path(__file__).parent / "baselines"


@dataclass(slots=True)
class BenchResult:
    label: str
    min_ns: int
    median_ns: int
    p95_ns: int
    p99_ns: int
    mean_ns: int
    stdev_ns: int
    iterations: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_samples(cls, samples: list[int], *, label: str) -> BenchResult:
        samples.sort()
        n = len(samples)
        return cls(
            label=label,
            min_ns=samples[0],
            median_ns=samples[n // 2],
            p95_ns=samples[int(n * 0.95)],
            p99_ns=samples[int(n * 0.99)],
            mean_ns=int(statistics.mean(samples)),
            stdev_ns=int(statistics.stdev(samples)) if n > 1 else 0,
            iterations=n,
        )


class ResultRegistry:
    """Collects BenchResults by label during a run."""

    def __init__(self) -> None:
        self._results: dict[str, BenchResult] = {}

    def record(self, samples: list[int], *, label: str) -> BenchResult:
        result = BenchResult.from_samples(samples, label=label)
        self._results[label] = result
        return result

    def all(self) -> dict[str, BenchResult]:
        return dict(self._results)

    def to_json_dict(self) -> dict[str, dict[str, Any]]:
        return {label: r.to_dict() for label, r in self._results.items()}

    def clear(self) -> None:
        self._results.clear()


# Module-level default registry
registry = ResultRegistry()


def bench(
    fn,
    *,
    warmup: int = 50,
    iterations: int = 1000,
    label: str = "",
) -> BenchResult:
    """Run fn iterations times with GC disabled, return BenchResult."""
    for _ in range(warmup):
        fn()

    gc.disable()
    try:
        samples = []
        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            fn()
            t1 = time.perf_counter_ns()
            samples.append(t1 - t0)
    finally:
        gc.enable()

    return registry.record(samples, label=label)


def bench_frame_buckets(
    setup,
    mutate,
    *,
    warmup: int = 20,
    iterations: int = 200,
    label_prefix: str,
    buckets: tuple[str, ...] | None = None,
) -> dict[str, BenchResult]:
    """Benchmark frame timing buckets. Does NOT call setup.destroy() — caller manages lifecycle."""
    if buckets is None:
        buckets = FRAME_BUCKETS
    samples = {name: [] for name in buckets}

    for _ in range(warmup):
        mutate()
        setup.render_frame()

    gc.disable()
    try:
        for _ in range(iterations):
            mutate()
            setup.render_frame()
            timings = setup.renderer.last_frame_timings
            for name in buckets:
                samples[name].append(getattr(timings, name))
    finally:
        gc.enable()

    return {
        name: registry.record(
            samples[name], label=f"{label_prefix}: {name.removesuffix('_ns')}"
        )
        for name in buckets
    }


def collect_frame_medians(
    setup,
    mutate,
    iterations: int,
    *,
    buckets: tuple[str, ...] | None = None,
    label_prefix: str = "",
) -> dict[str, int]:
    """Lightweight median-only frame collection. Records full stats in registry if label_prefix given."""
    if buckets is None:
        buckets = FRAME_BUCKETS
    # One warmup frame
    setup.render_frame()
    samples = {name: [] for name in buckets}
    for _ in range(iterations):
        if mutate is not None:
            mutate()
        setup.render_frame()
        timings = setup.renderer.last_frame_timings
        for name in buckets:
            samples[name].append(getattr(timings, name))

    medians = {}
    for name in buckets:
        vals = sorted(samples[name])
        medians[name] = vals[len(vals) // 2]
        if label_prefix:
            registry.record(
                samples[name],
                label=f"{label_prefix}: {name.removesuffix('_ns')}",
            )
    return medians


def format_result(result: BenchResult | dict[str, Any]) -> str:
    """Format a benchmark result as a human-readable one-liner."""
    if isinstance(result, BenchResult):
        r = result.to_dict()
    else:
        r = result
    return (
        f"  {r['label']:<55s}  "
        f"median={r['median_ns']:>10,}ns  "
        f"p95={r['p95_ns']:>10,}ns  "
        f"mean={r['mean_ns']:>10,}ns"
    )


# ── Baseline I/O ─────────────────────────────────────────────────────


def save_baseline(results: dict[str, dict[str, Any]], name: str = "baseline") -> Path:
    _BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    path = _BASELINES_DIR / f"{name}.json"
    path.write_text(json.dumps(results, indent=2) + "\n")
    return path


def load_baseline(name: str = "baseline") -> dict[str, dict[str, Any]] | None:
    path = _BASELINES_DIR / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


# ── Comparison ───────────────────────────────────────────────────────

_REGRESSION_THRESHOLD = 0.10  # 10%
_IMPROVEMENT_THRESHOLD = -0.10


def compare_results(
    current: dict[str, dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
    metric: str = "median_ns",
) -> list[dict[str, Any]]:
    """Compare current results against baseline, return sorted list of comparisons."""
    comparisons = []
    for label in sorted(set(current) | set(baseline)):
        cur = current.get(label)
        base = baseline.get(label)
        if cur is None or base is None:
            continue
        cur_val = cur[metric]
        base_val = base[metric]
        if base_val == 0:
            continue
        change_pct = (cur_val - base_val) / base_val
        if change_pct > _REGRESSION_THRESHOLD:
            status = "regression"
        elif change_pct < _IMPROVEMENT_THRESHOLD:
            status = "improvement"
        else:
            status = "unchanged"
        comparisons.append({
            "label": label,
            "current": cur_val,
            "baseline": base_val,
            "change_pct": change_pct,
            "status": status,
        })
    # Regressions first, then improvements, then unchanged
    order = {"regression": 0, "improvement": 1, "unchanged": 2}
    comparisons.sort(key=lambda c: (order[c["status"]], -abs(c["change_pct"])))
    return comparisons


def print_comparison(comparisons: list[dict[str, Any]]) -> None:
    """Print colored comparison table to terminal."""
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    RED = "\033[91m" if is_tty else ""
    GREEN = "\033[92m" if is_tty else ""
    DIM = "\033[2m" if is_tty else ""
    RESET = "\033[0m" if is_tty else ""

    regressions = [c for c in comparisons if c["status"] == "regression"]
    improvements = [c for c in comparisons if c["status"] == "improvement"]
    unchanged = [c for c in comparisons if c["status"] == "unchanged"]

    def _print_row(c: dict[str, Any], color: str) -> None:
        sign = "+" if c["change_pct"] > 0 else ""
        print(
            f"  {color}{c['label']:<55s}  "
            f"now={c['current']:>10,}ns  "
            f"was={c['baseline']:>10,}ns  "
            f"{sign}{c['change_pct']:>+7.1%}{RESET}"
        )

    if regressions:
        print(f"\n{RED}REGRESSIONS (>{_REGRESSION_THRESHOLD:.0%}):{RESET}")
        for c in regressions:
            _print_row(c, RED)

    if improvements:
        print(f"\n{GREEN}IMPROVEMENTS (<{_IMPROVEMENT_THRESHOLD:.0%}):{RESET}")
        for c in improvements:
            _print_row(c, GREEN)

    if unchanged:
        print(f"\n{DIM}UNCHANGED:{RESET}")
        for c in unchanged:
            _print_row(c, DIM)

    total = len(comparisons)
    print(
        f"\n  {len(regressions)} regressions, "
        f"{len(improvements)} improvements, "
        f"{len(unchanged)} unchanged "
        f"(of {total} benchmarks)"
    )
