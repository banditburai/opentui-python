"""Character-diff testing utilities for OpenTUI Python."""

from __future__ import annotations
from typing import Literal


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

        for y, (exp_line, act_line) in enumerate(zip(self.expected, self.actual)):
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
        return len(self.differences) > 0

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
