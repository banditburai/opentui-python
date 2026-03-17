"""PyTreeSitterClient — real syntax highlighting using py-tree-sitter.

Implements the TreeSitterClient interface from code_renderable.py using
native tree-sitter C bindings via the py-tree-sitter package.

Usage:
    from opentui.tree_sitter_client import PyTreeSitterClient
    client = PyTreeSitterClient()
    result = await client.highlight_once("def hello(): pass", "python")
    # result["highlights"] is a list of [start, end, group_name] or
    # [start, end, group_name, {"conceal": "..."}]
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language registry: filetype → (module_name, function_name)
# ---------------------------------------------------------------------------

_LANG_REGISTRY: dict[str, tuple[str, str]] = {
    "python": ("tree_sitter_python", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "json": ("tree_sitter_json", "language"),
    "markdown": ("tree_sitter_markdown", "language"),
    "markdown_inline": ("tree_sitter_markdown", "inline_language"),
    "bash": ("tree_sitter_bash", "language"),
    # Aliases
    "py": ("tree_sitter_python", "language"),
    "js": ("tree_sitter_javascript", "language"),
    "ts": ("tree_sitter_typescript", "language_typescript"),
    "sh": ("tree_sitter_bash", "language"),
    "shell": ("tree_sitter_bash", "language"),
    "zsh": ("tree_sitter_bash", "language"),
}

# Bundled query directory (relative to this file)
_QUERIES_DIR = Path(__file__).parent / "tree_sitter_queries"

# Map filetypes to query subdirectory names (when different from filetype)
_QUERY_DIR_MAP: dict[str, str] = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
}


# ---------------------------------------------------------------------------
# Byte-to-char offset conversion
# ---------------------------------------------------------------------------


def _byte_to_char_map(text: str) -> list[int]:
    """Build byte-offset → char-offset lookup table.

    py-tree-sitter returns UTF-8 byte offsets, but the existing highlight
    pipeline expects Python character offsets (string indexing). For ASCII-only
    text these are identical; for non-ASCII text we need this mapping.
    """
    mapping: list[int] = []
    for i, ch in enumerate(text):
        for _ in ch.encode("utf-8"):
            mapping.append(i)
    mapping.append(len(text))  # sentinel for end positions
    return mapping


# ---------------------------------------------------------------------------
# Query loading
# ---------------------------------------------------------------------------


def _load_bundled_query(filetype: str) -> str | None:
    """Load a bundled highlights.scm for the given filetype."""
    query_dir = _QUERY_DIR_MAP.get(filetype, filetype)
    query_path = _QUERIES_DIR / query_dir / "highlights.scm"
    if query_path.is_file():
        return query_path.read_text(encoding="utf-8")
    return None


def _load_query_for_filetype(filetype: str) -> str | None:
    """Load highlight query, trying bundled queries first, then pip package."""
    # Try bundled queries
    query_text = _load_bundled_query(filetype)
    if query_text:
        return query_text

    # Try loading from the pip package's bundled queries
    module_name = _LANG_REGISTRY.get(filetype, (None, None))[0]
    if module_name:
        try:
            pkg = importlib.import_module(module_name)
            # Some packages bundle queries/highlights.scm
            pkg_dir = Path(pkg.__file__).parent if pkg.__file__ else None
            if pkg_dir:
                for candidate in [
                    pkg_dir / "queries" / "highlights.scm",
                    pkg_dir / "highlights.scm",
                ]:
                    if candidate.is_file():
                        return candidate.read_text(encoding="utf-8")
        except (ImportError, AttributeError, OSError):
            pass

    return None


# ---------------------------------------------------------------------------
# PyTreeSitterClient
# ---------------------------------------------------------------------------


class PyTreeSitterClient:
    """Real tree-sitter highlighting using py-tree-sitter native C bindings.

    Implements the same interface as TreeSitterClient from code_renderable.py.
    Parsing runs in a thread via asyncio.to_thread() to avoid blocking the
    event loop.
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[Any, Any]] = {}  # filetype → (Parser, Query)
        self._unavailable: set[str] = set()  # filetypes we know we can't handle

    def _ensure_ready(self, filetype: str) -> tuple[Any, Any] | None:
        """Lazily create and cache Parser + Query for a filetype.

        Returns (Parser, Query) or None if the filetype isn't supported.
        """
        if filetype in self._unavailable:
            return None

        cached = self._cache.get(filetype)
        if cached is not None:
            return cached

        try:
            from tree_sitter import Language, Parser, Query  # noqa: F811

            registry_entry = _LANG_REGISTRY.get(filetype)
            if not registry_entry:
                self._unavailable.add(filetype)
                return None

            module_name, func_name = registry_entry
            mod = importlib.import_module(module_name)
            lang_func = getattr(mod, func_name)
            lang = Language(lang_func())
            parser = Parser(lang)

            query_text = _load_query_for_filetype(filetype)
            if not query_text:
                # No query available — still cache parser for potential future use
                # but we can't highlight without a query
                self._unavailable.add(filetype)
                return None

            query = Query(lang, query_text)
            result = (parser, query)
            self._cache[filetype] = result
            return result

        except (ImportError, OSError, Exception) as exc:
            logger.debug("Failed to initialize tree-sitter for %s: %s", filetype, exc)
            self._unavailable.add(filetype)
            return None

    def _parse_sync(
        self,
        parser: Any,
        query: Any,
        content: str,
    ) -> list[list]:
        """Synchronous parse + query.  Called from a thread."""
        from tree_sitter import QueryCursor

        content_len = len(content)

        # Ensure trailing newline: tree-sitter-markdown (and some other
        # grammars) require it to properly close block-level constructs like
        # fenced code blocks.  Without it the closing delimiter is absorbed
        # into the code content and conceal queries don't match it.
        parse_content = content if content.endswith("\n") else content + "\n"
        encoded = parse_content.encode("utf-8")
        tree = parser.parse(encoded)

        # Use matches() to get pattern-level settings (for conceal)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        needs_mapping = not parse_content.isascii()
        char_map = _byte_to_char_map(parse_content) if needs_mapping else None

        highlights: list[list] = []
        for pattern_idx, match_dict in matches:
            settings = query.pattern_settings(pattern_idx)
            has_conceal = "conceal" in settings

            for group_name, nodes in match_dict.items():
                for node in nodes:
                    if char_map:
                        start = char_map[node.start_byte]
                        end = char_map[min(node.end_byte, len(char_map) - 1)]
                    else:
                        start = node.start_byte
                        end = node.end_byte

                    # Clamp offsets to the original content length so the
                    # appended newline doesn't leak into highlights.
                    start = min(start, content_len)
                    end = min(end, content_len)

                    if start == end:
                        continue

                    if has_conceal:
                        highlights.append(
                            [
                                start,
                                end,
                                group_name,
                                {"conceal": settings["conceal"]},
                            ]
                        )
                    else:
                        highlights.append([start, end, group_name])

        highlights.sort(key=lambda h: (h[0], -h[1]))
        return highlights

    async def highlight_once(self, content: str, filetype: str) -> dict:
        """Highlight content and return result dict.

        Returns {"highlights": [...]} where each highlight is
        [start, end, group_name] or [start, end, group_name, {"conceal": "..."}].
        """
        ready = self._ensure_ready(filetype)
        if not ready:
            return {"highlights": []}

        parser, query = ready
        highlights = await asyncio.to_thread(
            self._parse_sync,
            parser,
            query,
            content,
        )
        return {"highlights": highlights}

    def start_highlight_once(self, content: str, filetype: str) -> asyncio.Future:
        """Synchronously create a highlight request and return a future."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        future = loop.create_future()

        async def _run():
            try:
                result = await self.highlight_once(content, filetype)
                if not future.done():
                    future.set_result(result)
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)

        loop.create_task(_run())
        return future

    async def initialize(self) -> None:
        """Initialize the client (no-op — lazy init)."""

    async def preload_parser(self, filetype: str) -> None:
        """Preload parser for a filetype."""
        self._ensure_ready(filetype)

    @property
    def supported_filetypes(self) -> list[str]:
        """Return list of filetypes that have registered language packages."""
        return list(_LANG_REGISTRY.keys())

    def is_filetype_available(self, filetype: str) -> bool:
        """Check if a filetype can be highlighted."""
        if filetype in self._unavailable:
            return False
        if filetype in self._cache:
            return True
        return self._ensure_ready(filetype) is not None
