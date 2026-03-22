"""Port of upstream terminal-palette.test.ts.

Upstream: packages/core/src/lib/terminal-palette.test.ts
Tests: 33
"""

from __future__ import annotations

from typing import Callable

import pytest

from opentui.palette.terminal import TerminalPalette


# ---------------------------------------------------------------------------
# MockStream  -- mirrors the TypeScript EventEmitter-based MockStream
# ---------------------------------------------------------------------------


class MockStream:
    """Emulates a TTY stream with on_data / remove_listener / write."""

    def __init__(self, *, is_tty: bool = True) -> None:
        self.is_tty = is_tty
        self._handlers: list[Callable[[str], None]] = []
        self.written: list[str] = []

    # -- ReadableStream protocol --
    def on_data(self, handler: Callable[[str], None]) -> None:
        self._handlers.append(handler)

    def remove_listener(self, handler: Callable[[str], None]) -> None:
        try:
            self._handlers.remove(handler)
        except ValueError:
            pass

    # -- WritableStream protocol --
    def write(self, data: str) -> bool:
        self.written.append(data)
        return True

    # -- test helper: push data to all listeners --
    def emit(self, data: str) -> None:
        for h in list(self._handlers):
            h(data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTerminalPalette:
    """TerminalPalette"""

    class TestOSCSupportDetection:
        """OSC support detection"""

        def test_detect_osc_support_returns_true_on_response(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect_osc_support(500)
            stdin.emit("\x1b]4;0;#ff0000\x07")

            result = det.finish(default=False)
            assert result is True

        def test_detect_osc_support_returns_false_on_timeout(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect_osc_support(100)
            # No data emitted -> not supported
            result = det.finish(default=False)
            assert result is False

    class TestOSC4HexFormatParsing:
        """OSC 4 hex format parsing"""

        def test_parses_osc_4_hex_format_correctly(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})

            # Phase 1: trigger OSC support
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            # Phase 2: palette + special
            for i in range(256):
                if i == 0:
                    color = "#ff00aa"
                elif i == 1:
                    color = "#00ff00"
                elif i == 2:
                    color = "#0000ff"
                else:
                    color = "#000000"
                stdin.emit(f"\x1b]4;{i};{color}\x07")
            stdin.emit("\x1b]10;#aabbcc\x07")
            stdin.emit("\x1b]11;#ddeeff\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"
            assert result.palette[2] == "#0000ff"
            assert result.default_foreground == "#aabbcc"
            assert result.default_background == "#ddeeff"

    class TestOSC4RGBFormatParsing:
        """OSC 4 rgb format parsing"""

        def test_parses_osc_4_rgb_format_with_4_hex_digits(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b]4;0;rgb:ffff/0000/aaaa\x07")
            for i in range(1, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            import re

            assert result.palette[0] is not None
            assert re.fullmatch(r"#[0-9a-f]{6}", result.palette[0])
            assert result.palette[0] == "#ff00aa"

        def test_parses_osc_4_rgb_format_with_2_hex_digits(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b]4;0;rgb:ff/00/aa\x07")
            for i in range(1, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            import re

            assert result.palette[0] is not None
            assert re.fullmatch(r"#[0-9a-f]{6}", result.palette[0])
            assert result.palette[0] == "#ff00aa"

    class TestMultipleColorResponses:
        """Multiple color responses"""

        def test_handles_multiple_color_responses_in_single_buffer(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit(
                "\x1b]4;0;rgb:0000/0000/0000\x07"
                "\x1b]4;1;rgb:aa00/0000/0000\x07"
                "\x1b]4;2;rgb:0000/aa00/0000\x07"
                "\x1b]4;3;rgb:aa00/aa00/0000\x07"
            )
            for i in range(4, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#000000"
            assert result.palette[1] == "#a90000"
            assert result.palette[2] == "#00a900"
            assert result.palette[3] == "#a9a900"

    class TestTerminatorHandling:
        """Terminator handling"""

        def test_handles_bel_terminator(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b]4;0;#ff0000\x07")
            for i in range(1, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()
            assert result.palette[0] == "#ff0000"

        def test_handles_st_terminator(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b]4;0;#00ff00\x1b\\")
            for i in range(1, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()
            assert result.palette[0] == "#00ff00"

    class TestColorScaling:
        """Color scaling"""

        def test_scales_color_components_correctly(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b]4;0;rgb:ffff/0000/0000\x07")
            for i in range(1, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()
            assert result.palette[0] == "#ff0000"

    class TestMissingColors:
        """Missing colors"""

        def test_returns_null_for_colors_that_dont_respond(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 1000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            # Only respond with colour 0
            stdin.emit("\x1b]4;0;#ff0000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff0000"
            assert any(c is None for c in result.palette)

    class TestChunkedResponses:
        """Chunked responses"""

        def test_handles_response_split_across_chunks(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            # Split color 0 across two chunks
            stdin.emit("\x1b]4;0;#ff")
            stdin.emit("00aa\x07")

            # Split color 1 across three chunks
            stdin.emit("\x1b]4;1;rgb:0000/")
            stdin.emit("ffff/")
            stdin.emit("0000\x07")

            for i in range(2, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"

        def test_handles_response_split_mid_escape_sequence(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            # Split at ESC character
            stdin.emit("\x1b")
            stdin.emit("]4;0;#ff00aa\x07")

            # Split after ESC]
            stdin.emit("\x1b]")
            stdin.emit("4;1;#00ff00\x07")

            # Split after ESC]4
            stdin.emit("\x1b]4")
            stdin.emit(";2;#0000ff\x07")

            # Split after ESC]4;
            stdin.emit("\x1b]4;")
            stdin.emit("3;#ffff00\x07")

            for i in range(4, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"
            assert result.palette[2] == "#0000ff"
            assert result.palette[3] == "#ffff00"

    class TestMixedInputHandling:
        """Mixed input handling"""

        def test_handles_osc_response_mixed_with_mouse_events(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b]4;0;#ff00aa\x07")
            stdin.emit("\x1b[<0;10;5M")
            stdin.emit("\x1b]4;1;#00ff00\x07")
            stdin.emit("\x1b[<0;11;5M")
            stdin.emit("\x1b]4;2;#0000ff\x07")
            stdin.emit("\x1b[<0;12;5m")
            for i in range(3, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"
            assert result.palette[2] == "#0000ff"

        def test_handles_osc_response_mixed_with_key_events(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b]4;0;#ff00aa\x07")
            stdin.emit("hello")
            stdin.emit("\x1b]4;1;#00ff00\x07")
            stdin.emit("\x1b[A")
            stdin.emit("\x1b]4;2;#0000ff\x07")
            stdin.emit("\x1b[B")
            stdin.emit("\x1b]4;3;#ffff00\x07")
            for i in range(4, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"
            assert result.palette[2] == "#0000ff"
            assert result.palette[3] == "#ffff00"

        def test_handles_mixed_ansi_sequences_and_osc_responses(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b[2J")
            stdin.emit("\x1b]4;0;#ff00aa\x07")
            stdin.emit("\x1b[H")
            stdin.emit("\x1b]4;1;#00ff00\x07")
            stdin.emit("\x1b[31m")
            stdin.emit("\x1b]4;2;#0000ff\x07")
            stdin.emit("\x1b[0m")
            for i in range(3, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"
            assert result.palette[2] == "#0000ff"

    class TestComplexChunking:
        """Complex chunking"""

        def test_handles_complex_chunking_with_partial_responses(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            # Send response0 in 3-byte chunks
            response0 = "\x1b]4;0;rgb:ffff/0000/aaaa\x07"
            for i in range(0, len(response0), 3):
                stdin.emit(response0[i : i + 3])

            # Partial with junk interspersed -- colour 1 won't parse
            stdin.emit("\x1b]4;1")
            stdin.emit(";#00")
            stdin.emit("some junk data")
            stdin.emit("ff00")
            stdin.emit("\x1b[D")
            stdin.emit("\x07")

            # But then a clean colour 1 response
            stdin.emit("\x1b]4;1;#00ff00\x07")

            for i in range(2, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"

    class TestMalformedResponses:
        """Malformed responses"""

        def test_ignores_malformed_responses_and_waits_for_valid_ones(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            # Malformed: too short hex
            stdin.emit("\x1b]4;0;#ff00\x07")
            # Malformed: invalid hex chars in rgb
            stdin.emit("\x1b]4;1;rgb:gg00/0000/0000\x07")
            # Malformed: non-hex chars
            stdin.emit("\x1b]4;2;#zzzzzz\x07")

            # Valid ones
            stdin.emit("\x1b]4;0;#ff00aa\x07")
            stdin.emit("\x1b]4;1;#00ff00\x07")
            stdin.emit("\x1b]4;2;#0000ff\x07")
            for i in range(3, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"
            assert result.palette[2] == "#0000ff"

    class TestBufferOverflow:
        """Buffer overflow"""

        def test_handles_buffer_overflow_gracefully(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            # Push a massive junk blob
            stdin.emit("x" * 10000)

            stdin.emit("\x1b]4;0;#ff00aa\x07")
            stdin.emit("\x1b]4;1;#00ff00\x07")
            for i in range(2, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#ff00aa"
            assert result.palette[1] == "#00ff00"

    class TestBlobProcessing:
        """Blob processing"""

        def test_handles_all_256_colors_in_a_single_blob(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            blob = ""
            for i in range(256):
                if i == 0:
                    color = "#ff0011"
                elif i == 1:
                    color = "#00ff22"
                elif i == 255:
                    color = "#aabbcc"
                else:
                    color = "#000000"
                blob += f"\x1b]4;{i};{color}\x07"
            stdin.emit(blob)

            result = det.finish()

            assert result.palette[0] == "#ff0011"
            assert result.palette[1] == "#00ff22"
            assert result.palette[255] == "#aabbcc"
            assert len(result.palette) == 256

        def test_handles_blob_split_across_multiple_chunks(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            blob = ""
            for i in range(256):
                if i == 5:
                    color = "#112233"
                elif i == 100:
                    color = "#445566"
                elif i == 200:
                    color = "#778899"
                else:
                    color = "#000000"
                blob += f"\x1b]4;{i};{color}\x07"

            chunk_size = 500
            for j in range(0, len(blob), chunk_size):
                stdin.emit(blob[j : j + chunk_size])

            result = det.finish()

            assert result.palette[5] == "#112233"
            assert result.palette[100] == "#445566"
            assert result.palette[200] == "#778899"
            assert len(result.palette) == 256

        def test_handles_blob_with_mixed_junk_data(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            blob = ""
            for i in range(256):
                if i == 10:
                    color = "#abcdef"
                elif i == 50:
                    color = "#fedcba"
                else:
                    color = "#000000"
                blob += f"\x1b]4;{i};{color}\x07"

                if i % 20 == 0:
                    blob += "JUNK_DATA_HERE"
                if i % 30 == 0:
                    blob += "\x1b[2J\x1b[H"
                if i % 40 == 0:
                    blob += "\x1b[<0;10;5M"

            stdin.emit(blob)

            result = det.finish()

            assert result.palette[10] == "#abcdef"
            assert result.palette[50] == "#fedcba"
            assert len(result.palette) == 256

    class TestRealisticPatterns:
        """Realistic patterns"""

        def test_handles_realistic_terminal_response_pattern(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            # Chunk 1: colours 0-5
            chunk1 = ""
            for i in range(6):
                chunk1 += f"\x1b]4;{i};#ff0000\x07"
            stdin.emit(chunk1)

            # Chunk 2: colours 6-50, split in the middle
            chunk2 = ""
            for i in range(6, 51):
                chunk2 += f"\x1b]4;{i};#00ff00\x07"
            stdin.emit(chunk2[:200])
            stdin.emit(chunk2[200:])

            # Mouse event interleaved
            stdin.emit("\x1b[<35;20;10M")

            # Chunk 3: colours 51-150
            chunk3 = ""
            for i in range(51, 151):
                chunk3 += f"\x1b]4;{i};#0000ff\x07"
            stdin.emit(chunk3)

            # Chunk 4: colours 151-255
            chunk4 = ""
            for i in range(151, 256):
                chunk4 += f"\x1b]4;{i};#ffffff\x07"
            stdin.emit(chunk4)

            result = det.finish()

            assert result.palette[0] == "#ff0000"
            assert result.palette[5] == "#ff0000"
            assert result.palette[6] == "#00ff00"
            assert result.palette[50] == "#00ff00"
            assert result.palette[51] == "#0000ff"
            assert result.palette[150] == "#0000ff"
            assert result.palette[151] == "#ffffff"
            assert result.palette[255] == "#ffffff"
            assert len(result.palette) == 256

    class TestCustomWriteFunction:
        """Custom write function"""

        def test_uses_custom_write_function_when_provided(self):
            stdin = MockStream()
            stdout = MockStream()
            written_data: list[str] = []

            def custom_write(data: str) -> bool:
                written_data.append(data)
                return True

            palette = TerminalPalette(stdin, stdout, custom_write)

            det = palette.detect_osc_support(500)
            stdin.emit("\x1b]4;0;#ff0000\x07")

            result = det.finish(default=False)

            assert result is True
            assert len(written_data) == 1
            assert written_data[0] == "\x1b]4;0;?\x07"

        def test_uses_custom_write_function_for_palette_detection(self):
            stdin = MockStream()
            stdout = MockStream()
            written_data: list[str] = []

            def custom_write(data: str) -> bool:
                written_data.append(data)
                return True

            palette = TerminalPalette(stdin, stdout, custom_write)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            for i in range(256):
                stdin.emit(f"\x1b]4;{i};#aabbcc\x07")

            det.finish()

            assert len(written_data) == 3
            assert written_data[0] == "\x1b]4;0;?\x07"

            palette_query = written_data[1]
            for i in range(256):
                assert f"\x1b]4;{i};?\x07" in palette_query

            special_query = written_data[2]
            assert "\x1b]10;?\x07" in special_query
            assert "\x1b]11;?\x07" in special_query

        def test_falls_back_to_stdout_write_when_no_custom_write_function_provided(self):
            stdin = MockStream()
            stdout = MockStream()

            palette = TerminalPalette(stdin, stdout)

            det = palette.detect_osc_support(500)
            stdin.emit("\x1b]4;0;#ff0000\x07")

            result = det.finish(default=False)

            assert result is True
            assert len(stdout.written) == 1
            assert stdout.written[0] == "\x1b]4;0;?\x07"

        def test_custom_write_function_can_intercept_and_modify_output(self):
            stdin = MockStream()
            stdout = MockStream()
            intercepted_writes: list[str] = []
            actual_writes = [0]

            def custom_write(data: str) -> bool:
                intercepted_writes.append(data)
                actual_writes[0] += 1
                return True

            palette = TerminalPalette(stdin, stdout, custom_write)

            det = palette.detect_osc_support(500)
            stdin.emit("\x1b]4;0;#ff0000\x07")

            det.finish(default=False)

            assert actual_writes[0] == 1
            assert len(intercepted_writes) == 1
            assert intercepted_writes[0] == "\x1b]4;0;?\x07"

    class TestSpecialOSCColors:
        """Special OSC colors"""

        def test_detects_all_special_osc_colors_10_through_19(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            for i in range(256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")
            stdin.emit("\x1b]10;#ff0001\x07")
            stdin.emit("\x1b]11;#ff0002\x07")
            stdin.emit("\x1b]12;#ff0003\x07")
            stdin.emit("\x1b]13;#ff0004\x07")
            stdin.emit("\x1b]14;#ff0005\x07")
            stdin.emit("\x1b]15;#ff0006\x07")
            stdin.emit("\x1b]16;#ff0007\x07")
            stdin.emit("\x1b]17;#ff0008\x07")
            stdin.emit("\x1b]19;#ff0009\x07")

            result = det.finish()

            assert result.default_foreground == "#ff0001"
            assert result.default_background == "#ff0002"
            assert result.cursor_color == "#ff0003"
            assert result.mouse_foreground == "#ff0004"
            assert result.mouse_background == "#ff0005"
            assert result.tek_foreground == "#ff0006"
            assert result.tek_background == "#ff0007"
            assert result.highlight_background == "#ff0008"
            assert result.highlight_foreground == "#ff0009"

        def test_handles_special_colors_in_rgb_format(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            for i in range(256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")
            stdin.emit("\x1b]10;rgb:ffff/0000/0000\x07")
            stdin.emit("\x1b]11;rgb:0000/ffff/0000\x07")

            result = det.finish()

            assert result.default_foreground == "#ff0000"
            assert result.default_background == "#00ff00"

        def test_handles_missing_special_colors_gracefully(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            for i in range(256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")
            stdin.emit("\x1b]10;#ff0001\x07")
            stdin.emit("\x1b]11;#ff0002\x07")

            result = det.finish()

            assert result.default_foreground == "#ff0001"
            assert result.default_background == "#ff0002"
            assert result.cursor_color is None
            assert result.mouse_foreground is None
            assert result.mouse_background is None

        def test_special_colors_with_st_terminator(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            for i in range(256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")
            stdin.emit("\x1b]10;#aabbcc\x1b\\")
            stdin.emit("\x1b]11;#ddeeff\x1b\\")

            result = det.finish()

            assert result.default_foreground == "#aabbcc"
            assert result.default_background == "#ddeeff"

        def test_handles_mixed_palette_and_special_color_responses(self):
            stdin = MockStream()
            stdout = MockStream()
            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 2000, "size": 256})
            stdin.emit("\x1b]4;0;#000000\x07")
            det.advance()

            stdin.emit("\x1b]4;0;#010203\x07")
            stdin.emit("\x1b]10;#aabbcc\x07")
            stdin.emit("\x1b]4;1;#040506\x07")
            stdin.emit("\x1b]11;#ddeeff\x07")
            for i in range(2, 256):
                stdin.emit(f"\x1b]4;{i};#000000\x07")

            result = det.finish()

            assert result.palette[0] == "#010203"
            assert result.palette[1] == "#040506"
            assert result.default_foreground == "#aabbcc"
            assert result.default_background == "#ddeeff"

    class TestNonTTYHandling:
        """Non-TTY handling"""

        def test_returns_null_special_colors_on_non_tty(self):
            stdin = MockStream(is_tty=False)
            stdout = MockStream(is_tty=False)

            palette = TerminalPalette(stdin, stdout)

            det = palette.detect({"timeout": 100})
            result = det.finish()

            assert result.default_foreground is None
            assert result.default_background is None
            assert result.cursor_color is None
            assert all(c is None for c in result.palette)

        def test_returns_null_special_colors_on_osc_not_supported(self):
            stdin = MockStream()
            stdout = MockStream()

            palette = TerminalPalette(stdin, stdout)

            # Don't emit any response -> OSC not supported
            det = palette.detect({"timeout": 100})
            result = det.finish()

            assert result.default_foreground is None
            assert result.default_background is None
            assert result.cursor_color is None
            assert all(c is None for c in result.palette)
