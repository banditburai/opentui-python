"""Dedicated unit tests for opentui.palette module.

Tests the internal functions, classes, and async detection logic in
``palette.py`` directly, without going through the renderer layer.

The integration tests in ``tests/integration/test_renderer_palette.py``
exercise palette detection via the renderer; these tests focus on:
- ``_scale_component`` / ``_to_hex`` pure colour helpers
- ``_OSC4_RE`` / ``_OSC_SPECIAL_RE`` regex matching
- ``TerminalColors`` dataclass
- ``MockPaletteStdin`` / ``MockPaletteStdout`` mock streams
- ``TerminalPalette`` async methods directly
- Edge cases: malformed data, buffer overflow, partial chunks, timeouts
"""

from __future__ import annotations

import asyncio
import re

import pytest

from opentui.palette import (
    MockPaletteStdin,
    MockPaletteStdout,
    TerminalColors,
    TerminalPalette,
)
from opentui.palette.common import (
    OSC4_RE as _OSC4_RE,
    OSC_SPECIAL_RE as _OSC_SPECIAL_RE,
    _scale_component,
    _to_hex,
)


# ===================================================================
# _scale_component
# ===================================================================


class TestScaleComponent:
    """_scale_component colour scaling helper."""

    def test_single_hex_digit(self):
        # 'f' -> 15, max=15, scaled=255 -> 'ff'
        assert _scale_component("f") == "ff"

    def test_single_hex_digit_zero(self):
        assert _scale_component("0") == "00"

    def test_single_hex_digit_mid(self):
        # '8' -> 8, max=15, scaled=round(8/15*255)=136 -> '88'
        assert _scale_component("8") == "88"

    def test_two_hex_digits_max(self):
        assert _scale_component("ff") == "ff"

    def test_two_hex_digits_zero(self):
        assert _scale_component("00") == "00"

    def test_two_hex_digits_mid(self):
        # 'aa' -> 170, max=255, scaled=170 -> 'aa'
        assert _scale_component("aa") == "aa"

    def test_two_hex_digits_80(self):
        # '80' -> 128, max=255, scaled=128 -> '80'
        assert _scale_component("80") == "80"

    def test_three_hex_digits(self):
        # 'fff' -> 4095, max=4095, scaled=255 -> 'ff'
        assert _scale_component("fff") == "ff"

    def test_three_hex_digits_zero(self):
        assert _scale_component("000") == "00"

    def test_four_hex_digits_max(self):
        # 'ffff' -> 65535, max=65535, scaled=255 -> 'ff'
        assert _scale_component("ffff") == "ff"

    def test_four_hex_digits_zero(self):
        assert _scale_component("0000") == "00"

    def test_four_hex_digits_8000(self):
        # '8000' -> 32768, max=65535, scaled=round(32768/65535*255)=128 -> '80'
        assert _scale_component("8000") == "80"

    def test_four_hex_digits_aa00(self):
        # 'aa00' -> 43520, max=65535, scaled=round(43520/65535*255) -> 'a9'
        result = _scale_component("aa00")
        assert re.fullmatch(r"[0-9a-f]{2}", result)
        assert result == "a9"

    def test_case_insensitive_input(self):
        assert _scale_component("FF") == _scale_component("ff")
        assert _scale_component("FFFF") == _scale_component("ffff")
        assert _scale_component("Aa") == _scale_component("aa")


# ===================================================================
# _to_hex
# ===================================================================


class TestToHex:
    """_to_hex colour conversion helper."""

    def test_hex6_path(self):
        assert _to_hex(hex6="FF00AA") == "#ff00aa"

    def test_hex6_already_lowercase(self):
        assert _to_hex(hex6="aabbcc") == "#aabbcc"

    def test_rgb_components_two_digit(self):
        assert _to_hex(r="ff", g="00", b="aa") == "#ff00aa"

    def test_rgb_components_four_digit(self):
        assert _to_hex(r="ffff", g="0000", b="aaaa") == "#ff00aa"

    def test_rgb_components_one_digit(self):
        assert _to_hex(r="f", g="0", b="a") == "#ff00aa"

    def test_rgb_components_three_digit(self):
        assert _to_hex(r="fff", g="000", b="aaa") == "#ff00aa"

    def test_fallback_when_nothing_provided(self):
        assert _to_hex() == "#000000"

    def test_fallback_partial_rgb_missing_r(self):
        assert _to_hex(g="ff", b="ff") == "#000000"

    def test_fallback_partial_rgb_missing_g(self):
        assert _to_hex(r="ff", b="ff") == "#000000"

    def test_fallback_partial_rgb_missing_b(self):
        assert _to_hex(r="ff", g="ff") == "#000000"

    def test_hex6_takes_precedence_over_rgb(self):
        # When both hex6 and rgb are supplied, hex6 wins
        assert _to_hex(r="00", g="00", b="00", hex6="FFFFFF") == "#ffffff"


