import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .markdown_blocks import _render_table, _strip_inline_formatting
from .markdown_parser import MarkedToken


class RenderNodeContext:
    def __init__(
        self,
        syntax_style: Any,
        conceal: bool,
        conceal_code: bool,
        tree_sitter_client: Any,
        default_render: Callable,
    ):
        self.syntax_style = syntax_style
        self.conceal = conceal
        self.conceal_code = conceal_code
        self.tree_sitter_client = tree_sitter_client
        self.default_render = default_render


@dataclass
class MarkdownTableOptions:
    width_mode: str = "full"
    column_fitter: str = "proportional"
    wrap_mode: str = "word"
    cell_padding: int = 0
    borders: bool = True
    outer_border: bool | None = None
    selectable: bool = True


def parse_table_options(
    value: dict[str, Any] | MarkdownTableOptions | None,
) -> MarkdownTableOptions:
    if isinstance(value, dict):
        d: dict[str, Any] = value
        return MarkdownTableOptions(
            width_mode=d.get("widthMode", d.get("width_mode", "full")),
            column_fitter=d.get("columnFitter", d.get("column_fitter", "proportional")),
            wrap_mode=d.get("wrapMode", d.get("wrap_mode", "word")),
            cell_padding=d.get("cellPadding", d.get("cell_padding", 0)),
            borders=d.get("borders", True),
            outer_border=d.get("outerBorder", d.get("outer_border")),
            selectable=d.get("selectable", True),
        )
    if isinstance(value, MarkdownTableOptions):
        return value
    return MarkdownTableOptions()


def should_render_separately(token: MarkedToken) -> bool:
    return token.type in ("code", "table", "blockquote")


def get_inter_block_margin(token: MarkedToken, has_next: bool) -> int:
    if not has_next:
        return 0
    return 1 if should_render_separately(token) else 0


def build_renderable_tokens(
    tokens: list[MarkedToken], *, has_custom_render_node: bool
) -> list[MarkedToken]:
    if has_custom_render_node:
        return [t for t in tokens if t.type != "space"]

    render_tokens: list[MarkedToken] = []
    markdown_raw = ""

    def flush() -> None:
        nonlocal markdown_raw
        if not markdown_raw:
            return
        normalized = re.sub(r"(?:\r?\n){2,}$", "\n", markdown_raw)
        if normalized:
            render_tokens.append(
                MarkedToken(
                    type="paragraph",
                    raw=normalized,
                    text=normalized,
                )
            )
        markdown_raw = ""

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.type == "space":
            if not markdown_raw:
                i += 1
                continue

            next_idx = i + 1
            while next_idx < len(tokens) and tokens[next_idx].type == "space":
                next_idx += 1

            next_token = tokens[next_idx] if next_idx < len(tokens) else None
            if next_token and not should_render_separately(next_token):
                markdown_raw += token.raw
            i += 1
            continue

        if should_render_separately(token):
            flush()
            render_tokens.append(token)
            i += 1
            continue

        markdown_raw += token.raw
        i += 1

    flush()
    return render_tokens


def process_text_line(line: str, *, conceal: bool) -> str:
    if conceal:
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            return _strip_inline_formatting(heading_match.group(2), True)

        return _strip_inline_formatting(line, True)
    return line


def render_token_lines(
    token: MarkedToken,
    *,
    conceal: bool,
) -> tuple[str, list[str]]:
    if token.type == "table":
        if token.rows:
            table_lines = _render_table(token.header, token.rows, conceal)
            return "table", table_lines
        return "text", token.raw.rstrip("\n").split("\n")

    if token.type == "code":
        code_text = token.text
        if code_text.endswith("\n"):
            code_text = code_text[:-1]
        return "code", code_text.split("\n") if code_text else []

    if token.type == "blockquote":
        lines = token.raw.rstrip("\n").split("\n")
        return "text", lines

    raw = token.raw.rstrip("\n")
    if not raw:
        return "text", []

    lines = raw.split("\n")
    return "text", [process_text_line(line, conceal=conceal) for line in lines]
