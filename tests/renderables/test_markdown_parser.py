"""Port of upstream markdown-parser.test.ts.

Upstream: packages/core/src/renderables/__tests__/markdown-parser.test.ts
Tests ported: 16/16 (0 skipped)
"""

from unittest.mock import patch

import pytest

from opentui.markdown_parser import ParseState, parse_markdown_incremental
import opentui.markdown_parser as mp


class TestMarkdownParser:
    """Maps to top-level tests in markdown-parser.test.ts."""

    def test_first_parse_returns_all_tokens(self):
        """Maps to test("first parse returns all tokens")."""
        state = parse_markdown_incremental("# Hello\n\nParagraph", None)

        assert state.content == "# Hello\n\nParagraph"
        assert len(state.tokens) > 0
        assert state.tokens[0].type == "heading"

    def test_reuses_unchanged_tokens_when_appending_content(self):
        """Maps to test("reuses unchanged tokens when appending content")."""
        state1 = parse_markdown_incremental("# Hello\n\nPara 1\n\n", None)
        state2 = parse_markdown_incremental(
            "# Hello\n\nPara 1\n\nPara 2", state1, 0
        )  # No trailing unstable

        # First tokens should be same object reference (reused)
        assert state2.tokens[0] is state1.tokens[0]  # heading
        assert state2.tokens[1] is state1.tokens[1]  # space or paragraph

    def test_trailing_unstable_tokens_are_re_parsed(self):
        """Maps to test("trailing unstable tokens are re-parsed")."""
        state1 = parse_markdown_incremental("# Hello\n\nPara 1\n\n", None)
        state2 = parse_markdown_incremental("# Hello\n\nPara 1\n\nPara 2", state1, 2)

        # With trailingUnstable=2, last 2 tokens from state1 should be re-parsed
        # state1 has tokens and with trailing=2, some are kept stable
        assert len(state2.tokens) > 0
        # The new tokens are re-parsed versions
        assert state2.tokens[0].type == "heading"

    def test_handles_content_that_diverges_from_start(self):
        """Maps to test("handles content that diverges from start")."""
        state1 = parse_markdown_incremental("# Hello", None)
        state2 = parse_markdown_incremental("## World", state1)

        # Content changed from start, no tokens can be reused
        assert state2.tokens[0] is not state1.tokens[0]
        assert state2.tokens[0].type == "heading"

    def test_handles_empty_content(self):
        """Maps to test("handles empty content")."""
        state = parse_markdown_incremental("", None)

        assert state.content == ""
        assert state.tokens == []

    def test_handles_empty_previous_state(self):
        """Maps to test("handles empty previous state")."""
        prev_state = ParseState(content="", tokens=[])
        state = parse_markdown_incremental("# Hello", prev_state)

        assert len(state.tokens) > 0
        assert state.tokens[0].type == "heading"

    def test_handles_content_truncation(self):
        """Maps to test("handles content truncation")."""
        state1 = parse_markdown_incremental("# Hello\n\nPara 1\n\nPara 2", None)
        state2 = parse_markdown_incremental("# Hello", state1)

        assert len(state2.tokens) == 1
        assert state2.tokens[0].type == "heading"

    def test_handles_partial_token_match(self):
        """Maps to test("handles partial token match")."""
        state1 = parse_markdown_incremental("# Hello World", None)
        state2 = parse_markdown_incremental("# Hello", state1)

        # Token at start doesn't match exactly, so it's re-parsed
        assert state2.tokens[0] is not state1.tokens[0]

    def test_handles_multiple_stable_tokens_with_explicit_boundaries(self):
        """Maps to test("handles multiple stable tokens with explicit boundaries")."""
        # Use content with clear token boundaries that won't change
        content1 = "Para 1\n\nPara 2\n\nPara 3\n\n"
        state1 = parse_markdown_incremental(content1, None)

        content2 = content1 + "Para 4"
        state2 = parse_markdown_incremental(content2, state1, 0)

        # All original tokens should be reused (same object reference)
        for i in range(len(state1.tokens)):
            assert state2.tokens[i] is state1.tokens[i]
        # And there should be a new token at the end
        assert len(state2.tokens) == len(state1.tokens) + 1

    def test_code_blocks_are_parsed_correctly(self):
        """Maps to test("code blocks are parsed correctly")."""
        state = parse_markdown_incremental("```js\nconst x = 1;\n```", None)

        code_token = next((t for t in state.tokens if t.type == "code"), None)
        assert code_token is not None
        assert code_token.lang == "js"

    def test_streaming_scenario_with_incremental_typing(self):
        """Maps to test("streaming scenario with incremental typing")."""
        state = None

        # Simulate typing character by character
        state = parse_markdown_incremental("#", state, 2)
        assert len(state.tokens) == 1

        state = parse_markdown_incremental("# ", state, 2)
        state = parse_markdown_incremental("# H", state, 2)
        state = parse_markdown_incremental("# He", state, 2)
        state = parse_markdown_incremental("# Hel", state, 2)
        state = parse_markdown_incremental("# Hell", state, 2)
        state = parse_markdown_incremental("# Hello", state, 2)

        assert state.tokens[0].type == "heading"
        assert state.tokens[0].text == "Hello"

    def test_token_identity_is_preserved_for_stable_tokens(self):
        """Maps to test("token identity is preserved for stable tokens")."""
        # Create initial state with multiple paragraphs
        state1 = parse_markdown_incremental("A\n\nB\n\nC\n\n", None)

        # Append content - with trailingUnstable=0, all tokens should be reused
        state2 = parse_markdown_incremental("A\n\nB\n\nC\n\nD", state1, 0)

        # Verify token identity (same object reference)
        assert state2.tokens[0] is state1.tokens[0]
        assert state2.tokens[1] is state1.tokens[1]
        assert state2.tokens[2] is state1.tokens[2]

    def test_trailing_unstable_re_parses_trailing_table_when_new_rows_are_appended(
        self,
    ):
        """Maps to test("trailingUnstable re-parses trailing table when new rows are appended")."""
        content1 = "| A |\n|---|\n| 1 |"
        state1 = parse_markdown_incremental(content1, None, 2)
        table1 = next((t for t in state1.tokens if t.type == "table"), None)

        assert table1 is not None
        assert len(table1.rows) == 1

        content2 = "| A |\n|---|\n| 1 |\n| 2 |"
        state2 = parse_markdown_incremental(content2, state1, 2)
        table2 = next((t for t in state2.tokens if t.type == "table"), None)

        assert table2 is not None
        assert len(table2.rows) == 2
        assert table2 is not table1

    def test_trailing_unstable_updates_trailing_table_rows_in_multi_table_markdown(
        self,
    ):
        """Maps to test("trailingUnstable updates trailing table rows in multi-table markdown")."""
        table1_markdown = "| T1 |\n|---|\n| a |\n| b |"
        table2_markdown = "| T2 |\n|---|\n| 1 |\n| 2 |"

        content1 = f"{table1_markdown}\n\n{table2_markdown}"
        state1 = parse_markdown_incremental(content1, None, 2)
        tables1 = [t for t in state1.tokens if t.type == "table"]

        assert len(tables1) == 2
        assert len(tables1[0].rows) == 2
        assert len(tables1[1].rows) == 2

        content2 = f"{table1_markdown}\n\n{table2_markdown}\n| 3 |"
        state2 = parse_markdown_incremental(content2, state1, 2)
        tables2 = [t for t in state2.tokens if t.type == "table"]

        assert len(tables2) == 2
        assert len(tables2[0].rows) == 2
        assert tables2[1] is not tables1[1]
        assert len(tables2[1].rows) == 3

    def test_falls_back_to_full_re_parse_when_incremental_tail_parse_fails(
        self,
    ):
        """Maps to test("falls back to full re-parse when incremental tail parse fails")."""
        content1 = "| A |\n|---|\n| 1 |"
        content2 = "| A |\n|---|\n| 1 |\n| 2 |"
        state1 = parse_markdown_incremental(content1, None, 2)

        original_lex = mp.lex
        lex_calls = 0

        def failing_lex_first_call(src):
            nonlocal lex_calls
            lex_calls += 1
            if lex_calls == 1:
                raise Exception("incremental tail parse failed")
            return original_lex(src)

        mp.lex = failing_lex_first_call
        try:
            state2 = parse_markdown_incremental(content2, state1, 2)
            table = next((t for t in state2.tokens if t.type == "table"), None)

            assert lex_calls >= 2
            assert table is not None
            assert len(table.rows) == 2
        finally:
            mp.lex = original_lex

    def test_returns_empty_token_list_when_both_incremental_and_full_parse_fail(
        self,
    ):
        """Maps to test("returns empty token list when both incremental and full parse fail")."""
        content1 = "| A |\n|---|\n| 1 |"
        content2 = "| A |\n|---|\n| 1 |\n| 2 |"
        state1 = parse_markdown_incremental(content1, None, 2)

        original_lex = mp.lex

        def always_failing_lex(src):
            raise Exception("parse failed")

        mp.lex = always_failing_lex
        try:
            state2 = parse_markdown_incremental(content2, state1, 2)
            assert state2.tokens == []
        finally:
            mp.lex = original_lex
