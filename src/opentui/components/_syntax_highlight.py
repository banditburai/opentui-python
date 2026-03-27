"""Syntax highlighting types, tree-sitter client, and chunk conversion.

Self-contained module extracted from code_renderable.py. Provides the data
types (StyleDefinition, SyntaxStyle, TextChunk, LineHighlight, etc.) and
the tree_sitter_to_text_chunks() conversion used by CodeRenderable and tests.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any

from .. import structs as s

_URL_SCOPES = ("markup.link.url", "string.special.url")


def _detect_links(
    chunks: list[TextChunk],
    context: Any,
) -> list[TextChunk]:
    """Scan highlight scopes for URL patterns and back-track for labels."""
    content: str = context["content"] if isinstance(context, dict) else context.content
    highlights: list = context["highlights"] if isinstance(context, dict) else context.highlights

    ranges: list[dict[str, Any]] = []

    for i, hl in enumerate(highlights):
        start, end, group = hl[0], hl[1], hl[2]
        if group not in _URL_SCOPES:
            continue
        url = content[start:end]
        ranges.append({"start": start, "end": end, "url": url})
        for j in range(i - 1, -1, -1):
            prev_start, prev_end, prev_group = highlights[j][0], highlights[j][1], highlights[j][2]
            if prev_group == "markup.link.label":
                ranges.append({"start": prev_start, "end": prev_end, "url": url})
                break
            # Skip metadata captures (conceal, nospell) interleaved with link highlights
            if prev_group in ("conceal", "nospell"):
                continue
            if not prev_group.startswith("markup.link"):
                break

    if not ranges:
        return chunks

    content_pos = 0
    for chunk in chunks:
        if not chunk.text:
            continue
        idx = content.find(chunk.text, content_pos)
        if idx < 0:
            continue
        for r in ranges:
            if idx < r["end"] and idx + len(chunk.text) > r["start"]:
                chunk.link = {"url": r["url"]}
                break
        content_pos = idx + len(chunk.text)

    return chunks


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
        ss = cls()
        for name, style_def in styles.items():
            fields = {
                k: style_def[k]
                for k in ("fg", "bg", "bold", "italic", "underline", "dim")
                if k in style_def
            }
            ss.register_style(name, StyleDefinition(**fields))
        return ss

    def register_style(self, name: str, style: StyleDefinition) -> int:
        self._styles[name] = style
        if name not in self._style_ids:
            self._style_ids[name] = self._next_id
            self._next_id += 1
        return self._style_ids[name]

    def get_style(self, name: str) -> StyleDefinition | None:
        style = self._styles.get(name)
        if style is not None:
            return style
        # Fallback: try base scope (e.g., "markup" from "markup.heading.1")
        if "." in name:
            base = name.split(".", maxsplit=1)[0]
            return self._styles.get(base)
        return None

    def get_style_id(self, name: str) -> int:
        if name not in self._style_ids:
            self._style_ids[name] = self._next_id
            self._next_id += 1
        return self._style_ids[name]


@dataclass
class TextChunk:
    text: str
    fg: s.RGBA | None = None
    bg: s.RGBA | None = None
    attributes: int = 0
    link: dict[str, str] | None = None


@dataclass
class LineHighlight:
    start: int
    end: int
    style_id: int


class TreeSitterClient:
    def __init__(self, options: dict | None = None) -> None:
        self._options = options or {}

    def start_highlight_once(
        self,
        content: str,
        filetype: str,
    ) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        future.set_result({"highlights": []})
        return future

    async def highlight_once(
        self,
        content: str,
        filetype: str,
    ) -> dict:
        return await self.start_highlight_once(content, filetype)

    async def initialize(self) -> None:
        pass

    async def preload_parser(self, filetype: str) -> None:
        pass


class MockTreeSitterClient(TreeSitterClient):
    def __init__(self, options: dict | None = None) -> None:
        super().__init__(options)
        self._highlight_futures: list[dict] = []
        self._mock_result: dict = {"highlights": []}
        self._auto_resolve_timeout: float | None = None
        if options and "autoResolveTimeout" in options:
            self._auto_resolve_timeout = options["autoResolveTimeout"] / 1000.0

    def set_mock_result(self, result: dict) -> None:
        self._mock_result = result

    def start_highlight_once(self, content: str, filetype: str) -> asyncio.Future:
        loop = asyncio.get_running_loop()
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

            asyncio.get_running_loop().create_task(_auto_resolve())

        return future

    async def highlight_once(self, content: str, filetype: str) -> dict:
        return await self.start_highlight_once(content, filetype)

    def resolve_highlight_once(self, index: int = 0) -> None:
        if 0 <= index < len(self._highlight_futures):
            entry = self._highlight_futures[index]
            future = entry["future"]
            if not future.done():
                future.set_result(dict(self._mock_result))
            self._highlight_futures.pop(index)

    def resolve_all_highlight_once(self) -> None:
        for entry in self._highlight_futures:
            future = entry["future"]
            if not future.done():
                future.set_result(dict(self._mock_result))
        self._highlight_futures.clear()

    def is_highlighting(self) -> bool:
        return bool(self._highlight_futures)


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


def tree_sitter_to_text_chunks(
    content: str,
    highlights: list,
    syntax_style: SyntaxStyle,
    conceal_options: dict | None = None,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    default_style = syntax_style.get_style("default")
    conceal_enabled = (conceal_options or {}).get("enabled", True)

    if not highlights:
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
                merged_attrs = 0
                for grp in groups:
                    sty = syntax_style.get_style(grp)
                    if sty:
                        if sty.fg is not None:
                            merged_fg = sty.fg
                        if sty.bg is not None:
                            merged_bg = sty.bg
                        if sty.bold:
                            merged_attrs |= s.TEXT_ATTRIBUTE_BOLD
                        if sty.italic:
                            merged_attrs |= s.TEXT_ATTRIBUTE_ITALIC
                        if sty.underline:
                            merged_attrs |= s.TEXT_ATTRIBUTE_UNDERLINE
                        if sty.dim:
                            merged_attrs |= s.TEXT_ATTRIBUTE_DIM

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
                            attributes=merged_attrs,
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


__all__ = [
    "ChunkRenderContext",
    "HighlightContext",
    "LineHighlight",
    "MockTreeSitterClient",
    "StyleDefinition",
    "SyntaxStyle",
    "TextChunk",
    "TreeSitterClient",
    "tree_sitter_to_text_chunks",
]
