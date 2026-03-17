#!/usr/bin/env python3
"""Verify test parity between upstream TypeScript and Python test files.

Parses TEST_PARITY.md to find all PORT entries, counts test cases in both
TS and Python files, detects faked tests, and produces a summary report.

Usage:
    python tests/verify_parity.py              # Full report
    python tests/verify_parity.py --file rgba  # Filter by name substring
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF_CORE = ROOT / "reference" / "opentui" / "packages" / "core" / "src"
REF_SOLID = ROOT / "reference" / "opentui" / "packages" / "solid" / "tests"
TESTS = ROOT / "tests"

# --- TS test counting ---

# Match test( or it( at word boundary, not inside comments
_TS_TEST_RE = re.compile(r"""\b(?:test|it)\s*\(\s*["'`]""")
_TS_TEST_EACH_RE = re.compile(r"""\b(?:test|it)\s*\.\s*each\s*\(\s*\[""")
_TS_LINE_COMMENT = re.compile(r"//.*$", re.MULTILINE)
_TS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_TS_TEMPLATE_LITERAL = re.compile(r"`[^`]*`", re.DOTALL)


def _strip_ts_comments(src: str) -> str:
    src = _TS_BLOCK_COMMENT.sub("", src)
    src = _TS_LINE_COMMENT.sub("", src)
    src = _TS_TEMPLATE_LITERAL.sub('""', src)
    return src


def _count_ts_each_entries(src: str, pos: int) -> int:
    """Count array entries in test.each([...])."""
    depth = 0
    count = 0
    i = pos
    in_array = False
    while i < len(src):
        ch = src[i]
        if ch == "[" and not in_array:
            in_array = True
            depth = 1
            count = 1  # first entry
            i += 1
            continue
        if in_array:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
            elif ch == "," and depth == 1:
                count += 1
        i += 1
    return max(count, 1)


def count_ts_tests(filepath: Path) -> int:
    """Count test/it calls in a TypeScript test file."""
    if not filepath.exists():
        return -1
    src = filepath.read_text()
    src = _strip_ts_comments(src)

    count = 0
    # Handle test.each / it.each
    for m in _TS_TEST_EACH_RE.finditer(src):
        n = _count_ts_each_entries(src, m.end() - 1)
        count += n

    # Handle regular test() / it() — exclude those that are test.each
    each_positions = {m.start() for m in _TS_TEST_EACH_RE.finditer(src)}
    for m in _TS_TEST_RE.finditer(src):
        # Skip if this is part of a test.each
        if any(m.start() >= ep and m.start() < ep + 20 for ep in each_positions):
            continue
        # Skip if preceded by describe (describe.each etc)
        before = src[max(0, m.start() - 20) : m.start()].strip()
        if before.endswith("describe"):
            continue
        count += 1

    return count


# --- Python test counting ---

_PY_TEST_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)", re.MULTILINE)


def count_py_tests(filepath: Path) -> tuple[int, list[str]]:
    """Count test functions in a Python test file. Returns (count, names)."""
    if not filepath.exists():
        return -1, []
    src = filepath.read_text()
    names = []
    for m in _PY_TEST_RE.finditer(src):
        name = m.group(1)
        if name == "test_placeholder":
            continue
        names.append(name)
    return len(names), names


# --- Fake detection ---

_FAKE_PATTERNS = [
    re.compile(r"^\s*pass\s*$"),
    re.compile(r"^\s*assert\s+True\s*$"),
    re.compile(r'^\s*assert\s+True\s*,\s*["\']'),
]