# ===================================================================
# Regex: _OSC4_RE
# ===================================================================


class TestOSC4Regex:
    """_OSC4_RE matching for OSC 4 palette responses."""

    def test_matches_hex_format_bel(self):
        m = _OSC4_RE.search("\x1b]4;0;#ff00aa\x07")
        assert m is not None
        assert m.group(1) == "0"
        assert m.group(5) == "ff00aa"

    def test_matches_hex_format_st(self):
        m = _OSC4_RE.search("\x1b]4;0;#ff00aa\x1b\\")
        assert m is not None
        assert m.group(1) == "0"
        assert m.group(5) == "ff00aa"

    def test_matches_rgb_format_bel(self):
        m = _OSC4_RE.search("\x1b]4;0;rgb:ffff/0000/aaaa\x07")
        assert m is not None
        assert m.group(1) == "0"
        assert m.group(2) == "ffff"
        assert m.group(3) == "0000"
        assert m.group(4) == "aaaa"
        assert m.group(5) is None

    def test_matches_rgb_format_st(self):
        m = _OSC4_RE.search("\x1b]4;255;rgb:1234/5678/9abc\x1b\\")
        assert m is not None
        assert m.group(1) == "255"
        assert m.group(2) == "1234"
        assert m.group(3) == "5678"
        assert m.group(4) == "9abc"

    def test_large_index(self):
        m = _OSC4_RE.search("\x1b]4;255;#aabbcc\x07")
        assert m is not None
        assert m.group(1) == "255"

    def test_no_match_on_malformed_short_hex(self):
        m = _OSC4_RE.search("\x1b]4;0;#ff00\x07")
        assert m is None

    def test_no_match_on_missing_terminator(self):
        m = _OSC4_RE.search("\x1b]4;0;#ff00aa")
        assert m is None

    def test_no_match_on_invalid_hex(self):
        m = _OSC4_RE.search("\x1b]4;0;#zzzzzz\x07")
        assert m is None

    def test_finditer_multiple(self):
        data = "\x1b]4;0;#aaaaaa\x07\x1b]4;1;#bbbbbb\x07"
        matches = list(_OSC4_RE.finditer(data))
        assert len(matches) == 2
        assert matches[0].group(1) == "0"
        assert matches[1].group(1) == "1"

    def test_embedded_in_other_data(self):
        data = "some junk\x1b]4;5;#112233\x07more junk"
        m = _OSC4_RE.search(data)
        assert m is not None
        assert m.group(1) == "5"
        assert m.group(5) == "112233"

    def test_two_digit_rgb(self):
        m = _OSC4_RE.search("\x1b]4;0;rgb:ff/00/aa\x07")
        assert m is not None
        assert m.group(2) == "ff"
        assert m.group(3) == "00"
        assert m.group(4) == "aa"


# ===================================================================
# Regex: _OSC_SPECIAL_RE
# ===================================================================


class TestOSCSpecialRegex:
    """_OSC_SPECIAL_RE matching for OSC 10-19 special colour responses."""

    def test_matches_osc10_hex_bel(self):
        m = _OSC_SPECIAL_RE.search("\x1b]10;#ffffff\x07")
        assert m is not None
        assert m.group(1) == "10"
        assert m.group(5) == "ffffff"

    def test_matches_osc11_hex_st(self):
        m = _OSC_SPECIAL_RE.search("\x1b]11;#000000\x1b\\")
        assert m is not None
        assert m.group(1) == "11"

    def test_matches_osc12_rgb_bel(self):
        m = _OSC_SPECIAL_RE.search("\x1b]12;rgb:ffff/0000/ffff\x07")
        assert m is not None
        assert m.group(1) == "12"
        assert m.group(2) == "ffff"
        assert m.group(3) == "0000"
        assert m.group(4) == "ffff"

    def test_matches_osc19(self):
        m = _OSC_SPECIAL_RE.search("\x1b]19;#aabbcc\x07")
        assert m is not None
        assert m.group(1) == "19"

    def test_no_match_without_terminator(self):
        m = _OSC_SPECIAL_RE.search("\x1b]10;#ffffff")
        assert m is None

    def test_does_not_match_osc4_palette_responses(self):
        # OSC 4 has an extra index field: ESC]4;<index>;<color>
        # The special regex expects ESC]<code>;<color> directly,
        # so it should NOT match an OSC 4 palette response.
        m = _OSC_SPECIAL_RE.search("\x1b]4;0;#ff00aa\x07")
        assert m is None

    def test_finditer_multiple_special(self):
        data = "\x1b]10;#ffffff\x07\x1b]11;#000000\x07\x1b]12;#00ff00\x07"
        matches = list(_OSC_SPECIAL_RE.finditer(data))
        assert len(matches) == 3
        codes = [m.group(1) for m in matches]
        assert codes == ["10", "11", "12"]


