"""Tests for StdinBuffer — ported from lib/stdin-buffer.test.ts.

Upstream: reference/opentui/packages/core/src/lib/stdin-buffer.test.ts
Async timeout tests use threading.Event to wait for timer-based flush.
"""

from __future__ import annotations

import time

import pytest
from opentui.input.stdin_buffer import StdinBuffer


@pytest.fixture
def buf():
    emitted: list[str] = []
    pasted: list[str] = []
    b = StdinBuffer(timeout=10)
    b.on("data", lambda s: emitted.append(s))
    b.on("paste", lambda s: pasted.append(s))
    return b, emitted, pasted


def mk(timeout=10):
    """Create buffer with collectors."""
    emitted: list[str] = []
    pasted: list[str] = []
    b = StdinBuffer(timeout=timeout)
    b.on("data", lambda s: emitted.append(s))
    b.on("paste", lambda s: pasted.append(s))
    return b, emitted, pasted


# ── Regular Characters ──────────────────────────────────────────────────


class TestRegularCharacters:
    def test_single_char(self, buf):
        b, em, _ = buf
        b.process("a")
        assert em == ["a"]

    def test_multiple_chars(self, buf):
        b, em, _ = buf
        b.process("abc")
        assert em == ["a", "b", "c"]

    def test_unicode(self, buf):
        b, em, _ = buf
        b.process("hello 世界")
        assert em == ["h", "e", "l", "l", "o", " ", "世", "界"]

    def test_emoji(self, buf):
        b, em, _ = buf
        b.process("👍")
        assert em == ["👍"]

    def test_emoji_mixed_ascii(self, buf):
        b, em, _ = buf
        b.process("hi👍bye")
        assert em == ["h", "i", "👍", "b", "y", "e"]

    def test_emoji_split_across_chunks(self, buf):
        b, em, _ = buf
        high = "\ud83d"
        low = "\udc4d"
        b.process(high)
        assert em == []
        assert b.get_buffer() == high
        b.process(low)
        assert em == [high + low]
        assert b.get_buffer() == ""

    def test_split_emoji_mixed_with_ascii(self, buf):
        b, em, _ = buf
        high = "\ud83d"
        low = "\udc4d"
        b.process("a" + high)
        assert em == ["a"]
        assert b.get_buffer() == high
        b.process(low + "b")
        assert em == ["a", high + low, "b"]


# ── Complete Escape Sequences ───────────────────────────────────────────


class TestCompleteEscapeSequences:
    def test_mouse_sgr(self, buf):
        b, em, _ = buf
        b.process("\x1b[<35;20;5m")
        assert em == ["\x1b[<35;20;5m"]

    def test_arrow_key(self, buf):
        b, em, _ = buf
        b.process("\x1b[A")
        assert em == ["\x1b[A"]

    def test_function_key(self, buf):
        b, em, _ = buf
        b.process("\x1b[11~")
        assert em == ["\x1b[11~"]

    def test_meta_key(self, buf):
        b, em, _ = buf
        b.process("\x1ba")
        assert em == ["\x1ba"]

    def test_ss3(self, buf):
        b, em, _ = buf
        b.process("\x1bOA")
        assert em == ["\x1bOA"]


# ── Partial Escape Sequences ───────────────────────────────────────────


class TestPartialEscapeSequences:
    def test_incomplete_mouse_sgr(self, buf):
        b, em, _ = buf
        b.process("\x1b")
        assert em == []
        assert b.get_buffer() == "\x1b"
        b.process("[<35")
        assert em == []
        assert b.get_buffer() == "\x1b[<35"
        b.process(";20;5m")
        assert em == ["\x1b[<35;20;5m"]
        assert b.get_buffer() == ""

    def test_incomplete_csi(self, buf):
        b, em, _ = buf
        b.process("\x1b[")
        assert em == []
        b.process("1;")
        assert em == []
        b.process("5H")
        assert em == ["\x1b[1;5H"]

    def test_split_many_chunks(self, buf):
        b, em, _ = buf
        for ch in ["\x1b", "[", "<", "3", "5", ";", "2", "0", ";", "5", "m"]:
            b.process(ch)
        assert em == ["\x1b[<35;20;5m"]

    def test_flush_after_timeout(self):
        b, em, _ = mk(timeout=10)
        b.process("\x1b[<35")
        assert em == []
        time.sleep(0.025)
        assert em == ["\x1b[<35"]


# ── Mixed Content ──────────────────────────────────────────────────────


