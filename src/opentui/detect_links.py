"""Link detection in syntax-highlighted text.

Scans highlight scopes for URL patterns (markup.link.url, string.special.url)
and back-tracks to find associated labels (markup.link.label).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .components.code_renderable import TextChunk

URL_SCOPES = ("markup.link.url", "string.special.url")


def detect_links(
    chunks: list[TextChunk],
    context: Any,
) -> list[TextChunk]:
    content: str = context["content"] if isinstance(context, dict) else context.content
    highlights: list = context["highlights"] if isinstance(context, dict) else context.highlights

    ranges: list[dict[str, Any]] = []

    for i, hl in enumerate(highlights):
        start, end, group = hl[0], hl[1], hl[2]
        if group not in URL_SCOPES:
            continue
        url = content[start:end]
        ranges.append({"start": start, "end": end, "url": url})
        for j in range(i - 1, -1, -1):
            prev_start, prev_end, prev_group = highlights[j][0], highlights[j][1], highlights[j][2]
            if prev_group == "markup.link.label":
                ranges.append({"start": prev_start, "end": prev_end, "url": url})
                break
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
