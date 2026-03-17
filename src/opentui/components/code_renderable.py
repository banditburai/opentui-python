"""CodeRenderable - syntax-highlighted code display component.

Code block component with syntax highlighting via Tree-sitter.
Renders code with optional syntax highlighting via a pluggable tree-sitter
client interface. Supports streaming mode, concealment, draw modes, and
onHighlight/onChunks callbacks.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import structs as s
from .text_renderable import TextRenderable

if TYPE_CHECKING:
    from ..renderer import Buffer


# ---------------------------------------------------------------------------
# SimpleHighlight type  (tuple: [start, end, group, meta?])
# ---------------------------------------------------------------------------

# A SimpleHighlight is a tuple of (start_offset, end_offset, group_name, optional_meta).
# In Python we represent it as a tuple or list.
SimpleHighlight = list  # [int, int, str] or [int, int, str, dict]


# ---------------------------------------------------------------------------
# SyntaxStyle
# ---------------------------------------------------------------------------


@dataclass
class StyleDefinition:
    fg: s.RGBA | None = None
    bg: s.RGBA | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    dim: bool = False


class SyntaxStyle:
    """Manages syntax highlight style mappings.

    Maps group names (e.g. 'keyword', 'string') to style definitions.
    Provides style lookup with fallback to base scope names.
    """

    def __init__(self) -> None:
        self._styles: dict[str, StyleDefinition] = {}
        self._style_ids: dict[str, int] = {}
        self._next_id = 1

    @classmethod
    def from_styles(cls, styles: dict[str, dict]) -> SyntaxStyle:
        """Create a SyntaxStyle from a dict of style definitions.

        Args:
            styles: Maps group names to dicts with optional keys: fg, bg, bold, italic, etc.
        """
        ss = cls()
        for name, style_def in styles.items():
            sd = StyleDefinition()
            if "fg" in style_def:
                sd.fg = style_def["fg"]
            if "bg" in style_def:
                sd.bg = style_def["bg"]
            if "bold" in style_def:
                sd.bold = style_def["bold"]
            if "italic" in style_def:
                sd.italic = style_def["italic"]
            if "underline" in style_def:
                sd.underline = style_def["underline"]
            if "dim" in style_def:
                sd.dim = style_def["dim"]
            ss.register_style(name, sd)
        return ss

    def register_style(self, name: str, style: StyleDefinition) -> int:
        """Register a style and return its ID."""
        self._styles[name] = style
        if name not in self._style_ids:
            self._style_ids[name] = self._next_id
            self._next_id += 1
        return self._style_ids[name]

    def get_style(self, name: str) -> StyleDefinition | None:
        """Get a style by name, with fallback to base scope."""
        style = self._styles.get(name)
        if style is not None:
            return style
        # Fallback: try base scope (e.g., "markup" from "markup.heading.1")
        if "." in name:
            base = name.split(".", maxsplit=1)[0]
            return self._styles.get(base)
        return None

    def get_style_id(self, name: str) -> int:
        """Get the numeric ID for a style name."""
        if name not in self._style_ids:
            self._style_ids[name] = self._next_id
            self._next_id += 1
        return self._style_ids[name]


# ---------------------------------------------------------------------------
# TextChunk (simplified)
# ---------------------------------------------------------------------------


@dataclass
class TextChunk:
    """A chunk of styled text."""

    text: str
    fg: s.RGBA | None = None
    bg: s.RGBA | None = None
    attributes: int = 0


# ---------------------------------------------------------------------------
# LineHighlight (returned by getLineHighlights)
# ---------------------------------------------------------------------------


@dataclass
class LineHighlight:
    """A highlight span within a single line."""

    start: int
    end: int
    style_id: int


# ---------------------------------------------------------------------------
# TreeSitterClient interface
# ---------------------------------------------------------------------------


class TreeSitterClient:
    """Base tree-sitter client interface.

    Production implementations would communicate with a tree-sitter worker.
    For testing, use MockTreeSitterClient.

    The highlight pipeline has two phases:
    1. ``start_highlight_once`` (synchronous) - creates a pending request
    2. ``await`` the returned awaitable to get the result

    ``highlight_once`` is the async convenience wrapper that does both.
    """

    def __init__(self, options: dict | None = None) -> None:
        self._options = options or {}

    def start_highlight_once(
        self,
        content: str,
        filetype: str,
    ) -> asyncio.Future:
        """Synchronously create a highlight request and return a future.

        The default implementation returns an already-resolved future.
        Override in subclasses to provide real async behavior.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        future = loop.create_future()
        future.set_result({"highlights": []})
        return future

    async def highlight_once(
        self,
        content: str,
        filetype: str,
    ) -> dict:
        """Highlight content and return result dict.

        Returns:
            {"highlights": [...], "warning": str|None, "error": str|None}
        """
        return await self.start_highlight_once(content, filetype)

    async def initialize(self) -> None:
        """Initialize the client (no-op in base)."""

    async def preload_parser(self, filetype: str) -> None:
        """Preload parser for a filetype (no-op in base)."""


