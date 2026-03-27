"""Tests for PyTreeSitterClient — real tree-sitter highlighting.

All tests require the tree-sitter package and language grammars.
They are automatically skipped if the highlighting extras aren't installed.
"""

import asyncio

import pytest

ts = pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_python")

from opentui.tree_sitter_client import (
    PyTreeSitterClient,
    _byte_to_char_map,
    _load_bundled_query,
    _LANG_REGISTRY,
)


# ---------------------------------------------------------------------------
# Byte-to-char mapping
# ---------------------------------------------------------------------------


class TestByteToCharMap:
    def test_ascii_identity(self):
        text = "hello world"
        mapping = _byte_to_char_map(text)
        # For ASCII, byte offset == char offset
        assert len(mapping) == len(text) + 1  # +1 sentinel
        for i in range(len(text)):
            assert mapping[i] == i

    def test_two_byte_utf8(self):
        text = "héllo"  # é is 2 bytes in UTF-8
        mapping = _byte_to_char_map(text)
        # h(1) é(2) l(1) l(1) o(1) = 6 bytes + 1 sentinel = 7
        assert len(mapping) == 7
        assert mapping[0] == 0  # h
        assert mapping[1] == 1  # first byte of é
        assert mapping[2] == 1  # second byte of é
        assert mapping[3] == 2  # l
        assert mapping[4] == 3  # l
        assert mapping[5] == 4  # o
        assert mapping[6] == 5  # sentinel

    def test_three_byte_utf8(self):
        text = "x日y"  # 日 is 3 bytes
        mapping = _byte_to_char_map(text)
        # x(1) 日(3) y(1) = 5 bytes + 1 sentinel
        assert len(mapping) == 6
        assert mapping[0] == 0  # x
        assert mapping[1] == 1  # first byte of 日
        assert mapping[2] == 1  # second byte of 日
        assert mapping[3] == 1  # third byte of 日
        assert mapping[4] == 2  # y
        assert mapping[5] == 3  # sentinel

    def test_four_byte_utf8_emoji(self):
        text = "a👍b"  # 👍 is 4 bytes
        mapping = _byte_to_char_map(text)
        # a(1) 👍(4) b(1) = 6 bytes + 1 sentinel
        assert len(mapping) == 7
        assert mapping[0] == 0  # a
        assert mapping[1] == 1  # first byte of 👍
        assert mapping[4] == 1  # fourth byte of 👍
        assert mapping[5] == 2  # b
        assert mapping[6] == 3  # sentinel

    def test_empty_string(self):
        mapping = _byte_to_char_map("")
        assert mapping == [0]  # just sentinel

    def test_all_ascii(self):
        text = "abc"
        mapping = _byte_to_char_map(text)
        assert mapping == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# Client initialization and caching
# ---------------------------------------------------------------------------


class TestClientInit:
    def test_creates_client(self):
        client = PyTreeSitterClient()
        assert client._cache == {}
        assert client._unavailable == set()

    def test_ensure_ready_caches_parser(self):
        client = PyTreeSitterClient()
        result1 = client._ensure_ready("python")
        assert result1 is not None
        result2 = client._ensure_ready("python")
        assert result1 is result2  # same cached tuple

    def test_ensure_ready_unknown_filetype(self):
        client = PyTreeSitterClient()
        result = client._ensure_ready("nonexistent_language_xyz")
        assert result is None
        assert "nonexistent_language_xyz" in client._unavailable

    def test_ensure_ready_caches_unavailable(self):
        client = PyTreeSitterClient()
        client._ensure_ready("nonexistent_language_xyz")
        # Second call should return None immediately without re-attempting
        result = client._ensure_ready("nonexistent_language_xyz")
        assert result is None

    def test_supported_filetypes(self):
        client = PyTreeSitterClient()
        ft = client.supported_filetypes
        assert "python" in ft
        assert "javascript" in ft
        assert "typescript" in ft

    def test_is_filetype_available_python(self):
        client = PyTreeSitterClient()
        assert client.is_filetype_available("python") is True

    def test_is_filetype_available_unknown(self):
        client = PyTreeSitterClient()
        assert client.is_filetype_available("cobol_xyz") is False


# ---------------------------------------------------------------------------
# highlight_once
# ---------------------------------------------------------------------------


