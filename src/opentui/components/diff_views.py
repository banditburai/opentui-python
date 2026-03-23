from __future__ import annotations

from .diff_parser import LogicalLine
from .line_types import LineColorConfig, LineSign


def build_error_view_lines(parse_error, diff_text: str) -> list[str]:
    return [f"Error parsing diff: {parse_error}", "", *diff_text.split("\n")]


def build_unified_view_data(owner) -> tuple[list[str], dict[int, LineColorConfig], dict[int, LineSign], dict[int, int]]:
    if not owner._parsed_diff:
        return [], {}, {}, {}

    content_lines: list[str] = []
    line_colors: dict[int, LineColorConfig] = {}
    line_signs: dict[int, LineSign] = {}
    line_numbers: dict[int, int] = {}
    line_index = 0

    for hunk in owner._parsed_diff.hunks:
        old_line_num = hunk.old_start
        new_line_num = hunk.new_start

        for line in hunk.lines:
            if not line:
                continue
            first_char = line[0]
            content = line[1:]

            if first_char == "+":
                content_lines.append(content)
                line_colors[line_index] = LineColorConfig(
                    gutter=owner._added_line_number_bg,
                    content=owner._added_content_bg if owner._added_content_bg else owner._added_bg,
                )
                line_signs[line_index] = LineSign(after=" +", after_color=owner._added_sign_color)
                line_numbers[line_index] = new_line_num
                new_line_num += 1
                line_index += 1
            elif first_char == "-":
                content_lines.append(content)
                line_colors[line_index] = LineColorConfig(
                    gutter=owner._removed_line_number_bg,
                    content=owner._removed_content_bg if owner._removed_content_bg else owner._removed_bg,
                )
                line_signs[line_index] = LineSign(after=" -", after_color=owner._removed_sign_color)
                line_numbers[line_index] = old_line_num
                old_line_num += 1
                line_index += 1
            elif first_char == " ":
                content_lines.append(content)
                line_colors[line_index] = LineColorConfig(
                    gutter=owner._line_number_bg_color,
                    content=owner._context_content_bg if owner._context_content_bg else owner._context_bg,
                )
                line_numbers[line_index] = new_line_num
                old_line_num += 1
                new_line_num += 1
                line_index += 1

    return content_lines, line_colors, line_signs, line_numbers


def build_split_view_data(owner) -> tuple[
    list[str],
    list[str],
    dict[int, LineColorConfig],
    dict[int, LineColorConfig],
    dict[int, LineSign],
    dict[int, LineSign],
    dict[int, int],
    dict[int, int],
    set[int],
    set[int],
]:
    if not owner._parsed_diff:
        return [], [], {}, {}, {}, {}, {}, {}, set(), set()

    left_logical: list[LogicalLine] = []
    right_logical: list[LogicalLine] = []

    for hunk in owner._parsed_diff.hunks:
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
                    LogicalLine(content=content, line_num=old_line_num, color=owner._context_bg, line_type="context")
                )
                right_logical.append(
                    LogicalLine(content=content, line_num=new_line_num, color=owner._context_bg, line_type="context")
                )
                old_line_num += 1
                new_line_num += 1
                i += 1
            elif first_char == "\\":
                i += 1
            else:
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
                                color=owner._removed_bg,
                                sign=LineSign(after=" -", after_color=owner._removed_sign_color),
                                line_type="remove",
                            )
                        )
                    else:
                        left_logical.append(LogicalLine(content="", hide_line_number=True, line_type="empty"))

                    if j < len(adds):
                        right_logical.append(
                            LogicalLine(
                                content=adds[j][0],
                                line_num=adds[j][1],
                                color=owner._added_bg,
                                sign=LineSign(after=" +", after_color=owner._added_sign_color),
                                line_type="add",
                            )
                        )
                    else:
                        right_logical.append(LogicalLine(content="", hide_line_number=True, line_type="empty"))

    left_lines = [ll.content for ll in left_logical]
    right_lines = [ll.content for ll in right_logical]
    left_line_colors: dict[int, LineColorConfig] = {}
    right_line_colors: dict[int, LineColorConfig] = {}
    left_line_signs: dict[int, LineSign] = {}
    right_line_signs: dict[int, LineSign] = {}
    left_line_numbers: dict[int, int] = {}
    right_line_numbers: dict[int, int] = {}
    left_hide_line_numbers: set[int] = set()
    right_hide_line_numbers: set[int] = set()

    for idx, ll in enumerate(left_logical):
        if ll.line_num is not None:
            left_line_numbers[idx] = ll.line_num
        if ll.hide_line_number:
            left_hide_line_numbers.add(idx)
        if ll.line_type == "remove":
            left_line_colors[idx] = LineColorConfig(
                gutter=owner._removed_line_number_bg,
                content=owner._removed_content_bg if owner._removed_content_bg else owner._removed_bg,
            )
        elif ll.line_type == "context":
            left_line_colors[idx] = LineColorConfig(
                gutter=owner._line_number_bg_color,
                content=owner._context_content_bg if owner._context_content_bg else owner._context_bg,
            )
        if ll.sign:
            left_line_signs[idx] = ll.sign

    for idx, ll in enumerate(right_logical):
        if ll.line_num is not None:
            right_line_numbers[idx] = ll.line_num
        if ll.hide_line_number:
            right_hide_line_numbers.add(idx)
        if ll.line_type == "add":
            right_line_colors[idx] = LineColorConfig(
                gutter=owner._added_line_number_bg,
                content=owner._added_content_bg if owner._added_content_bg else owner._added_bg,
            )
        elif ll.line_type == "context":
            right_line_colors[idx] = LineColorConfig(
                gutter=owner._line_number_bg_color,
                content=owner._context_content_bg if owner._context_content_bg else owner._context_bg,
            )
        if ll.sign:
            right_line_signs[idx] = ll.sign

    return (
        left_lines,
        right_lines,
        left_line_colors,
        right_line_colors,
        left_line_signs,
        right_line_signs,
        left_line_numbers,
        right_line_numbers,
        left_hide_line_numbers,
        right_hide_line_numbers,
    )


__all__ = ["build_error_view_lines", "build_split_view_data", "build_unified_view_data"]
