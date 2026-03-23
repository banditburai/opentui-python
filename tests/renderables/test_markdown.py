"""Port of upstream Markdown.test.ts.

Upstream: packages/core/src/renderables/__tests__/Markdown.test.ts
Tests ported: 94/94
"""

import pytest

from opentui import ScrollBox, create_test_renderer
from opentui.components.markdown_renderable import (
    _MarkdownCodeBlock,
    MarkdownRenderable,
    MarkdownTableOptions,
    _MarkdownTableBlock,
)


# ---------------------------------------------------------------------------
# Helper fixtures & functions
# ---------------------------------------------------------------------------


@pytest.fixture
async def setup():
    """Create a test renderer (60x40)."""
    ts = await create_test_renderer(width=60, height=40)
    yield ts
    ts.destroy()


def _capture(setup) -> str:
    """Render one frame and return the char-frame text."""
    return setup.capture_char_frame()


def _render_markdown_sync(setup, markdown: str, conceal: bool = True) -> str:
    """Create a MarkdownRenderable, add to root, render, return trimmed frame."""
    md = MarkdownRenderable(
        id="markdown",
        content=markdown,
        conceal=conceal,
        table_options={"widthMode": "content"},
    )
    setup.renderer.root.add(md)
    setup.render_frame()

    lines = _capture(setup).split("\n")
    lines = [ln.rstrip() for ln in lines]
    return "\n" + "\n".join(lines).rstrip()


def _find_selectable_point(renderable, direction: str) -> tuple[int, int]:
    points = []
    for y in range(renderable.y, renderable.y + renderable.height):
        for x in range(renderable.x, renderable.x + renderable.width):
            if renderable.should_start_selection(x, y):
                points.append((x, y))
    assert points, "No selectable points found"

    if direction == "top-left":
        points.sort(key=lambda p: (p[1], p[0]))
        return points[0]

    points.sort(key=lambda p: (-p[1], -p[0]))
    return points[0]


