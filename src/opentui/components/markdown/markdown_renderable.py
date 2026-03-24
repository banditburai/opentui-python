from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...enums import RenderStrategy
from ..base import Renderable
from .markdown_blocks import (
    BlockState,
    _ExternalBlockRenderable,
    _MarkdownBlockRenderable,
    _MarkdownCodeBlock,
    _MarkdownTableBlock,
)
from .markdown_parser import MarkedToken, ParseState, parse_markdown_incremental
from .markdown_renderable_blocks import (
    apply_table_options,
    create_code_renderable,
    create_markdown_text_renderable,
    create_table_renderable,
    update_table_renderable,
)
from .markdown_renderable_planning import (
    MarkdownTableOptions,
    RenderNodeContext,
    build_renderable_tokens,
    get_inter_block_margin,
    parse_table_options,
    render_token_lines,
)

if TYPE_CHECKING:
    from ...renderer import Buffer


class MarkdownRenderable(Renderable):
    """Renders markdown content as terminal output.

    Parses markdown incrementally, creating child renderables for each
    block: tables become _MarkdownTableBlock, code blocks become
    _MarkdownCodeBlock, and text blocks become _MarkdownCodeBlock with filetype="markdown".

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

        self._table_options = parse_table_options(table_options)

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
        self._table_options = parse_table_options(value)
        self._apply_table_options_to_blocks()

    # Internal state accessors for tests
    @property
    def _blockStates(self) -> list[BlockState]:
        """Alias for tests that access _blockStates."""
        return self._block_states

    # -- Public methods --

    def clear_cache(self) -> None:
        self._parse_state = None
        self._clear_block_states()
        self._update_blocks()
        self.mark_dirty()

    # -- Private methods --

    def _apply_table_options_to_blocks(self) -> None:
        for state in self._block_states:
            if isinstance(state.renderable, _MarkdownTableBlock):
                apply_table_options(state.renderable, self._table_options)
        self.mark_dirty()

    def _clear_block_states(self) -> None:
        for state in self._block_states:
            state.renderable.destroy()
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

        block_tokens = build_renderable_tokens(
            tokens, has_custom_render_node=self._render_node is not None
        )
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
                existing.renderable.destroy()

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
            removed.renderable.destroy()

    def _create_block_renderable(
        self,
        token: MarkedToken,
        index: int,
        has_next: bool,
    ) -> Renderable | None:
        block_id = f"{self._id}-block-{index}"
        margin_bottom = get_inter_block_margin(token, has_next)

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
                if isinstance(
                    custom,
                    _MarkdownBlockRenderable | _MarkdownCodeBlock | _MarkdownTableBlock,
                ):
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
        margin_bottom = get_inter_block_margin(token, has_next)

        if token.type == "table":
            if token.rows:
                return create_table_renderable(
                    token,
                    block_id=block_id,
                    conceal=self._conceal,
                    margin_bottom=margin_bottom,
                    table_options=self._table_options,
                )
            return create_markdown_text_renderable(
                token.raw,
                block_id=block_id,
                conceal=self._conceal,
                margin_bottom=margin_bottom,
            )

        if token.type == "code":
            return create_code_renderable(token, block_id=block_id, margin_bottom=margin_bottom)

        if token.type == "space":
            return None

        if not token.raw:
            return None

        return create_markdown_text_renderable(
            token.raw,
            block_id=block_id,
            conceal=self._conceal,
            margin_bottom=margin_bottom,
        )

    def _update_existing_block(
        self,
        state: BlockState,
        token: MarkedToken,
        index: int,
        has_next: bool,
    ) -> None:
        margin_bottom = get_inter_block_margin(token, has_next)

        if (
            token.type == "table"
            and isinstance(state.renderable, _MarkdownTableBlock)
            and token.rows
        ):
            update_table_renderable(
                state.renderable,
                token,
                conceal=self._conceal,
                margin_bottom=margin_bottom,
                table_options=self._table_options,
            )
            return

        _, lines = render_token_lines(token, conceal=self._conceal)
        state.renderable.update_lines(lines, margin_bottom)

    def _rerender_blocks(self) -> None:
        for i, state in enumerate(self._block_states):
            has_next = i < len(self._block_states) - 1
            token = state.token
            margin_bottom = get_inter_block_margin(token, has_next)

            if (
                token.type == "table"
                and isinstance(state.renderable, _MarkdownTableBlock)
                and token.rows
            ):
                update_table_renderable(
                    state.renderable,
                    token,
                    conceal=self._conceal,
                    margin_bottom=margin_bottom,
                    table_options=self._table_options,
                )
                continue

            if token.type == "code":
                # Code blocks don't change with conceal (unless concealCode)
                state.renderable.margin_bottom = margin_bottom
                continue

            _, lines = render_token_lines(token, conceal=self._conceal)
            state.renderable.update_lines(lines, margin_bottom)

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        if self._style_dirty:
            self._style_dirty = False
            self._rerender_blocks()

        super().render(buffer, delta_time)