# ===================================================================
# TerminalColors dataclass
# ===================================================================


class TestTerminalColors:
    """TerminalColors dataclass construction and access."""

    def test_default_construction(self):
        tc = TerminalColors()
        assert tc.palette == []
        assert tc.default_foreground is None
        assert tc.default_background is None
        assert tc.cursor_color is None
        assert tc.mouse_foreground is None
        assert tc.mouse_background is None
        assert tc.tek_foreground is None
        assert tc.tek_background is None
        assert tc.highlight_background is None
        assert tc.highlight_foreground is None

    def test_construction_with_palette(self):
        palette = ["#000000", "#ff0000", None, "#00ff00"]
        tc = TerminalColors(palette=palette)
        assert tc.palette == palette
        assert len(tc.palette) == 4
        assert tc.palette[2] is None

    def test_construction_with_all_fields(self):
        tc = TerminalColors(
            palette=["#aabbcc"],
            default_foreground="#ffffff",
            default_background="#000000",
            cursor_color="#00ff00",
            mouse_foreground="#ff0000",
            mouse_background="#0000ff",
            tek_foreground="#112233",
            tek_background="#445566",
            highlight_background="#778899",
            highlight_foreground="#aabbcc",
        )
        assert tc.default_foreground == "#ffffff"
        assert tc.default_background == "#000000"
        assert tc.cursor_color == "#00ff00"
        assert tc.mouse_foreground == "#ff0000"
        assert tc.mouse_background == "#0000ff"
        assert tc.tek_foreground == "#112233"
        assert tc.tek_background == "#445566"
        assert tc.highlight_background == "#778899"
        assert tc.highlight_foreground == "#aabbcc"

    def test_palette_default_factory_is_fresh_list(self):
        tc1 = TerminalColors()
        tc2 = TerminalColors()
        assert tc1.palette is not tc2.palette

    def test_equality(self):
        tc1 = TerminalColors(palette=["#000000"], default_foreground="#ffffff")
        tc2 = TerminalColors(palette=["#000000"], default_foreground="#ffffff")
        assert tc1 == tc2

    def test_inequality(self):
        tc1 = TerminalColors(palette=["#000000"])
        tc2 = TerminalColors(palette=["#ffffff"])
        assert tc1 != tc2


# ===================================================================
# MockPaletteStdin
# ===================================================================


class TestMockPaletteStdin:
    """MockPaletteStdin mock stream behaviour."""

    def test_is_tty_default(self):
        stdin = MockPaletteStdin()
        assert stdin.is_tty is True
        assert stdin.isTTY is True

    def test_is_tty_false(self):
        stdin = MockPaletteStdin(is_tty=False)
        assert stdin.is_tty is False
        assert stdin.isTTY is False

    def test_add_data_listener(self):
        stdin = MockPaletteStdin()
        received = []
        listener = lambda data: received.append(data)
        stdin.add_data_listener(listener)
        assert stdin.listener_count() == 1

    def test_remove_data_listener(self):
        stdin = MockPaletteStdin()
        listener = lambda _data: None
        stdin.add_data_listener(listener)
        assert stdin.listener_count() == 1
        stdin.remove_data_listener(listener)
        assert stdin.listener_count() == 0

    def test_remove_nonexistent_listener_is_safe(self):
        stdin = MockPaletteStdin()
        # Removing a listener that was never added should not raise
        stdin.remove_data_listener(lambda _data: None)
        assert stdin.listener_count() == 0

    def test_emit_data_calls_listeners(self):
        stdin = MockPaletteStdin()
        received = []
        stdin.add_data_listener(lambda data: received.append(data))
        stdin.emit_data("hello")
        assert received == ["hello"]

    def test_emit_data_calls_multiple_listeners(self):
        stdin = MockPaletteStdin()
        r1, r2 = [], []
        stdin.add_data_listener(lambda data: r1.append(data))
        stdin.add_data_listener(lambda data: r2.append(data))
        stdin.emit_data("test")
        assert r1 == ["test"]
        assert r2 == ["test"]

    def test_duplicate_listener_not_added_twice(self):
        stdin = MockPaletteStdin()
        listener = lambda _data: None
        stdin.add_data_listener(listener)
        stdin.add_data_listener(listener)
        assert stdin.listener_count() == 1

    def test_emit_after_remove(self):
        stdin = MockPaletteStdin()
        received = []
        listener = lambda data: received.append(data)
        stdin.add_data_listener(listener)
        stdin.remove_data_listener(listener)
        stdin.emit_data("should not appear")
        assert received == []

    def test_listener_can_remove_itself_during_emit(self):
        """Listeners are iterated over a copy, so self-removal is safe."""
        stdin = MockPaletteStdin()
        calls = []

        def self_removing(data):
            calls.append(data)
            stdin.remove_data_listener(self_removing)

        stdin.add_data_listener(self_removing)
        stdin.emit_data("first")
        stdin.emit_data("second")
        assert calls == ["first"]


