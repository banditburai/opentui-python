"""MarkdownRenderable - renders parsed markdown as terminal output."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..enums import RenderStrategy
from ..markdown_parser import MarkedToken, ParseState, parse_markdown_incremental
from .base import Renderable
from .markdown_blocks import (
    BlockState,
    CodeRenderable,
    TextTableRenderable,
    _ExternalBlockRenderable,
    _MarkdownBlockRenderable,
    _render_table,
    _strip_inline_formatting,
    _strip_table_cell,
)

if TYPE_CHECKING:
    from ..renderer import Buffer


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
    border_style: str = "single"
    border_color: str = "#888888"
    selectable: bool = True


class MarkdownRenderable(Renderable):
    """Renders markdown content as terminal output.

    Parses markdown incrementally, creating child renderables for each
    block: tables become TextTableRenderable, code blocks become
    CodeRenderable, and text blocks become CodeRenderable with filetype="markdown".

    Supports concealment of inline formatting markers, streaming mode
    for incremental content updates, and custom render node callbacks.
    """

    def __init__(
        self,
        *,
        content: str = "",
        syntax_style: Any = None,
        conceal: bool = True,
        conceal_code: bool = False,
        tree_sitter_client: Any = None,
        streaming: bool = False,
        table_options: dict | MarkdownTableOptions | None = None,
        render_node: Callable | None = None,
        **kwargs,
    ):
        super().__init__(flex_direction="column", **kwargs)

        self._content = content
        self._syntax_style = syntax_style
        self._conceal = conceal
        self._conceal_code = conceal_code
        self._tree_sitter_client = tree_sitter_client
        self._streaming = streaming
        self._render_node = render_node
        self._style_dirty = False

        if isinstance(table_options, dict):
            self._table_options = MarkdownTableOptions(
                width_mode=table_options.get("widthMode", table_options.get("width_mode", "full")),
                column_fitter=table_options.get(
                    "columnFitter", table_options.get("column_fitter", "proportional")
                ),
                wrap_mode=table_options.get("wrapMode", table_options.get("wrap_mode", "word")),
                cell_padding=table_options.get("cellPadding", table_options.get("cell_padding", 0)),
                borders=table_options.get("borders", True),
                selectable=table_options.get("selectable", True),
            )
        elif isinstance(table_options, MarkdownTableOptions):
            self._table_options = table_options
        else:
            self._table_options = MarkdownTableOptions()

        self._parse_state: ParseState | None = None
        self._block_states: list[BlockState] = []

        self._update_blocks()

    def get_render_strategy(self) -> RenderStrategy:
        return RenderStrategy.HEAVY_WIDGET

    # -- Public properties --

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str) -> None:
        if self.is_destroyed:
            return
        if self._content != value:
            self._content = value
            self._update_blocks()
            self.mark_dirty()

    @property
    def syntax_style(self) -> Any:
        return self._syntax_style

    @syntax_style.setter
    def syntax_style(self, value: Any) -> None:
        if self._syntax_style is not value:
            self._syntax_style = value
            self._style_dirty = True
            self.mark_paint_dirty()

    @property
    def conceal(self) -> bool:
        return self._conceal

    @conceal.setter
    def conceal(self, value: bool) -> None:
        if self._conceal != value:
            self._conceal = value
            self._style_dirty = True
            self.mark_paint_dirty()

    @property
    def conceal_code(self) -> bool:
        return self._conceal_code

    @conceal_code.setter
    def conceal_code(self, value: bool) -> None:
        if self._conceal_code != value:
            self._conceal_code = value
            self._style_dirty = True
            self.mark_paint_dirty()

    @property
    def streaming(self) -> bool:
        return self._streaming

    @streaming.setter
    def streaming(self, value: bool) -> None:
        if self.is_destroyed:
            return
        if self._streaming != value:
            self._streaming = value
            self._update_blocks(force_table_refresh=True)

    @property
    def table_options(self) -> MarkdownTableOptions:
        return self._table_options

    @table_options.setter
    def table_options(self, value: dict | MarkdownTableOptions) -> None:
        if isinstance(value, dict):
            self._table_options = MarkdownTableOptions(
                width_mode=value.get("widthMode", value.get("width_mode", "full")),
                column_fitter=value.get("columnFitter", value.get("column_fitter", "proportional")),
                wrap_mode=value.get("wrapMode", value.get("wrap_mode", "word")),
                cell_padding=value.get("cellPadding", value.get("cell_padding", 0)),
                borders=value.get("borders", True),
                selectable=value.get("selectable", True),
            )
        else:
            self._table_options = value
        self._apply_table_options_to_blocks()

    # Internal state accessors for tests
    @property
    def _blockStates(self) -> list[BlockState]:
        """Alias for tests that access _blockStates."""
        return self._block_states

    @property
    def _parseState(self) -> ParseState | None:
        """Alias for tests that access _parseState."""
        return self._parse_state

    # -- Public methods --

    def clear_cache(self) -> None:
        self._parse_state = None
        self._clear_block_states()
        self._update_blocks()
        self.mark_dirty()

    # -- Private methods --

    def _should_render_separately(self, token: MarkedToken) -> bool:
        return token.type in ("code", "table", "blockquote")

    def _get_inter_block_margin(self, token: MarkedToken, has_next: bool) -> int:
        if not has_next:
            return 0
        return 1 if self._should_render_separately(token) else 0

    def _build_renderable_tokens(self, tokens: list[MarkedToken]) -> list[MarkedToken]:
        """Group tokens into renderable blocks.

        When no custom renderNode is set, non-separately-rendered tokens
        (headings, paragraphs, lists, hr) are merged into single markdown
        text blocks. Spacing tokens between them are absorbed.
        """
        if self._render_node:
            return [t for t in tokens if t.type != "space"]

        render_tokens: list[MarkedToken] = []
        markdown_raw = ""

        def flush():
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
                if next_token and not self._should_render_separately(next_token):
                    markdown_raw += token.raw
                i += 1
                continue

            if self._should_render_separately(token):
                flush()
                render_tokens.append(token)
                i += 1
                continue

            markdown_raw += token.raw
            i += 1

        flush()
        return render_tokens

    def _render_token_lines(
        self, token: MarkedToken, margin_bottom: int = 0
    ) -> tuple[str, list[str]]:
        if token.type == "table":
            if token.rows:
                table_lines = _render_table(token.header, token.rows, self._conceal)
                return "table", table_lines
            else:
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
        return "text", [self._process_text_line(line) for line in lines]

    def _process_text_line(self, line: str) -> str:
        if self._conceal:
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if heading_match:
                return _strip_inline_formatting(heading_match.group(2), True)

            return _strip_inline_formatting(line, True)
        return line

    def _create_table_renderable(
        self,
        token: MarkedToken,
        block_id: str,
        margin_bottom: int = 0,
    ) -> TextTableRenderable:
        table_lines = _render_table(token.header, token.rows, self._conceal)

        num_cols = len(token.header)
        table_content: list[list[list[dict[str, str]]]] = []

        header_row: list[list[dict[str, str]]] = []
        for h in token.header:
            text = _strip_table_cell(h.get("text", ""), self._conceal)
            header_row.append([{"text": text}])
        table_content.append(header_row)

        for row in token.rows:
            data_row: list[list[dict[str, str]]] = []
            for i in range(num_cols):
                if i < len(row):
                    text = _strip_table_cell(row[i].get("text", ""), self._conceal)
                    data_row.append([{"text": text}])
                else:
                    data_row.append([{"text": ""}])
            table_content.append(data_row)

        renderable = TextTableRenderable(
            id=block_id,
            block_type="table",
            lines=table_lines,
            margin_bottom=margin_bottom,
        )
        renderable.content = table_content
        renderable.column_width_mode = self._table_options.width_mode
        renderable.column_fitter = self._table_options.column_fitter
        renderable.wrap_mode = self._table_options.wrap_mode
        renderable.cell_padding = self._table_options.cell_padding
        renderable.show_borders = self._table_options.borders
        renderable._border_val = self._table_options.borders
        renderable._outer_border = (
            self._table_options.outer_border
            if self._table_options.outer_border is not None
            else self._table_options.borders
        )
        renderable.selectable = self._table_options.selectable

        return renderable

    def _create_code_renderable(
        self,
        token: MarkedToken,
        block_id: str,
        margin_bottom: int = 0,
    ) -> CodeRenderable:
        code_text = token.text
        if code_text.endswith("\n"):
            code_text = code_text[:-1]
        lines = code_text.split("\n") if code_text else []

        return CodeRenderable(
            id=block_id,
            block_type="code",
            lines=lines,
            margin_bottom=margin_bottom,
            filetype=token.lang or "",
        )

    def _create_markdown_text_renderable(
        self,
        raw: str,
        block_id: str,
        margin_bottom: int = 0,
    ) -> CodeRenderable:
        raw_stripped = raw.rstrip("\n")
        if not raw_stripped:
            return CodeRenderable(
                id=block_id,
                block_type="text",
                lines=[],
                margin_bottom=margin_bottom,
                filetype="markdown",
            )

        lines = raw_stripped.split("\n")
        processed_lines = [self._process_text_line(line) for line in lines]

        return CodeRenderable(
            id=block_id,
            block_type="text",
            lines=processed_lines,
            margin_bottom=margin_bottom,
            filetype="markdown",
        )

    def _update_table_renderable(
        self,
        renderable: TextTableRenderable,
        token: MarkedToken,
        margin_bottom: int = 0,
    ) -> None:
        """Update an existing table renderable with new token data.

        Reuses cell chunk list objects when their content hasn't changed,
        so that identity-based stability checks pass (``cell is old_cell``).
        """
        table_lines = _render_table(token.header, token.rows, self._conceal)

        old_content = renderable.content if renderable.content else []

        num_cols = len(token.header)
        table_content: list[list[list[dict[str, str]]]] = []

        header_row: list[list[dict[str, str]]] = []
        for col_idx, h in enumerate(token.header):
            text = _strip_table_cell(h.get("text", ""), self._conceal)
            new_chunk = [{"text": text}]
            if (
                old_content
                and col_idx < len(old_content[0])
                and old_content[0][col_idx] == new_chunk
            ):
                header_row.append(old_content[0][col_idx])
            else:
                header_row.append(new_chunk)
        table_content.append(header_row)

        for row_idx, row in enumerate(token.rows):
            data_row: list[list[dict[str, str]]] = []
            old_row_idx = row_idx + 1  # +1 for header
            for i in range(num_cols):
                if i < len(row):
                    text = _strip_table_cell(row[i].get("text", ""), self._conceal)
                    new_chunk = [{"text": text}]
                else:
                    new_chunk = [{"text": ""}]
                if (
                    old_row_idx < len(old_content)
                    and i < len(old_content[old_row_idx])
                    and old_content[old_row_idx][i] == new_chunk
                ):
                    data_row.append(old_content[old_row_idx][i])
                else:
                    data_row.append(new_chunk)
            table_content.append(data_row)

        renderable.content = table_content
        renderable.update_lines(table_lines, margin_bottom)
        renderable.column_width_mode = self._table_options.width_mode
        renderable.column_fitter = self._table_options.column_fitter

    def _apply_table_options_to_blocks(self) -> None:
        for state in self._block_states:
            if isinstance(state.renderable, TextTableRenderable):
                state.renderable.column_width_mode = self._table_options.width_mode
                state.renderable.column_fitter = self._table_options.column_fitter
                state.renderable.wrap_mode = self._table_options.wrap_mode
                state.renderable.cell_padding = self._table_options.cell_padding
                state.renderable._border_val = self._table_options.borders
                state.renderable._outer_border = (
                    self._table_options.outer_border
                    if self._table_options.outer_border is not None
                    else self._table_options.borders
                )
                state.renderable.show_borders = self._table_options.borders
                state.renderable.selectable = self._table_options.selectable
        self.mark_dirty()

    def _clear_block_states(self) -> None:
        for state in self._block_states:
            state.renderable.destroy_recursively()
        self._block_states = []

    def _update_blocks(self, force_table_refresh: bool = False) -> None:
        if self.is_destroyed:
            return

        if not self._content:
            self._clear_block_states()
            self._parse_state = None
            return

        trailing_unstable = 2 if self._streaming else 0
        self._parse_state = parse_markdown_incremental(
            self._content, self._parse_state, trailing_unstable
        )

        tokens = self._parse_state.tokens
        if not tokens and self._content:
            # Parse failure - fallback
            self._clear_block_states()
            fallback = self._create_markdown_text_renderable(self._content, f"{self._id}-fallback")
            self.add(fallback)
            self._block_states = [
                BlockState(
                    token=MarkedToken(type="text", raw=self._content, text=self._content),
                    token_raw=self._content,
                    renderable=fallback,
                )
            ]
            return

        block_tokens = self._build_renderable_tokens(tokens)
        last_block_index = len(block_tokens) - 1

        block_index = 0
        for i, token in enumerate(block_tokens):
            has_next = i < last_block_index
            existing = (
                self._block_states[block_index] if block_index < len(self._block_states) else None
            )

            # Same token object reference = unchanged
            if existing and existing.token is token:
                if force_table_refresh:
                    self._update_existing_block(existing, token, block_index, has_next)
                block_index += 1
                continue

            # Same raw content and type
            if existing and existing.token_raw == token.raw and existing.token.type == token.type:
                existing.token = token
                if force_table_refresh:
                    self._update_existing_block(existing, token, block_index, has_next)
                block_index += 1
                continue

            # Same type, different content - update in place
            if existing and existing.token.type == token.type:
                self._update_existing_block(existing, token, block_index, has_next)
                existing.token = token
                existing.token_raw = token.raw
                block_index += 1
                continue

            # Different type or new block
            if existing:
                existing.renderable.destroy_recursively()

            renderable = self._create_block_renderable(token, block_index, has_next)
            if renderable:
                self.add(renderable)

                if block_index < len(self._block_states):
                    self._block_states[block_index] = BlockState(
                        token=token,
                        token_raw=token.raw,
                        renderable=renderable,
                    )
                else:
                    self._block_states.append(
                        BlockState(
                            token=token,
                            token_raw=token.raw,
                            renderable=renderable,
                        )
                    )
            block_index += 1

        while len(self._block_states) > block_index:
            removed = self._block_states.pop()
            removed.renderable.destroy_recursively()

    def _create_block_renderable(
        self,
        token: MarkedToken,
        index: int,
        has_next: bool,
    ) -> Renderable | None:
        block_id = f"{self._id}-block-{index}"
        margin_bottom = self._get_inter_block_margin(token, has_next)

        if self._render_node:
            ctx = RenderNodeContext(
                syntax_style=self._syntax_style,
                conceal=self._conceal,
                conceal_code=self._conceal_code,
                tree_sitter_client=self._tree_sitter_client,
                default_render=lambda: self._create_default_renderable(token, index, has_next),
            )
            custom = self._render_node(token, ctx)
            if custom is not None:
                if isinstance(custom, _MarkdownBlockRenderable | CodeRenderable):
                    return custom
                return _ExternalBlockRenderable(
                    child=custom,
                    id=block_id,
                    margin_bottom=margin_bottom,
                )

        return self._create_default_renderable(token, index, has_next)

    def _create_default_renderable(
        self,
        token: MarkedToken,
        index: int,
        has_next: bool,
    ) -> Renderable | None:
        block_id = f"{self._id}-block-{index}"
        margin_bottom = self._get_inter_block_margin(token, has_next)

        if token.type == "table":
            if token.rows:
                return self._create_table_renderable(token, block_id, margin_bottom)
            else:
                # Table with no data rows - show raw
                return self._create_markdown_text_renderable(token.raw, block_id, margin_bottom)

        if token.type == "code":
            return self._create_code_renderable(token, block_id, margin_bottom)

        if token.type == "space":
            return None

        if not token.raw:
            return None

        return self._create_markdown_text_renderable(token.raw, block_id, margin_bottom)

    def _update_existing_block(
        self,
        state: BlockState,
        token: MarkedToken,
        index: int,
        has_next: bool,
    ) -> None:
        margin_bottom = self._get_inter_block_margin(token, has_next)

        if (
            token.type == "table"
            and isinstance(state.renderable, TextTableRenderable)
            and token.rows
        ):
            self._update_table_renderable(state.renderable, token, margin_bottom)
            return

        block_type, lines = self._render_token_lines(token, margin_bottom)
        state.renderable.update_lines(lines, margin_bottom)

    def _rerender_blocks(self) -> None:
        for i, state in enumerate(self._block_states):
            has_next = i < len(self._block_states) - 1
            token = state.token
            margin_bottom = self._get_inter_block_margin(token, has_next)

            if (
                token.type == "table"
                and isinstance(state.renderable, TextTableRenderable)
                and token.rows
            ):
                self._update_table_renderable(state.renderable, token, margin_bottom)
                continue

            if token.type == "code":
                # Code blocks don't change with conceal (unless concealCode)
                state.renderable.margin_bottom = margin_bottom
                continue

            block_type, lines = self._render_token_lines(token, margin_bottom)
            state.renderable.update_lines(lines, margin_bottom)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if self._style_dirty:
            self._style_dirty = False
            self._rerender_blocks()

        super().render(buffer, delta_time)
