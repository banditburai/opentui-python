"""DiffRenderable - unified and split-view diff display."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .. import structs as s
from ..enums import RenderStrategy
from ..text_utils import wrap_text as _tu_wrap_text
from .base import Renderable
from .diff_parser import (
    LineColorConfig,
    LineSign,
    LogicalLine,
    StructuredPatch,
    parse_patch,
)
from .raster_cache import RasterCache

if TYPE_CHECKING:
    from ..renderer import Buffer


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
        # Adapter objects for CodeRenderable/LineNumberRenderable-like API
        "_left_code_adapter",
        "_right_code_adapter",
        "_left_line_num_adapter",
        "_right_line_num_adapter",
        # Retained raster cache
        "_raster",
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

        # Cached adapter renderables for event emission
        self._left_code_adapter: _DiffCodeAdapter | None = None
        self._right_code_adapter: _DiffCodeAdapter | None = None
        # Cached line number adapter renderables
        self._left_line_num_adapter: _DiffLineNumberAdapter | None = None
        self._right_line_num_adapter: _DiffLineNumberAdapter | None = None
        self._raster = RasterCache(f"diff-{self.id}")

        if self._diff_text:
            self._parse_diff()
            self._build_view()

    def get_render_strategy(self) -> RenderStrategy:
        """Diffs are heavy widgets that benefit from retained raster composition."""
        return RenderStrategy.HEAVY_WIDGET

    def mark_dirty(self) -> None:
        if hasattr(self, "_raster"):
            self._raster.invalidate()
        super().mark_dirty()

    def mark_paint_dirty(self) -> None:
        if hasattr(self, "_raster"):
            self._raster.invalidate()
        super().mark_paint_dirty()

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
            self._left_line_num_adapter = None
            self._right_line_num_adapter = None
            self._build_view()  # _build_view() already calls mark_dirty()

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
            self._build_view()  # _build_view() already calls mark_dirty()

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
            self.mark_paint_dirty()

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
        if self._left_code_adapter is None:
            self._left_code_adapter = _DiffCodeAdapter(self, "left")
        return self._left_code_adapter

    @property
    def right_code_renderable(self) -> Any:
        if self._right_code_adapter is None:
            self._right_code_adapter = _DiffCodeAdapter(self, "right")
        return self._right_code_adapter

    @property
    def left_side(self) -> Any:
        if self._parsed_diff and self._parsed_diff.hunks:
            if self._left_line_num_adapter is None:
                self._left_line_num_adapter = _DiffLineNumberAdapter(self, "left")
            return self._left_line_num_adapter
        return None

    @property
    def right_side(self) -> Any:
        if self._view_mode == "split" and self._parsed_diff and self._parsed_diff.hunks:
            if self._right_line_num_adapter is None:
                self._right_line_num_adapter = _DiffLineNumberAdapter(self, "right")
            return self._right_line_num_adapter
        return None

    # ── Diff parsing ────────────────────────────────────────────────────

    def _parse_diff(self) -> None:
        self._left_line_num_adapter = None
        self._right_line_num_adapter = None

        if not self._diff_text:
            self._parsed_diff = None
            self._parse_error = None
            return

        try:
            patches = parse_patch(self._diff_text)
            if not patches:
                self._parsed_diff = None
                self._parse_error = None
                return
            self._parsed_diff = patches[0]
            self._parse_error = None
        except Exception as e:
            self._parsed_diff = None
            self._parse_error = e

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
        if self._left_code_adapter is not None:
            self._left_code_adapter.emit("line-info-change")
        if self._right_code_adapter is not None:
            self._right_code_adapter.emit("line-info-change")

    def _build_error_view(self) -> None:
        self._unified_lines = []
        self._unified_line_colors = {}
        self._unified_line_signs = {}
        self._unified_line_numbers = {}

        self._unified_lines.append(f"Error parsing diff: {self._parse_error}")
        self._unified_lines.append("")
        self._unified_lines.extend(self._diff_text.split("\n"))

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

    def _render_diff_contents(self, buffer: Buffer) -> None:
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

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if not self._visible:
            return

        if self._render_before:
            self._render_before(buffer, delta_time, self)

        self._raster.render_cached(
            buffer,
            self._x,
            self._y,
            self._layout_width,
            self._layout_height,
            self._render_diff_contents,
        )

        if self._render_after:
            self._render_after(buffer, delta_time, self)

    def _render_error_view(self, buffer: Buffer, x: int, y: int, width: int, height: int) -> None:
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

        Delegates to ``text_utils.wrap_text`` which uses ``display_width()``
        for correct CJK/emoji handling.  Maps ``mode=None`` to ``wrap="none"``
        to preserve the original "return [text]" behavior.
        """
        return _tu_wrap_text(text, width, mode or "none")

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

        def _draw_side(
            buf: Buffer,
            vr: int,
            i: int,
            ly: int,
            rows: list[str],
            sx: int,
            cx: int,
            cw: int,
            gw: int,
            sw: int,
            cc: Any,
            line_nums: dict[int, int],
            signs: dict[int, Any],
            hide: set[int],
        ) -> None:
            if vr >= len(rows):
                return
            if cc and cc.gutter and self._show_line_numbers:
                buf.fill_rect(sx, ly, gw + sw + 1, 1, cc.gutter)
            if cc and cc.content:
                buf.fill_rect(cx, ly, cw, 1, cc.content)
            if vr == 0 and self._show_line_numbers and i not in hide:
                ln = line_nums.get(i)
                if ln is not None:
                    buf.draw_text(
                        str(ln).rjust(gw),
                        sx,
                        ly,
                        self._line_number_fg_color,
                        cc.gutter if cc else None,
                    )
            if vr == 0 and self._show_line_numbers:
                s = signs.get(i)
                if s and s.after:
                    buf.draw_text(s.after, sx + gw, ly, s.after_color, cc.gutter if cc else None)
            if cw > 0:
                buf.draw_text(
                    rows[vr], cx, ly, self._diff_fg, cc.content if cc else self._background_color
                )

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
                _draw_side(
                    buffer,
                    vr,
                    i,
                    ly,
                    lw,
                    x,
                    l_cx,
                    left_cw,
                    l_gw,
                    l_sw,
                    l_cc,
                    self._left_line_numbers,
                    self._left_line_signs,
                    l_hide,
                )
                _draw_side(
                    buffer,
                    vr,
                    i,
                    ly,
                    rw,
                    x + half_width,
                    r_cx,
                    right_cw,
                    r_gw,
                    r_sw,
                    r_cc,
                    self._right_line_numbers,
                    self._right_line_signs,
                    r_hide,
                )
                visual_row += 1

    # ── Destroy ─────────────────────────────────────────────────────────

    def destroy(self) -> None:
        """Release retained raster resources before normal teardown."""
        self._raster.release()
        super().destroy()


class _DiffCodeAdapter:
    """Adapter providing CodeRenderable-like API for DiffRenderable's left/right panes."""

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


class _DiffLineNumberAdapter:
    """Adapter providing LineNumberRenderable-like API for DiffRenderable's left/right panes."""

    def __init__(self, owner: DiffRenderable, side: str):
        self._owner = owner
        self._side = side

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
