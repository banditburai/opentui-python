"""Port of upstream terminal-capability-detection.test.ts.

Upstream: packages/core/src/lib/terminal-capability-detection.test.ts
Tests ported: 21/21
"""

import asyncio

import pytest

from opentui import create_test_renderer
from opentui.terminal_capability_detection import (
    is_capability_response,
    is_pixel_resolution_response,
    parse_pixel_resolution,
)


class TestIsCapabilityResponse:
    """Maps to describe("isCapabilityResponse")."""

    def test_detects_decrpm_responses(self):
        """Maps to test("detects DECRPM responses")."""
        assert is_capability_response("\x1b[?1016;2$y") is True
        assert is_capability_response("\x1b[?2027;0$y") is True
        assert is_capability_response("\x1b[?2031;2$y") is True
        assert is_capability_response("\x1b[?1004;1$y") is True
        assert is_capability_response("\x1b[?2026;2$y") is True
        assert is_capability_response("\x1b[?2004;2$y") is True

    def test_detects_cpr_responses_for_width_detection(self):
        """Maps to test("detects CPR responses for width detection")."""
        assert is_capability_response("\x1b[1;2R") is True  # explicit width
        assert is_capability_response("\x1b[1;3R") is True  # scaled text

    def test_does_not_detect_regular_cpr_responses_as_capabilities(self):
        """Maps to test("does not detect regular CPR responses as capabilities")."""
        assert is_capability_response("\x1b[10;5R") is False
        assert is_capability_response("\x1b[20;30R") is False

    def test_detects_xtversion_responses(self):
        """Maps to test("detects XTVersion responses")."""
        assert is_capability_response("\x1bP>|kitty(0.40.1)\x1b\\") is True
        assert is_capability_response("\x1bP>|ghostty 1.1.3\x1b\\") is True
        assert is_capability_response("\x1bP>|tmux 3.5a\x1b\\") is True

    def test_detects_kitty_graphics_responses(self):
        """Maps to test("detects Kitty graphics responses")."""
        assert is_capability_response("\x1b_Gi=1;OK\x1b\\") is True
        assert (
            is_capability_response("\x1b_Gi=1;EINVAL:Zero width/height not allowed\x1b\\") is True
        )

    def test_detects_da1_device_attributes_responses(self):
        """Maps to test("detects DA1 (Device Attributes) responses")."""
        assert is_capability_response("\x1b[?62;c") is True
        assert is_capability_response("\x1b[?62;22c") is True
        assert is_capability_response("\x1b[?1;2;4c") is True
        assert is_capability_response("\x1b[?6c") is True

    def test_detects_kitty_keyboard_query_responses(self):
        """Maps to test("detects Kitty keyboard query responses")."""
        assert is_capability_response("\x1b[?0u") is True
        assert is_capability_response("\x1b[?1u") is True
        assert is_capability_response("\x1b[?31u") is True

    def test_does_not_detect_regular_keypresses(self):
        """Maps to test("does not detect regular keypresses")."""
        assert is_capability_response("a") is False
        assert is_capability_response("A") is False
        assert is_capability_response("\x1b") is False
        assert is_capability_response("\x1ba") is False

    def test_does_not_detect_arrow_keys(self):
        """Maps to test("does not detect arrow keys")."""
        assert is_capability_response("\x1b[A") is False
        assert is_capability_response("\x1b[B") is False
        assert is_capability_response("\x1b[C") is False
        assert is_capability_response("\x1b[D") is False

    def test_does_not_detect_function_keys(self):
        """Maps to test("does not detect function keys")."""
        assert is_capability_response("\x1bOP") is False
        assert is_capability_response("\x1b[11~") is False
        assert is_capability_response("\x1b[24~") is False

    def test_does_not_detect_modified_arrow_keys(self):
        """Maps to test("does not detect modified arrow keys")."""
        assert is_capability_response("\x1b[1;2A") is False
        assert is_capability_response("\x1b[1;5C") is False

    def test_does_not_detect_mouse_sequences(self):
        """Maps to test("does not detect mouse sequences")."""
        assert is_capability_response("\x1b[<35;20;5m") is False
        assert is_capability_response("\x1b[<0;10;10M") is False


class TestIsPixelResolutionResponse:
    """Maps to describe("isPixelResolutionResponse")."""

    def test_detects_pixel_resolution_responses(self):
        """Maps to test("detects pixel resolution responses")."""
        assert is_pixel_resolution_response("\x1b[4;720;1280t") is True
        assert is_pixel_resolution_response("\x1b[4;1080;1920t") is True
        assert is_pixel_resolution_response("\x1b[4;0;0t") is True

    def test_does_not_detect_other_sequences(self):
        """Maps to test("does not detect other sequences")."""
        assert is_pixel_resolution_response("a") is False
        assert is_pixel_resolution_response("\x1b[A") is False
        assert is_pixel_resolution_response("\x1b[?1016;2$y") is False


