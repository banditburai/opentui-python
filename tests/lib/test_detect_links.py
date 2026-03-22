"""Tests for detect_links — ported from lib/detect-links.test.ts (5 tests).

Upstream: reference/opentui/packages/core/src/lib/detect-links.test.ts
"""

from __future__ import annotations

from opentui.components.code_renderable import TextChunk
from opentui.detect_links import detect_links
from opentui.structs import RGBA


def chunk(text: str) -> TextChunk:
    return TextChunk(text=text, fg=RGBA(1, 1, 1, 1), attributes=0)


def test_markup_link_url_chunks():
    content = "[Click here](https://example.com)"
    highlights = [
        (0, 1, "markup.link"),
        (1, 11, "markup.link.label"),
        (11, 13, "markup.link"),
        (13, 32, "markup.link.url"),
        (32, 33, "markup.link"),
    ]
    chunks = [
        chunk("["),
        chunk("Click here"),
        chunk("]("),
        chunk("https://example.com"),
        chunk(")"),
    ]
    result = detect_links(chunks, {"content": content, "highlights": highlights})
    url_chunk = next(c for c in result if c.text == "https://example.com")
    assert url_chunk.link == {"url": "https://example.com"}
    label_chunk = next(c for c in result if c.text == "Click here")
    assert label_chunk.link == {"url": "https://example.com"}


def test_string_special_url_chunks():
    content = "// see https://example.com for details"
    highlights = [
        (0, 38, "comment"),
        (7, 26, "string.special.url"),
    ]
    chunks = [chunk("// see "), chunk("https://example.com"), chunk(" for details")]
    result = detect_links(chunks, {"content": content, "highlights": highlights})
    url_chunk = next(c for c in result if c.text == "https://example.com")
    assert url_chunk.link == {"url": "https://example.com"}


def test_no_links_on_non_url():
    content = "const x = 42"
    highlights = [
        (0, 5, "keyword"),
        (6, 7, "variable"),
        (10, 12, "number"),
    ]
    chunks = [chunk("const"), chunk(" "), chunk("x"), chunk(" = "), chunk("42")]
    result = detect_links(chunks, {"content": content, "highlights": highlights})
    for c in result:
        assert c.link is None


def test_unchanged_when_no_url_scopes():
    content = "hello world"
    highlights = [(0, 5, "keyword")]
    chunks = [chunk("hello"), chunk(" world")]
    result = detect_links(chunks, {"content": content, "highlights": highlights})
    assert result is chunks


def test_concealed_text():
    content = "[Click here](https://example.com)"
    highlights = [
        (0, 1, "markup.link"),
        (1, 11, "markup.link.label"),
        (11, 13, "markup.link"),
        (13, 32, "markup.link.url"),
        (32, 33, "markup.link"),
    ]
    chunks = [chunk(""), chunk("Click here"), chunk(" "), chunk("https://example.com"), chunk("")]
    result = detect_links(chunks, {"content": content, "highlights": highlights})
    url_chunk = next(c for c in result if c.text == "https://example.com")
    assert url_chunk.link == {"url": "https://example.com"}
    label_chunk = next(c for c in result if c.text == "Click here")
    assert label_chunk.link == {"url": "https://example.com"}