class TestMixedContent:
    def test_chars_then_escape(self, buf):
        b, em, _ = buf
        b.process("abc\x1b[A")
        assert em == ["a", "b", "c", "\x1b[A"]

    def test_escape_then_chars(self, buf):
        b, em, _ = buf
        b.process("\x1b[Aabc")
        assert em == ["\x1b[A", "a", "b", "c"]

    def test_multiple_sequences(self, buf):
        b, em, _ = buf
        b.process("\x1b[A\x1b[B\x1b[C")
        assert em == ["\x1b[A", "\x1b[B", "\x1b[C"]

    def test_partial_with_preceding_chars(self, buf):
        b, em, _ = buf
        b.process("abc\x1b[<35")
        assert em == ["a", "b", "c"]
        assert b.get_buffer() == "\x1b[<35"
        b.process(";20;5m")
        assert em == ["a", "b", "c", "\x1b[<35;20;5m"]


# ── Mouse Events ──────────────────────────────────────────────────────


class TestMouseEvents:
    def test_mouse_press(self, buf):
        b, em, _ = buf
        b.process("\x1b[<0;10;5M")
        assert em == ["\x1b[<0;10;5M"]

    def test_mouse_release(self, buf):
        b, em, _ = buf
        b.process("\x1b[<0;10;5m")
        assert em == ["\x1b[<0;10;5m"]

    def test_mouse_move(self, buf):
        b, em, _ = buf
        b.process("\x1b[<35;20;5m")
        assert em == ["\x1b[<35;20;5m"]

    def test_split_mouse(self, buf):
        b, em, _ = buf
        b.process("\x1b[<3")
        b.process("5;1")
        b.process("5;")
        b.process("10m")
        assert em == ["\x1b[<35;15;10m"]

    def test_multiple_mouse(self, buf):
        b, em, _ = buf
        b.process("\x1b[<35;1;1m\x1b[<35;2;2m\x1b[<35;3;3m")
        assert em == ["\x1b[<35;1;1m", "\x1b[<35;2;2m", "\x1b[<35;3;3m"]

    def test_old_style_mouse(self, buf):
        b, em, _ = buf
        b.process("\x1b[M abc")
        assert em == ["\x1b[M ab", "c"]

    def test_incomplete_old_style_mouse(self, buf):
        b, em, _ = buf
        b.process("\x1b[M")
        assert b.get_buffer() == "\x1b[M"
        b.process(" a")
        assert b.get_buffer() == "\x1b[M a"
        b.process("b")
        assert em == ["\x1b[M ab"]


# ── Edge Cases ─────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_input(self, buf):
        b, em, _ = buf
        b.process("")
        assert em == [""]

    def test_lone_escape_timeout(self):
        b, em, _ = mk(timeout=10)
        b.process("\x1b")
        assert em == []
        time.sleep(0.025)
        assert em == ["\x1b"]

    def test_lone_escape_flush(self, buf):
        b, em, _ = buf
        b.process("\x1b")
        assert em == []
        flushed = b.flush()
        assert flushed == ["\x1b"]

    def test_bytes_input(self, buf):
        b, em, _ = buf
        b.process(b"\x1b[A")
        assert em == ["\x1b[A"]

    def test_very_long_sequence(self, buf):
        b, em, _ = buf
        long_seq = "\x1b[" + "1;" * 50 + "H"
        b.process(long_seq)
        assert em == [long_seq]


# ── Flush ──────────────────────────────────────────────────────────────


class TestFlush:
    def test_flush_incomplete(self, buf):
        b, em, _ = buf
        b.process("\x1b[<35")
        flushed = b.flush()
        assert flushed == ["\x1b[<35"]
        assert b.get_buffer() == ""

    def test_nothing_to_flush(self, buf):
        b, em, _ = buf
        assert b.flush() == []

    def test_timeout_flush(self):
        b, em, _ = mk(timeout=10)
        b.process("\x1b[<35")
        assert em == []
        time.sleep(0.025)
        assert em == ["\x1b[<35"]


# ── Clear ──────────────────────────────────────────────────────────────


class TestClear:
    def test_clear_buffer(self, buf):
        b, em, _ = buf
        b.process("\x1b[<35")
        assert b.get_buffer() == "\x1b[<35"
        b.clear()
        assert b.get_buffer() == ""
        assert em == []


# ── Real-world ─────────────────────────────────────────────────────────


