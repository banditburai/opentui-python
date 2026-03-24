"""Unified-diff parser and diff-specific dataclasses.

Extracted from ``diff_renderable.py`` so the parser can be tested and
reused independently of the rendering layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ... import structs as s
from ..line_types import LineColorConfig, LineSign


@dataclass
class Hunk:
    old_start: int = 0
    old_lines: int = 0
    new_start: int = 0
    new_lines: int = 0
    lines: list[str] = field(default_factory=list)


@dataclass
class StructuredPatch:
    old_file_name: str = ""
    new_file_name: str = ""
    old_header: str = ""
    new_header: str = ""
    hunks: list[Hunk] = field(default_factory=list)


@dataclass
class LogicalLine:
    content: str = ""
    line_num: int | None = None
    hide_line_number: bool = False
    color: s.RGBA | None = None
    sign: LineSign | None = None
    line_type: str = "context"  # "context" | "add" | "remove" | "empty"


_HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")


def parse_patch(text: str) -> list[StructuredPatch]:
    """Parse a unified diff string into StructuredPatch objects.

    Raises ValueError on malformed hunk headers.
    """
    if not text:
        return []

    patches: list[StructuredPatch] = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Look for --- header
        if line.startswith("---"):
            patch = StructuredPatch()
            parts = line.split("\t", 1)
            patch.old_file_name = parts[0][4:].strip()  # skip "--- "
            patch.old_header = parts[1] if len(parts) > 1 else ""
            i += 1

            if i < len(lines) and lines[i].startswith("+++"):
                parts = lines[i].split("\t", 1)
                patch.new_file_name = parts[0][4:].strip()
                patch.new_header = parts[1] if len(parts) > 1 else ""
                i += 1

            while i < len(lines):
                line = lines[i]
                if line.startswith("---"):
                    break

                if line.startswith("@@"):
                    m = _HUNK_HEADER_RE.match(line)
                    if not m:
                        raise ValueError(f"Unknown line {i + 1} {line!r}")
                    hunk = Hunk(
                        old_start=int(m.group(1)),
                        old_lines=int(m.group(2)) if m.group(2) else 1,
                        new_start=int(m.group(3)),
                        new_lines=int(m.group(4)) if m.group(4) else 1,
                    )
                    i += 1

                    # Collect hunk lines -- track expected line count to
                    # know when the hunk is complete.
                    expected_old = hunk.old_lines
                    expected_new = hunk.new_lines
                    seen_old = 0
                    seen_new = 0
                    while i < len(lines):
                        hline = lines[i]
                        if hline.startswith("@@") or hline.startswith("---"):
                            break
                        if hline.startswith("+"):
                            hunk.lines.append(hline)
                            seen_new += 1
                            i += 1
                        elif hline.startswith("-"):
                            hunk.lines.append(hline)
                            seen_old += 1
                            i += 1
                        elif hline.startswith(" "):
                            hunk.lines.append(hline)
                            seen_old += 1
                            seen_new += 1
                            i += 1
                        elif hline.startswith("\\"):
                            # "\ No newline at end of file" -- skip
                            i += 1
                        elif hline == "":
                            # Empty line -- could be an empty context line within
                            # a hunk (common in diffs) or end of diff.
                            # Treat as context if we haven't consumed all expected lines.
                            if seen_old < expected_old or seen_new < expected_new:
                                hunk.lines.append(" ")  # empty context line
                                seen_old += 1
                                seen_new += 1
                                i += 1
                            else:
                                i += 1
                                break
                        else:
                            raise ValueError(f"Unknown line {i + 1} {hline!r}")

                    patch.hunks.append(hunk)
                elif line.startswith("Index:") or line.startswith("====="):
                    i += 1
                else:
                    i += 1

            patches.append(patch)
        else:
            i += 1

    return patches
