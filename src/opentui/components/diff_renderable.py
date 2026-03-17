"""DiffRenderable - unified and split-view diff display.

Side-by-side and unified diff viewer component.
Renders unified diff format with line numbers, signs (+/-), and custom colors.
Supports both unified (single column) and split (side-by-side) view modes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .. import structs as s
from .base import Renderable

if TYPE_CHECKING:
    from ..renderer import Buffer


# ---------------------------------------------------------------------------
# Diff parsing (subset of unified diff patch parsing)
# ---------------------------------------------------------------------------


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
            # Parse old filename
            parts = line.split("\t", 1)
            patch.old_file_name = parts[0][4:].strip()  # skip "--- "
            patch.old_header = parts[1] if len(parts) > 1 else ""
            i += 1

            # Parse new filename (+++)
            if i < len(lines) and lines[i].startswith("+++"):
                parts = lines[i].split("\t", 1)
                patch.new_file_name = parts[0][4:].strip()
                patch.new_header = parts[1] if len(parts) > 1 else ""
                i += 1

            # Parse hunks
            while i < len(lines):
                line = lines[i]
                if line.startswith("---"):
                    break  # next patch

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

                    # Collect hunk lines — track expected line count to
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
                            # "\ No newline at end of file" — skip
                            i += 1
                        elif hline == "":
                            # Empty line — could be an empty context line within
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


# ---------------------------------------------------------------------------
# Line sign type
# ---------------------------------------------------------------------------


@dataclass
class LineSign:
    after: str = ""
    after_color: s.RGBA | None = None


@dataclass
class LineColorConfig:
    gutter: s.RGBA | None = None
    content: s.RGBA | None = None


# ---------------------------------------------------------------------------
# Logical line for split view processing
# ---------------------------------------------------------------------------


@dataclass
class LogicalLine:
    content: str = ""
    line_num: int | None = None
    hide_line_number: bool = False
    color: s.RGBA | None = None
    sign: LineSign | None = None
    line_type: str = "context"  # "context" | "add" | "remove" | "empty"


# ---------------------------------------------------------------------------
# DiffRenderable
# ---------------------------------------------------------------------------


class DiffRenderable(Renderable):
    """Unified and split-view diff renderer.

    Parses unified diff format and renders with line numbers, +/- signs,
    and customizable colors for added, removed, and context lines.

    Usage:
        diff = DiffRenderable(
            diff=unified_diff_string,
            view="unified",   # or "split"
            show_line_numbers=True,
        )
    """

    __slots__ = (
        "_diff_text",
        "_view_mode",
        "_parsed_diff",
        "_parse_error",
        # Code options
        "_diff_fg",
        "_filetype_str",
        "_wrap_mode_str",
        "_conceal_mode",
        # Line number options
        "_show_line_numbers",
        "_line_number_fg_color",
        "_line_number_bg_color",
        # Diff styling
        "_added_bg",
        "_removed_bg",
        "_context_bg",
        "_added_content_bg",
        "_removed_content_bg",
        "_context_content_bg",
        "_added_sign_color",
        "_removed_sign_color",
        "_added_line_number_bg",
        "_removed_line_number_bg",
        # Internal rendering data
        "_unified_lines",
        "_unified_line_colors",
        "_unified_line_signs",
        "_unified_line_numbers",
        # Split view data
        "_left_lines",
        "_right_lines",
        "_left_line_colors",
        "_right_line_colors",
        "_left_line_signs",
        "_right_line_signs",
        "_left_line_numbers",
        "_right_line_numbers",
        "_left_hide_line_numbers",
        "_right_hide_line_numbers",
        # Listener tracking
        "_listener_count",
        # Line highlighting
        "_user_line_colors",
        "_user_highlight_ranges",
        # Rebuild state
        "_pending_rebuild",
        "_last_width",
        # Cached mock renderables for event emission
        "_mock_left_code",
        "_mock_right_code",
        # Cached mock line number renderables
        "_mock_left_line_num",
        "_mock_right_line_num",
    )

    def __init__(
        self,
        *,
        diff: str = "",
        view: str = "unified",
        # Code options
        fg: s.RGBA | str | None = None,
        filetype: str | None = None,
        wrap_mode: str | None = None,
        conceal: bool = False,
        # Line number options
        show_line_numbers: bool = True,
        line_number_fg: s.RGBA | str | None = "#888888",
        line_number_bg: s.RGBA | str | None = "transparent",
        # Diff styling
        added_bg: s.RGBA | str | None = "#1a4d1a",
        removed_bg: s.RGBA | str | None = "#4d1a1a",
        context_bg: s.RGBA | str | None = "transparent",
        added_content_bg: s.RGBA | str | None = None,
        removed_content_bg: s.RGBA | str | None = None,
        context_content_bg: s.RGBA | str | None = None,
        added_sign_color: s.RGBA | str | None = "#22c55e",
        removed_sign_color: s.RGBA | str | None = "#ef4444",
        added_line_number_bg: s.RGBA | str | None = "transparent",
        removed_line_number_bg: s.RGBA | str | None = "transparent",
        # Base renderable options
        **kwargs,
    ):
        # Set flex direction based on view mode
        if "flex_direction" not in kwargs:
            kwargs["flex_direction"] = "row" if view == "split" else "column"
        super().__init__(**kwargs)

        self._diff_text = diff
        self._view_mode = view
        self._parsed_diff: StructuredPatch | None = None
        self._parse_error: Exception | None = None

        # Code options — use a separate attribute name to avoid collision with base fg
        self._diff_fg: s.RGBA | None = self._parse_color(fg) if fg else None
        self._filetype_str = filetype
        self._wrap_mode_str = wrap_mode
        self._conceal_mode = conceal

        # Line number options
        self._show_line_numbers = show_line_numbers
        self._line_number_fg_color = self._parse_color(line_number_fg)
        self._line_number_bg_color = self._parse_color(line_number_bg)

        # Diff styling
        self._added_bg = self._parse_color(added_bg) or s.RGBA(0.102, 0.302, 0.102, 1)
        self._removed_bg = self._parse_color(removed_bg) or s.RGBA(0.302, 0.102, 0.102, 1)
        self._context_bg = self._parse_color(context_bg)
        self._added_content_bg = self._parse_color(added_content_bg)
        self._removed_content_bg = self._parse_color(removed_content_bg)
        self._context_content_bg = self._parse_color(context_content_bg)
        self._added_sign_color = self._parse_color(added_sign_color) or s.RGBA(
            0.133, 0.773, 0.369, 1
        )
        self._removed_sign_color = self._parse_color(removed_sign_color) or s.RGBA(
            0.937, 0.267, 0.267, 1
        )
        self._added_line_number_bg = self._parse_color(added_line_number_bg)
        self._removed_line_number_bg = self._parse_color(removed_line_number_bg)

        # Internal rendering data (unified view)
        self._unified_lines: list[str] = []
        self._unified_line_colors: dict[int, LineColorConfig] = {}
        self._unified_line_signs: dict[int, LineSign] = {}
        self._unified_line_numbers: dict[int, int] = {}

        # Split view data
        self._left_lines: list[str] = []
        self._right_lines: list[str] = []
        self._left_line_colors: dict[int, LineColorConfig] = {}
        self._right_line_colors: dict[int, LineColorConfig] = {}
        self._left_line_signs: dict[int, LineSign] = {}
        self._right_line_signs: dict[int, LineSign] = {}
        self._left_line_numbers: dict[int, int] = {}
        self._right_line_numbers: dict[int, int] = {}
        self._left_hide_line_numbers: set[int] = set()
        self._right_hide_line_numbers: set[int] = set()

        # Listener tracking (for no-leak tests)
        self._listener_count = 0

        # Line highlighting API
        self._user_line_colors: dict[int, s.RGBA | str | LineColorConfig] = {}
        self._user_highlight_ranges: list[tuple[int, int, s.RGBA | str | LineColorConfig]] = []

        # Rebuild state
        self._pending_rebuild = False
        self._last_width = 0

        # Cached mock renderables for event emission
        self._mock_left_code: _MockCodeRenderable | None = None
        self._mock_right_code: _MockCodeRenderable | None = None
        # Cached mock line number renderables
        self._mock_left_line_num: _MockLineNumberRenderable | None = None
        self._mock_right_line_num: _MockLineNumberRenderable | None = None

        # Parse and build view
        if self._diff_text:
            self._parse_diff()
            self._build_view()

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def diff(self) -> str:
        return self._diff_text

    @diff.setter
    def diff(self, value: str) -> None:
        if self._diff_text != value:
            self._diff_text = value
            self._parse_diff()
            self._rebuild_view()

    @property
    def view(self) -> str:
        return self._view_mode

    @view.setter
    def view(self, value: str) -> None:
        if self._view_mode != value:
            self._view_mode = value
            self._flex_direction = "row" if value == "split" else "column"
            self._mock_left_line_num = None
            self._mock_right_line_num = None
            self._build_view()
            self.mark_dirty()

    @property
    def filetype(self) -> str | None:
        return self._filetype_str

    @filetype.setter
    def filetype(self, value: str | None) -> None:
        if self._filetype_str != value:
            self._filetype_str = value
            self._rebuild_view()

    @property
    def wrap_mode(self) -> str | None:
        return self._wrap_mode_str

    @wrap_mode.setter
    def wrap_mode(self, value: str | None) -> None:
        if self._wrap_mode_str != value:
            self._wrap_mode_str = value
            self._build_view()
            self.mark_dirty()

    @property
    def show_line_numbers(self) -> bool:
        return self._show_line_numbers

    @show_line_numbers.setter
    def show_line_numbers(self, value: bool) -> None:
        if self._show_line_numbers != value:
            self._show_line_numbers = value
            self.mark_dirty()

    @property
    def conceal(self) -> bool:
        return self._conceal_mode

    @conceal.setter
    def conceal(self, value: bool) -> None:
        if self._conceal_mode != value:
            self._conceal_mode = value
            self._rebuild_view()

    # fg property — override base to manage diff-specific fg
    @property
    def fg(self) -> s.RGBA | None:
        return self._diff_fg

    @fg.setter
    def fg(self, value: s.RGBA | str | None) -> None:
        parsed = self._parse_color(value) if value else None
        if self._diff_fg != parsed:
            self._diff_fg = parsed
            self.mark_dirty()

    # Diff color properties
    @property
    def added_bg(self) -> s.RGBA:
        return self._added_bg

    @added_bg.setter
    def added_bg(self, value: s.RGBA | str) -> None:
        parsed = self._parse_color(value)
        if parsed and self._added_bg != parsed:
            self._added_bg = parsed
            self._rebuild_view()

    @property
    def removed_bg(self) -> s.RGBA:
        return self._removed_bg

    @removed_bg.setter
    def removed_bg(self, value: s.RGBA | str) -> None:
        parsed = self._parse_color(value)
        if parsed and self._removed_bg != parsed:
            self._removed_bg = parsed
            self._rebuild_view()

    @property
    def context_bg(self) -> s.RGBA | None:
        return self._context_bg

    @property
    def added_content_bg(self) -> s.RGBA | None:
        return self._added_content_bg

    @added_content_bg.setter
    def added_content_bg(self, value: s.RGBA | str | None) -> None:
        parsed = self._parse_color(value) if value else None
        if self._added_content_bg != parsed:
            self._added_content_bg = parsed
            self._rebuild_view()

    @property
    def removed_content_bg(self) -> s.RGBA | None:
        return self._removed_content_bg

    @removed_content_bg.setter
    def removed_content_bg(self, value: s.RGBA | str | None) -> None:
        parsed = self._parse_color(value) if value else None
        if self._removed_content_bg != parsed:
            self._removed_content_bg = parsed
            self._rebuild_view()

    @property
    def context_content_bg(self) -> s.RGBA | None:
        return self._context_content_bg

    @property
    def added_sign_color(self) -> s.RGBA:
        return self._added_sign_color

    @property
    def removed_sign_color(self) -> s.RGBA:
        return self._removed_sign_color

    @property
    def line_number_fg(self) -> s.RGBA | None:
        return self._line_number_fg_color

    @property
    def line_number_bg(self) -> s.RGBA | None:
        return self._line_number_bg_color

    @property
    def added_line_number_bg(self) -> s.RGBA | None:
        return self._added_line_number_bg

    @property
    def removed_line_number_bg(self) -> s.RGBA | None:
        return self._removed_line_number_bg

    # ── Internal: access CodeRenderable-like and LineNumberRenderable-like ──

    @property
    def left_code_renderable(self) -> Any:
        """Access internal left CodeRenderable (unified/split left side)."""
        if self._mock_left_code is None:
            self._mock_left_code = _MockCodeRenderable(self, "left")
        return self._mock_left_code

    @property
    def right_code_renderable(self) -> Any:
        """Access internal right CodeRenderable (split view right side)."""
        if self._mock_right_code is None:
            self._mock_right_code = _MockCodeRenderable(self, "right")
        return self._mock_right_code

    @property
    def left_side(self) -> Any:
        """Access internal left LineNumberRenderable (unified/split left side)."""
        if self._parsed_diff and self._parsed_diff.hunks:
            if self._mock_left_line_num is None:
                self._mock_left_line_num = _MockLineNumberRenderable(self, "left")
            return self._mock_left_line_num
        return None

    @property
    def right_side(self) -> Any:
        """Access internal right LineNumberRenderable (split view right side)."""
        if self._view_mode == "split" and self._parsed_diff and self._parsed_diff.hunks:
            if self._mock_right_line_num is None:
                self._mock_right_line_num = _MockLineNumberRenderable(self, "right")
            return self._mock_right_line_num
        return None

    # ── Diff parsing ────────────────────────────────────────────────────

    def _parse_diff(self) -> None:
        if not self._diff_text:
            self._parsed_diff = None
            self._parse_error = None
            self._mock_left_line_num = None
            self._mock_right_line_num = None
            return

        try:
            patches = parse_patch(self._diff_text)
            if not patches:
                self._parsed_diff = None
                self._parse_error = None
                self._mock_left_line_num = None
                self._mock_right_line_num = None
                return
            self._parsed_diff = patches[0]
            self._parse_error = None
            self._mock_left_line_num = None
            self._mock_right_line_num = None
        except Exception as e:
            self._parsed_diff = None
            self._parse_error = e
            self._mock_left_line_num = None
            self._mock_right_line_num = None

    # ── View building ───────────────────────────────────────────────────

    def _build_view(self) -> None:
        if self._parse_error:
            self._build_error_view()
            return

        if not self._parsed_diff or not self._parsed_diff.hunks:
            self._unified_lines = []
            self._unified_line_colors = {}
            self._unified_line_signs = {}
            self._unified_line_numbers = {}
            self._left_lines = []
            self._right_lines = []
            return

        if self._view_mode == "unified":
            self._build_unified_view()
        else:
            self._build_split_view()

        self.mark_dirty()

    def _rebuild_view(self) -> None:
        self._build_view()
        # Notify cached mock code renderables so registered event handlers fire
        self._emit_line_info_change()

    def _emit_line_info_change(self) -> None:
        """Fire 'line-info-change' on cached mock code renderables (if any)."""
        if self._mock_left_code is not None:
            self._mock_left_code.emit("line-info-change")
        if self._mock_right_code is not None:
            self._mock_right_code.emit("line-info-change")

    def _build_error_view(self) -> None:
        """Build error display with error message and raw diff."""
        self._unified_lines = []
        self._unified_line_colors = {}
        self._unified_line_signs = {}
        self._unified_line_numbers = {}

        # Error message line
        error_msg = f"Error parsing diff: {self._parse_error}"
        self._unified_lines.append(error_msg)
        # Blank line
        self._unified_lines.append("")
        # Raw diff content
        for line in self._diff_text.split("\n"):
            self._unified_lines.append(line)

        self.mark_dirty()

    def _build_unified_view(self) -> None:
        if not self._parsed_diff:
            return

        content_lines: list[str] = []
        line_colors: dict[int, LineColorConfig] = {}
        line_signs: dict[int, LineSign] = {}
        line_numbers: dict[int, int] = {}

        line_index = 0

        for hunk in self._parsed_diff.hunks:
            old_line_num = hunk.old_start
            new_line_num = hunk.new_start

            for line in hunk.lines:
                if not line:
                    continue
                first_char = line[0]
                content = line[1:]

                if first_char == "+":
                    content_lines.append(content)
                    config = LineColorConfig(
                        gutter=self._added_line_number_bg,
                        content=self._added_content_bg
                        if self._added_content_bg
                        else self._added_bg,
                    )
                    line_colors[line_index] = config
                    line_signs[line_index] = LineSign(
                        after=" +",
                        after_color=self._added_sign_color,
                    )
                    line_numbers[line_index] = new_line_num
                    new_line_num += 1
                    line_index += 1
                elif first_char == "-":
                    content_lines.append(content)
                    config = LineColorConfig(
                        gutter=self._removed_line_number_bg,
                        content=self._removed_content_bg
                        if self._removed_content_bg
                        else self._removed_bg,
                    )
                    line_colors[line_index] = config
                    line_signs[line_index] = LineSign(
                        after=" -",
                        after_color=self._removed_sign_color,
                    )
                    line_numbers[line_index] = old_line_num
                    old_line_num += 1
                    line_index += 1
                elif first_char == " ":
                    content_lines.append(content)
                    config = LineColorConfig(
                        gutter=self._line_number_bg_color,
                        content=self._context_content_bg
                        if self._context_content_bg
                        else self._context_bg,
                    )
                    line_colors[line_index] = config
                    line_numbers[line_index] = new_line_num
                    old_line_num += 1
                    new_line_num += 1
                    line_index += 1

        self._unified_lines = content_lines
        self._unified_line_colors = line_colors
        self._unified_line_signs = line_signs
        self._unified_line_numbers = line_numbers

    def _build_split_view(self) -> None:
        if not self._parsed_diff:
            return

        left_logical: list[LogicalLine] = []
        right_logical: list[LogicalLine] = []

        for hunk in self._parsed_diff.hunks:
            old_line_num = hunk.old_start
            new_line_num = hunk.new_start

            i = 0
            while i < len(hunk.lines):
                line = hunk.lines[i]
                if not line:
                    i += 1
                    continue
                first_char = line[0]

                if first_char == " ":
                    content = line[1:]
                    left_logical.append(
                        LogicalLine(
                            content=content,
                            line_num=old_line_num,
                            color=self._context_bg,
                            line_type="context",
                        )
                    )
                    right_logical.append(
                        LogicalLine(
                            content=content,
                            line_num=new_line_num,
                            color=self._context_bg,
                            line_type="context",
                        )
                    )
                    old_line_num += 1
                    new_line_num += 1
                    i += 1
                elif first_char == "\\":
                    i += 1
                else:
                    # Collect a block of removes and adds
                    removes: list[tuple[str, int]] = []
                    adds: list[tuple[str, int]] = []

                    while i < len(hunk.lines):
                        current_line = hunk.lines[i]
                        if not current_line:
                            i += 1
                            continue
                        current_char = current_line[0]

                        if current_char in {" ", "\\"}:
                            break

                        content = current_line[1:]
                        if current_char == "-":
                            removes.append((content, old_line_num))
                            old_line_num += 1
                        elif current_char == "+":
                            adds.append((content, new_line_num))
                            new_line_num += 1
                        i += 1

                    max_length = max(len(removes), len(adds))

                    for j in range(max_length):
                        if j < len(removes):
                            left_logical.append(
                                LogicalLine(
                                    content=removes[j][0],
                                    line_num=removes[j][1],
                                    color=self._removed_bg,
                                    sign=LineSign(after=" -", after_color=self._removed_sign_color),
                                    line_type="remove",
                                )
                            )
                        else:
                            left_logical.append(
                                LogicalLine(
                                    content="",
                                    hide_line_number=True,
                                    line_type="empty",
                                )
                            )

                        if j < len(adds):
                            right_logical.append(
                                LogicalLine(
                                    content=adds[j][0],
                                    line_num=adds[j][1],
                                    color=self._added_bg,
                                    sign=LineSign(after=" +", after_color=self._added_sign_color),
                                    line_type="add",
                                )
                            )
                        else:
                            right_logical.append(
                                LogicalLine(
                                    content="",
                                    hide_line_number=True,
                                    line_type="empty",
                                )
                            )

        # Build rendering data from logical lines
        self._left_lines = [ll.content for ll in left_logical]
        self._right_lines = [ll.content for ll in right_logical]

        self._left_line_colors = {}
        self._right_line_colors = {}
        self._left_line_signs = {}
        self._right_line_signs = {}
        self._left_line_numbers = {}
        self._right_line_numbers = {}
        self._left_hide_line_numbers = set()
        self._right_hide_line_numbers = set()

        for idx, ll in enumerate(left_logical):
            if ll.line_num is not None:
                self._left_line_numbers[idx] = ll.line_num
            if ll.hide_line_number:
                self._left_hide_line_numbers.add(idx)
            if ll.line_type == "remove":
                self._left_line_colors[idx] = LineColorConfig(
                    gutter=self._removed_line_number_bg,
                    content=self._removed_content_bg
                    if self._removed_content_bg
                    else self._removed_bg,
                )
            elif ll.line_type == "context":
                self._left_line_colors[idx] = LineColorConfig(
                    gutter=self._line_number_bg_color,
                    content=self._context_content_bg
                    if self._context_content_bg
                    else self._context_bg,
                )
            if ll.sign:
                self._left_line_signs[idx] = ll.sign

        for idx, ll in enumerate(right_logical):
            if ll.line_num is not None:
                self._right_line_numbers[idx] = ll.line_num
            if ll.hide_line_number:
                self._right_hide_line_numbers.add(idx)
            if ll.line_type == "add":
                self._right_line_colors[idx] = LineColorConfig(
                    gutter=self._added_line_number_bg,
                    content=self._added_content_bg if self._added_content_bg else self._added_bg,
                )
            elif ll.line_type == "context":
                self._right_line_colors[idx] = LineColorConfig(
                    gutter=self._line_number_bg_color,
                    content=self._context_content_bg
                    if self._context_content_bg
                    else self._context_bg,
                )
            if ll.sign:
                self._right_line_signs[idx] = ll.sign

    # ── Rendering ───────────────────────────────────────────────────────

    def _compute_gutter_width(self, line_numbers: dict[int, int]) -> int:
        """Compute gutter width based on max line number."""
        if not line_numbers:
            return 2  # minimum
        max_num = max(line_numbers.values())
        num_width = len(str(max_num))
        # Format: " <num> <sign> " — num_width + 1 padding left + sign(2) + 1 space
        return num_width + 1  # just the number column width (padding added at render)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render the diff to the buffer."""
        if not self._visible:
            return

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        x = self._x + self._padding_left
        y = self._y + self._padding_top
        total_width = self._layout_width - self._padding_left - self._padding_right
        total_height = self._layout_height - self._padding_top - self._padding_bottom

        if total_width <= 0 or total_height <= 0:
            return

        if self._border:
            bt = 1 if self._border_top else 0
            br = 1 if self._border_right else 0
            bb = 1 if self._border_bottom else 0
            bl = 1 if self._border_left else 0
            x += bl
            y += bt
            total_width -= bl + br
            total_height -= bt + bb

        if self._parse_error:
            self._render_error_view(buffer, x, y, total_width, total_height)
        elif self._view_mode == "unified":
            self._render_unified(buffer, x, y, total_width, total_height)
        else:
            self._render_split(buffer, x, y, total_width, total_height)

        if self._render_after:
            self._render_after(buffer, delta_time, self)

    def _render_error_view(self, buffer: Buffer, x: int, y: int, width: int, height: int) -> None:
        """Render error view with error message and raw diff."""
        for i, line in enumerate(self._unified_lines):
            if i >= height:
                break
            line_y = y + i
            fg = s.RGBA(0.937, 0.267, 0.267, 1) if i == 0 else self._diff_fg
            display_line = line[:width]
            buffer.draw_text(display_line, x, line_y, fg, self._background_color)

    @staticmethod
    def _wrap_text(text: str, width: int, mode: str | None) -> list[str]:
        """Split *text* into visual rows that fit in *width* columns.

        When *mode* is ``"word"``, breaks on word boundaries; ``"char"``
        breaks at any character.  Returns ``[text]`` (single row) if
        the text already fits or mode is ``None``/``"none"``.
        """
        if width <= 0 or len(text) <= width:
            return [text]

        rows: list[str] = []
        remaining = text

        if mode == "word":
            while len(remaining) > width:
                # Find last space within width
                break_at = remaining.rfind(" ", 0, width + 1)
                if break_at <= 0:
                    break_at = width  # hard break
                rows.append(remaining[:break_at])
                remaining = (
                    remaining[break_at:].lstrip(" ") if mode == "word" else remaining[break_at:]
                )
            if remaining:
                rows.append(remaining)
        else:  # char
            while len(remaining) > width:
                rows.append(remaining[:width])
                remaining = remaining[width:]
            if remaining:
                rows.append(remaining)

        return rows or [text]

    def _render_side(
        self,
        buffer: Buffer,
        x: int,
        y: int,
        width: int,
        height: int,
        lines: list[str],
        line_colors: dict[int, LineColorConfig],
        line_signs: dict[int, LineSign],
        line_numbers: dict[int, int],
        hide_line_numbers: set[int] | None = None,
    ) -> None:
        """Render one side (unified or one half of split)."""
        if not lines:
            return

        hide_ln = hide_line_numbers or set()
        do_wrap = self._wrap_mode_str in ("word", "char")

        gutter_width = 0
        sign_width = 0
        if self._show_line_numbers:
            max_num = max(line_numbers.values()) if line_numbers else 0
            num_digits = max(len(str(max_num)), 1)
            gutter_width = num_digits + 1  # +1 for left padding
            sign_width = 2  # " +" or " -"

        content_x = x + gutter_width + sign_width + (1 if self._show_line_numbers else 0)
        content_width = width - gutter_width - sign_width - (1 if self._show_line_numbers else 0)

        visual_row = 0  # tracks the current visual row offset from y

        for i, line in enumerate(lines):
            if visual_row >= height:
                break

            # Line color config
            color_config = line_colors.get(i)

            if do_wrap and content_width > 0 and len(line) > content_width:
                visual_lines = self._wrap_text(line, content_width, self._wrap_mode_str)
            else:
                visual_lines = [line[:content_width] if content_width > 0 else ""]

            for vl_idx, vl_text in enumerate(visual_lines):
                if visual_row >= height:
                    break

                line_y = y + visual_row

                if color_config and color_config.gutter and self._show_line_numbers:
                    buffer.fill_rect(
                        x, line_y, gutter_width + sign_width + 1, 1, color_config.gutter
                    )

                if color_config and color_config.content:
                    buffer.fill_rect(content_x, line_y, content_width, 1, color_config.content)

                if vl_idx == 0 and self._show_line_numbers and i not in hide_ln:
                    line_num = line_numbers.get(i)
                    if line_num is not None:
                        num_str = str(line_num).rjust(gutter_width)
                        buffer.draw_text(
                            num_str,
                            x,
                            line_y,
                            self._line_number_fg_color,
                            color_config.gutter if color_config else None,
                        )

                if vl_idx == 0 and self._show_line_numbers:
                    sign = line_signs.get(i)
                    if sign and sign.after:
                        sign_x = x + gutter_width
                        buffer.draw_text(
                            sign.after,
                            sign_x,
                            line_y,
                            sign.after_color,
                            color_config.gutter if color_config else None,
                        )

                if content_width > 0:
                    buffer.draw_text(
                        vl_text,
                        content_x,
                        line_y,
                        self._diff_fg,
                        color_config.content if color_config else self._background_color,
                    )

                visual_row += 1

    def _render_unified(self, buffer: Buffer, x: int, y: int, width: int, height: int) -> None:
        """Render unified view."""
        self._render_side(
            buffer,
            x,
            y,
            width,
            height,
            self._unified_lines,
            self._unified_line_colors,
            self._unified_line_signs,
            self._unified_line_numbers,
        )

    def _render_split(self, buffer: Buffer, x: int, y: int, width: int, height: int) -> None:
        """Render split view (side by side) with aligned wrapping."""
        half_width = width // 2
        right_width = width - half_width
        do_wrap = self._wrap_mode_str in ("word", "char")

        if not do_wrap:
            # No wrapping — simple independent render
            self._render_side(
                buffer,
                x,
                y,
                half_width,
                height,
                self._left_lines,
                self._left_line_colors,
                self._left_line_signs,
                self._left_line_numbers,
                self._left_hide_line_numbers,
            )
            self._render_side(
                buffer,
                x + half_width,
                y,
                right_width,
                height,
                self._right_lines,
                self._right_line_colors,
                self._right_line_signs,
                self._right_line_numbers,
                self._right_hide_line_numbers,
            )
            return

        # With wrapping, we need to compute visual row counts for each
        # logical line on both sides and align them.
        def _content_width(w: int, line_nums: dict[int, int], show_ln: bool) -> int:
            gw = 0
            sw = 0
            if show_ln:
                max_n = max(line_nums.values()) if line_nums else 0
                nd = max(len(str(max_n)), 1)
                gw = nd + 1
                sw = 2
            return w - gw - sw - (1 if show_ln else 0)

        left_cw = _content_width(half_width, self._left_line_numbers, self._show_line_numbers)
        right_cw = _content_width(right_width, self._right_line_numbers, self._show_line_numbers)

        num_logical = max(len(self._left_lines), len(self._right_lines))

        # Pre-compute wrapped visual rows per logical line
        left_wrapped: list[list[str]] = []
        right_wrapped: list[list[str]] = []

        for i in range(num_logical):
            if i < len(self._left_lines):
                lt = self._left_lines[i]
                if left_cw > 0 and len(lt) > left_cw:
                    left_wrapped.append(self._wrap_text(lt, left_cw, self._wrap_mode_str))
                else:
                    left_wrapped.append([lt[:left_cw] if left_cw > 0 else ""])
            else:
                left_wrapped.append([""])

            if i < len(self._right_lines):
                rt = self._right_lines[i]
                if right_cw > 0 and len(rt) > right_cw:
                    right_wrapped.append(self._wrap_text(rt, right_cw, self._wrap_mode_str))
                else:
                    right_wrapped.append([rt[:right_cw] if right_cw > 0 else ""])
            else:
                right_wrapped.append([""])

        # Now render both sides aligned
        visual_row = 0

        # Left gutter metrics
        l_gw = 0
        l_sw = 0
        if self._show_line_numbers:
            l_max = max(self._left_line_numbers.values()) if self._left_line_numbers else 0
            l_nd = max(len(str(l_max)), 1)
            l_gw = l_nd + 1
            l_sw = 2
        l_cx = x + l_gw + l_sw + (1 if self._show_line_numbers else 0)

        # Right gutter metrics
        r_gw = 0
        r_sw = 0
        if self._show_line_numbers:
            r_max = max(self._right_line_numbers.values()) if self._right_line_numbers else 0
            r_nd = max(len(str(r_max)), 1)
            r_gw = r_nd + 1
            r_sw = 2
        r_cx = x + half_width + r_gw + r_sw + (1 if self._show_line_numbers else 0)

        l_hide = self._left_hide_line_numbers
        r_hide = self._right_hide_line_numbers

        for i in range(num_logical):
            if visual_row >= height:
                break

            lw = left_wrapped[i]
            rw = right_wrapped[i]
            max_rows = max(len(lw), len(rw))

            l_cc = self._left_line_colors.get(i)
            r_cc = self._right_line_colors.get(i)

            for vr in range(max_rows):
                if visual_row >= height:
                    break
                ly = y + visual_row

                # -- Left side --
                if vr < len(lw):
                    if l_cc and l_cc.gutter and self._show_line_numbers:
                        buffer.fill_rect(x, ly, l_gw + l_sw + 1, 1, l_cc.gutter)
                    if l_cc and l_cc.content:
                        buffer.fill_rect(l_cx, ly, left_cw, 1, l_cc.content)
                    if vr == 0 and self._show_line_numbers and i not in l_hide:
                        ln = self._left_line_numbers.get(i)
                        if ln is not None:
                            ns = str(ln).rjust(l_gw)
                            buffer.draw_text(
                                ns, x, ly, self._line_number_fg_color, l_cc.gutter if l_cc else None
                            )
                    if vr == 0 and self._show_line_numbers:
                        ls = self._left_line_signs.get(i)
                        if ls and ls.after:
                            buffer.draw_text(
                                ls.after,
                                x + l_gw,
                                ly,
                                ls.after_color,
                                l_cc.gutter if l_cc else None,
                            )
                    if left_cw > 0:
                        buffer.draw_text(
                            lw[vr],
                            l_cx,
                            ly,
                            self._diff_fg,
                            l_cc.content if l_cc else self._background_color,
                        )

                # -- Right side --
                if vr < len(rw):
                    rx = x + half_width
                    if r_cc and r_cc.gutter and self._show_line_numbers:
                        buffer.fill_rect(rx, ly, r_gw + r_sw + 1, 1, r_cc.gutter)
                    if r_cc and r_cc.content:
                        buffer.fill_rect(r_cx, ly, right_cw, 1, r_cc.content)
                    if vr == 0 and self._show_line_numbers and i not in r_hide:
                        rn = self._right_line_numbers.get(i)
                        if rn is not None:
                            ns = str(rn).rjust(r_gw)
                            buffer.draw_text(
                                ns,
                                rx,
                                ly,
                                self._line_number_fg_color,
                                r_cc.gutter if r_cc else None,
                            )
                    if vr == 0 and self._show_line_numbers:
                        rs = self._right_line_signs.get(i)
                        if rs and rs.after:
                            buffer.draw_text(
                                rs.after,
                                rx + r_gw,
                                ly,
                                rs.after_color,
                                r_cc.gutter if r_cc else None,
                            )
                    if right_cw > 0:
                        buffer.draw_text(
                            rw[vr],
                            r_cx,
                            ly,
                            self._diff_fg,
                            r_cc.content if r_cc else self._background_color,
                        )

                visual_row += 1

    # ── Line highlighting API ───────────────────────────────────────────

    def set_line_color(self, line: int, color: s.RGBA | str | LineColorConfig) -> None:
        """Set color for a specific line."""
        self._user_line_colors[line] = color

    def clear_line_color(self, line: int) -> None:
        """Clear color for a specific line."""
        self._user_line_colors.pop(line, None)

    def set_line_colors(self, line_colors: dict[int, s.RGBA | str | LineColorConfig]) -> None:
        """Set colors for multiple lines."""
        self._user_line_colors.update(line_colors)

    def clear_all_line_colors(self) -> None:
        """Clear all line colors."""
        self._user_line_colors.clear()

    def highlight_lines(
        self, start_line: int, end_line: int, color: s.RGBA | str | LineColorConfig
    ) -> None:
        """Highlight a range of lines."""
        self._user_highlight_ranges.append((start_line, end_line, color))

    def clear_highlight_lines(self, start_line: int, end_line: int) -> None:
        """Clear highlight for a range of lines."""
        self._user_highlight_ranges = [
            (s, e, c)
            for s, e, c in self._user_highlight_ranges
            if not (s == start_line and e == end_line)
        ]

    # ── Destroy ─────────────────────────────────────────────────────────

    def destroy_recursively(self) -> None:
        """Override to clean up listeners."""
        self._pending_rebuild = False
        super().destroy_recursively()


