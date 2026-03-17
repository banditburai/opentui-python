"""Tests for highlight→chunk conversion and style cascade in code_renderable.py.

Tests the tree_sitter_to_text_chunks function and related helpers.
"""

from __future__ import annotations

import pytest

from opentui.components.code_renderable import (
    SyntaxStyle,
    StyleDefinition,
    TextChunk,
    tree_sitter_to_text_chunks,
)
from opentui.structs import RGBA


def _make_style(**scopes: dict) -> SyntaxStyle:
    """Helper to build a SyntaxStyle with named scopes."""
    return SyntaxStyle.from_styles(scopes)


# ---------------------------------------------------------------------------
# Basic conversion
# ---------------------------------------------------------------------------


class TestBasicConversion:
    def test_no_highlights_returns_single_chunk(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        chunks = tree_sitter_to_text_chunks("hello world", [], style)
        assert len(chunks) == 1
        assert chunks[0].text == "hello world"

    def test_single_highlight(self):
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
        )
        highlights = [[0, 3, "keyword"]]  # "def"
        chunks = tree_sitter_to_text_chunks("def foo", highlights, style)
        assert len(chunks) == 2
        assert chunks[0].text == "def"
        assert chunks[0].fg == RGBA(0, 0, 1, 1)
        assert chunks[1].text == " foo"

    def test_multiple_non_overlapping_highlights(self):
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
            function={"fg": RGBA(0, 1, 0, 1)},
        )
        highlights = [
            [0, 3, "keyword"],  # "def"
            [4, 7, "function"],  # "foo"
        ]
        chunks = tree_sitter_to_text_chunks("def foo()", highlights, style)
        assert len(chunks) == 4  # def, " ", foo, "()"
        assert chunks[0].text == "def"
        assert chunks[0].fg == RGBA(0, 0, 1, 1)
        assert chunks[1].text == " "
        assert chunks[2].text == "foo"
        assert chunks[2].fg == RGBA(0, 1, 0, 1)
        assert chunks[3].text == "()"  # trailing unhighlighted text

    def test_empty_content(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        chunks = tree_sitter_to_text_chunks("", [], style)
        assert len(chunks) == 1
        assert chunks[0].text == ""

    def test_highlight_covers_entire_content(self):
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            string={"fg": RGBA(0, 1, 0, 1)},
        )
        highlights = [[0, 7, "string"]]
        chunks = tree_sitter_to_text_chunks('"hello"', highlights, style)
        assert len(chunks) == 1
        assert chunks[0].text == '"hello"'
        assert chunks[0].fg == RGBA(0, 1, 0, 1)

    def test_trailing_text_after_highlights(self):
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
        )
        highlights = [[0, 3, "keyword"]]
        chunks = tree_sitter_to_text_chunks("def foo(): pass", highlights, style)
        assert chunks[-1].text == " foo(): pass"
        assert chunks[-1].fg == RGBA(1, 1, 1, 1)  # default style

    def test_zero_width_highlights_ignored(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        highlights = [[3, 3, "keyword"]]  # zero-width
        chunks = tree_sitter_to_text_chunks("hello", highlights, style)
        assert len(chunks) == 1
        assert chunks[0].text == "hello"


# ---------------------------------------------------------------------------
# Style cascade (B6 fix)
# ---------------------------------------------------------------------------


class TestStyleCascade:
    def test_overlapping_highlights_merge_fg(self):
        """When two highlights overlap, the more specific one provides fg."""
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
        )
        style.register_style("keyword.control", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        # Two overlapping highlights: keyword and keyword.control
        highlights = [
            [0, 3, "keyword"],
            [0, 3, "keyword.control"],
        ]
        chunks = tree_sitter_to_text_chunks("def", highlights, style)
        assert len(chunks) == 1
        # keyword.control (more specific) should win for fg
        assert chunks[0].fg == RGBA(1, 0, 0, 1)

    def test_overlapping_merge_bg_from_less_specific(self):
        """Less specific highlight provides bg when more specific doesn't have bg."""
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
        )
        style.register_style("markup", StyleDefinition(bg=RGBA(0.1, 0.1, 0.1, 1)))
        style.register_style("markup.heading", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        highlights = [
            [0, 5, "markup"],
            [0, 5, "markup.heading"],
        ]
        chunks = tree_sitter_to_text_chunks("# foo", highlights, style)
        assert len(chunks) == 1
        # markup.heading provides fg, markup provides bg
        assert chunks[0].fg == RGBA(1, 0, 0, 1)
        assert chunks[0].bg == RGBA(0.1, 0.1, 0.1, 1)

    def test_single_active_highlight_uses_its_style(self):
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            string={"fg": RGBA(0, 1, 0, 1)},
        )
        highlights = [[0, 5, "string"]]
        chunks = tree_sitter_to_text_chunks("hello", highlights, style)
        assert chunks[0].fg == RGBA(0, 1, 0, 1)

    def test_unknown_style_falls_back_to_default(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        highlights = [[0, 5, "nonexistent_group"]]
        chunks = tree_sitter_to_text_chunks("hello", highlights, style)
        # Should fall back to default fg
        assert chunks[0].fg == RGBA(1, 1, 1, 1)

    def test_dotted_name_falls_back_to_base(self):
        """keyword.control should fall back to keyword style."""
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
        )
        highlights = [[0, 3, "keyword.control"]]
        chunks = tree_sitter_to_text_chunks("def", highlights, style)
        assert chunks[0].fg == RGBA(0, 0, 1, 1)  # falls back to keyword


