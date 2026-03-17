"""Link detection in syntax-highlighted text.

Scans highlight scopes for URL patterns (markup.link.url, string.special.url)
and back-tracks to find associated labels (markup.link.label).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TextChunk:
    text: str
    fg: Any = None
    attributes: int = 0
    link: dict[str, str] | None = None


# SimpleHighlight is [start, end, scope_name]
SimpleHighlight = tuple[int, int, str]

URL_SCOPES = ("markup.link.url", "string.special.url")


def detect_links(
    chunks: list[TextChunk],
    context: dict[str, Any],
) -> list[TextChunk]:
    content: str = context["content"]
    highlights: list[SimpleHighlight] = context["highlights"]

    ranges: list[dict[str, Any]] = []

    for i, hl in enumerate(highlights):
        start, end, group = hl
        if group not in URL_SCOPES:
            continue
        url = content[start:end]
        ranges.append({"start": start, "end": end, "url": url})
        for j in range(i - 1, -1, -1):
            label_start, label_end, prev = highlights[j]
            if prev == "markup.link.label":
                ranges.append({"start": label_start, "end": label_end, "url": url})
                break
            if not prev.startswith("markup.link"):
                break

    if not ranges:
        return chunks

    content_pos = 0
    for chunk in chunks:
        if len(chunk.text) <= 1:
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