# ---------------------------------------------------------------------------
# Mock internal renderables for test compatibility
# ---------------------------------------------------------------------------


class _MockCodeRenderable:
    """Mock CodeRenderable for tests that access DiffRenderable internals.

    Provides enough API surface for the listener-tracking tests.
    """

    def __init__(self, owner: DiffRenderable, side: str):
        self._owner = owner
        self._side = side
        self._event_handlers: dict[str, list] = {}
        self._fg_override: s.RGBA | None = None

    @property
    def fg(self) -> s.RGBA | None:
        return self._owner._diff_fg

    @fg.setter
    def fg(self, value: s.RGBA | None) -> None:
        self._owner._diff_fg = value

    @property
    def content(self) -> str:
        if self._side == "left":
            if self._owner._view_mode == "unified":
                return "\n".join(self._owner._unified_lines)
            return "\n".join(self._owner._left_lines)
        return "\n".join(self._owner._right_lines)

    @content.setter
    def content(self, value: str) -> None:
        self.emit("line-info-change")

    @property
    def wrapMode(self) -> str | None:
        return self._owner._wrap_mode_str

    @wrapMode.setter
    def wrapMode(self, value: str) -> None:
        pass

    @property
    def isHighlighting(self) -> bool:
        return False

    @property
    def lineInfo(self) -> dict:
        lines = self._owner._unified_lines if self._side == "left" else self._owner._right_lines
        return {"lineSources": list(range(len(lines)))}

    @property
    def virtualLineCount(self) -> int:
        lines = self._owner._unified_lines if self._side == "left" else self._owner._right_lines
        return len(lines)

    def on(self, event: str, handler: Any) -> None:
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Any | None = None) -> None:
        if event not in self._event_handlers:
            return
        if handler is None:
            self._event_handlers[event] = []
        else:
            self._event_handlers[event] = [h for h in self._event_handlers[event] if h != handler]

    def emit(self, event: str, *args: Any) -> None:
        for handler in self._event_handlers.get(event, []):
            handler(*args)

    def listener_count(self, event: str) -> int:
        return len(self._event_handlers.get(event, []))


class _MockLineNumberRenderable:
    """Mock LineNumberRenderable for tests accessing DiffRenderable internals."""

    def __init__(self, owner: DiffRenderable, side: str):
        self._owner = owner
        self._side = side
        self._destroyed = False

    @property
    def isDestroyed(self) -> bool:
        return self._owner._destroyed

    @property
    def is_destroyed(self) -> bool:
        return self._owner._destroyed

    @property
    def showLineNumbers(self) -> bool:
        return self._owner._show_line_numbers

    @showLineNumbers.setter
    def showLineNumbers(self, value: bool) -> None:
        self._owner._show_line_numbers = value


__all__ = [
    "DiffRenderable",
    "LineColorConfig",
    "LineSign",
    "parse_patch",
]
