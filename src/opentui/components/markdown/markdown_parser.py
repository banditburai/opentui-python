"""Incremental markdown parser.

Provides a GFM-compatible markdown lexer and incremental parsing that reuses
unchanged tokens from previous parse states.  The lexer produces tokens whose
shape matches the marked-style format (type, raw, text, lang, rows, header,
align, ...) so that downstream renderers can consume them identically.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarkedToken:
    """A single markdown token produced by the lexer."""

    type: str
    raw: str
    text: str = ""
    depth: int = 0  # heading depth (1-6)
    lang: str = ""  # code block language
    # Table-specific
    header: list[dict[str, Any]] = field(default_factory=list)
    align: list[str | None] = field(default_factory=list)
    rows: list[list[dict[str, Any]]] = field(default_factory=list)


@dataclass
class ParseState:
    """Holds the result of a markdown parse: the source content and tokens."""

    content: str
    tokens: list[MarkedToken]


# Regex patterns (order matters -- checked sequentially)
_RE_SPACE = re.compile(r"^\n+")
_RE_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:\n|$)")
_RE_FENCED_CODE = re.compile(r"^(`{3,})([^\n]*)\n([\s\S]*?)(?:\1)(?:\n|$)?")
_RE_TABLE = re.compile(
    r"^"
    r"(\|[^\n]+)\n"  # header row
    r"(\|[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?)[ \t]*\n"  # separator
    r"((?:\|[^\n]*(?:\n|$))*)",  # body rows (greedy)
)
_RE_HR = re.compile(r"^(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})(?:\n|$)")
_RE_BLOCKQUOTE = re.compile(r"^(?:>(?:[^\n]*)\n?)+")
_RE_PARAGRAPH = re.compile(r"^[^\n]+(?:\n|$)")


def _parse_table_cells(row_text: str) -> list[dict[str, Any]]:
    """Split a table row into cells, returning marked-style cell dicts.

    Handles escaped pipes (``\\|``) so they are kept as literal ``|``
    characters inside a cell rather than treated as column separators.
    """
    stripped = row_text.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    # Split respecting escaped pipes
    cells: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(stripped):
        if stripped[i] == "\\" and i + 1 < len(stripped) and stripped[i + 1] == "|":
            current.append("|")
            i += 2
        elif stripped[i] == "|":
            cells.append("".join(current))
            current = []
            i += 1
        else:
            current.append(stripped[i])
            i += 1
    cells.append("".join(current))
    return [{"text": c.strip()} for c in cells]


def _parse_alignment(sep_row: str) -> list[str | None]:
    """Parse the separator row of a table to determine column alignments."""
    stripped = sep_row.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    parts = stripped.split("|")
    aligns: list[str | None] = []
    for p in parts:
        part = p.strip()
        left = part.startswith(":")
        right = part.endswith(":")
        if left and right:
            aligns.append("center")
        elif right:
            aligns.append("right")
        elif left:
            aligns.append("left")
        else:
            aligns.append(None)
    return aligns


def lex(src: str) -> list[MarkedToken]:
    """Tokenize *src* into a list of :class:`MarkedToken`.

    This is intentionally a minimal GFM-compatible lexer that covers headings,
    paragraphs, code blocks, tables, and whitespace (space) tokens.

    Every character in *src* is accounted for in exactly one token's ``raw``
    field, so ``"".join(t.raw for t in lex(src)) == src`` always holds.  This
    invariant is critical for the incremental parser.
    """
    tokens: list[MarkedToken] = []
    pos = 0
    src_len = len(src)

    while pos < src_len:
        remaining = src[pos:]

        # Any run of newlines at the current position is captured as a space
        # token.  Blank lines between block elements are preserved as space tokens.
        m = _RE_SPACE.match(remaining)
        if m:
            raw = m.group(0)
            tokens.append(MarkedToken(type="space", raw=raw))
            pos += len(raw)
            continue

        m = _RE_HEADING.match(remaining)
        if m:
            raw = m.group(0)
            tokens.append(
                MarkedToken(
                    type="heading",
                    raw=raw,
                    text=m.group(2).strip(),
                    depth=len(m.group(1)),
                )
            )
            pos += len(raw)
            continue

        m = _RE_FENCED_CODE.match(remaining)
        if m:
            raw = m.group(0)
            tokens.append(
                MarkedToken(
                    type="code",
                    raw=raw,
                    lang=m.group(2).strip(),
                    text=m.group(3),
                )
            )
            pos += len(raw)
            continue

        m = _RE_TABLE.match(remaining)
        if m:
            raw = m.group(0)
            header_cells = _parse_table_cells(m.group(1))
            alignment = _parse_alignment(m.group(2))
            body_text = m.group(3)
            rows: list[list[dict[str, Any]]] = []
            for line in body_text.split("\n"):
                stripped = line.strip()
                if stripped:
                    rows.append(_parse_table_cells(stripped))
            tokens.append(
                MarkedToken(
                    type="table",
                    raw=raw,
                    header=header_cells,
                    align=alignment,
                    rows=rows,
                )
            )
            pos += len(raw)
            continue

        m = _RE_HR.match(remaining)
        if m:
            raw = m.group(0)
            tokens.append(MarkedToken(type="hr", raw=raw))
            pos += len(raw)
            continue

        m = _RE_BLOCKQUOTE.match(remaining)
        if m:
            raw = m.group(0)
            tokens.append(MarkedToken(type="blockquote", raw=raw, text=raw))
            pos += len(raw)
            continue

        m = _RE_PARAGRAPH.match(remaining)
        if m:
            raw = m.group(0)
            tokens.append(
                MarkedToken(
                    type="paragraph",
                    raw=raw,
                    text=raw.strip(),
                )
            )
            pos += len(raw)
            continue

        # If nothing matched, skip one character to avoid infinite loop
        pos += 1  # pragma: no cover

    return tokens


class LexError(Exception):
    """Raised when the lexer cannot process input."""


def parse_markdown_incremental(
    new_content: str,
    prev_state: ParseState | None,
    trailing_unstable: int = 2,
) -> ParseState:
    """Incrementally parse markdown, reusing unchanged tokens from *prev_state*.

    Compares ``token.raw`` at each offset -- matching tokens keep the same
    object reference so that downstream renderers can perform identity checks
    to skip re-rendering unchanged content.

    Parameters
    ----------
    new_content:
        The full markdown source to parse.
    prev_state:
        Result of a previous ``parse_markdown_incremental`` call, or ``None``
        for a fresh parse.
    trailing_unstable:
        Number of trailing tokens from *prev_state* to consider "unstable"
        and always re-parse.  This handles cases like an incomplete heading
        (``"# Hello"`` later becoming ``"# Hello World"``).  Defaults to 2.
    """
    if prev_state is None or not prev_state.tokens:
        try:
            tokens = lex(new_content)
            return ParseState(content=new_content, tokens=tokens)
        except Exception:
            return ParseState(content=new_content, tokens=[])

    offset = 0
    reuse_count = 0

    for token in prev_state.tokens:
        token_length = len(token.raw)
        if (
            offset + token_length <= len(new_content)
            and new_content[offset : offset + token_length] == token.raw
        ):
            reuse_count += 1
            offset += token_length
        else:
            break

    # Keep last N tokens unstable
    reuse_count = max(0, reuse_count - trailing_unstable)

    offset = 0
    for i in range(reuse_count):
        offset += len(prev_state.tokens[i].raw)

    stable_tokens = prev_state.tokens[:reuse_count]
    remaining_content = new_content[offset:]

    if not remaining_content:
        return ParseState(content=new_content, tokens=list(stable_tokens))

    try:
        new_tokens = lex(remaining_content)
        return ParseState(content=new_content, tokens=list(stable_tokens) + new_tokens)
    except Exception:
        try:
            full_tokens = lex(new_content)
            return ParseState(content=new_content, tokens=full_tokens)
        except Exception:
            return ParseState(content=new_content, tokens=[])