class TestParsePixelResolution:
    """Maps to describe("parsePixelResolution")."""

    def test_parses_valid_pixel_resolution_responses(self):
        """Maps to test("parses valid pixel resolution responses")."""
        assert parse_pixel_resolution("\x1b[4;720;1280t") == {"width": 1280, "height": 720}
        assert parse_pixel_resolution("\x1b[4;1080;1920t") == {"width": 1920, "height": 1080}
        assert parse_pixel_resolution("\x1b[4;0;0t") == {"width": 0, "height": 0}

    def test_returns_none_for_invalid_sequences(self):
        """Maps to test("returns null for invalid sequences")."""
        assert parse_pixel_resolution("a") is None
        assert parse_pixel_resolution("\x1b[A") is None
        assert parse_pixel_resolution("\x1b[?1016;2$y") is None


class TestRealWorldTerminalCapabilitySequences:
    """Maps to describe("real-world terminal capability sequences")."""

    def test_kitty_terminal_full_response_individual_sequences(self):
        """Maps to test("kitty terminal full response - individual sequences")."""
        assert is_capability_response("\x1b[?1016;2$y") is True
        assert is_capability_response("\x1b[?2027;0$y") is True
        assert is_capability_response("\x1b[1;2R") is True
        assert is_capability_response("\x1b[1;3R") is True
        assert is_capability_response("\x1bP>|kitty(0.40.1)\x1b\\") is True
        assert (
            is_capability_response("\x1b_Gi=1;EINVAL:Zero width/height not allowed\x1b\\") is True
        )
        assert is_capability_response("\x1b[?62;c") is True

    def test_ghostty_terminal_response_individual_sequences(self):
        """Maps to test("ghostty terminal response - individual sequences")."""
        assert is_capability_response("\x1bP>|ghostty 1.1.3\x1b\\") is True
        assert is_capability_response("\x1b_Gi=1;OK\x1b\\") is True
        assert is_capability_response("\x1b[?62;22c") is True

    def test_alacritty_terminal_response_individual_sequences(self):
        """Maps to test("alacritty terminal response - individual sequences")."""
        assert is_capability_response("\x1b[?1016;0$y") is True
        assert is_capability_response("\x1b[?6c") is True

    def test_vscode_terminal_minimal_response(self):
        """Maps to test("vscode terminal minimal response")."""
        assert is_capability_response("\x1b[?1016;2$y") is True


class TestRendererCapabilitiesEvent:
    """Maps to describe("renderer capabilities event")."""

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture
    def setup(self, event_loop):
        s = event_loop.run_until_complete(create_test_renderer(width=80, height=24))
        yield s
        s.destroy()

    def test_kitty_terminal_emits_capabilities_event_for_each_response(self, setup):
        """Maps to test("kitty terminal emits capabilities event for each response").

        Feeds kitty terminal capability response sequences through stdin
        and verifies that a 'capabilities' event is emitted for each one.
        """
        events: list[dict] = []
        setup.renderer.on("capabilities", lambda cap: events.append(cap))

        # Ensure stdin input pipeline is wired up
        _ = setup.stdin

        # 1. DECRPM: SGR pixel mouse — ESC[?1016;2$y (mode supported, reset)
        setup.stdin.emit("data", "\x1b[?1016;2$y")
        assert len(events) == 1
        assert events[-1]["type"] == "decrpm"
        assert events[-1]["mode"] == 1016
        assert events[-1]["value"] == 2

        # 2. DECRPM: Grapheme cluster — ESC[?2027;0$y (not recognized)
        setup.stdin.emit("data", "\x1b[?2027;0$y")
        assert len(events) == 2
        assert events[-1]["type"] == "decrpm"
        assert events[-1]["mode"] == 2027
        assert events[-1]["value"] == 0

        # 3. CPR for explicit width detection — ESC[1;2R
        setup.stdin.emit("data", "\x1b[1;2R")
        assert len(events) == 3
        assert events[-1]["type"] == "cpr"
        assert events[-1]["row"] == 1
        assert events[-1]["col"] == 2

        # 4. CPR for scaled text detection — ESC[1;3R
        setup.stdin.emit("data", "\x1b[1;3R")
        assert len(events) == 4
        assert events[-1]["type"] == "cpr"
        assert events[-1]["row"] == 1
        assert events[-1]["col"] == 3

        # 5. XTVersion: kitty — ESC P >| kitty(0.40.1) ESC \
        setup.stdin.emit("data", "\x1bP>|kitty(0.40.1)\x1b\\")
        assert len(events) == 5
        assert events[-1]["type"] == "xtversion"
        assert events[-1]["name"] == "kitty"
        assert events[-1]["version"] == "0.40.1"

        # 6. Kitty graphics response — ESC _ Gi=1;EINVAL:... ESC \
        setup.stdin.emit("data", "\x1b_Gi=1;EINVAL:Zero width/height not allowed\x1b\\")
        assert len(events) == 6
        assert events[-1]["type"] == "kitty_graphics"
        assert events[-1]["supported"] is True  # EINVAL means graphics engine exists
        assert events[-1]["image_id"] == 1

        # 7. DA1 (Device Attributes) — ESC[?62;c
        setup.stdin.emit("data", "\x1b[?62;c")
        assert len(events) == 7
        assert events[-1]["type"] == "da1"
        assert events[-1]["params"] == [62]