# ---------------------------------------------------------------------------
# Conceal handling
# ---------------------------------------------------------------------------


class TestConcealHandling:
    def test_conceal_meta_hides_text(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        highlights = [[0, 1, "conceal", {"conceal": ""}]]
        chunks = tree_sitter_to_text_chunks("# Hello", highlights, style)
        # The "#" should be concealed (empty replacement = hidden)
        texts = [c.text for c in chunks]
        assert "#" not in texts[0] if texts else True

    def test_conceal_meta_replaces_text(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        highlights = [[0, 6, "entity", {"conceal": "<"}]]
        chunks = tree_sitter_to_text_chunks("&lt;  rest", highlights, style)
        texts = "".join(c.text for c in chunks)
        assert "<" in texts
        assert "&lt;" not in texts

    def test_conceal_group_name(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        highlights = [[0, 1, "conceal"]]
        chunks = tree_sitter_to_text_chunks("# Hello", highlights, style)
        texts = "".join(c.text for c in chunks)
        assert texts == " Hello"

    def test_conceal_with_space(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        highlights = [[0, 1, "conceal.with.space"]]
        chunks = tree_sitter_to_text_chunks("] rest", highlights, style)
        texts = "".join(c.text for c in chunks)
        assert texts == "  rest"  # ] replaced with space

    def test_conceal_disabled(self):
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        highlights = [[0, 1, "conceal", {"conceal": ""}]]
        chunks = tree_sitter_to_text_chunks(
            "# Hello",
            highlights,
            style,
            conceal_options={"enabled": False},
        )
        texts = "".join(c.text for c in chunks)
        assert texts == "# Hello"  # nothing hidden


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_adjacent_highlights_no_gap(self):
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            a={"fg": RGBA(1, 0, 0, 1)},
            b={"fg": RGBA(0, 1, 0, 1)},
        )
        highlights = [
            [0, 3, "a"],
            [3, 6, "b"],
        ]
        chunks = tree_sitter_to_text_chunks("aaabbb", highlights, style)
        assert len(chunks) == 2
        assert chunks[0].text == "aaa"
        assert chunks[0].fg == RGBA(1, 0, 0, 1)
        assert chunks[1].text == "bbb"
        assert chunks[1].fg == RGBA(0, 1, 0, 1)

    def test_nested_highlights(self):
        """Outer highlight spans more text than inner highlight."""
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            outer={"fg": RGBA(0, 0, 1, 1)},
        )
        style.register_style("inner", StyleDefinition(fg=RGBA(1, 0, 0, 1)))
        highlights = [
            [0, 10, "outer"],
            [3, 7, "inner"],
        ]
        chunks = tree_sitter_to_text_chunks("0123456789", highlights, style)
        # Should have: [0-3] outer, [3-7] inner wins, [7-10] outer
        assert len(chunks) == 3
        assert chunks[0].fg == RGBA(0, 0, 1, 1)  # outer
        assert chunks[1].fg == RGBA(1, 0, 0, 1)  # inner
        assert chunks[2].fg == RGBA(0, 0, 1, 1)  # outer

    def test_multiline_content(self):
        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
        )
        content = "def foo():\n    pass"
        highlights = [
            [0, 3, "keyword"],  # def
            [15, 19, "keyword"],  # pass
        ]
        chunks = tree_sitter_to_text_chunks(content, highlights, style)
        full_text = "".join(c.text for c in chunks)
        assert full_text == content

    def test_no_default_style(self):
        """SyntaxStyle with no 'default' key should still work."""
        style = _make_style(keyword={"fg": RGBA(0, 0, 1, 1)})
        highlights = [[0, 3, "keyword"]]
        chunks = tree_sitter_to_text_chunks("def foo", highlights, style)
        assert chunks[0].fg == RGBA(0, 0, 1, 1)
        assert chunks[1].fg is None  # no default


# ---------------------------------------------------------------------------
# Real tree-sitter integration tests
# ---------------------------------------------------------------------------


class TestRealTreeSitter:
    """Tests that use the real PyTreeSitterClient for end-to-end validation.

    These tests require the tree-sitter native packages to be installed.
    """

    def test_should_handle_unsupported_filetype_gracefully(self):
        """Unsupported filetypes should return empty highlights, not crash."""
        pytest.importorskip("tree_sitter")
        import asyncio
        from opentui.tree_sitter_client import PyTreeSitterClient  # type: ignore[reportMissingImports]

        async def _run():
            client = PyTreeSitterClient()
            result = await client.highlight_once("hello world", "cobol")
            return result

        result = asyncio.run(_run())
        assert result["highlights"] == []

        # Using empty highlights with tree_sitter_to_text_chunks should
        # produce a single chunk containing the original text.
        style = _make_style(default={"fg": RGBA(1, 1, 1, 1)})
        chunks = tree_sitter_to_text_chunks("hello world", result["highlights"], style)
        assert len(chunks) == 1
        assert chunks[0].text == "hello world"

    def test_should_preserve_original_text_content(self):
        """Concatenating all chunk texts must reproduce the original source."""
        pytest.importorskip("tree_sitter")
        pytest.importorskip("tree_sitter_python")
        import asyncio
        from opentui.tree_sitter_client import PyTreeSitterClient

        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
            function={"fg": RGBA(0, 1, 0, 1)},
            variable={"fg": RGBA(1, 0.5, 0, 1)},
            string={"fg": RGBA(0.8, 0, 0, 1)},
        )

        code = 'def foo(bar): return bar + "hello"'

        async def _run():
            client = PyTreeSitterClient()
            return await client.highlight_once(code, "python")

        result = asyncio.run(_run())
        chunks = tree_sitter_to_text_chunks(code, result["highlights"], style)
        reconstructed = "".join(c.text for c in chunks)
        assert reconstructed == code

    def test_should_apply_different_styles_to_different_syntax_elements(self):
        """Keywords, functions, and strings should each get their own style."""
        pytest.importorskip("tree_sitter")
        pytest.importorskip("tree_sitter_python")
        import asyncio
        from opentui.tree_sitter_client import PyTreeSitterClient

        keyword_fg = RGBA(0, 0, 1, 1)
        function_fg = RGBA(0, 1, 0, 1)
        string_fg = RGBA(0.8, 0, 0, 1)

        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": keyword_fg},
            function={"fg": function_fg},
            variable={"fg": RGBA(1, 0.5, 0, 1)},
            string={"fg": string_fg},
        )

        code = 'def greet(name): return "hello"'

        async def _run():
            client = PyTreeSitterClient()
            return await client.highlight_once(code, "python")

        result = asyncio.run(_run())
        chunks = tree_sitter_to_text_chunks(code, result["highlights"], style)

        # Build a mapping from text to fg color for easy lookup
        chunk_map = {c.text: c.fg for c in chunks}

        # "def" should have the keyword style
        assert chunk_map.get("def") == keyword_fg
        # "return" should also have the keyword style
        assert chunk_map.get("return") == keyword_fg
        # "greet" should have the function style (function or variable)
        greet_chunk = next((c for c in chunks if c.text == "greet"), None)
        assert greet_chunk is not None
        assert greet_chunk.fg in (function_fg, RGBA(1, 0.5, 0, 1))  # function or variable
        # '"hello"' should have the string style
        hello_chunk = next((c for c in chunks if '"hello"' in c.text), None)
        assert hello_chunk is not None
        assert hello_chunk.fg == string_fg

    def test_should_handle_template_literals_correctly_without_duplication(self):
        """Template literal text must not be duplicated in chunk output."""
        pytest.importorskip("tree_sitter")
        pytest.importorskip("tree_sitter_javascript")
        import asyncio
        from opentui.tree_sitter_client import PyTreeSitterClient

        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
            variable={"fg": RGBA(1, 0.5, 0, 1)},
            string={"fg": RGBA(0.8, 0, 0, 1)},
            punctuation={"fg": RGBA(0.5, 0.5, 0.5, 1)},
            operator={"fg": RGBA(1, 1, 0, 1)},
            embedded={"fg": RGBA(0.7, 0.7, 0, 1)},
        )

        code = "const x = `hello ${name} world`;"

        async def _run():
            client = PyTreeSitterClient()
            return await client.highlight_once(code, "javascript")

        result = asyncio.run(_run())
        chunks = tree_sitter_to_text_chunks(code, result["highlights"], style)
        full_text = "".join(c.text for c in chunks)

        # The reconstructed text must exactly match the original (no duplication)
        assert full_text == code

    def test_should_handle_complex_template_literals_with_multiple_expressions(self):
        """Template literals with multiple ${...} expressions must preserve text."""
        pytest.importorskip("tree_sitter")
        pytest.importorskip("tree_sitter_javascript")
        import asyncio
        from opentui.tree_sitter_client import PyTreeSitterClient

        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
            variable={"fg": RGBA(1, 0.5, 0, 1)},
            string={"fg": RGBA(0.8, 0, 0, 1)},
            punctuation={"fg": RGBA(0.5, 0.5, 0.5, 1)},
            operator={"fg": RGBA(1, 1, 0, 1)},
            embedded={"fg": RGBA(0.7, 0.7, 0, 1)},
            property={"fg": RGBA(0.3, 0.6, 0.9, 1)},
        )

        code = "const msg = `Hello ${user.name}, you have ${count} items`;"

        async def _run():
            client = PyTreeSitterClient()
            return await client.highlight_once(code, "javascript")

        result = asyncio.run(_run())
        chunks = tree_sitter_to_text_chunks(code, result["highlights"], style)
        full_text = "".join(c.text for c in chunks)

        # Text must be preserved exactly, with no duplication or loss
        assert full_text == code
        # There should be multiple chunks (at least the template string parts,
        # the two interpolation expressions, keyword, variable, etc.)
        assert len(chunks) > 5

    def test_should_correctly_highlight_template_literal_with_embedded_expressions(self):
        """Embedded expressions inside template literals get distinct styles."""
        pytest.importorskip("tree_sitter")
        pytest.importorskip("tree_sitter_javascript")
        import asyncio
        from opentui.tree_sitter_client import PyTreeSitterClient

        string_fg = RGBA(0.8, 0, 0, 1)
        variable_fg = RGBA(1, 0.5, 0, 1)
        punctuation_fg = RGBA(0.5, 0.5, 0.5, 1)

        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
            variable={"fg": variable_fg},
            string={"fg": string_fg},
            punctuation={"fg": punctuation_fg},
            operator={"fg": RGBA(1, 1, 0, 1)},
            embedded={"fg": RGBA(0.7, 0.7, 0, 1)},
        )

        code = "const x = `hello ${name} world`;"

        async def _run():
            client = PyTreeSitterClient()
            return await client.highlight_once(code, "javascript")

        result = asyncio.run(_run())
        chunks = tree_sitter_to_text_chunks(code, result["highlights"], style)

        # The template literal string parts should have the string fg color
        hello_chunk = next((c for c in chunks if "`hello " in c.text), None)
        assert hello_chunk is not None
        assert hello_chunk.fg == string_fg

        world_chunk = next((c for c in chunks if " world`" in c.text), None)
        assert world_chunk is not None
        assert world_chunk.fg == string_fg

        # The variable inside ${...} should have the variable fg color
        name_chunk = next((c for c in chunks if c.text == "name"), None)
        assert name_chunk is not None
        assert name_chunk.fg == variable_fg

        # The ${ and } delimiters should have punctuation style (via fallback
        # from punctuation.special to punctuation)
        dollar_brace_chunk = next((c for c in chunks if c.text == "${"), None)
        assert dollar_brace_chunk is not None
        assert dollar_brace_chunk.fg == punctuation_fg

    def test_should_work_with_real_tree_sitter_output_containing_dot_delimited_groups(self):
        """Dot-delimited groups like punctuation.special fall back to base style."""
        pytest.importorskip("tree_sitter")
        pytest.importorskip("tree_sitter_javascript")
        import asyncio
        from opentui.tree_sitter_client import PyTreeSitterClient

        punctuation_fg = RGBA(0.5, 0.5, 0.5, 1)

        style = _make_style(
            default={"fg": RGBA(1, 1, 1, 1)},
            keyword={"fg": RGBA(0, 0, 1, 1)},
            variable={"fg": RGBA(1, 0.5, 0, 1)},
            string={"fg": RGBA(0.8, 0, 0, 1)},
            punctuation={"fg": punctuation_fg},
            operator={"fg": RGBA(1, 1, 0, 1)},
            embedded={"fg": RGBA(0.7, 0.7, 0, 1)},
        )

        code = "const x = `hello ${name}`;"

        async def _run():
            client = PyTreeSitterClient()
            return await client.highlight_once(code, "javascript")

        result = asyncio.run(_run())
        highlights = result["highlights"]

        # Verify that tree-sitter actually produces dot-delimited group names
        group_names = [h[2] for h in highlights]
        dot_groups = [g for g in group_names if "." in g]
        assert len(dot_groups) > 0, (
            "Expected tree-sitter to produce dot-delimited groups like "
            f"'punctuation.special', got: {group_names}"
        )

        # Convert to chunks and verify dot-delimited groups get the base style
        chunks = tree_sitter_to_text_chunks(code, highlights, style)
        full_text = "".join(c.text for c in chunks)
        assert full_text == code

        # Find chunks that were styled via a dot-delimited group fallback;
        # punctuation.special, punctuation.delimiter, punctuation.bracket
        # should all resolve to the punctuation base style.
        punc_chunks = [c for c in chunks if c.fg == punctuation_fg and c.text in ("${", "}", ";")]
        assert len(punc_chunks) > 0, (
            "Expected dot-delimited groups (e.g. punctuation.special) to "
            "fall back to punctuation style"
        )
