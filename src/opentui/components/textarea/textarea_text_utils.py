from ...structs import char_width as char_display_width


def str_display_width(text: str) -> int:
    """Return total display width of a string (CJK chars count as 2)."""
    return sum(char_display_width(ch) for ch in text)


def offset_to_line_col(text: str, offset: int) -> tuple[int, int]:
    """Convert a character offset to (line, display_col).

    Returns display-width columns (CJK chars count as 2).
    """
    offset = max(0, min(offset, len(text)))
    line = 0
    col = 0
    for i in range(offset):
        if text[i] == "\n":
            line += 1
            col = 0
        else:
            col += char_display_width(text[i])
    return (line, col)


def line_col_to_offset(text: str, line: int, col: int) -> int:
    """Convert (line, display_col) to a character offset.

    Accepts display-width columns (CJK chars count as 2).
    """
    offset = 0
    current_line = 0
    for ch in text:
        if current_line == line:
            break
        if ch == "\n":
            current_line += 1
        offset += 1
    # Now offset is at the start of the target line.
    # Walk display columns to find the character offset.
    display_col = 0
    while offset < len(text) and text[offset] != "\n" and display_col < col:
        display_col += char_display_width(text[offset])
        offset += 1
    return offset


def char_class(ch: str) -> int:
    """Classify a character for word boundary detection.

    Returns 0 for whitespace, 1 for CJK/ideograph, 2 for other (ASCII, etc).
    """
    if ch in (" ", "\n", "\t"):
        return 0
    cp = ord(ch)
    # CJK Unified Ideographs
    if 0x4E00 <= cp <= 0x9FFF:
        return 1
    # CJK Extension A
    if 0x3400 <= cp <= 0x4DBF:
        return 1
    # CJK Extension B-I (supplementary)
    if 0x20000 <= cp <= 0x3134F:
        return 1
    # CJK Compatibility Ideographs
    if 0xF900 <= cp <= 0xFAFF:
        return 1
    # Hangul Syllables
    if 0xAC00 <= cp <= 0xD7AF:
        return 1
    # CJK Punctuation (Ideographic full stop, etc.)
    if 0x3000 <= cp <= 0x303F:
        return 1
    # Fullwidth forms
    if 0xFF00 <= cp <= 0xFFEF:
        return 1
    # Hiragana
    if 0x3040 <= cp <= 0x309F:
        return 1
    # Katakana
    if 0x30A0 <= cp <= 0x30FF:
        return 1
    return 2


def next_word_boundary(text: str, offset: int) -> int:
    length = len(text)
    if offset >= length:
        return length
    pos = offset
    start_class = char_class(text[pos])
    if start_class == 0:
        # In whitespace: skip whitespace, then the following word group,
        # then trailing whitespace
        while pos < length and char_class(text[pos]) == 0:
            pos += 1
        if pos < length:
            word_class = char_class(text[pos])
            while pos < length and char_class(text[pos]) == word_class:
                pos += 1
            while pos < length and char_class(text[pos]) == 0:
                pos += 1
        return pos
    else:
        while pos < length and char_class(text[pos]) == start_class:
            pos += 1
        while pos < length and char_class(text[pos]) == 0:
            pos += 1
        return pos


def prev_word_boundary(text: str, offset: int) -> int:
    if offset <= 0:
        return 0
    pos = offset
    while pos > 0 and char_class(text[pos - 1]) == 0:
        pos -= 1
    if pos <= 0:
        return 0
    prev_cls = char_class(text[pos - 1])
    while pos > 0 and char_class(text[pos - 1]) == prev_cls:
        pos -= 1
    return pos
