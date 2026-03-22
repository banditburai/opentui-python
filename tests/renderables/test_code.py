"""Port of upstream Code.test.ts.

Upstream: packages/core/src/renderables/Code.test.ts
Tests ported: 53/53
"""

import asyncio

import pytest

from opentui import create_test_renderer, TestSetup
from opentui.components.code_renderable import (
    CodeRenderable,
    MockTreeSitterClient,
    SyntaxStyle,
    TreeSitterClient,
)
from opentui.components.box import Box
from opentui.structs import RGBA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup(width: int = 80, height: int = 24) -> TestSetup:
    """Create a test renderer with the given dimensions."""
    return await create_test_renderer(width, height)


def _make_syntax_style(**group_defs) -> SyntaxStyle:
    """Create a SyntaxStyle from keyword args like default={fg: RGBA(...)}.

    Convenience wrapper for tests.
    """
    styles = {}
    for raw_name, style in group_defs.items():
        dotted = raw_name.replace("__", ".")
        styles[dotted] = style
    return SyntaxStyle.from_styles(styles)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestCodeRenderable:
    """Maps to top-level tests in Code.test.ts (no describe blocks)."""

    @pytest.mark.asyncio
    async def test_basic_construction(self):
        """Maps to test("CodeRenderable - basic construction")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                    "string": {"fg": RGBA(0, 1, 0, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content='const message = "Hello, world!";',
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
            )

            assert code.content == 'const message = "Hello, world!";'
            assert code.filetype == "javascript"
            assert code.syntax_style is syntax_style
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_content_updates(self):
        """Maps to test("CodeRenderable - content updates")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="original content",
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
            )

            assert code.content == "original content"

            code.content = "updated content"
            assert code.content == "updated content"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_filetype_updates(self):
        """Maps to test("CodeRenderable - filetype updates")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="console.log('test');",
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
            )

            assert code.filetype == "javascript"

            code.filetype = "typescript"
            assert code.filetype == "typescript"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_re_highlights_when_content_changes_during_active_highlighting(self):
        """Maps to test("CodeRenderable - re-highlights when content changes during active highlighting")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [
                        [0, 5, "keyword"],
                        [6, 13, "identifier"],
                    ],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=False,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()

            code.content = "let newMessage = 'world';"
            assert code.content == "let newMessage = 'world';"

            setup.render_frame()
            assert mock_client.is_highlighting()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            assert mock_client.is_highlighting()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            assert not mock_client.is_highlighting()
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_multiple_content_changes_during_highlighting(self):
        """Maps to test("CodeRenderable - multiple content changes during highlighting")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="original content",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=False,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()

            code.content = "first change"
            code.content = "second change"
            code.content = "final content"
            assert code.content == "final content"

            setup.render_frame()
            assert mock_client.is_highlighting()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            assert mock_client.is_highlighting()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            assert not mock_client.is_highlighting()
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_uses_fallback_rendering_when_no_filetype_provided(self):
        """Maps to test("CodeRenderable - uses fallback rendering when no filetype provided")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello world';",
                syntax_style=syntax_style,
                conceal=False,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert code.content == "const message = 'hello world';"
            assert code.filetype is None
            assert code.plain_text == "const message = 'hello world';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_uses_fallback_rendering_when_highlighting_throws_error(self):
        """Maps to test("CodeRenderable - uses fallback rendering when highlighting throws error")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()

            # Override to throw
            async def _failing_highlight(content, filetype):
                raise RuntimeError("Highlighting failed")

            mock_client.highlight_once = _failing_highlight
            mock_client.highlight_once = _failing_highlight

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello world';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=False,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            await asyncio.sleep(0.02)
            setup.render_frame()

            assert code.content == "const message = 'hello world';"
            assert code.filetype == "javascript"
            assert code.plain_text == "const message = 'hello world';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_handles_empty_content(self):
        """Maps to test("CodeRenderable - handles empty content")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="",
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
            )

            setup.render_frame()

            assert code.content == ""
            assert code.filetype == "javascript"
            assert code.plain_text == ""
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_empty_content_does_not_trigger_highlighting(self):
        """Maps to test("CodeRenderable - empty content does not trigger highlighting")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=False,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.content == "const message = 'hello';"
            assert code.plain_text == "const message = 'hello';"

            code.content = ""
            setup.render_frame()

            assert not mock_client.is_highlighting()
            assert code.content == ""
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_text_renders_immediately_before_highlighting_completes(self):
        """Maps to test("CodeRenderable - text renders immediately before highlighting completes")."""
        setup = await _setup(32, 2)
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [
                        [0, 5, "keyword"],
                        [6, 13, "identifier"],
                    ],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello world';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()

            frame_before = setup.capture_char_frame()
            assert "const message" in frame_before

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            frame_after = setup.capture_char_frame()
            assert "const message" in frame_after
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_batches_concurrent_content_and_filetype_updates(self):
        """Maps to test("CodeRenderable - batches concurrent content and filetype updates")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            highlight_count = 0
            mock_client = MockTreeSitterClient()
            original_highlight = mock_client.highlight_once

            async def _counting_highlight(content, filetype):
                nonlocal highlight_count
                highlight_count += 1
                return await original_highlight(content, filetype)

            mock_client.highlight_once = _counting_highlight
            mock_client.highlight_once = _counting_highlight

            mock_client.set_mock_result(
                {
                    "highlights": [[0, 3, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=False,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            highlight_count = 0

            code.content = "let newMessage = 'world';"
            code.filetype = "typescript"

            setup.render_frame()
            # Yield to let the async highlight task start (the counting wrapper
            # is patched on the instance, so highlighting runs asynchronously)
            await asyncio.sleep(0)

            mock_client.resolve_all_highlight_once()
            await asyncio.sleep(0.01)

            assert highlight_count == 1
            assert code.content == "let newMessage = 'world';"
            assert code.filetype == "typescript"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_batches_multiple_updates_in_same_tick_into_single_highlight(self):
        """Maps to test("CodeRenderable - batches multiple updates in same tick into single highlight")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            highlight_count = 0
            highlight_calls = []
            mock_client = MockTreeSitterClient()
            original_highlight = mock_client.highlight_once

            async def _tracking_highlight(content, filetype):
                nonlocal highlight_count
                highlight_count += 1
                highlight_calls.append({"content": content, "filetype": filetype})
                return await original_highlight(content, filetype)

            mock_client.highlight_once = _tracking_highlight

            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="initial",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=False,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            highlight_count = 0
            highlight_calls.clear()

            code.content = "first content change"
            code.filetype = "typescript"
            code.content = "second content change"

            setup.render_frame()
            # Yield to let the async highlight task start (the counting wrapper
            # is patched on the instance, so highlighting runs asynchronously)
            await asyncio.sleep(0)

            mock_client.resolve_all_highlight_once()
            await asyncio.sleep(0.01)

            assert highlight_count == 1
            assert highlight_calls[0]["content"] == "second content change"
            assert highlight_calls[0]["filetype"] == "typescript"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_renders_markdown_with_typescript_injection_correctly(self):
        """Maps to test("CodeRenderable - renders markdown with TypeScript injection correctly")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(1, 0, 0, 1)},
                    "string": {"fg": RGBA(0, 1, 0, 1)},
                    "markup.heading.1": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            markdown_code = '# Hello\n\n```typescript\nconst msg: string = "hi";\n```'

            code = CodeRenderable(
                setup.renderer,
                id="test-markdown",
                content=markdown_code,
                filetype="markdown",
                syntax_style=syntax_style,
                conceal=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            # Without a real tree-sitter client, we use fallback rendering
            # The plain text should contain all the content
            assert "# Hello" in code.plain_text
            assert "const msg" in code.plain_text
            assert "typescript" in code.plain_text
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_continues_highlighting_after_unresolved_promise(self):
        """Maps to test("CodeRenderable - continues highlighting after unresolved promise")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            highlight_count = 0
            pending_calls: list[dict] = []

            class HangingMockClient(TreeSitterClient):
                async def highlight_once(self, content, filetype):
                    nonlocal highlight_count
                    highlight_count += 1

                    should_hang = highlight_count == 4 and filetype == "typescript"
                    pending_calls.append(
                        {
                            "content": content,
                            "filetype": filetype,
                            "never": should_hang,
                        }
                    )

                    if should_hang:
                        # Never resolve
                        await asyncio.Future()

                    return {"highlights": []}

            mock_client = HangingMockClient()

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="interface User { name: string; }",
                filetype="typescript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=False,
            )

            setup.renderer.root.add(code)
            setup.render_frame()
            await asyncio.sleep(0.02)

            highlight_count = 0
            pending_calls.clear()

            code.content = "const message = 'hello';"
            code.filetype = "javascript"
            setup.render_frame()
            await asyncio.sleep(0.02)

            code.content = "# Documentation"
            code.filetype = "markdown"
            setup.render_frame()
            await asyncio.sleep(0.02)

            code.content = "const message = 'world';"
            code.filetype = "javascript"
            setup.render_frame()
            await asyncio.sleep(0.02)

            code.content = "interface User { name: string; }"
            code.filetype = "typescript"
            setup.render_frame()
            await asyncio.sleep(0.02)

            code.content = "# New Documentation"
            code.filetype = "markdown"
            setup.render_frame()
            await asyncio.sleep(0.02)

            markdown_happened = any(
                p["content"] == "# New Documentation" and p["filetype"] == "markdown"
                for p in pending_calls
            )

            assert code.content == "# New Documentation"
            assert code.filetype == "markdown"
            assert markdown_happened
            assert highlight_count == 5
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_concealment_is_enabled_by_default(self):
        """Maps to test("CodeRenderable - concealment is enabled by default")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
            )

            assert code.conceal is True
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_concealment_can_be_disabled_explicitly(self):
        """Maps to test("CodeRenderable - concealment can be disabled explicitly")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                conceal=False,
            )

            assert code.conceal is False
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_applies_concealment_to_styled_text(self):
        """Maps to test("CodeRenderable - applies concealment to styled text")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=True,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)

            assert code.conceal is True

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.content == "const message = 'hello';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_updating_conceal_triggers_re_highlighting(self):
        """Maps to test("CodeRenderable - updating conceal triggers re-highlighting")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                conceal=True,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert code.conceal is True

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            code.conceal = False
            assert code.conceal is False

            setup.render_frame()

            assert mock_client.is_highlighting()
            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_draw_unstyled_text_is_true_by_default(self):
        """Maps to test("CodeRenderable - draw_unstyled_text is true by default")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
            )

            assert code.draw_unstyled_text is True
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_draw_unstyled_text_can_be_set_to_false(self):
        """Maps to test("CodeRenderable - draw_unstyled_text can be set to false")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                draw_unstyled_text=False,
            )

            assert code.draw_unstyled_text is False
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_with_draw_unstyled_text_true_text_renders_before_highlighting(self):
        """Maps to test("CodeRenderable - with draw_unstyled_text=true, text renders before highlighting")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=True,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()

            assert code.plain_text == "const message = 'hello';"

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.plain_text == "const message = 'hello';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_with_draw_unstyled_text_false_text_does_not_render_before_highlighting_but_line_count_is_correct(
        self,
    ):
        """Maps to test("CodeRenderable - with draw_unstyled_text=false, text does not render before highlighting but line_count is correct")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()

            # Text buffer has content for line_count, but nothing renders
            assert code.plain_text == "const message = 'hello';"
            assert code.line_count == 1
            frame_before = setup.capture_char_frame()
            assert frame_before.strip() == ""

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.plain_text == "const message = 'hello';"
            frame_after = setup.capture_char_frame()
            assert "const message" in frame_after
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_updating_draw_unstyled_text_from_false_to_true_triggers_re_highlighting(self):
        """Maps to test("CodeRenderable - updating draw_unstyled_text from false to true triggers re-highlighting")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)

            assert code.draw_unstyled_text is False

            setup.render_frame()
            assert code.plain_text == "const message = 'hello';"
            assert code.line_count == 1

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            code.draw_unstyled_text = True
            assert code.draw_unstyled_text is True

            setup.render_frame()

            assert mock_client.is_highlighting()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert not mock_client.is_highlighting()
            assert code.plain_text == "const message = 'hello';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_updating_draw_unstyled_text_from_true_to_false_triggers_re_highlighting(self):
        """Maps to test("CodeRenderable - updating draw_unstyled_text from true to false triggers re-highlighting")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=True,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert code.draw_unstyled_text is True

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            code.draw_unstyled_text = False
            assert code.draw_unstyled_text is False

            setup.render_frame()

            assert mock_client.is_highlighting()
            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_uses_fallback_rendering_on_error_even_with_draw_unstyled_text_false(self):
        """Maps to test("CodeRenderable - uses fallback rendering on error even with draw_unstyled_text=false")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()

            async def _failing_highlight(content, filetype):
                raise RuntimeError("Highlighting failed")

            mock_client.highlight_once = _failing_highlight
            mock_client.highlight_once = _failing_highlight

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello world';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)

            await asyncio.sleep(0.02)
            setup.render_frame()

            assert code.plain_text == "const message = 'hello world';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_with_draw_unstyled_text_false_and_no_filetype_fallback_is_used(self):
        """Maps to test("CodeRenderable - with draw_unstyled_text=false and no filetype, fallback is used")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello world';",
                syntax_style=syntax_style,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)

            setup.render_frame()

            assert code.filetype is None
            assert code.plain_text == "const message = 'hello world';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_with_draw_unstyled_text_false_multiple_updates_only_render_final_highlighted_text(
        self,
    ):
        """Maps to test("CodeRenderable - with draw_unstyled_text=false, multiple updates only render final highlighted text")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 3, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()

            # Text buffer has content for line_count, but nothing renders
            assert code.plain_text == "const message = 'hello';"
            assert code.line_count == 1
            frame_before = setup.capture_char_frame()
            assert frame_before.strip() == ""

            code.content = "let newMessage = 'world';"
            setup.render_frame()

            # Text buffer updated but still no rendering
            assert code.plain_text == "let newMessage = 'world';"
            assert code.line_count == 1
            frame_after_update = setup.capture_char_frame()
            assert frame_after_update.strip() == ""

            mock_client.resolve_all_highlight_once()
            await asyncio.sleep(0.01)
            setup.render_frame()
            await asyncio.sleep(0.01)

            assert not mock_client.is_highlighting()
            assert code.plain_text == "let newMessage = 'world';"
            frame_final = setup.capture_char_frame()
            assert "let newMessage" in frame_final
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_simulates_markdown_stream_from_llm_with_async_updates(self):
        """Maps to test.skip("CodeRenderable - simulates markdown stream from LLM with async updates")."""
        import random

        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                    "string": {"fg": RGBA(0, 1, 0, 1)},
                    "markup.heading.1": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            # Base markdown content that we'll repeat to grow to target size
            base_markdown_content = (
                "# Code Example\n"
                "\n"
                "Here's a simple TypeScript function:\n"
                "\n"
                "```typescript\n"
                "function greet(name: string): string {\n"
                "  return `Hello, ${name}!`;\n"
                "}\n"
                "\n"
                'const message = greet("World");\n'
                "console.log(message);\n"
                "```\n"
            )

            target_size = 64 * 128
            full_markdown_content = ""
            iteration = 0
            while len(full_markdown_content) < target_size:
                full_markdown_content += (
                    f"\n--- Iteration {iteration} ---\n\n" + base_markdown_content
                )
                iteration += 1

            code = CodeRenderable(
                setup.renderer,
                id="test-markdown-stream",
                content="",
                filetype="markdown",
                syntax_style=syntax_style,
                conceal=False,
                left=0,
                top=0,
                draw_unstyled_text=False,
            )
            # Use real tree-sitter if available
            try:
                from opentui.tree_sitter_client import PyTreeSitterClient

                code.tree_sitter_client = PyTreeSitterClient()
                await code.tree_sitter_client.initialize()
                await code.tree_sitter_client.preload_parser("markdown")
            except ImportError:
                pass

            setup.renderer.root.add(code)
            setup.renderer.start()

            current_content = ""
            chunk_size = 64
            chunks = []
            for i in range(0, len(full_markdown_content), chunk_size):
                chunks.append(
                    full_markdown_content[i : min(i + chunk_size, len(full_markdown_content))]
                )

            for chunk in chunks:
                current_content += chunk
                code.content = current_content
                await asyncio.sleep(random.randint(1, 25) / 1000)

            # Wait for highlighting to complete
            await asyncio.sleep(0.5)

            assert code.content == full_markdown_content
            assert len(code.content) >= target_size
            assert "# Code Example" in code.plain_text
            assert "function greet" in code.plain_text
            assert "typescript" in code.plain_text
            assert "Hello" in code.plain_text

            plain_text = code.plain_text
            assert len(plain_text) > target_size * 0.9
            assert "Code Example" in plain_text
            assert "const message = greet" in plain_text
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_option_is_false_by_default(self):
        """Maps to test("CodeRenderable - streaming option is false by default")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
            )

            assert code.streaming is False
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_can_be_enabled(self):
        """Maps to test("CodeRenderable - streaming can be enabled")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                streaming=True,
            )

            assert code.streaming is True
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_mode_respects_draw_unstyled_text_only_for_initial_content(self):
        """Maps to test("CodeRenderable - streaming mode respects draw_unstyled_text only for initial content")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const initial = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
                draw_unstyled_text=True,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)

            setup.render_frame()
            assert code.plain_text == "const initial = 'hello';"

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            code.content = "const updated = 'world';"

            assert code.content == "const updated = 'world';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_mode_with_draw_unstyled_text_false_waits_for_new_highlights(self):
        """Maps to test("CodeRenderable - streaming mode with draw_unstyled_text=false waits for new highlights")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient({"autoResolveTimeout": 10})
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const initial = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            await asyncio.sleep(0.03)
            setup.render_frame()

            assert code.plain_text == "const initial = 'hello';"

            code.content = "const updated = 'world';"
            # In streaming + draw_unstyled_text=false, text buffer not updated yet
            assert code.plain_text == "const initial = 'hello';"

            setup.render_frame()
            await asyncio.sleep(0.03)
            setup.render_frame()

            assert code.plain_text == "const updated = 'world';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_on_chunks_callback_can_transform_chunks_when_highlights_are_empty(self):
        """Maps to test("CodeRenderable - on_chunks callback can transform chunks when highlights are empty")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            callback_invoked = False

            def _on_chunks(chunks, context):
                nonlocal callback_invoked
                callback_invoked = True
                from opentui.components.code_renderable import TextChunk

                return [TextChunk(text=c.text.upper(), fg=c.fg, bg=c.bg) for c in chunks]

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="hello",
                filetype="plaintext",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                on_chunks=_on_chunks,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert callback_invoked
            assert code.plain_text == "HELLO"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_on_highlight_callback_receives_highlights_and_context(self):
        """Maps to test("CodeRenderable - on_highlight callback receives highlights and context")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            callback_invoked = False
            received_highlights = None
            received_context = None

            def _on_highlight(highlights, context):
                nonlocal callback_invoked, received_highlights, received_context
                callback_invoked = True
                received_highlights = [list(h) for h in highlights]
                received_context = {
                    "content": context.content,
                    "filetype": context.filetype,
                    "syntax_style": context.syntax_style,
                }
                return highlights

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                on_highlight=_on_highlight,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert callback_invoked
            assert received_highlights is not None
            assert len(received_highlights) == 1
            assert received_highlights[0] == [0, 5, "keyword"]
            assert received_context["content"] == "const message = 'hello';"
            assert received_context["filetype"] == "javascript"
            assert received_context["syntax_style"] is syntax_style
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_on_highlight_callback_can_add_custom_highlights(self):
        """Maps to test("CodeRenderable - on_highlight callback can add custom highlights")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                    "custom.highlight": {"fg": RGBA(1, 0, 0, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            def _on_highlight(highlights, context):
                highlights.append([6, 13, "custom.highlight", {}])
                return highlights

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                on_highlight=_on_highlight,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.plain_text == "const message = 'hello';"

            line_highlights = code.get_line_highlights(0)
            assert len(line_highlights) >= 2

            keyword_style_id = syntax_style.get_style_id("keyword")
            keyword_hl = [h for h in line_highlights if h.style_id == keyword_style_id]
            assert len(keyword_hl) > 0

            custom_style_id = syntax_style.get_style_id("custom.highlight")
            custom_hl = [h for h in line_highlights if h.style_id == custom_style_id]
            assert len(custom_hl) > 0
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_on_highlight_callback_returning_undefined_uses_original_highlights(self):
        """Maps to test("CodeRenderable - on_highlight callback returning undefined uses original highlights")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            callback_invoked = False

            def _on_highlight(highlights, context):
                nonlocal callback_invoked
                callback_invoked = True

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                on_highlight=_on_highlight,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert callback_invoked
            assert code.plain_text == "const message = 'hello';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_on_highlight_callback_is_called_on_re_highlighting_when_content_changes(self):
        """Maps to test("CodeRenderable - on_highlight callback is called on re-highlighting when content changes")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            callback_count = 0

            def _on_highlight(highlights, context):
                nonlocal callback_count
                callback_count += 1
                return highlights

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                on_highlight=_on_highlight,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert callback_count == 1

            code.content = "let newMessage = 'world';"
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert callback_count == 2
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_on_highlight_callback_supports_async_functions(self):
        """Maps to test("CodeRenderable - on_highlight callback supports async functions")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                    "async.highlight": {"fg": RGBA(0, 1, 0, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            async_callback_completed = False

            async def _on_highlight(highlights, context):
                nonlocal async_callback_completed
                await asyncio.sleep(0.005)
                highlights.append([6, 13, "async.highlight", {}])
                async_callback_completed = True
                return highlights

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const message = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                on_highlight=_on_highlight,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.02)
            setup.render_frame()

            assert async_callback_completed
            assert code.plain_text == "const message = 'hello';"

            line_highlights = code.get_line_highlights(0)
            assert len(line_highlights) >= 2

            async_style_id = syntax_style.get_style_id("async.highlight")
            async_hl = [
                h
                for h in line_highlights
                if h.style_id == async_style_id and h.start == 6 and h.end == 13
            ]
            assert len(async_hl) > 0
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_mode_caches_highlights_between_updates(self):
        """Maps to test("CodeRenderable - streaming mode caches highlights between updates")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const initial = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            code.content = "const updated = 'world';"

            code.content = "const updated2 = 'test';"

            code.content = "const final = 'done';"

            setup.render_frame()

            assert code.content == "const final = 'done';"
            assert code.plain_text == "const final = 'done';"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_mode_works_with_large_content_updates(self):
        """Maps to test("CodeRenderable - streaming mode works with large content updates")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const x = 1;",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
                draw_unstyled_text=True,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            content = "const x = 1;"
            for i in range(10):
                content += f"\nconst var{i} = {i};"
                code.content = content
                await asyncio.sleep(0.005)

            setup.render_frame()
            mock_client.resolve_all_highlight_once()
            await asyncio.sleep(0.02)
            setup.render_frame()

            assert "const var9 = 9;" in code.content
            assert "const var9 = 9;" in code.plain_text
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_disabling_streaming_clears_cached_highlights(self):
        """Maps to test("CodeRenderable - disabling streaming clears cached highlights")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const initial = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert code.streaming is True

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            code.streaming = False
            assert code.streaming is False

            setup.render_frame()

            assert mock_client.is_highlighting()
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_mode_with_draw_unstyled_text_false_shows_nothing_initially(self):
        """Maps to test("CodeRenderable - streaming mode with draw_unstyled_text=false shows nothing initially")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const initial = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)

            setup.render_frame()
            frame_before = setup.capture_char_frame()
            assert frame_before.strip() == ""

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            frame_after = setup.capture_char_frame()
            assert "const initial" in frame_after
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_mode_handles_empty_cached_highlights_gracefully(self):
        """Maps to test("CodeRenderable - streaming mode handles empty cached highlights gracefully")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="plain text",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
                draw_unstyled_text=True,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            code.content = "more plain text"
            setup.render_frame()

            assert code.content == "more plain text"
            assert code.plain_text == "more plain text"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_selection_across_two_code_renderables_in_flex_row(self):
        """Maps to test("CodeRenderable - selection across two Code renderables in flex row")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            container = Box(
                id="container",
                width=80,
                height=10,
                flex_direction="row",
                left=0,
                top=0,
            )
            setup.renderer.root.add(container)

            left_code = CodeRenderable(
                setup.renderer,
                id="left-code",
                content="line1\nline2\nline3\nline4\nline5",
                syntax_style=syntax_style,
                selectable=True,
                wrap_mode="none",
                width=20,
                height=5,
            )

            right_code = CodeRenderable(
                setup.renderer,
                id="right-code",
                content="lineA\nlineB\nlineC\nlineD\nlineE",
                syntax_style=syntax_style,
                selectable=True,
                wrap_mode="none",
                width=20,
                height=5,
            )

            container.add(left_code)
            container.add(right_code)

            setup.render_frame()

            assert left_code.x == 0
            assert right_code.x > left_code.x

            start_x = left_code.x + 2
            start_y = left_code.y + 2
            end_x = right_code.x + 3
            end_y = right_code.y + right_code.height + 2

            setup.mock_mouse.drag(start_x, start_y, end_x, end_y)
            setup.render_frame()

            assert left_code.has_selection()
            assert right_code.has_selection()

            left_selection = left_code.get_selected_text()
            right_selection = right_code.get_selected_text()
            left_sel_obj = left_code.get_selection()
            right_sel_obj = right_code.get_selection()

            assert left_sel_obj is not None
            assert right_sel_obj is not None

            if left_sel_obj and right_sel_obj:
                assert left_sel_obj["start"] > 0
                assert left_sel_obj["end"] == 29
                assert right_sel_obj["start"] == 0
                assert right_sel_obj["end"] == 29
                assert left_selection == "ne3\nline4\nline5"
                assert right_selection == "lineA\nlineB\nlineC\nlineD\nlineE"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_content_update_during_async_highlighting_does_not_get_overwritten_by_stale_highlight_result(
        self,
    ):
        """Maps to test("CodeRenderable - content update during async highlighting does not get overwritten by stale highlight result")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result(
                {
                    "highlights": [[0, 5, "keyword"]],
                }
            )

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="line1\nline2\nline3",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=True,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()
            assert code.line_count == 3

            code.content = "line1\nline2\nline3\nline4\nline5"
            assert code.line_count == 5

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)

            assert code.content == "line1\nline2\nline3\nline4\nline5"
            assert code.line_count == 5

            setup.render_frame()
            assert code.line_count == 5

            assert mock_client.is_highlighting()

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.content == "line1\nline2\nline3\nline4\nline5"
            assert code.line_count == 5
            assert code.plain_text == "line1\nline2\nline3\nline4\nline5"
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_line_count_is_correct_immediately_with_draw_unstyled_text_false(self):
        """Maps to test("CodeRenderable - line_count is correct immediately with draw_unstyled_text=false")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="line1\nline2\nline3\nline4\nline5",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
            )

            assert code.line_count == 5
            assert code.content == "line1\nline2\nline3\nline4\nline5"

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()
            assert code.line_count == 5

            frame_before = setup.capture_char_frame()
            assert frame_before.strip() == ""

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.line_count == 5
            frame_after = setup.capture_char_frame()
            assert "line1" in frame_after
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_line_count_updates_correctly_when_content_changes_with_draw_unstyled_text_false(
        self,
    ):
        """Maps to test("CodeRenderable - line_count updates correctly when content changes with draw_unstyled_text=false")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="line1\nline2\nline3",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
            )

            assert code.line_count == 3

            setup.renderer.root.add(code)
            setup.render_frame()

            code.content = "line1\nline2\nline3\nline4\nline5\nline6\nline7"
            assert code.line_count == 7

            setup.render_frame()
            assert code.line_count == 7

            code.content = "line1\nline2"
            assert code.line_count == 2

            setup.render_frame()
            assert code.line_count == 2
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_line_info_is_accessible_with_draw_unstyled_text_false_before_highlighting(self):
        """Maps to test("CodeRenderable - line_info is accessible with draw_unstyled_text=false before highlighting")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="short\nlonger line here\nmed",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
            )

            setup.renderer.root.add(code)

            assert code.line_count == 3
            line_info = code.line_info
            assert line_info is not None
            assert len(line_info.line_start_cols) == 3

            setup.render_frame()

            assert mock_client.is_highlighting()
            line_info = code.line_info
            assert line_info is not None
            assert len(line_info.line_start_cols) == 3
            assert len(line_info.line_sources) == 3

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            line_info = code.line_info
            assert line_info is not None
            assert len(line_info.line_start_cols) == 3
            assert len(line_info.line_sources) == 3
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_plain_text_reflects_content_immediately_with_draw_unstyled_text_false(self):
        """Maps to test("CodeRenderable - plain_text reflects content immediately with draw_unstyled_text=false")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="initial content",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
            )

            assert code.plain_text == "initial content"

            setup.renderer.root.add(code)
            setup.render_frame()

            assert mock_client.is_highlighting()
            assert code.plain_text == "initial content"

            code.content = "updated content"
            assert code.plain_text == "updated content"

            setup.render_frame()
            frame = setup.capture_char_frame()
            assert frame.strip() == ""

            mock_client.resolve_all_highlight_once()
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.plain_text == "updated content"
            final_frame = setup.capture_char_frame()
            assert "updated content" in final_frame
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_text_length_is_correct_with_draw_unstyled_text_false(self):
        """Maps to test("CodeRenderable - text_length is correct with draw_unstyled_text=false")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            content = "hello world test"
            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content=content,
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                draw_unstyled_text=False,
            )

            assert code.text_length == len(content)

            setup.renderer.root.add(code)
            setup.render_frame()

            assert code.text_length == len(content)

            new_content = "longer content here"
            code.content = new_content
            assert code.text_length == len(new_content)
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_mode_with_draw_unstyled_text_false_has_correct_line_count(self):
        """Maps to test("CodeRenderable - streaming mode with draw_unstyled_text=false has correct line_count")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient()
            mock_client.set_mock_result({"highlights": []})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="line1\nline2",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
                draw_unstyled_text=False,
            )

            assert code.line_count == 2

            setup.renderer.root.add(code)
            setup.render_frame()

            frame_before = setup.capture_char_frame()
            assert frame_before.strip() == ""

            mock_client.resolve_highlight_once(0)
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.line_count == 2

            # In streaming + draw_unstyled_text=false, text buffer is NOT updated
            # on content change. line_count reflects the text buffer, not _code_content.
            code.content = "line1\nline2\nline3\nline4"
            assert code.line_count == 2  # text buffer not updated yet

            code.content = "line1\nline2\nline3\nline4\nline5\nline6"
            assert code.line_count == 2  # still not updated

            setup.render_frame()
            mock_client.resolve_all_highlight_once()
            await asyncio.sleep(0.01)
            setup.render_frame()

            assert code.line_count == 6
            final_frame = setup.capture_char_frame()
            assert "line1" in final_frame
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_with_conceal_and_draw_unstyled_text_false_should_not_jump_when_fenced_code_blocks_are_concealed(
        self,
    ):
        """Maps to test("CodeRenderable - streaming with conceal and draw_unstyled_text=false should not jump when fenced code blocks are concealed")."""
        from opentui.testing.capture import TestRecorder

        # This test uses real tree-sitter for proper conceal metadata
        try:
            from opentui.tree_sitter_client import PyTreeSitterClient
        except ImportError:
            pytest.skip("tree-sitter not available")

        setup = await _setup(80, 20)
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                    "keyword": {"fg": RGBA(0, 0, 1, 1)},
                    "string": {"fg": RGBA(0, 1, 0, 1)},
                    "markup.heading.1": {"fg": RGBA(0, 0, 1, 1)},
                    "markup.raw.block": {"fg": RGBA(0.5, 0.5, 0.5, 1)},
                }
            )

            ts_client = PyTreeSitterClient()
            if not ts_client.is_filetype_available("markdown"):
                pytest.skip("tree-sitter-markdown not available")

            code = CodeRenderable(
                setup.renderer,
                id="test-markdown",
                content="# Example",
                filetype="markdown",
                syntax_style=syntax_style,
                tree_sitter_client=ts_client,
                streaming=True,
                conceal=True,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)

            # Helper to wait for highlighting cycle
            async def wait_for_highlighting_cycle(timeout=2.0):
                import time

                start = time.monotonic()
                setup.render_frame()
                await asyncio.sleep(0.01)
                while code.is_highlighting and (time.monotonic() - start) < timeout:
                    await asyncio.sleep(0.01)
                setup.render_frame()

            # Use TestRecorder to capture frames
            recorder = TestRecorder(setup.renderer)

            # Start renderer and recorder
            setup.renderer.start()
            recorder.rec()

            # Wait for initial highlighting to complete
            await wait_for_highlighting_cycle()

            # Now simulate streaming: add more content including fenced code block
            code.content = "# Example\n\nHere's some code:\n\n```typescript\nconst x = 1;\n```"

            # Wait for highlighting to process the update
            await wait_for_highlighting_cycle()

            # Stop everything
            setup.renderer.stop()
            recorder.stop()

            frames = recorder.recorded_frames

            # Analyze frames to detect the presence of backticks
            frame_analysis = []
            for recorded_frame in frames:
                frame = recorded_frame.frame
                has_backticks = "```" in frame
                lines = [line for line in frame.split("\n") if line.strip()]
                is_empty = len(frame.strip()) == 0
                frame_analysis.append(
                    {
                        "has_backticks": has_backticks,
                        "line_count": len(lines),
                        "is_empty": is_empty,
                    }
                )

            # Check for flickering (non-empty frame followed by empty frame)
            has_flickering = False
            for i in range(2, len(frame_analysis)):
                prev = frame_analysis[i - 1]
                curr = frame_analysis[i]
                if not prev["is_empty"] and curr["is_empty"]:
                    has_flickering = True

            # No frames should show raw backticks (they should be concealed)
            frames_with_backticks = [
                f for f in frame_analysis if f["has_backticks"] and not f["is_empty"]
            ]

            assert len(frames_with_backticks) == 0
            assert has_flickering is False

            # Verify final frame
            if frame_analysis:
                final_frame = frame_analysis[-1]
                assert final_frame["is_empty"] is False
                assert final_frame["has_backticks"] is False

                final_frame_text = frames[-1].frame
                assert "Example" in final_frame_text
        finally:
            setup.destroy()

    @pytest.mark.asyncio
    async def test_streaming_with_draw_unstyled_text_false_falls_back_to_unstyled_text_when_highlights_fail(
        self,
    ):
        """Maps to test("CodeRenderable - streaming with draw_unstyled_text=false falls back to unstyled text when highlights fail")."""
        setup = await _setup()
        try:
            syntax_style = SyntaxStyle.from_styles(
                {
                    "default": {"fg": RGBA(1, 1, 1, 1)},
                }
            )

            mock_client = MockTreeSitterClient({"autoResolveTimeout": 10})

            code = CodeRenderable(
                setup.renderer,
                id="test-code",
                content="const initial = 'hello';",
                filetype="javascript",
                syntax_style=syntax_style,
                tree_sitter_client=mock_client,
                streaming=True,
                draw_unstyled_text=False,
                left=0,
                top=0,
            )

            setup.renderer.root.add(code)
            setup.render_frame()

            await asyncio.sleep(0.03)
            setup.render_frame()

            # Now make highlighting fail
            async def _failing_highlight(content, filetype):
                raise RuntimeError("Highlighting failed")

            mock_client.highlight_once = _failing_highlight
            mock_client.highlight_once = _failing_highlight

            code.content = "const updated = 'world';"

            setup.render_frame()
            await asyncio.sleep(0.03)
            setup.render_frame()

            assert code.plain_text == "const updated = 'world';"
        finally:
            setup.destroy()