class TestRealWorld:
    def test_rapid_typing_with_mouse(self, buf):
        b, em, _ = buf
        b.process("h")
        b.process("\x1b")
        b.process("[<35;")
        b.process("10;5m")
        b.process("e")
        b.process("l")
        assert em == ["h", "\x1b[<35;10;5m", "e", "l"]


# ── Double-escape sequences ───────────────────────────────────────────


class TestDoubleEscape:
    def test_option_left(self, buf):
        b, em, _ = buf
        b.process("\x1b\x1b[D")
        assert em == ["\x1b\x1b[D"]

    def test_option_right(self, buf):
        b, em, _ = buf
        b.process("\x1b\x1b[C")
        assert em == ["\x1b\x1b[C"]

    def test_option_up(self, buf):
        b, em, _ = buf
        b.process("\x1b\x1b[A")
        assert em == ["\x1b\x1b[A"]

    def test_option_down(self, buf):
        b, em, _ = buf
        b.process("\x1b\x1b[B")
        assert em == ["\x1b\x1b[B"]

    def test_option_arrow_chunks(self, buf):
        b, em, _ = buf
        b.process("\x1b")
        b.process("\x1b[D")
        assert em == ["\x1b\x1b[D"]

    def test_option_arrow_modifier(self, buf):
        b, em, _ = buf
        b.process("\x1b\x1b[1;2C")
        assert em == ["\x1b\x1b[1;2C"]

    def test_double_escape_ss3(self, buf):
        b, em, _ = buf
        b.process("\x1b\x1bOA")
        assert em == ["\x1b\x1bOA"]

    def test_option_arrow_mixed(self, buf):
        b, em, _ = buf
        b.process("a\x1b\x1b[Db")
        assert em == ["a", "\x1b\x1b[D", "b"]


# ── Bracketed Paste ───────────────────────────────────────────────────