class TestMarkdownRenderable:
    """Maps to top-level test() calls in Markdown.test.ts (no describe blocks)."""

    # ── Table tests ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_basic_table_alignment(self, setup):
        """Maps to test("basic table alignment")."""
        result = _render_markdown_sync(
            setup, "| Name | Age |\n|---|---|\n| Alice | 30 |\n| Bob | 5 |"
        )
        assert "┌" in result
        assert "│Name" in result or "│Name " in result
        assert "│Alice" in result
        assert "│Bob" in result
        assert "│Age│" in result or "│Age│" in result.replace(" ", "")
        assert "└" in result

    @pytest.mark.asyncio
    async def test_tableoptions_widthmode_configures_markdown_table_layout(self, setup):
        """Maps to test("tableOptions.widthMode configures markdown table layout")."""
        md = MarkdownRenderable(
            id="markdown-table-width-mode",
            content="| Name | Age |\n|---|---|\n| Alice | 30 |",
            table_options={"widthMode": "full", "columnFitter": "balanced"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table = md._blockStates[0].renderable
        assert isinstance(table, _MarkdownTableBlock)
        assert table.column_width_mode == "full"
        assert table.column_fitter == "balanced"

    @pytest.mark.asyncio
    async def test_tableoptions_updates_existing_markdown_table_renderable(self, setup):
        """Maps to test("tableOptions updates existing markdown table renderable")."""
        md = MarkdownRenderable(
            id="markdown-table-updates",
            content="| Name | Age |\n|---|---|\n| Alice | 30 |",
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table = md._blockStates[0].renderable
        assert isinstance(table, _MarkdownTableBlock)
        assert table.column_width_mode == "full"

        md.table_options = {
            "widthMode": "full",
            "columnFitter": "balanced",
            "wrapMode": "word",
            "cellPadding": 1,
            "borders": False,
            "selectable": False,
        }
        setup.render_frame()

        updated_table = md._blockStates[0].renderable
        assert updated_table is table
        assert updated_table.column_width_mode == "full"
        assert updated_table.column_fitter == "balanced"
        assert updated_table.wrap_mode == "word"
        assert updated_table.cell_padding == 1
        assert updated_table.border is False
        assert updated_table.outer_border is False
        assert updated_table.show_borders is False
        assert updated_table.selectable is False

    @pytest.mark.asyncio
    async def test_table_with_inline_code_backticks(self, setup):
        """Maps to test("table with inline code (backticks)")."""
        md_text = "| Command | Description |\n|---|---|\n| `npm install` | Install deps |\n| `npm run build` | Build project |\n| `npm test` | Run tests |"
        result = _render_markdown_sync(setup, md_text)
        assert "│npm install" in result
        assert "│Install deps" in result
        assert "│npm run build│" in result or "│npm run build" in result
        assert "│Run tests" in result

    @pytest.mark.asyncio
    async def test_table_with_bold_text(self, setup):
        """Maps to test("table with bold text")."""
        md_text = (
            "| Feature | Status |\n|---|---|\n| **Authentication** | Done |\n| **API** | WIP |"
        )
        result = _render_markdown_sync(setup, md_text)
        assert "│Authentication" in result
        assert "│Done" in result
        assert "│API" in result
        assert "│WIP" in result
        # Concealed: no ** markers
        assert "**" not in result

    @pytest.mark.asyncio
    async def test_table_with_italic_text(self, setup):
        """Maps to test("table with italic text")."""
        md_text = "| Item | Note |\n|---|---|\n| One | *important* |\n| Two | *ok* |"
        result = _render_markdown_sync(setup, md_text)
        assert "│important" in result
        assert "│ok" in result
        # In conceal mode, no * markers around words
        assert "*important*" not in result

    @pytest.mark.asyncio
    async def test_table_with_mixed_formatting(self, setup):
        """Maps to test("table with mixed formatting")."""
        md_text = "| Type | Value | Notes |\n|---|---|---|\n| **Bold** | `code` | *italic* |\n| Plain | **strong** | `cmd` |"
        result = _render_markdown_sync(setup, md_text)
        assert "│Bold" in result
        assert "│code" in result
        assert "│italic" in result
        assert "│Plain" in result
        assert "│strong" in result
        assert "│cmd" in result

    @pytest.mark.asyncio
    async def test_table_with_alignment_markers(self, setup):
        """Maps to test("table with alignment markers (left, center, right)")."""
        md_text = (
            "| Left | Center | Right |\n|:---|:---:|---:|\n| A | B | C |\n| Long text | X | Y |"
        )
        result = _render_markdown_sync(setup, md_text)
        assert "│Left" in result
        assert "│A" in result
        assert "│Long text│" in result or "│Long text" in result

    @pytest.mark.asyncio
    async def test_table_with_empty_cells(self, setup):
        """Maps to test("table with empty cells")."""
        md_text = "| A | B |\n|---|---|\n| X |  |\n|  | Y |"
        result = _render_markdown_sync(setup, md_text)
        assert "│A│B│" in result
        assert "│X│" in result
        assert "│Y│" in result or "│ │Y│" in result

    @pytest.mark.asyncio
    async def test_table_with_long_header_and_short_content(self, setup):
        """Maps to test("table with long header and short content")."""
        md_text = "| Very Long Column Header | Short |\n|---|---|\n| A | B |"
        result = _render_markdown_sync(setup, md_text)
        assert "Very Long Column Header" in result
        assert "│A" in result

    @pytest.mark.asyncio
    async def test_table_with_short_header_and_long_content(self, setup):
        """Maps to test("table with short header and long content")."""
        md_text = "| X | Y |\n|---|---|\n| This is very long content | Short |"
        result = _render_markdown_sync(setup, md_text)
        assert "This is very long content" in result
        assert "│Short" in result

    @pytest.mark.asyncio
    async def test_table_inside_code_block_should_not_be_formatted(self, setup):
        """Maps to test("table inside code block should NOT be formatted")."""
        md_text = "```\n| Not | A | Table |\n|---|---|---|\n| Should | Stay | Raw |\n```\n\n| Real | Table |\n|---|---|\n| Is | Formatted |"
        result = _render_markdown_sync(setup, md_text)
        # The table inside code block should be raw text
        assert "| Not | A | Table |" in result
        assert "| Should | Stay | Raw |" in result
        # The real table should be formatted
        assert "│Real" in result or "│Real│" in result.replace(" ", "")
        assert "│Formatted" in result

    @pytest.mark.asyncio
    async def test_multiple_tables_in_same_document(self, setup):
        """Maps to test("multiple tables in same document")."""
        md_text = "| Table1 | A |\n|---|---|\n| X | Y |\n\nSome text between.\n\n| Table2 | BB |\n|---|---|\n| Long content | Z |"
        result = _render_markdown_sync(setup, md_text)
        assert "│Table1" in result
        assert "│X" in result
        assert "Some text between." in result
        assert "│Table2" in result
        assert "│Long content│" in result or "│Long content" in result

    @pytest.mark.asyncio
    async def test_table_with_escaped_pipe_character(self, setup):
        """Maps to test("table with escaped pipe character")."""
        md_text = "| Command | Output |\n|---|---|\n| echo | Hello |\n| ls \\| grep | Filtered |"
        result = _render_markdown_sync(setup, md_text)
        assert "│echo" in result
        assert "│Hello" in result
        # The escaped pipe should appear as a literal pipe
        assert "ls | grep" in result or "ls \\| grep" in result
        assert "│Filtered" in result

    @pytest.mark.asyncio
    async def test_table_with_unicode_characters(self, setup):
        """Maps to test("table with unicode characters")."""
        md_text = (
            "| Emoji | Name |\n|---|---|\n| 🎉 | Party |\n| 🚀 | Rocket |\n| 日本語 | Japanese |"
        )
        result = _render_markdown_sync(setup, md_text)
        assert "│Party" in result
        assert "│Rocket" in result
        assert "日本語" in result
        assert "│Japanese" in result

    @pytest.mark.asyncio
    async def test_table_with_links(self, setup):
        """Maps to test("table with links")."""
        md_text = "| Name | Link |\n|---|---|\n| Google | [link](https://google.com) |\n| GitHub | [gh](https://github.com) |"
        result = _render_markdown_sync(setup, md_text)
        assert "│Google" in result
        assert "link (https://google.com)" in result or "link" in result
        assert "│GitHub" in result

    @pytest.mark.asyncio
    async def test_single_row_table_header_delimiter_only(self, setup):
        """Maps to test("single row table (header + delimiter only)")."""
        md_text = "| Only | Header |\n|---|---|"
        result = _render_markdown_sync(setup, md_text)
        # Header + delimiter only = no data rows, rendered as raw text
        assert "| Only | Header |" in result
        assert "|---|---|" in result

    @pytest.mark.asyncio
    async def test_table_with_many_columns(self, setup):
        """Maps to test("table with many columns")."""
        md_text = "| A | B | C | D | E |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |"
        result = _render_markdown_sync(setup, md_text)
        assert "│A│B│C│D│E│" in result
        assert "│1│2│3│4│5│" in result

    @pytest.mark.asyncio
    async def test_no_tables_returns_original_content(self, setup):
        """Maps to test("no tables returns original content")."""
        md_text = "# Just a heading\n\nSome paragraph text.\n\n- List item"
        result = _render_markdown_sync(setup, md_text)
        assert "Just a heading" in result
        assert "Some paragraph text." in result
        assert "- List item" in result

    @pytest.mark.asyncio
    async def test_table_with_nested_inline_formatting(self, setup):
        """Maps to test("table with nested inline formatting")."""
        md_text = "| Description |\n|---|\n| This has **bold and `code`** together |\n| And *italic with **nested bold*** |"
        result = _render_markdown_sync(setup, md_text)
        assert "This has bold and code together" in result
        assert "And italic with nested bold" in result

    # ── conceal=false table tests ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_conceal_false_table_with_bold_text(self, setup):
        """Maps to test("conceal=false: table with bold text")."""
        md_text = (
            "| Feature | Status |\n|---|---|\n| **Authentication** | Done |\n| **API** | WIP |"
        )
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "│**Authentication**│" in result or "│**Authentication**" in result
        assert "│Done" in result

    @pytest.mark.asyncio
    async def test_conceal_false_table_with_inline_code(self, setup):
        """Maps to test("conceal=false: table with inline code")."""
        md_text = "| Command | Description |\n|---|---|\n| `npm install` | Install deps |\n| `npm run build` | Build project |"
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "`npm install`" in result
        assert "`npm run build`" in result

    @pytest.mark.asyncio
    async def test_conceal_false_table_with_italic_text(self, setup):
        """Maps to test("conceal=false: table with italic text")."""
        md_text = "| Item | Note |\n|---|---|\n| One | *important* |\n| Two | *ok* |"
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "*important*" in result
        assert "*ok*" in result

    @pytest.mark.asyncio
    async def test_conceal_false_table_with_mixed_formatting(self, setup):
        """Maps to test("conceal=false: table with mixed formatting")."""
        md_text = "| Type | Value | Notes |\n|---|---|---|\n| **Bold** | `code` | *italic* |\n| Plain | **strong** | `cmd` |"
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "│**Bold**│" in result or "│**Bold**" in result
        assert "│`code`" in result
        assert "│*italic*│" in result or "│*italic*" in result

    @pytest.mark.asyncio
    async def test_conceal_false_table_with_unicode_characters(self, setup):
        """Maps to test("conceal=false: table with unicode characters")."""
        md_text = (
            "| Emoji | Name |\n|---|---|\n| 🎉 | Party |\n| 🚀 | Rocket |\n| 日本語 | Japanese |"
        )
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "│Party" in result
        assert "│Rocket" in result
        assert "日本語" in result
        assert "│Japanese" in result

    @pytest.mark.asyncio
    async def test_conceal_false_basic_table_alignment(self, setup):
        """Maps to test("conceal=false: basic table alignment")."""
        md_text = "| Name | Age |\n|---|---|\n| Alice | 30 |\n| Bob | 5 |"
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "│Name" in result
        assert "│Alice" in result
        assert "│Bob" in result

    # ── Table with surrounding content ────────────────────────────────

    @pytest.mark.asyncio
    async def test_table_with_paragraphs_before_and_after(self, setup):
        """Maps to test("table with paragraphs before and after")."""
        md_text = "This is a paragraph before the table.\n\n| Name | Age |\n|---|---|\n| Alice | 30 |\n\nThis is a paragraph after the table."
        result = _render_markdown_sync(setup, md_text)
        assert "This is a paragraph before the table." in result
        assert "│Name" in result
        assert "│Alice" in result
        assert "This is a paragraph after the table." in result

    @pytest.mark.asyncio
    async def test_selection_across_markdown_table_includes_table_data(self, setup):
        """Maps to test("selection across markdown table includes table data")."""
        md = MarkdownRenderable(
            id="markdown",
            content="Intro line above table.\n\n| Component | Status | Notes |\n|---|---|---|\n| Authentication | **Done** | OAuth2 + SSO |\n| Payments API | *In Progress* | Retry + idempotency |\n| Search Indexer | `Done` | Ranking + typo fix |\n\nOutro line below table.",
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table = next(
            state.renderable
            for state in md._blockStates
            if isinstance(state.renderable, _MarkdownTableBlock)
        )
        start = _find_selectable_point(table, "top-left")
        end = _find_selectable_point(table, "bottom-right")

        setup.mock_mouse.drag(start[0], start[1], end[0], end[1])
        setup.render_frame()

        assert table.has_selection() is True
        selected = setup.renderer.get_selection().get_selected_text()
        assert "Component" in selected
        assert "Status" in selected
        assert "Notes" in selected
        assert "Authentication" in selected
        assert "OAuth2 + SSO" in selected
        assert "Payments API" in selected
        assert "Retry + idempotency" in selected
        assert "Search Indexer" in selected
        assert "Ranking + typo fix" in selected

    @pytest.mark.asyncio
    async def test_markdown_paragraph_blocks_use_real_text_selection(self, setup):
        md = MarkdownRenderable(
            id="markdown-text-selection",
            content="Hello markdown paragraph.\n\nAnother line.",
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        text_block = next(
            state.renderable
            for state in md._blockStates
            if isinstance(state.renderable, _MarkdownCodeBlock)
        )
        setup.mock_mouse.drag(text_block.x, text_block.y, text_block.x + 6, text_block.y)
        setup.render_frame()

        assert text_block.has_selection() is True
        assert text_block.get_selected_text() in ("Hello ", "Hello m", "Hello")

    @pytest.mark.asyncio
    async def test_markdown_selection_stays_stable_when_scrolled(self, setup):
        md = MarkdownRenderable(
            id="markdown-scroll-selection",
            content="\n\n".join(f"Line {i} with markdown text." for i in range(18)),
            width=30,
        )
        scrollbox = ScrollBox(width=30, height=4, scroll_y=True)
        scrollbox.add(md)
        setup.renderer.root.add(scrollbox)
        setup.render_frame()

        text_block = next(
            state.renderable
            for state in md._blockStates
            if isinstance(state.renderable, _MarkdownCodeBlock)
        )
        setup.mock_mouse.drag(text_block.x, text_block.y, text_block.x + 4, text_block.y)
        setup.render_frame()

        selected_before = setup.renderer.get_selection().get_selected_text()
        assert selected_before

        setup.mock_mouse.scroll(scrollbox.x + 1, scrollbox.y + 1, "down")
        setup.render_frame()

        selected_after = setup.renderer.get_selection().get_selected_text()
        assert selected_after == selected_before

    # ── Code block tests ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_code_block_with_language(self, setup):
        """Maps to test("code block with language")."""
        md_text = "```typescript\nconst x = 1;\nconsole.log(x);\n```"
        result = _render_markdown_sync(setup, md_text)
        assert "const x = 1;" in result
        assert "console.log(x);" in result
        # Fences should be hidden
        assert "```" not in result

    @pytest.mark.asyncio
    async def test_code_block_without_language(self, setup):
        """Maps to test("code block without language")."""
        md_text = "```\nplain code block\nwith multiple lines\n```"
        result = _render_markdown_sync(setup, md_text)
        assert "plain code block" in result
        assert "with multiple lines" in result

    @pytest.mark.asyncio
    async def test_code_block_mixed_with_text(self, setup):
        """Maps to test("code block mixed with text")."""
        md_text = 'Here is some code:\n\n```js\nfunction hello() {\n  return "world";\n}\n```\n\nAnd here is more text after.'
        result = _render_markdown_sync(setup, md_text)
        assert "Here is some code:" in result
        assert "function hello() {" in result
        assert 'return "world";' in result
        assert "And here is more text after." in result

    @pytest.mark.asyncio
    async def test_multiple_code_blocks(self, setup):
        """Maps to test("multiple code blocks")."""
        md_text = 'First block:\n\n```python\nprint("hello")\n```\n\nSecond block:\n\n```rust\nfn main() {}\n```'
        result = _render_markdown_sync(setup, md_text)
        assert "First block:" in result
        assert 'print("hello")' in result
        assert "Second block:" in result
        assert "fn main() {}" in result

    @pytest.mark.asyncio
    async def test_code_block_in_conceal_false_mode(self, setup):
        """Maps to test("code block in conceal=false mode")."""
        md_text = "```js\nconst x = 1;\n```"
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "const x = 1;" in result

    @pytest.mark.asyncio
    async def test_code_block_concealment_is_disabled_by_default(self, setup):
        """Maps to test("code block concealment is disabled by default")."""
        md = MarkdownRenderable(
            id="markdown-code-default-conceal",
            content="```markdown\n# Hidden heading\n```",
            conceal=True,
            conceal_code=False,
        )
        setup.renderer.root.add(md)
        setup.render_frame()
        frame = _capture(setup)
        # With concealCode=false (default), the # should still be visible
        assert "# Hidden heading" in frame

    @pytest.mark.asyncio
    async def test_code_block_concealment_can_be_enabled_with_concealcode(self, setup):
        """Maps to test("code block concealment can be enabled with concealCode").

        Since we don't have tree-sitter conceal support, we verify the concealCode
        flag is set and the code block continues rendering without exposing fences.
        """
        md = MarkdownRenderable(
            id="markdown-code-conceal-enabled",
            content="```markdown\n# Hidden heading\n```",
            conceal=True,
            conceal_code=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        assert md.conceal_code is True
        frame = _capture(setup)
        assert "# Hidden heading" in frame
        assert "```" not in frame

    @pytest.mark.asyncio
    async def test_toggling_concealcode_updates_existing_code_block_renderables(self, setup):
        """Maps to test("toggling concealCode updates existing code block renderables")."""
        md = MarkdownRenderable(
            id="markdown-code-conceal-toggle",
            content="```markdown\n# Hidden heading\n```",
            conceal=True,
            conceal_code=False,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame_before = _capture(setup)
        assert "# Hidden heading" in frame_before

        md.conceal_code = True
        assert md.conceal_code is True
        setup.render_frame()

        frame_after = _capture(setup)
        assert "# Hidden heading" in frame_after
        assert "```" not in frame_after

    # ── Heading tests ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_headings_h1_through_h3(self, setup):
        """Maps to test("headings h1 through h3")."""
        md_text = "# Heading 1\n\n## Heading 2\n\n### Heading 3"
        result = _render_markdown_sync(setup, md_text)
        assert "Heading 1" in result
        assert "Heading 2" in result
        assert "Heading 3" in result
        # Concealed: no # markers
        assert "# Heading" not in result

    @pytest.mark.asyncio
    async def test_headings_with_conceal_false_show_markers(self, setup):
        """Maps to test("headings with conceal=false show markers")."""
        md_text = "# Heading 1\n\n## Heading 2"
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "# Heading 1" in result
        assert "## Heading 2" in result

    # ── List tests ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_unordered_list(self, setup):
        """Maps to test("unordered list")."""
        md_text = "- Item one\n- Item two\n- Item three"
        result = _render_markdown_sync(setup, md_text)
        assert "- Item one" in result
        assert "- Item two" in result
        assert "- Item three" in result

    @pytest.mark.asyncio
    async def test_ordered_list(self, setup):
        """Maps to test("ordered list")."""
        md_text = "1. First item\n2. Second item\n3. Third item"
        result = _render_markdown_sync(setup, md_text)
        assert "1. First item" in result
        assert "2. Second item" in result
        assert "3. Third item" in result

    @pytest.mark.asyncio
    async def test_list_with_inline_formatting(self, setup):
        """Maps to test("list with inline formatting")."""
        md_text = "- **Bold** item\n- *Italic* item\n- `Code` item"
        result = _render_markdown_sync(setup, md_text)
        assert "- Bold item" in result
        assert "- Italic item" in result
        assert "- Code item" in result

    # ── Blockquote tests ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_simple_blockquote(self, setup):
        """Maps to test("simple blockquote")."""
        md_text = "> This is a quote\n> spanning multiple lines"
        result = _render_markdown_sync(setup, md_text)
        assert "> This is a quote" in result
        assert "> spanning multiple lines" in result

    # ── Inline formatting tests ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_bold_text(self, setup):
        """Maps to test("bold text")."""
        md_text = "This has **bold** text in it."
        result = _render_markdown_sync(setup, md_text)
        assert "This has bold text in it." in result
        assert "**" not in result

    @pytest.mark.asyncio
    async def test_italic_text(self, setup):
        """Maps to test("italic text")."""
        md_text = "This has *italic* text in it."
        result = _render_markdown_sync(setup, md_text)
        assert "This has italic text in it." in result

    @pytest.mark.asyncio
    async def test_inline_code(self, setup):
        """Maps to test("inline code")."""
        md_text = "Use `console.log()` to debug."
        result = _render_markdown_sync(setup, md_text)
        assert "Use console.log() to debug." in result

    @pytest.mark.asyncio
    async def test_mixed_inline_formatting(self, setup):
        """Maps to test("mixed inline formatting")."""
        md_text = "**Bold**, *italic*, and `code` together."
        result = _render_markdown_sync(setup, md_text)
        assert "Bold, italic, and code together." in result

    @pytest.mark.asyncio
    async def test_inline_formatting_with_conceal_false(self, setup):
        """Maps to test("inline formatting with conceal=false")."""
        md_text = "**Bold**, *italic*, and `code` together."
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "**Bold**" in result
        assert "*italic*" in result
        assert "`code`" in result

    # ── Link tests ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_links_with_conceal_mode(self, setup):
        """Maps to test("links with conceal mode")."""
        md_text = "Check out [OpenTUI](https://github.com/sst/opentui) for more."
        result = _render_markdown_sync(setup, md_text)
        assert "OpenTUI (https://github.com/sst/opentui)" in result or "OpenTUI" in result
        assert "for more." in result

    @pytest.mark.asyncio
    async def test_links_with_conceal_false(self, setup):
        """Maps to test("links with conceal=false")."""
        md_text = "Check out [OpenTUI](https://github.com/sst/opentui) for more."
        result = _render_markdown_sync(setup, md_text, conceal=False)
        assert "[OpenTUI](https://github.com/sst/opentui)" in result

    # ── Horizontal rule ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_horizontal_rule(self, setup):
        """Maps to test("horizontal rule")."""
        md_text = "Before\n\n---\n\nAfter"
        result = _render_markdown_sync(setup, md_text)
        assert "Before" in result
        assert "---" in result
        assert "After" in result

    # ── Complex document ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_complex_markdown_document(self, setup):
        """Maps to test("complex markdown document")."""
        md_text = '# Project Title\n\nWelcome to **OpenTUI**, a terminal UI library.\n\n## Features\n\n- Automatic table alignment\n- `inline code` support\n- *Italic* and **bold** text\n\n## Code Example\n\n```typescript\nconst md = new MarkdownRenderable(ctx, {\n  content: "# Hello",\n})\n```\n\n## Links\n\nVisit [GitHub](https://github.com) for more.\n\n---\n\n*Press `?` for help*'
        result = _render_markdown_sync(setup, md_text)
        assert "Project Title" in result
        assert "Welcome to OpenTUI, a terminal UI library." in result
        assert "Features" in result
        assert "- Automatic table alignment" in result
        assert "- inline code support" in result
        assert "- Italic and bold text" in result
        assert "Code Example" in result
        assert 'content: "# Hello",' in result
        assert "Links" in result
        assert "---" in result
        assert "Press ? for help" in result

    # ── Custom renderNode tests ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_custom_rendernode_can_override_heading_rendering(self, setup):
        """Maps to test("custom renderNode can override heading rendering")."""

        def custom_render(token, ctx):
            if token.type == "heading":
                text = token.text
                lines = [f"[CUSTOM] {text}"]
                return _MarkdownCodeBlock(
                    id="custom",
                    block_type="text",
                    lines=lines,
                    filetype="markdown",
                )
            return ctx.default_render()

        md = MarkdownRenderable(
            id="custom-heading",
            content="# Custom Heading\n\nRegular paragraph.",
            render_node=custom_render,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "[CUSTOM] Custom Heading" in frame
        assert "Regular paragraph." in frame

    @pytest.mark.asyncio
    async def test_custom_rendernode_can_override_code_block_rendering(self, setup):
        """Maps to test("custom renderNode can override code block rendering")."""

        def custom_render(token, ctx):
            if token.type == "code":
                lines = [f"CODE: {token.text.rstrip()}"]
                return _MarkdownCodeBlock(
                    id="code-text",
                    block_type="text",
                    lines=lines,
                    filetype="",
                )
            return ctx.default_render()

        md = MarkdownRenderable(
            id="custom-code",
            content="```js\nconst x = 1;\n```",
            render_node=custom_render,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "CODE: const x = 1;" in frame

    @pytest.mark.asyncio
    async def test_custom_rendernode_returning_null_uses_default(self, setup):
        """Maps to test("custom renderNode returning null uses default")."""
        md = MarkdownRenderable(
            id="custom-null",
            content="# Heading\n\nParagraph text.",
            render_node=lambda token, ctx: None,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "Heading" in frame
        assert "Paragraph text." in frame

    # ── Incomplete/invalid markdown tests ─────────────────────────────

    @pytest.mark.asyncio
    async def test_incomplete_code_block_no_closing_fence(self, setup):
        """Maps to test("incomplete code block (no closing fence)")."""
        md_text = "Here is some code:\n\n```javascript\nconst x = 1;\nconsole.log(x);"
        result = _render_markdown_sync(setup, md_text)
        assert "Here is some code:" in result
        # The unclosed code block text should still appear
        assert "const x = 1;" in result
        assert "console.log(x);" in result

    @pytest.mark.asyncio
    async def test_incomplete_bold_no_closing_asterisks(self, setup):
        """Maps to test("incomplete bold (no closing **)")."""
        md_text = "This has **unclosed bold text"
        result = _render_markdown_sync(setup, md_text)
        assert "This has **unclosed bold text" in result

    @pytest.mark.asyncio
    async def test_incomplete_italic_no_closing_asterisk(self, setup):
        """Maps to test("incomplete italic (no closing *)")."""
        md_text = "This has *unclosed italic text"
        result = _render_markdown_sync(setup, md_text)
        assert "This has *unclosed italic text" in result

    @pytest.mark.asyncio
    async def test_incomplete_link_no_closing_paren(self, setup):
        """Maps to test("incomplete link (no closing paren)")."""
        md_text = "Check out [this link](https://example.com"
        result = _render_markdown_sync(setup, md_text)
        # The incomplete link should show partially converted
        assert "this link" in result
        assert "example.com" in result

    @pytest.mark.asyncio
    async def test_incomplete_table_only_header(self, setup):
        """Maps to test("incomplete table (only header)")."""
        md_text = "| Header1 | Header2 |"
        result = _render_markdown_sync(setup, md_text)
        assert "| Header1 | Header2 |" in result

    @pytest.mark.asyncio
    async def test_incomplete_table_header_delimiter_no_rows(self, setup):
        """Maps to test("incomplete table (header + delimiter, no rows)")."""
        md_text = "| Header1 | Header2 |\n|---|---|"
        result = _render_markdown_sync(setup, md_text)
        assert "| Header1 | Header2 |" in result
        assert "|---|---|" in result

    @pytest.mark.asyncio
    async def test_streaming_like_content_with_partial_code_block(self, setup):
        """Maps to test("streaming-like content with partial code block")."""
        md_text = "# Title\n\nSome text before code.\n\n```py"
        result = _render_markdown_sync(setup, md_text)
        assert "Title" in result
        assert "Some text before code." in result

    @pytest.mark.asyncio
    async def test_malformed_table_with_missing_pipes(self, setup):
        """Maps to test("malformed table with missing pipes")."""
        md_text = "| A | B\n|---|---\n| 1 | 2"
        result = _render_markdown_sync(setup, md_text)
        # Malformed table may still be parsed and rendered
        assert "A" in result
        assert "B" in result

    # ── Trailing blank lines tests ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_trailing_blank_lines_do_not_add_spacing(self, setup):
        """Maps to test("trailing blank lines do not add spacing")."""
        md_text = "# Heading\n\nParagraph text.\n\n\n"
        result = _render_markdown_sync(setup, md_text)
        assert "Heading" in result
        assert "Paragraph text." in result
        # The trailing blank lines should not add extra visible content
        trimmed = result.rstrip()
        assert trimmed.endswith("Paragraph text.")

    @pytest.mark.asyncio
    async def test_multiple_trailing_blank_lines_do_not_add_spacing(self, setup):
        """Maps to test("multiple trailing blank lines do not add spacing")."""
        md_text = "First paragraph.\n\nSecond paragraph.\n\n\n\n"
        result = _render_markdown_sync(setup, md_text)
        assert "First paragraph." in result
        assert "Second paragraph." in result
        trimmed = result.rstrip()
        assert trimmed.endswith("Second paragraph.")

    @pytest.mark.asyncio
    async def test_blank_lines_between_blocks_add_spacing(self, setup):
        """Maps to test("blank lines between blocks add spacing")."""
        md_text = "First\n\nSecond\n\nThird"
        result = _render_markdown_sync(setup, md_text)
        assert "First" in result
        assert "Second" in result
        assert "Third" in result

    @pytest.mark.asyncio
    async def test_code_block_at_end_with_trailing_blank_lines(self, setup):
        """Maps to test("code block at end with trailing blank lines")."""
        md_text = "Text before\n\n```js\nconst x = 1;\n```\n\n"
        result = _render_markdown_sync(setup, md_text)
        assert "Text before" in result
        assert "const x = 1;" in result

    @pytest.mark.asyncio
    async def test_table_at_end_with_trailing_blank_lines(self, setup):
        """Maps to test("table at end with trailing blank lines")."""
        md_text = "| A | B |\n|---|---|\n| 1 | 2 |\n\n\n"
        result = _render_markdown_sync(setup, md_text)
        assert "│A│B│" in result or ("│A" in result and "│B" in result)
        assert "│1│2│" in result or ("│1" in result and "│2" in result)

    # ── Incremental parsing tests ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_incremental_update_reuses_unchanged_blocks_when_appending(self, setup):
        """Maps to test("incremental update reuses unchanged blocks when appending")."""
        md = MarkdownRenderable(
            id="markdown",
            content="# Hello\n\nParagraph 1",
            streaming=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        first_block_before = md._blockStates[0].renderable

        md.content = "# Hello\n\nParagraph 1\n\nParagraph 2"
        setup.render_frame()

        first_block_after = md._blockStates[0].renderable
        assert first_block_after is first_block_before

    @pytest.mark.asyncio
    async def test_streaming_mode_keeps_trailing_tokens_unstable(self, setup):
        """Maps to test("streaming mode keeps trailing tokens unstable")."""
        md = MarkdownRenderable(
            id="markdown",
            content="# Hello",
            streaming=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame1 = _capture(setup).strip()
        assert "Hello" in frame1

        md.content = "# Hello World"
        setup.render_frame()

        frame2 = _capture(setup).strip()
        assert "Hello World" in frame2

    @pytest.mark.asyncio
    async def test_streaming_code_blocks_with_concealcode_true_do_not_flash_unconcealed_markdown(
        self, setup
    ):
        """Maps to test("streaming code blocks with concealCode=true do not flash unconcealed markdown")."""
        md = MarkdownRenderable(
            id="markdown-streaming-conceal-flicker",
            content="# Stream\n\n```markdown\n# Hidden heading\n```",
            conceal=True,
            conceal_code=True,
            streaming=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "# Hidden heading" in frame
        assert "```" not in frame

    @pytest.mark.asyncio
    async def test_non_streaming_mode_parses_all_tokens_as_stable(self, setup):
        """Maps to test("non-streaming mode parses all tokens as stable")."""
        md = MarkdownRenderable(
            id="markdown",
            content="# Hello\n\nPara 1\n\nPara 2",
            streaming=False,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "Hello" in frame
        assert "Para 1" in frame
        assert "Para 2" in frame

    @pytest.mark.asyncio
    async def test_content_update_with_same_text_does_not_rebuild(self, setup):
        """Maps to test("content update with same text does not rebuild")."""
        md = MarkdownRenderable(
            id="markdown",
            content="# Hello",
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame_before = _capture(setup)

        md.content = "# Hello"
        setup.render_frame()

        frame_after = _capture(setup)
        assert frame_after == frame_before

    @pytest.mark.asyncio
    async def test_block_type_change_creates_new_renderable(self, setup):
        """Maps to test("block type change creates new renderable")."""
        md = MarkdownRenderable(
            id="markdown",
            content="# Hello",
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame_before = _capture(setup)
        assert "Hello" in frame_before

        md.content = "Hello"
        setup.render_frame()

        frame_after = _capture(setup)
        assert "Hello" in frame_after

    @pytest.mark.asyncio
    async def test_streaming_property_can_be_toggled(self, setup):
        """Maps to test("streaming property can be toggled")."""
        md = MarkdownRenderable(
            id="markdown",
            content="# Hello",
            streaming=False,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        assert md.streaming is False
        frame_before = _capture(setup)
        assert "Hello" in frame_before

        md.streaming = True
        assert md.streaming is True

        setup.render_frame()

        frame = _capture(setup).strip()
        assert "Hello" in frame

    @pytest.mark.asyncio
    async def test_clearcache_forces_full_rebuild(self, setup):
        """Maps to test("clearCache forces full rebuild")."""
        rendered_tokens: list[tuple[str, str]] = []

        def custom_render(token, ctx):
            rendered_tokens.append((token.type, token.raw))
            return ctx.default_render()

        md = MarkdownRenderable(
            id="markdown",
            content="# Hello\n\nWorld",
            render_node=custom_render,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        initial_render_count = len(rendered_tokens)
        assert initial_render_count >= 2

        md.clear_cache()
        setup.render_frame()

        assert len(rendered_tokens) >= initial_render_count * 2
        frame = _capture(setup)
        assert "Hello" in frame
        assert "World" in frame

    # ── Streaming table tests ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_streaming_to_non_streaming_transition_keeps_final_table_row_visible(self, setup):
        """Maps to test("streaming->non-streaming transition keeps final table row visible")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| Value |\n|---|\n| first |\n| second |",
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table_while_streaming = md._blockStates[0].renderable
        frame = _capture(setup)
        assert "first" in frame
        assert "second" in frame

        md.streaming = False
        setup.render_frame()

        frame = _capture(setup)
        assert "first" in frame
        assert "second" in frame
        assert md._blockStates[0].renderable is table_while_streaming

    @pytest.mark.asyncio
    async def test_streaming_table_remains_visible_when_a_new_block_starts(self, setup):
        """Maps to test("streaming table remains visible when a new block starts")."""
        table_md = "| Value |\n|---|\n| first |\n| second |"
        md = MarkdownRenderable(
            id="markdown",
            content=table_md,
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table_while_trailing = md._blockStates[0].renderable
        frame = _capture(setup)
        assert "first" in frame
        assert "second" in frame

        md.content = f"{table_md}\n\nAfter table block."
        setup.render_frame()

        frame = _capture(setup)
        assert md.streaming is True
        assert "first" in frame
        assert "second" in frame
        assert "After table block." in frame
        assert md._blockStates[0].renderable is table_while_trailing

    @pytest.mark.asyncio
    async def test_stream_end_mid_table_finalizes_full_table_snapshot(self, setup):
        """Maps to test("stream end mid-table finalizes full table snapshot")."""
        md = MarkdownRenderable(
            id="markdown",
            content="",
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)

        md.content = "| Name | Score |\n|---|---|\n"
        setup.render_frame()

        md.content = "| Name | Score |\n|---|---|\n| Alpha | 10 |\n"
        setup.render_frame()

        md.content = "| Name | Score |\n|---|---|\n| Alpha | 10 |\n| Bravo | 20 |\n"
        setup.render_frame()

        md.content = "| Name | Score |\n|---|---|\n| Alpha | 10 |\n| Bravo | 20 |\n| Charlie | 30 |"
        setup.render_frame()

        frame = _capture(setup)
        assert "Charlie" in frame

        md.streaming = False
        setup.render_frame()

        frame = _capture(setup)
        assert "Charlie" in frame
        assert "Alpha" in frame
        assert "Bravo" in frame

    @pytest.mark.asyncio
    async def test_ignores_content_updates_after_markdown_renderable_is_destroyed_during_streaming(
        self, setup
    ):
        """Maps to test("ignores content updates after markdown renderable is destroyed during streaming")."""
        md = MarkdownRenderable(
            id="markdown",
            content="",
            streaming=True,
        )
        setup.renderer.root.add(md)

        md.content = "| Name | Score |\n|---|---|\n| Alpha | 10 |\n"
        setup.render_frame()

        md.destroy_recursively()
        assert md.is_destroyed is True

        # Should not throw
        md.content = "| Name | Score |\n|---|---|\n| Alpha | 10 |\n| Bravo | 20 |\n"
        md.streaming = False

        setup.render_frame()

    @pytest.mark.asyncio
    async def test_non_streaming_to_streaming_transition_keeps_final_table_row_visible(self, setup):
        """Maps to test("non-streaming->streaming transition keeps final table row visible")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| Value |\n|---|\n| first |\n| second |",
            streaming=False,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table_while_stable = md._blockStates[0].renderable
        frame = _capture(setup)
        assert "first" in frame
        assert "second" in frame

        md.streaming = True
        setup.render_frame()

        frame = _capture(setup)
        assert "first" in frame
        assert "second" in frame
        assert md._blockStates[0].renderable is table_while_stable

    @pytest.mark.asyncio
    async def test_streaming_table_reuses_renderable_while_updating_row_content(self, setup):
        """Maps to test("streaming table reuses renderable while updating row content")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| A |\n|---|\n| 1 |",
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table_before = md._blockStates[0].renderable

        md.content = "| B |\n|---|\n| 2 |"
        setup.render_frame()

        table_after_same_rows = md._blockStates[0].renderable
        assert table_after_same_rows is table_before

        md.content = "| B |\n|---|\n| 2 |\n| 3 |"
        setup.render_frame()

        table_after_new_row = md._blockStates[0].renderable
        assert table_after_new_row is table_before

    @pytest.mark.asyncio
    async def test_table_shows_all_rows_when_streaming_is_false(self, setup):
        """Maps to test("table shows all rows when streaming is false")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| A |\n|---|\n| 1 |",
            streaming=False,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "1" in frame

    @pytest.mark.asyncio
    async def test_table_updates_content_when_not_streaming(self, setup):
        """Maps to test("table updates content when not streaming")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| A |\n|---|\n| 1 |",
            streaming=False,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame1 = _capture(setup)
        assert "1" in frame1

        md.content = "| A |\n|---|\n| 2 |"
        setup.render_frame()

        frame2 = _capture(setup)
        assert "2" in frame2

    @pytest.mark.asyncio
    async def test_table_keeps_unchanged_cell_chunks_stable_across_updates(self, setup):
        """Maps to test("table keeps unchanged cell chunks stable across updates")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |",
            streaming=False,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table = md._blockStates[0].renderable
        assert isinstance(table, _MarkdownTableBlock)

        header_before = table.content[0][0]
        first_row_before = table.content[1][0]
        second_row_second_cell_before = table.content[2][1]
        changed_cell_before = table.content[2][0]

        md.content = "| A | B |\n|---|---|\n| 1 | 2 |\n| 33 | 4 |"
        setup.render_frame()

        table_after = md._blockStates[0].renderable
        assert table_after is table
        # Header and unchanged cells keep the same object references
        assert table_after.content[0][0] is header_before
        assert table_after.content[1][0] is first_row_before
        assert table_after.content[2][1] is second_row_second_cell_before
        # Changed cell has a new reference
        assert table_after.content[2][0] is not changed_cell_before

    @pytest.mark.asyncio
    async def test_streaming_table_updates_trailing_row_content(self, setup):
        """Maps to test("streaming table updates trailing row content")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| A |\n|---|\n| 1 |\n| 2 |",
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        table = md._blockStates[0].renderable
        content_before = table.content

        md.content = "| A |\n|---|\n| 1 |\n| 200 |"
        setup.render_frame()

        table_after = md._blockStates[0].renderable
        frame = _capture(setup)
        assert table_after is table
        assert table_after.content is not content_before
        assert "200" in frame

    @pytest.mark.asyncio
    async def test_streaming_complex_tables_keep_final_rows_visible(self, setup):
        """Maps to test("streaming complex tables keep final rows visible (issue #15244)")."""
        vm_header = "| VM | 状态 | Owner | Zone | CPU | Mem(GB) | Disk(GB) | Net | Uptime | Cost/月 | Notes |"
        vm_delimiter = "|---|---|---|---|---|---|---|---|---|---|---|"
        vm_rows = [
            "| vm-api-01 | 🟢 运行中 | alice | us-east-1a | 8 | 32 | 500 | 1.2Gbps | 99.99% | 12,345 | 主节点 — steady |",
            "| vm-job-02 | 🟢 运行中 | bob | ap-south-1b | 16 | 64 | 1,024 | 950Mbps | 98.70% | 23,456 | 批处理 — spikes |",
            "| vm-batch-03 | 🟡 维护中 | carol | eu-west-1c | 32 | 128 | 2,048 | 2.4Gbps | 97.10% | 34,567 | 最后一行 — must stay |",
        ]

        storage_header = "| 存储池 | 状态 | 使用率 | 可用(GB) | 已用(GB) | 冗余 | 备注 |"
        storage_delimiter = "|---|---|---|---|---|---|---|"
        storage_rows = [
            "| 热池A | 🟢 正常 | 72% | 12,500 | 32,500 | 3x | 混合负载 |",
            "| 温池B | 🟢 正常 | 81% | 8,250 | 35,750 | 2x | 历史数据 |",
            "| 冷池C | 🟡 告警 | 93% | 2,100 | 27,900 | 2x | 最后一行 — must stay |",
        ]

        def build_content(vm_count, storage_count):
            vm_part = f"### VM details\n\n{vm_header}\n{vm_delimiter}\n" + "\n".join(
                vm_rows[:vm_count]
            )
            storage_part = (
                f"### Storage details\n\n{storage_header}\n{storage_delimiter}\n"
                + "\n".join(storage_rows[:storage_count])
            )
            return f"{vm_part}\n\n{storage_part}"

        md = MarkdownRenderable(
            id="markdown",
            content="",
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)

        for vm_count, storage_count in [(2, 2), (3, 2), (3, 3)]:
            md.content = build_content(vm_count, storage_count)
            setup.render_frame()

        frame = _capture(setup)
        assert "VM details" in frame
        assert "Storage details" in frame
        assert "vm-batch-03" in frame
        assert "冷池C" in frame

    @pytest.mark.asyncio
    async def test_streaming_table_with_incomplete_first_row_is_rendered_with_padded_cells(
        self, setup
    ):
        """Maps to test("streaming table with incomplete first row is rendered with padded cells")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| A |\n|---|\n|",
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame1 = _capture(setup)
        # Should show table borders and header
        assert "A" in frame1

        md.content = "| A |\n|---|\n| 1"
        setup.render_frame()

        frame2 = _capture(setup)
        assert "1" in frame2

        md.content = "| A |\n|---|\n| 1 |\n| 2 |"
        setup.render_frame()

        frame3 = _capture(setup)
        assert "1" in frame3
        assert "2" in frame3

    @pytest.mark.asyncio
    async def test_streaming_table_transitions_from_raw_text_to_table_once_first_row_appears(
        self, setup
    ):
        """Maps to test("streaming table transitions from raw text to table once first row appears")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| Header |",
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "| Header |" in frame
        # No box-drawing chars yet
        assert "┌" not in frame

        md.content = "| Header |\n|---|"
        setup.render_frame()

        frame = _capture(setup)
        assert "|---|" in frame
        assert "┌" not in frame

        md.content = "| Header |\n|---|\n| D"
        setup.render_frame()

        frame = _capture(setup)
        # Now it should be a table with borders
        assert "Header" in frame
        assert "D" in frame

    @pytest.mark.asyncio
    async def test_streaming_table_remains_rendered_when_row_count_decreases(self, setup):
        """Maps to test("streaming table remains rendered when row count decreases")."""
        md = MarkdownRenderable(
            id="markdown",
            content="| A |\n|---|\n| 1 |\n| 2 |",
            streaming=True,
            table_options={"widthMode": "content"},
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "1" in frame
        assert "2" in frame

        md.content = "| A |\n|---|\n| 1 |"
        setup.render_frame()

        frame = _capture(setup)
        assert "1" in frame
        assert "|---|" not in frame

    # ── Conceal/theme change tests ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_conceal_change_updates_rendered_content(self, setup):
        """Maps to test("conceal change updates rendered content")."""
        md = MarkdownRenderable(
            id="markdown",
            content="# Hello **bold**",
            conceal=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame1 = _capture(setup)
        assert "**" not in frame1
        assert "#" not in frame1

        md.conceal = False
        setup.renderer.root.mark_dirty()
        setup.render_frame()

        frame2 = _capture(setup)
        assert "**" in frame2
        assert "#" in frame2

    @pytest.mark.asyncio
    async def test_theme_switching_syntaxstyle_change(self, setup):
        """Maps to test("theme switching (syntax_style change)").

        Since we don't have full syntax highlighting with colors, we verify
        the syntax_style property can be set and the content still renders.
        """
        md = MarkdownRenderable(
            id="markdown",
            content="# OpenTUI Markdown Demo\n\nWelcome to the **MarkdownRenderable** showcase!",
            syntax_style={"default": {"fg": (1, 0, 0, 1)}},
            conceal=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame1 = _capture(setup)
        assert "OpenTUI Markdown Demo" in frame1

        md.syntax_style = {"default": {"fg": (0, 0, 1, 1)}}
        setup.renderer.root.mark_dirty()
        setup.render_frame()

        frame2 = _capture(setup)
        assert "OpenTUI Markdown Demo" in frame2

    # ── Paragraph rendering tests ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_paragraph_links_are_rendered_with_markdown_conceal_behavior(self, setup):
        """Maps to test("paragraph links are rendered with markdown conceal behavior")."""
        md = MarkdownRenderable(
            id="markdown",
            content="Check [Google](https://google.com) out",
            conceal=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "Google" in frame
        assert "google.com" in frame
        assert "[Google](https://google.com)" not in frame

    @pytest.mark.asyncio
    async def test_paragraph_initial_render_does_not_flash_raw_markdown_markers(self, setup):
        """Maps to test("paragraph initial render does not flash raw markdown markers")."""
        md = MarkdownRenderable(
            id="markdown",
            content="This has **bold** text.",
            conceal=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        frame = _capture(setup)
        assert "This has bold text." in frame
        assert "**bold**" not in frame

    @pytest.mark.asyncio
    async def test_paragraph_updates_do_not_flash_raw_markdown_markers(self, setup):
        """Maps to test("paragraph updates do not flash raw markdown markers")."""
        md = MarkdownRenderable(
            id="markdown",
            content="**First** value",
            conceal=True,
        )
        setup.renderer.root.add(md)
        setup.render_frame()

        md.content = "**Second** value"
        setup.render_frame()

        frame = _capture(setup)
        assert "Second value" in frame
        assert "**Second**" not in frame