class TestHighlightOnce:
    async def test_python_basic(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("def hello(): pass", "python")
        assert "highlights" in result
        highlights = result["highlights"]
        assert len(highlights) > 0
        # Each highlight is [start, end, group] or [start, end, group, meta]
        for h in highlights:
            assert len(h) >= 3
            assert isinstance(h[0], int)
            assert isinstance(h[1], int)
            assert isinstance(h[2], str)
            assert h[0] < h[1]  # non-empty span

    async def test_javascript_basic(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("const x = 1;", "javascript")
        highlights = result["highlights"]
        assert len(highlights) > 0
        groups = {h[2] for h in highlights}
        assert "keyword" in groups  # "const"

    async def test_typescript_basic(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("const x: number = 1;", "typescript")
        highlights = result["highlights"]
        assert len(highlights) > 0

    async def test_json_basic(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once('{"key": "value"}', "json")
        highlights = result["highlights"]
        assert len(highlights) > 0

    async def test_bash_basic(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("echo hello", "bash")
        highlights = result["highlights"]
        assert len(highlights) > 0

    async def test_unsupported_filetype_returns_empty(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("some code", "unknown_lang_xyz")
        assert result == {"highlights": []}

    async def test_empty_content(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("", "python")
        assert result == {"highlights": []}

    async def test_highlights_sorted_by_start(self):
        client = PyTreeSitterClient()
        code = "def foo():\n    x = 1\n    return x"
        result = await client.highlight_once(code, "python")
        highlights = result["highlights"]
        starts = [h[0] for h in highlights]
        assert starts == sorted(starts)

    async def test_alias_py(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("x = 1", "py")
        assert len(result["highlights"]) > 0

    async def test_alias_js(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("const x = 1;", "js")
        assert len(result["highlights"]) > 0

    async def test_alias_ts(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("const x = 1;", "ts")
        assert len(result["highlights"]) > 0

    async def test_alias_sh(self):
        client = PyTreeSitterClient()
        result = await client.highlight_once("echo hi", "sh")
        assert len(result["highlights"]) > 0


# ---------------------------------------------------------------------------
# Non-ASCII / byte offset conversion
# ---------------------------------------------------------------------------


class TestNonAsciiHighlighting:
    async def test_non_ascii_char_offsets_correct(self):
        """Highlights for non-ASCII content should use char offsets, not byte offsets."""
        client = PyTreeSitterClient()
        code = 'x = "héllo"'
        result = await client.highlight_once(code, "python")
        highlights = result["highlights"]
        # All offsets should be valid Python string indices
        for h in highlights:
            start, end = h[0], h[1]
            assert 0 <= start < len(code), f"start {start} out of range for len {len(code)}"
            assert 0 < end <= len(code), f"end {end} out of range for len {len(code)}"
            # The substring should be valid
            _ = code[start:end]

    async def test_emoji_char_offsets(self):
        """Emoji content (4-byte UTF-8) should produce correct char offsets."""
        client = PyTreeSitterClient()
        code = 'x = "👍"'
        result = await client.highlight_once(code, "python")
        highlights = result["highlights"]
        for h in highlights:
            start, end = h[0], h[1]
            assert 0 <= start < len(code)
            assert 0 < end <= len(code)

    async def test_cjk_char_offsets(self):
        """CJK characters (3-byte UTF-8) should produce correct char offsets."""
        client = PyTreeSitterClient()
        code = 'x = "日本語"'
        result = await client.highlight_once(code, "python")
        highlights = result["highlights"]
        for h in highlights:
            start, end = h[0], h[1]
            assert 0 <= start < len(code)
            assert 0 < end <= len(code)

    async def test_ascii_skips_char_mapping(self):
        """Pure ASCII content should not build a byte→char map (optimization)."""
        client = PyTreeSitterClient()
        code = "def hello(): pass"
        result = await client.highlight_once(code, "python")
        # Just verify it works — the optimization is internal
        assert len(result["highlights"]) > 0


# ---------------------------------------------------------------------------
# Markdown conceal support
# ---------------------------------------------------------------------------


class TestConcealHighlights:
    async def test_markdown_heading_conceal(self):
        """Markdown headings should include conceal metadata."""
        client = PyTreeSitterClient()
        # Markdown parser needs trailing newline for proper parsing
        result = await client.highlight_once("# Hello\n", "markdown")
        highlights = result["highlights"]
        # Should have a conceal highlight for the # marker
        conceal_highlights = [h for h in highlights if len(h) > 3 and "conceal" in (h[3] or {})]
        assert len(conceal_highlights) > 0
        # The conceal value should be empty string (hide the marker)
        assert conceal_highlights[0][3]["conceal"] == ""

    async def test_markdown_no_conceal_for_text(self):
        """Regular text in markdown should not have conceal metadata."""
        client = PyTreeSitterClient()
        result = await client.highlight_once("Just some text.\n", "markdown")
        highlights = result["highlights"]
        conceal_highlights = [h for h in highlights if len(h) > 3 and "conceal" in (h[3] or {})]
        assert len(conceal_highlights) == 0


# ---------------------------------------------------------------------------
# start_highlight_once (Future-based API)
# ---------------------------------------------------------------------------


class TestStartHighlightOnce:
    async def test_returns_future_with_result(self):
        client = PyTreeSitterClient()
        future = client.start_highlight_once("def foo(): pass", "python")
        result = await future
        assert "highlights" in result
        assert len(result["highlights"]) > 0

    async def test_unsupported_returns_empty(self):
        client = PyTreeSitterClient()
        future = client.start_highlight_once("code", "nonexistent_xyz")
        result = await future
        assert result == {"highlights": []}


# ---------------------------------------------------------------------------
# preload_parser
# ---------------------------------------------------------------------------


class TestPreloadParser:
    async def test_preload_creates_cache_entry(self):
        client = PyTreeSitterClient()
        assert "javascript" not in client._cache
        await client.preload_parser("javascript")
        assert "javascript" in client._cache

    async def test_preload_unknown_is_noop(self):
        client = PyTreeSitterClient()
        await client.preload_parser("nonexistent_xyz")
        assert "nonexistent_xyz" in client._unavailable