class TestBracketedPaste:
    def test_complete_paste(self):
        b, em, pa = mk()
        b.process("\x1b[200~hello world\x1b[201~")
        assert pa == ["hello world"]
        assert em == []

    def test_paste_in_chunks(self):
        b, em, pa = mk()
        b.process("\x1b[200~")
        assert pa == []
        b.process("hello ")
        assert pa == []
        b.process("world\x1b[201~")
        assert pa == ["hello world"]
        assert em == []

    def test_input_before_after_paste(self):
        b, em, pa = mk()
        b.process("a")
        b.process("\x1b[200~pasted\x1b[201~")
        b.process("b")
        assert em == ["a", "b"]
        assert pa == ["pasted"]

    def test_paste_split_many_chunks(self):
        b, em, pa = mk()
        b.process("\x1b[200~")
        b.process("chunk1")
        b.process("chunk2")
        b.process("chunk3\x1b[201~")
        assert pa == ["chunk1chunk2chunk3"]
        assert em == []

    def test_multiple_pastes(self):
        b, em, pa = mk()
        b.process("\x1b[200~first\x1b[201~")
        b.process("a")
        b.process("\x1b[200~second\x1b[201~")
        assert pa == ["first", "second"]
        assert em == ["a"]

    def test_empty_paste(self):
        b, em, pa = mk()
        b.process("\x1b[200~\x1b[201~")
        assert pa == [""]
        assert em == []

    def test_normal_after_paste(self):
        b, em, pa = mk()
        b.process("\x1b[200~pasted content\x1b[201~")
        b.process("abc")
        b.process("\x1b[A")
        assert pa == ["pasted content"]
        assert em == ["a", "b", "c", "\x1b[A"]

    def test_data_before_paste_same_chunk(self):
        b, em, pa = mk()
        b.process("abc\x1b[200~pasted\x1b[201~")
        assert em == ["a", "b", "c"]
        assert pa == ["pasted"]

    def test_data_after_paste_same_chunk(self):
        b, em, pa = mk()
        b.process("\x1b[200~pasted\x1b[201~xyz")
        assert pa == ["pasted"]
        assert em == ["x", "y", "z"]

    def test_data_before_and_after_paste(self):
        b, em, pa = mk()
        b.process("abc\x1b[200~pasted\x1b[201~xyz")
        assert em == ["a", "b", "c", "x", "y", "z"]
        assert pa == ["pasted"]

    def test_escape_before_paste(self):
        b, em, pa = mk()
        b.process("\x1b[A\x1b[200~pasted\x1b[201~")
        assert em == ["\x1b[A"]
        assert pa == ["pasted"]

    def test_escape_after_paste(self):
        b, em, pa = mk()
        b.process("\x1b[200~pasted\x1b[201~\x1b[B")
        assert pa == ["pasted"]
        assert em == ["\x1b[B"]

    def test_escape_before_and_after_paste(self):
        b, em, pa = mk()
        b.process("\x1b[A\x1b[200~pasted\x1b[201~\x1b[B")
        assert em == ["\x1b[A", "\x1b[B"]
        assert pa == ["pasted"]

    def test_mixed_before_paste(self):
        b, em, pa = mk()
        b.process("a\x1b[Ab\x1b[200~pasted\x1b[201~")
        assert em == ["a", "\x1b[A", "b"]
        assert pa == ["pasted"]

    def test_mixed_after_paste(self):
        b, em, pa = mk()
        b.process("\x1b[200~pasted\x1b[201~x\x1b[By")
        assert pa == ["pasted"]
        assert em == ["x", "\x1b[B", "y"]

    def test_complex_mixed(self):
        b, em, pa = mk()
        b.process("start\x1b[A\x1b[200~pasted content\x1b[201~\x1b[Bend")
        assert em == ["s", "t", "a", "r", "t", "\x1b[A", "\x1b[B", "e", "n", "d"]
        assert pa == ["pasted content"]

    def test_paste_start_split(self):
        b, em, pa = mk()
        b.process("\x1b[200")
        assert pa == []
        assert em == []
        b.process("~content\x1b[201~")
        assert pa == ["content"]
        assert em == []

    def test_paste_end_split(self):
        b, em, pa = mk()
        b.process("\x1b[200~content\x1b[201")
        assert pa == []
        b.process("~")
        assert pa == ["content"]
        assert em == []

    def test_paste_markers_split(self):
        b, em, pa = mk()
        b.process("\x1b")
        b.process("[")
        b.process("200")
        b.process("~")
        assert pa == []
        b.process("content")
        assert pa == []
        b.process("\x1b")
        b.process("[")
        b.process("201")
        b.process("~")
        assert pa == ["content"]

    def test_paste_with_newlines(self):
        b, em, pa = mk()
        b.process("\x1b[200~line1\nline2\nline3\x1b[201~")
        assert pa == ["line1\nline2\nline3"]
        assert em == []

    def test_paste_with_tabs(self):
        b, em, pa = mk()
        b.process("\x1b[200~col1\tcol2\tcol3\x1b[201~")
        assert pa == ["col1\tcol2\tcol3"]
        assert em == []

    def test_paste_with_special_chars(self):
        b, em, pa = mk()
        b.process("\x1b[200~!@#$%^&*()_+-=[]{}|;:',.<>?/\x1b[201~")
        assert pa == ["!@#$%^&*()_+-=[]{}|;:',.<>?/"]
        assert em == []

    def test_paste_with_unicode(self):
        b, em, pa = mk()
        b.process("\x1b[200~Hello 世界 🎉\x1b[201~")
        assert pa == ["Hello 世界 🎉"]
        assert em == []

    def test_very_long_paste(self):
        b, em, pa = mk()
        long = "a" * 10000
        b.process(f"\x1b[200~{long}\x1b[201~")
        assert pa == [long]
        assert em == []

    def test_paste_interrupted_by_clear(self):
        b, em, pa = mk()
        b.process("\x1b[200~partial content")
        assert pa == []
        b.clear()
        assert pa == []
        b.process("a")
        assert em == ["a"]
        assert pa == []

    def test_paste_interrupted_by_destroy(self):
        b, em, pa = mk()
        b.process("\x1b[200~partial content")
        assert pa == []
        b.destroy()
        assert pa == []

    def test_consecutive_pastes(self):
        b, em, pa = mk()
        b.process("\x1b[200~first\x1b[201~\x1b[200~second\x1b[201~")
        assert pa == ["first", "second"]
        assert em == []

    def test_empty_paste_then_data(self):
        b, em, pa = mk()
        b.process("\x1b[200~\x1b[201~")
        b.process("a")
        assert pa == [""]
        assert em == ["a"]

    def test_data_between_start_chunks(self):
        b, em, pa = mk()
        b.process("\x1b")
        b.process("[")
        b.process("200~content\x1b[201~")
        assert pa == ["content"]
        assert em == []

    def test_incomplete_escape_before_paste(self):
        b, em, pa = mk()
        b.process("\x1b[<35")
        assert em == []
        b.process(";20;5m\x1b[200~paste\x1b[201~")
        assert em == ["\x1b[<35;20;5m"]
        assert pa == ["paste"]

    def test_paste_then_incomplete_escape(self):
        b, em, pa = mk()
        b.process("\x1b[200~paste\x1b[201~\x1b[<35")
        assert pa == ["paste"]
        assert em == []
        assert b.get_buffer() == "\x1b[<35"
        b.process(";20;5m")
        assert em == ["\x1b[<35;20;5m"]

    def test_escape_interrupted_by_paste(self):
        b, em, pa = mk()
        b.process("\x1b[1;")
        assert em == []
        assert b.get_buffer() == "\x1b[1;"
        b.process("5H\x1b[200~paste\x1b[201~")
        assert em == ["\x1b[1;5H"]
        assert pa == ["paste"]

    def test_paste_start_as_different_sequence(self):
        b, em, pa = mk()
        b.process("\x1b[20")
        assert em == []
        b.process("0R")
        assert em == ["\x1b[200R"]
        assert pa == []

    def test_multiple_escapes_after_paste(self):
        b, em, pa = mk()
        b.process("\x1b[200~pasted\x1b[201~\x1b[A\x1b[B\x1b[C")
        assert pa == ["pasted"]
        assert em == ["\x1b[A", "\x1b[B", "\x1b[C"]

    def test_bytes_paste(self):
        b, em, pa = mk()
        b.process(b"\x1b[200~pasted\x1b[201~")
        assert pa == ["pasted"]
        assert em == []

    def test_paste_carriage_returns(self):
        b, em, pa = mk()
        b.process("\x1b[200~line1\r\nline2\r\nline3\x1b[201~")
        assert pa == ["line1\r\nline2\r\nline3"]
        assert em == []

    def test_paste_start_inside_paste(self):
        b, em, pa = mk()
        b.process("\x1b[200~content with \x1b[200~ inside\x1b[201~")
        assert pa == ["content with \x1b[200~ inside"]
        assert em == []

    def test_nested_paste_inner_end_closes(self):
        b, em, pa = mk()
        b.process("\x1b[200~outer \x1b[200~inner\x1b[201~ rest\x1b[201~")
        assert pa == ["outer \x1b[200~inner"]
        assert " " in em
        assert "r" in em
        assert "e" in em
        assert "s" in em
        assert "t" in em
        assert "\x1b[201~" in em

    def test_paste_end_without_start(self):
        b, em, pa = mk()
        b.process("\x1b[201~")
        assert pa == []
        assert em == ["\x1b[201~"]

    def test_paste_end_in_regular(self):
        b, em, pa = mk()
        b.process("hello\x1b[201~world")
        assert pa == []
        assert em == ["h", "e", "l", "l", "o", "\x1b[201~", "w", "o", "r", "l", "d"]

    def test_multiple_paste_starts(self):
        b, em, pa = mk()
        b.process("\x1b[200~first \x1b[200~ second \x1b[200~ third\x1b[201~")
        assert pa == ["first \x1b[200~ second \x1b[200~ third"]
        assert em == []

    def test_paste_literal_backslash(self):
        b, em, pa = mk()
        b.process("\x1b[200~The text \\x1b[200~ is literal\x1b[201~")
        assert pa == ["The text \\x1b[200~ is literal"]
        assert em == []


