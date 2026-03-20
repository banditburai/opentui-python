"""Unified benchmark entry point for OpenTUI Python.

Usage:
  python benchmarks/run_all.py              # run all, print results
  python benchmarks/run_all.py --save       # run all, save as baselines/baseline.json
  python benchmarks/run_all.py --save NAME  # run all, save as baselines/NAME.json
  python benchmarks/run_all.py --compare    # run all, compare to baseline.json
  python benchmarks/run_all.py --compare NAME
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when running as script
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from benchmarks.harness import compare_results, load_baseline, print_comparison, registry, save_baseline
except ImportError:
    from harness import compare_results, load_baseline, print_comparison, registry, save_baseline


def _run_reactivity() -> None:
    print("\n" + "=" * 95)
    print("  Reactivity Benchmarks")
    print("=" * 95)
    from benchmarks.bench_reactivity import main as reactivity_main
    reactivity_main()


def _run_render_matrix() -> None:
    print("\n" + "=" * 95)
    print("  Render Matrix Benchmarks")
    print("=" * 95)
    from benchmarks.bench_render_matrix import _run
    asyncio.run(_run())


def _run_layout_pipeline() -> None:
    print("\n" + "=" * 95)
    print("  Layout Pipeline Benchmarks")
    print("=" * 95)
    from benchmarks.bench_layout_pipeline import _run
    asyncio.run(_run())


def _run_yoga_layout_shapes() -> None:
    print("\n" + "=" * 95)
    print("  Yoga Layout Shape Benchmarks")
    print("=" * 95)
    from benchmarks.bench_yoga_layout_shapes import _run
    asyncio.run(_run())


def _run_text_render() -> None:
    print("\n" + "=" * 95)
    print("  Text Render Benchmarks")
    print("=" * 95)
    from benchmarks.bench_text_render import _run
    asyncio.run(_run())


_SUITES = [
    ("reactivity", _run_reactivity),
    ("render_matrix", _run_render_matrix),
    ("layout_pipeline", _run_layout_pipeline),
    ("yoga_layout_shapes", _run_yoga_layout_shapes),
    ("text_render", _run_text_render),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenTUI benchmark runner")
    parser.add_argument(
        "--save", nargs="?", const="baseline", default=None, metavar="NAME",
        help="Save results as a baseline (default name: 'baseline')",
    )
    parser.add_argument(
        "--compare", nargs="?", const="baseline", default=None, metavar="NAME",
        help="Compare results against a saved baseline",
    )
    parser.add_argument(
        "--suite", nargs="*", default=None, metavar="NAME",
        help=f"Run only specific suites. Available: {', '.join(n for n, _ in _SUITES)}",
    )
    args = parser.parse_args()

    registry.clear()

    print(f"OpenTUI benchmark suite — {time.strftime('%Y-%m-%d %H:%M:%S')}")

    suites = _SUITES
    if args.suite:
        suite_names = set(args.suite)
        suites = [(n, fn) for n, fn in _SUITES if n in suite_names]
        unknown = suite_names - {n for n, _ in _SUITES}
        if unknown:
            print(f"Unknown suites: {', '.join(sorted(unknown))}", file=sys.stderr)
            sys.exit(1)

    for _name, run_fn in suites:
        run_fn()

    current = registry.to_json_dict()
    print(f"\n{'=' * 95}")
    print(f"  Total: {len(current)} benchmarks recorded")
    print(f"{'=' * 95}")

    if args.save is not None:
        path = save_baseline(current, args.save)
        print(f"\nBaseline saved to {path} ({len(current)} benchmarks)")

    if args.compare is not None:
        baseline = load_baseline(args.compare)
        if baseline is None:
            print(
                f"\nNo baseline found for '{args.compare}'. "
                f"Run with --save first.",
                file=sys.stderr,
            )
            sys.exit(1)
        comparisons = compare_results(current, baseline)
        print(f"\n{'=' * 95}")
        print(f"  COMPARISON vs '{args.compare}' baseline")
        print(f"{'=' * 95}")
        print_comparison(comparisons)


if __name__ == "__main__":
    main()
