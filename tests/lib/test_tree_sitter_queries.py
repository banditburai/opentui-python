"""Tests for tree-sitter query loading and validation.

Verifies that bundled .scm queries load correctly and produce valid results.
"""

import pytest

ts = pytest.importorskip("tree_sitter")

from opentui.tree_sitter_client import (
    _load_bundled_query,
    _load_query_for_filetype,
    _QUERIES_DIR,
    PyTreeSitterClient,
)


class TestBundledQueries:
    def test_javascript_query_exists(self):
        query = _load_bundled_query("javascript")
        assert query is not None
        assert len(query) > 100

    def test_typescript_query_exists(self):
        query = _load_bundled_query("typescript")
        assert query is not None
        assert len(query) > 100

    def test_markdown_query_exists(self):
        query = _load_bundled_query("markdown")
        assert query is not None
        assert "heading" in query.lower()

    def test_markdown_inline_query_exists(self):
        query = _load_bundled_query("markdown_inline")
        assert query is not None
        assert "emphasis" in query.lower()

    def test_zig_query_exists(self):
        query = _load_bundled_query("zig")
        assert query is not None
        assert len(query) > 100

    def test_nonexistent_query_returns_none(self):
        query = _load_bundled_query("nonexistent_language_xyz")
        assert query is None


class TestQueryLoading:
    def test_load_by_alias(self):
        """Loading by alias (e.g., 'js') should find the JavaScript query."""
        query = _load_query_for_filetype("js")
        assert query is not None

    def test_load_by_alias_ts(self):
        query = _load_query_for_filetype("ts")
        assert query is not None

    def test_load_by_alias_sh(self):
        query = _load_query_for_filetype("sh")
        assert query is not None


class TestQueryValidation:
    """Verify that bundled queries parse without errors."""

    @pytest.mark.parametrize(
        "filetype,module,func",
        [
            ("javascript", "tree_sitter_javascript", "language"),
            ("markdown", "tree_sitter_markdown", "language"),
            ("markdown_inline", "tree_sitter_markdown", "inline_language"),
        ],
    )
    def test_bundled_query_parses_successfully(self, filetype, module, func):
        """Each bundled query should parse without QueryError."""
        import importlib
        from tree_sitter import Language, Query

        mod = importlib.import_module(module)
        lang_func = getattr(mod, func)
        lang = Language(lang_func())

        query_text = _load_bundled_query(filetype)
        assert query_text is not None

        # Should not raise QueryError
        q = Query(lang, query_text)
        assert q.pattern_count > 0

    def test_typescript_query_parses(self):
        pytest.importorskip("tree_sitter_typescript")
        import tree_sitter_typescript as tsts
        from tree_sitter import Language, Query

        lang = Language(tsts.language_typescript())
        query_text = _load_bundled_query("typescript")
        assert query_text is not None
        q = Query(lang, query_text)
        assert q.pattern_count > 0

    def test_queries_dir_exists(self):
        assert _QUERIES_DIR.is_dir()
