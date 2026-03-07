"""Tests for chat panel component."""

from opentui.components import Box, Text

from opencode.tui.components.chat import (
    chat_message,
    chat_panel,
    code_block,
    parse_markdown,
)


# --- Markdown parsing ---


class TestParseMarkdown:
    def test_plain_text(self):
        nodes = parse_markdown("hello world")
        assert len(nodes) == 1
        assert isinstance(nodes[0], Text)
        assert nodes[0]._content == "hello world"

    def test_bold(self):
        nodes = parse_markdown("some **bold** text")
        assert len(nodes) == 3
        assert nodes[1]._content == "bold"
        assert nodes[1]._bold is True

    def test_italic(self):
        nodes = parse_markdown("some *italic* text")
        assert len(nodes) == 3
        assert nodes[1]._content == "italic"
        assert nodes[1]._italic is True

    def test_inline_code(self):
        nodes = parse_markdown("use `foo()` here")
        assert len(nodes) == 3
        assert nodes[1]._content == "foo()"

    def test_fenced_code_block(self):
        md = "before\n```python\nprint('hi')\n```\nafter"
        nodes = parse_markdown(md)
        # Should have: before text, code block box, after text
        code_boxes = [n for n in nodes if isinstance(n, Box)]
        assert len(code_boxes) == 1

    def test_bold_not_parsed_as_italic(self):
        nodes = parse_markdown("**bold**")
        assert len(nodes) == 1
        assert nodes[0]._bold is True
        assert nodes[0]._content == "bold"

    def test_fence_without_trailing_newline(self):
        md = "```py\ncode()```"
        nodes = parse_markdown(md)
        code_boxes = [n for n in nodes if isinstance(n, Box)]
        assert len(code_boxes) == 1

    def test_empty_string(self):
        nodes = parse_markdown("")
        assert nodes == []


# --- Code block ---


class TestCodeBlock:
    def test_returns_box(self):
        cb = code_block("print('hi')")
        assert isinstance(cb, Box)

    def test_contains_code_text(self):
        cb = code_block("x = 1")
        children = cb.get_children()
        texts = [getattr(c, "_content", "") for c in children if isinstance(c, Text)]
        assert any("x = 1" in t for t in texts)

    def test_with_language(self):
        cb = code_block("fn main() {}", language="rust")
        assert isinstance(cb, Box)


# --- Chat message ---


class TestChatMessage:
    def test_user_message(self):
        msg = chat_message(role="user", content="Hello")
        assert isinstance(msg, Box)

    def test_assistant_message(self):
        msg = chat_message(role="assistant", content="Hi there")
        assert isinstance(msg, Box)

    def test_contains_content(self):
        msg = chat_message(role="user", content="Test content")
        children = msg.get_children()
        # Flatten to find text content
        all_text = _collect_text(msg)
        assert any("Test content" in t for t in all_text)

    def test_contains_role_label(self):
        msg = chat_message(role="user", content="hi")
        all_text = _collect_text(msg)
        # Should have a role indicator
        assert any("user" in t.lower() for t in all_text)

    def test_markdown_in_content(self):
        msg = chat_message(role="assistant", content="use **bold** here")
        assert isinstance(msg, Box)

    def test_streaming_shows_cursor(self):
        msg = chat_message(role="assistant", content="partial", streaming=True)
        all_text = _collect_text(msg)
        assert any("\u2588" in t for t in all_text)  # block cursor char

    def test_streaming_false_no_cursor(self):
        msg = chat_message(role="assistant", content="done")
        all_text = _collect_text(msg)
        assert not any("\u2588" in t for t in all_text)


# --- Chat panel ---


class TestChatPanel:
    def test_empty(self):
        panel = chat_panel(messages=[])
        assert isinstance(panel, Box)

    def test_with_messages(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        panel = chat_panel(messages=msgs)
        assert isinstance(panel, Box)
        children = panel.get_children()
        assert len(children) == 2

    def test_with_streaming_last(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hel"},
        ]
        panel = chat_panel(messages=msgs, streaming=True)
        assert isinstance(panel, Box)

    def test_none_content_handled(self):
        msgs = [{"role": "assistant", "content": None}]
        panel = chat_panel(messages=msgs)
        assert isinstance(panel, Box)


# --- Helpers ---


def _collect_text(node, depth=0):
    """Recursively collect all text content from a component tree."""
    if depth > 10:
        return []
    texts = []
    if isinstance(node, Text):
        texts.append(getattr(node, "_content", ""))
    if hasattr(node, "get_children"):
        for child in node.get_children():
            texts.extend(_collect_text(child, depth + 1))
    return texts