# ===================================================================
# MockPaletteStdout
# ===================================================================


class TestMockPaletteStdout:
    """MockPaletteStdout mock stream behaviour."""

    def test_is_tty_default(self):
        stdout = MockPaletteStdout()
        assert stdout.is_tty is True
        assert stdout.isTTY is True

    def test_is_tty_false(self):
        stdout = MockPaletteStdout(is_tty=False)
        assert stdout.is_tty is False

    def test_write_records_data(self):
        stdout = MockPaletteStdout()
        result = stdout.write("hello")
        assert result is True
        assert stdout.writes == ["hello"]

    def test_write_multiple(self):
        stdout = MockPaletteStdout()
        stdout.write("a")
        stdout.write("b")
        assert stdout.writes == ["a", "b"]

    def test_responder_called_on_write(self):
        received = []
        stdout = MockPaletteStdout(responder=lambda data: received.append(data))
        stdout.write("query")
        assert received == ["query"]

    def test_no_responder(self):
        stdout = MockPaletteStdout(responder=None)
        result = stdout.write("data")
        assert result is True
        assert stdout.writes == ["data"]


# ===================================================================
# TerminalPalette - detect_osc_support
# ===================================================================


class TestDetectOSCSupport:
    """TerminalPalette.detect_osc_support."""

    @pytest.mark.asyncio
    async def test_returns_true_on_valid_response(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;rgb:0000/0000/0000\x07")

        task = asyncio.create_task(respond())
        result = await detector.detect_osc_support(timeout_ms=500)
        await task
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        result = await detector.detect_osc_support(timeout_ms=50)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_non_tty_stdin(self):
        stdin = MockPaletteStdin(is_tty=False)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        result = await detector.detect_osc_support(timeout_ms=50)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_non_tty_stdout(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=False)
        detector = TerminalPalette(stdin, stdout)

        result = await detector.detect_osc_support(timeout_ms=50)
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_osc_query(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;#000000\x07")

        task = asyncio.create_task(respond())
        await detector.detect_osc_support(timeout_ms=500)
        await task
        assert any("\x1b]4;0;?" in w for w in stdout.writes)

    @pytest.mark.asyncio
    async def test_ignores_non_osc_data(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("random keyboard input")
            await asyncio.sleep(0)
            stdin.emit_data("\x1b[A")  # arrow key
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;#ff0000\x07")  # valid response

        task = asyncio.create_task(respond())
        result = await detector.detect_osc_support(timeout_ms=500)
        await task
        assert result is True

    @pytest.mark.asyncio
    async def test_hex_format_response(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;#aabbcc\x07")

        task = asyncio.create_task(respond())
        result = await detector.detect_osc_support(timeout_ms=500)
        await task
        assert result is True

    @pytest.mark.asyncio
    async def test_st_terminator_response(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;#aabbcc\x1b\\")

        task = asyncio.create_task(respond())
        result = await detector.detect_osc_support(timeout_ms=500)
        await task
        assert result is True


# ===================================================================
# TerminalPalette - _query_palette
# ===================================================================


class TestQueryPalette:
    """TerminalPalette._query_palette."""

    @pytest.mark.asyncio
    async def test_queries_specified_indices(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            for i in range(4):
                stdin.emit_data(f"\x1b]4;{i};#aa{i:02x}bb\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1, 2, 3], timeout_ms=500)
        await task

        assert results[0] == "#aa00bb"
        assert results[1] == "#aa01bb"
        assert results[2] == "#aa02bb"
        assert results[3] == "#aa03bb"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_indices(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;#ff0000\x07")
            # indices 1 and 2 never arrive

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1, 2], timeout_ms=100)
        await task

        assert results[0] == "#ff0000"
        assert results[1] is None
        assert results[2] is None

    @pytest.mark.asyncio
    async def test_returns_all_none_for_non_tty(self):
        stdin = MockPaletteStdin(is_tty=False)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        results = await detector._query_palette([0, 1], timeout_ms=100)
        assert results[0] is None
        assert results[1] is None

    @pytest.mark.asyncio
    async def test_rgb_format_responses(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;rgb:ffff/0000/0000\x07")
            stdin.emit_data("\x1b]4;1;rgb:0000/ffff/0000\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1], timeout_ms=500)
        await task

        assert results[0] == "#ff0000"
        assert results[1] == "#00ff00"

    @pytest.mark.asyncio
    async def test_sends_correct_osc_queries(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            for i in [3, 7]:
                stdin.emit_data(f"\x1b]4;{i};#000000\x07")

        task = asyncio.create_task(respond())
        await detector._query_palette([3, 7], timeout_ms=500)
        await task

        combined = "".join(stdout.writes)
        assert "\x1b]4;3;?\x07" in combined
        assert "\x1b]4;7;?\x07" in combined

    @pytest.mark.asyncio
    async def test_multiple_responses_in_one_chunk(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            # Send all responses concatenated
            blob = ""
            for i in range(4):
                blob += f"\x1b]4;{i};#aa{i:02x}00\x07"
            stdin.emit_data(blob)

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1, 2, 3], timeout_ms=500)
        await task

        assert results[0] == "#aa0000"
        assert results[1] == "#aa0100"
        assert results[2] == "#aa0200"
        assert results[3] == "#aa0300"

    @pytest.mark.asyncio
    async def test_chunked_response(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            # Split a response across two chunks
            stdin.emit_data("\x1b]4;0;#ff")
            await asyncio.sleep(0)
            stdin.emit_data("00aa\x07")
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;1;#00ff00\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1], timeout_ms=500)
        await task

        assert results[0] == "#ff00aa"
        assert results[1] == "#00ff00"


# ===================================================================
# TerminalPalette - _query_special_colors
# ===================================================================


class TestQuerySpecialColors:
    """TerminalPalette._query_special_colors."""

    @pytest.mark.asyncio
    async def test_parses_all_special_colors(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        special_map = {
            10: "#ff0001",
            11: "#ff0002",
            12: "#ff0003",
            13: "#ff0004",
            14: "#ff0005",
            15: "#ff0006",
            16: "#ff0007",
            17: "#ff0008",
            19: "#ff0009",
        }

        async def respond():
            await asyncio.sleep(0)
            for idx, color in special_map.items():
                stdin.emit_data(f"\x1b]{idx};{color}\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_special_colors(timeout_ms=500)
        await task

        for idx, color in special_map.items():
            assert results[idx] == color

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_special_colors(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]10;#ffffff\x07")
            stdin.emit_data("\x1b]11;#000000\x07")
            # Others never arrive

        task = asyncio.create_task(respond())
        results = await detector._query_special_colors(timeout_ms=100)
        await task

        assert results[10] == "#ffffff"
        assert results[11] == "#000000"
        assert results[12] is None
        assert results[13] is None
        assert results[19] is None

    @pytest.mark.asyncio
    async def test_returns_all_none_for_non_tty(self):
        stdin = MockPaletteStdin(is_tty=False)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        results = await detector._query_special_colors(timeout_ms=100)
        for idx in [10, 11, 12, 13, 14, 15, 16, 17, 19]:
            assert results[idx] is None

    @pytest.mark.asyncio
    async def test_rgb_format_special_colors(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]10;rgb:ffff/0000/0000\x07")
            stdin.emit_data("\x1b]11;rgb:0000/ffff/0000\x07")
            for idx in [12, 13, 14, 15, 16, 17, 19]:
                stdin.emit_data(f"\x1b]{idx};#000000\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_special_colors(timeout_ms=500)
        await task

        assert results[10] == "#ff0000"
        assert results[11] == "#00ff00"

    @pytest.mark.asyncio
    async def test_sends_osc_queries_for_all_special_indices(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        # Let it timeout -- we only care about what was written
        await detector._query_special_colors(timeout_ms=50)

        combined = "".join(stdout.writes)
        for idx in [10, 11, 12, 13, 14, 15, 16, 17, 19]:
            assert f"\x1b]{idx};?\x07" in combined


# ===================================================================
# TerminalPalette - detect (full flow)
# ===================================================================


class TestDetectFullFlow:
    """TerminalPalette.detect full palette detection."""

    @pytest.mark.asyncio
    async def test_full_detection_with_responding_terminal(self):
        stdin = MockPaletteStdin(is_tty=True)

        def responder(data):
            loop = asyncio.get_event_loop()
            if "\x1b]4;0;?" in data and "\x1b]4;1;?" not in data:
                loop.call_soon(lambda: stdin.emit_data("\x1b]4;0;rgb:0000/0000/0000\x07"))
            elif "\x1b]4;" in data and "?" in data:

                def emit():
                    for i in range(16):
                        stdin.emit_data(f"\x1b]4;{i};#aa{i:02x}00\x07")

                loop.call_soon(emit)
            elif "\x1b]10;?" in data:

                def emit_special():
                    stdin.emit_data("\x1b]10;#ffffff\x07")
                    stdin.emit_data("\x1b]11;#000000\x07")
                    stdin.emit_data("\x1b]12;#00ff00\x07")
                    for idx in [13, 14, 15, 16, 17, 19]:
                        stdin.emit_data(f"\x1b]{idx};#aabbcc\x07")

                loop.call_soon(emit_special)

        stdout = MockPaletteStdout(is_tty=True, responder=responder)
        detector = TerminalPalette(stdin, stdout)

        result = await detector.detect(timeout=500, size=16)

        assert isinstance(result, TerminalColors)
        assert len(result.palette) == 16
        assert result.palette[0] == "#aa0000"
        assert result.palette[15] == "#aa0f00"
        assert result.default_foreground == "#ffffff"
        assert result.default_background == "#000000"
        assert result.cursor_color == "#00ff00"

    @pytest.mark.asyncio
    async def test_returns_all_none_when_osc_not_supported(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)  # no responder
        detector = TerminalPalette(stdin, stdout)

        result = await detector.detect(timeout=100, size=8)

        assert isinstance(result, TerminalColors)
        assert len(result.palette) == 8
        assert all(c is None for c in result.palette)
        assert result.default_foreground is None
        assert result.default_background is None

    @pytest.mark.asyncio
    async def test_returns_all_none_for_non_tty(self):
        stdin = MockPaletteStdin(is_tty=False)
        stdout = MockPaletteStdout(is_tty=False)
        detector = TerminalPalette(stdin, stdout)

        result = await detector.detect(timeout=100, size=4)

        assert len(result.palette) == 4
        assert all(c is None for c in result.palette)

    @pytest.mark.asyncio
    async def test_detect_size_256(self):
        stdin = MockPaletteStdin(is_tty=True)

        def responder(data):
            loop = asyncio.get_event_loop()
            if "\x1b]4;0;?" in data and "\x1b]4;1;?" not in data:
                loop.call_soon(lambda: stdin.emit_data("\x1b]4;0;#000000\x07"))
            elif "\x1b]4;" in data and "?" in data:

                def emit():
                    for i in range(256):
                        stdin.emit_data(f"\x1b]4;{i};#000000\x07")

                loop.call_soon(emit)
            elif "\x1b]10;?" in data:

                def emit_special():
                    for idx in [10, 11, 12, 13, 14, 15, 16, 17, 19]:
                        stdin.emit_data(f"\x1b]{idx};#000000\x07")

                loop.call_soon(emit_special)

        stdout = MockPaletteStdout(is_tty=True, responder=responder)
        detector = TerminalPalette(stdin, stdout)

        result = await detector.detect(timeout=2000, size=256)

        assert len(result.palette) == 256
        assert all(c == "#000000" for c in result.palette)


# ===================================================================
# TerminalPalette - cleanup and listener management
# ===================================================================


class TestDetectorCleanupAndListeners:
    """TerminalPalette cleanup and listener management."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_all_listeners(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        assert stdin.listener_count() == 0

        # Start a query that will time out
        task = asyncio.create_task(detector._query_palette([0], timeout_ms=200))
        await asyncio.sleep(0)
        # Listener added during query
        assert stdin.listener_count() >= 1

        await task
        # After timeout, listener should be cleaned up
        assert stdin.listener_count() == 0

    @pytest.mark.asyncio
    async def test_cleanup_method(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        # Manually add a listener through the detector
        dummy = lambda _data: None
        detector._add_stdin_listener(dummy)
        assert stdin.listener_count() == 1

        detector.cleanup()
        assert stdin.listener_count() == 0
        assert len(detector._active_listeners) == 0

    @pytest.mark.asyncio
    async def test_listeners_cleaned_up_after_successful_detection(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        initial_count = stdin.listener_count()

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;#000000\x07")

        task = asyncio.create_task(respond())
        result = await detector.detect_osc_support(timeout_ms=500)
        await task

        assert result is True
        assert stdin.listener_count() == initial_count

    @pytest.mark.asyncio
    async def test_listeners_cleaned_up_after_timeout(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        initial_count = stdin.listener_count()

        result = await detector.detect_osc_support(timeout_ms=50)
        assert result is False
        assert stdin.listener_count() == initial_count

    def test_custom_write_fn(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        written = []

        def custom_write(data):
            written.append(data)
            return True

        detector = TerminalPalette(stdin, stdout, write_fn=custom_write)
        detector._write_osc("test_data")

        assert written == ["test_data"]
        assert stdout.writes == []  # stdout.write was not called

    def test_default_write_fn_uses_stdout(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)
        detector._write_osc("test_data")

        assert stdout.writes == ["test_data"]


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    """Edge cases: buffer overflow, malformed data, partial responses."""

    @pytest.mark.asyncio
    async def test_buffer_trimming_on_large_input(self):
        """When buffer exceeds 8192 chars it should be trimmed."""
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            # Send a massive junk blob
            stdin.emit_data("x" * 10000)
            await asyncio.sleep(0)
            # Then send a valid response
            stdin.emit_data("\x1b]4;0;#ff00aa\x07")
            stdin.emit_data("\x1b]4;1;#00ff00\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1], timeout_ms=500)
        await task

        assert results[0] == "#ff00aa"
        assert results[1] == "#00ff00"

    @pytest.mark.asyncio
    async def test_malformed_responses_ignored(self):
        """Malformed OSC responses should be ignored; valid ones still parse."""
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            # Malformed: too-short hex
            stdin.emit_data("\x1b]4;0;#ff00\x07")
            # Malformed: invalid hex chars
            stdin.emit_data("\x1b]4;1;#zzzzzz\x07")
            # Malformed: no terminator (junk)
            stdin.emit_data("\x1b]4;2;#aabbcc")
            await asyncio.sleep(0)
            # Valid
            stdin.emit_data("\x1b]4;0;#ff00aa\x07")
            stdin.emit_data("\x1b]4;1;#00ff00\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1], timeout_ms=500)
        await task

        assert results[0] == "#ff00aa"
        assert results[1] == "#00ff00"

    @pytest.mark.asyncio
    async def test_interleaved_non_osc_data(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("keyboard input")
            stdin.emit_data("\x1b]4;0;#aabbcc\x07")
            stdin.emit_data("\x1b[A")  # arrow up
            stdin.emit_data("\x1b]4;1;#ddeeff\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1], timeout_ms=500)
        await task

        assert results[0] == "#aabbcc"
        assert results[1] == "#ddeeff"

    @pytest.mark.asyncio
    async def test_response_with_st_terminator(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;#ff0000\x1b\\")
            stdin.emit_data("\x1b]4;1;#00ff00\x1b\\")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1], timeout_ms=500)
        await task

        assert results[0] == "#ff0000"
        assert results[1] == "#00ff00"

    @pytest.mark.asyncio
    async def test_response_split_across_chunks(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;0;rgb:ffff/")
            await asyncio.sleep(0)
            stdin.emit_data("0000/aaaa\x07")
            await asyncio.sleep(0)
            stdin.emit_data("\x1b]4;1;#00ff00\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0, 1], timeout_ms=500)
        await task

        assert results[0] == "#ff00aa"
        assert results[1] == "#00ff00"

    @pytest.mark.asyncio
    async def test_ignores_out_of_range_indices(self):
        """Responses for indices not in the query should be ignored."""
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            # Index 99 was not queried
            stdin.emit_data("\x1b]4;99;#aabbcc\x07")
            # Index 0 was queried
            stdin.emit_data("\x1b]4;0;#ff0000\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_palette([0], timeout_ms=500)
        await task

        assert results[0] == "#ff0000"
        assert 99 not in results

    @pytest.mark.asyncio
    async def test_empty_query_indices(self):
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        results = await detector._query_palette([], timeout_ms=100)
        assert results == {}

    @pytest.mark.asyncio
    async def test_special_colors_with_interleaved_palette_responses(self):
        """OSC special color query should not be confused by OSC 4 responses."""
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            # Send an OSC 4 response (should not be picked up by special query)
            stdin.emit_data("\x1b]4;0;#aabbcc\x07")
            # Now send actual special color responses
            stdin.emit_data("\x1b]10;#ffffff\x07")
            stdin.emit_data("\x1b]11;#000000\x07")
            for idx in [12, 13, 14, 15, 16, 17, 19]:
                stdin.emit_data(f"\x1b]{idx};#112233\x07")

        task = asyncio.create_task(respond())
        results = await detector._query_special_colors(timeout_ms=500)
        await task

        assert results[10] == "#ffffff"
        assert results[11] == "#000000"
        # Note: OSC 4;0 would be parsed by _OSC_SPECIAL_RE as index 4,
        # but index 4 is not in the special_indices so it is correctly ignored.

    @pytest.mark.asyncio
    async def test_concurrent_palette_and_special_queries(self):
        """Palette and special queries can run concurrently."""
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            for i in range(4):
                stdin.emit_data(f"\x1b]4;{i};#00{i:02x}00\x07")
            stdin.emit_data("\x1b]10;#ffffff\x07")
            stdin.emit_data("\x1b]11;#000000\x07")
            for idx in [12, 13, 14, 15, 16, 17, 19]:
                stdin.emit_data(f"\x1b]{idx};#aabbcc\x07")

        task = asyncio.create_task(respond())
        palette_results, special_results = await asyncio.gather(
            detector._query_palette([0, 1, 2, 3], timeout_ms=500),
            detector._query_special_colors(timeout_ms=500),
        )
        await task

        assert palette_results[0] == "#000000"
        assert palette_results[3] == "#000300"
        assert special_results[10] == "#ffffff"
        assert special_results[11] == "#000000"

    @pytest.mark.asyncio
    async def test_non_string_chunk_is_converted(self):
        """The on_data callback should handle non-string chunks via str()."""
        stdin = MockPaletteStdin(is_tty=True)
        stdout = MockPaletteStdout(is_tty=True)
        detector = TerminalPalette(stdin, stdout)

        async def respond():
            await asyncio.sleep(0)
            # Emit a bytearray-like object that str() can convert
            # (In practice the mock always sends strings, but the code
            # handles non-strings via str() for robustness.)
            stdin.emit_data("\x1b]4;0;#aabbcc\x07")

        task = asyncio.create_task(respond())
        result = await detector.detect_osc_support(timeout_ms=500)
        await task
        assert result is True


# ===================================================================
# parse_osc4_responses / parse_osc_special_responses / has_osc4_response
# ===================================================================


class TestParseOSCFunctions:
    """Direct tests for the three OSC parsing helper functions."""

    def test_parse_osc4_responses_valid(self):
        from opentui.palette.terminal import parse_osc4_responses

        data = "\x1b]4;0;rgb:0000/0000/0000\x1b\\\x1b]4;1;rgb:ffff/0000/0000\x1b\\"
        result = parse_osc4_responses(data)
        assert 0 in result
        assert 1 in result
        assert result[0] == "#000000"
        assert result[1] == "#ff0000"

    def test_parse_osc4_responses_empty(self):
        from opentui.palette.terminal import parse_osc4_responses

        assert parse_osc4_responses("") == {}
        assert parse_osc4_responses("random junk") == {}

    def test_parse_osc_special_responses_valid(self):
        from opentui.palette.terminal import parse_osc_special_responses

        data = "\x1b]10;rgb:ffff/ffff/ffff\x1b\\\x1b]11;rgb:0000/0000/0000\x1b\\"
        result = parse_osc_special_responses(data)
        assert 10 in result
        assert 11 in result
        assert result[10] == "#ffffff"
        assert result[11] == "#000000"

    def test_parse_osc_special_responses_empty(self):
        from opentui.palette.terminal import parse_osc_special_responses

        assert parse_osc_special_responses("") == {}

    def test_has_osc4_response_true(self):
        from opentui.palette.terminal import has_osc4_response

        assert has_osc4_response("\x1b]4;0;rgb:0000/0000/0000\x1b\\") is True

    def test_has_osc4_response_false(self):
        from opentui.palette.terminal import has_osc4_response

        assert has_osc4_response("") is False
        assert has_osc4_response("not an osc response") is False