# ── Destroy ────────────────────────────────────────────────────────────


class TestDestroy:
    def test_clear_on_destroy(self, buf):
        b, em, _ = buf
        b.process("\x1b[<35")
        assert b.get_buffer() == "\x1b[<35"
        b.destroy()
        assert b.get_buffer() == ""

    def test_no_emit_after_destroy(self):
        b, em, _ = mk(timeout=10)
        b.process("\x1b[<35")
        b.destroy()
        time.sleep(0.025)
        assert em == []


# ── Terminal Capability Responses ─────────────────────────────────────


class TestTerminalCapability:
    def test_decrpm(self, buf):
        b, em, _ = buf
        b.process("\x1b[?1016;2$y")
        assert em == ["\x1b[?1016;2$y"]

    def test_split_decrpm(self, buf):
        b, em, _ = buf
        b.process("\x1b[?10")
        b.process("16;2$y")
        assert em == ["\x1b[?1016;2$y"]

    def test_cpr_width(self, buf):
        b, em, _ = buf
        b.process("\x1b[1;2R")
        assert em == ["\x1b[1;2R"]

    def test_cpr_scaled(self, buf):
        b, em, _ = buf
        b.process("\x1b[1;3R")
        assert em == ["\x1b[1;3R"]

    def test_xtversion_complete(self, buf):
        b, em, _ = buf
        b.process("\x1bP>|kitty(0.40.1)\x1b\\")
        assert em == ["\x1bP>|kitty(0.40.1)\x1b\\"]

    def test_xtversion_split(self, buf):
        b, em, _ = buf
        b.process("\x1bP>|kit")
        assert em == []
        assert b.get_buffer() == "\x1bP>|kit"
        b.process("ty(0.40")
        assert em == []
        assert b.get_buffer() == "\x1bP>|kitty(0.40"
        b.process(".1)\x1b\\")
        assert em == ["\x1bP>|kitty(0.40.1)\x1b\\"]
        assert b.get_buffer() == ""

    def test_ghostty_xtversion(self, buf):
        b, em, _ = buf
        b.process("\x1bP>|gho")
        b.process("stty 1.1.3")
        b.process("\x1b\\")
        assert em == ["\x1bP>|ghostty 1.1.3\x1b\\"]

    def test_tmux_xtversion(self, buf):
        b, em, _ = buf
        b.process("\x1bP>|tmux 3.5a\x1b\\")
        assert em == ["\x1bP>|tmux 3.5a\x1b\\"]

    def test_kitty_graphics_complete(self, buf):
        b, em, _ = buf
        b.process("\x1b_Gi=1;OK\x1b\\")
        assert em == ["\x1b_Gi=1;OK\x1b\\"]

    def test_kitty_graphics_split(self, buf):
        b, em, _ = buf
        b.process("\x1b_Gi=1;")
        assert em == []
        assert b.get_buffer() == "\x1b_Gi=1;"
        b.process("EINVAL:Zero width")
        assert em == []
        b.process("/height not allowed\x1b\\")
        assert em == ["\x1b_Gi=1;EINVAL:Zero width/height not allowed\x1b\\"]

    def test_da1(self, buf):
        b, em, _ = buf
        b.process("\x1b[?62;c")
        assert em == ["\x1b[?62;c"]

    def test_da1_multiple_attrs(self, buf):
        b, em, _ = buf
        b.process("\x1b[?62;22c")
        assert em == ["\x1b[?62;22c"]

    def test_da1_sixel(self, buf):
        b, em, _ = buf
        b.process("\x1b[?1;2;4c")
        assert em == ["\x1b[?1;2;4c"]

    def test_pixel_resolution(self, buf):
        b, em, _ = buf
        b.process("\x1b[4;720;1280t")
        assert em == ["\x1b[4;720;1280t"]

    def test_split_pixel_resolution(self, buf):
        b, em, _ = buf
        b.process("\x1b[4;72")
        b.process("0;1280t")
        assert em == ["\x1b[4;720;1280t"]

    def test_multiple_decrpm(self, buf):
        b, em, _ = buf
        b.process("\x1b[?1016;2$y\x1b[?2027;0$y\x1b[?2031;2$y")
        assert em == ["\x1b[?1016;2$y", "\x1b[?2027;0$y", "\x1b[?2031;2$y"]

    def test_kitty_full_capability_chunks(self, buf):
        b, em, _ = buf
        b.process("\x1b[?1016;2$y\x1b[?20")
        assert em == ["\x1b[?1016;2$y"]
        assert b.get_buffer() == "\x1b[?20"
        b.process("27;0$y\x1b[?2031;2$y\x1bP>|kit")
        assert em == ["\x1b[?1016;2$y", "\x1b[?2027;0$y", "\x1b[?2031;2$y"]
        assert b.get_buffer() == "\x1bP>|kit"
        b.process("ty(0.40.1)\x1b\\")
        assert em == [
            "\x1b[?1016;2$y",
            "\x1b[?2027;0$y",
            "\x1b[?2031;2$y",
            "\x1bP>|kitty(0.40.1)\x1b\\",
        ]

    def test_capability_with_user_input(self, buf):
        b, em, _ = buf
        b.process("\x1b[?1016;2$yh")
        assert em == ["\x1b[?1016;2$y", "h"]

    def test_keypress_during_capability(self, buf):
        b, em, _ = buf
        b.process("\x1bP>|kit")
        assert b.get_buffer() == "\x1bP>|kit"
        b.process("ty(0.40.1)\x1b\\a")
        assert em == ["\x1bP>|kitty(0.40.1)\x1b\\", "a"]

    def test_extremely_split_xtversion(self, buf):
        b, em, _ = buf
        for ch in list("\x1bP>|kitty(0.40.1)") + ["\x1b", "\\"]:
            b.process(ch)
        assert em == ["\x1bP>|kitty(0.40.1)\x1b\\"]