def _extract_test_body(src: str, test_start: int) -> str:
    """Extract the body of a test function starting at test_start."""
    lines = src[test_start:].split("\n")
    if not lines:
        return ""
    # Find the actual def line (m.start() may point before leading whitespace)
    def_line_idx = 0
    for i, line in enumerate(lines):
        if re.match(r"\s*(?:async\s+)?def\s+test_", line):
            def_line_idx = i
            break
    def_line = lines[def_line_idx]
    def_indent = len(def_line) - len(def_line.lstrip())
    body_lines = []
    for line in lines[def_line_idx + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        line_indent = len(line) - len(line.lstrip())
        if line_indent <= def_indent and stripped:
            break
        body_lines.append(stripped)
    return "\n".join(body_lines)


def detect_faked_tests(filepath: Path) -> list[str]:
    """Return names of tests that appear to be faked."""
    if not filepath.exists():
        return []
    src = filepath.read_text()
    faked = []
    for m in _PY_TEST_RE.finditer(src):
        name = m.group(1)
        if name == "test_placeholder":
            continue
        body = _extract_test_body(src, m.start())
        # Strip decorators, docstrings, comments
        meaningful = []
        in_docstring = False
        for line in body.split("\n"):
            if in_docstring:
                # Check if this line ends the docstring
                if '"""' in line or "'''" in line:
                    in_docstring = False
                continue
            if line.startswith('"""') or line.startswith("'''"):
                # Single-line docstring
                if line.count('"""') >= 2 or line.count("'''") >= 2:
                    continue
                in_docstring = True
                continue
            if line.startswith("#"):
                continue
            if line.startswith("@"):
                continue
            meaningful.append(line)

        meaningful_text = "\n".join(meaningful).strip()
        if not meaningful_text:
            faked.append(name)
            continue

        # Check for pass-only or assert True-only
        all_trivial = True
        for line in meaningful:
            stripped = line.strip()
            if not stripped:
                continue
            is_trivial = False
            for pat in _FAKE_PATTERNS:
                if pat.match(stripped):
                    is_trivial = True
                    break
            if not is_trivial:
                all_trivial = False
                break
        if all_trivial:
            # But allow pytest.fail inside a skip — that's the correct pattern
            if "pytest.fail" in body:
                continue
            faked.append(name)

    return faked


# --- Parse TEST_PARITY.md ---


@dataclass
class PortEntry:
    ts_file: str  # e.g. "lib/RGBA.test.ts"
    py_file: str  # e.g. "tests/lib/test_rgba.py"
    status_text: str


def parse_parity_md() -> list[PortEntry]:
    """Parse TEST_PARITY.md for PORT entries."""
    md_path = ROOT / "TEST_PARITY.md"
    src = md_path.read_text()
    entries = []
    # Match table rows: | upstream | python | module | status |
    row_re = re.compile(r"\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|[^|]*\|\s*(.*?)\s*\|")
    for m in row_re.finditer(src):
        ts_name = m.group(1).strip()
        py_name = m.group(2).strip()
        status = m.group(3).strip()
        if "**PORT**" in status or "**DONE**" in status:
            entries.append(PortEntry(ts_name, py_name, status))
    return entries


def resolve_ts_path(ts_file: str) -> Path:
    """Resolve an upstream TS test filename to its full path."""
    # Root level files
    if "/" not in ts_file:
        return REF_CORE / ts_file

    prefix = ts_file.split("/", maxsplit=1)[0]
    rest = "/".join(ts_file.split("/")[1:])

    if prefix == "solid":
        return REF_SOLID / rest

    if prefix == "tests":
        return REF_CORE / "tests" / rest

    if prefix == "testing":
        return REF_CORE / "testing" / rest

    if prefix == "lib":
        return REF_CORE / "lib" / rest

    if prefix == "renderables":
        # Some are in renderables/, others in renderables/__tests__/
        direct = REF_CORE / "renderables" / rest
        if direct.exists():
            return direct
        return REF_CORE / "renderables" / "__tests__" / rest

    if prefix == "animation":
        return REF_CORE / "animation" / rest

    return REF_CORE / ts_file


# --- Report ---


@dataclass
class FileResult:
    ts_file: str
    py_file: str
    ts_count: int
    py_count: int
    faked: list[str] = field(default_factory=list)
    status: str = ""  # OK, GAP, STUB, MISS, NOREF

    @property
    def label(self) -> str:
        if self.status == "OK":
            return "\033[32m[OK]\033[0m"
        if self.status == "GAP":
            return "\033[33m[GAP]\033[0m"
        if self.status == "STUB":
            return "\033[36m[STUB]\033[0m"
        if self.status == "MISS":
            return "\033[31m[MISS]\033[0m"
        if self.status == "NOREF":
            return "\033[35m[NOREF]\033[0m"
        return f"[{self.status}]"


def evaluate(entry: PortEntry) -> FileResult:
    ts_path = resolve_ts_path(entry.ts_file)
    py_path = ROOT / entry.py_file

    ts_count = count_ts_tests(ts_path)
    py_count, _py_names = count_py_tests(py_path)

    if ts_count == -1:
        return FileResult(entry.ts_file, entry.py_file, 0, max(py_count, 0), status="NOREF")

    if py_count == -1:
        return FileResult(entry.ts_file, entry.py_file, ts_count, 0, status="MISS")

    faked = detect_faked_tests(py_path)

    if py_count == 0:
        return FileResult(entry.ts_file, entry.py_file, ts_count, 0, faked=faked, status="STUB")

    real_count = py_count - len(faked)
    if real_count >= ts_count and not faked:
        return FileResult(
            entry.ts_file, entry.py_file, ts_count, py_count, faked=faked, status="OK"
        )

    return FileResult(entry.ts_file, entry.py_file, ts_count, py_count, faked=faked, status="GAP")


def main():
    parser = argparse.ArgumentParser(description="Verify test parity")
    parser.add_argument("--file", "-f", help="Filter by filename substring")
    args = parser.parse_args()

    entries = parse_parity_md()
    if args.file:
        entries = [
            e
            for e in entries
            if args.file.lower() in e.ts_file.lower() or args.file.lower() in e.py_file.lower()
        ]

    results = [evaluate(e) for e in entries]

    # Print per-file results
    for r in results:
        if r.status == "OK":
            print(
                f"{r.label}    {r.ts_file} -> {r.py_file}: "
                f"{r.py_count}/{r.ts_count} ({len(r.faked)} faked)"
            )
        elif r.status == "GAP":
            missing = r.ts_count - (r.py_count - len(r.faked))
            faked_str = f", {len(r.faked)} faked" if r.faked else ""
            print(
                f"{r.label}   {r.ts_file} -> {r.py_file}: "
                f"{r.ts_count} TS / {r.py_count} PY  MISSING: {missing}"
                f"{faked_str}"
            )
        elif r.status == "STUB":
            print(f"{r.label}  {r.ts_file} -> {r.py_file}: STUB ONLY")
        elif r.status == "MISS":
            print(f"{r.label}  {r.ts_file} -> {r.py_file}: FILE NOT FOUND")
        elif r.status == "NOREF":
            print(f"{r.label} {r.ts_file} -> {r.py_file}: TS REFERENCE NOT FOUND")

    # Summary
    done = sum(1 for r in results if r.status == "OK")
    partial = sum(1 for r in results if r.status == "GAP")
    stub = sum(1 for r in results if r.status == "STUB")
    miss = sum(1 for r in results if r.status == "MISS")
    noref = sum(1 for r in results if r.status == "NOREF")
    total = len(results)

    total_ts = sum(r.ts_count for r in results if r.ts_count > 0)
    total_py_real = sum(r.py_count - len(r.faked) for r in results if r.py_count > 0)

    pct = (total_py_real / total_ts * 100) if total_ts > 0 else 0

    print()
    print(
        f"Summary: {done}/{total} DONE | {partial}/{total} PARTIAL | "
        f"{stub}/{total} STUB | {miss} MISSING | {noref} NOREF | "
        f"{total_py_real}/{total_ts} tests ({pct:.1f}%)"
    )

    return 0 if done == total else 1


if __name__ == "__main__":
    sys.exit(main())