# ---------------------------------------------------------------------------
# MockTreeSitterClient
# ---------------------------------------------------------------------------


class MockTreeSitterClient(TreeSitterClient):
    """Mock tree-sitter client for testing.

    Queues highlight requests as
    pending futures that can be resolved manually or auto-resolved after
    a timeout.

    Key design: ``start_highlight_once`` is synchronous - it creates the
    future and appends to the pending list immediately. This mirrors JS
    Promise behavior where the executor runs synchronously.
    """

    def __init__(self, options: dict | None = None) -> None:
        super().__init__(options)
        self._highlight_futures: list[dict] = []
        self._mock_result: dict = {"highlights": []}
        self._auto_resolve_timeout: float | None = None
        if options and "autoResolveTimeout" in options:
            self._auto_resolve_timeout = options["autoResolveTimeout"] / 1000.0

    def set_mock_result(self, result: dict) -> None:
        """Set the result that will be returned when highlights are resolved."""
        self._mock_result = result

    def start_highlight_once(self, content: str, filetype: str) -> asyncio.Future:
        """Synchronously create a pending highlight request.

        Returns an asyncio.Future that will be resolved when
        resolve_highlight_once() or resolve_all_highlight_once() is called.
        This is synchronous so that is_highlighting() returns True immediately.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        future = loop.create_future()
        entry = {"future": future, "content": content, "filetype": filetype}
        self._highlight_futures.append(entry)

        if self._auto_resolve_timeout is not None:
            timeout = self._auto_resolve_timeout

            async def _auto_resolve():
                await asyncio.sleep(timeout)
                if entry in self._highlight_futures:
                    if not future.done():
                        future.set_result(dict(self._mock_result))
                    with contextlib.suppress(ValueError):
                        self._highlight_futures.remove(entry)

            asyncio.ensure_future(_auto_resolve())

        return future

    async def highlight_once(self, content: str, filetype: str) -> dict:
        """Queue a highlight request and await the result."""
        return await self.start_highlight_once(content, filetype)

    def resolve_highlight_once(self, index: int = 0) -> None:
        """Resolve a pending highlight at the given index."""
        if 0 <= index < len(self._highlight_futures):
            entry = self._highlight_futures[index]
            future = entry["future"]
            if not future.done():
                future.set_result(dict(self._mock_result))
            self._highlight_futures.pop(index)

    def resolve_all_highlight_once(self) -> None:
        """Resolve all pending highlights."""
        for entry in self._highlight_futures:
            future = entry["future"]
            if not future.done():
                future.set_result(dict(self._mock_result))
        self._highlight_futures.clear()

    def is_highlighting(self) -> bool:
        """Check if there are pending highlight requests."""
        return len(self._highlight_futures) > 0


# ---------------------------------------------------------------------------
# Highlight context types
# ---------------------------------------------------------------------------


@dataclass
class HighlightContext:
    content: str
    filetype: str
    syntax_style: SyntaxStyle


@dataclass
class ChunkRenderContext:
    content: str
    filetype: str
    syntax_style: SyntaxStyle
    highlights: list


# ---------------------------------------------------------------------------
# tree_sitter_to_text_chunks - convert highlights to TextChunks
# ---------------------------------------------------------------------------


def tree_sitter_to_text_chunks(
    content: str,
    highlights: list,
    syntax_style: SyntaxStyle,
    conceal_options: dict | None = None,
) -> list[TextChunk]:
    """Convert tree-sitter highlights to styled text chunks.

    Converts Tree-sitter highlight ranges to styled text chunks.
    """
    chunks: list[TextChunk] = []
    default_style = syntax_style.get_style("default")
    conceal_enabled = (conceal_options or {}).get("enabled", True)

    if not highlights:
        # No highlights - return content with default style
        chunks.append(
            TextChunk(
                text=content,
                fg=default_style.fg if default_style else None,
                bg=default_style.bg if default_style else None,
            )
        )
        return chunks

    boundaries: list[dict] = []
    for i, hl in enumerate(highlights):
        start = hl[0]
        end = hl[1]
        if start == end:
            continue
        boundaries.append({"offset": start, "type": "start", "index": i})
        boundaries.append({"offset": end, "type": "end", "index": i})

    boundaries.sort(key=lambda b: (b["offset"], 0 if b["type"] == "end" else 1))

    active_highlights: set[int] = set()
    current_offset = 0

    for boundary in boundaries:
        if current_offset < boundary["offset"]:
            segment_text = content[current_offset : boundary["offset"]]
            if active_highlights:
                groups = sorted(
                    (highlights[idx][2] for idx in active_highlights),
                    key=lambda g: g.count(".") + 1,
                )
                merged_fg = default_style.fg if default_style else None
                merged_bg = default_style.bg if default_style else None
                for grp in groups:
                    sty = syntax_style.get_style(grp)
                    if sty:
                        if sty.fg is not None:
                            merged_fg = sty.fg
                        if sty.bg is not None:
                            merged_bg = sty.bg

                conceal_text = None
                if conceal_enabled:
                    for idx in active_highlights:
                        group = highlights[idx][2]
                        meta = highlights[idx][3] if len(highlights[idx]) > 3 else None
                        if meta and isinstance(meta, dict) and "conceal" in meta:
                            conceal_text = meta["conceal"]
                            break
                        if group == "conceal" or group.startswith("conceal."):
                            conceal_text = ""
                            if group == "conceal.with.space":
                                conceal_text = " "
                            break

                if conceal_text is not None:
                    if conceal_text:
                        chunks.append(
                            TextChunk(
                                text=conceal_text,
                                fg=default_style.fg if default_style else None,
                                bg=default_style.bg if default_style else None,
                            )
                        )
                else:
                    chunks.append(
                        TextChunk(
                            text=segment_text,
                            fg=merged_fg,
                            bg=merged_bg,
                        )
                    )
            else:
                chunks.append(
                    TextChunk(
                        text=segment_text,
                        fg=default_style.fg if default_style else None,
                        bg=default_style.bg if default_style else None,
                    )
                )

        if boundary["type"] == "start":
            active_highlights.add(boundary["index"])
        else:
            active_highlights.discard(boundary["index"])

        current_offset = boundary["offset"]

    if current_offset < len(content):
        text = content[current_offset:]
        chunks.append(
            TextChunk(
                text=text,
                fg=default_style.fg if default_style else None,
                bg=default_style.bg if default_style else None,
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# StyledText wrapper for text chunks
# ---------------------------------------------------------------------------


class StyledTextWrapper:
    """Wrapper that converts TextChunks to a renderable text string.

    The native text buffer only supports plain text. This wrapper converts
    styled chunks to plain text for the buffer, while keeping the styled
    chunks for highlight tracking.
    """

    def __init__(self, chunks: list[TextChunk]) -> None:
        self._chunks = chunks

    def to_plain_text(self) -> str:
        return "".join(c.text for c in self._chunks)

    @property
    def chunks(self) -> list[TextChunk]:
        return self._chunks


# ---------------------------------------------------------------------------
# CodeRenderable
# ---------------------------------------------------------------------------


class CodeRenderable(TextRenderable):
    """Code renderable with optional syntax highlighting.

    Extends TextRenderable with:
    - Pluggable tree-sitter client for syntax highlighting
    - Streaming mode for progressive content updates
    - Concealment support
    - drawUnstyledText option to control pre-highlight rendering
    - onHighlight/onChunks callbacks for custom highlight processing

    Usage:
        syntax_style = SyntaxStyle.from_styles({
            "default": {"fg": RGBA(1, 1, 1, 1)},
            "keyword": {"fg": RGBA(0, 0, 1, 1)},
        })

        code = CodeRenderable(
            ctx, id="code",
            content="const x = 1;",
            filetype="javascript",
            syntax_style=syntax_style,
        )
    """

    def __init__(
        self,
        ctx: Any = None,
        *,
        content: str = "",
        filetype: str | None = None,
        syntax_style: SyntaxStyle | None = None,
        tree_sitter_client: TreeSitterClient | None = None,
        conceal: bool = True,
        draw_unstyled_text: bool = True,
        streaming: bool = False,
        on_highlight: Any = None,
        on_chunks: Any = None,
        # TextRenderable options
        selectable: bool = True,
        wrap_mode: str = "word",
        **kwargs,
    ):
        # Store content BEFORE calling super().__init__ which might call content setter
        super().__init__(
            content=None,  # Don't set content in super
            selectable=selectable,
            wrap_mode=wrap_mode,
            **kwargs,
        )

        # Store context (renderer)
        self._ctx = ctx

        # Code-specific state
        self._code_content = content
        self._filetype = filetype
        self._syntax_style = syntax_style or SyntaxStyle()
        self._tree_sitter_client = tree_sitter_client or TreeSitterClient()
        self._conceal = conceal
        self._draw_unstyled_text = draw_unstyled_text
        self._streaming = streaming
        self._on_highlight = on_highlight
        self._on_chunks = on_chunks

        # Highlighting state
        self._is_highlighting = False
        self._highlights_dirty = False
        self._highlight_snapshot_id = 0
        self._should_render_text_buffer = True
        self._had_initial_content = False
        self._last_highlights: list = []

        self._code_destroyed = False

        self._line_highlights: dict[int, list[LineHighlight]] = {}
        self._styled_chunks: list[TextChunk] = []

        # Prevent TextRenderable.render() from syncing from the (empty) root text
        # node, which would clear our manually-set text buffer content.
        self._has_manual_styled_text = True

        if content:
            self._text_buffer.set_text(content)
            self._update_text_info()
            self._should_render_text_buffer = self._draw_unstyled_text or not self._filetype
            self._highlights_dirty = True

    # ── Content property ────────────────────────────────────────────

    @property
    def content(self) -> str:
        return self._code_content

    @content.setter
    def content(self, value: str) -> None:
        if self._code_content != value:
            self._code_content = value
            self._highlights_dirty = True
            self._highlight_snapshot_id += 1

            if self._streaming and not self._draw_unstyled_text and self._filetype:
                # In streaming mode with drawUnstyledText=false, don't update text buffer
                # until highlights complete
                return

            self._text_buffer.set_text(value)
            self._update_text_info()

    # ── Filetype property ───────────────────────────────────────────

    @property
    def filetype(self) -> str | None:
        return self._filetype

    @filetype.setter
    def filetype(self, value: str | None) -> None:
        if self._filetype != value:
            self._filetype = value
            self._highlights_dirty = True

    # ── SyntaxStyle property ────────────────────────────────────────

    @property
    def syntax_style(self) -> SyntaxStyle:
        return self._syntax_style

    @syntax_style.setter
    def syntax_style(self, value: SyntaxStyle) -> None:
        if self._syntax_style is not value:
            self._syntax_style = value
            self._highlights_dirty = True

    # ── Conceal property ────────────────────────────────────────────

    @property
    def conceal(self) -> bool:
        return self._conceal

    @conceal.setter
    def conceal(self, value: bool) -> None:
        if self._conceal != value:
            self._conceal = value
            self._highlights_dirty = True

    # ── drawUnstyledText property ───────────────────────────────────

    @property
    def draw_unstyled_text(self) -> bool:
        return self._draw_unstyled_text

    @draw_unstyled_text.setter
    def draw_unstyled_text(self, value: bool) -> None:
        if self._draw_unstyled_text != value:
            self._draw_unstyled_text = value
            self._highlights_dirty = True

    # ── Streaming property ──────────────────────────────────────────

    @property
    def streaming(self) -> bool:
        return self._streaming

    @streaming.setter
    def streaming(self, value: bool) -> None:
        if self._streaming != value:
            self._streaming = value
            self._had_initial_content = False
            self._last_highlights = []
            self._highlights_dirty = True

    # ── TreeSitterClient property ───────────────────────────────────

    @property
    def tree_sitter_client(self) -> TreeSitterClient:
        return self._tree_sitter_client

    @tree_sitter_client.setter
    def tree_sitter_client(self, value: TreeSitterClient) -> None:
        if self._tree_sitter_client is not value:
            self._tree_sitter_client = value
            self._highlights_dirty = True

    # ── onHighlight property ────────────────────────────────────────

    @property
    def on_highlight(self) -> Any:
        return self._on_highlight

    @on_highlight.setter
    def on_highlight(self, value: Any) -> None:
        if self._on_highlight is not value:
            self._on_highlight = value
            self._highlights_dirty = True

    # ── onChunks property ───────────────────────────────────────────

    @property
    def on_chunks(self) -> Any:
        return self._on_chunks

    @on_chunks.setter
    def on_chunks(self, value: Any) -> None:
        if self._on_chunks is not value:
            self._on_chunks = value
            self._highlights_dirty = True

    # ── isHighlighting property ─────────────────────────────────────

    @property
    def is_highlighting(self) -> bool:
        return self._is_highlighting

    # ── Plain text override ─────────────────────────────────────────

    @property
    def plain_text(self) -> str:
        """Return content even if text buffer hasn't been updated yet."""
        return self._text_buffer.get_plain_text()

    # ── Line count override ─────────────────────────────────────────

    @property
    def line_count(self) -> int:
        """Return line count based on content, even before highlighting."""
        # The text buffer should always have the content for line counting
        return self._text_buffer.get_line_count()

    # ── Text length override ────────────────────────────────────────

    @property
    def text_length(self) -> int:
        """Return text length based on content."""
        return self._text_buffer.get_length()

    # ── Line highlights ─────────────────────────────────────────────

    def get_line_highlights(self, line_idx: int) -> list[LineHighlight]:
        """Get highlights for a specific line."""
        return self._line_highlights.get(line_idx, [])

    # ── Ensure visible text before highlight ────────────────────────

    def _ensure_visible_text_before_highlight(self) -> None:
        """Set _should_render_text_buffer based on current state."""
        if self._code_destroyed:
            return

        content = self._code_content

        if not self._filetype:
            self._should_render_text_buffer = True
            return

        is_initial = self._streaming and not self._had_initial_content
        should_draw_unstyled_now = (
            (is_initial and self._draw_unstyled_text)
            if self._streaming
            else self._draw_unstyled_text
        )

        if self._streaming and not is_initial:
            self._should_render_text_buffer = True
        elif should_draw_unstyled_now:
            self._text_buffer.set_text(content)
            self._should_render_text_buffer = True
        else:
            self._should_render_text_buffer = False

    # ── Start highlight ─────────────────────────────────────────────

    def _start_highlight_sync(self) -> None:
        """Synchronously initiate highlighting and schedule async completion.

        This mirrors JS behavior where calling an async function executes
        synchronously until the first real await. The tree-sitter client's
        ``start_highlight_once`` creates the pending request synchronously,
        making ``is_highlighting()`` return True immediately. The async
        completion (waiting for result, processing highlights) is scheduled
        via asyncio.ensure_future.

        When the client's ``highlight_once`` has been monkey-patched (e.g. for
        call counting in tests), we detect this and call the patched version
        instead, preserving the wrapper's side effects.
        """
        content = self._code_content
        filetype = self._filetype
        self._highlight_snapshot_id += 1
        snapshot_id = self._highlight_snapshot_id

        if not filetype:
            return

        is_initial = self._streaming and not self._had_initial_content
        if is_initial:
            self._had_initial_content = True

        self._is_highlighting = True

        client = self._tree_sitter_client

        # Detect if the client has a custom start_highlight_once (i.e.,
        # it's MockTreeSitterClient or a subclass that overrides it),
        # AND highlight_once hasn't been monkey-patched on the instance.
        has_custom_start = (
            type(client).start_highlight_once is not TreeSitterClient.start_highlight_once
        )
        highlight_once_patched = hasattr(client, "__dict__") and "highlight_once" in client.__dict__

        if has_custom_start and not highlight_once_patched:
            # Use synchronous start_highlight_once for immediate pending registration
            try:
                result_future = client.start_highlight_once(content, filetype)
            except Exception:
                asyncio.ensure_future(
                    self._complete_highlight_from_coro(
                        client.highlight_once(content, filetype),
                        content,
                        filetype,
                        snapshot_id,
                    )
                )
                return

            asyncio.ensure_future(
                self._complete_highlight(result_future, content, filetype, snapshot_id)
            )
        else:
            # Fall back to calling highlight_once as a coroutine.
            # This handles: custom TreeSitterClient subclasses, monkey-patched
            # highlight_once, and any client that doesn't override start_highlight_once.
            asyncio.ensure_future(
                self._complete_highlight_from_coro(
                    client.highlight_once(content, filetype),
                    content,
                    filetype,
                    snapshot_id,
                )
            )

    async def _complete_highlight(
        self,
        result_future: asyncio.Future,
        content: str,
        filetype: str,
        snapshot_id: int,
    ) -> None:
        """Async completion: await the highlight result and process it."""
        try:
            result = await result_future
            await self._process_highlight_result(result, content, filetype, snapshot_id)
        except Exception:
            self._handle_highlight_error(content, snapshot_id)

    async def _complete_highlight_from_coro(
        self,
        coro,
        content: str,
        filetype: str,
        snapshot_id: int,
    ) -> None:
        """Async completion from a coroutine (for clients without start_highlight_once)."""
        try:
            result = await coro
            await self._process_highlight_result(result, content, filetype, snapshot_id)
        except Exception:
            self._handle_highlight_error(content, snapshot_id)

    async def _process_highlight_result(
        self,
        result: dict,
        content: str,
        filetype: str,
        snapshot_id: int,
    ) -> None:
        """Process a highlight result dict."""
        if snapshot_id != self._highlight_snapshot_id:
            return

        if self._code_destroyed:
            return

        highlights = result.get("highlights", []) or []

        if self._on_highlight:
            context = HighlightContext(
                content=content,
                filetype=filetype,
                syntax_style=self._syntax_style,
            )
            modified = self._on_highlight(highlights, context)
            # Handle async callbacks
            if asyncio.iscoroutine(modified):
                modified = await modified
            if modified is not None:
                highlights = modified

        if snapshot_id != self._highlight_snapshot_id:
            return

        if self._code_destroyed:
            return

        if highlights and self._streaming:
            self._last_highlights = highlights

        if highlights or self._on_chunks:
            context = ChunkRenderContext(
                content=content,
                filetype=filetype,
                syntax_style=self._syntax_style,
                highlights=highlights,
            )

            chunks = tree_sitter_to_text_chunks(
                content,
                highlights,
                self._syntax_style,
                {"enabled": self._conceal},
            )

            if self._on_chunks:
                modified_chunks = self._on_chunks(chunks, context)
                if asyncio.iscoroutine(modified_chunks):
                    modified_chunks = await modified_chunks
                if modified_chunks is not None:
                    chunks = modified_chunks

            if snapshot_id != self._highlight_snapshot_id:
                return

            if self._code_destroyed:
                return

            self._build_line_highlights(content, highlights)

            plain = "".join(c.text for c in chunks)
            self._text_buffer.set_text(plain)
            self._styled_chunks = chunks
        else:
            self._text_buffer.set_text(content)

        self._should_render_text_buffer = True
        self._is_highlighting = False
        self._highlights_dirty = False
        self._update_text_info()
        self.mark_dirty()

    def _handle_highlight_error(self, content: str, snapshot_id: int) -> None:
        """Handle highlight failure by falling back to plain text."""
        if snapshot_id != self._highlight_snapshot_id:
            return

        if self._code_destroyed:
            return

        self._text_buffer.set_text(content)
        self._should_render_text_buffer = True
        self._is_highlighting = False
        self._highlights_dirty = False
        self._update_text_info()
        self.mark_dirty()

    def _build_line_highlights(self, content: str, highlights: list) -> None:
        """Build per-line highlight data from highlights."""
        self._line_highlights.clear()
        if not highlights:
            return

        lines = content.split("\n")
        line_offsets: list[int] = []
        offset = 0
        for line in lines:
            line_offsets.append(offset)
            offset += len(line) + 1  # +1 for newline

        for hl in highlights:
            start = hl[0]
            end = hl[1]
            group = hl[2]
            style_id = self._syntax_style.get_style_id(group)

            # Find which lines this highlight spans
            for line_idx, line_offset in enumerate(line_offsets):
                line_end = line_offset + len(lines[line_idx])
                if start < line_end and end > line_offset:
                    # Highlight intersects this line
                    hl_start = max(0, start - line_offset)
                    hl_end = min(len(lines[line_idx]), end - line_offset)
                    if hl_start < hl_end:
                        if line_idx not in self._line_highlights:
                            self._line_highlights[line_idx] = []
                        self._line_highlights[line_idx].append(
                            LineHighlight(start=hl_start, end=hl_end, style_id=style_id)
                        )

    # ── Render self (called each frame) ─────────────────────────────

    def _render_self(self, buffer: Any) -> None:
        """Process highlights dirty flag and trigger highlighting.

        Called from render() each frame.
        """
        if self._highlights_dirty:
            if self._code_destroyed:
                return

            if not self._code_content:
                self._should_render_text_buffer = False
                self._highlights_dirty = False
            elif not self._filetype:
                # No filetype - use fallback rendering (plain text)
                self._text_buffer.set_text(self._code_content)
                self._update_text_info()
                self._should_render_text_buffer = True
                self._highlights_dirty = False
            else:
                self._ensure_visible_text_before_highlight()
                self._highlights_dirty = False
                # Synchronously start the highlight request, then
                # schedule async completion
                self._start_highlight_sync()

    def render(self, buffer: Buffer, delta_time: float = 0) -> None:
        """Render code to the buffer."""
        if not self._visible:
            return

        self._render_self(buffer)

        if not self._should_render_text_buffer:
            return

        super().render(buffer, delta_time)

    # ── Destroy ─────────────────────────────────────────────────────

    def destroy(self) -> None:
        """Clean up resources."""
        self._code_destroyed = True
        self._line_highlights.clear()
        self._styled_chunks.clear()
        super().destroy()


__all__ = [
    "CodeRenderable",
    "SyntaxStyle",
    "StyleDefinition",
    "TreeSitterClient",
    "MockTreeSitterClient",
    "SimpleHighlight",
    "TextChunk",
    "LineHighlight",
    "HighlightContext",
    "ChunkRenderContext",
    "tree_sitter_to_text_chunks",
]
